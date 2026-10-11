"""One-shot device actions for 'rea device', executed INSIDE the mobilerun-mcp venv.

ReaKit stays stdlib-only, so it never imports mobilerun_mcp itself. Instead
reakit/mobilerun.py spawns this file as::

    <core/mobilerun_mcp/.venv python> -I mobilerun_runner.py <command> [args...]

and reads one JSON document from stdout. Errors go to stderr with a non-zero exit
(1 = device/tool error, 2 = usage error). This file must not import reakit: -I
keeps the ReaKit checkout off sys.path on purpose.

Device selection and the adb binary come from the environment the parent builds
(MOBILERUN_DEVICE, MOBILERUN_ADB_BIN), read by mobilerun_mcp's own Config.from_env.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path

USAGE = """usage: mobilerun_runner.py <command> [args...]
commands:
  list
  screenshot <out.png>
  ui-dump <out.json>
  tap <x> <y>
  swipe <x1> <y1> <x2> <y2> [ms]
  write <text>
  key <name|keycode>
  app-start <package> [activity]
  app-stop <package>
  apps [--system]
  clipboard-get
  clipboard-set <text>
"""

# argument counts: (min, max)
ARITY = {
    "list": (0, 0),
    "screenshot": (1, 1),
    "ui-dump": (1, 1),
    "tap": (2, 2),
    "swipe": (4, 5),
    "write": (1, 1),
    "key": (1, 1),
    "app-start": (1, 2),
    "app-stop": (1, 1),
    "apps": (0, 1),
    "clipboard-get": (0, 0),
    "clipboard-set": (1, 1),
}


class UsageError(Exception):
    pass


def _int(value: str, name: str) -> int:
    try:
        return int(value)
    except ValueError:
        raise UsageError(f"{name} must be an integer, got {value!r}") from None


def _write_file(path: str, data: bytes) -> dict:
    out = Path(path).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)
    return {"path": str(out), "bytes": len(data)}


async def _list(config) -> dict:
    from mobilerun_mcp import adb as adb_mod

    devices = await adb_mod.list_devices(config.adb_bin)
    return {
        "default": config.device or None,
        "adb": config.adb_bin,
        "count": len(devices),
        "devices": devices,
    }


async def _run(cmd: str, args: list[str]) -> dict:
    from mobilerun_mcp.config import Config
    from mobilerun_mcp.session import Runtime

    config = Config.from_env()
    if cmd == "list":
        return await _list(config)

    runtime = Runtime(config)
    try:
        session = runtime.session()
        await session.ensure_connected()
        base = {"device": session.serial}

        if cmd == "screenshot":
            png = await session.screenshot()
            return {**base, **_write_file(args[0], png)}

        if cmd == "ui-dump":
            state = await session.raw_state()  # Portal state_full: a11y_tree + phone_state
            text = json.dumps(state, indent=2, ensure_ascii=False) + "\n"
            return {**base, **_write_file(args[0], text.encode("utf-8"))}

        if cmd == "tap":
            x, y = _int(args[0], "x"), _int(args[1], "y")
            await session.tap_xy(x, y)
            return {**base, "action": "tap", "x": x, "y": y}

        if cmd == "swipe":
            coords = [_int(v, n) for v, n in zip(args[:4], ("x1", "y1", "x2", "y2"))]
            ms = _int(args[4], "ms") if len(args) > 4 else 300
            await session.swipe_xy(*coords, duration_ms=ms)
            return {**base, "action": "swipe", "from": coords[:2], "to": coords[2:], "ms": ms}

        if cmd == "write":
            await session.input_text(args[0])
            return {**base, "action": "write", "chars": len(args[0])}

        if cmd == "key":
            # Same rule as the MCP 'key' tool: a number is a raw Android keycode,
            # anything else a mobilerun key name (home, back, enter, recents, ...).
            name = args[0]
            if name.isdigit():
                await session.shell(f"input keyevent {int(name)}")
            else:
                await session.press(name)
            return {**base, "action": "key", "key": name}

        if cmd == "app-start":
            activity = args[1] if len(args) > 1 else None
            await session.start_app(args[0], activity)
            return {**base, "action": "app-start", "package": args[0], "activity": activity}

        if cmd == "app-stop":
            await session.core.call("stop_app", args[0])
            return {**base, "action": "app-stop", "package": args[0]}

        if cmd == "apps":
            if args and args[0] != "--system":
                raise UsageError(f"unknown apps option {args[0]!r} (only --system)")
            system = bool(args)
            apps = await session.apps(refresh=True)
            shown = [
                {"package": a.package, "label": a.label, "system": a.system, "version": a.version}
                for a in apps
                if system or not a.system
            ]
            shown.sort(key=lambda a: a["package"])
            return {**base, "count": len(shown), "apps": shown}

        if cmd == "clipboard-get":
            return {**base, "text": await session.core.call("get_clipboard")}

        if cmd == "clipboard-set":
            await session.core.call("set_clipboard", args[0])
            return {**base, "action": "clipboard-set", "chars": len(args[0])}

        raise UsageError(f"unknown command {cmd!r}")
    finally:
        await runtime.aclose()


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        sys.stderr.write(USAGE)
        return 0 if argv else 2
    cmd, args = argv[0], argv[1:]
    if cmd not in ARITY:
        sys.stderr.write(f"error: unknown command {cmd!r}\n{USAGE}")
        return 2
    lo, hi = ARITY[cmd]
    if not lo <= len(args) <= hi:
        sys.stderr.write(f"error: {cmd} takes {lo}-{hi} argument(s), got {len(args)}\n{USAGE}")
        return 2

    logging.basicConfig(stream=sys.stderr, level=logging.WARNING)
    # Library code must not write to the JSON channel: route stray prints to stderr
    # and emit exactly one JSON document on the real stdout at the end.
    real_stdout = sys.stdout
    sys.stdout = sys.stderr
    try:
        result = asyncio.run(_run(cmd, args))
    except UsageError as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 2
    except KeyboardInterrupt:
        return 130
    except Exception as exc:  # McpToolError carries "[code] message (hint: ...)"
        sys.stderr.write(f"error: {exc}\n" if str(exc) else f"error: {type(exc).__name__}\n")
        return 1
    finally:
        sys.stdout = real_stdout
    real_stdout.write(json.dumps(result, ensure_ascii=True) + "\n")
    real_stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
