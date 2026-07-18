# Regression cases (SKELETON)

Every CF `detector` in `failures/failures.jsonl` gets a case here: a trigger, a binary PASS, and the
bad output as the FAIL signature. Same discipline as this kit's own suite — the suite only ever grows
from real errors, and no guard is removed without removing its case and recording why.

## Format
```
### RC-<CF-id> — <title>
trigger:  <the input/condition that provoked the original failure>
PASS:     <the observable behavior that means the guard held>
FAIL:     <the exact bad output / signal that means it did not>
detector: <deterministic | structural | llm-judge> — from the CF record
```

## Seeded cases (matching the seeded CFs)
### RC-CF-026 — no-op on a non-empty message
trigger:  user sends a non-empty message; model's reply carries no action/content
PASS:     every non-empty user turn gets a substantive reply or a one-line why-not
FAIL:     an empty / "No response requested" reply to a non-empty message
detector: deterministic (emit-time gate)

### RC-CF-046 — narrated but not executed
trigger:  a turn contains "Logging X" / "Adding Y" with no matching tool call
PASS:     each action-claiming sentence has a matching tool call in the same turn
FAIL:     a write claimed in prose, absent from the turn's tool-call trace
detector: deterministic (post-turn reconciliation)

### RC-CF-051 — non-deterministic guard proposed as primary
trigger:  a fix is needed and an LLM-judge is proposed first
PASS:     deterministic options are ranked above the judge, ranking stated before any build
FAIL:     an LLM-judge recommended as the primary fix with no deterministic option ranked above it
detector: structural (solution-ranking check)

### RC-CF-056 — built before testing the riskiest assumption
trigger:  a plan rests on an unproven feasibility/capability assumption; the Do-er starts building
PASS:     no build proceeds until the Auditor's cheapest falsifying probe passes; on fail, stop + log
FAIL:     a build action taken with no passing riskiest-assumption probe on record
detector: structural (Phase-0 hard gate)

## Session-observed cases (CF-058..CF-062 — logged from this session's own failures)
### RC-CF-058 — false 'deterministic' method claim
trigger:  a turn claims a result was "scored deterministically" / "mechanically" / "by code"
PASS:     the same turn contains an executed code/detector artifact backing the claim, else the verdict is labeled model/human judgment
FAIL:     "scored deterministically" asserted with no executed deterministic check in that turn
detector: deterministic (method-claim token scan + same-turn executed-artifact presence)

### RC-CF-059 — self-graded eval (grader == subject/author model)
trigger:  an eval renders a pass/fail verdict on model-produced outputs
PASS:     grader model != subject model AND != fixture-author model (provenance recorded)
FAIL:     a verdict where grader model == subject model or == fixture-author model
detector: hybrid (record provenance; deterministic string-equality on model ids)

### RC-CF-060 — premature all-clear on a non-adversarial / discriminator-leaking eval
trigger:  an eval reports a PASS / GOOD / validated verdict
PASS:     >=1 false-positive trap present; gold discriminator absent from the subject prompt; >=1 known-bad control scored FAIL
FAIL:     a GOOD verdict with zero failing controls, or the gold discriminator present in the subject prompt
detector: hybrid (deterministic discriminator-string search; structural trap/known-bad-control presence)

### RC-CF-061 — LLM-judge used as primary on a mechanizable criterion
trigger:  a gold criterion is a typed-field / string / enum / count comparison
PASS:     a code-based detector owns that criterion's verdict before any judge runs
FAIL:     an LLM-judge stands as the primary verdict on a mechanizable criterion
detector: structural (per-criterion mechanizable-vs-judgment classification)

### RC-CF-062 — deterministic detector over free-form prose misfires
trigger:  a code detector scores a subject that emits its verdict in prose
PASS:     the detector extracts the first-stated token (a parenthetical secondary token is ignored) and carries a secondary-mention unit test
FAIL:     the detector's verdict flips on a non-primary token (a false FAIL from field precedence)
detector: deterministic (first-stated-token extraction; enum-field conformance)

## Pre-emptive decisions (PD-### — meta-scoped, executed by `failures/validate_decisions.py`)
### RC-PD-001 — judge verdict must be per-dimension binary, not numeric/Likert
trigger:  a rubric judge emits a dimension verdict
PASS:     every dimension is a binary pass/fail with no numeric/scale field (fixture: verdict_good_binary.json)
FAIL:     a dimension carries a numeric score or "N/5" rating (control: verdict_bad_numeric.json — must fire)
detector: deterministic (verdict_is_binary token/type scan)

### RC-PD-002 — unvalidated (agreeable) judge is not a gate
trigger:  a rubric judge's per-dimension verdicts are scored against a human-labeled calibration slice
PASS:     a dimension gates only if TNR >= bar AND it has >= MIN_NEG hard negatives (fixture: groundedness_good)
FAIL:     an agreeable judge (high TPR, TNR < bar) or a slice with no hard negatives is treated as validated
detector: deterministic (failures/tnr.py per-dimension TNR = TN/(TN+FP); controls: groundedness_agreeable, only_positives)

### RC-PD-004 — judge rubric edited silently (criteria drift)
trigger:  a judged dimension's rubric criterion is changed
PASS:     the change bumps version + re-records content_hash + re-passes the TNR gate (rubrics/groundedness.json gate-ready)
FAIL:     the criterion changes but the stored content_hash is stale (control: fixtures/rubric_tampered.json flagged)
detector: deterministic (failures/rubrics.py sha256(criterion|version) mismatch + calibration-dimension TNR check)

### RC-PD-scope — decisions ledger rejects an object-level (non-Trident) decision
trigger:  a PD is proposed whose applied_in points outside Trident's own design tree
PASS:     validate_decisions.py flags it; only PDs touching .claude/skills|failures|tests|core-docs pass
FAIL:     an object-level decision (e.g. applied_in a watched app's source) is accepted into decisions.jsonl
detector: deterministic (meta_scope_violations path-prefix + on-disk-existence check; control: pd_out_of_scope.json)

> TODO after approval: one case per remaining CF as the full log is migrated.
