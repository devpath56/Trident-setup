# House rules — the single source of truth for Trident's cross-cutting behavior (SKELETON)

Every skill (`trident`, `auditor`, `simba`) points here for shared rules. **Change a cross-cutting
rule here, not in each skill** (the anti-drift discipline — FL-cf001, FL-cf011).

## The invariants (each traces to a real failure)
0. **Riskiest assumption first (hard block).** No build of any kind starts until the single riskiest
   assumption — ranked by kill-power × uncertainty — is proven by the cheapest falsifying probe. The
   Auditor (Sonnet 5) owns the feasibility gate; Simba owns the intent gate; the Do-er runs the probe but
   never self-approves. On probe fail → stop, report, log a CF (FL-cf056, FL-cf044, FL-cf039).
   **Enforced:** the RAT is written by `prongs/rat.mjs` (refuses placeholder assumptions/probes) and
   `validate_prongs.py` HR-0 rejects any `probe` row with no `ratverdict` before it in the same run,
   so nothing is built before its RAT. Forward-only: probes predating rat.mjs are exempt.
1. **Deterministic first.** Any guard is enforced by the highest-reliability detector available:
   deterministic root-cause > deterministic detection > LLM-judge > written reminder (FL-cf051).
2. **Never no-op a non-empty user message.** Emit-time gate; execute the bound action or say in one
   line why not (FL-cf026, FL-cf028, FL-cf033, FL-cf050).
3. **Narrated ≠ executed.** A sentence claiming a write is followed, same turn, by the tool call
   (FL-cf046).
4. **Done ⇒ acceptance artifact.** Never mark complete on handoff (FL-cf025).
5. **No self-grading free-form.** The Auditor is a different model (Sonnet 5) from the Do-er (Opus) and emits
   **per-dimension binary PASS/FAIL** — never a numeric/Likert score, never a free-form verdict (FL-cf010,
   PD-001). Fail closed on no verdict (FL-cf049). The separation is *same-family* (Sonnet 5 vs Opus), not
   cross-provider — a cross-provider judge is reachable but declined as default for portability (PD-005) — so
   deterministic detectors carry the real decorrelation, not the judge (PD-003).
6. **Reversibility gate.** Classify each action; irreversible ones need explicit approval + blast-radius
   (FL-cf013).
7. **Read before assert.** Never claim a path/record/quote exists without reading it (FL-cf015, FL-cf052).
8. **Mounted ≠ executing.** A guard counts as coverage only once its heartbeat is verified (FL-cf034, FL-cf044).
9. **No personal data in a committed record.** Re-scan before every commit (FL-cf013 blast-radius).
10. **Keep the loops unleaked.** Prongs exchange typed artifacts only (`loop-contract.md`).
11. **No borrowed "deterministic."** Don't call a verdict deterministic/mechanical/by-code without an
    executed code artifact in the same turn; otherwise label it model/human judgment (CF-058).
12. **No self-graded evals.** The grader model ≠ the subject model ≠ the fixture-author model; record all
    three and fail closed if they collide — this applies to evaluations of Trident itself (CF-059).
13. **No premature all-clear.** An eval yields "good/validated" only with hard-negative traps present, the
    discriminator kept out of the subject's prompt, and a known-bad control that actually failed; otherwise
    the verdict is "not-yet-validated," never "good" (CF-060, CF-061).
14. **An unvalidated judge is not a gate.** A rubric judge's verdict counts only once the judge clears a
    per-class **TNR bar** on a human-labeled slice (catch the agreeableness bias: high TPR, collapsed TNR =
    silent false-PASS). Not-yet-validated → fail closed to a human check or Do-er re-loop (PD-002).

15. **Ask scope first, then intent — never infer either.** No Trident session starts from an inferred
    goal or an unbounded surface. Simba's first act in a new session is to ask, verbatim,
    **"what's the scope for this session?"** — capturing BOTH `in_scope` and `out_of_scope`, because a
    scope with no exclusions is not a scope. Only then does it ask what they are trying to get. The
    `IntentCard` is built from their answers — prior messages are corroboration, never the source. An IntentCard whose `goal` was
    derived without a user answer in the same session is not a valid gate input; fail closed and ask
    (PD-007). **Exception, narrowly scoped** — an instruction to skip the ask counts only if it:
    (a) names *skipping the intent question* specifically — a generic "go ahead", "ok", or "do it" is
    **not** a waiver and must never be read as one; (b) is scoped to the decision at hand, **never** a
    standing waiver for the session; and (c) is re-confirmed when a materially new decision arises that
    the original instruction did not cover. Record the instruction verbatim in `pinned_feedback`.
16. **Nested bullets and tables only.** Every Trident-authored surface — orchestrator reports, `IntentCard`,
    `AssumptionSet`, `RATVerdict`, `Verdict`, `DriftFlag` — is written as **nested bullets or tables**.
    No prose paragraphs, no essay narration. A field that needs explaining gets a sub-bullet, not a
    sentence of commentary. **Carve-out:** verbatim quoted evidence (`DriftFlag.evidence`, a quoted user
    instruction) and connected multi-sentence judge reasoning are compliant **inside a bullet or table
    cell** — the requirement is structural containment, not sentence-count austerity. Rationale: prong
    outputs are read as artifacts and diffed between loops; prose hides structure and lets a claim slip
    through unattributed (PD-007).

> Rung note: 0 and 1 are enforceable by code (0 via `prongs/rat.mjs` + `validate_prongs.py` HR-0, wired
> into `tests/selftest.py`, with negative controls); 11–14 are reminder/structural guards. They lower recurrence, they
> do not make it impossible. A model can still read a rule and break it; only a wired-in check is a gate.
> 14's TNR bar is itself the wired-in check that turns judge rule 5 from a reminder into a measured gate.
> 15 and 16 are gated by `failures/intent_gate.py` (executed, with negative controls, wired into
> `tests/selftest.py`): 15 checks the `intent_source` field AND that `scope.in_scope` / `scope.out_of_scope`
> are both present and non-empty; 16 scans a surface for prose paragraphs.
> Both gates check the **artifact**; neither can force Simba to have genuinely asked — that rung is still
> a discipline, and the field can be stamped `asked` untruthfully.

## Portability guardrails (do not break)
- No build, no dependencies — installs as a plain skills tree. Orchestration uses subagents, so the runtime surface is Claude Code / VS Code.
- Skills stay co-located; cross-references use `../` relative paths inside one `.claude/skills/` tree.
- No external paths. If a change adds one, it is wrong.
