---
name: trident
description: Wrap a working session in a three-prong quality harness — a Do-er (Opus) watched by Simba (durable intent memory + drift detector) and an Auditor (Fable; deterministic evaluators first, LLM-judge second), over one failures-log SSOT. Trigger on "invoke trident", "run trident", "audit this work"; and — always — owns the normalized "log failure" trigger that appends the next CF-### to the SSOT. Claude Code / VS Code only (spawns real subagents).
---

# trident — the orchestrator

> The reusable method (tightly-scoped loops · adversarial agents · incentive alignment) + the scored
> generate→re-rank primitive: `../references/method.md`.
> Cross-cutting rules live in `../references/house-rules.md` — change them there, never here.
> No-leak isolation: `../references/loop-contract.md`. Eval shapes: `../references/phoenix-protocol.md`.

## Conceptual loop
0. **Phase 0 — riskiest-assumption gate (before ANY build).** Simba → `IntentCard`; Do-er → `AssumptionSet`;
   Auditor → `RATVerdict` (riskiest by kill-power × uncertainty + cheapest probe); Do-er runs the probe.
   **Hard block: no build until it passes.** On fail → stop, report, `log failure`.
1. **Build** — Do-er works only past the gate → `Output` + `Spans`.
2. **Audit** — Simba drift-checks the `Output`; Auditor runs detectors → `Verdict` (deterministic → structural → judge).
3. **Correct** — on fail, return the *specific* failing detector to the Do-er; bounded retries (max 3).
4. **Close** — on pass, surface to the user; on a NEW failure mode, `log failure`.

## Runbook — what to do when the user says `invoke trident`
**You (this session) are the orchestrator.** You hold no prong's private context; you only pass the
typed artifacts between subagents. Subagents can't spawn subagents, so never wrap the whole harness in
one subagent — orchestrate from here. Keep a todolist of the phases below.

Models: **Simba** = default (cheap, focused) · **Do-er** = Opus · **Auditor** = Fable (never the Do-er's model).

**Phase 0 — RAT gate**
1. Spawn **Simba** (`agentType` per `../simba/SKILL.md`): input = the user's problem + *their* messages only.
   → returns `IntentCard` {goal, must_haves, forbid, pinned_feedback, intent_riskiest}.
2. Spawn **Do-er** (Opus): input = the task. → returns `AssumptionSet` — every capability/platform/feasibility
   assumption, each tagged {type, kill_power 1–5, uncertainty 1–5}. **It does not build yet.**
3. Spawn **Auditor** (Fable): input = `AssumptionSet` + `IntentCard`. → returns `RATVerdict`
   {riskiest (max kill_power × uncertainty), probe (the smallest command/read that could prove it impossible), pass_criteria}.
4. Run the probe (directly, or a scoped Do-er). Evaluate against `pass_criteria`.
5. **GATE:** fail → **STOP**, report to the user, `log failure`. pass → continue. *(Never skip this.)*

**Phase 1 — Build**
6. Spawn **Do-er** (Opus): input = task + `IntentCard` (honor must_haves / forbid / pinned_feedback).
   → returns `Output` (the diff/result) + `Spans` (short trace; mark ⊘ root / ⚠ error).

**Phase 2 — Audit**
7. Spawn **Simba**: input = `Output` + `IntentCard` (Output only — never the Do-er's reasoning).
   → returns `DriftFlag` {drifted_from, evidence} or "no drift".
8. Spawn **Auditor** (Fable): input = `Output`, `Spans`, `DriftFlag`, and the active detectors from
   `failures/failures.jsonl`. Order: deterministic → structural → (only if needed) rubric-judge; **fail closed**.
   → returns `Verdict` [{detector_id, pass|fail, signal_seen}].

**Phase 3 — Correct (max 3 rounds)**
9. If `Verdict` has fails → spawn a fresh **Do-er** with the *specific* failing detector(s) to fix; re-run Phase 2.
   Repeat ≤3. On exhaustion → surface the open `Verdict` to the user; never loop silently (FL-cf016).

**Phase 4 — Close**
10. On pass → surface `Output` to the user. If a NEW failure mode appeared that no CF covers → `log failure`.

## Trigger: `log failure` (and variants) — the SSOT owner
Normalize to intent (FL-cf026): `log failure` = `log fail` = `log this failure` = `log the fail` = `record failure`.
1. Locate the SSOT `failures/failures.jsonl` in the **Trident repo**. If it's not in session scope, say so
   in one line and stop — don't write a divergent copy (FL-cf034).
2. Read the **last line only** for max `CF-###`; next id = max + 1 (never full-read, never reuse).
3. Append one **sanitized** record (schema: `failures/schema.json`). Personal specifics go to
   `failures.local.jsonl` (gitignored), never the committed line (FL-cf013, FL-cf052).
4. **Auditor approves** the record (schema-valid, detector deterministic-where-possible, no personal data).
5. `python3 tests/selftest.py` must pass, then commit + push the SSOT to the Trident repo.
6. Confirm back: `logged CF-### (<title>)` — a silent skip is impossible (FL-cf046).

## Surface
Claude Code / VS Code only — the loop spawns real subagents (Do-er, Fable Auditor, Simba). With this
repo in scope, `log failure` appends → Auditor-approves → commits + pushes the SSOT. Never claim a write
happened if it didn't (FL-cf046).

## Hard guardrails (do not break)
- No build, no deps — installs as a plain skills tree; orchestration uses subagents (Claude Code / VS Code).
- No personal data or external paths in any committed record — re-scan before commit.
- Deterministic detectors before any LLM-judge (FL-cf051). The judge (Fable) is never the Do-er (Opus).
- Phase 0 is a hard gate — no build before the riskiest-assumption probe passes (FL-cf056).
