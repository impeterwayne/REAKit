---
name: runtime-extraction
description: Pull an app's private sandbox state (databases, shared-prefs, files, caches) off a device with `rea pull`. Use when you need the app's runtime data — stored tokens, SQLite DBs, config, keystores — after driving it into a given state. Handles ADB privilege escalation (native root, Magisk su, run-as).
---

# Sandbox runtime extraction with `rea pull`

Copies the target's private data directories off the device into
`workspaces/<package>/runtime/internal` and `runtime/external`.

## Command

```bash
rea pull <package>          # e.g. rea pull com.target.app
rea pull -p <package>       # same, explicit flag
```

## Privilege escalation (automatic)

`rea pull` tries, in order:

1. **Native root** — `adb root` on a rooted/eng build.
2. **Magisk `su`** — `adb shell su -c` on a Magisk-rooted device.
3. **`run-as`** — works only on a **debuggable** build of the app, no root needed.

If a pull comes back empty, check which path applied: a release build on a non-rooted device
exposes nothing via `run-as`, so you need root or a debuggable rebuild.

## Workflow

1. Drive the app into the state you care about first (skill `device-control`): log in, trigger
   the feature, let it write its DBs. Runtime extraction captures *current* state.
2. `rea pull <package>`.
3. Inspect `runtime/internal/` — `databases/*.db` (open with sqlite), `shared_prefs/*.xml`,
   `files/`, `cache/`. Correlate stored values (tokens, keys) back to the decompiled code that
   wrote them.

## Discipline

- `runtime/` is **generated** — a re-pull overwrites it; never hand-edit it. Copy anything you
  annotate into `findings/`.
- Extracted data is the app's own state; treat credentials found there as sensitive and keep
  them in the workspace, out of reports you share.

Full reference: `docs/runtime_extraction.md`.
