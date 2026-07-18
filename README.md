# Trident

**A three-prong quality harness for shipping features in Claude Code / VS Code — dependency-light, installs as skills.**

Trident wraps any working session in three prongs that hold each other honest:

- **Do-er** (Opus) — does the task.
- **Simba** — loyal to *you*. Reads only your messages, holds your intent, and catches the moment the
  Do-er starts to drift or forget a must-have — before it ships.
- **Auditor** (Sonnet 5) — judges the output with **deterministic evaluators first**, a rubric-based
  LLM-judge second. A different model from the Do-er, so it never grades its own work.

The shaft that binds the three: a **failures log** — one JSONL source of truth. Every real mistake is
logged once, turned into a check that stops it recurring, and surfaced to you. Work quality compounds.

## The method (read this)
Trident's reusable method, in [`.claude/skills/references/method.md`](./.claude/skills/references/method.md):
**multiple tightly-scoped loops · adversarial agents · incentive alignment.** Split work into small bounded
loops; in each, an agent loyal to a *different* master tries to break the result; every dispute is settled by
one authority over one shared failures log. Everything else in this repo is an instance of that method.

> Modeled on [Arize Phoenix](https://arize.com/docs/phoenix)'s eval shapes (trace → evaluate → curate
> failures → iterate) so it's grounded in a real framework and forward-compatible with a live Phoenix
> deployment — while installing as a plain skills tree in Claude Code / VS Code (where its subagents run).

## Status
**Skeleton for review.** The architecture is in [`ARCHITECTURE.md`](./ARCHITECTURE.md); skill files and
references are stubbed to its contract. Deep logic and the full failures-log migration follow design sign-off.

## Layout
```
ARCHITECTURE.md              the design doc (read this first)
.claude/skills/
  trident/    SKILL.md        orchestrator + the `log failure` SSOT trigger
  auditor/    SKILL.md        Sonnet 5 judge — deterministic evaluators first
  simba/      SKILL.md        your-intent guardian
  references/                 method (the reusable method), experiment-method (how to prove a claim), house-rules, loop-contract, evaluators, phoenix-protocol, failures-log
failures/
  failures.jsonl              the SSOT (sanitized, committed)
  schema.json                 record schema
  FAILURES.md                 generated human view (do not hand-edit)
tests/
  regression-cases.md         one case per guard, from a real failure
```

## The one discipline
Every guard exists only because of a real, observed failure — and maps to a check that stops that exact
failure recurring. The failures log only ever grows from real errors.
