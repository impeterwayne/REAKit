"""Offline tests for reakit.mobilerun - 'rea device' wiring over mobilerun-mcp.

No device, no venv, no network: ``subprocess.run`` and the venv lookup are
mocked, so these check argparse wiring, the spawned command lines, the
environment every spawn gets (MOBILERUN_ADB_BIN / MOBILERUN_DEVICE), the
missing-venv error path and the 'mcp --config' output shape.
"""

import contextlib
import io
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from reakit import mobilerun as mr
from reakit import mobilerun_runner as runner
from reakit.cli import create_parser

FAKE_PY = Path("/fake/venv/python")
FAKE_ADB = os.path.abspath("/fake/vendor/adb")


def parse(*argv):
    return create_parser().parse_args(list(argv))


def completed(stdout="", code=0):
    return subprocess.CompletedProcess(args=[], returncode=code, stdout=stdout)


@contextlib.contextmanager
def fake_venv(py=FAKE_PY):
    """Pretend the venv exists and keep build_env off the real os.environ/PATH."""
    base = {"PATH": os.pathsep.join(["/usr/bin", os.path.dirname(FAKE_ADB)]), "ADB_PATH": FAKE_ADB}
    real_build = mr.build_env

    with mock.patch.object(mr, "find_mobilerun_python", return_value=py), \
            mock.patch.object(mr, "build_env", side_effect=lambda serial=None: real_build(serial, base=dict(base))):
        yield


class TestParser(unittest.TestCase):
    def test_every_subcommand_parses(self):
        cases = {
            ("mcp",): {"device_mcp_config": False, "http": False, "port": mr.DEFAULT_HTTP_PORT},
            ("mcp", "--config"): {"device_mcp_config": True},
            ("mcp", "--http", "--port", "5000"): {"http": True, "port": 5000},
            ("list",): {},
            ("setup",): {},
            ("doctor",): {},
            ("screenshot", "out/s.png"): {"out": "out/s.png"},
            ("ui-dump", "u.json"): {"out": "u.json"},
            ("tap", "10", "20"): {"x": 10, "y": 20},
            ("swipe", "1", "2", "3", "4"): {"x1": 1, "y1": 2, "x2": 3, "y2": 4, "ms": None},
            ("swipe", "1", "2", "3", "4", "500"): {"ms": 500},
            ("write", "hello world"): {"text": "hello world"},
            ("key", "back"): {"key": "back"},
            ("key", "66"): {"key": "66"},
            ("app-start", "com.x"): {"package": "com.x", "activity": None},
            ("app-start", "com.x", ".Main"): {"activity": ".Main"},
            ("app-stop", "com.x"): {"package": "com.x"},
            ("apps",): {"system": False},
            ("apps", "--system"): {"system": True},
            ("clipboard-get",): {},
            ("clipboard-set", "abc"): {"text": "abc"},
        }
        for argv, expected in cases.items():
            with self.subTest(argv=argv):
                args = parse("device", *argv)
                self.assertEqual(args.command, "device")
                self.assertEqual(args.device_action, argv[0])
                for key, value in expected.items():
                    self.assertEqual(getattr(args, key), value)

    def test_alias_and_group_options(self):
        args = parse("dev", "-s", "emu-1", "--json", "tap", "1", "2")
        self.assertEqual(args.command, "dev")
        self.assertEqual(args.serial, "emu-1")
        self.assertTrue(args.json)

    def test_serial_after_action_and_not_clobbered(self):
        self.assertEqual(parse("device", "tap", "1", "2", "-s", "X").serial, "X")
        args = parse("device", "-s", "G", "list")
        self.assertEqual(args.serial, "G")
        self.assertFalse(parse("device", "list").json)
        self.assertIsNone(parse("device", "list").serial)

    def test_mcp_config_does_not_clash_with_global_config(self):
        args = parse("device", "mcp", "--config")
        self.assertTrue(args.device_mcp_config)
        self.assertIsNone(args.config)  # top-level ConfigManager path untouched

    def test_scrcpy_command_removed(self):
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            parse("scrcpy", "tap", "1", "2")
        self.assertEqual(parse("mirror", "-s", "X").serial, "X")

    def test_install_skip_mobilerun(self):
        self.assertTrue(parse("install", "--skip-mobilerun").skip_mobilerun)
        self.assertFalse(parse("install").skip_mobilerun)


