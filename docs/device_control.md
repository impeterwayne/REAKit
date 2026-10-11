# Android Device Control & Automation Guide (`rea device`)

Static analysis tells you what an app *could* do; driving the device shows you what it *does on
screen*. `rea device` is the device-automation half of a target, alongside `rea native` (compiled
code), `rea http` (the wire) and `rea pull` (on-device files). It is backed by the vendored
[**Mobilerun MCP**](https://github.com/droidrun/mobilerun-portal) engine (`core/mobilerun_mcp`, a
git submodule) and exposes it two ways:

1. **For AI clients:** the `mobilerun` MCP server — an observe → act → verify loop with 90+ tools.
2. **For scripts and saved artifacts:** the `rea device` CLI (alias `rea dev`) — screenshots,
   accessibility dumps, and one-shot gestures.

All heavy lifting runs on the host; the only thing on the device is the **Mobilerun Portal**
accessibility service. There is no control daemon to start or stop — both faces connect on demand.

```mermaid
flowchart LR
    AI["AI client<br/>(Claude Code, etc.)"] -->|rea device mcp| MCP["mobilerun MCP server<br/>(core/mobilerun_mcp)"]
    CLI["Your terminal<br/>rea device ..."] --> ENGINE["mobilerun engine"]
    MCP --> ENGINE
    ENGINE -->|adb (bundled)| PORTAL["Mobilerun Portal<br/>accessibility service"]
    PORTAL --> DEV[("Android device<br/>/ emulator")]
    CLI -->|screenshot / ui-dump| WS[("workspaces/&lt;pkg&gt;/docs/spec")]
```

---

## 1. One-time setup

