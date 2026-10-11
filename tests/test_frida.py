"""Offline tests for reakit.fridakit - config wiring, target resolution, script
buffering, RPC export normalization, frida-server management and bundled agents.

These run anywhere: no real ``frida`` package, no device, no network. Everything
that would touch a device, the host frida module or the GitHub releases API is
replaced with a fake that is injected into the object under test (mirroring how
test_httptoolkit swaps ``client._connect``). The one place that reaches the
network - ``FridaServerManager.resolve_version`` - has its ``_http_json`` helper
monkeypatched to a canned payload, so no socket is ever opened.
"""

import importlib.util
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from reakit.config import ConfigManager
from reakit import fridakit as fk


# ---------------------------------------------------------------------------
# Fakes (no real frida / adb / device / network)
# ---------------------------------------------------------------------------


class FakeExports:
    """Stands in for a script's ``exports_sync`` object.

    Each advertised export name becomes a callable attribute so ``getattr`` on
    the real resolver finds it, mirroring frida's own RPC proxy.
    """

    def __init__(self, names):
        for n in names:
            setattr(self, n, self._make(n))

    @staticmethod
    def _make(name):
        return lambda *a, **k: ("called", name, a)


class FakeScript:
    """Stands in for a ``frida.core.Script`` for ScriptHandle / RPC tests."""

    def __init__(self, export_names=(), *, with_list=True, exports_attr="exports_sync"):
        self._export_names = list(export_names)
        self._with_list = with_list
        self.is_destroyed = False
        self.handlers = []
        self.unloaded = False
        if export_names:
            setattr(self, exports_attr, FakeExports(export_names))

    def on(self, event, callback):
        self.handlers.append((event, callback))

    def list_exports(self):
        return list(self._export_names) if self._with_list else None

    def unload(self):
        self.unloaded = True


class FakeProc:
    def __init__(self, pid, name):
        self.pid = pid
        self.name = name


class FakeApp:
    def __init__(self, pid, identifier):
        self.pid = pid
        self.identifier = identifier


class FakeDevice:
    """Minimal stand-in for FridaDevice, for TargetSpec.resolve."""

    def __init__(self, procs=(), apps=(), frontmost=None):
        self._procs = list(procs)
        self._apps = list(apps)
        self._frontmost = frontmost
        self.id = "fake-device"

    def enumerate_processes(self):
        return self._procs

    def enumerate_applications(self):
        return self._apps

    def get_frontmost(self):
        return self._frontmost


class FakeAdb:
    """Stand-in for AdbHelper exposing only ``.shell`` with canned getprop output."""

    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def shell(self, cmd, timeout=60):
        self.calls.append(cmd)
        for key, val in self.responses.items():
            if key in cmd:
                return val
        return ""


def new_session_manager():
    """A SessionManager whose device is a bare stub (RPC tests never touch it)."""
    return fk.SessionManager(types.SimpleNamespace(id="dev0"))


# ---------------------------------------------------------------------------
# Config paths
# ---------------------------------------------------------------------------


