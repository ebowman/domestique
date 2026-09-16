"""Read-only installed inspection adapter; the retained engine is bundled once."""
import sys
import types
from .cli import Misuse, parse_cli, usage


def management_main(inspector):
    try:
        parsed = parse_cli(sys.argv[1:])
        if parsed["command"] == "help":
            print(usage(parsed["topic"]))
            return 0
        if parsed["command"] != "inspect":
            print("domestique2: operation unavailable; use the stable launcher", file=sys.stderr)
            return 1
        # Give dataclasses a registered, private module; never import from disk.
        name = "_domestique_v2_inspection"
        module = types.ModuleType(name)
        sys.modules[name] = module
        try:
            exec(compile(inspector, "<bundled-read-only-inspector>", "exec"), module.__dict__)
            return module.boundary_main([parsed["target"]])
        finally:
            del sys.modules[name]
    except Misuse:
        print("domestique2: invalid arguments; use help", file=sys.stderr)
        return 2
    except Exception:
        print("domestique2: inspection runtime-or-collection-failure", file=sys.stderr)
        return 1
