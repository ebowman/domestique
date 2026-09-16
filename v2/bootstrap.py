"""Trusted bootstrap orchestration; public update deliberately not implemented."""
import os
import sys
from .safe import Refusal
from .package import package_from_data
from .cli import Misuse, parse_cli, usage
from .publisher import PublicationFailure, _publish, publish_local
from .transport import fetch_package


def publish_version(version, env, dry_run=False, hook=None):
    def select(packages):
        # _publish validates ALL retained mappings/packages first. A known
        # corrupt mapping can never fall through into a network overwrite.
        for package in packages.values():
            if package["official_version"] == version:
                return package
        candidate = package_from_data(fetch_package(version, env), version)
        return dict(candidate, source_kind="official", official_version=version)
    return _publish(select, env, dry_run, hook)


def bootstrap_main():
    try:
        parsed = parse_cli(sys.argv[1:], bootstrap=True)
        if parsed["command"] == "help":
            print(usage("install"))
            return 0
        if os.environ.get("DOMESTIQUE_UPDATE_SOURCE"):
            raise Misuse("DOMESTIQUE_UPDATE_SOURCE refused; use explicit selectors")
        env = dict(os.environ)
        if "source" in parsed:
            result = publish_local(parsed["source"], env, parsed.get("dry-run", False))
        else:
            result = publish_version(parsed["version"], env, parsed.get("dry-run", False))
        print("domestique2 bootstrap: runtime=" + str(result["runtime"] or "unavailable") +
              " recovery=" + result["recovery"] + " changed=" + str(result["changed"]) +
              " dry_run=" + str(result["dry_run"]))
        return 0
    except Misuse as exc:
        print("install-v2.sh: " + str(exc), file=sys.stderr)
        return 2
    except PublicationFailure as exc:
        print("install-v2.sh: " + str(exc), file=sys.stderr)
        return 1
    except Exception:
        # No raw candidate/HTTP/native content, path values or interpreter traces.
        print("install-v2.sh: verification/publication refused; preserve existing state. "
              "Unknown, edited or different development-prototype launchers are not "
              "adopted/migrated; no fallback.", file=sys.stderr)
        return 1
