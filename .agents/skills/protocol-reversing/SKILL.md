---
name: protocol-reversing
description: Method for reverse-engineering an app's API/network protocol — request signing, session/token flows, custom encodings (protobuf, msgpack, encrypted bodies), and mapping each on-wire field back to the code that produces it. Use when the goal is to understand or reproduce how the app talks to its backend. Pairs with the traffic-capture tool skill.
---

# Reversing an app's protocol

The deliverable is not the captured packet — it is *how the app builds each field*, backed well
enough that you could reproduce or verify it. Work from both ends: the wire and the code.

## 1. Capture a clean example

Drive one representative flow (login, a signed API call) and capture it (skill `traffic-capture`):
`rea http events` → `rea http show <id>` → `rea http body <id>`. Note the distinctive fields:
auth headers (`Authorization`, `X-Sign`, `X-Token`), anti-replay (`ts`, `nonce`, `seq`), and the
body encoding.

## 2. Classify the body

- **JSON / form** — read it directly.
- **Protobuf / gRPC** — binary with field tags; no schema on the wire. Recover the schema from
  the decompiled `*.proto`-generated classes in `jadx_src/` (message classes, field numbers).
- **Encrypted / packed body** — a base64/hex blob that isn't JSON. The app encrypts before send;
  find that step in code (§3) or hook the pre-encryption call to read plaintext.

## 3. Trace each field back to code

For every field that isn't a plain value:

1. Grep the field/header name across `jadx_src/` (`grep_search "X-Sign"`).
2. Find the builder — the class assembling the request (often around `Retrofit`/`OkHttp`
   `Interceptor`, `addHeader`, `RequestBody`).
3. Follow what it hashes/signs/encrypts and **where the secret comes from**: a constant, the
   keystore, a prior response, the device, or `native` (hand off to `jni-reversing`).
4. Reconstruct the recipe: `X-Sign = HMAC_SHA256(key, canonical(ts + nonce + path + body))` — with
   the file:line for each part.

## 4. Confirm

Reproduce the field from a captured input and check it matches the captured output — a tiny script
that recomputes the signature over one real request and equals the observed header is proof.
Delegate the script (artifact) to a worker under `scripts/`; keep the captured vectors under
`findings/`.

## 5. Session & token lifecycle

Map the flow, not just one call: how a token is obtained, where it's stored (`rea pull` →
`runtime/`, shared-prefs/DB), how it's refreshed, and what invalidates it. Note anti-replay
windows (does the server reject a stale `ts`?) — they constrain any reproduction.

## Report

State the protocol as a recipe with evidence pointers per field, the confidence per field
(confirmed by reproduction vs. inferred), and the transport truths (TLS pinning, encoding). See
also skill `traffic-capture`, `docs/http_toolkit.md`.
