"""Device control via mobilerun-mcp - the backend behind 'rea device'.

mobilerun-mcp (core/mobilerun_mcp, a git submodule) is an MCP server that sees and
drives an Android device through the Mobilerun Portal APK (accessibility tree,
gestures, text input, screenshots) plus adb. It replaces the old Node scrcpy-cli;
the vendored scrcpy binary is still used for 'rea mirror' and as the one adb.

ReaKit itself stays stdlib-only. mobilerun-mcp lives in its own venv
(core/mobilerun_mcp/.venv, created by 'rea install'), and this module only ever
spawns that interpreter:

* ``rea device mcp``      -> ``<venv python> -I -m mobilerun_mcp`` (stdio or --http)
* ``rea device <action>`` -> ``<venv python> -I reakit/mobilerun_runner.py <action> ...``
                            which prints one JSON document on stdout
* ``rea device setup|doctor`` -> the venv's ``mobilerun`` CLI

Every spawn gets ReaKit's runtime env (bundled tools on PATH, ADB_PATH) plus
``MOBILERUN_ADB_BIN``/``ADBUTILS_ADB_PATH`` pinned to that same adb, so exactly one
adb server version runs (mismatched adb binaries kill each other's server), and
``MOBILERUN_DEVICE`` set from ``-s/--serial``.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from reakit.env import (
    BASE_DIR,
    MOBILERUN_DIR,
    MOBILERUN_VENV,
    find_mobilerun_python,
    inject_runtime_path,
)
from reakit.utils import Colors, log_error, log_info, log_success

DEFAULT_HTTP_PORT = 4816
RUNNER = Path(__file__).resolve().with_name("mobilerun_runner.py")
PORTAL_PACKAGE = "com.mobilerun.portal"

# 'rea device' subcommands served by the runner (the rest are handled here).
RUNNER_COMMANDS = (
    "list",
    "screenshot",
    "ui-dump",
    "tap",
    "swipe",
    "write",
    "key",
    "app-start",
    "app-stop",
    "apps",
    "clipboard-get",
    "clipboard-set",
)


class MobilerunMissing(RuntimeError):
    """The mobilerun-mcp venv does not exist (run 'rea install')."""


# ---------------------------------------------------------------------------
# Environment and interpreter
# ---------------------------------------------------------------------------


def resolve_adb(env: dict[str, str] | None = None) -> str | None:
    """The adb ReaKit uses everywhere else (ADB_PATH, else PATH) - see fridakit/_adb_base."""
    env = os.environ if env is None else env
    return env.get("ADB_PATH") or shutil.which("adb", path=env.get("PATH"))


def build_env(serial: str | None = None, base: dict[str, str] | None = None) -> dict:
    """Environment for every mobilerun spawn (runner, MCP server, mobilerun CLI).

    ``base`` defaults to ``os.environ`` after :func:`inject_runtime_path`, which puts
    the bundled scrcpy/adb dir on PATH and sets ADB_PATH.
    """
    if base is None:
        inject_runtime_path()
        base = os.environ
    env = dict(base)
    adb = resolve_adb(env)
    if adb:
        env["MOBILERUN_ADB_BIN"] = adb
        env["ADBUTILS_ADB_PATH"] = adb  # async_adbutils, used by mobilerun-core / the mobilerun CLI
        # The mobilerun CLI (doctor/setup) also calls shutil.which("adb"): put this adb's
        # dir first so a second platform-tools adb later on PATH is never picked.
        adb_dir = os.path.dirname(os.path.abspath(adb))
        rest = [p for p in env.get("PATH", "").split(os.pathsep) if p and os.path.normcase(os.path.abspath(p)) != os.path.normcase(adb_dir)]
        env["PATH"] = os.pathsep.join([adb_dir] + rest)
    if serial:
        env["MOBILERUN_DEVICE"] = serial
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def require_python() -> Path:
    py = find_mobilerun_python()
    if py is None:
        raise MobilerunMissing(
            f"mobilerun-mcp is not installed (no venv at {MOBILERUN_VENV}).\n"
            "    Run 'rea install' (needs uv) to create it, or by hand:\n"
            f"      uv venv --python 3.13 {MOBILERUN_VENV}\n"
            f"      uv pip install --python {MOBILERUN_VENV} -e {MOBILERUN_DIR}"
        )
    return py


def _missing(exc: MobilerunMissing) -> int:
    # stderr only: 'rea device mcp' must never write non-JSON-RPC bytes to stdout
    print(f"[-] {exc}", file=sys.stderr)
    return 1


def mobilerun_cli_cmd(py: Path) -> list[str]:
    """The venv's 'mobilerun' console script, else 'python -m mobilerun'."""
    exe = py.parent / ("mobilerun.exe" if os.name == "nt" else "mobilerun")
    if exe.is_file():
        return [str(exe)]
    return [str(py), "-m", "mobilerun"]


