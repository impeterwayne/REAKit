"""Frida dynamic-instrumentation integration for REA_Kit.

This module is the runtime-instrumentation half of a target, the counterpart to
:mod:`reakit.native` (static/native) and :mod:`reakit.httptoolkit` (network):

* :class:`FridaServerManager` owns the on-device ``frida-server`` lifecycle -
  ABI detection, a version-matched download from the frida GitHub releases
  (``urllib`` + ``lzma``, no third-party code), push/chmod, a detached
  ``su -c 'setsid ...'`` start that survives the ADB shell being reaped, and a
  status/liveness probe that compares the device binary against the host module.
* :class:`FridaDevice` resolves ``"usb" | "local" | "remote"`` and *prefers a
  remote device over USB auto-selection* - an ``adb forward`` plus an explicit
  ``add_remote_device('127.0.0.1:<port>')`` cannot be hijacked by an emulator
  when several devices are attached.
* :class:`SessionManager` / :class:`ScriptHandle` attach, spawn, inject scripts,
  bridge ``rpc.exports`` and run memory operations through one persistent helper
  agent per session (parameters pass by RPC arguments, never by string
  interpolation into JS).
* :func:`run_probe` injects a bundled or on-disk probe, streams every message to
  stdout *and* the target's workspace log, and tears the session down cleanly.

Stdlib only: ``pyproject.toml`` keeps ``dependencies = []``. The ``frida`` Python
package is imported **lazily inside the functions that need it** (never at module
import), with a clear ``pip install 'frida==17.*'`` hint when it is absent -
frida 17.x is the track REA_Kit aligns the host package and the on-device server
on. frida 17 removed the built-in ``Java`` / ``ObjC`` / ``Swift`` globals, so when
an injected agent references one :class:`SessionManager` transparently prepends a
bridge-loader prelude and serves the bridge JS (from the installed ``frida-tools``
package) over the script's send/recv channel on demand; the loader is a no-op on
frida 16, where the built-in bridge already exists.
"""

import importlib.util
import json
import lzma
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from urllib import error as urlerror
from urllib import request as urlrequest

from reakit.config import ConfigManager
from reakit.utils import (
    Colors,
    ensure_dir,
    log_dim,
    log_error,
    log_info,
    log_success,
    log_warn,
)

# ---------------------------------------------------------------------------
# Constants (shared with reakit.native / reakit.httptoolkit where noted)
# ---------------------------------------------------------------------------

DEFAULT_FRIDA_PORT = 27042
# A bare major track resolves to the latest 17.x tag at install time; an exact
# "17.2.9" pins it, and "host" matches the installed host package.
DEFAULT_FRIDA_VERSION = "17"
DEFAULT_SERVER_NAME = "frida-server"
DEVICE_TMP = "/data/local/tmp"

STATE_DIR = Path.home() / ".reakit"                 # reused by native/http
FRIDA_CACHE_DIR = STATE_DIR / "frida-cache"         # downloaded server binaries
BRIDGE_CACHE_DIR = STATE_DIR / "frida-bridges"      # cached Java/ObjC/Swift bridge JS
FRIDA_LOG_FILE = STATE_DIR / "frida.log"
FRIDA_PROBE_PID_FILE = STATE_DIR / "frida_probe.pid"

# frida-server release ABI names, keyed by Android's ro.product.cpu.abi.
ABI_MAP: dict[str, str] = {
    "arm64-v8a": "arm64",
    "arm64": "arm64",
    "armeabi-v7a": "arm",
    "armeabi": "arm",
    "arm": "arm",
    "x86_64": "x86_64",
    "x86": "x86",
}

FRIDA_RELEASES_API = "https://api.github.com/repos/frida/frida/releases"
# frida-server-<version>-android-<abi>.xz
FRIDA_SERVER_ASSET = "frida-server-{version}-android-{abi}.xz"
FRIDA_DOWNLOAD_URL = (
    "https://github.com/frida/frida/releases/download/{version}/" + FRIDA_SERVER_ASSET
)

# Where the bundled JS probe agents live. The .js files are created separately;
# this directory may not exist yet, and builtin_agent() only fails when invoked.
FRIDA_AGENTS_DIR = Path(__file__).resolve().parent / "frida_agents"

# The canonical bundled agents, referenced by name (see docs/frida.md).
BUILTIN_AGENTS = (
    "probe_net.js",
    "stalker_trace.js",
    "anti_detect.js",
    "rpc_template.js",
    "hook_patch.js",
    "mem_helper.js",
)

INSTALL_HINT = "pip install 'frida==17.*'"

# How many messages a ScriptHandle keeps before dropping the oldest. Caps the
# unbounded list that ya-frida-mcp's ScriptHandle grew without limit.
DEFAULT_MESSAGE_CAP = 5000


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class FridaError(Exception):
    """A Frida operation failed (missing module, device error, RPC error...)."""


class FridaNotRunning(FridaError):
    """frida-server is not reachable on the device / forwarded port."""


# ---------------------------------------------------------------------------
# Config / env resolution (env var > config key > default), mirroring native
# ---------------------------------------------------------------------------


def _config_value(config_mgr: "ConfigManager | None", key: str, env: str) -> "str | None":
    """Resolves a string setting: env var first, then the config file."""
    val = os.environ.get(env)
    if val:
        return val
    if config_mgr is not None:
        cfg = config_mgr.config_data.get(key)
        if cfg is not None:
            return str(cfg)
    return None


def frida_port(config_mgr: "ConfigManager | None" = None) -> int:
    """Host-side forwarded port (env FRIDA_PORT, config fridaServerPort, 27042)."""
    val = _config_value(config_mgr, "fridaServerPort", "FRIDA_PORT")
    if val and str(val).isdigit():
        return int(val)
    return DEFAULT_FRIDA_PORT


def frida_version(config_mgr: "ConfigManager | None" = None) -> str:
    """Target frida version/track (env FRIDA_VERSION, config fridaVersion, "17")."""
    return _config_value(config_mgr, "fridaVersion", "FRIDA_VERSION") or DEFAULT_FRIDA_VERSION


def server_name(config_mgr: "ConfigManager | None" = None) -> str:
    """On-device binary name (env FRIDA_SERVER_NAME, config fridaServerName, frida-server)."""
    return _config_value(config_mgr, "fridaServerName", "FRIDA_SERVER_NAME") or DEFAULT_SERVER_NAME


def host_frida_version() -> "str | None":
    """Returns the installed host frida module version, or None when absent.

    Guarded: never raises, never imports frida when the package is not present
    (``find_spec`` first), so callers can probe the environment safely.
    """
    try:
        if importlib.util.find_spec("frida") is None:
            return None
    except (ImportError, ValueError):
        return None
    try:
        import frida  # noqa: PLC0415 - deliberately lazy, see module docstring

        return getattr(frida, "__version__", None)
    except Exception:
        return None


def require_frida():
    """Imports and returns the frida module, or raises FridaError with a hint."""
    try:
        present = importlib.util.find_spec("frida") is not None
    except (ImportError, ValueError):
        present = False
    if not present:
        raise FridaError(
            "The 'frida' Python package is not installed. Install the 17.x host "
            f"package to match the on-device server:\n    {INSTALL_HINT}"
        )
    try:
        import frida  # noqa: PLC0415 - deliberately lazy

        return frida
    except Exception as exc:  # pragma: no cover - import-time breakage
        raise FridaError(f"Could not import frida: {exc}\n    Try: {INSTALL_HINT}") from exc


# ---------------------------------------------------------------------------
# ADB helper (honours ADB_PATH, mirrors httptoolkit's _adb / _adb_base)
# ---------------------------------------------------------------------------


def _adb_base(serial: "str | None" = None) -> list[str]:
    adb = os.environ.get("ADB_PATH") or shutil.which("adb") or "adb"
    return [adb, "-s", serial] if serial else [adb]


def _adb(args: list[str], serial: "str | None" = None, capture: bool = True, timeout: int = 60):
    """Runs one adb command, returning the CompletedProcess or None on failure."""
    cmd = _adb_base(serial) + args
    try:
        return subprocess.run(
            cmd,
            stdout=subprocess.PIPE if capture else None,
            stderr=subprocess.STDOUT if capture else None,
            text=True,
            errors="replace",
            timeout=timeout,
        )
    except FileNotFoundError:
        log_error("adb not found in PATH. Run 'rea env' to check the environment.")
        return None
    except subprocess.SubprocessError as exc:
        log_error(f"adb failed: {exc}")
        return None


