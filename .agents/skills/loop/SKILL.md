---
name: loop
description: Durable goal loop for long-running analysis — decompose a request into evidence-bound goals, record progress in an append-only ledger, and survive context loss or compaction without re-planning. Use when the user asks for a loop, durable or checkpointed execution, evidence-led work, or when a reversing task is large enough that losing your place would be expensive.
metadata:
  short-description: Evidence-bound goal loop with an append-only ledger
---

# loop

State lives under `.agents/state/loop/<session>/`. Drive it with `run_command`:

```bash
python .agents/scripts/loop.py <subcommand> [flags]
```

Two files per session. **`ledger.jsonl` is append-only and authoritative.** `goals.json` is only
a cache of it — never hand-edit either. If they ever disagree, the ledger wins and `reconstruct`
repairs the cache.

The CLI fails loud: non-zero exit and a reason on stderr. Read the error, fix the input, retry.
Do not work around it by writing state files yourself.

## After any context loss, do this first

```bash
python .agents/scripts/loop.py status --json
```

Then resume from what it reports. **Never re-plan from scratch and never redo a goal already
marked complete** — the ledger already holds the evidence.

## 1. Register goals, before any artifact

```bash
python .agents/scripts/loop.py create-goals \
  --brief "<the user's request, verbatim>" \
  --goals-json goals.json --json
```

The goal set is the binding contract for the run, so its quality caps the run's quality. In
reverse engineering a good goal names the **finding** and how it will be **proven**, not the
activity. The CLI rejects goals below the bar — see "The quality bar".

Goal shape (a reversing example):

```json
[
  {
    "id": "g1",
    "objective": "The X-Sign request header is a known, reproducible function of the request.",
    "deliverables": ["findings/x-sign.md", "scripts/reproduce_xsign.py"],
    "criteria": [
      {
        "id": "c1",
        "pass_condition": "the builder of X-Sign is located in the decompilation",
        "scenario": "grep -rn 'X-Sign' workspaces/com.target.app/jadx_src",
        "expected_evidence": "file:line of the header assembly, cited in findings/x-sign.md"
      },
      {
        "id": "c2",
        "pass_condition": "the recomputed signature equals the captured header, exit code 0",
        "scenario": "python scripts/reproduce_xsign.py --from-capture <event-id>",
        "expected_evidence": "exit code 0 and 'MATCH' printed, recorded in the checkpoint"
      }
    ],
    "constraints": ["assumed: v2 API only — reversible", "do not repackage the app"],
    "stop_when": "the reproduction script matches a captured request"
  }
]
```

One goal per outcome. Two independent findings → two goals, not one compound objective.

`create-goals` refuses to overwrite an existing goal set. For unrelated new work use `--session
<new-id>`; use `--force` only when you deliberately mean to discard recorded evidence.

## The quality bar

Enforced mechanically — a rejected goal is a real defect, not a formatting complaint:

| Rule | Why |
| :--- | :--- |
| The objective states an **outcome/finding**, not an activity | "Look at the .so" cannot fail, so it cannot finish. State what will be TRUE ("the signer is identified and reproduced"). |
| Every goal has `stop_when` | Without it the run spelunks past done. |
| Every goal has at least one criterion | A goal with no criterion measures nothing. |
| Each criterion has a **binary** `pass_condition` | "understand the crypto" is rejected. "exit code 0", "recomputed == captured", "grep finds the symbol" pass. |
| Each criterion names its `scenario` | The literal `rea`/grep/hook command that proves it — decided now. |
| Each criterion names its `expected_evidence` | Written at registration. Evidence invented after the work bends the contract to fit whatever happened. |

Record unstated bounds you chose in `constraints` as `assumed: <bound> — <rationale>,
<reversible?>`. Ask the user only when the missing detail is genuinely theirs (an irreversible
action like repackaging/installing, a real budget).

## 2. Work a goal, then checkpoint it

```bash
python .agents/scripts/loop.py checkpoint --goal-id g1 --status in_progress --json
```

Then, once you have actually run the scenario:

```bash
python .agents/scripts/loop.py checkpoint --goal-id g1 --status complete \
  --evidence "builder at Signer.java:88; reproduce_xsign matched event 41 (MATCH)" \
  --command "python scripts/reproduce_xsign.py --from-capture 41" --exit-code 0 \
  --evidence-path "findings/x-sign.md" --json
```

`--evidence` is **required** for any status other than `in_progress`. Record what you observed,
not what you expect. `--command` and `--exit-code` make a checkpoint auditable later without
re-running the work — which is why the stop-verifier can trust it.

Use `--status failed` when the scenario ran and did not pass, `inconclusive` when you could not
run it at all (packing/pinning you couldn't defeat). Both are useful; a silent gap is not.

## 3. Steer when the plan changes — on the record

```bash
python .agents/scripts/loop.py steer --kind add-goal  --goals-json new.json --rationale "..." --json
python .agents/scripts/loop.py steer --kind drop-goal --goal-id g3 --rationale "descoped" --json
python .agents/scripts/loop.py steer --kind revise    --goal-id g1 \
  --patch-json '{"stop_when": "reproduction matches AND session refresh mapped"}' \
  --rationale "token lifecycle was part of the ask" --json
python .agents/scripts/loop.py steer --kind note \
  --rationale "signer is native (libcore.so getK); handing to native-analyst" --json
```

`--rationale` is required. Future-you reading the ledger after compaction is the reviewer.

## 4. Verify the ledger is sufficient

```bash
python .agents/scripts/loop.py reconstruct --check --json
```

Exits non-zero if `goals.json` disagrees with the ledger. Run it before reporting completion.

## Stop rules

- **All goals complete** (`all_complete: true`) → deliver and stop. Don't keep digging.
- **A goal's `stop_when` holds** → that goal is done. Note further findings; don't chase them.
- **Three consecutive failed checkpoints on one goal** → stop, checkpoint `failed` with what you
  tried and where the real blocker is, and surface it.
- **You cannot run a criterion's scenario** → checkpoint `inconclusive` and say why.

A reproduced value or a live trace is completion proof; a decompiled routine that merely *looks*
right is not. Audit every criterion against the evidence actually recorded before reporting done.

## If you are resumed after trying to stop

A `Stop` hook (`.agents/hooks/stop_verifier.py`) holds the session open while a registered loop
still has work, and injects a system message naming the active goal. It fires only for a loop
**you** registered. It rejects a `complete` checkpoint on a recorded non-zero exit code or a
missing `--evidence-path`, and marks the loop stuck if a resume adds no new ledger entry. The way
out is never to argue with it: finish the goal, or close it out honestly with `failed` /
`inconclusive`. Resumes are capped (2 per goal, 1 after compaction, 6 per session).
