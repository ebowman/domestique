"""Copilot-only, consented role-file patching; no native probe or model registry.

The CLI checks caller assertions, not native evidence. The native caller must
establish support before invoking the interactive writer and effective loading
before requesting workflow readiness.
"""
import difflib
import json
import re
import stat
import sys

from machine import Refusal, identity, need, writable_directory
from native import LEAVES, ROLES
from project import (exclusion_path, exclusion_remainder, installation_identity,
                     project_identity, tracked_paths)
from project_data import (HASH, LIMIT, RECEIPT, atomic_write, load, matches,
                          owned_identity, read_bytes, regular, removable, save, sha)

MARKER = "# domestique-model-setup:"
RESERVED = "configure role models"


def scalar(text):
    """Deliberately bounded YAML subset, never a YAML reformatter."""
    text = text.strip()
    need(bool(text), "empty/complex YAML scalar; repair manually")
    if text.startswith('"'):
        decoder = json.JSONDecoder()
        try:
            value, end = decoder.raw_decode(text)
        except ValueError as exc:
            raise Refusal("unsafe YAML quoted scalar; repair manually") from exc
        need(type(value) is str and (not text[end:].strip() or
             text[end:].startswith((" #", "\t#"))), "unsafe YAML scalar suffix")
        return value
    if text.startswith("'"):
        match = re.fullmatch(r"'((?:[^']|'')*)'(?:[ \t]+#.*)?", text)
        need(match is not None, "unsafe YAML single-quoted scalar")
        return match[1].replace("''", "'")
    need(not any(c in text for c in "[]{}&*!|>'\"`%@") and
         not text.startswith(("-", "?", ":", "#")) and ": " not in text and
         not re.search(r":\s*$", text), "complex/unsafe YAML; repair manually")
    return re.split(r"[ \t]+#", text, maxsplit=1)[0].rstrip()


def parse(data, role):
    need(len(data) <= LIMIT, "oversize role")
    try:
        text = data.decode("utf-8")
    except UnicodeError as exc:
        raise Refusal("role is not UTF-8; repair manually") from exc
    need("\r" not in text and not any(ord(c) < 32 and c not in "\n\t" for c in text),
         "unsupported role line endings/control bytes; repair manually")
    lines = text.splitlines(keepends=True)
    need(lines and lines[0] == "---\n", "missing bounded YAML frontmatter")
    end = next((i for i in range(1, len(lines)) if lines[i] == "---\n"), None)
    need(end is not None, "missing YAML frontmatter terminator")
    markers = [i for i, line in enumerate(lines) if MARKER in line]
    need(not markers or (role == "implementer" and markers == [1] and
                         lines[1].startswith(MARKER + " ")),
         "duplicate/misplaced setup marker; repair manually")
    marker = None
    if markers:
        def unique(pairs):
            result = {}
            for key, value in pairs:
                need(key not in result, "duplicate setup marker field")
                result[key] = value
            return result
        marker = json.loads(lines[1][len(MARKER):], object_pairs_hook=unique)
        need(type(marker) is dict and set(marker) == {
            "v", "project", "harness", "implementer_sha256", "reviewer_sha256"} and
            type(marker["v"]) is int and marker["v"] == 1 and
            type(marker["project"]) is str and marker["harness"] == "copilot" and
            all(type(marker[r + "_sha256"]) is str and
                HASH.fullmatch(marker[r + "_sha256"]) for r in ROLES),
            "malformed setup marker; repair manually")
    fields = {}
    for index in range(1, end):
        line = lines[index]
        if not line.strip() or line.startswith("#"):
            continue
        match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_-]*):[ \t]*(.*?)\n", line)
        need(match is not None, "complex/unsafe YAML frontmatter; repair manually")
        key, value = match[1], match[2]
        need(key not in fields, "duplicate YAML field; repair manually")
        # Native tools may be a flat JSON string array; retain its exact bytes.
        if key == "tools" and value.startswith("["):
            tools = json.loads(value)
            need(type(tools) is list and all(type(t) is str for t in tools),
                 "complex tools YAML; repair manually")
        else:
            scalar(value)
        fields[key] = index
    need("effort" not in fields and "model_reasoning_effort" not in fields,
         "Copilot effort is unsupported; repair manually")
    clean = "".join(line for i, line in enumerate(lines) if i not in markers).encode()
    model = scalar(lines[fields["model"]].split(":", 1)[1]) if "model" in fields else None
    if model is not None:
        raw_model = lines[fields["model"]].split(":", 1)[1].strip()
        need(raw_model.startswith(("'", '"')) or
             (model.lower() not in ("null", "~", "true", "false", "yes", "no", "on", "off") and
              not re.match(r"^[+\-0-9.]", model)),
             "non-string/ambiguous YAML model scalar; repair manually")
        selection(model)  # Bound and reject embedded model control characters.
    return lines, fields, clean, marker, model


