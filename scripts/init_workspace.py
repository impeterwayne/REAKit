import os
import json
import argparse
from urllib.parse import urlparse, parse_qs
from pathlib import Path

def load_config(config_path):
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def create_directory(path):
    try:
        Path(path).mkdir(parents=True, exist_ok=True)
        print(f"  [+] Created: {path}")
    except Exception as e:
        print(f"  [-] Failed to create {path}: {e}")

def extract_paths(structure_dict):
    """Recursively extract all directory paths from the structure definition."""
    paths = []
    for key, value in structure_dict.items():
        if isinstance(value, str):
            paths.append(value)
        elif isinstance(value, dict):
            paths.extend(extract_paths(value))
    return paths

def extract_package_name(line):
    """Extracts a package name from a Google Play link, APK store link, or raw string."""
    line = line.strip()
    if not line:
        return None
    
    # Method 1: Google Play format (?id=com.app.name)
    if "?id=" in line or "&id=" in line:
        parsed = urlparse(line)
        qs = parse_qs(parsed.query)
        if "id" in qs:
            return qs["id"][0]
            
    # Method 2: APK URL format (.../com.app.name)
    if line.startswith("http://") or line.startswith("https://"):
        parts = [p for p in line.split('/') if p]
        potential_pkg = parts[-1]
        if "." in potential_pkg and not potential_pkg.endswith((".html", ".php")):
            # strip .apk if present
            if potential_pkg.endswith(".apk"):
                return potential_pkg[:-4]
            return potential_pkg
            
    # Method 3: Assume it is already a direct package name if it has periods
    if "." in line and " " not in line and "/" not in line:
        return line
        
    return None

def get_apps_from_txt(txt_file):
    """Reads a text file line by line and pulls Android package names."""
    apps = []
    if not os.path.exists(txt_file):
        print(f"Error: Provided text file '{txt_file}' not found.")
        return apps
        
    print(f"Parsing links from: {txt_file}")
    with open(txt_file, 'r', encoding='utf-8') as f:
        for line in f:
            pkg = extract_package_name(line)
            if pkg:
                # Use the final suffix of the package as a quick guess for an alias
                alias = pkg.split('.')[-1].capitalize()
                apps.append({
                    "packageName": pkg,
                    "alias": alias,
                    "source_link": line.strip()
                })
            else:
                if line.strip():
                    print(f"  [!] Could not extract package from: {line.strip()}")
                
    return apps

def init_workspace(config_file, input_txt=None):
    print(f"Reading configuration from: {config_file}\n")
    config = load_config(config_file)
    
    workspace_root = Path(config.get("workspaceRoot", "workspaces/default"))
    structure = config.get("defaultStructure", {})
    
    # Default to config apps
    apps = config.get("apps", [])
    
    # If a text file is provided, override or merge the app list
    if input_txt:
        txt_apps = get_apps_from_txt(input_txt)
        if txt_apps:
            apps = txt_apps # Replace the config apps entirely with the text file targets
            
    if not apps:
        print("No apps to initialize. Exiting.")
        return

    subdirs = extract_paths(structure)
    subdirs.sort(key=len)

    print(f"\nInitializing Workspace Root: {workspace_root.absolute()}\n")
    
    for app in apps:
        package_name = app.get("packageName")
        if not package_name:
            continue
            
        print(f"Initializing app: {package_name} (Alias: {app.get('alias', 'None')})")
        app_dir = workspace_root / package_name
        
        # Create base app directory
        create_directory(app_dir)
        
        # Save a metadata file so we remember where it came from
        if "source_link" in app:
            meta_path = app_dir / "target_info.txt"
            with open(meta_path, "w", encoding="utf-8") as meta_f:
                meta_f.write(f"Package: {package_name}\n")
                meta_f.write(f"Source URL: {app['source_link']}\n")
        
        # Create standard structure inside app directory
        for subdir in subdirs:
            target_path = app_dir / subdir
            create_directory(target_path)
            
        print("") # blank line for readability

    print("Workspace initialization complete.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Initialize workspace for App Analytics / RE")
    parser.add_argument('--config', '-c', default='workspace_config.json', help='Path to config JSON')
    parser.add_argument('--input', '-i', help='Path to generic txt file containing app URLs')
    
    args = parser.parse_args()
    
    if os.path.exists(args.config):
        init_workspace(args.config, args.input)
    else:
        print(f"Error: Configuration file '{args.config}' not found.")
