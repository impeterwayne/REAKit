---
name: device-control
description: Drive a connected Android device or emulator with the `mobilerun` MCP server (observe → act → verify) and the `rea device` CLI — tap, swipe, type, launch apps, read the screen, dump the accessibility tree, take screenshots. Use when you need to put an app into a specific state for runtime extraction or traffic capture, automate a UI flow, or inspect what is on screen.
---

# Device control with `mobilerun` + `rea device`

Two faces of the same engine, pick by who is driving:

- **Agents drive through the `mobilerun` MCP server.** It is the vendored device-automation
  backend (`core/mobilerun_mcp`), launched by `rea device mcp` and registered in
  `.agents/mcp_config.json` / `.mcp.json`. Prefer it for interactive flows — it observes the
  screen, grounds every tap in a real element, and verifies the result for you.
- **Scripts and saved artifacts use the `rea device` CLI** (alias `rea dev`). Use it to capture a
  screenshot or an accessibility dump to a file, or for one-shot gestures in a shell script.

There is no daemon to start or stop anymore — the MCP server and the CLI both connect on demand.

## The MCP loop: observe → act → verify

The full tool catalog (94 tools) lives in the vendored skill — read it rather than memorising:
`core/mobilerun_mcp/.agents/skills/mobilerun/SKILL.md` and its
`references/tools_reference.md`. The core loop:

1. **Observe.** `read_screen` (fast text/ASCII grid — use first when you only need the text),
   `perceive_screen` (annotated screenshot with numbered Set-of-Mark `som_id`s), or `get_ui_tree`
   (structured accessibility hierarchy with resource-ids, bounds, flags).
2. **Act.** `tap(x, y | som_id)`, `tap_text`, `swipe`, `scroll` / `scroll_until`, `type_text`,
   `press_back` / `press_home` / `press_enter`, `key`, `launch_app` / `start_app`, `stop_app`,
   `open_deeplink`, `wait_for_text` / `wait_for_idle`, and more.
3. **Verify.** Every state-changing tool settles the screen and returns a `post_action_observation`
   (foreground app, element count, keyboard visible, screen changed). Read it to confirm success
   instead of blindly re-observing.

Two rules that bite if ignored:

- **`som_id`s are single-use.** They belong to the frame `perceive_screen` returned. Any action
  invalidates them (`stale_som_id`) — re-observe before reusing.
- **Never guess coordinates.** Prefer `tap_text`, a fresh `som_id`, or `find_nodes_on_screen` over
  hard-coded pixels; resolution and layout vary by device.

## Tool index (all 94)

Names only, grouped so you know what exists. Signatures and parameters:
`core/mobilerun_mcp/.agents/skills/mobilerun/references/tools_reference.md`.

| Group | Tools |
| :--- | :--- |
| Perception | `read_screen`, `perceive_screen`, `get_ui_tree`, `get_screenshot`, `screenshot`, `screenshot_path` |
| Gestures & keys | `tap`, `double_tap`, `long_press`, `long_press_at`, `swipe`, `scroll`, `scroll_up` / `scroll_down` / `scroll_left` / `scroll_right`, `scroll_to`, `type_text`, `type`, `press_home`, `press_back`, `press_enter`, `open_recent_apps`, `key`, `press` (legacy) |
| Apps & deep links | `launch_app`, `start_app`, `lookup_app`, `list_apps`, `list_app_deeplinks`, `resolve_deeplink`, `open_deeplink` |
| Core: UI & device info | `ui`, `ui_json`, `ui_with_recovery`, `capabilities`, `supports`, `screen_size`, `current_app_id`, `time` |
| Core: find & act | `find_nodes`, `find_nodes_on_screen`, `tap_text`, `tap_node`, `tap_and_wait`, `scroll_until`, `clear_input` |
| Core: wait & assert | `assert_on`, `assert_text_visible`, `wait_for_app`, `wait_for_idle`, `wait_for_screen_change`, `wait_for_text`, `wait_for_nodes` |
| Core: app lifecycle | `open_and_settle`, `stop_app`, `install_app`, `uninstall_app`, `grant_permission`, `open_deep_link` |
| Core: misc | `get_clipboard`, `set_clipboard`, `execute_script` (unsupported on Android over adb) |
| System & media | `system_intent`, `resolve_contact`, `read_notifications`, `dismiss_notification`, `notification_action`, `get_media_sessions`, `media_control`, `volume_up`, `volume_down`, `mute` |
| Files | `find_files`, `open_file` |
| Device & setup | `get_device_status`, `list_devices`, `ping_device`, `connect_device`, `disconnect_device`, `setup_portal`, `doctor`, `request_screen_capture_permission`, `echo` |
| Wait, events & validation | `wait_for`, `watch_device_events`, `validate_action`, `verify_action` |
| Plan ledger | `set_plan`, `mark_step`, `record_finding`, `end_session`, `get_usage_guide`, `web_search` |

