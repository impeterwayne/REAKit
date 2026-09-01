---
name: workspace-setup
description: Create and manage a ReaKit target workspace with `rea init` / `rea target`. Use when starting analysis on a new app, adding a package to track, or when you are unsure where decompiled sources, native libs, traffic, or runtime data should live. Establishes the fixed directory layout every other skill depends on.
---

# Workspace setup with `rea init` / `rea target`

Every target gets a workspace with a fixed shape. The other skills read and write into it, so
set it up first and know the layout.

## Create / initialize

```bash
rea init <package-or-playstore-url>     # e.g. rea init com.target.app
rea init -i config/targets.txt          # initialize many from a list
rea init -w <root> -c <config.json>     # override workspace root / config
```

This creates `workspaces/<package>/` (root configurable in `config/workspace_config.json`) with:

| Dir | Holds | Written by |
| :--- | :--- | :--- |
| `apks/` | acquired packages | `rea download` |
| `jadx_src/` | decompiled Java | `rea decode` |
| `native/` | extracted `.so` + Ghidra exports | `rea native` |
| `runtime/internal`, `runtime/external` | pulled sandbox state | `rea pull` |
| `traffic/` | captured API exchanges | `rea http` |
| `docs/` | workspace notes | you |

Create `findings/`, `patches/`, `scripts/` yourself for durable analysis output — those are
never regenerated.

## Manage targets

```bash
rea target list                     # configured packages + workspaces
rea target add <package-or-url>     # track a new target
rea target remove <package-or-alias>
```

Targets and aliases live in `config/workspace_config.json`. `rea` resolves a bare `<package>`
argument against that config, and most native/http subcommands default to the only workspace
when you omit the target.

## Rules of the road

- **Generated dirs are off-limits to hand edits** — `jadx_src/`, `native/`, `apks/`, `runtime/`
  are overwritten on the next `rea` run (the artifact-guard hook enforces this).
- Your analysis goes in `findings/`, `docs/`, `patches/`, `scripts/`.

Full reference: `docs/workspace_management.md`, `docs/workspace_config.md`.
