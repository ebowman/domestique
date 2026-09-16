#!/usr/bin/env python3
"""ONE before/after global-all + local-all fixture, no native clients/DB.

Uses the reviewed runner's supervision; 120s/operation, 300s overall.
The baseline is current source with only the path helper block/emission list
restored from the checksum-pinned 20b6fe8 fixture. Both runs reuse the exact
same isolated topology. Explicit opt-in only; not an acceptance suite.
"""
import importlib.util
from pathlib import Path
import shutil
import tempfile
import time

from global_path_baseline import baseline

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("acceptance", ROOT / "test/acceptance.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def main(restore=baseline, prefix="dom-path-timing-"):
    control = runner.Control(300)
    with tempfile.TemporaryDirectory(prefix=prefix) as tmp:
        work = Path(tmp).resolve()
        env = runner.environment(work)
        current = runner.preview_fixture.source().decode()
        timings = {}
        completed = 0
        for label, source in (("before", restore(current)), ("after", current)):
            control.check()
            script = work / "installer.sh"
            script.write_text(source)
            scope = work / "scope"
            scope.mkdir()
            project = work / "project"
            project.mkdir()
            env["DOMESTIQUE_HOME"] = str(scope / "core")
            _, err, rc = runner.execute(
                ["git", "-C", str(project), "init", "-q"], env, 10, control)
            if rc:
                raise RuntimeError(err)
            for operation, args in (
                ("global", ["--global", "--platform", "all"]),
                ("local", ["--local", str(project), "--platform", "all"]),
            ):
                begin = time.monotonic()
                out, err, rc = runner.execute(
                    ["/bin/bash", str(script), *args], env, 120, control)
                elapsed = time.monotonic() - begin
                print(f"{label} {operation}: {elapsed:.3f}s rc={rc}", flush=True)
                if rc:
                    raise RuntimeError(out + err)
                timings[label, operation] = elapsed
                completed += 1
            # Only our newly created temporary fixture; never retained fixtures.
            for path in (scope, project, work / "home"):
                shutil.rmtree(path)
            (work / "home").mkdir()
        for operation in ("global", "local"):
            ratio = timings["before", operation] / timings["after", operation]
            saved = timings["before", operation] - timings["after", operation]
            print(f"{operation} measured speedup: {ratio:.3f}x; saved {saved:.3f}s", flush=True)
        print(f"completed operations: {completed} (1 global-all + 1 local-all per source)",
              flush=True)


if __name__ == "__main__":
    main()
