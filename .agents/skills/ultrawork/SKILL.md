---
name: ultrawork
description: >
  Maximum-rigour mode for a reverse-engineering request that must not come back wrong: classify the
  intent before acting, register the run as goals with evidence, delegate discovery and judgement
  instead of doing everything in one context, and prove each finding with a re-runnable `rea` command
  or a dynamic confirmation. Activates on "ultrawork", "ultra work", "ulw", or when the user asks for
  maximum rigour, "do this properly", "no shortcuts", "be thorough and verify". Use for end-to-end
  traces, deobfuscation, protocol reversing, and anything where a plausible-looking wrong answer is
  expensive. Do NOT use it for a one-line lookup — the overhead would be the whole cost.
metadata:
  short-description: Rigour mode — classify, register goals, delegate, prove
---

# ultrawork

Open your reply with `ultrawork:` and one line naming what you are about to do. That line is the
activation receipt — without it, nobody can tell this mode engaged.

This mode changes **how carefully** you work. It does not change **how much** you analyse —
scope stays whatever the request asked for. Rigour and minimalism are not in tension: the failure
being prevented here is confident wrongness, the cardinal RE sin, not a small analysis.

## 1. Classify the intent, before any tool call

State the classification in one line: **understanding | investigation | evaluation | implementation**.

| The user said | It is not a request to produce an artifact |
| :--- | :--- |
| "explain how X works", "how does the signing work" | understanding → explain with evidence → stop |
| "look into this", "is this packed", "where is Y" | investigation → report → stop |
| "is this exploitable", "what do you think of" | evaluation → recommend → stop |
| "hook X", "patch Y", "write a script that Z" | implementation → build it, verify it |

The failure this exists to stop is reading a question and starting to write a Frida script. Only
an explicit ask to build, hook, patch, or script authorises an executable artifact. When a request
carries two intents ("explain the protocol and reproduce the signature"), name both, do them in order.

## 2. Register the run before the first artifact

Implementation and multi-step analysis go through the [`loop`](../loop/SKILL.md) skill:

```bash
python .agents/scripts/loop.py create-goals --brief "<the request, verbatim>" \
  --goals-json goals.json --json
```

This is the run's contract, and three things depend on it:

- The goal quality bar is **enforced** — activity-only objectives ("look at the .so"), unfalsifiable
  pass conditions, and criteria without `expected_evidence` are rejected at registration. A good goal
  names the *finding* and how it will be proven.
- The ledger is your durable memory. After a compaction, `loop.py status --json` is the first thing
  you run, and you resume from what it reports.
- The `Stop` gate (`.agents/hooks/stop_verifier.py`) holds the session open until the goals hold and
  rejects a `complete` checkpoint sitting on a non-zero recorded exit code or a missing artifact.

Every criterion names its scenario — the literal `rea` command or hook — and its expected evidence,
decided **now**. Criteria invented afterwards bend to fit whatever happened.

## 3. Delegate discovery and judgement

Your context window is the scarcest thing in the run. Spend it on decisions, not on decompiled files
you could have had summarised.

| Need | Call |
| :--- | :--- |
| Where is X in the decompilation, which classes touch Y | `explore` — fan out 2–3 in **one** `invoke_subagent` call |
| JNI / `.so` decompilation and tracing | `native-analyst` |
| API traffic, correlate a request to its builder | `traffic-analyst` |
| Establish which screens/actions exist, spec an on-screen flow | `ba` |
| Deobfuscation strategy, crypto/protocol ID, review of a finding, a dead end after 2 tries | `oracle` (read-only) |
| One mechanical script/patch | `worker-quick` (no shell) |
| A hook that needs a device run, an end-to-end deobfuscator | `worker-deep` |

`Subagents` is an array — N independent questions are one call. Give a worker the goal, the
constraints, and the paths/addresses; never a numbered plan. Then verify its result yourself: a
subagent's summary is a claim, not evidence.

## 4. Prove it — evidence, not assertion

Nothing is done without an artifact that would have caught the mistake:

- Reproduce the finding with the offline command that backs it: `rea native decompile <fn>`, `rea
  native info`, `rea http show <id>` / `body <id>` — and quote the relevant output.
- Confirm the hard claims **dynamically**: a Frida hook logging a JNI method's args/return, a
  reproduced signature that equals the captured header. Static + one live confirmation is the bar.
- A decompiled routine that *looks like* HMAC is not proof it is — match the constants/imports, or hook it.
- Record each: `loop.py checkpoint --goal-id gN --status complete --evidence "..." --command "..." --exit-code 0`

Pre-existing anti-analysis (packing, pinning) you couldn't defeat is not a failure to hide — record
it `inconclusive` with what you tried.

**Never** report a decompiler guess as fact, claim a hook fires without a logged value, or repackage
the target unless the user asked.

## 5. Before you claim done

Any "no" is unfinished work, not a caveat:

1. Does every finding I registered have a re-runnable command or a logged capture recorded in **this** run?
2. Did I read the actual output of every command, or skim it?
3. Is every "the app does X" backed by bytes or a trace, not just decompiled appearance?
4. Is every part of the request answered — re-read the original now?
5. Did I classify the intent at the start, and does what I did match it?
6. Is any finding a guess dressed as a conclusion?

Then run `loop.py reconstruct --check --json`: it proves the record survives losing its cache.

## Completeness, not maximalism

Deliver the **requested scope, finished and verified** — a working hook, not a sketch; a protocol
reproduced, not "looks like HMAC". "Proof of concept" is not acceptable when a working artifact was
asked for. That is a bar on *finishing*, not a licence to analyse more of the app than the question
needs. Being asked for rigour is not permission to widen scope; name out-of-scope findings at the
end, don't chase them.

## Stop rules

- **All registered goals complete, evidence recorded** → report and stop. Don't keep spelunking.
- **A goal's `stop_when` holds** → that goal is done. Note improvements, leave them.
- **Three consecutive failed attempts at the same problem** → stop, checkpoint `failed` with what each
  attempt produced and where the real blocker is (packing, anti-hook, decompiler artifact), and surface it.
- **A criterion you cannot run** → checkpoint `inconclusive` and say why. Never mark complete on a
  scenario you did not execute.

Work past the stop line is a defect, not diligence.
