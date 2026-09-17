"""Appendix A/C only: closed project records, never filesystem ownership claims.

Serializers accept already witnessed provenance from the internal publisher.
Parsing/equal bytes alone cannot supply that provenance.
"""
from .safe import MAX_NUMBER, need, path_value, re, sha
from .package import RELEASE, PROVIDERS
from .records import encoded, record, parse_record, number

I_KEYS = ("worktree_root", "git_dir", "git_common_dir", "worktree_dev",
          "worktree_ino", "git_dir_dev", "git_dir_ino", "git_common_dev",
          "git_common_ino", "owner_uid")
K_TAIL = (("core_api", "1"), ("adapter_abi", "2"),
          ("activation_format", "2"), ("helper_abi", "2"))
HASH = r"[0-9a-f]{64}"
STATE = ".domestique-private/v2"


def native_inventory(provider):
    need(provider in PROVIDERS, "provider")
    prefix = "domestique-v2-" + provider
    skills = {"claude": ".claude", "codex": ".agents", "copilot": ".github"}[provider]
    roles = {"claude": ".claude", "codex": ".codex", "copilot": ".github"}[provider]
    extension = {"claude": ".md", "codex": ".toml", "copilot": ".agent.md"}[provider]
    leaves = [f"{skills}/skills/{prefix}{suffix}/SKILL.md"
              for suffix in ("", "-decompose", "-goal")]
    leaves += [f"{roles}/agents/{prefix}-{role}{extension}"
               for role in ("implementer", "reviewer")]
    if provider == "codex":
        leaves.append(f"{skills}/skills/{prefix}-goal/agents/openai.yaml")
    return tuple(sorted(leaves))


def skill_ids(provider):
    need(provider in PROVIDERS, "provider")
    sigil = "$" if provider == "codex" else "/"
    return tuple(sorted(sigil + "domestique-v2-" + provider + suffix
                        for suffix in ("", "-decompose", "-goal")))


def role_id(provider, role):
    need(provider in PROVIDERS and role in ("implementer", "reviewer"), "role")
    return "domestique-v2-" + provider + "-" + role


def role_leaf(provider, role):
    rid = role_id(provider, role)
    return next(p for p in native_inventory(provider) if "/agents/" + rid + "." in p)


def patterns(providers):
    return tuple(sorted({"/" + STATE + "/", *("/" + leaf for p in providers
                                             for leaf in native_inventory(p))}))


def identity_lines(i):
    need(tuple(i) == I_KEYS, "identity fields/order")
    for k in I_KEYS[:3]:
        need(path_value(i[k]).startswith("/"), "absolute identity path")
    for k in I_KEYS[3:]:
        number(i[k])
    return list(i.items())


def core_lines(root):
    need(path_value(str(root)).startswith("/"), "absolute core")
    return [("core_root", str(root)), *K_TAIL]


def generation(prior):
    if prior is None:
        return 1
    n = prior["generation"]
    need(type(n) is int and 1 <= n <= MAX_NUMBER, "generation")
    if prior["status"] == "disabled":
        need(n < MAX_NUMBER, "generation overflow")
        return n + 1
    need(prior["status"] == "enabled", "provider status")
    return n


def leaf_value(path, value):
    digest, mode = value
    path_value(path)
    need(re.fullmatch(HASH, digest) and mode == "0644", "native hash/mode")
    return path + ":" + digest + ":" + mode


def split_leaf(value):
    parts = value.rsplit(":", 2)
    need(len(parts) == 3, "leaf framing")
    path, digest, mode = parts
    need(leaf_value(path, (digest, mode)) == value, "leaf encoding")
    return path, (digest, mode)


def provider_lines(provider, block):
    need(set(block) == {"status", "generation", "template_release", "created", "baseline"},
         "provider fields")
    need(block["status"] in ("enabled", "disabled") and
         type(block["generation"]) is int and 1 <= block["generation"] <= MAX_NUMBER and
         re.fullmatch(RELEASE, block["template_release"]), "provider values")
    inventory = native_inventory(provider)
    need(tuple(block["created"]) == tuple(block["baseline"]) == inventory,
         "provider history inventory/order")
    lines = [("provider", provider), ("status", block["status"]),
             ("generation", str(block["generation"])),
             ("template_release", block["template_release"])]
    for leaf in inventory:
        lines += [("created", leaf_value(leaf, block["created"][leaf])),
                  ("baseline", leaf_value(leaf, block["baseline"][leaf]))]
    return lines + [("end_provider", provider)]


def exclusion_block(i, created):
    need(created and tuple(created) == tuple(sorted(set(created))) and
         set(created) <= set(patterns(PROVIDERS)), "block patterns")
    h = sha(encoded(identity_lines(i)))
    return (f"# BEGIN domestique-v2 {h}\n" + "".join(p + "\n" for p in created) +
            f"# END domestique-v2 {h}\n").encode()