class TestEnv(unittest.TestCase):
    def test_adb_and_device_are_pinned(self):
        base = {"PATH": "/usr/bin", "ADB_PATH": FAKE_ADB}
        env = mr.build_env("serial-1", base=base)
        self.assertEqual(env["MOBILERUN_ADB_BIN"], FAKE_ADB)
        self.assertEqual(env["ADBUTILS_ADB_PATH"], FAKE_ADB)
        self.assertEqual(env["MOBILERUN_DEVICE"], "serial-1")
        self.assertEqual(env["PATH"].split(os.pathsep)[0], os.path.dirname(FAKE_ADB))
        self.assertNotIn("MOBILERUN_DEVICE", base)  # base is not mutated

    def test_existing_device_env_kept_without_serial(self):
        env = mr.build_env(None, base={"PATH": "", "ADB_PATH": FAKE_ADB, "MOBILERUN_DEVICE": "keep"})
        self.assertEqual(env["MOBILERUN_DEVICE"], "keep")

    def test_adb_dir_not_duplicated_on_path(self):
        adb_dir = os.path.dirname(FAKE_ADB)
        env = mr.build_env(None, base={"PATH": os.pathsep.join(["/a", adb_dir]), "ADB_PATH": FAKE_ADB})
        self.assertEqual(env["PATH"].split(os.pathsep), [adb_dir, "/a"])


class TestDispatch(unittest.TestCase):
    def run_cli(self, *argv, stdout=""):
        args = parse("device", *argv)
        out = io.StringIO()
        with fake_venv(), mock.patch.object(mr.subprocess, "run", return_value=completed(stdout)) as run, \
                contextlib.redirect_stdout(out):
            code = mr.handle(args)
        return code, run, out.getvalue()

    def test_runner_command_line_and_env(self):
        code, run, out = self.run_cli(
            "-s", "dev-9", "tap", "5", "6",
            stdout=json.dumps({"device": "dev-9", "action": "tap", "x": 5, "y": 6}),
        )
        self.assertEqual(code, 0)
        cmd = run.call_args.args[0]
        self.assertEqual(cmd[:3], [str(FAKE_PY), "-I", str(mr.RUNNER)])
        self.assertEqual(cmd[3:], ["tap", "5", "6"])
        env = run.call_args.kwargs["env"]
        self.assertEqual(env["MOBILERUN_DEVICE"], "dev-9")
        self.assertEqual(env["MOBILERUN_ADB_BIN"], FAKE_ADB)
        self.assertIn("Tapped (5, 6)", out)

    def test_runner_argv_mapping(self):
        cases = [
            (("swipe", "1", "2", "3", "4", "250"), ["swipe", "1", "2", "3", "4", "250"]),
            (("swipe", "1", "2", "3", "4"), ["swipe", "1", "2", "3", "4"]),
            (("app-start", "com.a", ".B"), ["app-start", "com.a", ".B"]),
            (("apps", "--system"), ["apps", "--system"]),
            (("write", "hi there"), ["write", "hi there"]),
            (("screenshot", "x/s.png"), ["screenshot", "x/s.png"]),
            (("ui-dump", "u.json"), ["ui-dump", "u.json"]),
            (("key", "66"), ["key", "66"]),
            (("clipboard-set", "v"), ["clipboard-set", "v"]),
            (("list",), ["list"]),
        ]
        for argv, expected in cases:
            with self.subTest(argv=argv):
                _, run, _ = self.run_cli(*argv, stdout="{}")
                self.assertEqual(run.call_args.args[0][3:], expected)

    def test_json_flag_prints_raw_result(self):
        payload = {"device": "d", "text": "clip"}
        code, _, out = self.run_cli("--json", "clipboard-get", stdout=json.dumps(payload))
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out), payload)

    def test_runner_failure_propagates_exit_code(self):
        args = parse("device", "ui-dump", "u.json")
        with fake_venv(), mock.patch.object(mr.subprocess, "run", return_value=completed("", 1)):
            self.assertEqual(mr.handle(args), 1)

    def test_doctor_and_setup_use_mobilerun_cli(self):
        for action in ("doctor", "setup"):
            with self.subTest(action=action):
                code, run, _ = self.run_cli("-s", "abc", action)
                self.assertEqual(code, 0)
                cmd = run.call_args.args[0]
                self.assertEqual(cmd[-3:], [action, "-d", "abc"])
                self.assertEqual(run.call_args.kwargs["env"]["MOBILERUN_DEVICE"], "abc")

    def test_mcp_stdio_and_http(self):
        err = io.StringIO()
        with fake_venv(), mock.patch.object(mr.subprocess, "run", return_value=completed()) as run, \
                contextlib.redirect_stderr(err):
            self.assertEqual(mr.handle(parse("device", "mcp")), 0)
            self.assertEqual(run.call_args.args[0], [str(FAKE_PY), "-I", "-m", "mobilerun_mcp"])
            self.assertEqual(mr.handle(parse("device", "-s", "q", "mcp", "--http", "--port", "4900")), 0)
            self.assertEqual(run.call_args.args[0][-3:], ["--http", "--port", "4900"])
            self.assertEqual(run.call_args.kwargs["env"]["MOBILERUN_DEVICE"], "q")
        self.assertIn("mobilerun MCP server", err.getvalue())