class AdbHelper:
    """Thin ADB wrapper bound to one device serial.

    ``.shell`` / ``.su`` return the command's trimmed stdout as a string; ``.run``
    hands back the raw CompletedProcess for callers that need the return code.
    """

    def __init__(self, serial: "str | None" = None):
        self.serial = serial

    # -- raw ----------------------------------------------------------------
    def run(self, args: list[str], timeout: int = 60, capture: bool = True):
        """Runs ``adb <args>``; raises FridaError if adb is missing."""
        cmd = _adb_base(self.serial) + list(args)
        try:
            return subprocess.run(
                cmd,
                stdout=subprocess.PIPE if capture else None,
                stderr=subprocess.STDOUT if capture else None,
                text=True,
                errors="replace",
                timeout=timeout,
            )
        except FileNotFoundError as exc:
            raise FridaError("adb not found in PATH. Install platform-tools or set ADB_PATH.") from exc
        except subprocess.SubprocessError as exc:
            raise FridaError(f"adb command failed: {exc}") from exc

    # -- convenience --------------------------------------------------------
    def shell(self, cmd: str, timeout: int = 60) -> str:
        res = self.run(["shell", cmd], timeout=timeout)
        return (res.stdout or "").strip() if res else ""

    def su(self, cmd: str, timeout: int = 60) -> str:
        """Runs a device command as root via ``su -c '<cmd>'``."""
        escaped = cmd.replace("'", "'\\''")
        res = self.run(["shell", f"su -c '{escaped}'"], timeout=timeout)
        return (res.stdout or "").strip() if res else ""

    def push(self, local: "Path | str", remote: str, timeout: int = 300):
        res = self.run(["push", str(local), remote], timeout=timeout)
        if res is None or res.returncode != 0:
            raise FridaError(f"adb push failed: {(res.stdout or '').strip() if res else 'adb missing'}")
        return res

    def pull(self, remote: str, local: "Path | str", timeout: int = 300):
        res = self.run(["pull", remote, str(local)], timeout=timeout)
        if res is None or res.returncode != 0:
            raise FridaError(f"adb pull failed: {(res.stdout or '').strip() if res else 'adb missing'}")
        return res

    def forward(self, host_port: int, device_port: "int | None" = None):
        """Forwards host ``tcp:host_port`` to device ``tcp:device_port`` (same by default)."""
        device_port = device_port if device_port is not None else host_port
        res = self.run(["forward", f"tcp:{host_port}", f"tcp:{device_port}"])
        if res is None or res.returncode != 0:
            raise FridaError(
                f"adb forward tcp:{host_port} -> tcp:{device_port} failed: "
                f"{(res.stdout or '').strip() if res else 'adb missing'}"
            )
        return res

    def forward_remove(self, host_port: int):
        return self.run(["forward", "--remove", f"tcp:{host_port}"])

    def is_reachable(self) -> bool:
        res = self.run(["get-state"], timeout=15)
        return bool(res and res.returncode == 0 and "device" in (res.stdout or ""))

    def is_root(self) -> bool:
        """True when ``su -c id`` reports uid 0."""
        try:
            out = self.su("id")
        except FridaError:
            return False
        return "uid=0" in out


# ---------------------------------------------------------------------------
# Timestamps + message formatting (shared by the probe runner and printers)
# ---------------------------------------------------------------------------


def _host_ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def format_message(message: dict) -> "tuple[str, str]":
    """Turns a frida message into ``(device_ts, text)``. Never raises.

    Understands the ``{t, tag, msg}`` payload shape the bundled agents emit, and
    renders ``error`` messages with their description, location and stack.
    """
    if not isinstance(message, dict):
        return "-", f"? {message!r}"
    kind = message.get("type")
    if kind == "send":
        payload = message.get("payload")
        if isinstance(payload, dict):
            dev = payload.get("t") or "-"
            tag = payload.get("tag") or "SEND"
            msg = payload.get("msg")
            if msg is None:
                msg = {k: v for k, v in payload.items() if k not in ("t", "tag")}
            return str(dev), f"{tag} {msg}"
        return "-", f"SEND {payload!r}"
    if kind == "error":
        desc = message.get("description") or ""
        where = f"{message.get('fileName') or '?'}:{message.get('lineNumber') or '?'}"
        out = f"FRIDA-ERROR {desc} ({where})"
        stack = message.get("stack")
        if stack:
            out += "\n    " + str(stack).replace("\n", "\n    ")
        return "-", out
    return "-", f"{kind} {message!r}"


def _message_tag(message: dict) -> str:
    if not isinstance(message, dict):
        return "OTHER"
    if message.get("type") == "error":
        return "FRIDA-ERROR"
    payload = message.get("payload")
    if isinstance(payload, dict):
        return str(payload.get("tag") or "SEND")
    return "SEND"


# ---------------------------------------------------------------------------
# Target resolution (mirrors frida CLI flags -p / -n / -N / -F)
# ---------------------------------------------------------------------------


class TargetSpec:
    """A process selector: exactly one of pid / name / identifier / frontmost.

    ``-p`` pid, ``-n`` process name, ``-N`` application identifier, ``-F`` the
    frontmost application. :meth:`resolve` turns it into a concrete pid against a
    live :class:`FridaDevice`.
    """

    def __init__(
        self,
        pid: "int | None" = None,
        name: "str | None" = None,
        identifier: "str | None" = None,
        frontmost: bool = False,
    ):
        provided = [x for x in (pid is not None, bool(name), bool(identifier), frontmost) if x]
        if len(provided) != 1:
            raise FridaError(
                "TargetSpec needs exactly one of pid / name / identifier / frontmost"
            )
        self.pid = pid
        self.name = name
        self.identifier = identifier
        self.frontmost = frontmost

    def __repr__(self) -> str:
        if self.pid is not None:
            return f"TargetSpec(pid={self.pid})"
        if self.name:
            return f"TargetSpec(name={self.name!r})"
        if self.identifier:
            return f"TargetSpec(identifier={self.identifier!r})"
        return "TargetSpec(frontmost=True)"

    @classmethod
    def from_args(
        cls,
        pid: "int | None" = None,
        name: "str | None" = None,
        identifier: "str | None" = None,
        frontmost: bool = False,
        default: "str | None" = None,
    ) -> "TargetSpec":
        """Builds a spec from CLI-style flags, falling back to ``default`` as a name/identifier."""
        if pid is not None or name or identifier or frontmost:
            return cls(pid=pid, name=name, identifier=identifier, frontmost=frontmost)
        if default:
            # A dotted string is an application identifier; otherwise a process name.
            if "." in default and " " not in default:
                return cls(identifier=default)
            return cls(name=default)
        raise FridaError("No target given (use -p/-n/-N/-F or name a configured target).")

    def resolve(self, device: "FridaDevice") -> int:
        """Returns the pid this spec selects on *device*; raises if not running."""
        if self.pid is not None:
            return int(self.pid)
        if self.frontmost:
            app = device.get_frontmost()
            pid = getattr(app, "pid", 0) if app else 0
            if not pid:
                raise FridaError("No frontmost application is running.")
            return pid
        if self.identifier:
            for app in device.enumerate_applications():
                if getattr(app, "identifier", None) == self.identifier:
                    pid = getattr(app, "pid", 0)
                    if pid:
                        return pid
                    raise FridaError(
                        f"Application '{self.identifier}' is installed but not running; "
                        f"use 'spawn' to launch it under Frida."
                    )
            raise FridaError(f"No application with identifier '{self.identifier}'.")
        # name
        procs = device.enumerate_processes()
        exact = [p for p in procs if getattr(p, "name", None) == self.name]
        if exact:
            return exact[0].pid
        needle = (self.name or "").lower()
        partial = [p for p in procs if needle and needle in (getattr(p, "name", "") or "").lower()]
        if partial:
            return partial[0].pid
        raise FridaError(f"No running process named '{self.name}'.")


# ---------------------------------------------------------------------------
# Device: usb / local / remote(host:port), remote preferred over USB
# ---------------------------------------------------------------------------


