# Workspace Setup & Management Guide

This guide covers the directory schema and automated initialization workflow for reverse engineering targets using **ARE_Kit**. 

To maintain clean separation of work, each target Android application is allocated an isolated workspace partition within the directory defined by the configuration.

---

## 📂 Isolated Workspace Schema

The workspace structure is structured dynamically based on `config/workspace_config.json`. When initialized, each application target directory looks like this:

```text
workspaces/PalmReader/<package_name>/
├── apks/               # Store downloaded .apk, .xapk, or .apks split archives
├── jadx_src/           # Target directory for decompiled Java classes and Gradle project
├── docs/               # Local notes, static analyses, and threat modeling reports
├── runtime/            # Runtime extracted sandbox files
│   ├── internal/       # Sandbox directories pulled from /data/data/<package_name>
│   └── external/       # Data directory pulled from sdcard storage paths
└── target_info.txt     # Metadata file storing origin URL and package name
```

---

## 🛠️ Workspace Initialization script (`init_workspace.py`)

The script `scripts/init_workspace.py` parses either configured apps or targets list, resolves package names, and recursively creates the directory schema defined above.

### Command-line Syntax

```bash
python scripts/init_workspace.py [options]
```

### Argument Reference

| Flag | Long Option | Default | Description |
|---|---|---|---|
| `-c` | `--config` | `workspace_config.json` | Path to the global workspace configuration file. |
| `-i` | `--input` | *None* | Path to a plain text file (`targets.txt` or similar) containing target Google Play store URLs or raw package names. *If provided, this overrides the default config application list.* |

---

## ⚙️ How it Works under the Hood

1. **Configuration Lookup:** Loads global workspace roots and subdirectory schemas from the JSON config.
2. **Target Extraction:** Parses package names recursively from URLs, Google Play query strings (`?id=package.name`), or raw strings using string patterns.
3. **Directory Provisioning:** 
   - Dynamically walks nested dictionary structures in `defaultStructure` to extract output directories.
   - Sorts subdirectories by hierarchy depth so parent folders are consistently provisioned before child partitions.
4. **Metadata Preservation:** Creates `target_info.txt` inside the root of each target directory, preserving the original source URL for tracing purposes.

---

## 📖 Practical Examples

### Example 1: Initializing Workspace from centralized Config Apps
This is the default mode. It structures workspaces for all apps currently listed in `workspace_config.json`:

```bash
python scripts/init_workspace.py --config config/workspace_config.json
```

### Example 2: Initializing Workspace from a bulk Target List
If you have a collection of competitor URLs compiled in `config/targets.txt`, you can import and initialize workspaces for all of them:

```bash
python scripts/init_workspace.py --config config/workspace_config.json --input config/targets.txt
```

> [!TIP]
> When providing an input target list, the script automatically parses out the final suffix of the package name (e.g. `com.zodiac.horoscope.palmreader.scanpalmistry` becomes `Scanpalmistry`) and sets it as the default human-readable folder alias.
