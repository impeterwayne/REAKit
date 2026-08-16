# ARE_Kit CLI Reference Manual

The `are` CLI provides a unified interface for every stage of Android reverse engineering, APK downloading, decompilation, runtime sandbox extraction, device automation, and environment configuration.

---

## Global Usage & Syntax

```bash
are [command] [positional_arg] [options]
```

### Global Options

These options apply across all relevant subcommands:

| Flag | Long Option | Description |
|---|---|---|
| `-w` | `--workspace <dir>` | Custom workspace root directory path (Defaults to `./workspaces`). |
| `-c` | `--config <file>` | Path to workspace configuration file (Defaults to `config/workspace_config.json`). |

---

## Complete Commands Directory

| Command | Aliases | Description | Primary Example |
|---|---|---|---|
| [`are init`](#1-are-init) | | Provision workspace directories for targets | `are init com.example.app` |
| [`are download`](#2-are-download--are-dl) | `dl` | Download APK/XAPK packages via `apkd` | `are dl com.example.app` |
| [`are decode`](#3-are-decode--are-decompile) | `decompile` | Decompile APKs into Java Gradle projects via JADX | `are decode com.example.app` |
| [`are pull`](#4-are-pull--are-runtime) | `runtime` | Extract app sandbox files via ADB (root/su/run-as) | `are pull com.example.app` |
| [`are pipeline`](#5-are-pipeline--are-all--are-run) | `all`, `run` | Execute complete automated flow (init -> dl -> decode -> pull) | `are pipeline -t com.example.app` |
| [`are scrcpy`](#6-are-scrcpy--are-control) | `control` | Low-latency device automation via `scrcpy-cli` | `are scrcpy tap 500 1200` |
| [`are mirror`](#7-are-mirror--are-screen) | `screen` | Launch desktop screen mirroring window | `are mirror -s emulator-5554` |
| [`are jadx-gui`](#8-are-jadx-gui) | | Launch interactive graphical JADX decompiler | `are jadx-gui -t com.example.app` |
| [`are apktool`](#9-are-apktool) | | Disassemble / reassemble APKs using APKTool | `are apktool d app.apk -o out` |
| [`are target`](#10-are-target) | | Inspect, add, or remove target apps | `are target list` |
| [`are env`](#11-are-env--are-check) | `check` | Diagnostics report for prerequisites and connected devices | `are env` |
| [`are install`](#12-are-install--are-setup--are-setup-path) | `setup`, `setup-path` | Install & configure environment, tools, and Windows PATH | `are install` |

---

## Detailed Command Specifications

### 1. `are init`
Provisions isolated target folders (`apks/`, `jadx_src/`, `docs/`, `runtime/`) and creates target metadata.

```bash
are init [target] [options]
```

| Flag | Long Option | Description |
|---|---|---|
| | `[target]` | Optional positional package name or Google Play URL |
| `-t` | `--target <pkg_or_url>` | Target package name or Play Store URL |
| `-i` | `--input <file>` | Path to custom input text file containing package list |
| `-w` | `--workspace <dir>` | Custom workspace root directory path |
| `-c` | `--config <file>` | Path to `workspace_config.json` |

```bash
# Initialize all targets from config
are init

# Initialize single target directly
are init com.example.app
are init "https://play.google.com/store/apps/details?id=com.example.app"
```

---

### 2. `are download` (`are dl`)
Downloads APK or Split APK (`.xapk`, `.apks`) archives from remote sources into `workspaces/<package>/apks/`.

```bash
are download [target] [options]
```

| Flag | Long Option | Description |
|---|---|---|
| | `[target]` | Optional positional package name or Play Store URL |
| `-l` | `--link <url_or_pkg>` | Direct Play Store URL or package name |
| `-t` | `--target <pkg_or_alias>` | Target package name or configured alias |
| `-s` | `--source <provider>` | Download source (`apkcombo`, `fdroid`, `rustore`, `nashstore`) |
| | `--targets <file>` | Path to custom targets text file |

```bash
# Download all targets configured in workspace_config.json
are dl

# Download single package
are dl com.zodiac.horoscope.palmreader.scanpalmistry

# Download from F-Droid
are dl org.lichess.mobileV2 -s fdroid
```

---

### 3. `are decode` (`are decompile`)
Decompiles APK/XAPK archives into a clean Java Gradle project using JADX with CPU multi-threading and JVM heap safeguards.

```bash
are decode [target] [options]
```

| Flag | Long Option | Description | Default |
|---|---|---|---|
| | `[target]` | Optional positional package name or alias | Active target |
| `-t` | `--target <pkg_or_alias>` | Target package name or alias | Active target |
| `-l` | `--link <url_or_pkg>` | Direct URL or package name to decode | None |
| `-j` | `--threads <n>` | JADX worker threads | Auto-detected CPU cores |
| | `--heap <size>` | JVM Heap allocation memory | `8g` |

```bash
# Decompile active / all targets
are decode

# Decompile specific target with 16 GB heap
are decode com.example.app --heap 16g -j 8
```

---

### 4. `are pull` (`are runtime`)
Extracts internal app databases (SQLite), Shared Preferences (XML), and caches via ADB directly from the device sandbox.

```bash
are pull [package_name] [options]
```

| Flag | Long Option | Description |
|---|---|---|
| | `[package_name]` | Target Android package name (positional) |
| `-p`, `-t` | `--package`, `--target` | Target package name |

```bash
# Pull runtime data for active target
are pull

# Pull runtime data for specific package
are pull com.zodiac.horoscope.palmreader.scanpalmistry
```

---

### 5. `are pipeline` (`are all`, `are run`)
Executes the full end-to-end workflow (init -> download -> decode -> pull) sequentially.

```bash
are pipeline [target] [options]
```

| Flag | Long Option | Description |
|---|---|---|
| | `[target]` | Target package name or Play Store URL (positional) |
| `-t` | `--target <target>` | Target package name or Play Store URL |
| `-s` | `--source <provider>` | APK download source repository |
| | `--skip-decode` | Skip the JADX decompilation phase |
| | `--skip-pull` | Skip the ADB runtime extraction phase |

```bash
are pipeline -t https://play.google.com/store/apps/details?id=com.zodiac.horoscope.palmreader.scanpalmistry
```

---

### 6. `are scrcpy` (`are control`)
Automates Android devices with sub-millisecond latency using the bundled `scrcpy-cli` engine.

```bash
are scrcpy [daemon|action] [args...]
```

```bash
# Daemon Management
are scrcpy daemon start
are scrcpy daemon status
are scrcpy daemon stop

# Gestures & Input
are scrcpy tap 540 1200
are scrcpy swipe 540 1600 540 400 300
are scrcpy write "Search term"
are scrcpy key HOME

# Capture & UI Dump
are scrcpy screenshot app_home.png
are scrcpy ui-dump layout.xml
```

---

### 7. `are mirror` (`are screen`)
Launches a real-time interactive desktop screen mirroring window.

```bash
are mirror [options]
```

| Flag | Long Option | Description |
|---|---|---|
| `-s` | `--serial <serial>` | Specific Android device serial |
| `-m` | `--max-size <size>` | Limit max video dimensions (e.g. `1280`) |
| | `--fps <fps>` | Limit video frame rate (e.g. `60`) |

```bash
are mirror -s emulator-5554 -m 1280 --fps 60
```

---

### 8. `are jadx-gui`
Launches the interactive graphical JADX decompiler with optional automatic APK loading.

```bash
# Open blank JADX GUI
are jadx-gui

# Open JADX GUI and load target app's APK
are jadx-gui com.example.app
```

---

### 9. `are apktool`
Direct CLI wrapper for the bundled APKTool binary for smali and resource disassembly.

```bash
# Disassemble APK
are apktool d app.apk -o smali_dir

# Reassemble APK
are apktool b smali_dir -o rebuilt.apk
```

---

### 10. `are target`
Inspects, registers, and removes target applications in `workspace_config.json`.

```bash
# List configured targets and workspace directory statuses
are target list

# Add target from Google Play URL
are target add "https://play.google.com/store/apps/details?id=com.example.app"

# Add target with custom alias and source
are target add com.example.app --alias "CustomApp" --source "fdroid"

# Remove target
are target remove com.example.app
```

---

### 11. `are env` (`are check`)
Runs comprehensive diagnostic checks on Python, Java JDK, Node.js, bundled binaries, and connected ADB devices.

```bash
are env
```

---

### 12. `are install` (`are setup`, `are setup-path`)
Automated installer and environment configurator for ARE_Kit. Automatically registers Windows User Environment PATH for all bundled tools (`are`, `adb`, `scrcpy`, `jadx`, `apkd`, `apktool`, `scrcpy-cli`), configures runtime environment variables (`SCRCPY_SERVER_PATH`, `ADB_PATH`), builds & registers `scrcpy-cli` globally via `npm link`, and registers the `arekit` Python package in editable mode via `pip install -e .`.

```bash
# Standard complete installation & PATH registration (Permanent)
are install

# Configure PATH for current terminal session only
are install --session

# Check installation & environment status
are install --check

# Custom installation flags
are install --skip-pip    # Skip pip editable install
are install --skip-npm    # Skip npm scrcpy-cli linking
```
