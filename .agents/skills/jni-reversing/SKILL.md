---
name: jni-reversing
description: Method for reversing JNI / native-backed logic — mapping Java `native` methods to their `.so` implementation, resolving dynamically-registered functions, and confirming a native routine's behaviour. Use when signing/crypto/anti-tamper logic lives in a `.so` and you need to understand what a JNI method actually computes. Pairs with the native-analysis tool skill.
---

# Reversing JNI / native-backed logic

App logic hidden in native code follows a small number of patterns. Know them and the search
collapses.

## 1. Find the bridge (static, in `jadx_src/`)

- `System.loadLibrary("core")` → the library is `libcore.so`.
- A `native` method `String sign(...)` in `com.app.Signer` maps to either:
  - **Static registration**: symbol `Java_com_app_Signer_sign` (mangled full path). Grep for it:
    `rea native functions --grep Java_com_app` or `rea native jni`.
  - **Dynamic registration**: no `Java_*` symbol — the names are wired in `JNI_OnLoad` via
    `RegisterNatives`. Decompile `JNI_OnLoad` (`rea native decompile JNI_OnLoad`) and read the
    `JNINativeMethod` table it passes: each entry is `{name, signature, fnPtr}`, so the table maps
    the Java name to a raw address you then decompile.

## 2. Read the implementation (backend)

```bash
rea native serve <package> --lib libcore.so --port 8091 -d
export GHIDRA_MCP_URL=http://127.0.0.1:8091
rea native jni                              # entry points
rea native decompile Java_com_app_Signer_sign   # or the 0xADDR from the RegisterNatives table
rea native strings --grep -i "key|secret|http"
rea native imports  --grep "Cipher|AES|SHA|Mac|EVP_"   # crypto surface
```

The first two JNI args are always `JNIEnv* env, jobject/jclass`; the real parameters follow.
Calls back into Java go through `env->CallObjectMethod` / `GetStringUTFChars` etc. — those reveal
what Java state the native code reads.

## 3. Identify the computation

- Match constants: AES S-box, SHA-256 round constants, MD5 magic, a fixed HMAC block size.
- Match imports: OpenSSL `EVP_*`, Android `AES_*`, or a bundled crypto lib.
- Where is the key? A hard-coded byte array, a string decrypted at runtime, a value fetched from
  Java (keystore / prior response), or derived from the device.

## 4. Confirm dynamically

Decompiled C is a hypothesis. Confirm with a Frida hook on the JNI method (log args + return),
or on the crypto primitive it calls (`CCCrypt`, `EVP_EncryptUpdate`, `Mac.doFinal`). Static +
one live capture = a finding. The hook script is an artifact — delegate it to a worker under
`patches/` / `scripts/`.

## Anti-analysis to expect

`ptrace`/`prctl` anti-debug, `JNI_OnLoad`-time integrity checks, string encryption, and packers
(see `rea native info` fingerprint). Each is a finding and a signpost, not a stop.

Tool commands: skill `native-analysis`, `docs/native_analysis.md`.
