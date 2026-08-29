---
name: native-analysis
description: Analyze Android native libraries (.so / ELF) and their JNI functions using this repo's `rea native` CLI (extraction, ELF/packer fingerprinting, and headless Ghidra decompilation via GhidraMCP). Use when asked to inspect, decompile, or understand a .so file, JNI_* / Java_* native methods, an APK's native code, or a packer/obfuscator. Runs as plain CLI commands — no MCP server registration required.
---

# Native (.so) analysis with `rea native`

This repo ships a CLI, `rea native`, that extracts Android native libraries and analyzes
them through a **headless Ghidra** backend (GhidraMCP). You drive it entirely with shell
commands and read stdout — there is **no MCP server to register**, so nothing bloats context.

Run every command as `python rea.py native <args>` from the repo root (`D:\Quest\ReaKit`).
Full reference: `docs/native_analysis.md`.

## When to use this
- "What do the JNI functions in `<lib>.so` do?"
- "Decompile `<function>` from this native library."
- "Is this APK's native code packed/obfuscated? What framework is it?"
- "Extract and inspect the `.so` files in `<package>`."

## Two kinds of command

1. **Offline (no backend, instant)** — extraction and fingerprinting:
   ```bash
   python rea.py native extract <package>          # pull lib/<abi>/*.so from the APKs
   python rea.py native list <package>             # ranked table (packers/JNI first)
   python rea.py native info <package> --lib <name> # full ELF report for one library
   python rea.py native info <path/to/file.so>     # any .so path, no package needed
   ```

2. **Backend queries (need a running server on :8089)** — functions, strings, decompile:
   ```bash
   python rea.py native functions --grep Java_
   python rea.py native decompile <function-name-or-0xADDRESS>
   python rea.py native strings --grep -i "key|token|http"
   python rea.py native imports --grep "ptrace|dlopen|prctl"
   python rea.py native call <any-of-253-endpoints> -p key=value
   ```

## Standard workflow

```bash
# 1. (once) confirm the backend is set up
python rea.py native setup

# 2. extract native libraries (offline)
python rea.py native extract <package>
python rea.py native list <package>

# 3. start a headless server with ONE library loaded, detached
python rea.py native serve <package> --lib <name>.so --port 8091 -d
export GHIDRA_MCP_URL=http://127.0.0.1:8091      # PowerShell: $env:GHIDRA_MCP_URL="http://127.0.0.1:8091"

# 4. query it
python rea.py native jni                           # list Java_* entry points
python rea.py native decompile <function>          # decompiled C
python rea.py native strings --grep -i "secret|key|url"

# 5. stop when done
python rea.py native stop --port 8091
```

Analyzing a standalone `.so` (no package/workspace) — use `--file`:
```bash
python rea.py native serve --file <path/to/file.so> --port 8091 -d
export GHIDRA_MCP_URL=http://127.0.0.1:8091
python rea.py native jni
```

## Rules and gotchas
- **Ports:** the default backend port is 8089, which a running Ghidra GUI plugin may already
  hold. Prefer `--port 8091` and set `GHIDRA_MCP_URL` to match so queries hit your own server.
- **PowerShell vs bash:** set the env var with `$env:GHIDRA_MCP_URL="..."` in PowerShell, or
  `export GHIDRA_MCP_URL=...` in bash. In Git Bash, a leading-slash endpoint like
  `/list_functions` gets path-mangled — use the bare alias (`native functions`) or prefix the
  command with `MSYS_NO_PATHCONV=1`.
- **Big libraries:** `serve` warns and skips libraries over 64 MB (auto-analysis is slow). Pick a
  smaller/targeted library with `--lib`, or pass `--max-size-mb 0` / `--force` deliberately.
- **Keep output tight:** always add `--grep`/`--limit` to query commands so responses stay small.
- **Cleanup:** always `python rea.py native stop --port <port>` when finished.
- **Do not** register an MCP server or run `rea native mcp` for this — plain CLI is enough.

## Iterating many libraries in one server
Import the libraries once (auto-analysis is cached), then switch between them without
restarting Ghidra:
```bash
python rea.py native import <package> --abi arm64-v8a --jni-only   # analyze all, once
python rea.py native serve <package> --from-project --port 8091 -d
export GHIDRA_MCP_URL=http://127.0.0.1:8091
python rea.py native switch /arm64-v8a/<lib>.so                    # instant, no re-analysis
python rea.py native jni
```

## Reference files (read on demand)
- **`references/endpoints.md`** — the full **253-endpoint schema** (method, path, params,
  description, grouped by category). Consult it to call anything beyond the short commands,
  e.g. renaming, comments, structs, xref/call-graph, data types:
  ```bash
  python rea.py native call <endpoint> -p key=value          # -X POST for POST endpoints
  python rea.py native call rename_function -p function=FUN_00101234 -p new_name=verify_sig
  ```
- **`references/workflows/`** — GhidraMCP **workflow playbooks** (function documentation,
  data-type investigation, string labeling, orphaned-code discovery, plate comments, naming
  conventions). Their tool names map to `rea native call <tool_name>`. Open the matching
  playbook when the task is that kind of work (e.g. `STRING_LABELING_CONVENTION.md`,
  `FUNCTION_DOC_WORKFLOW_V5.md`, `TOOL_USAGE_GUIDE.md`). Do **not** read them all up front —
  only the one you need.

## Reporting
After running the commands, summarize what the library does based on: JNI export names, the
decompiled C of the key function(s), notable imports (anti-debug: `ptrace`/`prctl`; loading:
`dlopen`), and revealing strings. Quote the actual command output you observed.
