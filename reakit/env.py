import os
import sys
import shutil
import subprocess
from pathlib import Path
from reakit.utils import Colors, log_info, log_success, log_warn, log_error, log_dim

BASE_DIR = Path(__file__).resolve().parent.parent
CORE_DIR = BASE_DIR / "core"
# mobilerun-mcp (device control backend for 'rea device') is a git submodule with
# its own venv: it needs Python >=3.11,<3.14 and heavy deps (fastmcp, onnxruntime),
# so ReaKit itself stays stdlib-only and only ever spawns that interpreter.
MOBILERUN_DIR = CORE_DIR / "mobilerun_mcp"
MOBILERUN_VENV = MOBILERUN_DIR / ".venv"
MOBILERUN_PYTHON_VERSION = "3.13"


def venv_python(venv: Path) -> Path:
    """Path of the interpreter inside a venv (Scripts/python.exe on Windows, bin/python on POSIX)."""
    if os.name == "nt":
        return venv / "Scripts" / "python.exe"
    return venv / "bin" / "python"


def find_mobilerun_python() -> Path | None:
    """The mobilerun-mcp venv interpreter, or None when 'rea install' has not created it."""
    py = venv_python(MOBILERUN_VENV)
    return py if py.is_file() else None

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

def find_apkd_bin() -> Path | None:
    """Finds the apkd binary across bundled paths and PATH."""
    apkd_name = "apkd.exe" if os.name == "nt" else "apkd"
    candidates = [
        CORE_DIR / "apkdgo" / "bin" / apkd_name,
        CORE_DIR / "apkdgo" / "apkd" / apkd_name,
        CORE_DIR / "apkdgo" / apkd_name,
    ]
    for cand in candidates:
        if cand.is_file():
            return cand
    which_p = shutil.which(apkd_name)
    if which_p and Path(which_p).is_file():
        return Path(which_p)
    return None

