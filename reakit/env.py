import os
import sys
import shutil
import subprocess
from pathlib import Path
from reakit.utils import Colors, log_info, log_success, log_warn, log_error

BASE_DIR = Path(__file__).resolve().parent.parent
CORE_DIR = BASE_DIR / "core"

def find_scrcpy_dir() -> Path | None:
    """Finds bundled scrcpy directory under core/scrcpy_cli/vendor/scrcpy or core/."""
    # 1. Primary: core/scrcpy_cli/vendor/scrcpy
    vendor_scrcpy = CORE_DIR / "scrcpy_cli" / "vendor" / "scrcpy"
    if vendor_scrcpy.exists():
        return vendor_scrcpy
    
    vendor_dir = CORE_DIR / "scrcpy_cli" / "vendor"
    if vendor_dir.exists() and (vendor_dir / ("scrcpy.exe" if os.name == "nt" else "scrcpy")).exists():
        return vendor_dir

    # 2. Sibling legacy fallback if present
    if CORE_DIR.exists():
        for item in CORE_DIR.iterdir():
            if item.is_dir() and item.name.startswith("scrcpy-win64-"):
                return item
    return None

def get_bundled_paths() -> dict[str, Path]:
    """Returns a mapping of tool names to their bundled directory paths."""
    scrcpy_dir = find_scrcpy_dir() or (CORE_DIR / "scrcpy_cli" / "vendor" / "scrcpy")
    jadx_bin_dir = CORE_DIR / "jadx" / "bin"
    apkd_dir = CORE_DIR / "apkdgo"
    apktool_dir = CORE_DIR / "apktool"
    scrcpy_cli_dist = CORE_DIR / "scrcpy_cli" / "dist"

    return {
        "root": BASE_DIR,
        "scrcpy": scrcpy_dir,
        "jadx": jadx_bin_dir,
        "apkd": apkd_dir,
        "apktool": apktool_dir,
        "scrcpy_cli_dist": scrcpy_cli_dist,
    }

def get_path_directories() -> list[Path]:
    """Returns list of directories that should be in PATH."""
    bundled = get_bundled_paths()
    dirs = [
        bundled["root"],
        bundled["scrcpy"],
        bundled["jadx"],
        bundled["apkd"],
        bundled["apktool"],
    ]
    return [d for d in dirs if d.exists()]

def inject_runtime_path():
    """Injects bundled tool directories into the current Python runtime environment PATH."""
    current_path = os.environ.get("PATH", "")
    dirs = get_path_directories()
    new_dirs = []
    
    path_entries = [os.path.abspath(p) for p in current_path.split(os.pathsep) if p]
    
    for d in dirs:
        abs_d = str(d.resolve())
        if abs_d not in path_entries:
            new_dirs.append(abs_d)

    if new_dirs:
        os.environ["PATH"] = os.pathsep.join(new_dirs + path_entries)

    # Set default scrcpy environment variables if not already defined or invalid
    scrcpy_dir = find_scrcpy_dir()
    if scrcpy_dir and scrcpy_dir.exists():
        server_file = scrcpy_dir / "scrcpy-server"
        existing_server = os.environ.get("SCRCPY_SERVER_PATH")
        if server_file.exists() and (not existing_server or not Path(existing_server).exists()):
            os.environ["SCRCPY_SERVER_PATH"] = str(server_file.resolve())
        if "SCRCPY_SERVER_VERSION" not in os.environ:
            os.environ["SCRCPY_SERVER_VERSION"] = "4.1"
        
        adb_file = scrcpy_dir / ("adb.exe" if os.name == "nt" else "adb")
        existing_adb = os.environ.get("ADB_PATH") or os.environ.get("ADB")
        if adb_file.exists() and (not existing_adb or not Path(existing_adb).exists()):
            os.environ["ADB_PATH"] = str(adb_file.resolve())
            os.environ["ADB"] = str(adb_file.resolve())

