# Android Reverse Engineering Kit (ARE_Kit)
---
## Installation & Setup

Clone the repository with submodules and run the main installer:

```bash
git clone --recurse-submodules https://github.com/impeterwayne/ARE_Kit.git
cd ARE_Kit
python are.py install
```

> **Windows Batch Alternative**: You can also run `install.bat` from the root directory.

### Verify Installation:
```bash
are env
```

---
## Architecture

`ARE_Kit` is partitioned into clean, modular components coordinated by a unified CLI engine:

```mermaid
flowchart TD
    subgraph Static ["Static Pipeline (are pipeline)"]
        direction TB
        S1["<b>1. are init</b><br/><i>Workspace Setup</i> · are target"]
        S2["<b>2. are download</b><br/><i>APK Acquisition via apkd</i>"]
        S3["<b>3. are decode</b><br/><i>JADX Decompilation</i>"]
        S1 --> S2 --> S3
    end

    subgraph Dynamic ["Dynamic Analysis Loop"]
        direction TB
        S4["<b>4. are scrcpy</b><br/><i>Device Control & UI Automation</i>"]
        S5["<b>5. are pull</b><br/><i>ADB Sandbox Runtime Extraction</i>"]
        
        S4 -->|Interact & Trigger State| S5
        S5 -->|Iterate / Next Action| S4
    end

    Static --> Dynamic

    Static --> WS[(Target Workspace)]
    S5 --> WS
    S4 <--> DEV[(Android Device / Emulator)]
```

---

## Documentation Index

1. **[CLI Reference Manual](./docs/cli_reference.md)** - Comprehensive manual for the `are` CLI and all 12 subcommands.
2. **[Device Control & Automation Guide](./docs/scrcpy_control.md)** - Low-latency scrcpy daemon control and automation actions.
3. **[Workspace Setup & Management Guide](./docs/workspace_management.md)** - Directory schemas and target workspace management.
4. **[Target Downloading Guide](./docs/downloading_targets.md)** - Automated APK downloading via `apkd`.
5. **[Bytecode Decompilation & JADX Guide](./docs/decompilation.md)** - JADX memory safeguards, split APK merging, and decompilation.
6. **[Runtime Extraction Guide](./docs/runtime_extraction.md)** - ADB privilege escalation (native root, Magisk su, run-as) and sandbox pulling.
7. **[Configuration Schema Guide](./docs/workspace_config.md)** - Central `workspace_config.json` schema details.

---

## Prerequisites

To run all capabilities of `ARE_Kit`, ensure the following packages are installed:

* **Python 3.8+** (runs the `arekit` engine).
* **Java Development Kit (JDK) 11+** (required for `JADX` decompiler and `APKTool`).
* **Node.js 22+** (required for `scrcpy-cli` device automation).
* **A Connected Device or Emulator** (physical device, Genymotion, or Android Studio AVD).

