---
name: decompilation
description: Decompile an APK/XAPK to readable Java with `rea decode` (JADX), and navigate the resulting `jadx_src/` tree. Use when you need to read an app's bytecode-derived sources, search for a class/method/string, or (re)generate decompilation. Covers JADX heap/thread tuning and split-APK merging.
---

# Bytecode decompilation with `rea decode`

Runs JADX over the acquired package(s) and writes readable Java to
`workspaces/<package>/jadx_src/`.

## Commands

```bash
rea decode <package>                 # decompile the acquired APK(s)
rea decode <path/to/app.apk>         # decompile a specific file
rea decode <package> -j 8 --heap 8g  # threads and JVM heap (default heap 8g)
```

- **Split/XAPK apps are merged** before decompilation, so `jadx_src/` is one coherent tree.
- **Heap matters.** Large apps OOM JADX — raise `--heap` (e.g. `16g`) if decode dies mid-run.
  Lower `-j` if the machine thrashes.

## Navigating the output

- The tree mirrors package structure: `jadx_src/com/target/...`.
- Search with `grep`/`grep_search`, don't read blindly:
  - crypto/signing: `HmacSHA`, `Cipher`, `AES`, `Mac`, `MessageDigest`, `sign`, `secret`, `token`
  - endpoints: hostnames, `/api/`, `Retrofit`, `OkHttp`, `@POST`, `@GET`
  - native bridges: `System.loadLibrary`, `native `, `JNI`
- Obfuscated names (`a`, `b.a`) carry meaning at their **call sites** — read who calls them.

## Discipline

- `jadx_src/` is **generated** — never hand-edit it (the artifact-guard hook blocks it); it is
  overwritten on the next `rea decode`. Findings and annotations go under `findings/` / `docs/`.
- Decompiled Java can be wrong where the bytecode is unusual. When it reads implausibly, check
  the smali (`rea apktool d ...`) or the raw bytecode before trusting it.
- For interactive browsing, `rea jadx-gui` opens the JADX GUI on the workspace.

Full reference: `docs/decompilation.md`, `jadx_help.txt`.