class FridaDevice:
    """Wraps a ``frida.core.Device`` with REA_Kit resolution and cleanup.

    Prefer :meth:`create` over the constructor: it establishes the transport and,
    for the default ``remote`` spec, sets up ``adb forward`` + an explicit
    ``add_remote_device('127.0.0.1:<port>')`` so an attached emulator cannot win
    the USB auto-selection race.
    """

    def __init__(
        self,
        raw_device,
        *,
        spec: str = "remote",
        host: "str | None" = None,
        port: "int | None" = None,
        serial: "str | None" = None,
        adb: "AdbHelper | None" = None,
        forwarded: bool = False,
    ):
        self._device = raw_device
        self.spec = spec
        self.host = host
        self.port = port
        self.serial = serial
        self.adb = adb or AdbHelper(serial)
        self._forwarded = forwarded

    # -- construction -------------------------------------------------------
    @classmethod
    def create(
        cls,
        config_mgr: "ConfigManager | None" = None,
        spec: "str | None" = None,
        serial: "str | None" = None,
        port: "int | None" = None,
    ) -> "FridaDevice":
        """Resolves a device from a spec string.

        ``"usb"`` / ``"local"`` use frida's own selection. ``"remote"`` (default)
        forwards and attaches ``127.0.0.1:<port>``. ``"host:port"`` or
        ``"remote:host:port"`` attaches that explicit address without forwarding.
        """
        frida = require_frida()
        spec = (spec or "remote").strip()
        port = port if port is not None else frida_port(config_mgr)
        adb = AdbHelper(serial)

        if spec == "usb":
            try:
                return cls(frida.get_usb_device(timeout=5), spec="usb", serial=serial, adb=adb)
            except Exception as exc:
                raise FridaError(f"Could not select a USB device: {exc}") from exc
        if spec == "local":
            return cls(frida.get_local_device(), spec="local", adb=adb)

        # Remote (default and explicit host:port forms).
        host = "127.0.0.1"
        forwarded = False
        if spec == "remote":
            adb.forward(port, port)
            forwarded = True
        else:
            bare = spec[len("remote:"):] if spec.startswith("remote:") else spec
            if ":" in bare:
                host, _, p = bare.rpartition(":")
                try:
                    port = int(p)
                except ValueError as exc:
                    raise FridaError(f"Invalid remote address '{spec}'") from exc
            else:
                host = bare

        addr = f"{host}:{port}"
        mgr = frida.get_device_manager()
        # Drop any cached remote device holding a dead socket from a restarted server.
        try:
            mgr.remove_remote_device(addr)
        except Exception:
            pass
        try:
            device = mgr.add_remote_device(addr)
        except Exception as exc:
            if forwarded:
                adb.forward_remove(port)
            raise FridaNotRunning(
                f"Could not reach frida-server at {addr}: {exc}\n"
                f"    Start it with: rea frida server start  (and check: rea frida doctor)"
            ) from exc
        return cls(
            device,
            spec="remote",
            host=host,
            port=port,
            serial=serial,
            adb=adb,
            forwarded=forwarded,
        )

    # -- identity -----------------------------------------------------------
    @property
    def raw(self):
        return self._device

    @property
    def id(self) -> str:
        return getattr(self._device, "id", "?")

    @property
    def name(self) -> str:
        return getattr(self._device, "name", "?")

    @property
    def type(self) -> str:
        return getattr(self._device, "type", "?")

    # -- enumeration --------------------------------------------------------
    def enumerate_processes(self, **kwargs):
        try:
            return self._device.enumerate_processes(**kwargs)
        except Exception as exc:
            raise FridaError(f"enumerate_processes failed: {exc}") from exc

    def enumerate_applications(self, **kwargs):
        try:
            return self._device.enumerate_applications(**kwargs)
        except Exception as exc:
            raise FridaError(f"enumerate_applications failed: {exc}") from exc

    def get_frontmost(self, **kwargs):
        try:
            return self._device.get_frontmost_application(**kwargs)
        except Exception as exc:
            raise FridaError(f"get_frontmost_application failed: {exc}") from exc

    def query_system_parameters(self) -> dict:
        try:
            return self._device.query_system_parameters()
        except Exception as exc:
            raise FridaError(f"query_system_parameters failed: {exc}") from exc

    # -- process control ----------------------------------------------------
    def spawn(
        self,
        program,
        argv: "list[str] | None" = None,
        env: "dict[str, str] | None" = None,
        cwd: "str | None" = None,
        stdio: "str | None" = None,
    ) -> int:
        kwargs: dict = {}
        if argv is not None:
            kwargs["argv"] = argv
        if env is not None:
            kwargs["env"] = env
        if cwd is not None:
            kwargs["cwd"] = cwd
        if stdio is not None:
            kwargs["stdio"] = stdio
        try:
            return self._device.spawn(program, **kwargs)
        except Exception as exc:
            raise FridaError(f"spawn({program!r}) failed: {exc}") from exc

    def resume(self, pid: int) -> None:
        try:
            self._device.resume(pid)
        except Exception as exc:
            raise FridaError(f"resume({pid}) failed: {exc}") from exc

    def kill(self, pid: int) -> None:
        try:
            self._device.kill(pid)
        except Exception as exc:
            raise FridaError(f"kill({pid}) failed: {exc}") from exc

    def attach(self, pid: int, realm: "str | None" = None, persist_timeout: "int | None" = None):
        kwargs: dict = {}
        if realm is not None:
            kwargs["realm"] = realm
        if persist_timeout is not None:
            kwargs["persist_timeout"] = persist_timeout
        try:
            return self._device.attach(pid, **kwargs)
        except Exception as exc:
            raise FridaError(f"attach({pid}) failed: {exc}") from exc

    # -- spawn gating -------------------------------------------------------
    def enable_spawn_gating(self) -> None:
        self._device.enable_spawn_gating()

    def disable_spawn_gating(self) -> None:
        self._device.disable_spawn_gating()

    def enumerate_pending_spawn(self) -> list:
        return list(self._device.enumerate_pending_spawn())

    def enumerate_pending_children(self) -> list:
        return list(self._device.enumerate_pending_children())

    # -- native library injection ------------------------------------------
    def inject_library_file(self, target: int, path: str, entrypoint: str, data: str = "") -> int:
        try:
            return self._device.inject_library_file(target, path, entrypoint, data)
        except Exception as exc:
            raise FridaError(f"inject_library_file failed: {exc}") from exc

    def inject_library_blob(self, target: int, blob: bytes, entrypoint: str, data: str = "") -> int:
        try:
            return self._device.inject_library_blob(target, blob, entrypoint, data)
        except Exception as exc:
            raise FridaError(f"inject_library_blob failed: {exc}") from exc

    # -- cleanup ------------------------------------------------------------
    def close(self) -> None:
        """Removes the adb forward this device created (if any)."""
        if self._forwarded and self.port:
            try:
                self.adb.forward_remove(self.port)
            except FridaError:
                pass
            self._forwarded = False


# ---------------------------------------------------------------------------
# frida-server lifecycle on the device
# ---------------------------------------------------------------------------


def _http_json(url: str, timeout: int = 60):
    """GETs a JSON document from the GitHub API; returns parsed data or None."""
    req = urlrequest.Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "reakit"})
    try:
        with urlrequest.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urlerror.URLError, json.JSONDecodeError, OSError):
        return None


