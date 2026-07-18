# The Trident Experiment Method — how to prove a claim before shipping it

Evolved from every experiment in `experiments/` (the v1 Trident-vs-Opus A/B, the people-first re-runs
RESULT-01/02/04, and the context-contract run RESULT-05). Each of the ten rules below exists because a real
run needed it. Use this whenever a proposal must be *proven*, not asserted — a new guard, a design change, a
"this is faster/better" claim.

## The protocol (in order)

1. **Pre-register, then commit — before running.** Write the hypothesis, the metrics, and the numeric PASS
   criteria, and commit that file *first*. The bar cannot move after you see results. (RESULT-05 failed P1 at
   31% vs a pre-registered 40%; because the bar was locked, that's an honest FAIL, not a fudged pass.)

2. **Make the key claim a runnable assertion.** The thing that must be true should be an executed test, not a
   judgment. Execute behavior; never grep the artifact for a keyword (CF-014). "Intent survived" became
   `parse_config("__proto__: 1")` raises — pass/fail, no opinion.

3. **Change exactly one variable.** Arms differ only in the thing under test; same task, same Do-er model,
   same instructions, a **shared seed** for any common starting point. Anything else that differs is a
   confound that invalidates the result.

4. **Steelman the baseline.** Give the control every advantage (full context, best effort). A win over a
   strong baseline means something; a win over a crippled one means nothing.

5. **Prime the design against `failures.jsonl` first.** Before running, list the CF modes that could wreck
   *this experiment* and neutralize each — the Auditor's anticipate-failures step aimed at your own method.
   The recurring offenders: CF-010 (self-scoring optimism), CF-014 (grep vs execute), CF-021 (winning one
   axis while another rots), CF-051 (use the deterministic check), CF-037/046 (don't narrate unexecuted
   results), CF-056 (probe feasibility first), CF-004 (no invented numbers).

6. **Deterministic metrics first; LLM-judge only for the rest.** Counts, tests, and greps beat a rubric-judge
   (CF-051). Reserve the judge for what can't be executed, and even then anchor it to a rubric, never
   free-form (CF-010).

7. **Feasibility probe before the full run (Phase 0).** Spend minutes proving the run is even measurable
   (can a Do-er's output be extracted and executed here?) before spending the whole budget (CF-056). Round 1
   often doubles as this probe.

8. **Certify with an independent, fail-closed auditor.** A *different model* (Sonnet 5, never the Opus Do-er)
   scores each criterion and the conjunction, and fails closed on anything unproven. It also guards honesty:
   in RESULT-05 the auditor refused to let an un-pre-registered bonus finding or a different (R3-alone)
   metric upgrade the verdict.

9. **State n and separate luck from guarantee.** Say how many trials ran. With n=1, a single good outcome is
   an observation, not proof — distinguish "true by construction" (a deterministic gate that always fires)
   from "happened once." Report every caveat the result rests on (proxy metrics, shared seed, sample size).

10. **Report the honest verdict, even a FAIL — done means verified.** A pre-registered FAIL is a *successful*
    experiment: it tells you the truth and where the claim would hold (the crossover). Don't move goalposts;
    record what to run next. The experiment is done when criteria are scored against real measurements, not
    when the turn ends (CF-025).

## The standard shape
- **A/B, N rounds.** Arm A = baseline, Arm B = the change. Fresh subagent per round so the orchestrator
  controls exactly what crosses each boundary (no-leak; see `loop-contract.md`).
- **Scored via the generate → re-rank loop** (`method.md`) when ranking candidates: delta re-score only the
  new/changed, keep a roads-not-taken ledger, stop at target+stall or a round cap.
- **Success rubric (Trident's):** a validity gate first, then the primary metric, then a tiebreak — e.g.
  *fewer user prompts + faster* (primary) → *quality-per-token* (tiebreak), with a blind,
  deterministic-anchored judge. Pick the arm only after the validity gate passes.

## Template
Copy `experiments/EXP-context-contract.md` as the pre-registration shape (claim · falsifiability · fixture ·
arms · metrics · pre-registered PASS table · anticipated-failures primer), and `RESULT-05-context-contract.md`
as the verdict shape (auditor-certified scorecard · what happened · honest caveats · decision faithful to the
pre-registration).
