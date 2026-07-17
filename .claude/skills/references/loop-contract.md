# Loop contract — tightly scoped, no leaks (SKELETON)

The single rule that makes Trident's three prongs safe: **a prong never sees another prong's working
state — only the typed artifacts they hand off.** This is the structural fix for context-degradation
(FL-cf009) and instruction-collision (FL-cf011): each loop stays small, so nothing drifts and no two
instruction sets blend.

## Isolation boundaries
| Prong | Sees | Never sees | Owns |
|---|---|---|---|
| Simba | user messages only | Do-er work, Auditor scratch | `IntentCard`, its own todolist |
| Do-er | the task + failing detectors fed back | Simba's raw notes, Auditor rubric internals | `Output`, `Spans`, its own todolist |
| Auditor | `Output`, `Spans`, detectors, `IntentCard` | Do-er's chain-of-thought scratch | `Verdict`, CF approvals, its own todolist |

## Why a shared context would break it
- If Simba read the Do-er's reasoning, it could be argued out of the user's intent (loses loyalty).
- If the Auditor saw the Do-er's scratch, optimism bias leaks in (FL-cf010) — it starts grading the
  effort, not the artifact.
- One giant shared context is exactly the long-session degradation that FL-cf009 documents.

## Each prong maintains its own todolist
Small, bounded, closed per cycle. A todo is `completed` only when its acceptance artifact exists
(FL-cf025) — never on handoff. Todolists do not cross prongs.

## Bounded retries
The Do-er↔Auditor loop is bounded (default 3). On exhaustion, surface the last `Verdict` and the
open detector to the user — never loop silently, never pass to escape the loop (FL-cf016 transient vs
persistent: retry the real failure, don't reroute around it).

> TODO after approval: exact retry bound, artifact serialization format, how prongs are spawned as
> subagents on each surface (Claude Code vs Cowork).