class FridaServerManager:
    """Downloads, installs and controls the on-device ``frida-server`` binary.

    Improves on the reference implementations: it stops any existing server
    before (re)installing, and starts the new one detached with
    ``su -c 'setsid ... &'`` so the daemon survives the ADB shell being reaped.
    """

    def __init__(self, adb: "AdbHelper | None" = None, config_mgr: "ConfigManager | None" = None):
        self.adb = adb or AdbHelper()
        self.config_mgr = config_mgr
        self.server_name = server_name(config_mgr)
        self.remote_path = f"{DEVICE_TMP}/{self.server_name}"

    # -- discovery ----------------------------------------------------------
    def detect_abi(self) -> str:
        """Maps ``ro.product.cpu.abi`` to a frida release ABI (arm64/arm/x86/x86_64)."""
        raw = self.adb.shell("getprop ro.product.cpu.abi").strip()
        if not raw:
            raise FridaError("Could not read device ABI (is a device connected? 'adb devices').")
        mapped = ABI_MAP.get(raw)
        if not mapped:
            # Fall back on the abilist, taking the first mappable entry.
            abilist = self.adb.shell("getprop ro.product.cpu.abilist").strip()
            for part in abilist.split(","):
                mapped = ABI_MAP.get(part.strip())
                if mapped:
                    break
        if not mapped:
            raise FridaError(f"Unsupported device ABI: {raw!r}")
        return mapped

    def resolve_version(self, spec: "str | None" = None) -> str:
        """Resolves a version spec to a concrete frida release tag.

        ``"17"`` (a bare major) -> the latest 17.x release on GitHub; ``"17.2.9"``
        -> itself; ``"host"`` / ``"match"`` -> the installed host module version.
        """
        spec = (spec or frida_version(self.config_mgr)).strip()
        if spec.lower() in ("host", "match", "host-match"):
            hv = host_frida_version()
            if not hv:
                raise FridaError(
                    "host-match requested but the frida host module is not installed "
                    f"({INSTALL_HINT})."
                )
            return hv
        if re.fullmatch(r"\d+\.\d+\.\d+", spec):
            return spec
        if re.fullmatch(r"\d+", spec):
            tag = self._latest_for_major(spec)
            if not tag:
                raise FridaError(f"Could not find a {spec}.x frida release on GitHub.")
            return tag
        # Anything else (e.g. a pre-release tag) is used verbatim.
        return spec

    def _latest_for_major(self, major: str, max_pages: int = 10) -> "str | None":
        """Finds the newest ``<major>.x.y`` tag by paging the releases API."""
        best: "str | None" = None
        best_key: "tuple[int, int, int] | None" = None
        for page in range(1, max_pages + 1):
            data = _http_json(f"{FRIDA_RELEASES_API}?per_page=100&page={page}")
            if not data:
                break
            saw_lower = False
            for rel in data:
                tag = (rel.get("tag_name") or rel.get("name") or "").strip()
                m = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", tag)
                if not m:
                    continue
                mj = int(m.group(1))
                if mj < int(major):
                    saw_lower = True
                if mj != int(major):
                    continue
                key = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
                if best_key is None or key > best_key:
                    best_key, best = key, tag
            # Releases are newest-first; once we have a hit and have scrolled past
            # the major, later pages are all older - stop.
            if best and saw_lower:
                break
            if len(data) < 100:
                break
        return best

    # -- download -----------------------------------------------------------
    def download(self, version: str, abi: str) -> Path:
        """Downloads + decompresses a frida-server binary into FRIDA_CACHE_DIR.

        Cached by name: a previously decompressed binary is reused.
        """
        ensure_dir(FRIDA_CACHE_DIR)
        bin_name = f"frida-server-{version}-android-{abi}"
        bin_path = FRIDA_CACHE_DIR / bin_name
        if bin_path.is_file() and bin_path.stat().st_size > 0:
            log_dim(f"using cached {bin_path.name}")
            return bin_path

        url = FRIDA_DOWNLOAD_URL.format(version=version, abi=abi)
        xz_path = FRIDA_CACHE_DIR / FRIDA_SERVER_ASSET.format(version=version, abi=abi)
        log_info(f"Downloading frida-server {version} ({abi}) ...")
        log_dim(url)
        try:
            urlrequest.urlretrieve(url, xz_path)
        except (urlerror.URLError, OSError) as exc:
            raise FridaError(
                f"Download failed for frida-server {version} ({abi}): {exc}\n"
                f"    Check the version exists at https://github.com/frida/frida/releases"
            ) from exc

        try:
            with lzma.open(xz_path, "rb") as compressed, open(bin_path, "wb") as out:
                while True:
                    chunk = compressed.read(1 << 20)
                    if not chunk:
                        break
                    out.write(chunk)
        except (lzma.LZMAError, OSError) as exc:
            raise FridaError(f"Could not decompress {xz_path.name}: {exc}") from exc
        finally:
            try:
                xz_path.unlink()
            except OSError:
                pass
        log_success(f"frida-server ready in cache: {bin_path}")
        return bin_path

    # -- lifecycle ----------------------------------------------------------
    def install(self, version: "str | None" = None, force: bool = False) -> bool:
        """Downloads, pushes and makes the server executable. Stops any old one first."""
        abi = self.detect_abi()
        resolved = self.resolve_version(version)
        log_info(f"Installing frida-server {resolved} for {abi} as {self.remote_path}")

        # Stop a running server before overwriting its binary (busy-file / mismatch).
        if self.is_running():
            log_info("Stopping the existing frida-server before reinstalling ...")
            self.stop()
            time.sleep(0.5)

        if not force:
            on_device = self._device_version()
            if on_device and on_device == resolved:
                log_info(f"frida-server {resolved} already on device; use --force to re-push.")
                return True

        local = self.download(resolved, abi)
        self.adb.push(local, self.remote_path)
        self.adb.su(f"chmod 755 {self.remote_path}")
        # Best-effort SELinux context fix so exec is permitted on stricter ROMs.
        self.adb.su(f"chown root {self.remote_path}")
        log_success(f"frida-server {resolved} installed at {self.remote_path}")
        return True

    def start(self) -> bool:
        """Starts the server detached so the ADB shell exiting does not reap it."""
        if self.is_running():
            log_info("frida-server is already running.")
            return True
        # setsid detaches from the controlling terminal; the trailing & plus the
        # redirected stdio keep adb from waiting on the process.
        cmd = f"setsid {self.remote_path} -D </dev/null >/dev/null 2>&1 &"
        self.adb.su(cmd, timeout=15)
        time.sleep(1.0)
        if self.is_running():
            log_success("frida-server started.")
            return True
        log_error("frida-server did not come up. Check it is installed and the device is rooted.")
        log_dim(f"Try manually: adb shell su -c '{self.remote_path} -D &'")
        return False

    def stop(self) -> bool:
        """Kills the running server (``su -c pkill``)."""
        self.adb.su(f"pkill -f {self.server_name}")
        time.sleep(0.4)
        if self.is_running():
            # Fall back to killing by pid from pidof.
            pid = self._pidof()
            if pid:
                self.adb.su(f"kill -9 {pid}")
                time.sleep(0.3)
        if self.is_running():
            log_warn("frida-server still appears to be running.")
            return False
        log_success("frida-server stopped.")
        return True

    # -- status -------------------------------------------------------------
    def _pidof(self) -> "str | None":
        out = self.adb.shell(f"pidof {self.server_name}").strip()
        if out:
            first = out.split()[0]
            if first.isdigit():
                return first
        return None

    def is_running(self) -> bool:
        return self._pidof() is not None

    def _device_version(self) -> "str | None":
        for runner in (self.adb.shell, self.adb.su):
            try:
                out = runner(f"{self.remote_path} --version").strip()
            except FridaError:
                out = ""
            m = re.search(r"\d+\.\d+\.\d+", out)
            if m:
                return m.group(0)
        return None

    def status(self) -> dict:
        """Reports liveness, the on-device version, the host version and a match flag."""
        pid = self._pidof()
        device_version = self._device_version()
        client_version = host_frida_version()
        return {
            "running": pid is not None,
            "pid": pid,
            "server_name": self.server_name,
            "remote_path": self.remote_path,
            "device_version": device_version,
            "client_version": client_version,
            "version_match": bool(device_version and client_version and device_version == client_version),
        }


# ---------------------------------------------------------------------------
# Scripts and sessions
# ---------------------------------------------------------------------------

# frida 17 removed the built-in Java / ObjC / Swift globals. A script that still
# references one needs the bridge loaded explicitly. This matches the names the
# loader prelude installs as lazy getters.
_BRIDGE_NAMES = ("java", "objc", "swift")

# Does an agent's source touch a runtime bridge (Java. / ObjC. / Swift.)? If so,
# and the host frida is >= 17, we prepend the loader prelude below.
_BRIDGE_PATTERN = re.compile(r"\bJava\s*\.|\bObjC\s*\.|\bSwift\s*\.")


def _needs_bridge(source: str) -> bool:
    """True when *source* references the Java / ObjC / Swift runtime bridge."""
    return bool(_BRIDGE_PATTERN.search(source or ""))


def _host_frida_major() -> "int | None":
    """Major version of the installed host frida module, or None when unknown."""
    hv = host_frida_version()
    if not hv:
        return None
    m = re.match(r"(\d+)", hv)
    return int(m.group(1)) if m else None


# Bridge-loader prelude. For each of Java / ObjC / Swift it installs a lazy getter
# on ``globalThis`` *only if that global is not already defined* - so on frida 16,
# whose built-in bridge is present, this is a complete no-op. On frida 17 the first
# access sends ``{type:"frida:load-bridge", name}`` to the host, blocks on
# ``recv("frida:bridge:<name>")``, evaluates the returned bridge source and caches
# it as a plain data property (later accesses never re-request). qjs- and
# v8-compatible: only uses send / recv / Script.evaluate / Object.defineProperty.
_BRIDGE_LOADER = """\
(function () {
  function installBridge(name) {
    if (typeof globalThis[name] !== 'undefined') {
      return; // built-in bridge already present (frida 16): leave it untouched
    }
    Object.defineProperty(globalThis, name, {
      configurable: true,
      enumerable: true,
      get: function () {
        var tag = 'frida:bridge:' + name;
        var reply = {};
        send({ type: 'frida:load-bridge', name: name });
        recv(tag, function (m) {
          reply.source = m.source;
          reply.filename = m.filename;
          reply.error = m.error;
        }).wait();
        if (!reply.source) {
          throw new Error(
            'frida bridge "' + name + '" could not be loaded from the host' +
            (reply.error ? ': ' + reply.error : '')
          );
        }
        var filename = reply.filename || ('/frida/bridges/' + name + '.js');
        // The frida-tools bridge file declares `var bridge = ...;`. Wrap it so the
        // completion value is that bridge, cache it on globalThis (replacing this
        // getter), and return it.
        var bridge = Script.evaluate(
          filename,
          '(function () {' + reply.source +
          ';Object.defineProperty(globalThis, "' + name + '", ' +
          '{configurable: true, enumerable: true, writable: true, value: bridge});' +
          'return bridge;})();'
        );
        return bridge;
      }
    });
  }
  installBridge('Java');
  installBridge('ObjC');
  installBridge('Swift');
})();
"""