class TestConfigPaths(unittest.TestCase):
    def test_frida_path_is_provisioned(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = ConfigManager(workspace_root=Path(tmp) / "ws")
            paths = cfg.get_app_paths("com.test.app")
            self.assertIn("frida", paths)
            self.assertEqual(paths["frida"].name, "frida")
            self.assertEqual(paths["frida"].parent.name, "dynamic")
            self.assertTrue(paths["frida"].as_posix().endswith("dynamic/frida"))


# ---------------------------------------------------------------------------
# Env > config > default resolution
# ---------------------------------------------------------------------------


class TestResolution(unittest.TestCase):
    ENV_KEYS = ("FRIDA_PORT", "FRIDA_VERSION", "FRIDA_SERVER_NAME")

    def _isolated_cfg(self, tmp, **values):
        """A ConfigManager that never reads the repo config file (nonexistent path)."""
        cfg = ConfigManager(config_path=Path(tmp) / "none.json", workspace_root=Path(tmp) / "ws")
        for k in ("fridaServerPort", "fridaVersion", "fridaServerName"):
            cfg.config_data.pop(k, None)
        cfg.config_data.update(values)
        return cfg

    def test_defaults_when_nothing_set(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(fk.frida_port(None), fk.DEFAULT_FRIDA_PORT)
            self.assertEqual(fk.frida_version(None), fk.DEFAULT_FRIDA_VERSION)
            self.assertEqual(fk.server_name(None), fk.DEFAULT_SERVER_NAME)
            self.assertEqual(fk.frida_port(None), 27042)
            self.assertEqual(fk.frida_version(None), "17")
            self.assertEqual(fk.server_name(None), "frida-server")

    def test_config_over_default(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {}, clear=True):
            cfg = self._isolated_cfg(
                tmp,
                fridaServerPort="9999",
                fridaVersion="17.7.19",
                fridaServerName="my-server",
            )
            self.assertEqual(fk.frida_port(cfg), 9999)
            self.assertEqual(fk.frida_version(cfg), "17.7.19")
            self.assertEqual(fk.server_name(cfg), "my-server")

    def test_env_over_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = self._isolated_cfg(
                tmp,
                fridaServerPort="9999",
                fridaVersion="17.0.0",
                fridaServerName="cfg-server",
            )
            env = {"FRIDA_PORT": "12345", "FRIDA_VERSION": "17.9.9", "FRIDA_SERVER_NAME": "env-server"}
            with mock.patch.dict(os.environ, env, clear=True):
                self.assertEqual(fk.frida_port(cfg), 12345)
                self.assertEqual(fk.frida_version(cfg), "17.9.9")
                self.assertEqual(fk.server_name(cfg), "env-server")

    def test_non_numeric_port_falls_back_to_default(self):
        with mock.patch.dict(os.environ, {"FRIDA_PORT": "not-a-number"}, clear=True):
            self.assertEqual(fk.frida_port(None), fk.DEFAULT_FRIDA_PORT)


# ---------------------------------------------------------------------------
# TargetSpec
# ---------------------------------------------------------------------------


class TestTargetSpec(unittest.TestCase):
    def test_exactly_one_selector_required(self):
        with self.assertRaises(fk.FridaError):
            fk.TargetSpec()  # zero selectors
        with self.assertRaises(fk.FridaError):
            fk.TargetSpec(pid=1, name="x")  # two selectors
        with self.assertRaises(fk.FridaError):
            fk.TargetSpec(name="x", frontmost=True)  # two selectors

    def test_single_selector_ok(self):
        self.assertEqual(fk.TargetSpec(pid=42).pid, 42)
        self.assertEqual(fk.TargetSpec(name="proc").name, "proc")
        self.assertEqual(fk.TargetSpec(identifier="com.x.y").identifier, "com.x.y")
        self.assertTrue(fk.TargetSpec(frontmost=True).frontmost)

    def test_from_args_dotted_default_is_identifier(self):
        spec = fk.TargetSpec.from_args(default="com.example.app")
        self.assertEqual(spec.identifier, "com.example.app")
        self.assertIsNone(spec.name)

    def test_from_args_plain_default_is_name(self):
        spec = fk.TargetSpec.from_args(default="someproc")
        self.assertEqual(spec.name, "someproc")
        self.assertIsNone(spec.identifier)

    def test_from_args_explicit_flag_wins(self):
        spec = fk.TargetSpec.from_args(pid=777, default="com.example.app")
        self.assertEqual(spec.pid, 777)

    def test_from_args_requires_a_target(self):
        with self.assertRaises(fk.FridaError):
            fk.TargetSpec.from_args()

    def test_resolve_pid_passthrough(self):
        device = FakeDevice()
        self.assertEqual(fk.TargetSpec(pid=1234).resolve(device), 1234)

    def test_resolve_name_against_fake_device(self):
        device = FakeDevice(procs=[FakeProc(10, "init"), FakeProc(20, "com.target")])
        self.assertEqual(fk.TargetSpec(name="com.target").resolve(device), 20)

    def test_resolve_identifier_against_fake_device(self):
        device = FakeDevice(apps=[FakeApp(55, "com.example.app")])
        self.assertEqual(fk.TargetSpec(identifier="com.example.app").resolve(device), 55)

    def test_resolve_missing_name_raises(self):
        device = FakeDevice(procs=[FakeProc(10, "init")])
        with self.assertRaises(fk.FridaError):
            fk.TargetSpec(name="nope").resolve(device)


# ---------------------------------------------------------------------------
# ScriptHandle message buffer
# ---------------------------------------------------------------------------


class TestScriptHandle(unittest.TestCase):
    def _handle(self, max_messages=fk.DEFAULT_MESSAGE_CAP):
        return fk.ScriptHandle(FakeScript(), pid=1, script_id="s1", max_messages=max_messages)

    def test_get_messages_drains(self):
        handle = self._handle()
        handle._on_message({"type": "send", "payload": {"tag": "A"}}, None)
        handle._on_message({"type": "send", "payload": {"tag": "B"}}, None)
        first = handle.get_messages()
        self.assertEqual(len(first), 2)
        self.assertEqual(handle.get_messages(), [])  # drained

    def test_binary_data_is_hex_encoded(self):
        handle = self._handle()
        handle._on_message({"type": "send"}, b"\xde\xad\xbe\xef")
        out = handle.get_messages()
        self.assertEqual(out[0]["data"], "deadbeef")

    def test_registers_message_handler(self):
        script = FakeScript()
        fk.ScriptHandle(script, pid=1, script_id="s1")
        self.assertEqual(script.handlers[0][0], "message")

    def test_cap_bounds_the_buffer(self):
        handle = self._handle(max_messages=10)
        for i in range(25):
            handle._on_message({"type": "send", "payload": {"i": i}}, None)
        out = handle.get_messages()
        self.assertEqual(len(out), 10)
        self.assertEqual(handle.dropped, 15)
        # Oldest were dropped: the surviving window is the last 10.
        self.assertEqual(out[0]["message"]["payload"]["i"], 15)
        self.assertEqual(out[-1]["message"]["payload"]["i"], 24)


# ---------------------------------------------------------------------------
# RPC export normalization - the key cross-worker contract
# ---------------------------------------------------------------------------


class TestResolveExport(unittest.TestCase):
    CANDIDATES = ("readMem", "read", "readMemory", "memRead")

    def _handle_advertising(self, name):
        script = FakeScript(export_names=[name])
        return fk.ScriptHandle(script, pid=1, script_id="s1")

    def test_camelcase_exact(self):
        sm = new_session_manager()
        fn = sm._resolve_export(self._handle_advertising("readMemory"), *self.CANDIDATES)
        self.assertTrue(callable(fn))

    def test_snake_case_normalizes(self):
        sm = new_session_manager()
        fn = sm._resolve_export(self._handle_advertising("read_memory"), *self.CANDIDATES)
        self.assertTrue(callable(fn))

    def test_lowercase_normalizes(self):
        sm = new_session_manager()
        fn = sm._resolve_export(self._handle_advertising("readmemory"), *self.CANDIDATES)
        self.assertTrue(callable(fn))

    def test_all_spellings_resolve(self):
        sm = new_session_manager()
        for spelling in ("readMemory", "read_memory", "readmemory"):
            with self.subTest(spelling=spelling):
                fn = sm._resolve_export(self._handle_advertising(spelling), *self.CANDIDATES)
                self.assertIsNotNone(fn, f"{spelling} should resolve for {self.CANDIDATES}")
                self.assertTrue(callable(fn))

    def test_unrelated_export_does_not_resolve(self):
        sm = new_session_manager()
        fn = sm._resolve_export(self._handle_advertising("writeMemory"), *self.CANDIDATES)
        self.assertIsNone(fn)

    def test_export_names_lists_advertised(self):
        sm = new_session_manager()
        handle = self._handle_advertising("read_memory")
        self.assertEqual(sm._export_names(handle), ["read_memory"])


# ---------------------------------------------------------------------------
# FridaServerManager - ABI detection and version resolution (no network)
# ---------------------------------------------------------------------------


RELEASES_PAGE = [
    {"tag_name": "17.2.3"},
    {"tag_name": "17.1.0"},
    {"tag_name": "17.0.0"},
    {"tag_name": "16.7.19"},
]


class TestFridaServerManager(unittest.TestCase):
    def test_detect_abi_maps_getprop(self):
        adb = FakeAdb({"ro.product.cpu.abi": "arm64-v8a"})
        mgr = fk.FridaServerManager(adb=adb, config_mgr=None)
        self.assertEqual(mgr.detect_abi(), "arm64")

    def test_detect_abi_falls_back_to_abilist(self):
        adb = FakeAdb({
            "ro.product.cpu.abilist": "weird-abi,armeabi-v7a",
            "ro.product.cpu.abi": "weird-abi",
        })
        mgr = fk.FridaServerManager(adb=adb, config_mgr=None)
        self.assertEqual(mgr.detect_abi(), "arm")

    def test_detect_abi_empty_raises(self):
        adb = FakeAdb({})
        mgr = fk.FridaServerManager(adb=adb, config_mgr=None)
        with self.assertRaises(fk.FridaError):
            mgr.detect_abi()

    def test_resolve_version_major_picks_latest_17(self):
        adb = FakeAdb({})
        mgr = fk.FridaServerManager(adb=adb, config_mgr=None)
        calls = []

        def fake_http_json(url, timeout=60):
            calls.append(url)
            return RELEASES_PAGE if "page=1" in url else []

        with mock.patch.object(fk, "_http_json", side_effect=fake_http_json):
            self.assertEqual(mgr.resolve_version("17"), "17.2.3")
        self.assertTrue(calls, "a GitHub listing should have been consulted for a bare major")

    def test_resolve_version_exact_passthrough_no_network(self):
        adb = FakeAdb({})
        mgr = fk.FridaServerManager(adb=adb, config_mgr=None)
        with mock.patch.object(fk, "_http_json", side_effect=AssertionError("network hit")):
            self.assertEqual(mgr.resolve_version("17.2.3"), "17.2.3")


# ---------------------------------------------------------------------------
# Bundled agents
# ---------------------------------------------------------------------------


class TestBuiltinAgent(unittest.TestCase):
    def test_all_six_builtin_agents_load_nonempty(self):
        for name in fk.BUILTIN_AGENTS:
            with self.subTest(agent=name):
                src = fk.builtin_agent(name)
                self.assertIsInstance(src, str)
                self.assertTrue(src.strip(), f"{name} should have source")

    def test_name_without_extension_is_accepted(self):
        bare = fk.BUILTIN_AGENTS[0][:-3]  # strip ".js"
        self.assertTrue(fk.builtin_agent(bare).strip())

    def test_unknown_agent_raises(self):
        with self.assertRaises(fk.FridaError):
            fk.builtin_agent("no_such_agent_xyz.js")


# ---------------------------------------------------------------------------
# host_frida_version - never raises, str or None either way
# ---------------------------------------------------------------------------


class TestHostFridaVersion(unittest.TestCase):
    def test_returns_str_or_none_as_is(self):
        result = fk.host_frida_version()
        self.assertTrue(result is None or isinstance(result, str))

    def test_absent_frida_returns_none(self):
        with mock.patch("importlib.util.find_spec", return_value=None):
            self.assertIsNone(fk.host_frida_version())

    @unittest.skipUnless(
        importlib.util.find_spec("frida") is not None,
        "real frida package not installed on host",
    )
    def test_present_frida_returns_str_or_none(self):
        result = fk.host_frida_version()
        self.assertTrue(result is None or isinstance(result, str))


if __name__ == "__main__":
    unittest.main(verbosity=2)
