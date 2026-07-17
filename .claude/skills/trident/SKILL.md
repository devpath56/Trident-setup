---
name: trident
description: Wrap a working session in a three-prong quality harness — a Do-er (Opus) watched by Simba (guards user intent) and an Auditor (Fable; deterministic evaluators first, LLM-judge second), all reading/writing one failures-log SSOT. Trigger on "run trident", "audit this work", "watch my intent on this", and — always — owns the normalized `log failure` trigger that appends the next CF-### to the SSOT. SKELETON — contract only; logic filled in after design approval.
---

# trident — the orchestrator (SKELETON)

> This file states the loop and the triggers. Deep prose/logic is intentionally deferred until
> `ARCHITECTURE.md` is approved. Cross-cutting rules live in `../references/house-rules.md` — change
> them there, never here.

## The loop (see `../references/loop-contract.md` for the no-leak isolation contract)
0. **Phase 0 — riskiest-assumption gate (before ANY build).** Simba → `IntentCard` (incl. the
   intent-riskiest assumption); Do-er → `AssumptionSet` (all capability/platform assumptions enumerated);
   Auditor → `RATVerdict` (the single riskiest by kill-power × uncertainty + the cheapest falsifying probe);
   Do-er runs the probe. **Hard block: no build until it passes.** On fail → stop, report, `log failure`.
1. Spin up **Simba** (`../simba/SKILL.md`) → `IntentCard` from the user's messages only.
2. Let the **Do-er** work (only past the Phase-0 gate); capture its `Spans` (`../references/phoenix-protocol.md`).
3. Spin up the **Auditor** (`../auditor/SKILL.md`) → `Verdict` (deterministic → structural → judge).
4. On fail: return the specific failing detector(s) to the Do-er; bounded retries.
   On Simba intent-drift flag: inject the IntentCard delta into the Auditor's next pass.
5. On pass: surface to the user. On a NEW failure mode: `log failure` (below), Auditor approves, user sees it.

Each prong keeps its **own todolist and isolated context**. Only the typed artifacts cross a boundary.

## Trigger: `log failure` (and variants) — the SSOT owner
Normalize to intent (per FL-cf026): `log failure` = `log fail` = `log this failure` = `log the fail` = `record failure`.
On any of these:
1. Locate the SSOT: `failures/failures.jsonl` in the **Trident repo**. If the Trident repo is not in
   session scope, say so in one line and stop — do not write a divergent copy (FL-cf034: don't fake a guard).
2. Read the **last line only** to get max `CF-###`; next id = max + 1 (never full-read, never reuse — FL-cf-numbering).
3. Append one sanitized record (schema: `failures/schema.json`). Personal specifics (names, paths) go
   to `failures.local.jsonl` (gitignored), never to the committed line (FL-cf013 blast-radius, FL-cf052 fidelity).
4. Auditor approves the record (well-formed, deterministic-detector-first) before it is surfaced.
5. Commit + push the SSOT to the Trident repo (git-tracked SSOT, same discipline as this kit's `progress.json`).
6. Confirm back to the user: `logged CF-### (<title>)` — so a silent skip is impossible (FL-cf046).

## Surface
Claude Code / VS Code only — the loop spawns real subagents (Do-er, Fable Auditor, Simba). With this
repo in scope, `log failure` appends → Auditor-approves → commits + pushes the SSOT git file. Never
claim a write happened if it didn't (FL-cf046).

## Hard guardrails (do not break)
- No build, no deps — installs as a plain skills tree; orchestration uses subagents (Claude Code / VS Code).
- No personal data or external paths in any committed record — re-scan before commit.
- Deterministic detectors before any LLM-judge (FL-cf051). The judge (Fable) is never the Do-er (Opus).
