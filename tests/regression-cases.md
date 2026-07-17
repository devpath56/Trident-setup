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

> TODO after approval: one case per remaining CF as the full log is migrated.
