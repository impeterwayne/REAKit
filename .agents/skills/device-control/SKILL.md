---
name: device-control
description: Drive a connected Android device or emulator with `rea scrcpy` (scrcpy-cli) — tap, swipe, type, launch apps, dump the UI hierarchy, take screenshots. Use when you need to put an app into a specific state for runtime extraction or traffic capture, automate a UI flow, or inspect what is on screen. The daemon is managed for you.
---

# Device control with `rea scrcpy`

`rea scrcpy <args>` passes straight through to `scrcpy-cli`, giving low-latency,
screen-free control of a device. Use it to drive an app into the state other skills capture.

## The daemon is managed for you

The `device-daemon` hook starts and stops the `scrcpy-cli` daemon per session. **Do not run
`daemon start` / `daemon stop`** — just issue actions.

## Common actions

```bash
rea scrcpy device-list                 # confirm a device is attached (-s <serial> to pick one)
rea scrcpy app-start com.target.app    # launch the target
rea scrcpy app-stop com.target.app
rea scrcpy tap <x> <y>
rea scrcpy swipe <x1> <y1> <x2> <y2> [ms]
rea scrcpy write "text to type"
rea scrcpy key <keycode>               # e.g. KEYCODE_ENTER, BACK
rea scrcpy scroll <x> <y> <dx> <dy>
rea scrcpy screenshot shot.png         # capture the screen
rea scrcpy ui-dump layout.xml          # UI hierarchy XML -> coordinates for the next tap
rea scrcpy clipboard-get | clipboard-set <text>
```

For an interactive mirror window instead of headless control: `rea mirror` (aliases `screen`).

## Workflow

1. `rea scrcpy device-list` — confirm the device, note the serial if more than one.
2. `rea scrcpy ui-dump layout.xml` — read node bounds to compute exact tap coordinates rather
   than guessing pixels.
3. Drive the flow (`app-start`, `tap`, `write`, ...).
4. Then capture: `rea pull` for sandbox state, `rea http` for traffic.

## Discipline

- Screenshots and UI dumps are scratch — keep the ones that matter under `findings/` / `docs/`.
- Device automation is for the target you were authorized to analyse; don't wander to other apps.

Full reference: `docs/scrcpy_control.md`.
