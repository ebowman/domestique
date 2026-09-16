"""Deterministic closed-package emission and trusted stable dispatcher bundling.

Internal Python API only, not install-v2.sh or the future public parser/fetcher.
No execution of retained shell source. No external build tool or runtime imports.
"""
import ast
import os
from pathlib import Path
from .safe import exclusive, need, physical, sha
from .package import DIRS, LEAVES, ROLES, package_header, payload_mode, verify_package
from .factories import PROVIDERS, factory

SOURCE = Path(__file__).resolve().parent


def bundle(names):
    parts = []
    for name in names:
        text = (SOURCE / (name + ".py")).read_text()
        lines = text.splitlines(keepends=True)
        imports = [(n.lineno, n.end_lineno) for n in ast.parse(text).body
                   if isinstance(n, ast.ImportFrom) and n.level]
        parts.append("".join(line for i, line in enumerate(lines, 1)
                             if not any(start <= i <= end for start, end in imports)))
    result = "\n".join(parts)
    compile(result, "<trusted-v2-bundle>", "exec")
    return result


def python_shell(program):
    # -I -S -B: no cwd/site/user imports, environment startup or bytecode writes.
    return ("#!/bin/bash\nset -eu\ncommand -v python3 >/dev/null 2>&1 || exit 1\n"
            "if [ \"$(command -v python3)\" = /usr/bin/python3 ] && "
            "[ \"$(uname -s)\" = Darwin ]; then exit 1; fi\n"
            "exec python3 -I -S -B - \"$@\" <<'DOMESTIQUE_V2_TRUSTED_PY'\n" +
            "import sys\nif sys.version_info < (3, 9): sys.exit(1)\n" +
            program + "\nDOMESTIQUE_V2_TRUSTED_PY\n").encode()


def launcher_bytes(root, home):
    return python_shell(bundle(("safe", "package", "records", "journal", "runtime")) +
                        f"\nsys.exit(launcher_main({str(root)!r}, {str(home)!r}))\n")


def package_data(version):
    refusal = (b"#!/bin/bash\n"
               b"printf '%s\\n' 'domestique2: unsupported; activation/management unavailable' >&2\n"
               b"exit 1\n")
    data = {"PACKAGE": package_header(version),
            "domestique2.sh": refusal, "update2.sh": refusal,
            # No bind/read/route/bootstrap/Beads old-policy bypass.
            "bin/resolve-core": refusal}
    for role in ROLES:
        data["roles/" + role + ".md"] = (SOURCE / "roles" / (role + ".md")).read_bytes()
    for provider in PROVIDERS:
        data["adapters/" + provider + ".templates"] = factory(provider)
    data["SHA256SUMS"] = b"".join((sha(data[p]) + "  " + p + "\n").encode()
                                  for p in sorted(data))
    need(tuple(sorted(data)) == LEAVES, "build inventory")
    return data


def emit_package(destination, version):
    """Exclusively emit a local development package; caller owns output parent."""
    destination = physical(destination)
    need(not destination.exists(), "package output collision")
    data = package_data(version)
    os.mkdir(destination, 0o700)
    for d in DIRS:
        os.mkdir(destination / d, 0o700)
    for p in LEAVES:
        exclusive(destination / p, data[p], payload_mode(p))
    return verify_package(destination, version, installed=True)
