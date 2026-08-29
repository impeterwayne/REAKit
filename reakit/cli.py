import re
import sys
import json
import argparse
from pathlib import Path
from reakit.utils import print_banner, log_info, log_success, log_warn, log_error, log_dim, Colors
from reakit.config import ConfigManager
from reakit.workspace import WorkspaceManager
from reakit.downloader import Downloader
from reakit.decompiler import Decompiler
from reakit.runtime import RuntimeExtractor
from reakit.scrcpy import ScrcpyBridge
from reakit.env import (
    check_environment,
    print_environment_report,
    install_environment,
    setup_windows_user_path,
    inject_runtime_path,
)
from reakit.native import (
    DEFAULT_MCP_URL,
    GhidraMcpClient,
    GhidraMcpServer,
    GhidraProject,
    NativeExtractor,
    build_ghidra_mcp,
    doctor,
    find_ghidra_home,
    ghidra_version,
    human_size,
    gui_extension_installed,
    install_gui_extension,
    install_mcp_bridge_package,
    print_endpoints,
    print_ghidra_setup_help,
    print_mcp_config,
    run_mcp_bridge,
    show_info,
)
import os

def _add_target_args(parser: argparse.ArgumentParser, positional_help: str = "Target package name or alias"):
    """Adds the target/workspace/config flags shared by every native subcommand."""
    parser.add_argument("target_pos", nargs="?", help=positional_help)
    parser.add_argument("--target", "-t", help="Target package name, alias, or Store URL")
    # SUPPRESS keeps an unused subcommand flag from clobbering a global 'rea -w ... native ...'
    parser.add_argument(
        "--workspace", "-w", default=argparse.SUPPRESS, help="Workspace root directory"
    )
    parser.add_argument(
        "--config", "-c", default=argparse.SUPPRESS, help="Path to workspace_config.json"
    )


# Query subcommands that map straight onto GhidraMCP endpoints.
# name -> (help text, takes a positional value)
NATIVE_QUERY_COMMANDS = {
    "program": ("Show the program currently loaded in the server", False),
    "functions": ("List functions (address, name)", False),
    "search-functions": ("Search functions by name pattern", True),
    "decompile": ("Decompile a function by name or 0x address", True),
    "disassemble": ("Disassemble a function at an address", True),
    "strings": ("List defined strings", False),
    "search-strings": ("Search strings by term", True),
    "imports": ("List imported symbols", False),
    "exports": ("List exported symbols", False),
    "segments": ("List memory segments", False),
    "globals": ("List global variables", False),
    "xrefs-to": ("List references to an address", True),
    "xrefs-from": ("List references from an address", True),
    "memory": ("Read raw bytes at an address", True),
}


def _add_server_args(parser: argparse.ArgumentParser):
    """Flags shared by every command that talks to a GhidraMCP server."""
    parser.add_argument("--url", help=f"GhidraMCP base URL (default {DEFAULT_MCP_URL})")
    parser.add_argument("--token", help="Bearer token (or set GHIDRA_MCP_AUTH_TOKEN)")
    parser.add_argument("--param", "-p", action="append", default=[], help="Extra parameter key=value (repeatable)")
    parser.add_argument("--grep", "-g", help="Keep only response lines matching this regex")
    parser.add_argument("--limit", type=int, help="Max results for endpoints that page")
    parser.add_argument("--raw", action="store_true", help="Print the raw response without JSON formatting")


