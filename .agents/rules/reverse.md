---
trigger: always_on
---

# Reverse Engineering Rule: evidence over inference

This harness analyses Android apps you were given to analyse — authorized security testing,
CTF, malware/RE research, interop and compatibility work. Do the analysis rigorously; the
value is in claims that hold up, not in a fast guess.

## 1. Every claim is backed by an artifact

The failure mode of RE is the confident, wrong answer. A decompiler emits plausible C from
ambiguous bytes; an obfuscator renames `sign()` to `a()` and inlines it into three call
sites; a string that reads like a key is a red herring. So:

- **Name the evidence.** A finding cites the file and line (`jadx_src/.../Api.java:214`), the
  address (`0x11a40` in `libnative.so`), or the captured exchange (`rea http show <id>`). "The
  app signs requests with HMAC-SHA256" without a pointer is a hypothesis, not a finding.
- **Prefer the lowest layer that settles it.** Smali/bytecode and native instructions beat
  decompiled Java/C when they disagree. When JADX output looks wrong, check the smali.
- **Confirm dynamically when you can.** A hooked value, a logged argument, or a captured
  request turns a static guess into a fact. Static + one dynamic confirmation is the standard.

## 2. The workspace layout is the map

A target lives under `workspaces/<package>/` (or the repo-local workspace) with a fixed shape.
Know where things are and where new things go:

| Directory | Holds | Written by |
| :--- | :--- | :--- |
| `apks/` | acquired packages | `rea download` |
| `jadx_src/` | decompiled Java | `rea decode` |
| `native/` | extracted `.so` + Ghidra exports | `rea native` |
| `runtime/` | pulled sandbox state (internal/external) | `rea pull` |
| `traffic/` | captured API exchanges | `rea http` |
| `findings/`, `docs/` | **your** analysis, notes, reports | you |

`jadx_src/`, `native/`, `apks/`, `runtime/` are **generated** — they are overwritten on the
next `rea` run. Never hand-edit them (the artifact-guard hook blocks it). Analysis, patches,
and hook scripts go under `findings/`, `docs/`, or `patches/`, which survive.

## 3. Use the kit; don't reinvent it

Reach for the `rea` CLI before writing bespoke tooling — it already wraps the tools and the
workspace conventions. The static pipeline is `rea init → download → decode`; native analysis
is `rea native`; dynamic work is `rea scrcpy` / `rea pull` / `rea http`. Each has a skill under
`.agents/skills/`. Only write a custom script when no subcommand covers the step.

## 4. Report like an analyst

A finding states **what** (the mechanism), **where** (the evidence pointer), and **how sure**
(confirmed by bytes/trace, or inferred and why). Distinguish "the code does X" from "I believe
the code does X". Note the blast radius: which classes, which endpoints, which native calls.
When something is obfuscated or packed and you could not resolve it, say so plainly and name
the next step — a partial map labelled honestly beats a complete-looking map that is half guess.
