---
name: static-pipeline
description: Run the full static acquisition pipeline (init → download → decode → native extract) with `rea pipeline`, or its steps individually. Use when starting analysis on a new target from scratch and you want decompiled sources and extracted native libs ready in one command. Orchestrates the other static skills.
---

# Static pipeline with `rea pipeline`

One command takes a package from nothing to a fully-populated workspace: workspace init → APK
download → JADX decompilation → native `.so` extraction.

## Command

```bash
rea pipeline <package-or-play-url>       # aliases: rea all, rea run
rea pipeline <package> -s <source>       # pick a download provider
rea pipeline <package> -j 8 --heap 16g   # JADX threads / heap (default heap 16g)
rea pipeline <package> --skip-decode     # acquire only
rea pipeline <package> --skip-native     # skip .so extraction
```

Equivalent to running, in order:

```bash
rea init <package>
rea download <package>
rea decode <package>
rea native extract <package>   # unless --skip-native
```

## When to use

- **Cold start** on a new target: prefer `rea pipeline` over the four commands.
- Use the **individual** skills when you already have part of the workspace, need to tune one
  step (re-decode with more heap, download a different source), or are iterating.

## After it runs

The workspace has `apks/`, `jadx_src/`, and `native/` populated. Next:

- Read the decompilation → skill `decompilation`.
- Inspect native libs → skill `native-analysis`.
- Go dynamic (device/traffic) → skills `device-control`, `traffic-capture`, `runtime-extraction`.

Each step is generated output; keep your findings under `findings/` / `docs/`.

Full reference: `docs/cli_reference.md`.