def _add_native_parser(subparsers):
    """Registers 'rea native' - .so extraction plus the Ghidra/GhidraMCP CLI."""
    native_p = subparsers.add_parser(
        "native",
        aliases=["so", "nat"],
        help="Extract native .so libraries and analyze them through headless Ghidra (GhidraMCP)",
    )
    native_sub = native_p.add_subparsers(dest="native_action", help="Native analysis actions")

    # --- extraction (no Ghidra needed) ---
    ex_p = native_sub.add_parser("extract", aliases=["x"], help="Extract lib/<abi>/*.so from the target packages")
    _add_target_args(ex_p)
    ex_p.add_argument("--abi", action="append", help="Only extract this ABI (repeatable, e.g. --abi arm64-v8a)")
    ex_p.add_argument("--no-embedded", action="store_true", help="Skip .so files hidden outside lib/ (assets, res)")
    ex_p.add_argument("--force", action="store_true", help="Re-extract even if the file already exists")
    ex_p.add_argument("--input", "-i", help="APK directory override")
    ex_p.add_argument("--output", "-o", help="Output directory override")
    ex_p.add_argument("--limit", type=int, default=40, help="Rows to print in the summary table (0 = all)")

    ls_p = native_sub.add_parser("list", aliases=["ls"], help="List extracted native libraries and fingerprints")
    _add_target_args(ls_p)
    ls_p.add_argument("--json", action="store_true", help="Print the raw manifest JSON")
    ls_p.add_argument("--limit", type=int, default=40, help="Rows to print (0 = all)")
    ls_p.add_argument("--abi", help="Only list this ABI")
    ls_p.add_argument("--grep", "-g", help="Regex filter on library names")

    info_p = native_sub.add_parser("info", help="Show the ELF fingerprint of one library (offline)")
    _add_target_args(info_p, positional_help="Target package name, alias, or path to a .so file")
    info_p.add_argument("--lib", "-L", help="Library name or substring, e.g. libfoo.so")
    info_p.add_argument("--abi", help="ABI to pick, e.g. arm64-v8a")

    # --- setup ---
    build_p = native_sub.add_parser("build", help="Build the GhidraMCP plugin jar and install the MCP bridge")
    build_p.add_argument("--ghidra-home", help="Ghidra installation directory")
    build_p.add_argument("--no-deploy", action="store_true", help="Do not install the extension into Ghidra")
    build_p.add_argument("--skip-prereqs", action="store_true", help="Skip installing Ghidra jars into the Maven repo")
    build_p.add_argument("--bridge-only", action="store_true", help="Only pip-install the MCP bridge package")
    build_p.add_argument("--no-bridge", action="store_true", help="Only build the jar, skip the MCP bridge")

    setup_p = native_sub.add_parser("setup", aliases=["doctor"], help="Check Ghidra, plugin jar, bridge and server")
    setup_p.add_argument("--ghidra-home", help="Ghidra installation directory to validate")
    setup_p.add_argument("--port", type=int, default=8089, help="Server port to probe")

    # --- server lifecycle ---
    serve_p = native_sub.add_parser(
        "serve", aliases=["server"], help="Start the headless GhidraMCP server, optionally with a .so loaded"
    )
    _add_target_args(serve_p)
    serve_p.add_argument("--lib", "-L", help="Library name or substring to load")
    serve_p.add_argument("--abi", help="ABI to load (default: arm64-v8a when present)")
    serve_p.add_argument("--file", "-f", help="Load this binary path directly")
    serve_p.add_argument("--project", help="Ghidra project directory to open")
    serve_p.add_argument("--program", help="Program name inside the project")
    serve_p.add_argument("--port", type=int, default=8089, help="Listen port (default 8089)")
    serve_p.add_argument("--bind", default="127.0.0.1", help="Bind address (default 127.0.0.1)")
    serve_p.add_argument("--heap", default="4g", help="JVM max heap (default 4g)")
    serve_p.add_argument("--background", "-d", action="store_true", help="Run detached and wait until the API answers")
    serve_p.add_argument("--timeout", type=int, default=900, help="Seconds to wait for readiness in background mode")
    serve_p.add_argument("--ghidra-home", help="Ghidra installation directory")
    serve_p.add_argument("--jar", help="GhidraMCP jar path override")
    serve_p.add_argument("--java", help="java executable to use (JDK 21 recommended)")
    serve_p.add_argument("--from-project", action="store_true", help="Open the target's imported Ghidra project instead of a single .so")
    serve_p.add_argument("--no-load", action="store_true", help="Start with no program loaded")

    # import into a shared Ghidra project (GUI-browsable, cached for the server)
    imp_p = native_sub.add_parser("import", aliases=["proj"], help="Import .so files into a shared Ghidra project (GUI + cache)")
    _add_target_args(imp_p)
    imp_p.add_argument("--lib", "-L", help="Only import libraries whose name matches this substring")
    imp_p.add_argument("--abi", help="Import this ABI (default: one preferred ABI)")
    imp_p.add_argument("--all-abis", action="store_true", help="Import every ABI (per-ABI project folders)")
    imp_p.add_argument("--jni-only", action="store_true", help="Only import libraries that export Java_* JNI symbols")
    imp_p.add_argument("--no-analyze", action="store_true", help="Import without running auto-analysis")
    imp_p.add_argument("--overwrite", action="store_true", help="Overwrite programs already in the project")
    imp_p.add_argument("--max-size-mb", type=int, default=64, help="Skip libraries larger than this (0 = no limit)")
    imp_p.add_argument("--force", action="store_true", help="Import even oversized libraries")
    imp_p.add_argument("--cpu", type=int, help="Max CPU cores for analysis")
    imp_p.add_argument("--analysis-timeout", type=int, help="Auto-analysis timeout per file (seconds)")
    imp_p.add_argument("--heap", help="JVM max heap for analyzeHeadless (e.g. 8G)")
    imp_p.add_argument("--ghidra-home", help="Ghidra installation directory")

    # launch the Ghidra GUI on a target's project
    gui_p = native_sub.add_parser("gui", help="Open the Ghidra GUI on a target's imported project")
    _add_target_args(gui_p)
    gui_p.add_argument("--project-only", action="store_true", help="Fail if no project exists instead of opening the project manager")
    gui_p.add_argument("--install-plugin", action="store_true", help="Install the GhidraMCP GUI extension and exit (no window)")
    gui_p.add_argument("--force-install", action="store_true", help="Reinstall the GUI extension even if present")
    gui_p.add_argument("--ghidra-home", help="Ghidra installation directory")

    stop_p = native_sub.add_parser("stop", help="Stop the background GhidraMCP server")
    stop_p.add_argument("--port", type=int, default=8089, help="Port of the server to stop")

    load_p = native_sub.add_parser("load", help="Load a .so into an already running server")
    _add_target_args(load_p)
    load_p.add_argument("--lib", "-L", help="Library name or substring")
    load_p.add_argument("--abi", help="ABI filter")
    load_p.add_argument("--file", "-f", help="Load this binary path directly")
    load_p.add_argument("--language", help="Language id for raw blobs, e.g. ARM:LE:32:Cortex")
    load_p.add_argument("--compiler-spec", help="Compiler spec for raw blobs, e.g. default")
    load_p.add_argument("--url", help=f"GhidraMCP base URL (default {DEFAULT_MCP_URL})")
    load_p.add_argument("--token", help="Bearer token (or set GHIDRA_MCP_AUTH_TOKEN)")

    # switch the running server to another program in the open project
    sw_p = native_sub.add_parser("switch", help="Switch the running server to another program in the open project")
    sw_p.add_argument("program", help="In-project program path, e.g. /arm64-v8a/libfoo.so")
    sw_p.add_argument("--url", help=f"GhidraMCP base URL (default {DEFAULT_MCP_URL})")
    sw_p.add_argument("--token", help="Bearer token (or set GHIDRA_MCP_AUTH_TOKEN)")

    # --- generic API access ---
    call_p = native_sub.add_parser("call", help="Call any GhidraMCP endpoint (253 available)")
    call_p.add_argument("endpoint", help="Endpoint path (/list_functions) or alias (functions)")
    call_p.add_argument("value", nargs="?", help="Positional value for the endpoint main parameter")
    call_p.add_argument("--method", "-X", help="Override the HTTP method")
    _add_server_args(call_p)

    ep_p = native_sub.add_parser("endpoints", aliases=["api"], help="List the GhidraMCP endpoints available")
    ep_p.add_argument("--grep", "-g", help="Filter by path or description")
    ep_p.add_argument("--category", help="Filter by category, e.g. function, decompile, xref")
    ep_p.add_argument("--limit", type=int, default=0, help="Max rows (0 = all)")

    for name, (help_text, takes_value) in NATIVE_QUERY_COMMANDS.items():
        q_p = native_sub.add_parser(name, help=help_text)
        if takes_value:
            q_p.add_argument("value", nargs="?", help="Address, name, or search term")
        _add_server_args(q_p)

    jni_p = native_sub.add_parser("jni", help="List Java_* JNI entry points in the loaded program")
    _add_server_args(jni_p)

    # --- MCP bridge for AI clients ---
    mcp_p = native_sub.add_parser("mcp", help="Run the MCP bridge over the same server (for AI clients)")
    mcp_p.add_argument("--print-config", action="store_true", help="Print MCP client configuration and exit")
    mcp_p.add_argument("--url", help=f"GhidraMCP base URL the bridge should target (default {DEFAULT_MCP_URL})")
    mcp_p.add_argument("mcp_args", nargs=argparse.REMAINDER, help="Arguments passed to bridge-mcp-ghidra")

    return native_p


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rea",
        description="REA_Kit - Unified Reverse Engineering Android & Automation Framework",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("--workspace", "-w", help="Custom workspace root directory (defaults to ./workspaces in CWD)")
    parser.add_argument("--config", "-c", help="Path to workspace config JSON (defaults to local rea.config.json or workspace_config.json)")

    subparsers = parser.add_subparsers(dest="command", help="Available Commands")

    # 1. init
    init_p = subparsers.add_parser("init", help="Initialize workspace directory structure for targets")
    init_p.add_argument("target_pos", nargs="?", help="Target package name or Google Play URL (optional)")
    init_p.add_argument("--target", "-t", help="Single package name or link to initialize")
    init_p.add_argument("--input", "-i", help="Path to targets txt file")
    init_p.add_argument("--workspace", "-w", help="Workspace root directory")
    init_p.add_argument("--config", "-c", help="Path to workspace_config.json")

    # 2. download / dl
    dl_p = subparsers.add_parser("download", aliases=["dl"], help="Download APKs for targets using apkd")
    dl_p.add_argument("target_pos", nargs="?", help="Target package name or URL (optional)")
    dl_p.add_argument("--link", "-l", help="Direct URL or package name to download")
    dl_p.add_argument("--target", "-t", help="Target package name or alias")
    dl_p.add_argument("--source", "-s", help="Download source provider (apkcombo, fdroid, rustore, nashstore)")
    dl_p.add_argument("--targets", help="Path to targets.txt")
    dl_p.add_argument("--workspace", "-w", help="Workspace root directory")
    dl_p.add_argument("--config", "-c", help="Path to workspace_config.json")

    # 3. decode / decompile
    dec_p = subparsers.add_parser("decode", aliases=["decompile"], help="Decompile APK/XAPK packages using JADX")
    dec_p.add_argument("target_pos", nargs="?", help="Target package name or APK path (optional)")
    dec_p.add_argument("--link", "-l", help="Direct URL or package name to decode")
    dec_p.add_argument("--target", "-t", help="Target package name or alias")
    dec_p.add_argument("--targets", help="Path to targets.txt")
    dec_p.add_argument("--threads", "-j", type=int, help="Number of worker threads for JADX")
    dec_p.add_argument("--heap", default="8g", help="JVM Heap memory allocation (e.g. 8g, 4g)")
    dec_p.add_argument("--workspace", "-w", help="Workspace root directory")
    dec_p.add_argument("--config", "-c", help="Path to workspace_config.json")

    # 4. pull / runtime
    pull_p = subparsers.add_parser("pull", aliases=["runtime"], help="Extract sandbox runtime data via ADB (using package name)")
    pull_p.add_argument("package_name", nargs="?", help="Target Android package name (e.g. com.example.app)")
    pull_p.add_argument("--package", "-p", "--target", "-t", dest="target", help="Target Android package name")
    pull_p.add_argument("--workspace", "-w", help="Workspace root directory")
    pull_p.add_argument("--config", "-c", help="Path to workspace_config.json")

    # 5. pipeline / all / run
    pipe_p = subparsers.add_parser("pipeline", aliases=["all", "run"], help="Run automated static pipeline: init -> download -> decode")
    pipe_p.add_argument("target_pos", nargs="?", help="Target package name or Store URL")
    pipe_p.add_argument("--target", "-t", help="Target package name or Store URL")
    pipe_p.add_argument("--source", "-s", help="Download source provider")
    pipe_p.add_argument("--threads", "-j", type=int, help="Number of worker threads for JADX")
    pipe_p.add_argument("--heap", default="16g", help="JVM Heap memory allocation for JADX (e.g. 16g, 8g)")
    pipe_p.add_argument("--skip-decode", action="store_true", help="Skip decompilation step")
    pipe_p.add_argument("--skip-native", action="store_true", help="Skip native .so extraction step")
    pipe_p.add_argument("--workspace", "-w", help="Workspace root directory")
    pipe_p.add_argument("--config", "-c", help="Path to workspace_config.json")

    # 5b. native / so - ELF extraction and Ghidra analysis
    _add_native_parser(subparsers)

    # 6. scrcpy / control
    scrcpy_p = subparsers.add_parser("scrcpy", aliases=["control"], help="Android device automation via scrcpy-cli")
    scrcpy_p.add_argument("scrcpy_args", nargs=argparse.REMAINDER, help="Arguments passed directly to scrcpy-cli")

    # 7. mirror / screen
    mirror_p = subparsers.add_parser("mirror", aliases=["screen"], help="Launch interactive scrcpy screen mirroring window")
    mirror_p.add_argument("-s", "--serial", help="Target Android device serial")
    mirror_p.add_argument("-m", "--max-size", type=int, help="Limit video width and height")
    mirror_p.add_argument("--fps", type=int, help="Limit frame rate (e.g. 60)")
    mirror_p.add_argument("extra_args", nargs=argparse.REMAINDER, help="Additional arguments for scrcpy.exe")

    # 8. jadx-gui
    gui_p = subparsers.add_parser("jadx-gui", help="Launch interactive JADX GUI")
    gui_p.add_argument("target_pos", nargs="?", help="Target package name to load APK from (optional)")
    gui_p.add_argument("--target", "-t", help="Target package name to load APK from")
    gui_p.add_argument("--workspace", "-w", help="Workspace root directory")
    gui_p.add_argument("--config", "-c", help="Path to workspace_config.json")

    # 9. apktool
    apktool_p = subparsers.add_parser("apktool", help="Run bundled APKTool")
    apktool_p.add_argument("apktool_args", nargs=argparse.REMAINDER, help="Arguments passed to apktool")

    # 10. target (list / add / remove)
    target_p = subparsers.add_parser("target", help="Manage targets and configuration")
    target_p.add_argument("--workspace", "-w", help="Workspace root directory")
    target_p.add_argument("--config", "-c", help="Path to workspace_config.json")
    target_sub = target_p.add_subparsers(dest="target_action", help="Target actions")
    target_sub.add_parser("list", help="List all configured applications and workspaces")
    t_add = target_sub.add_parser("add", help="Add a target package or URL")
    t_add.add_argument("package_or_url", help="Package name or Play Store URL")
    t_add.add_argument("--alias", "-a", help="Friendly alias name")
    t_add.add_argument("--source", "-s", help="Download source provider (e.g. apkcombo, fdroid)")
    t_rm = target_sub.add_parser("remove", help="Remove a target package")
    t_rm.add_argument("package_or_alias", help="Package name or alias to remove")

    # 11. env / check
    subparsers.add_parser("env", aliases=["check"], help="Check environment prerequisites, tools, and connected devices")

    # 12. install / setup / setup-path
    sp_p = subparsers.add_parser(
        "install",
        aliases=["setup", "setup-path"],
        help="Install & configure REA_Kit environment, tools, and Windows PATH",
    )
    sp_p.add_argument("--permanent", action="store_true", default=True, help="Permanently configure Windows User PATH and Environment (default)")
    sp_p.add_argument("--session", action="store_true", help="Configure PATH for current session only")
    sp_p.add_argument("--check", action="store_true", help="Check current environment & PATH status")
    sp_p.add_argument("--skip-pip", action="store_true", help="Skip editable Python package installation (pip install -e .)")
    sp_p.add_argument("--skip-npm", action="store_true", help="Skip scrcpy-cli global linking (npm link)")

    return parser

