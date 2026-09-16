"""Appendix A/B/D machine encoders and strict readers (no general record engine)."""
from .safe import (MAX_NUMBER, META_LIMIT, Refusal, need, path_value, read, sha,
                   stat, text_bounds, Path, re)
from .package import LEAVES, RELEASE, VERSION, payload_mode


def encoded(lines):
    data = "".join(k + "=" + str(v) + "\n" for k, v in lines).encode()
    return data


def record(lines):
    data = encoded(lines)
    result = data + ("checksum=" + sha(data) + "\n").encode()
    text_bounds(result)
    return result


def parse_record(data):
    lines = text_bounds(data).splitlines()
    need(lines and re.fullmatch(r"checksum=[0-9a-f]{64}", lines[-1]), "record checksum")
    need(sha(data[:-(len(lines[-1]) + 1)]) == lines[-1][9:], "record corruption")
    pairs = []
    for line in lines[:-1]:
        key, sep, value = line.partition("=")
        need(sep and key and value, "empty record field")
        pairs.append((key, value))
    need(record(pairs) == data, "noncanonical record")
    return pairs


def number(value):
    need(re.fullmatch(r"0|[1-9][0-9]*", value) and int(value) <= MAX_NUMBER,
         "invalid decimal")
    return int(value)


def machine(root, launcher, placeholder=False):
    s = root.stat() if not placeholder else None
    return [("core_root", str(root)), ("core_dev", str(s.st_dev if s else MAX_NUMBER)),
            ("core_ino", str(s.st_ino if s else MAX_NUMBER)),
            ("owner_uid", str(s.st_uid if s else MAX_NUMBER)),
            ("launcher_path", str(launcher)), ("launcher_abi", "2")]


def pair(path, data, mode):
    value = f"{path}:{sha(data)}:{mode:04o}"
    return [("created", value), ("baseline", value)]


def manifest_bytes(m, launcher_data, releases):
    need(0 < len(releases) <= 1024, "release block bounds")
    lines = [("format", "2"), ("scope", "runtime"), *m, ("core_api", "1"),
             ("adapter_abi", "2"), ("activation_format", "2"), ("helper_abi", "2")]
    lines += pair(dict(m)["launcher_path"], launcher_data, 0o755)
    for r, package in sorted(releases.items()):
        lines += [("release", r), ("version", package["version"]),
                  ("source_kind", package["source_kind"]),
                  ("official_version", package["official_version"])]
        for leaf in LEAVES:
            lines += pair(f"releases/{r}/{leaf}", package["data"][leaf], payload_mode(leaf))
        lines += [("end_release", r)]
    return record(lines)


def manifest_read(data, m, launcher_data, load):
    rows = parse_record(data)
    prefix = [("format", "2"), ("scope", "runtime"), *m, ("core_api", "1"),
              ("adapter_abi", "2"), ("activation_format", "2"), ("helper_abi", "2")]
    prefix += pair(dict(m)["launcher_path"], launcher_data, 0o755)
    need(rows[:len(prefix)] == prefix, "runtime identity/launcher provenance")
    rest = rows[len(prefix):]
    releases = {}
    official = set()
    while rest:
        need(len(releases) < 1024 and len(rest) >= 29, "release block bounds")
        (key, r), (vk, v), (sk, source), (ok, mapping) = rest[:4]
        need(key == "release" and re.fullmatch(RELEASE, r) and r not in releases
             and (not releases or r > next(reversed(releases))) and vk == "version"
             and re.fullmatch(VERSION, v) and sk == "source_kind" and
             source in ("local", "official") and ok == "official_version" and
             mapping == ("-" if source == "local" else v), "release metadata")
        if source == "official":
            need(v not in official, "duplicate official version")
            official.add(v)
        package = load(r)
        need(package["release"] == r and package["version"] == v, "release identity")
        expected = rest[:4]
        for leaf in LEAVES:
            expected += pair(f"releases/{r}/{leaf}", package["data"][leaf], payload_mode(leaf))
        expected += [("end_release", r)]
        need(rest[:len(expected)] == expected, "release creation/baseline")
        package = dict(package, source_kind=source, official_version=mapping)
        releases[r] = package
        rest = rest[len(expected):]
    need(manifest_bytes(m, launcher_data, releases) == data, "manifest encoding")
    return releases


