import os
import shutil
import subprocess
from pathlib import Path
from reakit.config import CORE_DIR
from reakit.env import find_scrcpy_dir
from reakit.utils import log_info, log_success, log_error

class ScrcpyBridge:
    """Desktop screen mirroring with the vendored scrcpy binary (rea mirror).

    Device control moved to mobilerun-mcp (reakit/mobilerun.py, rea device).
    """

    def __init__(self):
        self.scrcpy_dir = find_scrcpy_dir() or (CORE_DIR / "scrcpy_cli" / "vendor" / "scrcpy")

    def launch_mirror(
        self,
        serial: str | None = None,
        max_size: int | None = None,
        max_fps: int | None = None,
        extra_args: list[str] | None = None,
    ) -> int:
        """Launches interactive desktop screen mirroring using bundled scrcpy.exe."""
        scrcpy_exe = self.scrcpy_dir / ("scrcpy.exe" if os.name == "nt" else "scrcpy")
        if not scrcpy_exe.exists():
            scrcpy_exe_path = shutil.which("scrcpy")
            if not scrcpy_exe_path:
                log_error("scrcpy executable not found in bundled core directory or system PATH.")
                return 1
            scrcpy_exe = Path(scrcpy_exe_path)

        cmd = [str(scrcpy_exe.resolve())]
        if serial:
            cmd.extend(["-s", serial])
        if max_size:
            cmd.extend(["-m", str(max_size)])
        if max_fps:
            cmd.extend(["--max-fps", str(max_fps)])
        if extra_args:
            cmd.extend(extra_args)

        # Setup environment variables for scrcpy
        env = os.environ.copy()
        if self.scrcpy_dir.exists():
            server_path = self.scrcpy_dir / "scrcpy-server"
            existing_server = env.get("SCRCPY_SERVER_PATH")
            if server_path.exists() and (not existing_server or not Path(existing_server).exists()):
                env["SCRCPY_SERVER_PATH"] = str(server_path.resolve())

            adb_file = self.scrcpy_dir / ("adb.exe" if os.name == "nt" else "adb")
            existing_adb = env.get("ADB_PATH") or env.get("ADB")
            if adb_file.exists() and (not existing_adb or not Path(existing_adb).exists()):
                env["ADB_PATH"] = str(adb_file.resolve())
                env["ADB"] = str(adb_file.resolve())

        log_info(f"Launching screen mirroring: {' '.join(cmd)}")
        try:
            cwd = str(self.scrcpy_dir.resolve()) if self.scrcpy_dir.exists() else None
            subprocess.Popen(cmd, cwd=cwd, env=env)
            log_success("Interactive scrcpy mirroring window started.")
            return 0
        except Exception as e:
            log_error(f"Failed to launch scrcpy: {e}")
            return 1