def _resolve_native_target(args, config_mgr) -> str | None:
    """Resolves the target for a native subcommand, defaulting to the only workspace."""
    target = getattr(args, "target_pos", None) or getattr(args, "target", None)
    if target:
        return target

    workspaces = WorkspaceManager(config_mgr).list_workspaces()
    if len(workspaces) == 1:
        pkg = workspaces[0]["package"]
        log_info(f"No target given; using the only workspace: {pkg}")
        return pkg
    if config_mgr.targets:
        pkg = config_mgr.targets[0].get("packageName")
        if pkg:
            log_info(f"No target given; using first configured target: {pkg}")
            return pkg
    return None


def _parse_kv_params(pairs: list[str]) -> dict[str, str]:
    params = {}
    for pair in pairs or []:
        if "=" not in pair:
            log_warn(f"Ignoring malformed --param '{pair}' (expected key=value)")
            continue
        key, value = pair.split("=", 1)
        params[key.strip()] = value.strip()
    return params


def _native_client(args) -> GhidraMcpClient:
    return GhidraMcpClient(base_url=getattr(args, "url", None), token=getattr(args, "token", None))


def _resolve_native_so(args, config_mgr) -> Path | None:
    """Resolves --file, or a target plus --lib/--abi, to a .so path on disk."""
    if getattr(args, "file", None):
        path = Path(args.file)
        if not path.is_file():
            log_error(f"File not found: {path}")
            return None
        return path

    target = _resolve_native_target(args, config_mgr)
    if not target:
        log_error("Target package or --file is required.")
        return None

    extractor = NativeExtractor(config_mgr)
    so_path = extractor.resolve_library(target, name=getattr(args, "lib", None), abi=getattr(args, "abi", None))
    if not so_path:
        log_error("No matching native library found.")
        log_info(f"Run 'rea native extract {target}' first, or refine --lib / --abi.")
        return None
    return so_path