| Requirement | Notes |
|---|---|
| **mobilerun venv** | `rea install` builds it (Python **3.11–3.13**, via [`uv`](https://docs.astral.sh/uv/)). Skip it with `rea install --skip-mobilerun` if you don't need device control. |
| **Mobilerun Portal APK** | The `com.mobilerun.portal` accessibility service must be installed and enabled on the device. `rea device setup` installs and enables it for you. |
| **ADB** | Already bundled with REA_Kit (`core/scrcpy_cli/vendor/scrcpy/adb.exe`). mobilerun is pointed at that same binary via `MOBILERUN_ADB_BIN`, so its adb version always matches the rest of the kit. |

```bash
rea env             # reports mobilerun status among the other prerequisites
rea device setup    # install + enable the Mobilerun Portal accessibility service
rea device doctor   # full diagnostics: ADB, connection, Portal permissions
```

### Device selection

With a single device attached, it is picked automatically. With more than one, name it with the
`-s/--serial` group flag or the `MOBILERUN_DEVICE` environment variable:

```bash
rea device -s emulator-5554 list
```

---

## 2. Driving from an AI client (the `mobilerun` MCP server)

Agents drive the device through the `mobilerun` MCP server, not the CLI. It is registered for the
agent harness in `.agents/mcp_config.json` and for Claude Code in `.mcp.json`. To print
ready-to-paste client configuration for another client:

```bash
rea device mcp --config     # emit MCP client configuration
rea device mcp              # run the stdio MCP server
rea device mcp --http --port 4816   # run it over HTTP instead of stdio
```

The core loop is **observe → act → verify**:

1. **Observe** — `read_screen` (fast text grid), `perceive_screen` (annotated screenshot with
   numbered `som_id` marks), or `get_ui_tree` (structured accessibility hierarchy).
2. **Act** — `tap(x, y | som_id)`, `tap_text`, `swipe`, `scroll` / `scroll_until`, `type_text`,
   `press_back` / `press_home` / `press_enter`, `key`, `launch_app` / `start_app`, `stop_app`,
   `open_deeplink`, `wait_for_text` / `wait_for_idle`, and more.
3. **Verify** — state-changing tools settle the screen and return a `post_action_observation`;
   read it instead of re-observing blindly.

Two gotchas: `som_id`s are single-use (any action invalidates them — re-observe before reuse), and
never hard-code coordinates (prefer `tap_text` or a fresh `som_id`). The full 90+ tool catalog
with parameters is in the vendored skill —
`core/mobilerun_mcp/.agents/skills/mobilerun/SKILL.md` and its `references/tools_reference.md`.

---

## 3. The `rea device` CLI (`rea dev`)

For scripts, one-shot gestures, and saving durable artifacts into the workspace.

### Gestures & input

```bash
rea device tap 540 1200
rea device swipe 540 1600 540 400 300      # x1 y1 x2 y2 [duration_ms]
rea device write "Search query text"
rea device key ENTER                         # named key or numeric keycode (BACK, HOME, ...)
```

### Screen capture & inspection

```bash
rea device screenshot app_screen.png         # PNG
rea device ui-dump layout.json               # accessibility tree as JSON (no XML)
```

The dump is the Portal accessibility tree serialized as JSON — resource-ids, text, bounds, and
interactive flags for every node. Use the bounds to compute the next tap instead of guessing.

### Application & clipboard

```bash
rea device app-start com.example.app [activity]
rea device app-stop com.example.app
rea device apps [--system]                   # list installed packages
rea device clipboard-get
rea device clipboard-set "Sample auth token"
```

Add `--json` to any inspection command for machine-readable output.

### Command reference

| Command | Description |
|---|---|
| `rea device mcp [--config] [--http] [--port N]` | Run (or print config for) the `mobilerun` MCP server |
| `rea device list` | List connected ADB devices |
| `rea device setup` | Install and enable the Mobilerun Portal APK |
| `rea device doctor` | Diagnose ADB, connection, and Portal permissions |
| `rea device screenshot <out.png>` | Capture the screen to a PNG |
| `rea device ui-dump <out.json>` | Dump the accessibility tree as JSON |
| `rea device tap <x> <y>` | Tap at coordinates |
| `rea device swipe <x1> <y1> <x2> <y2> [ms]` | Swipe between two points |
| `rea device write <text>` | Type text into the focused field |
| `rea device key <name\|keycode>` | Press a named key or keycode |
| `rea device app-start <pkg> [activity]` | Launch an app |
| `rea device app-stop <pkg>` | Force-stop an app |
| `rea device apps [--system]` | List installed packages |
| `rea device clipboard-get` | Read the device clipboard |
| `rea device clipboard-set <text>` | Set the device clipboard |

Group flags: `-s/--serial <serial>` (or `MOBILERUN_DEVICE`) to pick a device, `--json` for
machine-readable output. Command alias: `rea dev`.

---

## 4. Interactive screen mirroring (`rea mirror` / `rea screen`)

For a live desktop window with full mouse and keyboard interaction — a human watching the device,
not an agent driving it — use `rea mirror`, which is backed by scrcpy and unchanged:

```bash
rea mirror                                   # mirror the default device
rea mirror -s emulator-5554 -m 1280 --fps 60 # specific serial, max size, frame rate
rea mirror -- --stay-awake --turn-screen-off # pass extra scrcpy flags
```

| Flag | Long Option | Description |
|---|---|---|
| `-s` | `--serial <serial>` | Specific Android device serial |
| `-m` | `--max-size <size>` | Limit video width and height (e.g. `1280`) |
| | `--fps <fps>` | Limit video frame rate (e.g. `60`) |

---

## 5. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `no device selected` | More than one device attached. Set `-s <serial>` or `MOBILERUN_DEVICE`. |
| `adb devices` shows `unauthorized` | Unlock the phone and tap **Allow** on the USB debugging prompt. |
| `Mobilerun Portal is not enabled` | Install + enable the Portal: `rea device setup`. Verify with `rea device doctor`. |
| Client lists no `mobilerun` tools | Check the MCP config path/syntax (`rea device mcp --config`) and restart the client. |
| `stale_som_id` | The screen changed after your last action — re-observe (`perceive_screen` / `read_screen`). |
| adb version mismatch with the rest of the kit | mobilerun uses REA_Kit's bundled adb via `MOBILERUN_ADB_BIN` (`core/scrcpy_cli/vendor/scrcpy/adb.exe`); confirm that env var points there. |
| mobilerun venv missing | `rea install` (or re-run without `--skip-mobilerun`). `rea env` reports its status. |
