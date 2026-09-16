"""Frozen V2/1 argv grammar. Parsing never discovers files or runs operations."""
import re
from .safe import Refusal
from .package import VERSION

COMMANDS = ("enable", "disable", "update", "inspect", "retire-global", "version", "help")
PLATFORMS = ("claude", "codex", "copilot", "both", "claude-copilot",
             "codex-copilot", "all")


class Misuse(Refusal):
    pass


def argument(ok):
    if not ok:
        raise Misuse("invalid arguments; use help")


def literal(value):
    argument(bool(value) and len(value.encode("utf-8")) <= 4096 and
             not any(ord(c) < 32 or 127 <= ord(c) <= 159 for c in value))
    return value


def parse_cli(argv, bootstrap=False):
    args = list(argv)
    if "--" in args:
        argument(args.count("--") == 1 and args[-1] == "--")
        args.pop()
    if bootstrap:
        if args in (["--help"], ["-h"], ["help"]):
            return {"command": "help", "topic": "install"}
        command = "install"
    else:
        if not args:
            return {"command": "bare", "target": "."}
        if args in (["--help"], ["-h"]):
            return {"command": "help", "topic": None}
        if args == ["--version"]:
            return {"command": "version"}
        if args[0] == "--inspect":
            args[0] = "inspect"
        elif len(args) == 2 and args[-1] == "--inspect":
            argument(not args[0].startswith("-"))
            args = ["inspect", args[0]]
        command = args.pop(0)
        argument(command in COMMANDS)
        if args in (["--help"], ["-h"]):
            return {"command": "help", "topic": command}
        if command == "help":
            argument(len(args) <= 1 and (not args or args[0] in COMMANDS))
            return {"command": "help", "topic": args[0] if args else None}
    result = {"command": command}
    allowed = {
        "install": ("source", "version", "dry-run"),
        "update": ("source", "version", "dry-run"),
        "enable": ("platform", "dry-run"), "disable": ("platform", "dry-run"),
        "retire-global": ("platform", "dry-run"), "inspect": (), "version": (),
    }[command]
    while args:
        value = args.pop(0)
        if value.startswith("-"):
            flag, equal, item = value.partition("=")
            key = flag[2:] if flag.startswith("--") else ""
            argument(key in allowed and key not in result)
            if key == "dry-run":
                argument(not equal)
                result[key] = True
                continue
            if not equal:
                argument(bool(args))
                item = args.pop(0)
            literal(item)
            argument(not item.startswith("-"))
            result[key] = item
        else:
            argument(command in ("enable", "disable", "inspect") and "target" not in result)
            result["target"] = literal(value)
    if command in ("install", "update"):
        argument(("version" in result) != ("source" in result))
        if "version" in result:
            argument(re.fullmatch(VERSION, result["version"]) is not None)
        if "source" in result:
            argument("://" not in result["source"])
    if "platform" in result:
        argument(result["platform"] in PLATFORMS)
    argument(command != "retire-global" or "platform" in result)
    if command in ("enable", "disable", "inspect"):
        result.setdefault("target", ".")
    return result


def usage(topic=None):
    if topic == "install":
        return ("install-v2.sh (--version 2.MINOR.PATCH | --source PACKAGE_DIRECTORY) "
                "[--dry-run]\n"
                "Verified runtime-only bootstrap; no activation, PATH or alias edits.\n"
                "Official URLs are a future publication contract, not a release claim.")
    return ("domestique2 [help [COMMAND] | version | inspect [TARGET]]\n"
            "Aliases: --help, -h, --version, --inspect [TARGET], TARGET --inspect.\n"
            "Bare invocation: read-only help and inspect .; always offline.\n"
            "enable/disable [TARGET] [--platform P] [--dry-run],\n"
            "update (--version V | --source PATH) [--dry-run],\n"
            "retire-global --platform P [--dry-run]: UNIMPLEMENTED, exit 1.\n"
            "Inspection retains legacy/preview inventory; V2 activation inventory "
            "and native/workflow guards are unavailable.")