def _frida_tools_bridges_dir() -> "Path | None":
    """Locates the ``bridges/`` directory inside the installed frida_tools package.

    Guarded and lazy: never imports frida_tools, only resolves its on-disk path via
    ``find_spec`` so an absent package degrades gracefully.
    """
    try:
        spec = importlib.util.find_spec("frida_tools")
    except (ImportError, ValueError):
        return None
    if spec is None or not spec.origin:
        return None
    bridges = Path(spec.origin).resolve().parent / "bridges"
    return bridges if bridges.is_dir() else None


def _bridge_source(name: str) -> str:
    """Returns the bridge JS for ``name in {java, objc, swift}`` for frida 17.

    Resolution order: the installed ``frida-tools`` package (cached into
    ``BRIDGE_CACHE_DIR`` on success), then a previously cached copy, else a
    :class:`FridaError` explaining that frida-tools supplies the bridge. Never hits
    an unofficial network URL and never bundles the bridge JS into the repo.
    """
    key = (name or "").strip().lower()
    if key not in _BRIDGE_NAMES:
        raise FridaError(
            f"Unknown frida bridge {name!r}; expected one of {', '.join(_BRIDGE_NAMES)}."
        )
    cached = BRIDGE_CACHE_DIR / f"{key}.js"

    # 1. Primary: the installed frida_tools package (match it to the frida version).
    bridges_dir = _frida_tools_bridges_dir()
    if bridges_dir is not None:
        src = bridges_dir / f"{key}.js"
        if src.is_file():
            try:
                text = src.read_text(encoding="utf-8")
            except OSError:
                text = ""
            if text:
                try:
                    ensure_dir(BRIDGE_CACHE_DIR)
                    cached.write_text(text, encoding="utf-8")
                except OSError:
                    pass  # cache is best-effort; the in-memory copy is enough
                return text

    # 2. A cached copy from an earlier run (frida-tools no longer importable).
    if cached.is_file():
        try:
            return cached.read_text(encoding="utf-8")
        except OSError:
            pass

    # 3. Nothing available - a clear, actionable error (never a network fetch).
    raise FridaError(
        f"The frida '{key}' bridge is required for Java/ObjC/Swift hooking on "
        f"frida 17 but could not be located. frida 17 removed the built-in bridges; "
        f"install the matching frida-tools package, which ships them:\n"
        f"    pip install frida-tools\n"
        f"(the bridge JS lives under the frida_tools package's bridges/ directory)."
    )


# Inline introspection agent: parameters arrive as RPC arguments, so there is no
# string interpolation of caller data into the JS (no injection surface).
_INTROSPECT_AGENT = """
rpc.exports = {
  enumerateModules: function (filter) {
    var mods = Process.enumerateModules();
    if (filter) {
      var f = ('' + filter).toLowerCase();
      mods = mods.filter(function (m) { return m.name.toLowerCase().indexOf(f) >= 0; });
    }
    return mods.map(function (m) {
      return { name: m.name, base: m.base.toString(), size: m.size, path: m.path };
    });
  },
  enumerateExports: function (moduleName) {
    var m = null;
    try { m = Process.getModuleByName('' + moduleName); } catch (e) { m = Process.findModuleByName('' + moduleName); }
    if (!m) return [];
    return m.enumerateExports().map(function (e) {
      return { type: e.type, name: e.name, address: e.address.toString() };
    });
  }
};
"""


class ScriptHandle:
    """Owns one loaded script and its message buffer.

    The buffer is appended to under a lock and capped in size (ya-frida-mcp grew
    it without bound and read it without locking); :meth:`get_messages` drains it
    atomically so a reader never sees the same message twice.
    """

    def __init__(
        self,
        script,
        pid: int,
        script_id: str,
        max_messages: int = DEFAULT_MESSAGE_CAP,
        bridge_loader: bool = False,
    ):
        self._script = script
        self.pid = pid
        self.script_id = script_id
        self._max = max(1, max_messages)
        self._messages: list[dict] = []
        self._lock = threading.Lock()
        self._dropped = 0
        # When True, frida:load-bridge requests from the loader prelude are served
        # here (and NOT buffered as ordinary output).
        self._bridge_loader = bridge_loader
        script.on("message", self._on_message)

    def _on_message(self, message, data) -> None:
        # Intercept the bridge-load handshake BEFORE buffering, so the loader's
        # send/recv round-trip never shows up as script output.
        if self._bridge_loader and self._handle_bridge_request(message):
            return
        entry = {"message": message, "data": data.hex() if isinstance(data, (bytes, bytearray)) else data}
        with self._lock:
            self._messages.append(entry)
            overflow = len(self._messages) - self._max
            if overflow > 0:
                del self._messages[:overflow]
                self._dropped += overflow

    def _handle_bridge_request(self, message) -> bool:
        """Serves one ``frida:load-bridge`` request; True if it was one.

        On success posts the bridge source back on the ``frida:bridge:<name>`` tag
        the loader waits on; on failure posts an ``error`` on the same tag so the
        lazy getter unblocks and raises instead of hanging the script.
        """
        if not isinstance(message, dict) or message.get("type") != "send":
            return False
        payload = message.get("payload")
        if not isinstance(payload, dict) or payload.get("type") != "frida:load-bridge":
            return False
        name = str(payload.get("name") or "").strip().lower()
        tag = f"frida:bridge:{name}"
        try:
            source = _bridge_source(name)
            self._script.post({"type": tag, "name": name, "filename": f"{name}.js", "source": source})
        except FridaError as exc:
            log_error(f"frida {name} bridge unavailable: {exc}")
            self._script.post({"type": tag, "name": name, "error": str(exc)})
        except Exception as exc:  # pragma: no cover - defensive, must not hang script
            log_error(f"frida {name} bridge load failed: {exc}")
            self._script.post({"type": tag, "name": name, "error": str(exc)})
        return True

    def get_messages(self) -> list[dict]:
        """Returns and clears the buffered messages (copy + clear under the lock)."""
        with self._lock:
            out = list(self._messages)
            self._messages.clear()
            return out

    @property
    def dropped(self) -> int:
        with self._lock:
            return self._dropped

    @property
    def is_destroyed(self) -> bool:
        return bool(getattr(self._script, "is_destroyed", False))


