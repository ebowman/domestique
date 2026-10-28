"""Synthetic TOML lifecycle fixture ONLY, not setup or native model evidence.

Mutate a freshly installed scratch pair, with parser-checked illustrative values.
No questionnaire, model validation, availability or native runtime is simulated.
"""

import hashlib
import json
from pathlib import Path
import sys
import tomllib

root = Path(sys.argv[1]).resolve(strict=True)
choice = sys.argv[2]
assert choice in ("explicit", "inherit")
roles = root / ".codex/agents"
implementer = roles / "implementer.toml"
reviewer = roles / "reviewer.toml"
before_i = implementer.read_bytes()
before_r = reviewer.read_bytes()
assert b"domestique-model-setup:" not in before_i + before_r

# Deliberately NOT an available model claim: exercise TOML basic-string escaping
# offline, including a quote, backslash, shell literals and non-BMP Unicode.
example = 'fixture-"quoted"\\path/$literal;$(not-executed)-é-🧪'
encoded = json.dumps(example, ensure_ascii=False).encode()
assert tomllib.loads((b"model = " + encoded).decode())["model"] == example
outputs = []
for before, model, effort, role in (
    (before_i, b"gpt-5.6-terra", b"medium", "implementer"),
    (before_r, b"gpt-5.6", b"high", "reviewer"),
):
    old_model = b'model = "' + model + b'"\n'
    old_effort = b'model_reasoning_effort = "' + effort + b'"\n'
    assert before.count(old_model) == before.count(old_effort) == 1
    replacement = b"model = " + encoded + b" # fixture model comment\n"
    if choice == "inherit":
        replacement = b"# fixture model comment\n"
    after = before.replace(old_model, replacement)
    description = next(line for line in before.splitlines(keepends=True)
                       if line.startswith(b"description = "))
    custom_description = (
        f"Codex only; never match in another harness. Host-specific {role} description"
    )
    after = after.replace(description, b"description = " +
                          json.dumps(custom_description).encode() + b"\n")
    # Exercise independent inheritance: omit model but retain reviewer effort;
    # explicit fixture retains model but omits implementer effort.
    if role == "implementer":
        after = after.replace(old_effort, b"")
    local = f"\nLOCAL {role.upper()} INSTRUCTIONS: preserve these bytes.\n"
    assert after.endswith(b'"""\n')
    after = after[:-4] + local.encode() + b'"""\n'
    after += b'\n[fixture]\nmodel = "unrelated table value"\nkeep = 42\n'
    parsed = tomllib.loads(after.decode())
    original = tomllib.loads(before.decode())
    assert parsed["name"] == role
    assert parsed["description"] == custom_description
    assert parsed["sandbox_mode"] == original["sandbox_mode"]
    assert parsed["developer_instructions"] == original["developer_instructions"] + local
    assert parsed["fixture"] == {"model": "unrelated table value", "keep": 42}
    assert parsed.get("model") == (example if choice == "explicit" else None)
    assert parsed.get("model_reasoning_effort") == ("high" if role == "reviewer" else None)
    outputs.append(after)
i, r = outputs
marker = {
    "v": 1,
    "project": str(root),
    "harness": "codex",
    "implementer_sha256": hashlib.sha256(i).hexdigest(),
    "reviewer_sha256": hashlib.sha256(r).hexdigest(),
}
line = b"# domestique-model-setup: " + json.dumps(marker).encode() + b"\n"
assert tomllib.loads((line + i).decode()) == tomllib.loads(i.decode())
reviewer.write_bytes(r)
implementer.write_bytes(line + i)
