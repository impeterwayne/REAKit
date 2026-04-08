import os
import subprocess
import json
import shlex
from pathlib import PurePosixPath

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR = os.path.join(BASE_DIR, "config")
TARGETS_FILE = os.path.join(CONFIG_DIR, "targets.txt")
WORKSPACE_CONFIG_FILE = os.path.join(CONFIG_DIR, "workspace_config.json")

def format_display_path(path):
    absolute_path = os.path.abspath(path)
    try:
        relative_path = os.path.relpath(absolute_path, BASE_DIR)
    except ValueError:
        return absolute_path

    if relative_path.startswith(".."):
        return absolute_path
    return relative_path

def get_target_package():
    try:
        with open(TARGETS_FILE, "r", encoding="utf-8") as f:
            target_url = f.read().strip()
            if "id=" in target_url:
                return target_url.split("id=")[1].split("&")[0]
            # fallback if it's just the package name
            return target_url
    except Exception as e:
        print(f"[!] Warning: Could not read {TARGETS_FILE}: {e}")
        return "com.zodiac.horoscope.palmreader.scanpalmistry"

def get_output_dirs(package_name):
    workspace_root = "workspaces/PalmReader"
    runtime_internal = os.path.join("runtime", "internal")
    runtime_external = os.path.join("runtime", "external")
    try:
        if os.path.exists(WORKSPACE_CONFIG_FILE):
            with open(WORKSPACE_CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
                workspace_root = config.get("workspaceRoot", workspace_root)
                runtime_config = config.get("defaultStructure", {}).get("runtime", {})
                runtime_internal = runtime_config.get("internal", runtime_internal)
                runtime_external = runtime_config.get("external", runtime_external)
    except Exception as e:
        print(f"[!] Warning: Could not read {WORKSPACE_CONFIG_FILE}: {e}")

    if not os.path.isabs(workspace_root):
        workspace_root = os.path.join(BASE_DIR, workspace_root)

    app_root = os.path.join(workspace_root, package_name)
    return {
        "internal": os.path.join(app_root, runtime_internal),
        "external": os.path.join(app_root, runtime_external),
    }

PACKAGE_NAME = get_target_package()
OUTPUT_DIRS = get_output_dirs(PACKAGE_NAME)

def sanitize_filename(filename):
    illegal_chars = '<>:"\\|?*'
    for char in illegal_chars:
        filename = filename.replace(char, '_')
    return filename

def get_safe_relative_parts(remote_path, base_dir):
    try:
        relative_path = PurePosixPath(remote_path).relative_to(PurePosixPath(base_dir))
    except ValueError:
        return []

    parts = []
    for part in relative_path.parts:
        if not part or part in {".", ".."}:
            continue
        parts.append(sanitize_filename(part))
    return parts

def run_cmd(cmd):
    if isinstance(cmd, list):
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    else:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=True)
    return result.stdout.strip(), result.stderr.strip(), result.returncode

def ensure_local_dir(path):
    local_dir = os.path.abspath(os.path.normpath(path))
    drive, _ = os.path.splitdrive(local_dir)
    drive_root = os.path.join(drive + os.sep) if drive else os.path.abspath(os.sep)
    if local_dir == drive_root:
        return None
    if not os.path.exists(local_dir):
        os.makedirs(local_dir, exist_ok=True)
    return local_dir

def pull_file(remote_path, local_path, access_mode):
    if access_mode == "native_root":
        pull_cmd = ["adb", "exec-out", "cat", remote_path]
    elif access_mode == "su":
        pull_cmd = ["adb", "exec-out", "su", "-c", f"cat {shlex.quote(remote_path)}"]
    elif access_mode == "shell":
        pull_cmd = ["adb", "exec-out", "cat", remote_path]
    else:
        pull_cmd = ["adb", "exec-out", "run-as", PACKAGE_NAME, "cat", remote_path]

    with open(local_path, "wb") as f:
        return subprocess.run(pull_cmd, stdout=f, stderr=subprocess.PIPE)

def extract_runtime_tree(label, base_dir, output_dir, file_list, access_mode):
    files = [line.strip() for line in file_list.splitlines() if line.strip() and "Permission denied" not in line]
    print(f"[*] Found {len(files)} {label} files to extract.")

    for remote_path in files:
        safe_parts = get_safe_relative_parts(remote_path, base_dir)
        if not safe_parts:
            continue

        relative_path = "/".join(safe_parts)
        filename = safe_parts[-1]
        local_dir_parts = safe_parts[:-1]
        local_dir = os.path.join(output_dir, *local_dir_parts) if local_dir_parts else output_dir
        local_dir = ensure_local_dir(local_dir)
        if not local_dir:
            print(f"[-] Skipping suspicious local directory target for {remote_path}")
            continue

        local_path = os.path.join(local_dir, filename)
        result = pull_file(remote_path, local_path, access_mode)

        if result.returncode == 0:
            print(f"[+] Pulled {label}/{relative_path} -> {local_path}")
        else:
            print(f"[-] Failed to pull {label}/{relative_path}")
            if os.path.exists(local_path) and os.path.getsize(local_path) == 0:
                os.remove(local_path)