class TestMissingVenv(unittest.TestCase):
    def test_actions_fail_with_install_hint(self):
        for argv in (("list",), ("tap", "1", "2"), ("mcp",), ("doctor",)):
            with self.subTest(argv=argv):
                err, out = io.StringIO(), io.StringIO()
                with mock.patch.object(mr, "find_mobilerun_python", return_value=None), \
                        mock.patch.object(mr.subprocess, "run") as run, \
                        contextlib.redirect_stderr(err), contextlib.redirect_stdout(out):
                    code = mr.handle(parse("device", *argv))
                self.assertEqual(code, 1)
                run.assert_not_called()
                self.assertIn("rea install", err.getvalue())
                self.assertEqual(out.getvalue(), "")  # stdout stays clean (MCP channel)


class TestMcpConfig(unittest.TestCase):
    def test_shape_and_hint(self):
        out = io.StringIO()
        with mock.patch.object(mr, "rea_launcher", return_value=["rea"]), \
                mock.patch.object(mr, "find_mobilerun_python", return_value=FAKE_PY), \
                contextlib.redirect_stdout(out):
            self.assertEqual(mr.handle(parse("device", "mcp", "--config")), 0)
        text = out.getvalue()
        config = json.loads(text[: text.index("\n}") + 2])
        entry = config["mcpServers"]["mobilerun"]
        self.assertEqual(entry, {"type": "stdio", "command": "rea", "args": ["device", "mcp"]})
        self.assertIn("claude mcp add mobilerun -- rea device mcp", text)

    def test_serial_is_forwarded_and_fallback_launcher(self):
        with mock.patch.object(mr.shutil, "which", return_value=None):
            entry = mr.mcp_config("S1")["mcpServers"]["mobilerun"]
        self.assertEqual(entry["command"], sys.executable)
        self.assertTrue(entry["args"][0].endswith("rea.py"))
        self.assertEqual(entry["args"][1:], ["device", "-s", "S1", "mcp"])

    def test_committed_configs_launch_rea_device_mcp(self):
        root = Path(__file__).resolve().parent.parent
        for name in (".mcp.json", ".agents/mcp_config.json"):
            with self.subTest(file=name):
                entry = json.loads((root / name).read_text(encoding="utf-8"))["mcpServers"]["mobilerun"]
                self.assertEqual([entry["command"]] + entry["args"], ["rea", "device", "mcp"])


class TestRunnerArgs(unittest.TestCase):
    """The runner validates arity before importing mobilerun_mcp (not installed here)."""

    def run_main(self, *argv):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = runner.main(list(argv))
        return code, err.getvalue()

    def test_usage_errors(self):
        self.assertEqual(self.run_main()[0], 2)
        self.assertEqual(self.run_main("bogus")[0], 2)
        self.assertEqual(self.run_main("tap", "1")[0], 2)
        self.assertEqual(self.run_main("swipe", "1", "2", "3", "4", "5", "6")[0], 2)

    def test_commands_match_cli(self):
        self.assertEqual(set(runner.ARITY), set(mr.RUNNER_COMMANDS))


LIST_TOOLS = """
import asyncio, json
from mobilerun_mcp.config import Config
from mobilerun_mcp.server import build_server
tools = asyncio.run(build_server(Config.from_env()).list_tools())
print(json.dumps(sorted(t.name for t in tools)))
"""


@unittest.skipUnless(mr.find_mobilerun_python(), "mobilerun venv not installed (rea install)")
class TestSkillCoversEveryTool(unittest.TestCase):
    """Fails when the device-control skill stops naming a tool the server exposes.

    Asks the real server (in its venv, with the opt-in adb tool enabled) for its
    tool list, so a submodule bump that adds tools turns this red until the
    skill's tool index is updated.
    """

    def test_every_tool_is_named_in_the_skill(self):
        env = dict(os.environ, MOBILERUN_MCP_ENABLE_ADB="1")
        res = subprocess.run(
            [str(mr.find_mobilerun_python()), "-I", "-c", LIST_TOOLS],
            capture_output=True, text=True, env=env, timeout=300, check=False,
        )
        self.assertEqual(res.returncode, 0, res.stderr[-2000:])
        tools = json.loads(res.stdout.strip().splitlines()[-1])
        self.assertGreater(len(tools), 50)
        skill = (Path(__file__).resolve().parent.parent / ".agents" / "skills" / "device-control" / "SKILL.md")
        text = skill.read_text(encoding="utf-8")
        missing = [t for t in tools if f"`{t}`" not in text]
        self.assertEqual(missing, [], f"tools missing from {skill.name}'s tool index: {missing}")


if __name__ == "__main__":
    unittest.main()
