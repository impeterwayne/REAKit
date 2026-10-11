---
name: dynamic-instrumentation
description: Instrument a running Android app with `rea frida` — manage frida-server, inject probes, hook Java/native, call the app's own functions over RPC, and read/scan memory. Use to confirm a static hypothesis at runtime, unpin TLS, dump decrypted buffers, trace native routines, or defeat root/debug detection. Start by checking the server is up (`rea frida doctor`); prefer attaching to a known PID and resume-after-load when spawning.
---

# Dynamic instrumentation with `rea frida`

`rea frida` drives Frida against a device: it manages frida-server (version- and ABI-matched),
enumerates and spawns/attaches processes, injects JS agents, exposes `rpc.exports`, and reads
memory. Probe output persists under `workspaces/<package>/dynamic/frida/`.

Default target is **frida 17.x**. frida 17 dropped the built-in Java/ObjC/Swift bridge; `rea frida`
loads it on demand from `frida-tools`. The packages are optional — install only when you actually
instrument: `pip install 'frida==17.*' 'frida-tools'` (native-only hooking doesn't need `frida-tools`).

## First: is the server up?

```bash
rea frida doctor            # host frida module + CLI, adb, device ABI, server liveness + version match, root
rea frida ls               # devices frida can see
rea frida ps               # processes (--apps for installed apps, --running to filter, --json)
```

If `doctor` says the server is missing or mismatched, set it up — it downloads the matched
frida-server, pushes it, and starts it detached as root:

```bash
rea frida setup                    # download+push+start frida-server matched to host version & device ABI
rea frida setup --version 16.5.9   # pin an exact version
rea frida server status|start|stop # lifecycle once installed
rea frida server install --force   # re-push (stops the old server first)
```

## Inject a probe

Bundled agents live in `reakit/frida_agents/`; pass one by name or point at your own file.

```bash
rea frida probe <pkg> --script probe_net --spawn --duration 120   # 4-layer network probe, spawn+resume
rea frida probe <pkg> --script anti_detect                        # observer-only root/frida detection recon
rea frida probe <pkg> --script stalker_trace --runtime v8         # basic-block tracer for one native module
rea frida probe <pkg> --file ./my_hook.js                         # your own agent
```

Probes stream live and are copied to `workspaces/<pkg>/dynamic/frida/`. Spawn when timing matters
(startup, first network call); otherwise attach. Hooks are live before the process resumes.

## Call the app's own code (RPC)

```bash
rea frida rpc <pkg> --file ./rpc.js --call getpackagename       # one-shot call, JSON out
rea frida rpc <pkg> --file ./rpc.js --call callnative 0x1234 ba de   # NativeFunction wrapper
rea frida rpc <pkg> --file ./rpc.js --repl                      # interactive
rea frida rpc <pkg> --file ./rpc.js --http 8099                 # POST /call, GET /exports, POST /reload
```

`rpc_template.js` is the starting point — it has the frida 16/17 `resolveExport` shim and
`callnative`/`callnativeaddr` wrappers for calling the app's exported or offset-addressed functions
(e.g. its own crypto).

## Memory and native

```bash
rea frida mem read  <pkg> --address 0x7f00 --size 64           # hex dump
rea frida mem scan  <pkg> --address 0x7f00 --size 4096 --pattern "de ad ?? ef"   # Memory.scanSync
rea frida mem write <pkg> --address 0x7f00 --hex "90 90"
rea frida mem protect <pkg> --address 0x7f00 --size 16 --prot rwx
rea frida inject-lib <pkg> --path /data/local/tmp/x.so --entrypoint init
rea frida gating enable <pkg> --child                          # spawn/child gating to catch forks
```

## Target selection

`-p PID` / `-n NAME` / `-N IDENTIFIER` / `-F` (frontmost) — mirrors the frida CLI. Prefer `-p` with
a PID from `rea frida ps` (frida's own enumeration can omit a running app). With no target, the
sole workspace / first configured target is used.

## Workflow

1. `rea frida doctor` — confirm the server; `setup` only if it says so.
2. Reproduce the behaviour under a probe (`probe_net` for network, `anti_detect` for detection).
3. Correlate: take a hooked class/method or a hit address and `grep_search` it in `jadx_src/` or
   cross-check in `rea native` — the code that built it is the finding, not the trace line.
4. Confirm a static hypothesis with a hook or an RPC call to the app's own function.

## Discipline

- The device, server, and probe logs are generated state — never hand-edit files under
  `dynamic/frida/`. Hand-written agents belong under `scripts/` or `patches/`.
- A probe that fires zero events is a signal: check the Java bridge loaded, the class is present,
  the UI was reached, and the server is still alive (ROMs hunt instrumentation).
- TLS pinning → report it, then unpin with a hook rather than fighting the proxy.

Full reference: `docs/frida.md`.
