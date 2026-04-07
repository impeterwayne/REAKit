import os
import json
import argparse
import subprocess
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

def extract_paths(structure_dict):
    paths = []
    for key, value in structure_dict.items():
        if isinstance(value, str):
            paths.append(value)
        elif isinstance(value, dict):
            paths.extend(extract_paths(value))
    return paths


def main():
    # Base directory is one level up from "scripts"
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    parser = argparse.ArgumentParser(description="Download targets using apkd")
    parser.add_argument('--config', default=os.path.join(base_dir, 'config', 'workspace_config.json'), help='Path to workspace_config.json')
    parser.add_argument('--targets', default=os.path.join(base_dir, 'config', 'targets.txt'), help='Path to targets.txt')
    parser.add_argument('--link', help='Direct link or package name to download instead of reading targets.txt')
    parser.add_argument('--apkd', default=os.path.join(base_dir, 'core', 'apkdgo', 'apkd.exe'), help='Path to apkd executable')
    args = parser.parse_args()

    config_path = os.path.abspath(args.config)
    if not os.path.exists(config_path):
        print(f"Config file not found: {config_path}")
        return

    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # workspaceRoot in config might be relative to base_dir
    workspace_root_rel = config.get('workspaceRoot', 'workspaces/default')
    workspace_root = os.path.abspath(os.path.join(base_dir, workspace_root_rel))
    apks_dir_name = config.get('defaultStructure', {}).get('apks', 'apks')

    if args.link:
        lines = [args.link]
    else:
        targets_path = os.path.abspath(args.targets)
        lines = []
        if os.path.exists(targets_path):
            with open(targets_path, 'r', encoding='utf-8') as f:
                lines.extend(f.readlines())
        
        # Fallback to apps from config if targets.txt is missing/empty
        if not lines and 'apps' in config:
            for app in config['apps']:
                if 'packageName' in app:
                    lines.append(app['packageName'])
                    
        if not lines:
            print("No targets found to download.")
            return

    apkd_path = os.path.abspath(args.apkd)
    if not os.path.exists(apkd_path):
        print(f"Error: apkd executable not found at {apkd_path}")
        return

    config_updated = False
    
    for line in lines:
        pkg = extract_package_name(line)
        if pkg:
            # Create full workspace structure for the app
            app_dir = os.path.abspath(os.path.join(workspace_root, pkg))
            structure = config.get('defaultStructure', {})
            subdirs = extract_paths(structure)
            for subdir in subdirs:
                os.makedirs(os.path.join(app_dir, subdir), exist_ok=True)
                
            output_dir = os.path.abspath(os.path.join(workspace_root, pkg, apks_dir_name))
            print(f"Downloading {pkg} to {output_dir}")
            
            cmd = [apkd_path, "-p", pkg, "-O", output_dir]
            print(f"Running: {' '.join(cmd)} from cwd={os.path.dirname(apkd_path)}")
            subprocess.run(cmd, cwd=os.path.dirname(apkd_path))
            
            # Add to config if not present
            apps = config.get('apps', [])
            if not any(a.get('packageName') == pkg for a in apps):
                alias = pkg.split('.')[-1].capitalize()
                apps.append({"packageName": pkg, "alias": alias})
                config['apps'] = apps
                config_updated = True
        else:
            if line.strip():
                print(f"Could not extract package from: {line.strip()}")
                
    if config_updated:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
        print(f"Updated config with new apps: {config_path}")

if __name__ == "__main__":
    main()