class SessionManager:
    """Manages attach/spawn sessions and injected scripts for one device.

    Sessions are namespaced by ``(device_id, pid)`` and pruned when frida reports
    the session ``detached``. Memory operations go through a single persistent
    helper agent per session rather than a fresh injection per call.
    """

    def __init__(self, device: "FridaDevice"):
        self.device = device
        self._sessions: dict[tuple, object] = {}          # (device_id, pid) -> Session
        self._scripts: dict[str, ScriptHandle] = {}       # script_id -> handle
        self._mem_helpers: dict[tuple, ScriptHandle] = {} # (device_id, pid) -> helper
        self._counter = 0
        self._lock = threading.Lock()

    # -- keys / lookups -----------------------------------------------------
    @property
    def device_id(self) -> str:
        return self.device.id

    def _key(self, pid: int) -> tuple:
        return (self.device_id, int(pid))

    def _get_session(self, pid: int):
        session = self._sessions.get(self._key(pid))
        if session is None:
            raise FridaError(f"No active session for pid {pid}; attach or spawn first.")
        return session

    def _get_script(self, script_id: str) -> ScriptHandle:
        handle = self._scripts.get(script_id)
        if handle is None:
            raise FridaError(f"No such script '{script_id}'.")
        return handle

    # -- attach / spawn -----------------------------------------------------
    def _register(self, pid: int, session) -> None:
        session.on("detached", lambda *a, p=pid: self._on_detached(p, *a))
        self._sessions[self._key(pid)] = session

    def _on_detached(self, pid: int, *_args) -> None:
        key = self._key(pid)
        self._sessions.pop(key, None)
        self._mem_helpers.pop(key, None)
        # Drop scripts that belonged to the dead process.
        with self._lock:
            dead = [sid for sid, h in self._scripts.items() if h.pid == pid]
            for sid in dead:
                self._scripts.pop(sid, None)

    def attach(self, target, realm: "str | None" = None) -> "tuple[int, object]":
        pid = target.resolve(self.device) if isinstance(target, TargetSpec) else int(target)
        session = self.device.attach(pid, realm=realm)
        self._register(pid, session)
        return pid, session

    def spawn_and_attach(
        self,
        program: str,
        argv: "list[str] | None" = None,
        env: "dict[str, str] | None" = None,
        cwd: "str | None" = None,
        stdio: "str | None" = None,
        auto_resume: bool = True,
    ) -> "tuple[int, object]":
        pid = self.device.spawn(program, argv=argv, env=env, cwd=cwd, stdio=stdio)
        session = self.device.attach(pid)
        self._register(pid, session)
        if auto_resume:
            self.device.resume(pid)
        return pid, session

    def detach(self, pid: int) -> None:
        session = self._sessions.pop(self._key(pid), None)
        self._mem_helpers.pop(self._key(pid), None)
        if session is not None:
            try:
                session.detach()
            except Exception:
                pass

    # -- scripts ------------------------------------------------------------
    def inject(self, pid: int, source: str, runtime: "str | None" = "qjs") -> str:
        session = self._get_session(pid)
        # frida 17 dropped the built-in Java/ObjC/Swift globals. When the agent uses
        # one and the host frida is >= 17, prepend the loader prelude and arm this
        # script's handle to serve the bridge source over send/recv. On frida 16 the
        # prelude is skipped (the built-in bridge is already there); the loader would
        # be a no-op anyway, but skipping keeps 16 byte-for-byte unchanged.
        major = _host_frida_major()
        use_bridge = _needs_bridge(source) and (major is None or major >= 17)
        if use_bridge:
            source = _BRIDGE_LOADER + source
        try:
            script = session.create_script(source, runtime=runtime) if runtime else session.create_script(source)
        except Exception as exc:
            raise FridaError(f"create_script failed: {exc}") from exc
        with self._lock:
            self._counter += 1
            script_id = f"script_{self._counter}"
        handle = ScriptHandle(script, pid, script_id, bridge_loader=use_bridge)
        try:
            script.load()
        except Exception as exc:
            raise FridaError(f"script load failed: {exc}") from exc
        self._scripts[script_id] = handle
        return script_id

    def unload_script(self, script_id: str) -> None:
        handle = self._scripts.pop(script_id, None)
        if handle is not None and not handle.is_destroyed:
            try:
                handle._script.unload()
            except Exception:
                pass

    def list_scripts(self) -> list[str]:
        return list(self._scripts.keys())

    def list_sessions(self) -> list[int]:
        return [pid for (_dev, pid) in self._sessions.keys()]

    def get_messages(self, script_id: str) -> list[dict]:
        return self._get_script(script_id).get_messages()

    def post_message(self, script_id: str, message, data: "bytes | None" = None) -> None:
        handle = self._get_script(script_id)
        try:
            if data is not None:
                handle._script.post(message, data)
            else:
                handle._script.post(message)
        except Exception as exc:
            raise FridaError(f"post_message failed: {exc}") from exc

    # -- rpc ----------------------------------------------------------------
    @staticmethod
    def _exports(handle: ScriptHandle):
        return getattr(handle._script, "exports_sync", None) or getattr(handle._script, "exports", None)

    def _export_names(self, handle: ScriptHandle) -> list[str]:
        for attr in ("list_exports_sync", "list_exports"):
            fn = getattr(handle._script, attr, None)
            if fn is None:
                continue
            try:
                names = fn()
                if names:
                    return list(names)
            except Exception:
                pass
        exports = self._exports(handle)
        return [n for n in dir(exports) if not n.startswith("_")] if exports else []

    def _resolve_export(self, handle: ScriptHandle, *wanted: str):
        exports = self._exports(handle)
        if exports is None:
            return None
        # Direct attribute hit first (covers frida's own camelCase->snake_case).
        for name in wanted:
            fn = getattr(exports, name, None)
            if callable(fn):
                return fn
        # Normalised match against the advertised export list.
        names = self._export_names(handle)
        norm = {re.sub(r"[_\s]", "", n.lower()): n for n in names}
        for name in wanted:
            key = re.sub(r"[_\s]", "", name.lower())
            if key in norm:
                return getattr(exports, norm[key], None)
        return None

    def list_exports(self, script_id: str) -> list[str]:
        return self._export_names(self._get_script(script_id))

    def rpc_call(self, script_id: str, method: str, args: "list | None" = None):
        handle = self._get_script(script_id)
        fn = self._resolve_export(handle, method)
        if fn is None:
            raise FridaError(
                f"Script '{script_id}' has no rpc export '{method}'. "
                f"Available: {', '.join(self._export_names(handle)) or '(none)'}"
            )
        try:
            return fn(*(args or []))
        except Exception as exc:
            raise FridaError(f"rpc call {method} failed: {exc}") from exc

    # -- child gating -------------------------------------------------------
    def enable_child_gating(self, pid: int) -> None:
        self._get_session(pid).enable_child_gating()

    def disable_child_gating(self, pid: int) -> None:
        self._get_session(pid).disable_child_gating()

    # -- compile / snapshot / eternalize -----------------------------------
    def compile_script(self, pid: int, source: str, runtime: "str | None" = None) -> bytes:
        session = self._get_session(pid)
        try:
            if runtime:
                return session.compile_script(source, runtime=runtime)
            return session.compile_script(source)
        except Exception as exc:
            raise FridaError(f"compile_script failed: {exc}") from exc

    def snapshot_script(
        self,
        pid: int,
        embed_script: str,
        warmup_script: "str | None" = None,
        runtime: "str | None" = None,
    ) -> bytes:
        session = self._get_session(pid)
        try:
            if runtime:
                return session.snapshot_script(embed_script, warmup_script or "", runtime=runtime)
            return session.snapshot_script(embed_script, warmup_script or "")
        except Exception as exc:
            raise FridaError(f"snapshot_script failed: {exc}") from exc

    def eternalize_script(self, script_id: str) -> None:
        handle = self._get_script(script_id)
        try:
            handle._script.eternalize()
        except Exception as exc:
            raise FridaError(f"eternalize failed: {exc}") from exc
        # An eternalized script outlives the session; forget our handle for it.
        self._scripts.pop(script_id, None)

    # -- introspection ------------------------------------------------------
    def enumerate_modules(self, pid: int, name_filter: "str | None" = None) -> list:
        sid = self.inject(pid, _INTROSPECT_AGENT)
        try:
            return self.rpc_call(sid, "enumerate_modules", [name_filter])
        finally:
            self.unload_script(sid)

    def enumerate_exports(self, pid: int, module: str) -> list:
        sid = self.inject(pid, _INTROSPECT_AGENT)
        try:
            return self.rpc_call(sid, "enumerate_exports", [module])
        finally:
            self.unload_script(sid)

    # -- memory (one persistent helper agent per session) -------------------
    def _mem_helper(self, pid: int) -> ScriptHandle:
        key = self._key(pid)
        helper = self._mem_helpers.get(key)
        if helper is not None and not helper.is_destroyed:
            return helper
        self._get_session(pid)  # ensure the session exists before injecting
        source = builtin_agent("mem_helper.js")
        sid = self.inject(pid, source)
        helper = self._scripts[sid]
        self._mem_helpers[key] = helper
        return helper

    def _mem_call(self, pid: int, candidates: "tuple[str, ...]", *args):
        helper = self._mem_helper(pid)
        fn = self._resolve_export(helper, *candidates)
        if fn is None:
            raise FridaError(
                f"mem_helper.js exposes none of {candidates}; "
                f"available: {', '.join(self._export_names(helper)) or '(none)'}"
            )
        try:
            return fn(*args)
        except Exception as exc:
            raise FridaError(f"memory op {candidates[0]} failed: {exc}") from exc

    @staticmethod
    def _addr_str(addr) -> str:
        if isinstance(addr, int):
            return hex(addr)
        return str(addr)

    def mem_read(self, pid: int, addr, size: int) -> str:
        result = self._mem_call(
            pid,
            ("readMem", "read", "readMemory", "memRead"),
            self._addr_str(addr),
            int(size),
        )
        if isinstance(result, str):
            return result
        if isinstance(result, (list, tuple)):
            return bytes(result).hex()
        if isinstance(result, (bytes, bytearray)):
            return bytes(result).hex()
        return str(result)

    def mem_write(self, pid: int, addr, hex_data: str) -> int:
        result = self._mem_call(
            pid,
            ("writeMem", "write", "writeMemory", "memWrite"),
            self._addr_str(addr),
            hex_data,
        )
        try:
            return int(result)
        except (TypeError, ValueError):
            return len(bytes.fromhex(hex_data))

    def mem_scan(self, pid: int, addr, size: int, pattern: str) -> list:
        return self._mem_call(
            pid,
            ("scanMem", "scan", "scanMemory", "memScan"),
            self._addr_str(addr),
            int(size),
            pattern,
        )

    def mem_protect(self, pid: int, addr, size: int, prot: str = "rwx") -> bool:
        result = self._mem_call(
            pid,
            ("protectMem", "protect", "memProtect"),
            self._addr_str(addr),
            int(size),
            prot,
        )
        return bool(result) if result is not None else True

    # -- teardown -----------------------------------------------------------
    def cleanup(self) -> None:
        for sid in list(self._scripts.keys()):
            self.unload_script(sid)
        for session in list(self._sessions.values()):
            try:
                session.detach()
            except Exception:
                pass
        self._sessions.clear()
        self._mem_helpers.clear()


