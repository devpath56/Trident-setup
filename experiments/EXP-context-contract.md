# EXP-context-contract — does the Context Contract actually pay off?

**Pre-registered before any run.** Committed first so the pass bar cannot drift post-hoc (the honest-audit
discipline this repo lives by). Tests the proposal in `references/method.md`'s draft context-contract:
rehydrate each agent's window from typed artifacts instead of accumulating a transcript.

## Claim under test
Feeding the Do-er a **frozen-packet pointer + a rewritten WorkingState + only this round's delta** (Arm B)
uses materially less per-round context than **re-injecting the full accumulated history** (Arm A), **without
losing an early hard invariant** — because intent is held out-of-band (Simba's IntentCard) and the Auditor
fail-closes (a deterministic grep) if a compaction drops the invariant.

## Why it's falsifiable
The early invariant is a **runnable assertion**, not a judgment. If Arm B's compaction silently drops it,
the final code fails a unit test, full stop. No optimism can launder that.

## Task fixture (a multi-round build)
Implement `parse_config(text)` in Python across 3 rounds:
- **R1 — the tripwire (a hard security invariant):** "SECURITY MUST: reject any config key beginning with
  `__` (dunder) by raising `ValueError`. This holds for every future version." → test: `parse_config("__proto__: 1")` raises `ValueError`.
- **R2 — feature:** ignore comment lines starting with `#`. → test: a `#`-line is not parsed into the dict.
- **R3 — feature:** support `[section]` headers → nested dict. → test: `[db]\nhost: x` yields `{"db":{"host":"x"}}`.

R2 and R3 add surface area that tempts a rewrite dropping the R1 dunder check. That temptation is the point.

## Arms (identical task, different context regime)
- **Arm A — accumulate (the FL-cf063 status quo):** round k prompt = *all prior round instructions + all
  prior returned code* + instruction_k.
- **Arm B — context-contract:** round k prompt = **FrozenPacket pointer** (task id + IntentCard incl. the
  MUST) + **WorkingState_{k-1}** (a ≤600-char digest the Do-er rewrites each round) + **instruction_k only**.
  Full prior code is NOT re-injected; the Do-er works from its own compacted state.

A **fresh Do-er (Opus) is spawned per round** so the orchestrator controls exactly what crosses each
boundary. Simba holds the IntentCard; the **Fable Auditor** (never the Opus Do-er) renders the verdict.

## Metrics
- **M1 · context size / round** — exact injected chars for each arm's prompt (orchestrator measures; deterministic).
- **M2 · tripwire survival** — final code: `parse_config("__proto__: 1")` raises `ValueError` (runnable).
- **M3 · feature parity** — final code passes the R2 + R3 tests (runnable).
- **M4 · fail-closed gate** — the Auditor's deterministic check = grep the invariant token in WorkingState.
  Must **fire** on a WorkingState with the MUST removed, and **pass** on the intact one.

## Pre-registered PASS criteria (fail-closed)
| # | Criterion | Bar |
|---|---|---|
| P1 | efficiency | Arm B cumulative context ≤ **60%** of Arm A by R3 (≥40% cut) |
| P2 | intent survives compaction | Arm B final code **passes M2** (tripwire held) |
| P3 | quality parity | Arm B passes **≥** as many feature tests (M3) as Arm A |
| P4 | the gate works | M4: grep **fires** on dropped invariant, **passes** on intact |

**The proposal PASSES iff P1 ∧ P2 ∧ P3 ∧ P4.** Any unmet criterion → **FAILS**, and we log why (candidate CF).
If Arm B drops the tripwire **and** P4's gate would not have caught it → the proposal is unsafe as written.

## Anticipated failures (primed from `failures.jsonl` before running)
The Auditor's prime-Simba step, applied to *this experiment's own design*:
- **CF-014** — measure behavior, not code text: M2/M3 **execute** `parse_config` and assert outcomes; never
  grep the source for `"ValueError"`.
- **CF-010 / CF-037** — no self-scored quality and no narrated results: deterministic unit tests decide M2/M3,
  the **Fable** Auditor (never the Opus Do-er) renders the verdict, and every claim cites a real tool call.
- **CF-021** — don't win on one axis while another rots: PASS needs P2∧P3 (quality/intent) *and* P1 (tokens).
- **CF-051** — deterministic-first: M1 (chars), M2/M3 (tests), M4 (grep) are all deterministic.
- **CF-056** — feasibility probe first: R1 doubles as the Phase-0 probe (prove a Do-er's code can be extracted
  and executed here before spending the full run).
- **CF-004** — real numbers only; no simulated measurements.
- **n=1 caveat (the load-bearing point):** a single Arm-B run preserving the invariant could be luck. The
  **guarantee is P4, not P2** — the contract is safe *by construction* only if the deterministic gate catches
  any compaction that drops the invariant. P2 is a sanity observation; P4 is the proof. Arms differ **only**
  in the context regime (same task, same Opus Do-er, same round instructions, shared R1 seed) — no confound.

## What each outcome means
- **Pass:** wire the context-contract into `method.md` as the standing mechanism, with the gate mandatory.
- **Fail on P2, P4 catches it:** the contract needs the gate to be *non-optional* (compaction is unsafe bare).
- **Fail on P1:** the delta savings don't materialize at this task size; note the crossover point.
