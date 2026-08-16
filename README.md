# ARE_Kit - Android Reverse Engineering & Automation Kit

A unified, developer-centric toolkit for Android reverse engineering, APK downloading, bytecode decompilation, runtime sandbox extraction, and device automation.

---

## Quick Start

### 1. Install & Setup Environment (One-time)
Run the automated installer script to register all bundled binaries (`are`, `adb`, `scrcpy`, `jadx`, `apkd`, `scrcpy-cli`), link dependencies, and configure PATH:

```cmd
install.bat
```
*(Alternatively, run `are install` or `python are.py install`)*

### 2. Verify Your Environment
```bash
are env
```

### 3. Run the End-to-End Analysis Pipeline
Download, decompile, and extract runtime data in a single command:
```bash
are pipeline -t https://play.google.com/store/apps/details?id=com.zodiac.horoscope.palmreader.scanpalmistry
```

---

## Unified CLI (`are`) Reference

`ARE_Kit` provides a single command-line interface `are` (or `python are.py`):

| Command | Alias | Description | Example |
|---|---|---|---|
| `are init` | | Initialize workspace directories for targets | `are init com.target.app` |
| `are download` | `dl` | Download APK/XAPK packages using `apkd` | `are dl com.target.app` |
| `are decode` | `decompile` | Decompile APKs to Gradle project with JADX | `are decode -t com.target.app` |
| `are pull` | `runtime` | Extract sandbox database/prefs via ADB | `are pull -t com.target.app` |
| `are pipeline` | `all`, `run` | Run complete flow (init -> dl -> decode -> pull) | `are pipeline -t com.target.app` |
| `are scrcpy` | `control` | Automate Android device via `scrcpy-cli` | `are scrcpy tap 500 1200` |
| `are mirror` | `screen` | Launch interactive screen mirroring | `are mirror -s emulator-5554` |
| `are jadx-gui` | | Launch interactive JADX GUI | `are jadx-gui -t com.target.app` |
| `are apktool` | | Run bundled APKTool commands | `are apktool d app.apk -o output` |
| `are target` | | List, add, or remove target apps | `are target list` |
| `are env` | `check` | Diagnostics report for prerequisites & tools | `are env` |
| `are install` | `setup`, `setup-path` | Install & configure environment, tools, and PATH | `are install` |

---

## Device Control & Automation (`scrcpy_cli` Module)

`ARE_Kit` integrates [`@impeterwayne/scrcpy-cli`](https://github.com/impeterwayne/scrcpy_cli) as a Git submodule in `core/scrcpy_cli`.

If cloning this repository afresh, initialize submodules with:
```bash
git clone --recurse-submodules https://github.com/impeterwayne/ARE_Kit.git
```

### Fast Daemon Mode:
```bash
# Start background daemon session
are scrcpy daemon start

# Fast low-latency actions
are scrcpy tap 500 1200
are scrcpy swipe 500 1500 500 300 200
are scrcpy write "Hello World"
are scrcpy key HOME
are scrcpy screenshot app_screen.png
are scrcpy ui-dump app_ui.xml

# Stop daemon when done
are scrcpy daemon stop
```

---

## Repository Structure

```text
ARE_Kit/
├── install.bat                  # Single automated installer & PATH setup (Windows)
├── are.bat                      # Windows CLI executable
├── are.py                       # Python CLI entrypoint
├── arekit/                      # Unified Python package
│   ├── cli.py                   # Central parser & command router
│   ├── config.py                # Workspace & targets configuration
│   ├── workspace.py             # Workspace provisioning engine
│   ├── downloader.py            # APK download orchestrator (apkd)
│   ├── decompiler.py            # JADX / APKTool decompiler engine
│   ├── runtime.py               # Runtime sandbox extractor (ADB root/su/run-as)
│   ├── scrcpy.py                # Bridge to scrcpy_cli & scrcpy.exe
│   └── env.py                   # Environment checker & PATH configurator
├── config/
│   └── workspace_config.json    # Unified workspace & target configuration
├── core/
│   ├── apkdgo/                  # Bundled APK download engine (apkd.exe)
│   ├── apktool/                 # Bundled APKTool (apktool.jar)
│   ├── jadx/                    # Bundled JADX Decompiler v1.5.6
│   └── scrcpy_cli/              # Bundled scrcpy-cli module (with vendor/scrcpy v4.1 & adb)
├── docs/                        # Comprehensive Technical Guides
│   ├── README.md                # Documentation overview & index
│   ├── cli_reference.md         # Detailed CLI command manual
│   ├── scrcpy_control.md        # Device control & daemon guide
│   ├── decompilation.md         # JADX & split APK merging guide
│   ├── downloading_targets.md   # APK downloading guide
│   ├── runtime_extraction.md    # Sandbox runtime pulling guide
│   ├── workspace_management.md  # Workspace structure guide
│   └── workspace_config.md      # Configuration schema guide
└── workspaces/                  # Target sandbox databases and source code
```

---

## Prerequisites

* **Python 3.8+**
* **Java Development Kit (JDK) 11+** (for JADX and APKTool)
* **Node.js 22+** (for `scrcpy-cli` device automation)
* **Connected Device / Emulator** (with USB debugging enabled)

---

## License
MIT License
