"""Fake CLI only: no database, backend, native client, model or workflow engine."""
import json
import os
from pathlib import Path
import sys

args = sys.argv[1:]
state = os.environ.get("FAKE_BD_STATE", "ok")
project = os.environ["FAKE_BD_PROJECT"]
scoped = len(args) >= 3 and args[:2] == ["-C", project]
allowed = args == ["--version"] or scoped
exit_code = 0 if allowed else 98
if state == "bad-state" and scoped:
    exit_code = 31
if state == "fail-version" and args == ["--version"]:
    exit_code = 32
effects = []
output = "fake bd fixture"
if scoped:
    operation = args[2:]
    if operation == ["status"]:
        output = "fake configured project status"
    elif operation[:1] == ["create"]:
        output = "fixture-epic" if "epic" in operation else "fixture-epic.1"
        effects = ["fake-plan-record"]
    elif operation == ["ready", "--parent", "fixture-epic"]:
        output = "[]"  # deliberately not evidence of epic completion
    elif operation == ["list", "--parent", "fixture-epic", "--all"]:
        output = '[{"id":"fixture-epic.1","status":"blocked"}]'
    elif operation in (["show", "fixture-epic.1"],
                       ["update", "fixture-epic.1", "--claim"],
                       ["close", "fixture-epic.1"]):
        output = "fixture task result"
        effects = ["fake-" + operation[0]] if operation[0] != "show" else []
    else:
        exit_code = 98
if exit_code:
    effects = []
    output = "FAKE-PRIVATE-CONFIG should not leak from readiness failure"
record = {"argv": args, "cwd": os.getcwd(), "exit": exit_code, "effects": effects,
          "retarget_keys": sorted(k for k in os.environ if k.startswith(("GIT_", "BEADS_", "BD_")))}
with Path(os.environ["FAKE_BD_LOG"]).open("a") as stream:
    stream.write(json.dumps(record) + "\n")
print(output, file=sys.stderr if exit_code else sys.stdout)
sys.exit(exit_code)
