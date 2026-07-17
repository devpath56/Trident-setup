# Trident — architecture (design doc, v0 for review)

> Status: **skeleton for review.** This doc is the contract. Skeleton `SKILL.md`s and
> references are stubbed to match it; deep logic is filled in *after* this design is approved.

## What Trident is
A **portable, zero-dependency skill bundle** (same class as this kit — runs in claude.ai,
Cowork, and Claude Code with no build, no deps, no hooks) that wraps any working session in a
**three-prong quality harness**. The three prongs:

```
             ┌── the work ──────────────┐
   you ──▶  DO-ER (Opus)  ─────────────▶ output ──▶ you
             │            ▲            │
             │            │            │
        SIMBA ───────────┘        AUDITOR (Fable)
     (guards your intent)      (judges the output)
```

- **Do-er** — the model doing the actual task (Opus by default). Trident does not replace it; it watches it.
- **Simba** — a subagent **loyal to you**. Reads *only your messages*, tracks intent, and injects
  the thing the Do-er is about to forget deep in its work back into the loop before it drifts.
- **Auditor** — a **Fable** subagent. Judges the Do-er's output with **deterministic evaluators first**,
  an **LLM-judge second** (per FL-cf051), modeled on Arize Phoenix's evaluator taxonomy.

The name is literal: three prongs, one shaft. The shaft is the **failures log** (the SSOT) — every
prong reads from and writes to it.

## Why these three, and the one rule they share
Everything Trident does is downstream of one discipline this kit already lives by:

> **Every guard exists only because of a real, observed failure — and maps to a check that
> stops that exact failure recurring.**

The `failures.jsonl` SSOT *is* that growing suite. Each record carries a one-line **guard** and a
**detector** (a mechanical check where possible). The Auditor runs the detectors. Simba watches for
the intent-drift class. New failures get logged, approved by the Auditor, and surfaced to you — so
work quality compounds instead of repeating the same mistakes.

## The loop (tightly scoped, no leaks)
Each prong runs its own loop with its **own todolist and its own isolated context**. "No leaks"
is a hard contract (see `references/loop-contract.md`): a prong never sees another prong's scratch
state — only the **typed artifacts** they exchange. This is deliberate — it is the fix for
context-degradation and instruction-collision failures (FL-cf009, FL-cf011).

```
1. SIMBA.read(user messages only)        → IntentCard         (what you actually asked for)
2. DO-ER.work(task)                       → Output + Spans     (the attempt + its trace)
3. AUDITOR.evaluate(Output, Spans,
                    detectors, IntentCard) → Verdict           (deterministic first, judge second)
4. if Verdict.fail → back to DO-ER with the specific failing detector(s)   (bounded retries)
   if Simba flags intent-drift → inject the IntentCard delta into step 3
5. on pass → surface to you. on a NEW failure mode → log it (SSOT), Auditor approves, you see it.
```

Artifacts exchanged between prongs (the only things that cross a loop boundary):

| Artifact | Producer | Consumer | Shape |
|---|---|---|---|
| `IntentCard` | Simba | Auditor | user-goal, must-haves, forbid-list, drift-signals |
| `Spans` | Do-er | Auditor | Phoenix/OpenInference-shaped span list (see below) |
| `Verdict` | Auditor | Do-er / you | per-detector pass/fail + the FAIL signature |
| `CF record` | any prong | SSOT | one `failures.jsonl` line (schema below) |

## The Auditor — deterministic-first, Fable-judged
Ordering is fixed and non-negotiable (FL-cf051 is itself a guard here):

1. **Deterministic detectors** — string/structural/grep checks derived from CF guards.
   Example: FL-cf047 → `grep <removed-entity> across every touched artifact` before "removal complete".
2. **Structural detectors** — schema/acceptance-test checks (FL-cf025: is there a verifiable artifact?).
3. **LLM-judge (Fable), rubric-based only** — for what deterministic checks can't reach
   (persona drift, verbatim-quote fidelity). **Never free-form self-assessment** (FL-cf010).
   Fable ≠ the Do-er (Opus) on purpose: a different model, so it is not grading its own work.

## Phoenix-modeled evaluation (described, not executed)
We are pure-skill, so we do not run `phoenix.evals`. Instead the SSOT and the Auditor **adopt
Phoenix's shapes**, so the whole thing is forward-compatible with a real Phoenix deployment later:

- **Spans** — the Do-er's trace uses the OpenInference span shape (name, input, output, status,
  error). Your existing private failure log's `Trace (spans — ⊘ root, ⚠ error)` convention already *is* this.
- **Evaluators** — code-based + LLM-based + human-label, exactly Phoenix's three kinds.
- **Datasets / experiments** — the `failures.jsonl` SSOT *is* the curated failure dataset;
  Phoenix's loop (trace → evaluate → curate failures → iterate) is Trident's loop.
- The optional (out-of-scope, by your "pure skill bundle" call) Python harness would pipe these
  same records into a live Phoenix instance with zero reshaping.

Sources for the Phoenix shapes: see `references/phoenix-protocol.md`.

## The failures log — one SSOT, JSONL, cross-session
- **Format: `failures.jsonl`** — one CF record per line (not a JSON array, not one big markdown file).
  Append is one line; numbering reads the last line only; diffs are one line per entry.
- **Single source of truth in the Trident repo.** The `log failure` trigger (owned by the
  `trident` skill, with normalized variants per FL-cf026) appends the next `CF-###` and commits/pushes
  to this file — from **any session that has the Trident repo in scope**. Same discipline this kit
  uses for `progress.json`.
- **Public/private split.** `failures.jsonl` (committed) holds only the **generalized, sanitized**
  record — pattern, guard, detector, PM implication. Raw personal incidents (company names, paths)
  stay in `failures.local.jsonl` (gitignored). Nothing personal reaches a public repo without your
  explicit say-so.
- `FAILURES.md` is a **generated** human view; never hand-edited. `failures/schema.json` validates a record.

See `references/failures-log.md` for the record schema and the `log failure` protocol.

## Open decisions for you (before I flesh out the logic)
1. **JSONL** for the SSOT — confirmed as my recommendation; veto here if you'd rather keep markdown.
2. **Standalone repo** — I can create `devpath56/Trident` (public) once you confirm; until then this
   is staged under `trident/` on this branch. Creating a public repo is the one outward action I'll
   hold for your explicit go.
3. **Full seed migration** — I've seeded a sanitized *representative* set now. Migrating all 55
   CFs (carefully sanitized, with an auditor pass per your FL-cf052) is a follow-up once the schema is approved.
