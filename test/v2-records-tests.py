"""V2 A/B/D facts, bounds and failure truth; no preview selectors or clients."""
import importlib.util
import json
import os
from pathlib import Path
import stat
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("v2_publisher_fixture",
                                             Path(__file__).with_name("v2-publisher-tests.py"))
V = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(V)
from v2.publisher import PublicationFailure, publish_local
from v2.records import (encoded, fact_bytes, machine, manifest_bytes, manifest_read,
                        parse_record, pending_bytes, previous_bytes, previous_read,
                        published_header, published_read, published_prefix, record)
from v2.runtime import runtime_read
from v2.journal import recovery_state
from v2.safe import MAX_NUMBER, Refusal, sha, snapshot, text_bounds
from v2.package import verify_package


def fact_oracle(root):
    """Independent hash/framing/action oracle, not the publisher's decoder."""
    state = root / "state"
    if not (state / "published").exists():
        return []
    pending = (state / "pending").read_bytes()
    plan = parse_record(pending)
    lines = (state / "published").read_bytes().splitlines(keepends=True)
    header = dict(x.decode().rstrip("\n").split("=", 1) for x in lines[:5])
    assert header["pending_sha256"] == sha(pending)
    assert header["header_sha256"] == sha(b"".join(lines[:4]))
    chain = header["header_sha256"]
    tail = lines[5:]
    assert len(tail) % 11 == 0
    facts = []
    for i in range(0, len(tail), 11):
        block = tail[i:i + 11]
        row = dict(x.decode().rstrip("\n").split("=", 1) for x in block)
        assert row["sequence"] == str(len(facts) + 1)
        assert row["fact_sha256"] == sha(chain.encode() + b"\n" + b"".join(block[:-1]))
        chain = row["fact_sha256"]
        if row["item"] != "0":
            offset = plan.index(("item", row["item"]))
            item = dict(plan[offset:offset + 8])
            assert row["phase"] == item["phase"]
            assert row["result"] == {"mkdir": "directory-created", "create": "created",
                                      "replace": "replaced"}[item["action"]]
            assert row["sha256"] == item["after_sha256"]
            assert row["mode"] == item["after_mode"]
            p = Path(item["path"])
            assert str(p.stat().st_dev) == row["dev"]
            assert str(p.stat().st_ino) == row["ino"]
            assert f"{stat.S_IMODE(p.stat().st_mode):04o}" == row["mode"]
            assert row["sha256"] == ("-" if p.is_dir() else sha(p.read_bytes()))
        else:
            assert row["phase"] == "complete" and row["result"] == "committed"
        facts.append(row)
    return facts