# ---------------------------------------------------------------------------
# MCP server
# ---------------------------------------------------------------------------


def mcp_server_cmd(py: Path, http: bool = False, port: int | None = None) -> list[str]:
    cmd = [str(py), "-I", "-m", "mobilerun_mcp"]
    if http:
        cmd += ["--http", "--port", str(port or DEFAULT_HTTP_PORT)]
    return cmd


def run_mcp_server(serial: str | None = None, http: bool = False, port: int | None = None) -> int:
    """Runs the mobilerun MCP server in the foreground (stdio by default).

    Everything printed here goes to stderr: in stdio transport stdout is the
    JSON-RPC channel, and a stray log line there breaks the handshake.
    """
    try:
        py = require_python()
    except MobilerunMissing as exc:
        return _missing(exc)
    cmd = mcp_server_cmd(py, http=http, port=port)
    env = build_env(serial)
    where = f"http://127.0.0.1:{port or DEFAULT_HTTP_PORT}/mcp" if http else "stdio"
    print(f"[*] Launching mobilerun MCP server ({where}): {' '.join(cmd)}", file=sys.stderr)
    print(f"[*] adb: {env.get('MOBILERUN_ADB_BIN') or 'not found'}", file=sys.stderr)
    try:
        return subprocess.run(cmd, env=env, check=False).returncode
    except KeyboardInterrupt:
        return 0
    except OSError as exc:
        print(f"[-] Could not launch the mobilerun MCP server: {exc}", file=sys.stderr)
        return 1


def rea_launcher() -> list[str]:
    """A command that runs 'rea' from any cwd: the installed console script, else rea.py."""
    exe = shutil.which("rea")
    if exe:
        return ["rea"]
    return [sys.executable, str(BASE_DIR / "rea.py")]


def mcp_config(serial: str | None = None) -> dict:
    launcher = rea_launcher()
    args = launcher[1:] + ["device"] + (["-s", serial] if serial else []) + ["mcp"]
    return {
        "mcpServers": {
            "mobilerun": {
                "type": "stdio",
                "command": launcher[0],
                "args": args,
            }
        }
    }


def print_mcp_config(serial: str | None = None) -> int:
    """Prints MCP client configuration for 'rea device mcp'."""
    config = mcp_config(serial)
    entry = config["mcpServers"]["mobilerun"]
    print(json.dumps(config, indent=2))
    print(f"\n{Colors.BOLD}Add it to Claude Code:{Colors.RESET}")
    print(f"  claude mcp add mobilerun -- {' '.join([entry['command']] + entry['args'])}\n")
    if find_mobilerun_python() is None:
        print("[!] mobilerun-mcp venv is missing - run 'rea install' before using this server.", file=sys.stderr)
    return 0


# ---------------------------------------------------------------------------
# One-shot actions
# ---------------------------------------------------------------------------


class RunnerError(RuntimeError):
    def __init__(self, code: int):
        super().__init__(f"mobilerun runner exited with code {code}")
        self.code = code


def run_runner(command: str, args: list[str] | None = None, serial: str | None = None) -> dict:
    """Runs one action in the mobilerun venv and returns its JSON result.

    The runner's stderr is passed straight through so its error message reaches
    the user; a non-zero exit raises :class:`RunnerError`.
    """
    py = require_python()
    cmd = [str(py), "-I", str(RUNNER), command] + [str(a) for a in (args or [])]
    res = subprocess.run(cmd, env=build_env(serial), stdout=subprocess.PIPE, text=True, encoding="utf-8", check=False)
    if res.returncode != 0:
        raise RunnerError(res.returncode)
    out = (res.stdout or "").strip()
    try:
        return json.loads(out.splitlines()[-1]) if out else {}
    except (ValueError, IndexError):
        log_error(f"Unreadable runner output: {out[:300]}")
        raise RunnerError(1) from None


