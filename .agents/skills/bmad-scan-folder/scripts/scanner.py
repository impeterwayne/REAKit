import os
import re
import argparse
from datetime import datetime

CLASS_RE = re.compile(r'public\s+(?:final\s+|abstract\s+|class\s+|interface\s+|enum\s+)*(class|interface|enum)\s+(\w+)')
METHOD_RE = re.compile(r'(public|protected|private)\s+(?:static\s+)?(?:final\s+)?([\w<>\[\]?]+)\s+(\w+)\s*\(([^)]*)\)')

def analyze_file(filepath, source_dir):
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except Exception as e:
        return None
        
    lines = content.splitlines()
    rel_path = os.path.relpath(filepath, source_dir)
    loc = len(lines)
    
    classes = []
    methods = []
    imports = []
    side_effects = []
    
    for line in lines:
        line_clean = line.strip()
        if line_clean.startswith('import '):
            imports.append(line_clean[7:-1])
        class_match = CLASS_RE.search(line_clean)
        if class_match:
            classes.append(class_match.group(2))
        
        if not line_clean.endswith(';') and not '=' in line_clean:
            method_match = METHOD_RE.search(line_clean)
            if method_match:
                ret_type = method_match.group(2)
                name = method_match.group(3)
                args = method_match.group(4)
                if ret_type not in ['class', 'interface', 'enum']:
                    methods.append(f"{name}({args}): {ret_type}")
        
        # simple heuristics for side effects
        if 'SharedPreferences' in line_clean or 'MMKV' in line_clean:
            side_effects.append("Local Storage")
        if 'SQLite' in line_clean or 'Room' in line_clean or 'INSERT ' in line_clean:
            side_effects.append("Database")
        if 'Retrofit' in line_clean or 'OkHttp' in line_clean or 'http' in line_clean.lower():
            side_effects.append("Network/API")
            
    side_effects = list(set(side_effects))
    
    return {
        'path': rel_path,
        'loc': loc,
        'classes': classes,
        'methods': methods,
        'imports': len(imports),
        'side_effects': side_effects
    }

def main():
    parser = argparse.ArgumentParser(description="Generate a Deep-Dive Markdown Inventory for a specific folder")
    parser.add_argument("--source", required=True, help="Absolute path to the source folder to scan")
    parser.add_argument("--output", required=True, help="Absolute path where the markdown report should be saved")
    args = parser.parse_args()

    source_dir = args.source
    output_file = args.output

    if not os.path.exists(source_dir):
        print(f"Error: Source directory '{source_dir}' does not exist.")
        return

    out_dir = os.path.dirname(output_file)
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    file_inventory = []

    print(f"Scanning {source_dir}...")
    for root, _, files in os.walk(source_dir):
        for f in files:
            # We target Java and Kotlin files assuming Android/Java codebase
            if f.endswith('.java') or f.endswith('.kt'):
                res = analyze_file(os.path.join(root, f), source_dir)
                if res:
                    file_inventory.append(res)
                    
    md = [
        f"# Deep-Dive Documentation: {os.path.basename(source_dir)}",
        f"\n**Source:** `{source_dir}`",
        f"**Generated on:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"\n**Files Analyzed:** {len(file_inventory)}",
        f"**Total LOC:** {sum(f['loc'] for f in file_inventory)}",
        "\n## Comprehensive File Inventory\n"
    ]

    for item in sorted(file_inventory, key=lambda x: x['path']):
        md.append(f"### `{item['path']}`")
        md.append(f"- **Purpose:** Extracted classes and logic from {item['path']}.")
        md.append(f"- **Lines of Code:** {item['loc']}")
        
        if item['classes']:
            md.append("- **Classes:** " + ", ".join(item['classes']))
        if item['methods']:
            md.append("- **Exports (Methods):**")
            for m in item['methods'][:15]: # Show up to 15 methods to avoid overwhelming size
                md.append(f"  - `{m}`")
            if len(item['methods']) > 15:
                md.append(f"  - ... ({len(item['methods']) - 15} more methods)")
        if item['side_effects']:
            md.append("- **Side Effects:** " + ", ".join(item['side_effects']))
        md.append(f"- **Dependencies (Imports):** {item['imports']} imports")
        md.append("\n---\n")

    md.append("\n## Data Flow & Integration Points")
    md.append("*(Automatically inferred from side effects)*\n")
    
    network = [f['path'] for f in file_inventory if 'Network/API' in f['side_effects']]
    if network:
        md.append("\n### Network / API Integrations")
        for n in network:
            md.append(f"- `{n}`")

    local_db = [f['path'] for f in file_inventory if 'Local Storage' in f['side_effects'] or 'Database' in f['side_effects']]
    if local_db:
        md.append("\n### Local Storage / Database")
        for l in local_db:
            md.append(f"- `{l}`")

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("\n".join(md))

    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("## Deep-Dive Scan Complete! ✓")
    print(f"**Generated:** {output_file}")
    print(f"**Files Analyzed:** {len(file_inventory)}")
    print(f"**Lines of Code Scanned:** {sum(f['loc'] for f in file_inventory)}")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

if __name__ == "__main__":
    main()
