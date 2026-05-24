# Automated Target Downloader Guide

This document describes how to configure and execute automated target APK downloads using **ARE_Kit** scripts and the bundled downloading binary.

---

## 🚀 Downloading Engine Overview

Downloading applications manually is tedious and prone to version drift. `ARE_Kit` integrates a compiled Go-based downloading utility (**`apkd`**), located in `core/apkdgo/apkd.exe`. The Python orchestrator `scripts/download_targets.py` automates directory mapping and runs the download executable concurrently.

---

## 🛠️ Downloader Script (`download_targets.py`)

The script reads target URLs or packages from files or parameters, resolves target namespaces, structures the folders, and downloads the binary packages directly into the respective target's `apks/` directory.

### Command-line Syntax

```bash
python scripts/download_targets.py [options]
```

### Argument Reference

| Flag | Long Option | Default | Description |
|---|---|---|---|
| *None* | `--config` | `config/workspace_config.json` | Path to the global workspace configuration file. |
| *None* | `--targets` | `config/targets.txt` | Path to targets list containing package names or download URLs. |
| *None* | `--link` | *None* | Direct URL or package name to download on-demand (ignores `targets.txt`). |
| *None* | `--apkd` | `core/apkdgo/apkd.exe` | Explicit path to the underlying `apkd.exe` binary. |

---

## 🔄 Automatic Configuration Auto-Discovery

When you download a package that was not previously registered in the system, `download_targets.py` automatically updates `workspace_config.json`:

1. Detects new packages downloaded during execution.
2. Extracts package endings (e.g. `com.lichess.mobileV2` -> `Mobilev2`).
3. Appends an entry into `apps` array with `packageName` and `alias`.
4. Writes updates back to `workspace_config.json` on exit.

This dynamic feature ensures newly fetched packages are immediately accessible by decompiler and sandbox tools without manual JSON entry.

---

## ⚙️ Downloader Engine Reference (`apkd.exe`)

The downloader is powered by the custom Go binary `apkd.exe`. 

### Standalone CLI Arguments

```text
Flags:
      --config string       path to YAML config file (defaults to ~/.config/apkd/config.yml if present)
      --dev                 download all apps from developer
  -f, --file string         file containing package names
  -F, --force               force download even if the file already exists
  -l, --list-sources        list available download sources
  -O, --output-dir string   output directory for downloaded APKs
  -o, --output-file string  output file name for downloaded APKs
  -p, --package stringArray package name of the app
      --proxy string        global proxy URL for all traffic
      --proxy-insecure      skip TLS certificate verification for requests sent through proxy
  -s, --source stringArray  specify source(s) for downloading
  -v, --verbose count       Set verbosity level. Use -v or -vv for more verbosity
  -V, --version             print version and exit
      --workers int         number of worker goroutines (default 3)
```

---

## 📖 Practical Examples

### Example 1: Download from Target file
Processes all URLs in `config/targets.txt` and downloads packages:

```bash
python scripts/download_targets.py --config config/workspace_config.json --targets config/targets.txt
```

### Example 2: Download a single target on-demand
Downloads a package and adds it to workspace configuration without editing `targets.txt`:

```bash
python scripts/download_targets.py --link com.whatsapp
```

> [!WARNING]
> Ensure you have adequate internet access during download. Some sources might utilize IP geoblocking or cloudflare checks. If you run into issues, try using the `--proxy` configuration options directly on the underlying `apkd.exe` tool.
