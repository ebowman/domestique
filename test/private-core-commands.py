"""Execute only our emitted adapters against isolated, synthetic core fixtures.

This verifies serialization and shell behavior, not native client discovery.
"""
import os
import pathlib
import re
import subprocess
import sys
import tomllib

path, provider, role, root, release_a, release_b = sys.argv[1:]
root = pathlib.Path(root)
text = pathlib.Path(path).read_text()
if provider == "codex":
    text = tomllib.loads(text)["developer_instructions"]
assert str(root) in text
blocks = re.findall(r"^```bash\n(.*?)^```$", text, re.M | re.S)
assert len(blocks) == 2  # core loading + separate ephemeral routing operation
command = blocks[0]
subprocess.run(["bash", "-n"], input=command, text=True, check=True)
agent = role in ("implementer", "reviewer")
assert "read " in command and 'orchestrator "$DOMESTIQUE_BOUND_RELEASE"' in command
assert "|| stop" not in command
if agent:
    assert command.count(" bind ") == 1
    assert f'{role} "$DOMESTIQUE_BOUND_RELEASE"' in command
    assert "task-brief DOMESTIQUE_BOUND_RELEASE" in command
else:
    # No phantom orchestrator/goal dispatch IDs in skill wrappers.
    assert not re.search(r"domestique-(claude|codex|copilot)-(local-)?orchestrator", text)


def run(*args):
    # A stale inherited B must not replace explicit A, or rescue absent input.
    env = dict(os.environ, DOMESTIQUE_BOUND_RELEASE=release_b)
    return subprocess.run(
        ["bash", "-c", command, "--", *args],
        env=env, capture_output=True, text=True, check=False,
    )


def expected(tag, binding):
    prefix = "" if agent else f"DOMESTIQUE_BOUND_RELEASE={binding}\n"
    roles = "orchestrator\n" if role == "orchestrator" else f"orchestrator\n{role}\n"
    return prefix + "".join(f"{tag}:{r}\n" for r in roles.splitlines())


def reject(*args):
    result = run(*args)
    assert result.returncode != 0 and result.stdout == "" and result.stderr, result


assert (root / "active").read_text() == f"release={release_b}\n"
result = run(release_a)
assert result.returncode == 0 and result.stdout == expected("quoted", release_a), result
if agent:
    reject()  # Missing brief argument despite a valid stale environment.
    assert "missing task-brief DOMESTIQUE_BOUND_RELEASE" in run().stderr
else:
    result = run()
    assert result.returncode == 0 and result.stdout == expected("newer", release_b), result
reject("")
reject("not-a-release")
reject("<verified release identity>")

# A delegated A also works with no active pointer at all; continuation skills
# use the identical explicit protocol.
active = root / "active"
saved_active = root / "saved-active"
active.rename(saved_active)
try:
    result = run(release_a)
    assert result.returncode == 0 and result.stdout == expected("quoted", release_a), result
    if agent:
        reject()
finally:
    saved_active.rename(active)

# Removing bound A while active B is valid must never fall back to B.
bound = root / "releases" / release_a
removed = root / "removed-bound"
bound.rename(removed)
try:
    reject(release_a)
finally:
    removed.rename(bound)
print(f"{provider} {role}: serialized shell A/B, missing/invalid, no-active, removal PASS")
