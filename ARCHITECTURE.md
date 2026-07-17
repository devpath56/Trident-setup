# Trident — architecture (design doc, v0 for review)

> Status: **skeleton for review.** This doc is the contract. Skeleton `SKILL.md`s and
> references are stubbed to match it; deep logic is filled in *after* this design is approved.

## What Trident is
A **skill bundle for Claude Code / VS Code** (no build, no deps) that wraps any working session in a
**three-prong quality harness**. It installs as plain skills, but its orchestration relies on real
**subagents**, so the target surface is Claude Code / VS Code where those exist — not claude.ai / Cowork.
The three prongs:

```
             ┌── the work ──────────────┐
   you ──▶  DO-ER (Opus)  ─────────────▶ output ──▶ you
             │            ▲            │
             │            │            │
        SIMBA ───────────┘        AUDITOR (Fable)
     (guards your intent)      (judges the output)
```

- **Do-er** — the model doing the actual task (Opus by default). Trident does not replace it; it watches it.
- **Simba** — a subagent **loyal to you**, and a **counterweight to the model's recency bias**: it
  durably remembers your goal and the corrections you've already made (which otherwise decay under the
  latest message), reads the Do-er's *result* to detect drift from that intent, and **flags it to the
  Auditor, which decides the response**. Simba proposes; the Auditor disposes.
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

## The method (the reusable core)
The three pillars behind everything below — **multiple tightly-scoped loops · adversarial agents ·
incentive alignment** — are stated as one reusable method in `references/method.md`, including the
weights-agnostic **scored generate → re-rank loop** primitive that pipelines instantiate. This section
describes Trident's specific loop; `method.md` is the general form.

## The loop (tightly scoped, no leaks)
Each prong runs its own loop with its **own todolist and its own isolated context**. "No leaks"
is a hard contract (see `references/loop-contract.md`): a prong never sees another prong's scratch
state — only the **typed artifacts** they exchange. This is deliberate — it is the fix for
context-degradation and instruction-collision failures (FL-cf009, FL-cf011).

```
0. PHASE 0 — RISKIEST-ASSUMPTION GATE (before any build):
   SIMBA.read(user messages only)        → IntentCard         (goal + the intent-riskiest assumption)
   DO-ER.plan(task)                       → AssumptionSet      (approach + every capability assumption)
   AUDITOR.rat(AssumptionSet, IntentCard) → RATVerdict         (the ONE riskiest + the cheapest probe)
   DO-ER.probe(RATVerdict.probe)          → probe result       (a throwaway — minutes, not hours)
   ══ HARD GATE: no build proceeds until the probe passes. On fail → STOP, report, log a CF. ══
1. DO-ER.work(task)                       → Output + Spans     (only now — the real build begins)
2. AUDITOR.evaluate(Output, Spans,
                    detectors, IntentCard) → Verdict           (deterministic first, judge second)
3. if Verdict.fail → back to DO-ER with the specific failing detector(s)   (bounded retries)
   if Simba emits a DriftFlag → the AUDITOR folds it into the Verdict and decides the action
4. on pass → surface to you. on a NEW failure mode → log it (SSOT), Auditor approves, you see it.
```

Artifacts exchanged between prongs (the only things that cross a loop boundary):

| Artifact | Producer | Consumer | Shape |
|---|---|---|---|
| `IntentCard` | Simba | Auditor | goal, must-haves, forbid-list, **pinned feedback**, intent-riskiest assumption (a persistent ledger, re-asserted each loop) |
| `DriftFlag` | Simba | Auditor | which IntentCard line the Do-er's `Output` diverged from + the evidence |
| `AssumptionSet` | Do-er | Auditor | every assumption the plan rests on, each tagged type + kill-power + uncertainty |
| `RATVerdict` | Auditor | Do-er | the single riskiest assumption + the cheapest falsifying probe + the hard gate |
| `Spans` | Do-er | Auditor | Phoenix/OpenInference-shaped span list (see below) |
| `Verdict` | Auditor | Do-er / you | per-detector pass/fail + the FAIL signature |
| `CF record` | any prong | SSOT | one `failures.jsonl` line (schema below) |

## Riskiest-assumption gate (Phase 0) — the "don't-waste-hours" rule
The single most expensive failure class is building something that was never possible. So **no build
of any kind starts until the riskiest assumption is proven by a cheap probe** (hard block, always):
- **Do-er** enumerates the plan's assumptions — it may not skip the capability/platform/connector ones.
- **Auditor (Fable)** owns the *feasibility* gate: it ranks assumptions by **kill-power × uncertainty**,
  names the single riskiest, and specifies the **cheapest falsifying probe** — the smallest experiment
  that could prove the approach impossible (one throwaway connector call, one capability query, one doc read).
- **Simba** owns the *intent* gate in parallel: is this even the goal? (It can't judge feasibility — its
  context is your messages only — so the two owners are complementary, not redundant.)
- **Do-er** runs the probe; the **Auditor** holds pass/fail. Build is blocked until it passes.
- On probe fail → **stop, report, and log a CF.** Minutes spent, not hours. This directly guards
  FL-cf044 (built on an unverified platform capability) and FL-cf039 (designed on an unprobed connector op).

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
- An optional (out-of-scope) Python harness could pipe these same records into a live Phoenix instance
  with zero reshaping.

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

## Decisions locked
- **SSOT format:** JSONL, one CF per line. ✓
- **Standalone repo:** live at `devpath56/Trident-setup` (public); `trident/` here is the staging mirror. ✓
- **Failures seed:** all 55 historical CFs migrated + CF-056 (built-before-feasibility). ✓
- **Riskiest-assumption gate:** Phase 0, hard block, always (Auditor owns feasibility, Simba owns intent). ✓
- **Simba's role:** durable intent memory + recency-bias counterweight; reads the Do-er's *Output* (not
  its reasoning) to detect drift; emits a `DriftFlag`; the **Auditor decides** the response. ✓
- **Cost stance:** all three prongs fire every loop (no lightweight path). The extra round-trips are
  accepted **if** quality earns them — that's exactly what the experiment's quality-per-token tiebreak tests. ✓
- **Surface:** Claude Code / VS Code only (subagents are the runtime mechanism). ✓
- **Success rubric:** validity gate → **fewer user prompts + faster** (primary) → quality-per-token (tiebreak);
  blind, deterministic-anchored judge. See `experiments/EXPERIMENT-TEMPLATE.md`. ✓

## Still open
- **The orchestration logic** — how each prong is actually spawned as a subagent, the retry bound, and
  the exact `log failure` git flow — is specified as contracts but not yet built. That's the next build.
- **The experiment run itself** — pick a medium-complexity OSS feature and run Arm A vs Arm B.