def selection(value):
    need(type(value) is str and 0 < len(value) <= 512 and
         all(c.isprintable() for c in value) and value == value.strip(),
         "each role needs an exact model ID or inherit; control characters refused")
    return None if value == "inherit" else value


def patch_model(data, role, model):
    lines, fields, _, _, _ = parse(data, role)
    # Keep the original inline comment, even when removing an inherited field.
    if "model" in fields:
        index = fields["model"]
        original = lines[index].split(":", 1)[1].strip()
        if original.startswith('"'):
            _, end = json.JSONDecoder().raw_decode(original)
            suffix = original[end:]
        elif original.startswith("'"):
            match = re.match(r"'(?:[^']|'')*'", original)
            suffix = original[match.end():]
        else:
            match = re.search(r"[ \t]+#", original)
            suffix = original[match.start():] if match else ""
        lines[index] = ("model: " + json.dumps(model) + suffix + "\n" if model is not None
                        else (suffix.lstrip() + "\n" if suffix else ""))
    elif model is not None:
        lines.insert(1, "model: " + json.dumps(model) + "\n")
    return "".join(line for line in lines if not line.startswith(MARKER)).encode()


def context(target, machine_root, machine_receipt):
    root, project = project_identity(target)
    need(machine_root != root and machine_root not in root.parents, "managed source is not a project")
    tracked = tracked_paths(root)
    need(not any(p in tracked for p in (RECEIPT, *(LEAVES[r] for r in ROLES))),
         "tracked role/receipt refused")
    record = load(root / RECEIPT, project, installation_identity(machine_root, machine_receipt))
    need(record["state"] == "active", "role setup requires active project ownership")
    path, data = exclusion_path(project)
    exclusion_remainder(path, data, record)
    writable_directory((root / RECEIPT).parent)
    roles = {}
    for role in ROLES:
        path = root / LEAVES[role]
        info = regular(path)
        writable_directory(path.parent)
        need(owned_identity(path, record["files"][LEAVES[role]]),
             f"{role}: replaced identity; human ownership resolution required")
        data = read_bytes(path)
        roles[role] = (data, identity(path), stat.S_IMODE(info.st_mode), parse(data, role))
    return root, record, roles


def confirmed(root, record, roles):
    marker = roles["implementer"][3][3]
    return bool(marker and marker["project"] == str(root) and
                all(marker[r + "_sha256"] == sha(roles[r][3][2]) and
                    record["files"][LEAVES[r]].get("model_setup", {}).get("confirmed", True) and
                    matches(root / LEAVES[r], record["files"][LEAVES[r]].get("model_setup"))
                    for r in ROLES))