# ---------------------------------------------------------------------------
# Bundled agents + probe runner
# ---------------------------------------------------------------------------


def _list_agents() -> list[str]:
    try:
        return sorted(p.name for p in FRIDA_AGENTS_DIR.glob("*.js"))
    except OSError:
        return []


def builtin_agent(name: str) -> str:
    """Loads a bundled JS agent from ``reakit/frida_agents/`` by name.

    Accepts ``"probe_net"`` or ``"probe_net.js"``. Raises FridaError (only when
    actually called) if the file is missing, so an incomplete install never
    breaks ``import reakit.fridakit``.
    """
    if not name.endswith(".js"):
        name = name + ".js"
    path = FRIDA_AGENTS_DIR / name
    if not path.is_file():
        available = ", ".join(_list_agents()) or "(none found)"
        raise FridaError(
            f"Bundled Frida agent not found: {path}\n    Available agents: {available}"
        )
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise FridaError(f"Could not read agent {path}: {exc}") from exc


def _load_probe_source(script: str) -> "tuple[str, str]":
    """Returns ``(source, label)`` for an on-disk path or a bundled agent name."""
    candidate = Path(script)
    if candidate.is_file():
        return candidate.read_text(encoding="utf-8"), candidate.name
    return builtin_agent(script), script if script.endswith(".js") else script + ".js"


def save_probe_log(config_mgr: "ConfigManager", pkg: str, lines: list[str]) -> "Path | None":
    """Writes probe output under the target's ``dynamic/frida`` workspace folder."""
    if not pkg:
        log_warn("No package resolved; probe log not saved to a workspace.")
        return None
    paths = config_mgr.get_app_paths(pkg)
    frida_dir = paths.get("frida")
    if frida_dir is None:
        # Workspace config may predate the 'frida' key; fall back to the convention.
        frida_dir = paths["root"] / "dynamic" / "frida"
    ensure_dir(frida_dir)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    out = Path(frida_dir) / f"probe_{stamp}.log"
    try:
        out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError as exc:
        log_warn(f"Could not write probe log: {exc}")
        return None
    log_success(f"Saved {len(lines)} probe line(s) -> {out}")
    return out


def run_probe(
    config_mgr: "ConfigManager",
    target: "str | None",
    script: str,
    spawn: bool = False,
    duration: float = 60.0,
    runtime: "str | None" = None,
    serial: "str | None" = None,
    port: "int | None" = None,
    device_spec: str = "remote",
    pid: "int | None" = None,
) -> int:
    """Injects a probe, streams messages to stdout and the workspace log, stays resident.

    Spawn-or-attach, load the probe, resume only after the script is loaded (so
    hooks are live before the first call), stream every message with both host and
    device timestamps for ``duration`` seconds, then unload/detach and remove the
    adb forward.
    """
    require_frida()
    try:
        source, label = _load_probe_source(script)
    except FridaError as exc:
        log_error(str(exc))
        return 1

    pkg = config_mgr.resolve_package_name(target) if target else None
    if spawn and not pkg and pid is None:
        log_error("--spawn needs a resolvable target package (there is no pid to spawn).")
        return 1

    lines: list[str] = []

    def emit(text: str) -> None:
        line = f"[host {_host_ts()}] {text}"
        print(line, flush=True)
        lines.append(line)

    emit(f"probe={label} spawn={spawn} duration={duration}s runtime={runtime or 'default'} target={pkg or target}")
    emit(f"frida host module {host_frida_version() or '?'}")

    device: "FridaDevice | None" = None
    sm: "SessionManager | None" = None
    sid: "str | None" = None
    the_pid: "int | None" = None
    ensure_dir(STATE_DIR)
    try:
        FRIDA_PROBE_PID_FILE.write_text(str(os.getpid()), encoding="utf-8")
    except OSError:
        pass

    try:
        try:
            device = FridaDevice.create(config_mgr, spec=device_spec, serial=serial, port=port)
        except FridaNotRunning as exc:
            log_error(str(exc))
            return 1
        emit(f"device {device.id} ({device.type}) via {device.spec}")
        sm = SessionManager(device)

        if spawn:
            the_pid, _session = sm.spawn_and_attach(pkg, auto_resume=False)
            emit(f"spawned {pkg} pid={the_pid} (paused)")
        else:
            spec = TargetSpec(pid=pid) if pid is not None else TargetSpec.from_args(default=pkg or target)
            the_pid, _session = sm.attach(spec)
            emit(f"attached to {spec} pid={the_pid}")

        sid = sm.inject(the_pid, source, runtime=runtime)
        emit(f"loaded {label} as {sid}")

        if spawn:
            device.resume(the_pid)
            emit(f"resumed pid={the_pid} (hooks installed before resume)")

        emit(f"staying resident for {duration}s - now drive the app UI (Ctrl+C to stop early)")
        deadline = time.monotonic() + max(0.0, float(duration))
        counts: dict[str, int] = {}
        while time.monotonic() < deadline:
            for entry in sm.get_messages(sid):
                msg = entry.get("message")
                dev, text = format_message(msg)
                tag = _message_tag(msg)
                counts[tag] = counts.get(tag, 0) + 1
                line = f"[host {_host_ts()}] [dev {dev}] {text}"
                print(line, flush=True)
                lines.append(line)
            time.sleep(0.4)
        # Drain any final messages.
        for entry in sm.get_messages(sid):
            dev, text = format_message(entry.get("message"))
            line = f"[host {_host_ts()}] [dev {dev}] {text}"
            print(line, flush=True)
            lines.append(line)

        emit("")
        emit(f"summary: {sum(counts.values())} message(s)")
        for tag in sorted(counts):
            emit(f"   {tag:<16} {counts[tag]}")
        if not counts:
            emit("   no probe output - did READY appear? check the frida-server version match (rea frida doctor)")
        return 0

    except KeyboardInterrupt:
        emit("interrupted; detaching")
        return 0
    except FridaError as exc:
        log_error(str(exc))
        return 1
    finally:
        if sm is not None and sid is not None:
            sm.unload_script(sid)
        if sm is not None and the_pid is not None:
            sm.detach(the_pid)
        if device is not None:
            device.close()
        if pkg:
            save_probe_log(config_mgr, pkg, lines)
        try:
            FRIDA_PROBE_PID_FILE.unlink(missing_ok=True)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Terminal reports
# ---------------------------------------------------------------------------


def print_devices(devices) -> int:
    rows = list(devices or [])
    if not rows:
        log_warn("No Frida devices found.")
        return 0
    print(f"\n{Colors.BOLD}Frida devices ({len(rows)}){Colors.RESET}\n")
    print(f"  {'ID':<28} {'Type':<10} Name")
    print("  " + "-" * 60)
    for d in rows:
        print(f"  {str(getattr(d, 'id', '?'))[:28]:<28} {str(getattr(d, 'type', '?'))[:10]:<10} {getattr(d, 'name', '')}")
    print("")
    return 0


def print_processes(processes, grep: "str | None" = None, limit: int = 0) -> int:
    rows = list(processes or [])
    if grep:
        pattern = re.compile(grep, re.IGNORECASE)
        rows = [p for p in rows if pattern.search(getattr(p, "name", "") or "")]
    rows.sort(key=lambda p: (getattr(p, "name", "") or "").lower())
    if not rows:
        log_warn("No processes matched.")
        return 0
    shown = rows[:limit] if limit else rows
    print(f"\n{Colors.BOLD}Processes ({len(shown)} of {len(rows)}){Colors.RESET}\n")
    print(f"  {'PID':>7}  Name")
    print("  " + "-" * 50)
    for p in shown:
        print(f"  {getattr(p, 'pid', 0):>7}  {getattr(p, 'name', '')}")
    print("")
    return 0


def print_applications(applications, grep: "str | None" = None, running_only: bool = False) -> int:
    rows = list(applications or [])
    if grep:
        pattern = re.compile(grep, re.IGNORECASE)
        rows = [
            a for a in rows
            if pattern.search(getattr(a, "identifier", "") or "") or pattern.search(getattr(a, "name", "") or "")
        ]
    if running_only:
        rows = [a for a in rows if getattr(a, "pid", 0)]
    rows.sort(key=lambda a: (getattr(a, "name", "") or "").lower())
    if not rows:
        log_warn("No applications matched.")
        return 0
    print(f"\n{Colors.BOLD}Applications ({len(rows)}){Colors.RESET}\n")
    print(f"  {'PID':>7}  {'Identifier':<42} Name")
    print("  " + "-" * 78)
    for a in rows:
        pid = getattr(a, "pid", 0)
        pid_str = str(pid) if pid else "-"
        color = Colors.GREEN if pid else Colors.DIM
        print(
            f"  {color}{pid_str:>7}{Colors.RESET}  "
            f"{str(getattr(a, 'identifier', ''))[:42]:<42} {getattr(a, 'name', '')}"
        )
    print("")
    return 0