def _run_native(args, config_mgr) -> int:
    """Dispatches 'rea native <action>'."""
    action = getattr(args, "native_action", None)
    if not action:
        log_error("A native subcommand is required.")
        log_info(
            "Typical flow: rea native extract <pkg> -> rea native serve <pkg> --lib <name> -d "
            "-> rea native functions --grep Java_"
        )
        log_info("Check prerequisites with: rea native setup")
        return 2

    extractor = NativeExtractor(config_mgr)

    # ---------- extraction (offline) ----------
    if action in ("extract", "x"):
        target = _resolve_native_target(args, config_mgr)
        if not target:
            log_error("Target package is required. Example: rea native extract com.example.app")
            return 1
        manifest = extractor.extract_package(
            target,
            abis=args.abi,
            include_embedded=not args.no_embedded,
            force=args.force,
            input_dir=args.input,
            output_dir=args.output,
            report_limit=args.limit,
        )
        return 0 if manifest else 1

    if action in ("list", "ls"):
        target = _resolve_native_target(args, config_mgr)
        if not target:
            log_error("Target package is required. Example: rea native list com.example.app")
            return 1
        if args.json:
            manifest = extractor.load_manifest(target)
            if not manifest:
                log_error("No native manifest. Run 'rea native extract' first.")
                return 1
            print(json.dumps(manifest, indent=2))
            return 0
        libs = extractor.list_libraries(target)
        if not libs:
            log_warn("No extracted native libraries found.")
            log_info(f"Tip: run 'rea native extract {target}'")
            return 1
        if args.abi:
            libs = [l for l in libs if l["abi"].lower() == args.abi.lower()]
        if args.grep:
            pattern = re.compile(args.grep, re.IGNORECASE)
            libs = [l for l in libs if pattern.search(l["name"])]
        if not libs:
            log_warn("No libraries matched the --abi / --grep filters.")
            return 1
        extractor.print_manifest({"libraries": libs}, limit=args.limit)
        return 0

    if action == "info":
        raw = getattr(args, "target_pos", None) or getattr(args, "target", None)
        if raw and Path(raw).is_file():
            return show_info(Path(raw))
        target = _resolve_native_target(args, config_mgr)
        if not target:
            log_error("Provide a .so path or a target package name.")
            return 1
        so_path = extractor.resolve_library(target, name=args.lib, abi=args.abi)
        if not so_path:
            log_error("No matching native library. Run 'rea native extract' or refine --lib / --abi.")
            return 1
        return show_info(so_path)

    # ---------- setup ----------
    if action == "build":
        ok = True
        if not args.bridge_only:
            ghidra_home = Path(args.ghidra_home) if args.ghidra_home else find_ghidra_home(config_mgr)
            if not ghidra_home:
                log_error("Ghidra installation not found; cannot build the plugin.")
                print_ghidra_setup_help()
                return 1
            log_info(f"Building GhidraMCP against Ghidra {ghidra_version(ghidra_home) or '?'} at {ghidra_home}")
            jar = build_ghidra_mcp(
                ghidra_home,
                deploy=not args.no_deploy,
                skip_prereqs=args.skip_prereqs,
            )
            ok = jar is not None
        if not args.no_bridge:
            ok = install_mcp_bridge_package() and ok
        return 0 if ok else 1

    if action in ("setup", "doctor"):
        return doctor(config_mgr, ghidra_home=args.ghidra_home, port=args.port)

    # ---------- shared project + GUI ----------
    if action in ("import", "proj"):
        project = GhidraProject(config_mgr, ghidra_home=args.ghidra_home)
        target = _resolve_native_target(args, config_mgr)
        if not target:
            log_error("Target package is required. Example: rea native import com.example.app")
            return 1
        gpr = project.import_libraries(
            target,
            lib=args.lib,
            abi=args.abi,
            all_abis=args.all_abis,
            jni_only=args.jni_only,
            analyze=not args.no_analyze,
            overwrite=args.overwrite,
            max_size_mb=args.max_size_mb,
            force=args.force,
            cpu=args.cpu,
            analysis_timeout=args.analysis_timeout,
            heap=args.heap,
        )
        return 0 if gpr else 1

    if action == "gui":
        if args.install_plugin or args.force_install:
            home = Path(args.ghidra_home) if args.ghidra_home else find_ghidra_home(config_mgr)
            installed = install_gui_extension(home, force=args.force_install)
            return 0 if installed else 1
        project = GhidraProject(config_mgr, ghidra_home=args.ghidra_home)
        target = _resolve_native_target(args, config_mgr)
        return project.launch_gui(target, project_only=args.project_only)

    # ---------- server lifecycle ----------
    if action in ("serve", "server"):
        so_path = None
        project_path = args.project
        if args.from_project:
            target = _resolve_native_target(args, config_mgr)
            if not target:
                log_error("Target package is required with --from-project.")
                return 1
            gproj = GhidraProject(config_mgr, ghidra_home=args.ghidra_home)
            if not gproj.exists(target):
                log_error(f"No imported project for {target}. Run 'rea native import {target}' first.")
                return 1
            project_path = str(gproj.project_file(target))
            log_info(f"Serving imported project: {project_path}")
            # Auto-pick a program unless the user named one. Only libraries that
            # were actually imported into the project can be loaded, so prefer a
            # JNI-exporting library and warn that --lib pins the choice.
            if not args.program and not args.no_load:
                extractor = NativeExtractor(config_mgr)
                if args.lib:
                    so = extractor.resolve_library(target, name=args.lib, abi=args.abi)
                else:
                    libs = extractor.list_libraries(target)
                    if args.abi:
                        libs = [l for l in libs if l["abi"].lower() == args.abi.lower()]
                    jni = [l for l in libs if (l.get("elf") or {}).get("jni_exports")]
                    pool = jni or libs
                    pool.sort(key=lambda l: l.get("size", 0))  # smallest first: likely imported, fast
                    chosen = pool[0] if pool else None
                    so = None
                    if chosen:
                        so = Path(chosen.get("abs_path") or chosen["path"])
                        if not so.is_absolute():
                            so = config_mgr.get_app_paths(
                                config_mgr.resolve_package_name(target)
                            )["root"] / chosen["path"]
                if so:
                    args.program = f"/{so.parent.name}/{so.name}"
                    log_info(f"Loading program: {args.program} (override with --program or --lib)")
                    log_dim("Only libraries imported via 'rea native import' are loadable.")
        elif not args.no_load and not (args.project or args.program):
            so_path = _resolve_native_so(args, config_mgr)
            if so_path is None:
                log_info("Start with no program using --no-load, or import first: rea native import <pkg>")
                return 1
            size = so_path.stat().st_size
            if size > 64 * 1024 * 1024:
                log_warn(f"{so_path.name} is {human_size(size)}; auto-analysis may take a long time.")
        server = GhidraMcpServer(
            config_mgr,
            ghidra_home=args.ghidra_home,
            jar=args.jar,
            port=args.port,
            bind=args.bind,
            heap=args.heap,
            java=args.java,
        )
        return server.start(
            file=so_path,
            project=project_path,
            program=args.program,
            background=args.background,
            wait_timeout=args.timeout,
        )

    if action == "stop":
        return GhidraMcpServer(config_mgr, port=args.port).stop()

    if action == "load":
        so_path = _resolve_native_so(args, config_mgr)
        if not so_path:
            return 1
        params = {}
        if args.language:
            params["language"] = args.language
        if args.compiler_spec:
            params["compiler_spec"] = args.compiler_spec
        client = _native_client(args)
        log_info(f"Loading {so_path.name} into the server at {client.base_url}...")
        return client.call("load", str(so_path.resolve()), params=params)

    if action == "switch":
        client = _native_client(args)
        return client.load_from_project(args.program)

    # ---------- generic API access ----------
    if action == "call":
        client = _native_client(args)
        return client.call(
            args.endpoint,
            args.value,
            params=_parse_kv_params(args.param),
            method=args.method,
            grep=args.grep,
            limit=args.limit,
            raw=args.raw,
        )

    if action in ("endpoints", "api"):
        return print_endpoints(grep=args.grep, category=args.category, limit=args.limit)

    if action == "jni":
        client = _native_client(args)
        params = _parse_kv_params(args.param)
        params.setdefault("name_pattern", "Java_")
        return client.call(
            "search-functions",
            None,
            params=params,
            grep=args.grep,
            limit=args.limit,
            raw=args.raw,
        )

    if action in NATIVE_QUERY_COMMANDS:
        client = _native_client(args)
        return client.call(
            action,
            getattr(args, "value", None),
            params=_parse_kv_params(args.param),
            grep=args.grep,
            limit=args.limit,
            raw=args.raw,
        )

    # ---------- MCP bridge ----------
    if action == "mcp":
        if args.print_config:
            return print_mcp_config(url=args.url)
        extra = [a for a in getattr(args, "mcp_args", []) if a != "--"]
        if args.url:
            os.environ["GHIDRA_MCP_URL"] = args.url
        return run_mcp_bridge(extra)

    log_error(f"Unknown native subcommand: {action}")
    return 2