class TransactionTests(unittest.TestCase):
    def test_failure_at_every_fresh_publication_boundary_truth_and_refuse_rerun(self):
        cases = [
            ("stage", None), ("before-claim", None), ("claim", "v2"),
            ("pending", None), ("previous", None), ("published", None),
            ("before-release", None), ("written-release", "PACKAGE"),
            ("after-release", "PACKAGE"), ("before-launcher", "domestique2"),
            ("written-launcher", "domestique2"), ("after-launcher", "domestique2"),
            ("before-manifest", None), ("written-manifest", None), ("after-manifest", None),
            ("before-active", None), ("before-rename-active", None),
            ("written-active", None), ("after-active", None),
            ("complete", None), ("before-clear-published", None),
            ("clear-published", None), ("clear-previous", None),
        ]
        for event, leaf in cases:
            with self.subTest(event=event), V.fixture() as s:
                p = V.source(s)
                target = verify_package(p)["release"]
                observed = []
                def fault(name, path):
                    if name == event and (leaf is None or path.name == leaf):
                        observed.append(name)
                        raise Refusal("synthetic publication fault")
                with self.assertRaises(Refusal) as error:
                    publish_local(p, s.env, hook=fault)
                self.assertEqual(observed, [event])
                selected_new = event in ("written-active", "after-active", "complete",
                                        "before-clear-published", "clear-published", "clear-previous")
                if isinstance(error.exception, PublicationFailure):
                    self.assertEqual(error.exception.selected, target if selected_new else "unavailable")
                if V.launcher(s).exists():
                    out = s.run([V.launcher(s), "version"], check=False)
                    self.assertEqual(out.returncode, 1)
                    if selected_new:
                        self.assertIn(target.encode(), out.stdout)
                        recovery = ("cleanup-pending" if event in ("complete", "before-clear-published")
                                    else "unknown" if event.startswith("clear-") else "pending")
                        self.assertIn(("recovery=" + recovery).encode(), out.stdout)
                        self.assertEqual(error.exception.recovery, recovery)
                facts = fact_oracle(V.root(s))
                if event == "written-launcher":
                    self.assertFalse((V.root(s) / "state/runtime-manifest").exists())
                    self.assertFalse(any(f["phase"] == "launcher" and f["result"] == "created"
                                         for f in facts))
                if event == "after-launcher":
                    self.assertTrue(any(f["phase"] == "launcher" and f["result"] == "created"
                                        for f in facts))
                if V.root(s).exists():
                    before = V.protected(s)
                    with self.assertRaises(Refusal):
                        publish_local(p, s.env)
                    self.assertEqual(before, V.protected(s))
                print("V2_FRESH_FAULT=" + json.dumps({"event": event, "facts": len(facts),
                                                     "runtime": target if selected_new else "unavailable"}))

    def test_update_faults_preserve_old_or_report_actual_new_and_metadata_only_previous(self):
        for event in ("pending", "written-release", "before-manifest", "written-manifest",
                      "before-active", "before-rename-active", "written-active",
                      "after-active", "complete", "clear-published", "clear-previous"):
            with self.subTest(event=event), V.fixture() as s:
                first = V.source(s)
                old = publish_local(first, s.env)["runtime"]
                old_active = (V.root(s) / "active").read_bytes()
                old_manifest = (V.root(s) / "state/runtime-manifest").read_bytes()
                old_launcher = snapshot(V.launcher(s))
                p = V.source(s, "2.1.0", "new")
                new = verify_package(p)["release"]
                def fault(name, path):
                    if name == event:
                        raise Refusal("update synthetic fault")
                    if name in ("before-launcher", "written-launcher", "after-launcher"):
                        self.fail("compatible launcher phase must have no writes")
                with self.assertRaises(PublicationFailure) as error:
                    publish_local(p, s.env, hook=fault)
                changed = event in ("written-active", "after-active", "complete",
                                    "clear-published", "clear-previous")
                expected = new if changed else old
                self.assertEqual(error.exception.selected, expected)
                self.assertEqual(snapshot(V.launcher(s)), old_launcher)
                self.assertEqual(verify_package(V.root(s) / "releases" / old)["release"], old)
                out = s.run([V.launcher(s), "version"], check=False)
                self.assertEqual(out.returncode, 1)
                self.assertIn(expected.encode(), out.stdout)
                recovery = ("cleanup-pending" if event == "complete" else "unknown"
                            if event in ("pending", "clear-published", "clear-previous") else "pending")
                self.assertIn(("recovery=" + recovery).encode(), out.stdout)
                self.assertEqual(error.exception.recovery, recovery)
                if event not in ("pending", "clear-previous"):
                    rows = parse_record((V.root(s) / "state/previous").read_bytes())
                    retained = {}
                    current = None
                    for key, value in rows:
                        if key == "path":
                            current = value
                        elif key == "record_chunk":
                            retained[current] = retained.get(current, b"") + bytes.fromhex(value.split(":", 1)[1])
                    self.assertEqual(retained, {str(V.root(s) / "active"): old_active,
                                               str(V.root(s) / "state/runtime-manifest"): old_manifest})
                    self.assertNotIn(str(p).encode(), (V.root(s) / "state/previous").read_bytes())
                fact_oracle(V.root(s))
                before = V.protected(s)
                with self.assertRaises(Refusal):
                    publish_local(p, s.env)
                self.assertEqual(before, V.protected(s))
                print("V2_UPDATE_FAULT=" + event + " runtime=" + expected)

    def test_fresh_launcher_static_help_exception_never_certifies_runtime(self):
        with V.fixture() as s:
            events = []
            def witness(event, path):
                if event == "after-launcher" and path.name == "domestique2":
                    self.assertFalse((V.root(s) / "state/runtime-manifest").exists())
                    self.assertFalse((V.root(s) / "active").exists())
                    events.append("launcher-before-manifest")
                if event == "after-manifest":
                    self.assertFalse((V.root(s) / "active").exists())
                    events.append("manifest-before-active")
                if event == "after-manifest" or event == "after-launcher" and path.name == "domestique2":
                    before = V.protected(s)
                    for arg in ("--help", "-h", "help"):
                        out = s.run([V.launcher(s), arg], check=False)
                        self.assertEqual((out.returncode, out.stderr), (0, b""))
                        self.assertNotIn(b"runtime=", out.stdout)
                    for arg in ("version", "--version", "enable", "inspect", "update",
                                "read", "start", "route", "bootstrap", "beads", "bind", "goal"):
                        out = s.run([V.launcher(s), arg], check=False)
                        self.assertEqual((out.returncode, out.stdout), (1, b""))
                    self.assertEqual(before, V.protected(s))
            publish_local(V.source(s), s.env, hook=witness)
            self.assertEqual(events, ["launcher-before-manifest", "manifest-before-active"])

    def test_static_help_has_no_filesystem_discovery(self):
        from v2.runtime import launcher_main
        with patch("v2.runtime.physical", side_effect=AssertionError("filesystem discovery")), \
                patch("v2.runtime.runtime_read", side_effect=AssertionError("runtime discovery")), \
                patch("v2.runtime.read", side_effect=AssertionError("file read")):
            for arg in ("--help", "-h", "help"):
                with patch("sys.argv", ["domestique2", arg]):
                    self.assertEqual(launcher_main("/unavailable", "/unavailable"), 0)

    def test_identity_race_release_collision_and_active_replacement_race(self):
        for event in ("before-release", "before-rename-active"):
            with self.subTest(event=event), V.fixture() as s:
                p = V.source(s)
                publish_local(p, s.env)
                p = V.source(s, "2.1.0", "next")
                def race(name, path):
                    if name == event:
                        if event == "before-release":
                            path.mkdir()
                        else:
                            raw = path.read_bytes()
                            path.unlink()
                            path.write_bytes(raw)
                            path.chmod(0o600)
                with self.assertRaises(PublicationFailure):
                    publish_local(p, s.env, hook=race)
                self.assertTrue((V.root(s) / "state/pending").exists())

    def test_torn_facts_orphans_corrupt_identity_and_no_ownership_from_intent(self):
        with V.fixture() as s:
            publish_local(V.source(s), s.env)
            p = V.source(s, "2.1.0", "next")
            def fault(event, path):
                if event == "before-active":
                    raise Refusal("synthetic")
            with self.assertRaises(PublicationFailure):
                publish_local(p, s.env, hook=fault)
            g, launch = V.root(s), V.launcher(s)
            classify = lambda: recovery_state(g, launch, launch.read_bytes())
            self.assertEqual(classify(), "pending")
            published = g / "state/published"
            data = published.read_bytes()
            published.write_bytes(data[:-20])
            self.assertEqual(classify(), "pending")
            published.write_bytes(data.replace(b"result=created", b"result=replaced", 1))
            self.assertEqual(classify(), "unknown")
            published.write_bytes(data)
            pending = g / "state/pending"
            rows = parse_record(pending.read_bytes())
            pending.write_bytes(record([(k, "0" if k == "core_ino" else v) for k, v in rows]))
            self.assertEqual(classify(), "unknown")
            pending.write_bytes(record(rows))
            published.unlink()
            self.assertEqual(classify(), "unknown")
            with self.assertRaises(Refusal):
                publish_local(p, s.env)

    def test_all_observed_journal_bytes_including_malformed_torn_suffix(self):
        with V.fixture() as s:
            publish_local(V.source(s), s.env)
            def fault(event, path):
                if event == "before-active":
                    raise Refusal("synthetic")
            with self.assertRaises(PublicationFailure):
                publish_local(V.source(s, "2.1.0", "next"), s.env, hook=fault)
            g, launch = V.root(s), V.launcher(s)
            published = g / "state/published"
            data = published.read_bytes()
            classify = lambda: recovery_state(g, launch, launch.read_bytes())
            variants = {"original-9001": b"x" * 9001, "original-NUL": b"x\x00y",
                        "aggregate": b"x\n" * 524289, "line-count": b"x\n" * 16385,
                        "impossible-field": b"not_sequence=", "wrong-order": b"sequence=0",
                        "leading-zero": b"sequence=01"}
            for label, value in (("utf8", b"\xff"), ("utf8-torn", b"\xc3"),
                                 ("NUL", b"\x00"), ("tab", b"\t"), ("CR", b"\r"),
                                 ("DEL", b"\x7f"), ("C1", b"\xc2\x85"),
                                 ("BOM", b"\xef\xbb\xbf"), ("line-bound", b"x" * 8192)):
                for ending in (b"", b"\n"):
                    variants[label + ("-complete" if ending else "-torn")] = value + ending
            for label, suffix in variants.items():
                published.write_bytes(data + suffix)
                before = s.snapshot()
                self.assertEqual(classify(), "unknown", label)
                self.assertEqual(before, s.snapshot(), label)
                self.assertEqual(published.read_bytes(), data + suffix)
                print("V2_JOURNAL_UNKNOWN=" + label)
            for cut in (1, 20, 65, 80, 130):
                published.write_bytes(data[:-cut])
                before = s.snapshot()
                self.assertEqual(classify(), "pending")
                self.assertEqual(before, s.snapshot())
            published.write_bytes(data)
            self.assertEqual(classify(), "pending")