A 95th tool, `adb` (raw adb args, e.g. `shell ...`), exists only when the server runs with
`MOBILERUN_MCP_ENABLE_ADB=1` and is refused under a safety policy. ReaKit does not enable it — use
`run_command` with `adb` / `rea pull` for shell work.

Most RE-relevant beyond the core loop: `list_app_deeplinks` / `open_deeplink` (reach screens
without navigating), `grant_permission` (skip runtime-permission dialogs), `read_notifications`
(OTP / push content), `watch_device_events` (what changed between actions), `stop_app` with
`clear_data` (reset to a cold start). Anything that reads the accessibility tree (`read_screen`,
`perceive_screen`, `get_ui_tree`, `find_*`, `tap_text`, the text/node waits) needs the Mobilerun
Portal installed — see Setup below; raw coordinate gestures and screenshots fall back to adb.

## The `rea device` CLI — scripts and saved artifacts

```bash
rea device list                              # confirm a device is attached (-s <serial> to pick one)
rea device app-start com.target.app [activity]  # launch the target
rea device app-stop com.target.app
rea device tap <x> <y>
rea device swipe <x1> <y1> <x2> <y2> [ms]
rea device write "text to type"
rea device key <name|keycode>                # e.g. ENTER, BACK, HOME
rea device screenshot shot.png               # capture the screen to a PNG
rea device ui-dump layout.json               # accessibility tree as JSON -> bounds for the next tap
rea device apps [--system]                   # list installed packages
rea device clipboard-get | clipboard-set <text>
```

Group flags: `-s/--serial` to pick a device (or `MOBILERUN_DEVICE`), `--json` for machine-readable
output. There is no XML dump anymore — `ui-dump` writes the Portal accessibility tree as JSON.

For an interactive mirror window instead of headless control: `rea mirror` (alias `rea screen`).

## Workflow

1. `rea device list` — confirm the device, note the serial if more than one.
2. Observe with the MCP loop (`read_screen` / `perceive_screen` / `get_ui_tree`) — or
   `rea device ui-dump layout.json` to read node bounds in a script — rather than guessing pixels.
3. Drive the flow (`launch_app` / `tap_text` / `type_text`, or the `rea device` equivalents).
4. Then capture: `rea pull` for sandbox state, `rea http` for traffic.

## Setup and troubleshooting

- **Prerequisites.** `rea install` builds the mobilerun venv (Python 3.11–3.13, via `uv`). The
  device needs the **Mobilerun Portal** APK (`com.mobilerun.portal`) with its accessibility
  service enabled.
- **Portal not installed / accessibility off.** Run `rea device setup` to install and enable the
  Portal. `rea device doctor` runs full diagnostics across ADB, the connection, and Portal
  permissions. `rea env` reports mobilerun status.
- **Device selection.** `-s <serial>` or `MOBILERUN_DEVICE`; with a single attached device it is
  picked automatically.
- **`stale_som_id`.** The screen changed after your last action — re-observe (`perceive_screen` /
  `read_screen`) to refresh the IDs.

## Discipline

- Screenshots and dumps are scratch — keep the ones that matter under `findings/` / `docs/`.
- Device automation is for the target you were authorized to analyse; don't wander to other apps.

Full reference: `docs/device_control.md`. Full MCP tool catalog:
`core/mobilerun_mcp/.agents/skills/mobilerun/SKILL.md`.