def run_mobilerun_cli(cli_args: list[str], serial: str | None = None) -> int:
    """Runs the venv's mobilerun CLI (setup / doctor) with output streamed through."""
    py = require_python()
    env = build_env(serial)
    device = serial or env.get("MOBILERUN_DEVICE")
    cmd = mobilerun_cli_cmd(py) + cli_args + (["-d", device] if device else [])
    log_info(f"Running: {' '.join(cmd)}")
    try:
        return subprocess.run(cmd, env=env, check=False).returncode
    except KeyboardInterrupt:
        return 130
    except OSError as exc:
        log_error(f"Could not run mobilerun: {exc}")
        return 1


def _human(command: str, args: list[str], data: dict) -> None:
    dev = data.get("device")
    if command == "list":
        devices = data.get("devices") or []
        if not devices:
            print("No devices attached (adb devices is empty).")
            return
        default = data.get("default")
        for d in devices:
            mark = "  (default)" if default and d.get("serial") == default else ""
            print(f"{d.get('serial'):<28} {d.get('state')}{mark}")
    elif command in ("screenshot", "ui-dump"):
        what = "Screenshot" if command == "screenshot" else "UI tree"
        log_success(f"{what} saved -> {data.get('path')} ({data.get('bytes')} bytes, {dev})")
    elif command == "apps":
        for a in data.get("apps") or []:
            label = f"  {a.get('label')}" if a.get("label") else ""
            print(f"{a.get('package')}{label}")
        print(f"\n{data.get('count', 0)} app(s)", file=sys.stderr)
    elif command == "clipboard-get":
        print(data.get("text") or "")
    elif command == "tap":
        log_success(f"Tapped ({data.get('x')}, {data.get('y')}) on {dev}")
    elif command == "swipe":
        log_success(f"Swiped {tuple(data.get('from', []))} -> {tuple(data.get('to', []))} in {data.get('ms')}ms on {dev}")
    elif command == "write":
        log_success(f"Typed {data.get('chars')} char(s) on {dev}")
    elif command == "key":
        log_success(f"Pressed {data.get('key')} on {dev}")
    elif command == "app-start":
        act = f"/{data['activity']}" if data.get("activity") else ""
        log_success(f"Started {data.get('package')}{act} on {dev}")
    elif command == "app-stop":
        log_success(f"Stopped {data.get('package')} on {dev}")
    elif command == "clipboard-set":
        log_success(f"Clipboard set ({data.get('chars')} char(s)) on {dev}")
    else:
        print(json.dumps(data, indent=2))


def runner_argv(args) -> tuple[str, list[str]]:
    """Maps parsed 'rea device <action>' args to (runner command, runner args)."""
    a = args.device_action
    if a in ("screenshot", "ui-dump"):
        return a, [args.out]
    if a == "tap":
        return a, [args.x, args.y]
    if a == "swipe":
        return a, [args.x1, args.y1, args.x2, args.y2] + ([args.ms] if args.ms is not None else [])
    if a in ("write", "clipboard-set"):
        return a, [args.text]
    if a == "key":
        return a, [args.key]
    if a == "app-start":
        return a, [args.package] + ([args.activity] if args.activity else [])
    if a == "app-stop":
        return a, [args.package]
    if a == "apps":
        return a, ["--system"] if args.system else []
    return a, []


def handle(args) -> int:
    """Dispatches 'rea device <action>'. Returns a process exit code."""
    action = getattr(args, "device_action", None)
    serial = getattr(args, "serial", None)
    try:
        if action == "mcp":
            if getattr(args, "device_mcp_config", False):
                return print_mcp_config(serial)
            return run_mcp_server(serial, http=args.http, port=args.port)
        if action == "setup":
            log_info(f"Installing + enabling the Mobilerun Portal ({PORTAL_PACKAGE}) on the device...")
            return run_mobilerun_cli(["setup"], serial)
        if action == "doctor":
            return run_mobilerun_cli(["doctor"], serial)
        if action in RUNNER_COMMANDS:
            command, rargs = runner_argv(args)
            data = run_runner(command, rargs, serial)
            if getattr(args, "json", False):
                print(json.dumps(data, indent=2, ensure_ascii=False))
            else:
                _human(command, rargs, data)
            return 0
    except MobilerunMissing as exc:
        return _missing(exc)
    except RunnerError as exc:
        return exc.code
    log_error("A device subcommand is required (see 'rea device -h').")
    return 1