def get_bundled_paths() -> dict[str, Path]:
    """Returns a mapping of tool names to their bundled directory paths."""
    scrcpy_dir = find_scrcpy_dir() or (CORE_DIR / "scrcpy_cli" / "vendor" / "scrcpy")
    jadx_bin_dir = CORE_DIR / "jadx" / "bin"
    apkd_dir = (CORE_DIR / "apkdgo" / "bin") if (CORE_DIR / "apkdgo" / "bin").exists() else (CORE_DIR / "apkdgo")
    apktool_dir = CORE_DIR / "apktool"

    return {
        "root": BASE_DIR,
        "scrcpy": scrcpy_dir,
        "jadx": jadx_bin_dir,
        "apkd": apkd_dir,
        "apktool": apktool_dir,
        "mobilerun": MOBILERUN_DIR,
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
    fix_unix_permissions()
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
        "name": "scrcpy (mirror + adb)",
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
    apkd_path = find_apkd_bin()
    results["apkd"] = {
        "name": "apkd (APK Downloader)",
        "path": str(apkd_path.resolve()) if apkd_path else "Not found",
        "status": "ok" if apkd_path else "missing",
    }

    # 8. mobilerun-mcp venv - backend for 'rea device' (device control + MCP server)
    results["mobilerun"] = check_mobilerun()

    # 9. Ghidra (backend for native .so analysis)
    # Imported lazily: reakit.native imports reakit.config, not reakit.env.
    from reakit.native import (
        find_ghidra_home,
        find_ghidra_mcp_jar,
        find_mcp_bridge,
        ghidra_version,
    )

    ghidra_home = find_ghidra_home()
    results["ghidra"] = {
        "name": "Ghidra (Native Analysis)",
        "version": ghidra_version(ghidra_home) or "Unknown",
        "path": str(ghidra_home) if ghidra_home else "Not found (set GHIDRA_HOME)",
        "status": "ok" if ghidra_home else "missing",
    }

    # 10. GhidraMCP plugin jar - powers 'rea native serve'
    jar = find_ghidra_mcp_jar(ghidra_home)
    results["ghidra_mcp_jar"] = {
        "name": "GhidraMCP Plugin Jar",
        "path": str(jar) if jar else "Not built (rea native build)",
        "status": "ok" if jar else "missing",
    }

    # 11. GhidraMCP MCP bridge - optional, for AI clients
    bridge = find_mcp_bridge()
    results["ghidra_mcp_bridge"] = {
        "name": "GhidraMCP MCP Bridge",
        "path": " ".join(bridge) if bridge else "Not installed (optional)",
        "status": "ok" if bridge else "warning",
    }

    # 12. HTTP Toolkit - backend for 'rea http' (API traffic capture)
    from reakit.httptoolkit import (
        HtkControlClient,
        find_htk_resources,
        find_htk_tool,
        htk_server_version,
    )

    htk_resources = find_htk_resources()
    results["http_toolkit"] = {
        "name": "HTTP Toolkit (API Traffic)",
        "version": htk_server_version() or "Unknown",
        "path": str(htk_resources) if htk_resources else "Not found (httptoolkit.com/download)",
        "status": "ok" if htk_resources else "missing",
    }

    # 13. HTTP Toolkit control API - only live while the desktop app is running
    if htk_resources:
        client = HtkControlClient(timeout=3)
        if client.is_ready():
            api_status, api_detail = "ok", "Live (rea http events)"
        elif client.is_running():
            api_status, api_detail = "warning", "Running, UI not connected yet"
        else:
            api_status, api_detail = "warning", "Not running (rea http start)"
        results["http_toolkit_api"] = {
            "name": "HTTP Toolkit Control API",
            "version": api_detail,
            "path": "Not found",
            "status": api_status,
        }

        htk_mcp = find_htk_tool("mcp")
        results["http_toolkit_mcp"] = {
            "name": "HTTP Toolkit MCP Bridge",
            "path": " ".join(htk_mcp) if htk_mcp else "Not found (optional)",
            "status": "ok" if htk_mcp else "warning",
        }

    # 14. Frida host Python module - optional backend for 'rea frida' (dynamic
    # instrumentation). OPTIONAL: never 'missing' in a way that fails install.
    # host_frida_version() is guarded (find_spec then import) - no top-level import.
    frida_mod_ver = None
    try:
        from reakit.fridakit import host_frida_version
        frida_mod_ver = host_frida_version()
    except Exception:
        frida_mod_ver = None
    results["frida"] = {
        "name": "Frida (Dynamic Instrumentation)",
        "version": frida_mod_ver or "Not installed (optional)",
        "path": "pip install 'frida==17.*'" if not frida_mod_ver else "host module",
        "status": "ok" if frida_mod_ver else "warning",
    }

    # 15. Frida CLI tools on PATH (frida-ps / frida) - optional convenience.
    frida_cli_path = shutil.which("frida-ps") or shutil.which("frida")
    results["frida_cli"] = {
        "name": "Frida CLI (frida-ps)",
        "version": "Available" if frida_cli_path else "Not found (optional)",
        "path": frida_cli_path or "pip install 'frida-tools'",
        "status": "ok" if frida_cli_path else "warning",
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

def check_mobilerun() -> dict:
    """Doctor entry for the mobilerun-mcp venv: it exists and 'import mobilerun_mcp' works."""
    info = {"name": "mobilerun-mcp (rea device)"}
    if not (MOBILERUN_DIR / "pyproject.toml").is_file():
        info.update(path="Submodule missing (git submodule update --init core/mobilerun_mcp)", status="missing")
        return info
    py = find_mobilerun_python()
    if not py:
        info.update(path="No venv (run: rea install)", status="missing")
        return info
    try:
        res = subprocess.run(
            [str(py), "-c", "import mobilerun_mcp, sys; print(sys.version.split()[0])"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=120,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        info.update(path=f"{py} ({exc})", status="missing")
        return info
    if res.returncode != 0:
        info.update(path=f"{py} (import mobilerun_mcp failed - run: rea install)", status="missing")
        return info
    info.update(version=f"Python {res.stdout.strip()}", path=str(py), status="ok")
    return info


def install_mobilerun() -> bool:
    """Creates core/mobilerun_mcp/.venv with uv and installs mobilerun-mcp into it (editable)."""
    if not (MOBILERUN_DIR / "pyproject.toml").is_file():
        log_warn("core/mobilerun_mcp is missing. Run: git submodule update --init core/mobilerun_mcp")
        return False
    uv = shutil.which("uv")
    if not uv:
        log_error("uv was not found in PATH; it is required to install mobilerun-mcp ('rea device').")
        log_info("Install uv (https://docs.astral.sh/uv/getting-started/installation/), then re-run 'rea install'.")
        return False

    py = venv_python(MOBILERUN_VENV)
    if not py.is_file():
        log_info(f"[*] Creating mobilerun-mcp venv (Python {MOBILERUN_PYTHON_VERSION}) at {MOBILERUN_VENV}...")
        res = subprocess.run(
            [uv, "venv", "--python", MOBILERUN_PYTHON_VERSION, str(MOBILERUN_VENV)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        if res.returncode != 0 or not py.is_file():
            log_error(f"uv venv failed ({res.returncode}): {res.stderr.strip()}")
            return False

    log_info("[*] Installing mobilerun-mcp into its venv (uv pip install -e core/mobilerun_mcp)...")
    res = subprocess.run(
        [uv, "pip", "install", "--python", str(py), "-e", str(MOBILERUN_DIR)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    if res.returncode != 0:
        log_error(f"uv pip install failed ({res.returncode}): {res.stderr.strip()[-2000:]}")
        return False
    log_success("mobilerun-mcp installed ('rea device' and 'rea device mcp' ready).")
    return True


def install_scrcpy_binaries() -> bool:
    """Downloads the scrcpy + adb platform binaries into core/scrcpy_cli/vendor/scrcpy.

    Only the binaries are used now ('rea mirror' and the shared ADB_PATH); the Node
    scrcpy-cli itself is no longer built or linked. download-scrcpy.mjs only uses
    Node built-ins, so no 'npm install' is needed - just node.
    """
    scrcpy_cli_dir = CORE_DIR / "scrcpy_cli"
    if not scrcpy_cli_dir.exists():
        return False

    vendor_scrcpy = scrcpy_cli_dir / "vendor" / "scrcpy"
    target_bin = vendor_scrcpy / ("scrcpy.exe" if os.name == "nt" else "scrcpy")
    target_adb = vendor_scrcpy / ("adb.exe" if os.name == "nt" else "adb")
    target_server = vendor_scrcpy / "scrcpy-server"
    if target_bin.exists() and target_adb.exists() and target_server.exists():
        return True

    download_script = scrcpy_cli_dir / "scripts" / "download-scrcpy.mjs"
    node_path = shutil.which("node")
    if not download_script.exists():
        log_warn(f"scrcpy download script not found: {download_script}")
        return False
    if not node_path:
        log_warn("Node.js was not found in PATH. Skipping the scrcpy/adb binary download.")
        return False

    log_info("[*] Bundling scrcpy & adb platform binaries for current OS...")
    try:
        subprocess.run([node_path, str(download_script)], cwd=str(scrcpy_cli_dir), check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except Exception as e:
        log_warn(f"Failed to bundle scrcpy platform binaries: {e}")
        return False
    return target_bin.exists() and target_adb.exists()

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

def fix_unix_permissions():
    """Ensures bundled binaries and scripts have executable (+x) permissions on POSIX systems."""
    if os.name == "nt":
        return
    
    bin_paths = [
        CORE_DIR / "jadx" / "bin" / "jadx",
        CORE_DIR / "jadx" / "bin" / "jadx-gui",
        CORE_DIR / "scrcpy_cli" / "vendor" / "scrcpy" / "adb",
        CORE_DIR / "scrcpy_cli" / "vendor" / "scrcpy" / "scrcpy",
        CORE_DIR / "apkdgo" / "bin" / "apkd",
        CORE_DIR / "apkdgo" / "apkd" / "apkd",
        CORE_DIR / "apkdgo" / "build.sh",
    ]
    for p in bin_paths:
        if p.exists():
            try:
                mode = p.stat().st_mode
                p.chmod(mode | 0o755)
            except OSError:
                pass

def build_apkd_linux() -> bool:
    """Builds apkd binary for Linux/Unix if Go is available and binary is missing."""
    if os.name == "nt":
        return True
    
    apkd_bin = find_apkd_bin()
    if apkd_bin and apkd_bin.is_file():
        return True
    
    go_path = shutil.which("go")
    if not go_path:
        return False
    
    apkd_dir = CORE_DIR / "apkdgo"
    bin_dir = apkd_dir / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    target_bin = bin_dir / "apkd"
    
    log_info("[*] Building apkd for Linux via Go...")
    try:
        res = subprocess.run(
            [go_path, "build", "-o", "bin/apkd", "./apkd"],
            cwd=str(apkd_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if res.returncode == 0 and target_bin.exists():
            target_bin.chmod(target_bin.stat().st_mode | 0o755)
            log_success("apkd Linux binary built successfully.")
            return True
        else:
            log_warn(f"Failed to build apkd: {res.stderr.strip()}")
            return False
    except Exception as e:
        log_warn(f"Error compiling apkd: {e}")
        return False

def link_user_binaries():
    """On POSIX systems, creates symlinks in ~/.local/bin or ~/bin for global CLI access."""
    if os.name == "nt":
        return
    
    bin_dir = Path.home() / ".local" / "bin"
    if not bin_dir.exists():
        bin_dir = Path.home() / "bin"
    
    bin_dir.mkdir(parents=True, exist_ok=True)

    links = {
        "rea": BASE_DIR / "rea.py",
        "reakit": BASE_DIR / "rea.py",
        "jadx": CORE_DIR / "jadx" / "bin" / "jadx",
        "jadx-gui": CORE_DIR / "jadx" / "bin" / "jadx-gui",
        "apkd": CORE_DIR / "apkdgo" / "bin" / "apkd",
        "adb": CORE_DIR / "scrcpy_cli" / "vendor" / "scrcpy" / "adb",
        "scrcpy": CORE_DIR / "scrcpy_cli" / "vendor" / "scrcpy" / "scrcpy",
    }
    for name, src in links.items():
        if src.exists():
            try:
                src.chmod(src.stat().st_mode | 0o755)
                target = bin_dir / name
                if target.is_symlink() or target.is_file():
                    target.unlink()
                target.symlink_to(src)
            except OSError:
                pass

def install_environment(
    permanent: bool = True,
    install_pip: bool = True,
    link_npm: bool = True,
    setup_ghidra: bool = True,
    skip_frida: bool = False,
    setup_mobilerun: bool = True,
) -> list[str]:
    """Complete REA_Kit installation: registers PATH, configures environment variables, bundles scrcpy/adb, installs mobilerun-mcp, builds apkd, and sets up Ghidra.

    ``link_npm`` (CLI: --skip-npm turns it off) now only gates the Node-driven
    scrcpy/adb binary download; the scrcpy-cli Node build/link is gone.
    """
    # 0. Ensure POSIX permissions and build apkd if Go compiler exists
    fix_unix_permissions()
    build_apkd_linux()
    link_user_binaries()

    dirs_to_add = get_path_directories()
    added_paths = []

    # 1. Bundle scrcpy/adb binaries (rea mirror + the one shared adb)
    if link_npm:
        install_scrcpy_binaries()

    # 1b. mobilerun-mcp in its own venv (rea device / rea device mcp)
    if setup_mobilerun:
        install_mobilerun()

    # 2. Install REA_Kit Python package
    if install_pip:
        install_pip_package()

    # 3. Setup Ghidra & GhidraMCP native bundle if missing
    if setup_ghidra:
        try:
            from reakit.native import find_ghidra_home, fetch_ghidra, find_ghidra_mcp_jar, build_ghidra_mcp
            ghidra_home = find_ghidra_home()
            if not ghidra_home:
                log_info("[*] Bundling Ghidra release for native analysis...")
                ghidra_home = fetch_ghidra()
            if ghidra_home and not find_ghidra_mcp_jar(ghidra_home):
                log_info("[*] Building GhidraMCP plugin jar...")
                build_ghidra_mcp(ghidra_home)
        except Exception as e:
            log_warn(f"Failed to auto-setup Ghidra bundle: {e}")

    # 3b. Frida (OPTIONAL, dependency-free by default): do NOT pip-install frida
    # here - REA_Kit stays stdlib-only. Just surface the hint so 'rea frida' works
    # once the user opts in. Gated by --skip-frida (a clean no-op when set).
    if not skip_frida:
        from reakit.fridakit import host_frida_version
        if host_frida_version():
            log_dim("frida host module already installed (dynamic instrumentation ready).")
        else:
            log_info(
                "[*] Optional: install frida for dynamic instrumentation ('rea frida'):"
            )
            log_dim("    pip install 'frida==17.*' 'frida-tools'   # frida-tools provides the Java/ObjC bridge on 17")

    # 4. Configure Windows User PATH and Environment Variables in Registry
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