def previous_bytes(tx, m, items, snapshots):
    lines = [("format", "2"), ("scope", "previous"), ("tx", tx),
             ("transaction_scope", "machine"), *m]
    for item in sorted(items, key=lambda i: str(i["path"]).encode()):
        p = item["path"]
        snap = snapshots[p]
        attrs, data = snap if snap is not None else (None, None)
        state = "absent" if snap is None else "directory" if data is None else "file"
        retained = data if p.name in ("active", "runtime-manifest") and data else b""
        chunks = [retained[i:i + 4000] for i in range(0, len(retained), 4000)]
        lines += [("path", p), ("state", state), ("sha256", sha(data) if data is not None else "-"),
                  ("mode", f"{stat.S_IMODE(attrs[3]):04o}" if attrs else "-"),
                  ("dev", attrs[1] if attrs else "-"), ("ino", attrs[2] if attrs else "-"),
                  ("record_bytes", len(retained)), ("record_chunks", len(chunks))]
        lines += [("record_chunk", f"{i}:{chunk.hex()}") for i, chunk in enumerate(chunks, 1)]
        lines += [("end_path", p)]
    return record(lines)


def previous_read(data, expected, validate_metadata):
    """Validate chunks independently, then exact plan/snapshot encoding."""
    rows = parse_record(data)
    index = 10  # format, scope, tx, transaction_scope, M
    while index < len(rows):
        block = rows[index:index + 8]
        need([k for k, _ in block] == ["path", "state", "sha256", "mode", "dev", "ino",
                                     "record_bytes", "record_chunks"], "previous fields")
        p, state, digest, mode, dev, ino, size, count = [v for _, v in block]
        path_value(p)
        b, c = number(size), number(count)
        need(b <= META_LIMIT and c == (b + 3999) // 4000, "previous chunk counts")
        index += 8
        chunks = []
        for i in range(1, c + 1):
            need(index < len(rows) and rows[index][0] == "record_chunk", "missing chunk")
            value = rows[index][1]
            prefix = str(i) + ":"
            need(value.startswith(prefix) and re.fullmatch(r"(?:[0-9a-f]{2})+", value[len(prefix):]),
                 "chunk encoding/order")
            chunk = bytes.fromhex(value[len(prefix):])
            need(len(chunk) == (4000 if i < c else b - 4000 * (c - 1)), "chunk size")
            chunks.append(chunk)
            index += 1
        need(index < len(rows) and rows[index] == ("end_path", p), "previous end")
        if b:
            raw = b"".join(chunks)
            need(sha(raw) == digest and state == "file" and
                 Path(p).name in ("active", "runtime-manifest"), "nonmetadata preimage")
            validate_metadata(Path(p), raw)
        index += 1
    need(data == expected, "previous plan/snapshot mismatch")


def pending_bytes(tx, m, previous, old, new, items):
    need(len(items) <= 4096, "transaction item bounds")
    lines = [("format", "2"), ("scope", "pending"), ("tx", tx),
             ("operation", "update" if old else "install"), ("transaction_scope", "machine"),
             *m, ("previous_sha256", sha(previous)), ("selected", "-"),
             ("old_release", old or "-"), ("new_release", new), ("outcome", "complete")]
    for i, item in enumerate(items, 1):
        lines += [("item", i), ("phase", item["phase"]), ("action", item["action"]),
                  ("path", item["path"]), ("after_sha256", sha(item["data"])
                   if item["data"] is not None else "-"),
                  ("after_mode", f'{item["mode"]:04o}'), ("reason", "none"), ("end_item", i)]
    return record(lines)


def published_header(tx, pending):
    data = encoded([("format", "2"), ("scope", "published"), ("tx", tx),
                    ("pending_sha256", sha(pending))])
    return data + encoded([("header_sha256", sha(data))])


def fact_bytes(previous_hash, sequence, phase, item, result, snap=None):
    attrs, data = snap if snap else (None, None)
    lines = [("sequence", sequence), ("phase", phase), ("item", item), ("result", result),
             ("provider", "-"), ("generation", "-"),
             ("sha256", sha(data) if data is not None else "-"),
             ("mode", f"{stat.S_IMODE(attrs[3]):04o}" if attrs else "-"),
             ("dev", attrs[1] if attrs else "-"), ("ino", attrs[2] if attrs else "-")]
    raw = encoded(lines)
    return raw + encoded([("fact_sha256", sha(previous_hash.encode() + b"\n" + raw))])


def published_read(data, tx, pending, items, complete=False):
    text_bounds(data)
    header = published_header(tx, pending)
    need(data.startswith(header), "published header")
    tail = data[len(header):].splitlines(keepends=True)
    need(len(tail) % 11 == 0, "torn fact")
    chain = header.splitlines()[-1].split(b"=")[1].decode()
    last = 0
    for sequence in range(1, len(tail) // 11 + 1):
        block = tail[(sequence - 1) * 11:sequence * 11]
        raw = b"".join(block[:-1])
        rows = [line.decode().rstrip("\n").split("=", 1) for line in block]
        need([r[0] for r in rows] == ["sequence", "phase", "item", "result", "provider",
             "generation", "sha256", "mode", "dev", "ino", "fact_sha256"], "fact fields")
        values = [r[1] for r in rows]
        seq, phase, idx, result, provider, generation, digest, mode, dev, ino, h = values
        need(number(seq) == sequence and provider == generation == "-" and
             h == sha(chain.encode() + b"\n" + raw), "fact hash chain")
        n = number(idx)
        if n == 0:
            need(result == "committed" and phase == "complete" and
                 digest == mode == dev == ino == "-" and last == len(items) and
                 sequence == len(tail) // 11, "premature commit")
        else:
            need(n == last + 1 and n <= len(items), "fact plan order")
            item = items[n - 1]
            need(phase == item["phase"] and result == {"mkdir": "directory-created",
                 "create": "created", "replace": "replaced"}[item["action"]] and
                 digest == (item["after_sha256"] if "after_sha256" in item else
                            sha(item["data"]) if item["data"] is not None else "-") and
                 mode == f'{item["mode"]:04o}', "fact action/result")
            number(dev)
            number(ino)
            last = n
        chain = h
    if complete:
        need(bool(tail) and len(tail) // 11 == len(items) + 1 and n == 0, "missing commit")
    return chain, len(tail) // 11


def published_prefix(data, tx, pending, items):
    """Validate ALL bytes; only a possible next fact's strict prefix may tear."""
    text_bounds(data, torn=True)
    header = published_header(tx, pending)
    need(data.startswith(header), "published header")
    tail = data[len(header):]
    lines = tail.split(b"\n")
    blocks = (len(lines) - 1) // 11
    prefix = header + b"".join(line + b"\n" for line in lines[:blocks * 11])
    chain, count = published_read(prefix, tx, pending, items)
    suffix = data[len(prefix):]
    if not suffix:
        return prefix, count
    need(count <= len(items), "bytes after committed")
    if count == len(items):
        expected = fact_bytes(chain, count + 1, "complete", 0, "committed")
        need(expected.startswith(suffix), "impossible committed prefix")
        return prefix, count
    item = items[count]
    digest = (item["after_sha256"] if "after_sha256" in item else
              sha(item["data"]) if item["data"] is not None else "-")
    fixed = encoded([("sequence", count + 1), ("phase", item["phase"]),
                     ("item", count + 1), ("result", {"mkdir": "directory-created",
                      "create": "created", "replace": "replaced"}[item["action"]]),
                     ("provider", "-"), ("generation", "-"), ("sha256", digest),
                     ("mode", f'{item["mode"]:04o}')])
    if len(suffix) < len(fixed):
        need(fixed.startswith(suffix), "impossible fact prefix")
        return prefix, count
    need(suffix.startswith(fixed), "invalid partial fact fields")
    rest = suffix[len(fixed):]
    raw = fixed
    for key in (b"dev=", b"ino="):
        if len(rest) < len(key):
            need(key.startswith(rest), "impossible fact field")
            return prefix, count
        need(rest.startswith(key), "invalid fact field")
        value, sep, remainder = rest[len(key):].partition(b"\n")
        if value:
            number(value.decode())
        else:
            need(not sep, "empty decimal")
        if not sep:
            return prefix, count
        raw += key + value + b"\n"
        rest = remainder
    checksum = encoded([("fact_sha256", sha(chain.encode() + b"\n" + raw))])
    need(checksum.startswith(rest), "impossible fact checksum prefix")
    return prefix, count
