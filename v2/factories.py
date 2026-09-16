"""Inert native serialization factories. Publication/admission belongs to hq-5jc.7.

These templates are data in the package, not globally discoverable files.
One protected loader text and four shared policies, never three engines.
"""
import json

PROVIDERS = ("claude", "codex", "copilot")
LOADER = (
    "Activation guards are unavailable in this checkpoint. STOP before reading\n"
    "any shared workflow body, delegation, client or Beads operation.\n"
    "Future guarded loader: releases/R/bin/resolve-core start G W PROVIDER SKILL;\n"
    "retain its complete BINDING for same-R read/route; never use an old helper,\n"
    "global role, active-resampled helper or unguarded policy as fallback.\n"
)


def factory(provider):
    if provider not in PROVIDERS:
        raise ValueError("unknown provider")
    prefix = "domestique-v2-" + provider
    skill_root = {"claude": ".claude", "codex": ".agents", "copilot": ".github"}[provider]
    role_root = {"claude": ".claude", "codex": ".codex", "copilot": ".github"}[provider]
    leaves = {}
    for suffix in ("", "-decompose", "-goal"):
        name = prefix + suffix
        meta = f"---\nname: {name}\ndescription: Explicit private Domestique workflow\n"
        if suffix == "-goal" and provider != "codex":
            meta += "disable-model-invocation: true\n"
        leaves[f"{skill_root}/skills/{name}/SKILL.md"] = meta + "---\n" + LOADER
    if provider == "codex":
        leaves[f".agents/skills/{prefix}-goal/agents/openai.yaml"] = (
            "policy:\n  allow_implicit_invocation: false\n")
    for role in ("implementer", "reviewer"):
        name = prefix + "-" + role
        if provider == "codex":
            leaves[f"{role_root}/agents/{name}.toml"] = (
                f'name = "{name}"\ndescription = "Private Domestique {role}"\n'
                'developer_instructions = """\n' + LOADER + '"""\n')
        else:
            extension = ".agent.md" if provider == "copilot" else ".md"
            leaves[f"{role_root}/agents/{name}{extension}"] = (
                f"---\nname: {name}\ndescription: Private Domestique {role}\n---\n" + LOADER)
    return (json.dumps(leaves, sort_keys=True, ensure_ascii=True, separators=(",", ":")) +
            "\n").encode()
