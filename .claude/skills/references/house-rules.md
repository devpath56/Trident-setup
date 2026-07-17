# House rules — the single source of truth for Trident's cross-cutting behavior (SKELETON)

Every skill (`trident`, `auditor`, `simba`) points here for shared rules. **Change a cross-cutting
rule here, not in each skill** (the anti-drift discipline — FL-cf001, FL-cf011).

## The invariants (each traces to a real failure)
0. **Riskiest assumption first (hard block).** No build of any kind starts until the single riskiest
   assumption — ranked by kill-power × uncertainty — is proven by the cheapest falsifying probe. The
   Auditor (Fable) owns the feasibility gate; Simba owns the intent gate; the Do-er runs the probe but
   never self-approves. On probe fail → stop, report, log a CF (FL-cf056, FL-cf044, FL-cf039).
1. **Deterministic first.** Any guard is enforced by the highest-reliability detector available:
   deterministic root-cause > deterministic detection > LLM-judge > written reminder (FL-cf051).
2. **Never no-op a non-empty user message.** Emit-time gate; execute the bound action or say in one
   line why not (FL-cf026, FL-cf028, FL-cf033, FL-cf050).
3. **Narrated ≠ executed.** A sentence claiming a write is followed, same turn, by the tool call
   (FL-cf046).
4. **Done ⇒ acceptance artifact.** Never mark complete on handoff (FL-cf025).
5. **No self-grading free-form.** The Auditor is a different model (Fable) and scores per-rubric-dimension
   (FL-cf010). Fail closed on no verdict (FL-cf049).
6. **Reversibility gate.** Classify each action; irreversible ones need explicit approval + blast-radius
   (FL-cf013).
7. **Read before assert.** Never claim a path/record/quote exists without reading it (FL-cf015, FL-cf052).
8. **Mounted ≠ executing.** A guard counts as coverage only once its heartbeat is verified (FL-cf034, FL-cf044).
9. **No personal data in a committed record.** Re-scan before every commit (FL-cf013 blast-radius).
10. **Keep the loops unleaked.** Prongs exchange typed artifacts only (`loop-contract.md`).

## Portability guardrails (do not break)
- No build, no dependencies — installs as a plain skills tree. Orchestration uses subagents, so the runtime surface is Claude Code / VS Code.
- Skills stay co-located; cross-references use `../` relative paths inside one `.claude/skills/` tree.
- No external paths. If a change adds one, it is wrong.
