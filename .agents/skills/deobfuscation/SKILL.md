---
name: deobfuscation
description: Method for working through obfuscated Android code — renamed symbols, string encryption, reflection indirection, packers/DEX loaders, and control-flow obfuscation. Use when the decompilation is deliberately unreadable and you need a strategy to recover meaning instead of grinding on it. Tells you which technique fits which obfuscation.
---

# Working through obfuscation

Obfuscation raises the cost of reading, not the impossibility. Identify the kind, then apply the
technique that beats it — and don't grind statically on something a dynamic capture settles in a
minute.

## 1. Identify what you're facing

| Symptom | Likely technique |
| :--- | :--- |
| Class/method names are `a`, `b`, `c.a` | identifier renaming (R8/ProGuard) |
| Strings are absent; code calls `X.a(int)` returning a string | string encryption / pooled decrypt |
| Logic goes through `Method.invoke` / `Class.forName` | reflection indirection |
| `jadx_src/` is tiny; real code loads later | packer / dynamic DEX loading |
| Functions have huge `switch`/state machines with no clear flow | control-flow flattening |
| `.so` fingerprint names a packer | native packing (see `rea native info`) |

## 2. Technique per case

- **Renaming** — names are gone but *structure* isn't. Anchor on things that can't be renamed:
  framework calls, `R.string`/resource ids, endpoint strings, JNI symbols, `Intent` actions.
  Read call sites; name functions by what they call.
- **String encryption** — find the decryptor (`X.a(int)` / `X.b(String)` called everywhere on
  string-typed results). Then either: hook it dynamically and log `(input → output)` across a
  run, or, if it's a pure static routine, reimplement it in a small script over the string pool.
  The hook/script is an artifact — delegate it.
- **Reflection** — the target class/method names are usually plaintext strings passed to
  `Class.forName`/`getMethod`. Grep those literals; they point at the real callee.
- **Packers / dynamic DEX** — the interesting code isn't in `jadx_src/`. Pull it at runtime:
  dump loaded DEX from the process (Frida `Java.enumerateLoadedClasses` / a DEX dumper), or pull
  `runtime/` after the loader runs. Then decompile the recovered DEX.
- **Control-flow flattening** — don't reconstruct by hand. Trace the real path dynamically (hook
  the dispatcher variable, or log the sequence of state values), or focus only on the block that
  touches your target data.

## 3. Golden rule: escalate to dynamic early

Static deobfuscation has sharply diminishing returns. The moment you're reconstructing a
decryptor or a flattened graph by eye, stop and hook it: one logged `input→output` table beats an
hour of static guessing. Static tells you *where* to hook; the hook tells you *what it does*.

## 4. Record recovered meaning where it survives

You cannot annotate `jadx_src/` (generated, overwritten). Keep a symbol map — obfuscated name →
recovered meaning, with the evidence — under `findings/` or `docs/`.

Consult `oracle` when the strategy itself is unclear; escalate native packing to `native-analyst`.
