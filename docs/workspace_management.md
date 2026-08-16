# Workspace Setup & Management Guide

This guide covers the directory schema, automated workspace provisioning, and target lifecycle management in **ARE_Kit**.

To maintain a clean separation of work, each target Android application is allocated an isolated workspace directory containing downloaded packages, decompiled Java sources, notes, and runtime databases.

---

## Isolated Workspace Schema

The workspace layout is provisioned dynamically based on `config/workspace_config.json`. When initialized, each target directory follows a standardized schema:

```text
workspaces/<package_name>/
├── apks/                                      # Downloaded APK, XAPK, or APKS split archives
├── jadx_src/                                  # Decompiled Java Gradle project (JADX)
│   ├── app/
│   │   ├── build.gradle
│   │   └── src/main/
│   │       ├── AndroidManifest.xml
│   │       ├── java/
│   │       └── resources/
│   ├── build.gradle
│   └── settings.gradle
├── docs/                                      # Local analyst notes, flow diagrams, and threat models
├── runtime/                                   # Extracted sandbox files (ADB)
│   ├── internal/                              # /data/data/<package_name> (databases, shared_prefs)
│   └── external/                              # /sdcard/Android/data/<package_name>
└── target_info.txt                            # Target metadata, source URL, and timestamp
```

---

## Workspace Initialization via CLI (`are init`)

The `are init` command reads targets from your configuration file or accepts target identifiers on the command line to create the full directory hierarchy.

### Command Syntax

```bash
are init [target] [options]
```

### Options

| Flag | Long Option | Description | Default |
|---|---|---|---|
| | `[target]` | Package name or Google Play URL (positional) | None |
| `-t` | `--target <pkg_or_url>` | Single package name or link to initialize | None |
| `-i` | `--input <file>` | Path to custom plain text targets file | None |
| `-w` | `--workspace <dir>` | Custom workspace root directory path | `./workspaces` |
| `-c` | `--config <file>` | Path to workspace configuration file | `config/workspace_config.json` |

---

### Practical Examples

#### 1. Initialize All Targets in Configuration
Initializes directories for all applications defined in `workspace_config.json`:
```bash
are init
```

#### 2. Initialize a Specific Target Package
```bash
are init com.zodiac.horoscope.palmreader.scanpalmistry
```

#### 3. Initialize from a Google Play Store URL
```bash
are init "https://play.google.com/store/apps/details?id=com.zodiac.horoscope.palmreader.scanpalmistry"
```

---

## Target Management (`are target`)

You can inspect, add, and remove targets dynamically using the `are target` subcommand:

### 1. List Configured Targets & Workspace Status
Inspect all configured targets and see if they have downloaded APKs, decompiled code, or extracted runtime files:
```bash
are target list
```

*Example Output:*
```text
ARE_Kit Project Context:
  * Active Config:  config\workspace_config.json
  * Workspace Root: workspaces

Configured Target Applications (2):
  1. com.zodiac.horoscope.palmreader.scanpalmistry (Alias: Scanpalmistry) (https://play.google.com/store/apps/details?id=com.zodiac.horoscope.palmreader.scanpalmistry)
  2. org.lichess.mobileV2 (Alias: Lichess) [Source: fdroid]

Workspace Directory Status (2):
  * com.zodiac.horoscope.palmreader.scanpalmistry: 1 APK(s), Decompiled, 4 runtime files (workspaces\com.zodiac.horoscope.palmreader.scanpalmistry)
  * org.lichess.mobileV2: 1 APK(s), Decompiled, 0 runtime files (workspaces\org.lichess.mobileV2)
```

### 2. Add a New Target Application
Add targets using package IDs or direct Play Store links (with optional custom aliases and download source providers):
```bash
# Add via Google Play Store URL
are target add "https://play.google.com/store/apps/details?id=com.example.app"

# Add with custom alias and source repository
are target add com.example.app --alias "CustomApp" --source "apkcombo"
```

### 3. Remove a Target Application
Remove a target from your active configuration by package name or alias:
```bash
are target remove com.example.app
```


