---
name: finding-review
description: >
  Audits a set of reverse-engineering findings before you rely on or report them — checking each
  claim against its evidence, hunting decompiler artifacts and unbacked inferences, and confirming
  the hard ones dynamically. Delegates re-verification to explore/native-analyst/traffic-analyst and
  judgement to oracle. Use when the user says "review the findings", "is this analysis right",
  "verify this before I report it", or asks whether a conclusion holds.
metadata:
  short-description: Delegated verification of RE findings, evidence first
---

# finding-review

You scope, synthesize, and verify. Re-checking and judgement are delegated — not because you
cannot read the evidence, but because a review that fits in one context is one that skimmed. Read
the findings and their pointers yourself before drawing any conclusion.

The cardinal RE failure is the confident, wrong claim. This skill exists to catch it before it
reaches the user. Reviewing does not authorize repackaging or patching the target.

## Phase 1 — Scope (delegate to `explore`, in parallel)

Fire 2-3 `explore` subagents in **one** `invoke_subagent` call:

1. **Evidence inventory** — for each finding, confirm the cited pointer exists and says what the
   finding claims (`jadx_src/.../F.java:88`, `libX.so @ 0xADDR`, `rea http show <id>`). Flag any
   claim with no pointer, or a pointer that doesn't support it.
2. **Cross-layer consistency** — where a finding rests on decompiled Java or Ghidra C, check the
   lower layer (smali / raw instructions) doesn't contradict it.
3. **Scope of the claim** — does "the app signs all requests" hold across the call sites, or was
   it seen once? Report the actual breadth.

Read the findings and their evidence with `view_file` before moving on.

## Phase 2 — Judgement (delegate to `oracle`)

Send `oracle` the findings plus Phase 1's results. Ask, in priority order:

- **Unbacked inference** — claims stated as fact that are actually guesses (decompiler-typed
  variables, "looks like HMAC" without the constants/imports, a string assumed to be a key).
- **Decompiler / obfuscation traps** — control-flow flattening misread as logic, an inlined
  helper mistaken for the whole routine, a red-herring string.
- **Reproduction gaps** — a signing/crypto claim that was never reproduced or hooked.

Split across parallel `oracle` calls when findings span static + native + protocol.

## Phase 3 — Dynamic confirmation (delegate to the specialist)

For each finding rated "inferred" or high-stakes, dispatch the matching specialist to close the
loop: `native-analyst` to hook/trace a JNI routine, `traffic-analyst` to reproduce a signature
over a captured request. Static + one live confirmation is the bar. A finding that cannot be
confirmed is downgraded, not dropped — say so.

## Phase 4 — Report

One report, ordered by how load-bearing each finding is. Per finding: the claim, its evidence
pointer, and a verdict — **confirmed** (bytes/trace back it), **plausible** (consistent, not
reproduced), or **refuted** (evidence contradicts it). Separate confirmed from plausible clearly.

Say plainly when the analysis holds up. Inventing doubt to look rigorous is as much a failure as
rubber-stamping — call it as you find it.

## Phase 5 — Corrections, only if asked

If the user asks for fixes to the analysis: mechanical ones (correct a pointer, restate a
confidence) you do directly in the `findings/` notes. A re-analysis (the routine does something
else) → dispatch `worker-deep` or the specialist with the specific gap, then re-verify their
result — a subagent's summary is a claim, not evidence.
