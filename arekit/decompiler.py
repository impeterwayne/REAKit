import os
import shutil
import zipfile
import subprocess
from pathlib import Path
from arekit.config import ConfigManager, CORE_DIR
from arekit.utils import log_info, log_success, log_warn, log_error

class Decompiler:
    def __init__(self, config_mgr: ConfigManager | None = None, jadx_path: Path | str | None = None):
        self.config_mgr = config_mgr or ConfigManager()
        self.jadx_path = Path(jadx_path) if jadx_path else self._find_jadx()

    def _find_jadx(self) -> Path:
        jadx_name = "jadx.bat" if os.name == "nt" else "jadx"
        bundled = CORE_DIR / "jadx" / "bin" / jadx_name
        if bundled.exists():
            return bundled
        return Path(jadx_name)

    def decompile_package(
        self,
        target: str,
        input_dir: Path | str | None = None,
        output_dir: Path | str | None = None,
        threads: int | None = None,
        heap_memory: str = "8g",
        extra_flags: list[str] | None = None,
    ) -> bool:
        """Decompiles a package APK or split APKs using JADX."""
        pkg = self.config_mgr.resolve_package_name(target)
        if not pkg:
            log_error(f"Could not resolve package name from '{target}'")
            return False

        paths = self.config_mgr.get_app_paths(pkg)
        in_path = Path(input_dir) if input_dir else paths["apks"]
        out_path = Path(output_dir) if output_dir else paths["jadx"]

        if not in_path.exists():
            log_warn(f"APK directory not found for {pkg}: {in_path}")
            return False

        out_path.mkdir(parents=True, exist_ok=True)

        # JVM Heap Memory Safeguard
        env = os.environ.copy()
        if "JADX_OPTS" not in env:
            env["JADX_OPTS"] = f"-Xmx{heap_memory} -Xms{heap_memory}"

        cpu_count = str(threads or os.cpu_count() or 8)

        # Look for APK archives
        archive_items = list(in_path.iterdir())
        apks_found = False

        for item in archive_items:
            if item.is_file() and item.suffix == ".apk":
                apks_found = True
                log_info(f"Decoding standard APK {item.name} for {pkg} -> {out_path}...")
                cmd = [
                    str(self.jadx_path),
                    "-d", str(out_path),
                    "-j", cpu_count,
                    "--export-gradle",
                    "--deobf",
                    "--add-debug-lines",
                    "--comments-level", "debug",
                    "--respect-bytecode-access-modifiers",
                    "--no-inline-anonymous",
                    "--no-inline-methods",
                    "--no-replace-consts",
                    str(item),
                ]
                if extra_flags:
                    cmd.extend(extra_flags)

                log_info(f"Running JADX on {item.name}...")
                res = subprocess.run(cmd, env=env)
                if res.returncode == 0:
                    log_success(f"Decompilation complete for {item.name}")
                else:
                    log_error(f"JADX exited with code {res.returncode}")

            elif item.is_file() and item.suffix in (".xapk", ".apks"):
                apks_found = True
                extract_dir = in_path / f"{item.name}_extracted"
                if not extract_dir.exists():
                    log_info(f"Extracting split archive {item.name}...")
                    try:
                        with zipfile.ZipFile(item, "r") as zip_ref:
                            zip_ref.extractall(extract_dir)
                    except zipfile.BadZipFile:
                        log_error(f"Corrupted or invalid zip archive: {item.name}")
                        continue

                extracted_apks = [str(f) for f in extract_dir.rglob("*.apk")]
                if not extracted_apks:
                    log_warn(f"No .apk files found inside {item.name}")
                    continue

                log_info(f"Decoding {item.name} ({len(extracted_apks)} split APKs) for {pkg} -> {out_path}...")
                cmd = [
                    str(self.jadx_path),
                    "-d", str(out_path),
                    "-j", cpu_count,
                    "--export-gradle",
                    "--deobf",
                    "--add-debug-lines",
                    "--comments-level", "debug",
                    "--respect-bytecode-access-modifiers",
                    "--no-inline-anonymous",
                    "--no-inline-methods",
                    "--no-replace-consts",
                ] + extracted_apks
                if extra_flags:
                    cmd.extend(extra_flags)

                log_info(f"Running JADX on split APKs...")
                res = subprocess.run(cmd, env=env)
                if res.returncode == 0:
                    log_success(f"Decompilation complete for {item.name}")
                else:
                    log_error(f"JADX exited with code {res.returncode}")

        if not apks_found:
            log_warn(f"No .apk, .xapk, or .apks files found in {in_path}")
            return False

        return True

    def decompile_targets(
        self,
        targets_file: Path | str | None = None,
        link: str | None = None,
        threads: int | None = None,
        heap_memory: str = "8g",
    ) -> int:
        """Decompiles all targets from a file, link, or workspace config."""
        if link:
            success = self.decompile_package(link, threads=threads, heap_memory=heap_memory)
            return 1 if success else 0

        targets = self.config_mgr.targets
        if targets_file:
            lines = self.config_mgr.read_targets_file(targets_file)
        else:
            lines = [t.get("packageName") for t in targets if t.get("packageName")]

        if not lines:
            log_warn("No targets found to decompile.")
            log_info("Tip: Run 'are decode <package_or_url>' or 'are target add <package_or_url>'.")
            return 0

        success_count = 0
        for line in lines:
            if self.decompile_package(line, threads=threads, heap_memory=heap_memory):
                success_count += 1

        log_info(f"Completed decompilations: {success_count}/{len(lines)} successful.")
        return success_count

    def launch_gui(self, target: str | None = None):
        """Launches JADX GUI, optionally loading target APK."""
        gui_name = "jadx-gui.bat" if os.name == "nt" else "jadx-gui"
        gui_path = CORE_DIR / "jadx" / "bin" / gui_name
        if not gui_path.exists():
            gui_path = Path(gui_name)

        cmd = [str(gui_path)]
        if target:
            pkg = self.config_mgr.resolve_package_name(target)
            if pkg:
                paths = self.config_mgr.get_app_paths(pkg)
                apks = list(paths["apks"].glob("*.apk")) if paths["apks"].exists() else []
                if apks:
                    cmd.append(str(apks[0]))

        log_info(f"Launching JADX GUI: {' '.join(cmd)}")
        subprocess.Popen(cmd)

    def run_apktool(self, args: list[str]) -> int:
        """Runs bundled apktool with specified arguments."""
        apktool_jar = CORE_DIR / "apktool" / "apktool.jar"
        if not apktool_jar.exists():
            log_error("apktool.jar not found in core/apktool/")
            return 1
        cmd = ["java", "-jar", str(apktool_jar.resolve())] + args
        log_info(f"Running: {' '.join(cmd)}")
        res = subprocess.run(cmd)
        return res.returncode
