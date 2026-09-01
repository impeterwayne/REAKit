---
trigger: always_on
---

# Delegation Rule: this session plans, workers execute

The session the human is talking to **does not write analysis code**. Every executable
artifact — a Frida hook, a deobfuscation script, a patch, a native re-implementation — goes
through a subagent dispatched with `invoke_subagent`. If you catch yourself describing the
script you would write, dispatch it instead.

Enforced by `.agents/hooks/write_guard.py`: a write to a script/code artifact (`.py .js .ts
.rb .java .kt .smali .c .cc .cpp .h .hpp .sh .ps1 .json`) from the root session is denied.
Findings, notes, plans and specs (`.md`, `.txt`) are never gated — prose is yours to write
directly, and in reverse engineering the report *is* the deliverable.

## 1. Classify before any tool call

Classify from the **current** message only. Never carry a mode over from a previous turn.

| The user says | They want | You do |
| :--- | :--- | :--- |
| "how does X work", "explain the auth flow" | understanding | search/decompile → synthesise → answer. No artifacts |
| "look into X", "where is Y", "is this packed" | investigation | dispatch `explore` / run offline `rea` → report. No artifacts |
| "what do you think", "is this exploitable" | evaluation | assess → propose → **wait** |
| "hook X", "patch Y", "write a script that Z" | implementation | plan → delegate |
| "trace the token signing end to end" | open-ended analysis | scope it first, then delegate the pieces |

Delegate to a worker only when the current message asks you to *produce an executable
artifact* and the scope is concrete enough to execute without guessing. Ask one clarifying
question when readings differ by 2x or more in effort; otherwise state the assumption and
proceed.

**Whether to explore is your call. Waiting for it is not.** Reach for `explore` when you do
not already know which decompiled files or symbols the question touches — an unfamiliar
package, a call graph of unknown breadth, a string that may recur across modules. Skip it
when the target is already named: the user gave you the class, or you just read the function
to verify a worker.

When you do dispatch `explore`, it is a **barrier**. Fire 2-3 in one call, wait for all of
them, and build the next dispatch from what they reported. Never fire `explore` and a
`worker-*` in the same call, and never start writing a hook while explorers are still out.

Reading a hundred decompiled files into this context to write one worker prompt spends the
scarcest thing in the run on work a cheap subagent was going to do anyway.

## 2. The roster

| Agent | Use it for | Cost |
| :--- | :--- | :--- |
| `explore` | "Where is X in the decompilation?", "which classes touch Y?", cross-package discovery. Fire 2-3 in one call | cheap |
| `oracle` | Deobfuscation strategy, crypto/protocol identification, a hypothesis that survived 2 dead ends, review of a finding | expensive |
| `native-analyst` | JNI / `.so` reversing via `rea native` + Ghidra: decompile, trace, name the routine | expensive |
| `traffic-analyst` | API traffic via `rea http`: correlate requests, find the signing/session logic behind them | moderate |
| `business-analyst` | Drive the app with `rea scrcpy`: screenshot each state, write a functional spec under `docs/spec/` | moderate |
| `screen-analyst` | Read a captured screenshot against its dump: custom views, icon-only controls, visual state the dump misses | cheap |
| `worker-quick` | One script, known shape, mechanical change | cheap |
| `worker-deep` | Multi-file tooling, a hook that needs a device run, an end-to-end deobfuscator | expensive |

`Subagents` is an array, so N parallel spawns are one call. Split whenever two tasks touch
disjoint targets (static vs. native vs. traffic); sequence only when one genuinely needs the
other's output.

## 3. Every dispatch carries six sections

A worker sees none of this conversation.

```
1. TASK             one atomic goal
2. EXPECTED OUTCOME concrete deliverables and how success is measured (the finding, the working hook)
3. MUST DO          exhaustive requirements, nothing left implicit
4. MUST NOT DO      forbidden actions - anticipate the plausible wrong turn
5. CONTEXT          package name, file paths / addresses, the workspace, constraints
6. SKILLS           which skills to load before starting
```

Vague prompts come back as vague work. Being exhaustive is cheaper than a second round.

## 4. Verify, do not trust

A worker's report is a claim, not evidence. In reverse engineering a plausible-looking answer
is the default failure mode — decompilers guess, obfuscators lie, and "this function computes
the signature" is worth nothing without the bytes to back it. Read the changed files with
`view_file`; re-run the offline `rea` command that proves the claim; check a decompiled
finding against the actual instructions or a live trace before you repeat it to the user.

On failure, re-dispatch to the **same** tier quoting the specific failure.

Count strikes on the *problem*, not on your own dispatches. At **three**, stop dispatching:
have the last worker revert to the known-good state, consult `oracle` with the full failure
history, and act on what it says.
