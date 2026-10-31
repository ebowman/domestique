"""Synthetic lifecycle fixture ONLY: not a setup engine or native evidence.

Mutate a freshly installed scratch pair to represent confirmed inheritance with
custom instructions. No questionnaire, availability check or runtime is simulated.
"""

import hashlib
import json
from pathlib import Path
import sys

root = Path(sys.argv[1]).resolve(strict=True)
roles = root / ".claude/agents"
implementer = roles / "implementer.md"
reviewer = roles / "reviewer.md"
before_i = implementer.read_bytes()
before_r = reviewer.read_bytes()
# Current fresh installs are already confirmed. Validate/remove only that
# marker before constructing this synthetic customized pair; keep prompt bytes.
prefix = b"# domestique-model-setup: "
lines = before_i.splitlines(keepends=True)
if len(lines) > 1 and lines[1].startswith(prefix):
    installed = json.loads(lines[1][len(prefix):])
    before_i = b"".join(lines[:1] + lines[2:])
    assert installed["project"] == str(root) and installed["harness"] == "claude"
    assert installed["implementer_sha256"] == hashlib.sha256(before_i).hexdigest()
    assert installed["reviewer_sha256"] == hashlib.sha256(before_r).hexdigest()
assert before_i.count(b"model: sonnet\n") == 1
assert before_r.count(b"model: opus\n") == 1
assert b"domestique-model-setup:" not in before_i + before_r
i = before_i.replace(b"model: sonnet\n", b'model: "inherit" # fixture model comment\n')
r = before_r.replace(b"model: opus\n", b'model: "inherit"\neffort: "high"\n')
i += b"\nLOCAL IMPLEMENTER INSTRUCTIONS: preserve these bytes.\n"
r += b"\nLOCAL REVIEWER INSTRUCTIONS: preserve these bytes.\n"
marker = {
    "v": 1,
    "project": str(root),
    "harness": "claude",
    "implementer_sha256": hashlib.sha256(i).hexdigest(),
    "reviewer_sha256": hashlib.sha256(r).hexdigest(),
}
line = b"# domestique-model-setup: " + json.dumps(marker).encode() + b"\n"
assert i.startswith(b"---\n")
reviewer.write_bytes(r)
implementer.write_bytes(i[:4] + line + i[4:])