def main():
    for output_dir in OUTPUT_DIRS.values():
        if not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
        
    print(f"[*] Target Package: {PACKAGE_NAME}")
    print(f"[*] Extracting internal runtime data into ./{format_display_path(OUTPUT_DIRS['internal'])}/...")
    print(f"[*] Extracting external runtime data into ./{format_display_path(OUTPUT_DIRS['external'])}/...")
    
    # Check if adb is accessible
    _, _, ret = run_cmd(["adb", "devices"])
    if ret != 0:
        print("[!] adb not found or not running. Please ensure adb is in your PATH.")
        return
        
    base_dir = f"/data/data/{PACKAGE_NAME}"
    
    # Elevate adbm daemon natively (for AVD/Genymotion)
    print("[*] Elevating ADB daemon to root...")
    run_cmd(["adb", "root"])
    
    is_su = False
    is_native_root = False
    
    # 1. Try Native ADB Root 
    stdout, stderr, ret = run_cmd(["adb", "shell", "find", base_dir, "-type", "f"])
    if not stderr and ret == 0 and stdout:
        print("[+] Native 'adb root' access successful!")
        is_native_root = True
    else:
        # 2. Try Magisk 'su' Root
        # Note: Must pass the entire command safely as a single quoted string to ADB shell
        su_cmd = f"su -c 'find {base_dir} -type f'"
        stdout, stderr, ret = run_cmd(f"adb shell \"{su_cmd}\"")
        if ret == 0 and stdout and "Permission denied" not in stderr:
            print("[+] Magisk 'su' access successful!")
            is_su = True
        else:
            # 3. Fallback to debuggable 'run-as'
            print("[-] Root access failed. Trying 'run-as' for debuggable app...")
            stdout, stderr, ret = run_cmd(["adb", "shell", "run-as", PACKAGE_NAME, "find", base_dir, "-type", "f"])
        
    if not stdout or "is not debuggable" in stderr or "Permission denied" in stderr:
        print("[!] Sandbox blocked read. Make sure the app is installed, device is rooted, or app is debuggable.")
        if stderr:
             print(f"Error: {stderr}")
        return

    internal_access_mode = "run_as"
    if is_native_root:
        internal_access_mode = "native_root"
    elif is_su:
        internal_access_mode = "su"

    extract_runtime_tree("internal", base_dir, OUTPUT_DIRS["internal"], stdout, internal_access_mode)

    external_base_dirs = [
        f"/sdcard/Android/data/{PACKAGE_NAME}",
        f"/storage/emulated/0/Android/data/{PACKAGE_NAME}",
    ]
    external_found = False
    external_files_by_base = {}
    for external_base_dir in external_base_dirs:
        external_stdout, external_stderr, external_ret = run_cmd(["adb", "shell", "find", external_base_dir, "-type", "f"])
        if external_ret == 0 and external_stdout and "No such file or directory" not in external_stderr:
            print(f"[+] External runtime files found under {external_base_dir}")
            external_found = True
            external_files_by_base[external_base_dir] = [
                line.strip()
                for line in external_stdout.splitlines()
                if line.strip() and "Permission denied" not in line
            ]

    if not external_found:
        print("[*] No readable external runtime files found under known external storage paths.")
    else:
        seen_external_paths = set()
        for external_base_dir in external_base_dirs:
            files = external_files_by_base.get(external_base_dir, [])
            unique_files = []
            for remote_path in files:
                if remote_path in seen_external_paths:
                    continue
                seen_external_paths.add(remote_path)
                unique_files.append(remote_path)

            if unique_files:
                extract_runtime_tree(
                    "external",
                    external_base_dir,
                    OUTPUT_DIRS["external"],
                    "\n".join(unique_files),
                    "shell",
                )

    print(
        f"\n[*] Extraction complete! Data saved to ./{format_display_path(OUTPUT_DIRS['internal'])}/ "
        f"and ./{format_display_path(OUTPUT_DIRS['external'])}/"
    )

if __name__ == '__main__':
    main()