def print_server_status(status: dict) -> int:
    print(f"\n{Colors.BOLD}frida-server status{Colors.RESET}\n")
    running = status.get("running")
    state = f"{Colors.GREEN}running{Colors.RESET}" if running else f"{Colors.RED}not running{Colors.RESET}"
    rows = [
        ("State", state + (f" (pid {status.get('pid')})" if status.get("pid") else "")),
        ("Binary", str(status.get("remote_path", "-"))),
        ("Device version", str(status.get("device_version") or "-")),
        ("Host version", str(status.get("client_version") or "-")),
    ]
    for label, value in rows:
        print(f"  {label:<16}: {value}")
    match = status.get("version_match")
    if status.get("device_version") and status.get("client_version"):
        if match:
            log_success("Host and device frida versions match.")
        else:
            log_warn("Host/device version MISMATCH - align both to the same 17.x version.")
            log_dim(f"host: {INSTALL_HINT}   device: rea frida server install --version <same>")
    print("")
    return 0


def print_messages(messages) -> int:
    rows = list(messages or [])
    if not rows:
        log_warn("No messages buffered.")
        return 0
    for entry in rows:
        msg = entry.get("message") if isinstance(entry, dict) else entry
        dev, text = format_message(msg)
        print(f"  [dev {dev}] {text}")
    return 0


# ---------------------------------------------------------------------------
# Setup help + doctor
# ---------------------------------------------------------------------------


def print_frida_setup_help() -> None:
    print(
        f"""
{Colors.BOLD}Frida dynamic instrumentation setup:{Colors.RESET}

  1. Install the host package (17.x is the target; the Java/ObjC bridge is loaded
     on demand, so no 16.x pin is needed):
       {Colors.CYAN}{INSTALL_HINT}{Colors.RESET}

  2. Install + start frida-server on a rooted device (downloads a version-matched
     binary and launches it detached):
       {Colors.CYAN}rea frida setup{Colors.RESET}            install the server and start it
       {Colors.CYAN}rea frida server status{Colors.RESET}    check liveness and the version match

  3. Verify everything:
       {Colors.CYAN}rea frida doctor{Colors.RESET}

{Colors.BOLD}A typical session:{Colors.RESET}

  {Colors.CYAN}rea frida ps --apps{Colors.RESET}                      list installed apps and running pids
  {Colors.CYAN}rea frida probe <target> --script probe_net --spawn{Colors.RESET}   spawn + network probe
  {Colors.CYAN}rea frida probe <target> --file my.js -d 120{Colors.RESET}          run your own script
  {Colors.CYAN}rea frida rpc <target> --file rpc_template.js --repl{Colors.RESET}  call rpc.exports live
  {Colors.CYAN}rea frida mem read <target> --address 0x.. --size 64{Colors.RESET}  read process memory

{Colors.BOLD}Why remote over USB:{Colors.RESET} REA_Kit forwards tcp:{DEFAULT_FRIDA_PORT} and attaches an explicit
  remote device, so an attached emulator cannot hijack the USB auto-selection.
"""
    )


def doctor(config_mgr: "ConfigManager", serial: "str | None" = None) -> int:
    """Reports the state of every Frida prerequisite. Returns 0 when all are OK."""
    print("")
    ok = True
    port = frida_port(config_mgr)

    # 1. Host frida module.
    hv = host_frida_version()
    if hv:
        if hv.startswith("17."):
            log_success(f"Host frida module: {hv}")
        elif hv.startswith("16."):
            log_info(f"Host frida module: {hv} (16.x works; REA_Kit now targets 17.x)")
        else:
            log_warn(f"Host frida module: {hv} (REA_Kit targets 17.x)")
    else:
        log_error(f"Host frida module not installed ({INSTALL_HINT})")
        ok = False

    # 2. frida-ps CLI (optional convenience).
    frida_ps = shutil.which("frida-ps") or shutil.which("frida-ps.exe")
    if frida_ps:
        log_success(f"frida-ps CLI: {frida_ps}")
    else:
        log_info("frida-ps CLI not on PATH (optional; comes with the frida-tools package).")

    # 3. adb reachable + a device present.
    adb = AdbHelper(serial)
    device_ok = False
    try:
        if adb.is_reachable():
            log_success("adb device reachable.")
            device_ok = True
        else:
            log_warn("adb present but no device in state 'device' (check: adb devices).")
            ok = False
    except FridaError as exc:
        log_error(str(exc))
        ok = False

    # 4. Device ABI + frida-server liveness/version + root.
    if device_ok:
        mgr = FridaServerManager(adb, config_mgr)
        try:
            abi = mgr.detect_abi()
            log_success(f"Device ABI: {abi}")
        except FridaError as exc:
            log_warn(str(exc))

        try:
            status = mgr.status()
            if status["running"]:
                dv = status.get("device_version") or "?"
                if status["version_match"]:
                    log_success(f"frida-server running (v{dv}) and matches the host.")
                elif status.get("client_version"):
                    log_warn(
                        f"frida-server running (v{dv}) but the host is v{status['client_version']} - "
                        f"align both to the same 17.x version."
                    )
                    ok = False
                else:
                    log_success(f"frida-server running (v{dv}).")
            else:
                log_warn("frida-server is not running (rea frida server start).")
                ok = False
        except FridaError as exc:
            log_warn(f"Could not read frida-server status: {exc}")
            ok = False

        if adb.is_root():
            log_success("Device root available (su -c id -> uid 0).")
        else:
            log_warn("No root (su) - frida-server needs root on most devices.")
            ok = False

    # 5. Bundled agents.
    agents = _list_agents()
    if agents:
        log_success(f"Bundled agents: {', '.join(agents)}")
    else:
        log_info(f"No bundled JS agents found yet in {FRIDA_AGENTS_DIR}.")

    if not ok:
        print_frida_setup_help()
    print("")
    log_dim(f"(host-side forwarded port: {port})")
    return 0 if ok else 1


# ---------------------------------------------------------------------------
# Optional MCP bridge (everything to stderr, like the HTTP bridge)
# ---------------------------------------------------------------------------


def _find_frida_mcp() -> "list[str] | None":
    """Finds a command that runs a Frida MCP server, if one is installed."""
    for exe_name in ("frida-mcp", "ya-frida-mcp"):
        exe = shutil.which(exe_name) or shutil.which(exe_name + ".exe")
        if exe:
            return [exe]
    for mod in ("ya_frida_mcp", "frida_mcp"):
        try:
            if importlib.util.find_spec(mod) is not None:
                return [sys.executable, "-m", mod]
        except (ImportError, ValueError):
            continue
    return None


def print_mcp_config(config_mgr: "ConfigManager | None" = None) -> int:
    """Prints MCP client configuration for a Frida MCP bridge."""
    cmd = _find_frida_mcp()
    if not cmd:
        log_warn("No Frida MCP server found on PATH.")
        log_info("Install one (e.g. 'pip install ya-frida-mcp'), then re-run 'rea frida mcp --config'.")
        cmd = ["ya-frida-mcp"]
    config = {
        "mcpServers": {
            "frida": {
                "type": "stdio",
                "command": cmd[0],
                "args": cmd[1:],
            }
        }
    }
    print(json.dumps(config, indent=2))
    print(f"\n{Colors.BOLD}Add it to Claude Code:{Colors.RESET}")
    print(f"  claude mcp add frida -- {' '.join(cmd)}\n")
    return 0


def run_mcp_bridge(config_mgr: "ConfigManager | None" = None, extra_args: "list[str] | None" = None) -> int:
    """Runs a Frida MCP server so an AI client can drive instrumentation.

    All diagnostics go to stderr: in stdio MCP transport the child's stdout is the
    JSON-RPC channel, so a stray log line there breaks the handshake.
    """
    cmd = _find_frida_mcp()
    if not cmd:
        print("[-] No Frida MCP bridge is installed.", file=sys.stderr)
        print("    Install one, e.g.: pip install ya-frida-mcp", file=sys.stderr)
        return 1
    cmd = cmd + (extra_args or [])
    print(f"[*] Launching Frida MCP bridge: {' '.join(cmd)}", file=sys.stderr)
    try:
        return subprocess.run(cmd).returncode
    except KeyboardInterrupt:
        return 0
    except OSError as exc:
        print(f"[-] Could not launch the Frida MCP bridge: {exc}", file=sys.stderr)
        return 1
