import sys
import argparse
from pathlib import Path
from arekit.utils import print_banner, log_info, log_success, log_warn, log_error, Colors
from arekit.config import ConfigManager
from arekit.workspace import WorkspaceManager
from arekit.downloader import Downloader
from arekit.decompiler import Decompiler
from arekit.runtime import RuntimeExtractor
from arekit.scrcpy import ScrcpyBridge
from arekit.env import (
    check_environment,
    print_environment_report,
    install_environment,
    setup_windows_user_path,
    inject_runtime_path,
)

def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="are",
        description="ARE_Kit - Unified Android Reverse Engineering & Automation Framework",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("--workspace", "-w", help="Custom workspace root directory (defaults to ./workspaces in CWD)")
    parser.add_argument("--config", "-c", help="Path to workspace config JSON (defaults to local are.config.json or workspace_config.json)")

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
    pipe_p.add_argument("--workspace", "-w", help="Workspace root directory")
    pipe_p.add_argument("--config", "-c", help="Path to workspace_config.json")

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
        help="Install & configure ARE_Kit environment, tools, and Windows PATH",
    )
    sp_p.add_argument("--permanent", action="store_true", default=True, help="Permanently configure Windows User PATH and Environment (default)")
    sp_p.add_argument("--session", action="store_true", help="Configure PATH for current session only")
    sp_p.add_argument("--check", action="store_true", help="Check current environment & PATH status")
    sp_p.add_argument("--skip-pip", action="store_true", help="Skip editable Python package installation (pip install -e .)")
    sp_p.add_argument("--skip-npm", action="store_true", help="Skip scrcpy-cli global linking (npm link)")

    return parser

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
            log_error("No target package specified. Use 'are pull <package_name>' or '--package <package_name>'")
            sys.exit(1)
        extractor.extract_package(target)

    elif cmd in ("pipeline", "all", "run"):
        target = args.target_pos or args.target
        if not target:
            log_error("Target package name or Google Play URL is required. Example: are pipeline com.example.app")
            sys.exit(1)

        pkg = config_mgr.resolve_package_name(target) or target
        log_info(f"=== Starting Pipeline for {pkg} ===")
        log_info(f"Workspace Directory: {config_mgr.get_app_paths(pkg)['root']}")
        
        # 1. Init
        log_info("[Step 1/3] Initializing workspace...")
        mgr = WorkspaceManager(config_mgr)
        mgr.init_target(pkg, source_link=target if target.startswith("http") else None)

        # 2. Download
        log_info("[Step 2/3] Downloading target APK...")
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
            log_info(f"[Step 3/3] Decompiling APKs with JADX (Heap: {args.heap})...")
            dec = Decompiler(config_mgr)
            dec_ok = dec.decompile_package(pkg, threads=args.threads, heap_memory=args.heap)
            if not dec_ok:
                log_error(f"Pipeline failed: Decompilation failed for {pkg}.")
                sys.exit(1)
        else:
            log_info("[Step 3/3] Decompilation skipped (--skip-decode).")

        log_success(f"=== Static pipeline completed successfully for {pkg}! ===")

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
            print(f"\n{Colors.BOLD}ARE_Kit Project Context:{Colors.RESET}")
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
                log_success("Configured PATH for ARE_Kit tools:")
                for p in added:
                    print(f"    • {p}")
                if permanent:
                    log_info("Newly opened terminals will immediately recognize 'are', 'adb', 'scrcpy', 'jadx', and 'apkd'.")
            else:
                log_info("All ARE_Kit tool directories are already configured in User PATH.")
            print("")
            print_environment_report()

if __name__ == "__main__":
    main()
