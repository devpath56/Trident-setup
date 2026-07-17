# Evaluators — turning each CF guard into a check the Auditor runs (SKELETON)

Every record in `failures/failures.jsonl` carries a `detector`. The Auditor's evaluator suite *is*
those detectors. This file is the method for writing them; the catalog lives in the JSONL itself so
there is one source of truth (no drift between a rule and its check — FL-cf001).

## The mapping method (per CF)
1. Read the CF's `guard` (the one-line rule).
2. Ask: **can a machine check this without a model?** If yes → `kind: deterministic` (grep, string,
   count, exit-code). Prefer this always (FL-cf051).
3. If it needs structure but not judgment (does an artifact exist? is the tool tier-3?) → `kind: structural`.
4. Only if it genuinely needs semantic judgment (persona drift, quote fidelity) → `kind: llm-judge`,
   and then rubric-based, Fable, fail-closed (FL-cf010, FL-cf049).
5. Write the `signal`: the exact FAIL signature the check emits. This is what shows up in the `Verdict`.

## Worked examples (already seeded in the JSONL)
| CF | guard (short) | detector kind | check | signal |
|---|---|---|---|---|
| CF-026 | never no-op a non-empty message | deterministic | emit-time: reply empty & last user msg non-empty? | empty reply to non-empty msg |
| CF-046 | narrated write ⇒ real tool call | deterministic | diff action-verbs vs tool-call trace this turn | claim with no matching call |
| CF-047 | removal is set-scoped | deterministic | grep entity across all touched files | non-zero cross-file hits |
| CF-025 | done ⇒ acceptance artifact | structural | is the named artifact present? | completed w/ no artifact |
| CF-013 | irreversible ⇒ approval | structural | tool tier-3 without approval token? | tier-3 call, no token |
| CF-052 | quote ⇒ verbatim | hybrid | gate: source tag present; judge: span verbatim in source | quote not found verbatim |
| CF-010 | no free-form self-grade | llm-judge | judge must emit per-dimension rubric scores | verdict w/ no rubric scores |

## Rule
A guard with **no runnable detector** is a written reminder — the weakest tier (FL-cf051). When you
add a CF, push as hard as possible up the ladder (deterministic > structural > judge > reminder)
before settling. Record which tier you landed on and why.
