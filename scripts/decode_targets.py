import os
import json
import argparse
import subprocess
import zipfile
import shutil
from urllib.parse import urlparse, parse_qs

def extract_package_name(line):
    line = line.strip()
    if not line:
        return None
    if "?id=" in line or "&id=" in line:
        parsed = urlparse(line)
        qs = parse_qs(parsed.query)
        if "id" in qs:
            return qs["id"][0]
    if line.startswith("http://") or line.startswith("https://"):
        parts = [p for p in line.split('/') if p]
        potential_pkg = parts[-1]
        if "." in potential_pkg and not potential_pkg.endswith((".html", ".php")):
            if potential_pkg.endswith(".apk"):
                return potential_pkg[:-4]
            return potential_pkg
    if "." in line and " " not in line and "/" not in line:
        return line
    return None

def build_app_lookup(config):
    apps = config.get('apps', [])
    lookup = {}
    for app in apps:
        package_name = app.get('packageName')
        if not package_name:
            continue

        lookup[package_name] = package_name

        alias = app.get('alias')
        if alias:
            lookup[alias] = package_name

    return lookup

def resolve_package_name(line, app_lookup):
    stripped_line = line.strip()
    if not stripped_line:
        return None

    if stripped_line in app_lookup:
        return app_lookup[stripped_line]

    extracted_package = extract_package_name(stripped_line)
    if extracted_package and extracted_package in app_lookup:
        return app_lookup[extracted_package]

    return extracted_package

def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    parser = argparse.ArgumentParser(description="Decode targets using jadx")
    parser.add_argument('--config', default=os.path.join(base_dir, 'config', 'workspace_config.json'), help='Path to workspace_config.json')
    parser.add_argument('--targets', default=os.path.join(base_dir, 'config', 'targets.txt'), help='Path to targets.txt')
    parser.add_argument('--link', help='Direct link or package name to decode instead of reading targets.txt')
    args = parser.parse_args()

    config_path = os.path.abspath(args.config)
    if not os.path.exists(config_path):
        print(f"Config file not found: {config_path}")
        return

    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    workspace_root_rel = config.get('workspaceRoot', 'workspaces/default')
    workspace_root = os.path.abspath(os.path.join(base_dir, workspace_root_rel))
    apks_dir_name = config.get('defaultStructure', {}).get('apks', 'apks')
    jadx_dir_name = config.get('defaultStructure', {}).get('jadx', 'jadx_src')
    app_lookup = build_app_lookup(config)

    if args.link:
        lines = [args.link]
    else:
        targets_path = os.path.abspath(args.targets)
        lines = []
        if os.path.exists(targets_path):
            with open(targets_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

        if not lines:
            lines = [app.get('packageName') for app in config.get('apps', []) if app.get('packageName')]

        if not lines:
            print(f"Targets file not found or empty, and no apps configured: {targets_path}")
            return

    jadx_exec_name = "jadx.bat" if os.name == 'nt' else "jadx"
    jadx_path = os.path.join(base_dir, "core", "jadx", "bin", jadx_exec_name)

    if not os.path.exists(jadx_path):
        print(f"Warning: jadx executable not found at {jadx_path}. Falling back to 'jadx' in PATH.")
        jadx_path = "jadx"

    # Verify jadx is available
    try:
        subprocess.run([jadx_path, "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print(f"Warning: {jadx_path} was not found or failed to execute. The command may fail.")

    env = os.environ.copy()
    if "JADX_OPTS" not in env:
        env["JADX_OPTS"] = "-Xmx8g -Xms8g"

    cpu_count = str(os.cpu_count() or 8)

    for line in lines:
        pkg = resolve_package_name(line, app_lookup)
        if pkg:
            input_dir = os.path.abspath(os.path.join(workspace_root, pkg, apks_dir_name))
            jadx_output_dir = os.path.abspath(os.path.join(workspace_root, pkg, jadx_dir_name))
            os.makedirs(jadx_output_dir, exist_ok=True)
            
            if not os.path.exists(input_dir):
                print(f"Directory not found, skipping: {input_dir}")
                continue
                
            apks_found = False
            for apk_name in os.listdir(input_dir):
                if apk_name.endswith('.apk'):
                    apks_found = True
                    apk_path = os.path.join(input_dir, apk_name)
                    decode_msg = f"Decoding {apk_name} for package {pkg} to {jadx_output_dir}"
                    print("-" * len(decode_msg))
                    print(decode_msg)
                    print("-" * len(decode_msg))
                    
                    jadx_cmd = [
                        jadx_path, 
                        "-d", jadx_output_dir,
                        "-j", cpu_count,
                        "--export-gradle",
                        "--deobf",
                        "--add-debug-lines",
                        "--comments-level", "debug",
                        "--respect-bytecode-access-modifiers",
                        "--no-inline-anonymous",
                        "--no-inline-methods",
                        "--no-replace-consts",
                        apk_path
                    ]
                    
                    print(f"Running: {' '.join(jadx_cmd)}")
                    subprocess.run(jadx_cmd, env=env)
                elif apk_name.endswith('.xapk') or apk_name.endswith('.apks'):
                    apks_found = True
                    archive_path = os.path.join(input_dir, apk_name)
                    extract_dir = os.path.join(input_dir, apk_name + "_extracted")
                    
                    if not os.path.exists(extract_dir):
                        print(f"Extracting {apk_name} to {extract_dir}...")
                        try:
                            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                                zip_ref.extractall(extract_dir)
                        except zipfile.BadZipFile:
                            print(f"Error: {apk_name} is not a valid zip file or is corrupted.")
                            continue
                    
                    extracted_apks = []
                    for root, dirs, files in os.walk(extract_dir):
                        for file in files:
                            if file.endswith('.apk'):
                                extracted_apks.append(os.path.join(root, file))
                    
                    if not extracted_apks:
                        print(f"No .apk files found inside the archive {apk_name}")
                        continue
                        
                    decode_msg = f"Decoding {apk_name} ({len(extracted_apks)} split APKs) for package {pkg} to {jadx_output_dir}"
                    print("-" * len(decode_msg))
                    print(decode_msg)
                    print("-" * len(decode_msg))
                    
                    jadx_cmd = [
                        jadx_path, 
                        "-d", jadx_output_dir,
                        "-j", cpu_count,
                        "--export-gradle",
                        "--deobf",
                        "--add-debug-lines",
                        "--comments-level", "debug",
                        "--respect-bytecode-access-modifiers",
                        "--no-inline-anonymous",
                        "--no-inline-methods",
                        "--no-replace-consts"
                    ] + extracted_apks
                    
                    print(f"Running: {' '.join(jadx_cmd)}")
                    subprocess.run(jadx_cmd, env=env)
            
            if not apks_found:
                print(f"No .apk, .xapk, or .apks files found in {input_dir}")
        else:
            if line.strip():
                print(f"Could not extract package from: {line.strip()}")

if __name__ == "__main__":
    main()
