# CLAUDE.md — maintaining Trident

Trident is a **dependency-light skill bundle for Claude Code / VS Code**: a three-prong quality harness
plus one failures-log SSOT. No build, no deps. Everything needed to run, modify, and extend it lives in
this repo. Its orchestration spawns real subagents, so the runtime surface is Claude Code / VS Code
(not claude.ai / Cowork).

## What it is
Three prongs watching any working session: a **Do-er** (Opus), **Simba** (loyal to the user, guards
intent), and an **Auditor** (Fable, deterministic evaluators first). They share one **failures log**
(`failures/failures.jsonl`) — every real mistake becomes a check that stops it recurring. See
`README.md` for the pitch and `ARCHITECTURE.md` for the full design.

## Architecture — one rule, one home
- **`.claude/skills/references/house-rules.md` is the single source of truth** for cross-cutting
  behavior (deterministic-first, no-op ban, narrated≠executed, done⇒artifact, no self-grading, …).
  Every skill points to it via `../references/house-rules.md`. **Change a cross-cutting rule there,
  not in each skill.**
- `.claude/skills/trident/SKILL.md` — the orchestrator + owner of the `log failure` trigger.
- `.claude/skills/auditor/SKILL.md`, `.../simba/SKILL.md` — the two watcher prongs.
- `.claude/skills/references/` — **method** (the reusable method: tightly-scoped loops · adversarial agents ·
  incentive alignment, + the scored generate→re-rank primitive + the context-contract), **experiment-method**
  (how to prove a claim before shipping: pre-register · one variable · runnable ground truth · independent
  fail-closed audit), loop-contract (no-leak isolation), evaluators (CF→check method), phoenix-protocol (the
  eval shapes borrowed from Arize Phoenix), failures-log (SSOT schema + protocol).
- `failures/failures.jsonl` — the **SSOT**: one CF record per line. `schema.json` validates a record.
  `FAILURES.md` is a **generated** human view — never hand-edit it.
- `tests/regression-cases.md` — one case per guard, each from a real observed failure.

## How to modify
1. A cross-cutting rule (evaluation order, endings, permission gates) → edit `house-rules.md`.
2. A prong's behavior → its own `SKILL.md`.
3. A new failure mode → append via the `log failure` protocol (`references/failures-log.md`).

## The `log failure` SSOT discipline
`log failure` (and normalized variants) appends the next `CF-###` to `failures/failures.jsonl` — read
the **last line only** to number, never full-read. The committed record is **sanitized**: no names,
paths, or company references. Raw incidents go to `failures.local.jsonl` (gitignored). The Auditor
approves each record; then commit + push so the SSOT stays current across sessions.

## Adding a guard — the discipline
Add a guard **only from a real observed failure**, never a hypothetical:
1. Capture the trigger and the exact bad output.
2. Add the CF record (guard + detector + the FAIL signature as `signal`).
3. Push the detector as high up the ladder as possible: deterministic > structural > llm-judge > reminder.
4. Add a regression case in `tests/regression-cases.md`.

The suite only ever grows from real errors.

## Hard guardrails (do not break)
- **No build, no deps.** Keep install trivial (a skills tree). Orchestration uses subagents — a Claude Code / VS Code capability; don't add machinery that assumes another surface.
- **No personal data, no external paths in any committed record.** Re-scan before every commit —
  grep the working set for your home-dir prefix, private workspace names, and company names; block on any hit.
- **Deterministic detectors before any LLM-judge.** The Auditor (Fable) is never the Do-er (Opus).
- **Keep skills co-located** under one `.claude/skills/` tree so `../references/…` resolves.
