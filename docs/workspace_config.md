# Workspace Configuration Schema Reference

This reference details the schema of the centralized configuration file **`config/workspace_config.json`**. 

All Python scripts in **ARE_Kit** read from this file to locate output paths, provision workspaces, and resolve application package mappings.

---

## ⚙️ Workspace Configuration File Layout

A standard configuration file consists of three top-level keys:

```json
{
  "workspaceRoot": "workspaces/PalmReader",
  "defaultStructure": {
    "apks": "apks",
    "jadx": "jadx_src",
    "docs": "docs",
    "runtime": {
      "base": "runtime",
      "internal": "runtime/internal",
      "external": "runtime/external"
    }
  },
  "apps": [
    {
      "packageName": "com.target.example",
      "alias": "TargetAppOne"
    },
    {
      "packageName": "com.zodiac.horoscope.palmreader.scanpalmistry",
      "alias": "Scanpalmistry"
    }
  ]
}
```

---

## 🔑 Schema Property Reference

### 1. `workspaceRoot` (String)
* **Description:** The relative or absolute base path where target workspace folders are created.
* **Default:** `workspaces/default`
* **Behavior:** If a relative path is provided, it resolves relative to the `ARE_Kit` root directory.

### 2. `defaultStructure` (Object)
Defines the standard internal directory schema initialized for every new target package.

| Path Key | Typical Value | Purpose |
|---|---|---|
| `apks` | `"apks"` | Path where package archives (`.apk`, `.xapk`) are downloaded and stored. |
| `jadx` | `"jadx_src"` | Folder where JADX outputs decompiled Java code and resource structures. |
| `docs` | `"docs"` | Directory for keeping notes, analysts' logs, or custom security reports. |
| `runtime.base` | `"runtime"` | Parent folder containing extracted runtime states. |
| `runtime.internal` | `"runtime/internal"` | Local target folder for `/data/data/<package>` data. |
| `runtime.external` | `"runtime/external"` | Local target folder for `/sdcard/Android/data/<package>` data. |

> [!NOTE]
> The scripts extract directory paths recursively. You can add arbitrary custom directories under `defaultStructure` (e.g. `"mitm": "mitm_intercepts"`) and `init_workspace.py` will automatically create them for every app workspace.

### 3. `apps` (Array of Objects)
Maintains a mapping between full package names and human-friendly folder names.

* **`packageName` (String):** The official unique package ID of the target Android application (e.g. `org.lichess.mobileV2`).
* **`alias` (String):** A unique, short, capitalized directory alias (e.g., `Mobilev2`). This determines the actual folder name generated inside the `workspaceRoot`.

---

## 🔄 Dynamic Runtime Modification

* The script `scripts/download_targets.py` automatically updates this file when it encounters a new package. It resolves a clean camel-case directory alias and appends it to the `apps` block.
* Standard JSON serialization is configured with a 2-space indentation to ensure the file remains readable and easily parsed by VCS (like Git).