def project_manifest_bytes(i, root, providers, exclusions):
    need(tuple(providers) == tuple(p for p in PROVIDERS if p in providers), "provider order")
    lines = [("format", "2"), ("scope", "project"), *identity_lines(i), *core_lines(root)]
    for p, block in providers.items():
        lines += provider_lines(p, block)
    need(tuple(exclusions) == tuple(sorted(exclusions)) and
         set(exclusions) <= set(patterns(PROVIDERS)), "exclusion inventory/order")
    for pattern, (origin, digest) in exclusions.items():
        need(origin in ("created", "preexisting") and re.fullmatch(HASH, digest),
             "exclusion origin/hash")
        lines.append(("exclude", f"{pattern}:{origin}:{digest}"))
    return record(lines)


def project_manifest_read(data):
    rows = parse_record(data)
    need(len(rows) >= 17 and rows[:2] == [("format", "2"), ("scope", "project")],
         "project framing")
    i = dict(rows[2:12])
    identity_lines(i)
    root = rows[12][1]
    need(rows[12:17] == core_lines(root), "project core tuple")
    rest, providers = rows[17:], {}
    for p in PROVIDERS:
        if not rest or rest[0] != ("provider", p):
            continue
        size = 5 + 2 * len(native_inventory(p))
        part = rest[:size]
        need(len(part) == size and [k for k, _ in part[:4]] ==
             ["provider", "status", "generation", "template_release"], "provider framing")
        block = dict(status=part[1][1], generation=number(part[2][1]),
                     template_release=part[3][1], created={}, baseline={})
        for n, leaf in enumerate(native_inventory(p)):
            for offset, kind in ((0, "created"), (1, "baseline")):
                key, value = part[4 + 2*n + offset]
                path, pair = split_leaf(value)
                need(key == kind and path == leaf, "provider leaf order")
                block[kind][leaf] = pair
        need(part == provider_lines(p, block), "provider end/roundtrip")
        providers[p] = block
        rest = rest[size:]
    exclusions = {}
    for key, value in rest:
        fields = value.rsplit(":", 2)
        need(key == "exclude" and len(fields) == 3, "exclusion framing")
        pattern, origin, digest = fields
        need(pattern not in exclusions, "duplicate exclusion")
        exclusions[pattern] = (origin, digest)
    need(project_manifest_bytes(i, root, providers, exclusions) == data, "manifest roundtrip")
    return i, root, providers, exclusions


def receipt_bytes(i, root, provider, block):
    need(block["status"] == "enabled", "disabled receipt")
    return record([("format", "2"), *identity_lines(i), ("provider", provider),
                   *core_lines(root), ("generation", str(block["generation"])),
                   ("record_sha256", sha(encoded(provider_lines(provider, block)))),
                   *(("skill", s) for s in skill_ids(provider)),
                   *(("role", role_id(provider, r)) for r in ("implementer", "reviewer"))])


def receipt_read(data, i, root, provider, block):
    parse_record(data)
    need(data == receipt_bytes(i, root, provider, block), "receipt identity/record")
    return sha(data)


def binding_bytes(i, root, provider, core, gen, receipt, release, entry, adapters):
    need(len(core) == 2, "binding core identity")
    for n in core:
        number(str(n))
    need(type(gen) is int and 1 <= gen <= MAX_NUMBER and re.fullmatch(HASH, receipt) and
         re.fullmatch(RELEASE, release) and entry in skill_ids(provider), "binding fields")
    need(tuple(adapters) == native_inventory(provider), "whole provider binding")
    lines = [("format", "2"), ("scope", "binding"), *identity_lines(i),
             ("provider", provider), *core_lines(root), ("core_dev", str(core[0])),
             ("core_ino", str(core[1])), ("generation", str(gen)),
             ("receipt_sha256", receipt), ("release", release), ("entry_skill", entry)]
    lines += [("adapter", leaf_value(leaf, pair)) for leaf, pair in adapters.items()]
    lines += [("route_" + role, role_id(provider, role) + ":" +
               adapters[role_leaf(provider, role)][0]) for role in ("implementer", "reviewer")]
    return record(lines)


def binding_read(data):
    rows = parse_record(data)
    need(len(rows) >= 31 and rows[:2] == [("format", "2"), ("scope", "binding")],
         "binding framing")
    i, provider, root = dict(rows[2:12]), rows[12][1], rows[13][1]
    need(rows[12][0] == "provider" and rows[13:18] == core_lines(root), "binding tuple")
    need([k for k, _ in rows[18:24]] == ["core_dev", "core_ino", "generation",
         "receipt_sha256", "release", "entry_skill"], "binding field order")
    dev, ino, gen, receipt, release, entry = [v for _, v in rows[18:24]]
    adapters = {}
    for row in rows[24:-2]:
        need(row[0] == "adapter", "binding adapter")
        path, value = split_leaf(row[1])
        need(path not in adapters, "duplicate adapter")
        adapters[path] = value
    result = dict(i=i, root=root, provider=provider, core=(number(dev), number(ino)),
                  gen=number(gen), receipt=receipt, release=release, entry=entry,
                  adapters=adapters)
    need(binding_bytes(i, root, provider, result["core"], result["gen"], receipt,
                       release, entry, adapters) == data, "binding route/roundtrip")
    return result
