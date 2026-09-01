---
trigger: always_on
---

# Dynamic Analysis Rule: device and traffic hygiene

Applies whenever the task drives a live device or captures traffic — `rea scrcpy`, `rea mirror`,
`rea pull`, `rea http`, or any hook/instrumentation run. Static-only tasks can ignore it.

## Before touching the device

- **Confirm a device is attached** (`rea env` / `rea scrcpy device-list`). One target device;
  name the serial with `-s` when more than one is connected.
- **The daemon is managed for you.** The `device-daemon` hook starts and stops `scrcpy-cli`.
  Do not run `daemon start` / `daemon stop` yourself — just issue actions (`tap`, `ui-dump`,
  `app-start`, `screenshot`).
- **Runtime extraction needs privilege.** `rea pull` escalates via native root, Magisk `su`, or
  `run-as` (debuggable builds). If a pull comes back empty, check which path applied before
  assuming there is nothing to pull.

## Capturing traffic

- **Just listen; assume the wiring is done.** Bare `rea http` attaches to the running HTTP
  Toolkit and streams live exchanges. Don't run `start` / `android` / `setup` pre-emptively —
  the listener says plainly if the app isn't up, and only then is wiring your problem
  (`rea http start`, `rea http android` to set the device proxy and CA).
- **Pinning is a finding, not an obstacle.** If HTTPS never appears, the app pins certificates —
  report it and reach for an unpinning hook rather than fighting the proxy.
- **Read from the log, don't re-drive blindly.** Exchanges persist under `traffic/`; inspect
  with `rea http events` / `show` / `body`. Drive the app to *produce* the state, then read the
  capture — don't guess at a request you can inspect.

## Correlate, then explain

Dynamic evidence exists to confirm a static hypothesis. A captured request plus the decompiled
code that builds it is a finding; either alone is a lead. When you observe a value on the wire,
trace back to where the app computed it — that's the reversing result, not the packet itself.