def main():
    inject_runtime_path()
    parser = create_parser()
    if len(sys.argv) == 1:
        print_banner()
        parser.print_help()
        sys.exit(0)

    args = parser.parse_args()
    cmd = args.command

    config_path = getattr(args, "config", None)
    workspace_root = getattr(args, "workspace", None)
    config_mgr = ConfigManager(config_path=config_path, workspace_root=workspace_root)

    if cmd == "init":
        mgr = WorkspaceManager(config_mgr)
        target = args.target_pos or args.target
        if target:
            app_root = mgr.init_target(target, source_link=target if target.startswith("http") else None)
            log_success(f"Initialized workspace for: {target} -> {app_root}")
        else:
            mgr.init_all(input_file=args.input)

    elif cmd in ("download", "dl"):
        dl = Downloader(config_mgr)
        target = args.target_pos or args.link or args.target
        if target:
            dl.download_package(target, source=args.source)
        else:
            dl.download_targets(targets_file=args.targets, source=args.source)

    elif cmd in ("decode", "decompile"):
        dec = Decompiler(config_mgr)
        target = args.target_pos or args.link or args.target
        if target:
            dec.decompile_package(target, threads=args.threads, heap_memory=args.heap)
        else:
            dec.decompile_targets(targets_file=args.targets, threads=args.threads, heap_memory=args.heap)

    elif cmd in ("pull", "runtime"):
        extractor = RuntimeExtractor(config_mgr)
        target = getattr(args, "package_name", None) or getattr(args, "target_pos", None) or getattr(args, "target", None)
        if not target:
            if config_mgr.targets:
                target = config_mgr.targets[0].get("packageName")
            else:
                targets = config_mgr.read_targets_file()
                if targets:
                    target = targets[0]
        
        if not target:
            log_error("No target package specified. Use 'rea pull <package_name>' or '--package <package_name>'")
            sys.exit(1)
        extractor.extract_package(target)

    elif cmd in ("pipeline", "all", "run"):
        target = args.target_pos or args.target
        if not target:
            log_error("Target package name or Google Play URL is required. Example: rea pipeline com.example.app")
            sys.exit(1)

        pkg = config_mgr.resolve_package_name(target) or target
        total_steps = 3 if args.skip_native else 4
        log_info(f"=== Starting Pipeline for {pkg} ===")
        log_info(f"Workspace Directory: {config_mgr.get_app_paths(pkg)['root']}")

        # 1. Init
        log_info(f"[Step 1/{total_steps}] Initializing workspace...")
        mgr = WorkspaceManager(config_mgr)
        mgr.init_target(pkg, source_link=target if target.startswith("http") else None)

        # 2. Download
        log_info(f"[Step 2/{total_steps}] Downloading target APK...")
        dl = Downloader(config_mgr)
        dl_ok = dl.download_package(target, source=args.source)

        paths = config_mgr.get_app_paths(pkg)
        has_existing_apks = False
        if paths["apks"].exists():
            existing_apks = [
                f for f in paths["apks"].iterdir()
                if f.is_file() and f.suffix in (".apk", ".xapk", ".apks")
            ]
            has_existing_apks = len(existing_apks) > 0

        if not dl_ok:
            if has_existing_apks:
                log_warn("Download failed or skipped, but existing APK package(s) found. Continuing with existing files...")
            else:
                log_error(f"Pipeline aborted: Download failed for {pkg} and no existing APK/XAPK files found in {paths['apks']}.")
                sys.exit(1)

        # 3. Decode
        if not args.skip_decode:
            log_info(f"[Step 3/{total_steps}] Decompiling APKs with JADX (Heap: {args.heap})...")
            dec = Decompiler(config_mgr)
            dec_ok = dec.decompile_package(pkg, threads=args.threads, heap_memory=args.heap)
            if not dec_ok:
                log_error(f"Pipeline failed: Decompilation failed for {pkg}.")
                sys.exit(1)
        else:
            log_info(f"[Step 3/{total_steps}] Decompilation skipped (--skip-decode).")

        # 4. Native libraries
        if not args.skip_native:
            log_info(f"[Step 4/{total_steps}] Extracting native .so libraries...")
            extractor = NativeExtractor(config_mgr)
            manifest = extractor.extract_package(pkg)
            if manifest is None:
                log_info("No native libraries in this target (pure Java/Kotlin app).")
            else:
                log_info(
                    f"Analyze them with: rea native serve {pkg} --lib <name> -d "
                    "then rea native functions --grep Java_"
                )

        log_success(f"=== Static pipeline completed successfully for {pkg}! ===")

    elif cmd in ("native", "so", "nat"):
        sys.exit(_run_native(args, config_mgr))

    elif cmd in ("scrcpy", "control"):
        bridge = ScrcpyBridge()
        scrcpy_args = getattr(args, "scrcpy_args", [])
        ret = bridge.run_cli(scrcpy_args)
        sys.exit(ret)

    elif cmd in ("mirror", "screen"):
        bridge = ScrcpyBridge()
        ret = bridge.launch_mirror(
            serial=args.serial,
            max_size=args.max_size,
            max_fps=args.fps,
            extra_args=getattr(args, "extra_args", None),
        )
        sys.exit(ret)

    elif cmd == "jadx-gui":
        dec = Decompiler(config_mgr)
        target = args.target_pos or args.target
        dec.launch_gui(target)

    elif cmd == "apktool":
        dec = Decompiler(config_mgr)
        apktool_args = getattr(args, "apktool_args", [])
        ret = dec.run_apktool(apktool_args)
        sys.exit(ret)

    elif cmd == "target":
        action = args.target_action
        if action == "list" or not action:
            print(f"\n{Colors.BOLD}REA_Kit Project Context:{Colors.RESET}")
            cfg_display = str(config_mgr.config_path) if config_mgr.config_path and config_mgr.config_path.exists() else "In-Memory Default (No local config file)"
            print(f"  * Active Config:  {Colors.CYAN}{cfg_display}{Colors.RESET}")
            print(f"  * Workspace Root: {Colors.CYAN}{config_mgr.workspace_root}{Colors.RESET}")

            targets = config_mgr.targets
            print(f"\n{Colors.BOLD}Configured Target Applications ({len(targets)}):{Colors.RESET}\n")
            if targets:
                for i, t in enumerate(targets, 1):
                    pkg = t.get("packageName")
                    alias = t.get("alias", "None")
                    src = f" [Source: {t.get('source')}]" if t.get("source") else ""
                    url = f" ({t.get('sourceLink')})" if t.get("sourceLink") else ""
                    print(f"  {i}. {Colors.CYAN}{pkg}{Colors.RESET} (Alias: {alias}){src}{url}")
            else:
                print("  (No configured target applications in active config)")

            mgr = WorkspaceManager(config_mgr)
            ws_list = mgr.list_workspaces()
            print(f"\n{Colors.BOLD}Workspace Directory Status ({len(ws_list)}):{Colors.RESET}\n")
            if ws_list:
                for ws in ws_list:
                    status_parts = []
                    status_parts.append(f"{ws['apks']} APK(s)")
                    status_parts.append("Decompiled" if ws["decompiled"] else "Not decompiled")
                    if ws.get("native_libs"):
                        status_parts.append(f"{ws['native_libs']} native lib(s)")
                    status_parts.append(f"{ws['runtime_files']} runtime files")
                    print(f"  * {Colors.GREEN}{ws['package']}{Colors.RESET}: {', '.join(status_parts)} ({ws['path']})")
            else:
                print(f"  (No workspace directories created yet in {config_mgr.workspace_root})")
            print("")

        elif action == "add":
            target_input = args.package_or_url
            source = getattr(args, "source", None)
            added = config_mgr.add_target(target_input, alias=args.alias, source=source)
            if added:
                resolved_pkg = config_mgr.resolve_package_name(target_input) or target_input
                log_success(f"Added target: {resolved_pkg} (Alias: {args.alias or resolved_pkg.split('.')[-1].capitalize()})")
                log_info(f"Saved to: {config_mgr.config_path}")
            else:
                log_warn(f"Target '{target_input}' is already configured.")

        elif action == "remove":
            removed = config_mgr.remove_target(args.package_or_alias)
            if removed:
                log_success(f"Removed target: {args.package_or_alias}")
                log_info(f"Saved to: {config_mgr.config_path}")
            else:
                log_warn(f"Target '{args.package_or_alias}' was not found in config.")

    elif cmd in ("env", "check"):
        print_banner()
        print_environment_report()

    elif cmd in ("install", "setup", "setup-path"):
        if args.check:
            print_banner()
            print_environment_report()
        else:
            permanent = not args.session
            added = install_environment(
                permanent=permanent,
                install_pip=not getattr(args, "skip_pip", False),
                link_npm=not getattr(args, "skip_npm", False),
            )
            if added:
                log_success("Configured PATH for REA_Kit tools:")
                for p in added:
                    print(f"    * {p}")
                if permanent:
                    log_info("Newly opened terminals will immediately recognize 'rea', 'adb', 'scrcpy', 'jadx', and 'apkd'.")
            else:
                log_info("All REA_Kit tool directories are already configured in User PATH.")
            print("")
            print_environment_report()

if __name__ == "__main__":
    main()