def write_setup(target, machine_root, machine_receipt, options):
    """One pair, displayed diff, interactive explicit consent, setup only."""
    need(options.get("--harness") == "copilot", "explicit native-entry --harness copilot required")
    need(options.get("--confirm-model-support"),
         "native support/availability/overrides unknown; stop, no paid probe or fallback")
    need(sys.stdin.isatty(), "noninteractive setup refused; use an interactive terminal, then reinvoke")
    chosen = {r: selection(options.get("--" + r + "-model")) for r in ROLES}
    root, record, roles = context(target, machine_root, machine_receipt)
    receipt_before = read_bytes(root / RECEIPT)
    outputs = {r: patch_model(roles[r][0], r, chosen[r]) for r in ROLES}
    marker = dict(v=1, project=str(root), harness="copilot",
                  **{r + "_sha256": sha(outputs[r]) for r in ROLES})
    outputs["implementer"] = (b"---\n" + (MARKER + " " + json.dumps(marker, sort_keys=True) +
                                        "\n").encode() + outputs["implementer"][4:])
    need(all(len(data) <= LIMIT for data in outputs.values()), "proposed role exceeds size bound")
    approved_removal = {r: removable(root / LEAVES[r], record["files"][LEAVES[r]]) for r in ROLES}
    print("Configure Domestique roles for " + json.dumps(str(root)) + " / copilot")
    for role in ROLES:
        print(json.dumps({"path": LEAVES[role], "current": roles[role][3][4],
                          "proposed": chosen[role], "inheritance": "omitted model = native default",
                          "removable": approved_removal[role]}))
        print("".join(difflib.unified_diff(
            roles[role][0].decode().splitlines(keepends=True),
            outputs[role].decode().splitlines(keepends=True),
            fromfile=LEAVES[role], tofile=LEAVES[role])), end="")
    print("Receipt: " + RECEIPT + "; record both model_setup identities/hashes/removable; "
          "creation facts unchanged. No tracked files or global/provider/auth/tool settings changed.")
    print("Caller support assertion is NOT native evidence. Save setup only / Cancel "
          "(type exactly 'Save setup only'; no default):", flush=True)
    if sys.stdin.readline().rstrip("\n") != "Save setup only":
        return "Cancelled; zero writes; no Beads or workflow."
    # Full preflight again after the human's potentially long interaction.
    _, current_record, current_roles = context(target, machine_root, machine_receipt)
    need(read_bytes(root / RECEIPT) == receipt_before and current_record == record and
         current_roles == roles, "inputs changed during consent; stop and ask again")
    changed = []
    receipt_attempted = False
    try:
        clean = roles["implementer"][3][2]
        if clean != roles["implementer"][0]:
            atomic_write(root / LEAVES["implementer"], lambda _: clean, roles["implementer"][2])
            changed.append(LEAVES["implementer"])
        for role in ("reviewer", "implementer"):
            atomic_write(root / LEAVES[role], lambda _, r=role: outputs[r], roles[role][2])
            if LEAVES[role] not in changed:
                changed.append(LEAVES[role])
        for role in ROLES:
            path = root / LEAVES[role]
            need(read_bytes(path) == outputs[role], f"{role} publication verification failed")
            record["files"][LEAVES[role]]["model_setup"] = {
                "identity": identity(path), "sha256": sha(outputs[role]),
                "removable": approved_removal[role]}
        receipt_attempted = True
        save(root / RECEIPT, record)
        changed.append(RECEIPT)
        verified_root, verified_record, verified_roles = context(target, machine_root, machine_receipt)
        need(confirmed(verified_root, verified_record, verified_roles), "receipt/pair verification failed")
    except (OSError, ValueError, Refusal) as exc:
        cleanup_errors = []
        if receipt_attempted:
            try:
                persisted = load(root / RECEIPT, record["project"], record["installation"])
                need(persisted == record or persisted == current_record,
                     "receipt changed during finalization; refusing invalidation")
                if persisted == record:
                    # Retain truthful ownership/hash/removal facts, but revoke
                    # completion after a failed publication or final check.
                    persisted["files"][LEAVES["implementer"]]["model_setup"]["confirmed"] = False
                    save(root / RECEIPT, persisted)
            except (OSError, ValueError, Refusal) as cleanup_exc:
                cleanup_errors.append(str(cleanup_exc))
        try:
            observed = context(target, machine_root, machine_receipt)
            completion = ("CONFIRMED persists; invalidation not established; "
                          "future gate may pass; human resolution required"
                          if confirmed(*observed) else "unconfirmed")
        except (OSError, ValueError, Refusal) as observation_exc:
            completion = "unverifiable: " + str(observation_exc)
        # Observe actual publications, including a save that replaced its file
        # but failed afterward. Never infer success from an attempted write.
        changed, unknown = [], []
        for path, old_data, old_identity in (
                *((root / LEAVES[r], roles[r][0], roles[r][1]) for r in ROLES),
                (root / RECEIPT, receipt_before, current_record["receipt_identity"])):
            try:
                if identity(path) != old_identity or read_bytes(path) != old_data:
                    changed.append(str(path.relative_to(root)))
            except (OSError, ValueError, Refusal):
                unknown.append(str(path.relative_to(root)))
        raise Refusal("PARTIAL role setup; changed paths: " + json.dumps(changed) +
                      "; unverifiable paths: " + json.dumps(unknown) +
                      "; cleanup errors: " + json.dumps(cleanup_errors) +
                      "; observed confirmation: " + completion +
                      "; no success or workflow authority; retry explicit preflight or resolve ownership: " +
                      str(exc)) from exc
    return ("Saved setup only; changed paths: " + json.dumps(changed) +
            ". End this request. Start a fresh Copilot client, verify exact role IDs/effective models, "
            "then explicitly reinvoke /dom-decompose or /dom-goal EPIC_ID. No automatic continuation.")