class RecordTests(unittest.TestCase):
    def test_manifest_strict_fields_order_identity_pairs_and_complete_leaves(self):
        with V.fixture() as s:
            result = publish_local(V.source(s), s.env)
            g, launch = V.root(s), V.launcher(s)
            raw = (g / "state/runtime-manifest").read_bytes()
            rows = parse_record(raw)
            m = machine(g, launch)
            load = lambda r: verify_package(g / "releases" / r, installed=True)
            self.assertIn(result["runtime"], manifest_read(raw, m, launch.read_bytes(), load))
            variants = [
                rows + [("unknown", "x")], rows[:-1], [rows[1], rows[0], *rows[2:]],
                [(k, "1" if k == "format" else v) for k, v in rows],
                [(k, "0" if k == "core_ino" else v) for k, v in rows],
                [(k, "official" if k == "source_kind" else v) for k, v in rows],
                [row for row in rows if row[0] != "baseline"],
                [(k, v.replace(":0755", ":0644") if k == "created" else v) for k, v in rows],
                [*rows, *rows[14:]],
            ]
            for variant in variants:
                with self.assertRaises(Refusal):
                    manifest_read(record(variant), m, launch.read_bytes(), load)
            with self.assertRaises(Refusal):
                parse_record(raw[:-5])

    def test_previous_chunk_boundaries_corruption_order_and_metadata_only(self):
        with V.fixture() as s:
            g = V.root(s)
            g.mkdir(parents=True)
            m = machine(g, V.launcher(s))
            for size in (4000, 4001, 8000, 8001):
                p = g / "runtime-manifest"
                raw = b"n" * size  # Hex includes a-f, so uppercase is genuinely invalid.
                p.write_bytes(raw)
                p.chmod(0o600)
                items = [dict(path=p)]
                previous = previous_bytes("a" * 32, m, items, {p: snapshot(p)})
                seen = []
                previous_read(previous, previous, lambda path, data: seen.append((path, data)))
                self.assertEqual(seen, [(p, raw)])
                rows = parse_record(previous)
                chunks = [v for k, v in rows if k == "record_chunk"]
                self.assertEqual(len(chunks), (size + 3999) // 4000)
                bad = [
                    [r for r in rows if r != ("record_chunk", chunks[0])],
                    rows + [("record_chunk", chunks[0])],
                    [(k, v[:-2] if k == "record_chunk" else v) for k, v in rows],
                    [(k, "2:" + v.split(":", 1)[1] if k == "record_chunk" else v) for k, v in rows],
                    [(k, v.upper() if k == "record_chunk" else v) for k, v in rows],
                ]
                for variant in bad:
                    with self.assertRaises(Refusal):
                        previous_read(record(variant), previous, lambda *_: None)

    def test_fact_hash_chain_torn_wrong_action_order_and_commit(self):
        tx = "a" * 32
        pending = b"synthetic trusted plan\n"
        item = dict(phase="release", action="create", data=b"body", mode=0o644)
        header = published_header(tx, pending)
        h = header.splitlines()[-1].split(b"=")[1].decode()
        snap = ((os.getuid(), 1, 2, stat.S_IFREG | 0o644, 1, 4, 0, 0), b"body")
        fact = fact_bytes(h, 1, "release", 1, "created", snap)
        h2 = fact.splitlines()[-1].split(b"=")[1].decode()
        complete = header + fact + fact_bytes(h2, 2, "complete", 0, "committed")
        self.assertEqual(published_read(complete, tx, pending, [item], True)[1], 2)
        for raw in (complete[:-1], complete[:-20], header + fact[:-10],
                    header + fact.replace(b"created", b"replaced"), header + fact + fact,
                    header + fact_bytes(h, 1, "complete", 0, "committed")):
            with self.assertRaises(Refusal):
                published_read(raw, tx, pending, [item], True)

    def test_every_possible_fact_prefix_and_impossible_torn_fields(self):
        tx, pending = "a" * 32, b"trusted plan\n"
        item = dict(phase="release", action="create", data=b"body", mode=0o644)
        header = published_header(tx, pending)
        chain = header.splitlines()[-1].split(b"=")[1].decode()
        snap = ((os.getuid(), 12, 34, stat.S_IFREG | 0o644, 1, 4, 0, 0), b"body")
        fact = fact_bytes(chain, 1, "release", 1, "created", snap)
        for cut in range(len(fact)):
            self.assertEqual(published_prefix(header + fact[:cut], tx, pending, [item]), (header, 0))
        complete = fact_bytes(fact.splitlines()[-1].split(b"=")[1].decode(), 2, "complete", 0, "committed")
        for cut in range(len(complete)):
            self.assertEqual(published_prefix(header + fact + complete[:cut], tx, pending, [item]),
                             (header + fact, 1))
        for before, after in ((b"sequence=1", b"sequence=2"), (b"phase=release", b"phase=active"),
                              (b"result=created", b"result=replaced"), (b"provider=-", b"provider=c"),
                              (b"mode=0644", b"mode=0755"), (b"dev=12", b"dev=01"),
                              (b"ino=34", b"ino=" + str(MAX_NUMBER + 1).encode())):
            bad = fact[:fact.index(before)] + after
            with self.assertRaises(Refusal):
                published_prefix(header + bad, tx, pending, [item])
        with self.assertRaises(Refusal):
            published_prefix(header + fact[:-2] + b"Z", tx, pending, [item])
        with self.assertRaises(Refusal):
            published_prefix(header + fact + complete + b"s", tx, pending, [item])

    def test_aggregate_metadata_line_item_and_release_overflow(self):
        for raw in (b"x" * 1048576 + b"\n", b"x" * 8192 + b"\n", b"x\n" * 16385):
            with self.assertRaises(Refusal):
                text_bounds(raw)
        with self.assertRaises(Refusal):
            pending_bytes("a" * 32, [], b"", None, "r-" + "a" * 64, [None] * 4097)
        with self.assertRaises(Refusal):
            manifest_bytes([], b"", dict.fromkeys(range(1025)))
        with V.fixture() as s:
            p = V.source(s)
            before = V.protected(s)
            # Force max encoded facts over A's limit; preflight must precede claims.
            oversized_fact = b"sequence=" + b"1" * 1048577 + b"\nfact_sha256=" + b"a" * 64 + b"\n"
            with patch("v2.publisher.fact_bytes", return_value=oversized_fact):
                with self.assertRaises(Refusal):
                    publish_local(p, s.env)
            self.assertEqual(before, V.protected(s))


if __name__ == "__main__":
    unittest.main()
