# Android Device Control & Automation Guide

**ARE_Kit** integrates [`@impeterwayne/scrcpy-cli`](https://github.com/impeterwayne/scrcpy_cli) as a core module to enable low-latency, agent-friendly Android device automation and real-time screen mirroring.

---

## Architecture: Fast Daemon vs. ADB Fallback

```mermaid
graph LR
    User[User / Agent / Pipeline] -->|are scrcpy / are control| CLI[scrcpy-cli Engine]
    CLI -->|Daemon Running| Socket[scrcpy Control Socket :27183]
    Socket -->|Sub-millisecond Latency| Server[scrcpy-server on Device]
    CLI -->|Daemon Inactive| ADB[Direct ADB Shell Execution]
    ADB --> OS[Android OS]
```

1. **Daemon Mode (Recommended):** Keeps a persistent `scrcpy-server` connection open via TCP socket forwarding. Touch events, text entry, key injection, screenshots, and UI dumps execute in single-digit milliseconds without spawning separate ADB processes.
2. **Direct ADB Fallback:** If the background daemon is not running, commands automatically fall back to standard ADB shell executions.

---

## Daemon Lifecycle

```bash
# Start background daemon for default device
are scrcpy daemon start

# Check daemon running status
are scrcpy daemon status

# Run daemon in foreground (useful for debugging)
are scrcpy daemon run

# Stop background daemon
are scrcpy daemon stop
```

### Targeting Specific Devices
```bash
are scrcpy -s emulator-5554 daemon start
```

---

## Action Commands Reference

### 1. Touch & Gestures
```bash
# Tap coordinate (x, y)
are scrcpy tap 540 1200

# Swipe from (x1, y1) to (x2, y2) with duration in ms
are scrcpy swipe 540 1600 540 400 300

# Scroll at coordinate (x, y) by (dx, dy)
are scrcpy scroll 540 1200 0 -200
```

### 2. Text Input & Keycodes
```bash
# Type text into focused input field
are scrcpy write "Search query text"

# Press named Android keys
are scrcpy key HOME
are scrcpy key BACK
are scrcpy key ENTER
are scrcpy key VOLUME_UP
are scrcpy key POWER

# Press numeric Android keycode
are scrcpy key 3
```

### 3. Screen Capture & UI Inspection
```bash
# Capture screenshot (saves to screenshot.png by default)
are scrcpy screenshot app_screen.png

# Dump UI hierarchy XML (saves to ui-dump.xml by default)
are scrcpy ui-dump layout.xml
```

### 4. Clipboard Operations
```bash
# Read device clipboard
are scrcpy clipboard-get

# Set device clipboard
are scrcpy clipboard-set "Sample auth token"
```

### 5. Application Management
```bash
# Launch application
are scrcpy app-start com.zodiac.horoscope.palmreader.scanpalmistry

# Force-stop application
are scrcpy app-stop com.zodiac.horoscope.palmreader.scanpalmistry

# List installed packages
are scrcpy app-list
```

### 6. Device Diagnostics
```bash
# Display model, Android version, SDK, and resolution
are scrcpy device-info

# List all connected ADB devices
are scrcpy device-list
```

---

## Interactive Screen Mirroring (`are mirror` / `are screen`)

To launch a desktop screen mirroring window with full mouse and keyboard interaction:

```bash
# Launch interactive mirror on default device
are mirror

# Mirror specific device serial with custom max resolution & frame rate
are mirror -s emulator-5554 -m 1280 --fps 60

# Pass extra scrcpy flags
are mirror -- --stay-awake --turn-screen-off
```

### Mirror Options

| Flag | Long Option | Description |
|---|---|---|
| `-s` | `--serial <serial>` | Specific Android device serial |
| `-m` | `--max-size <size>` | Limit video width and height (e.g. `1280`) |
| | `--fps <fps>` | Limit video frame rate (e.g. `60`) |
