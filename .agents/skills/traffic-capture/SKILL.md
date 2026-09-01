---
name: traffic-capture
description: Capture and inspect an app's API traffic with `rea http` (HTTP Toolkit) — list exchanges, read headers and bodies, wire the device proxy and CA, and handle the free-tier source quirk. Use when analysing network behaviour, auth/signing on the wire, or which endpoint returns what. Start by listening (bare `rea http`) and assume setup is already correct; read from the captured log, don't blindly re-drive.
---

# API traffic capture with `rea http`

`rea http` drives HTTP Toolkit: it launches the app, exposes the proxy, and reads captured
exchanges. Exchanges persist under `workspaces/<package>/traffic/`.

## Just listen

**Assume the setup is already correct** — HTTP Toolkit running, device proxied, CA trusted.
Start by listening:

```bash
rea http                                 # stream new exchanges live (bare `rea http` = listen)
rea http -g "login|token"                # client-side regex filter
rea http -f "hostname*=api"              # HTTP Toolkit filter expression
```

It fails immediately with a clear message if HTTP Toolkit is not actually up. Only then reach
for the setup commands below — don't run them pre-emptively.

## Setup and device wiring (only when listening says it isn't ready)

```bash
rea http setup            # check the HTTP Toolkit install + live API (alias: doctor)
rea http start            # launch HTTP Toolkit and wait for its API (alias: launch)
rea http proxy            # show proxy port, CA cert, reachable addresses
rea http android          # point an ADB device at the proxy + push the CA (alias: device)
rea http android --off    # clear the device proxy and reverse tunnels
rea http cert -o ca.pem   # export the CA certificate
```

## Read the capture

```bash
rea http events                          # list exchanges (aliases: log, ls)
rea http events -g "login|token" -n 50   # client-side regex filter, more rows
rea http events -f "status>=400 method=POST"   # HTTP Toolkit filter expression
rea http show <id>                       # headers, status, timing (8-char id prefix is enough)
rea http body <id>                       # response body (--request for the request; -o file for big ones)
rea http watch                           # explicit form of bare `rea http`
rea http clear                           # clear captured events
```

## Free-tier quirk (important)

`rea http call <operation>` and generic ops default their API source. **On the free tier, use
`--source mcp`, not `ctl`** — `httptoolkit-ctl` operations require Pro. The `events`/`show`/`body`
readers already use the working path.

## Workflow

1. `rea http` — just start listening; the proxy, CA and device wiring are assumed done.
2. Drive the app to produce traffic (skill `device-control`).
3. `rea http events` to find the exchange, `show`/`body` to read it.
4. Correlate: take a header/param name and `grep_search` it in `jadx_src/` to find the code that
   built it — that is the finding, not the packet.

## Pinning

If HTTPS traffic doesn't appear, the app likely pins certificates. Report pinning as a finding
and reach for an unpinning hook (Frida) rather than fighting the proxy.

Full reference: `docs/http_toolkit.md`.