def check_environment() -> dict:
    """Performs diagnostic checks on all prerequisites and bundled tools."""
    inject_runtime_path()
    results = {}

    # 1. Python
    results["python"] = {
        "name": "Python",
        "version": sys.version.split()[0],
        "path": sys.executable,
        "status": "ok" if sys.version_info >= (3, 8) else "warning",
    }

    # 2. Java JDK
    java_ver = None
    java_path = shutil.which("java")
    if java_path:
        try:
            res = subprocess.run(["java", "-version"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            for line in res.stdout.splitlines():
                if "version" in line.lower():
                    java_ver = line.strip()
                    break
        except Exception:
            pass
    results["java"] = {
        "name": "Java (JDK)",
        "version": java_ver or "Unknown",
        "path": java_path or "Not found in PATH",
        "status": "ok" if java_path else "missing",
    }

    # 3. Node.js
    node_ver = None
    node_path = shutil.which("node")
    if node_path:
        try:
            res = subprocess.run(["node", "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            node_ver = res.stdout.strip()
        except Exception:
            pass
    results["node"] = {
        "name": "Node.js",
        "version": node_ver or "Unknown",
        "path": node_path or "Not found in PATH",
        "status": "ok" if node_path else "missing",
    }

    # 4. ADB
    adb_ver = None
    adb_path = shutil.which("adb")
    devices = []
    if adb_path:
        try:
            res = subprocess.run(["adb", "version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            for line in res.stdout.splitlines():
                if "Android Debug Bridge" in line or "Version" in line:
                    adb_ver = line.strip()
                    break
            dev_res = subprocess.run(["adb", "devices", "-l"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            for line in dev_res.stdout.splitlines()[1:]:
                if line.strip():
                    devices.append(line.strip())
        except Exception:
            pass
    results["adb"] = {
        "name": "ADB (Android Debug Bridge)",
        "version": adb_ver or "Unknown",
        "path": adb_path or "Not found",
        "status": "ok" if adb_path else "missing",
        "devices": devices,
    }

    # 5. scrcpy
    scrcpy_ver = None
    scrcpy_path = shutil.which("scrcpy")
    if scrcpy_path:
        try:
            res = subprocess.run(["scrcpy", "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            for line in res.stdout.splitlines():
                if "scrcpy" in line:
                    scrcpy_ver = line.strip()
                    break
        except Exception:
            pass
    results["scrcpy"] = {
        "name": "scrcpy Screen Mirroring",
        "version": scrcpy_ver or "Unknown",
        "path": scrcpy_path or "Not found",
        "status": "ok" if scrcpy_path else "missing",
    }

    # 6. JADX
    jadx_ver = None
    jadx_exec = "jadx.bat" if os.name == "nt" else "jadx"
    jadx_path = shutil.which(jadx_exec) or shutil.which("jadx")
    if jadx_path:
        try:
            res = subprocess.run([jadx_path, "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            jadx_ver = res.stdout.strip()
        except Exception:
            pass
    results["jadx"] = {
        "name": "JADX Decompiler",
        "version": jadx_ver or "Unknown",
        "path": jadx_path or "Not found",
        "status": "ok" if jadx_path else "missing",
    }

    # 7. apkd (Go downloader)
    apkd_path = shutil.which("apkd.exe" if os.name == "nt" else "apkd")
    results["apkd"] = {
        "name": "apkd (APK Downloader)",
        "path": apkd_path or "Not found",
        "status": "ok" if apkd_path else "missing",
    }

    # 8. scrcpy_cli module
    scrcpy_cli_dist = CORE_DIR / "scrcpy_cli" / "dist" / "index.js"
    results["scrcpy_cli"] = {
        "name": "scrcpy-cli Module",
        "path": str(scrcpy_cli_dist.resolve()) if scrcpy_cli_dist.exists() else "Not built",
        "status": "ok" if scrcpy_cli_dist.exists() else "missing",
    }

    return results

def print_environment_report():
    """Prints a formatted report of all prerequisites and tools."""
    results = check_environment()
    print(f"\n{Colors.BOLD}REA_Kit System & Environment Diagnostics:{Colors.RESET}\n")
    print(f"{'Component':<28} | {'Status':<10} | {'Details'}")
    print("-" * 80)
    
    for key, info in results.items():
        name = info["name"]
        status = info["status"]
        if status == "ok":
            status_str = f"{Colors.GREEN}READY{Colors.RESET}"
        elif status == "warning":
            status_str = f"{Colors.YELLOW}WARN{Colors.RESET}"
        else:
            status_str = f"{Colors.RED}MISSING{Colors.RESET}"
        
        detail = info.get("version", "")
        if info.get("path") and info["path"] != "Not found":
            detail += f" ({info['path']})"
        print(f"{name:<28} | {status_str:<19} | {detail}")

    adb_devices = results.get("adb", {}).get("devices", [])
    print("\n" + "-" * 80)
    if adb_devices:
        log_success(f"Connected Android Devices ({len(adb_devices)}):")
        for dev in adb_devices:
            print(f"    * {dev}")
    else:
        log_warn("No connected Android devices detected. Connect a physical device or launch an emulator.")
    print("")

def install_scrcpy_cli() -> bool:
    """Builds and globally links scrcpy-cli via npm link so 'scrcpy-cli' command is globally available."""
    scrcpy_cli_dir = CORE_DIR / "scrcpy_cli"
    if not scrcpy_cli_dir.exists():
        return False

    npm_path = shutil.which("npm.cmd" if os.name == "nt" else "npm") or shutil.which("npm")
    if not npm_path:
        log_warn("npm was not found in PATH. Skipping global scrcpy-cli linking.")
        return False

    node_modules = scrcpy_cli_dir / "node_modules"
    if not node_modules.exists():
        log_info("[*] Installing scrcpy-cli dependencies (npm install)...")
        try:
            subprocess.run([npm_path, "install"], cwd=str(scrcpy_cli_dir), check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except Exception as e:
            log_warn(f"Failed to install scrcpy-cli dependencies: {e}")

    dist_file = scrcpy_cli_dir / "dist" / "index.js"
    if not dist_file.exists():
        log_info("[*] Building scrcpy-cli...")
        try:
            subprocess.run([npm_path, "run", "build"], cwd=str(scrcpy_cli_dir), check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except Exception as e:
            log_warn(f"Failed to build scrcpy-cli: {e}")

    log_info("[*] Registering scrcpy-cli globally via npm link...")
    try:
        res = subprocess.run([npm_path, "link", "--force"], cwd=str(scrcpy_cli_dir), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode == 0:
            log_success("Global 'scrcpy-cli' command registered successfully.")
            return True
        else:
            log_warn(f"npm link exited with code {res.returncode}: {res.stderr.strip()}")
            return False
    except Exception as e:
        log_warn(f"Failed to link scrcpy-cli globally: {e}")
        return False

def install_pip_package() -> bool:
    """Installs REA_Kit Python package in editable mode via pip."""
    pip_path = shutil.which("pip") or sys.executable
    pyproject_file = BASE_DIR / "pyproject.toml"
    if not pyproject_file.exists():
        return False

    log_info("[*] Installing REA_Kit Python package in editable mode via pip...")
    try:
        if pip_path == sys.executable:
            cmd = [sys.executable, "-m", "pip", "install", "-e", str(BASE_DIR), "--no-deps", "--quiet"]
        else:
            cmd = [pip_path, "install", "-e", str(BASE_DIR), "--no-deps", "--quiet"]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode == 0:
            log_success("REA_Kit CLI ('rea' and 'reakit') registered in Python environment.")
            return True
        else:
            log_warn(f"pip install exited with code {res.returncode}: {res.stderr.strip()}")
            return False
    except Exception as e:
        log_warn(f"Failed to install REA_Kit via pip: {e}")
        return False

def install_environment(permanent: bool = True, install_pip: bool = True, link_npm: bool = True) -> list[str]:
    """Complete REA_Kit installation: registers PATH, configures environment variables, links scrcpy-cli, and installs Python package."""
    dirs_to_add = get_path_directories()
    added_paths = []

    # 1. Build and link scrcpy-cli globally
    if link_npm:
        install_scrcpy_cli()

    # 2. Install REA_Kit Python package
    if install_pip:
        install_pip_package()

    # 3. Configure Windows User PATH and Environment Variables in Registry
    if permanent and os.name == "nt":
        try:
            # Query current User PATH from registry
            cmd_get = ['powershell', '-NoProfile', '-Command',
                       '[Environment]::GetEnvironmentVariable("Path", "User")']
            res = subprocess.run(cmd_get, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            current_user_path = res.stdout.strip()
            existing = [p.strip() for p in current_user_path.split(";") if p.strip()]
            
            # Filter out stale legacy scrcpy paths
            core_str = str(CORE_DIR.resolve()).lower()
            cleaned_existing = [
                p for p in existing
                if not (p.lower().startswith(core_str) and "scrcpy-win64" in p.lower())
            ]
            existing_lower = [p.lower() for p in cleaned_existing]
            
            new_list = list(cleaned_existing)
            for d in dirs_to_add:
                abs_str = str(d.resolve())
                if abs_str.lower() not in existing_lower:
                    new_list.append(abs_str)
                    added_paths.append(abs_str)
            
            if added_paths or len(cleaned_existing) != len(existing):
                new_user_path = ";".join(new_list)
                escaped_path = new_user_path.replace("'", "''")
                cmd_set = ['powershell', '-NoProfile', '-Command',
                           f'[Environment]::SetEnvironmentVariable("Path", \'{escaped_path}\', "User")']
                subprocess.run(cmd_set, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)

                scrcpy_dir = find_scrcpy_dir()
                if scrcpy_dir and scrcpy_dir.exists():
                    server_file = scrcpy_dir / "scrcpy-server"
                    if server_file.exists():
                        escaped_srv = str(server_file.resolve()).replace("'", "''")
                        subprocess.run(['powershell', '-NoProfile', '-Command',
                                       f'[Environment]::SetEnvironmentVariable("SCRCPY_SERVER_PATH", \'{escaped_srv}\', "User")'],
                                       check=False)
                        subprocess.run(['powershell', '-NoProfile', '-Command',
                                       '[Environment]::SetEnvironmentVariable("SCRCPY_SERVER_VERSION", "4.1", "User")'],
                                       check=False)
                    adb_file = scrcpy_dir / ("adb.exe" if os.name == "nt" else "adb")
                    if adb_file.exists():
                        escaped_adb = str(adb_file.resolve()).replace("'", "''")
                        subprocess.run(['powershell', '-NoProfile', '-Command',
                                       f'[Environment]::SetEnvironmentVariable("ADB_PATH", \'{escaped_adb}\', "User")'],
                                       check=False)
        except Exception as e:
            log_error(f"Failed to update Windows User PATH: {e}")
            return []

    # 4. Also update current session PATH
    inject_runtime_path()
    return [str(d.resolve()) for d in dirs_to_add]

def setup_windows_user_path(permanent: bool = True) -> list[str]:
    """Backwards-compatible alias for install_environment."""
    return install_environment(permanent=permanent)
