# AI-Native Spec Contract — the spec-of-spec for handoffs

> The rubric an AI-native handoff must satisfy before it is "done." Cross-cutting rules live in
> `./house-rules.md`; the reusable loop + scored generate→re-rank primitive live in `./method.md`.
> This doc is the **quality bar the build's score-loop climbs**, and the standard an Auditor grades a
> handoff against.

## Why this exists (the two north stars)
Building is cheap; a PM can ship ~80% of a feature with AI. What is not commoditized: **defining
acceptance criteria that are *earned*, not asserted**, and **handing production-readiness to engineers
as equal-partner owners**. So a handoff serves two accountabilities, and the spec is the contract
between them:

- **PM north star** — value: the product works and the acceptance bar is defined well.
- **Engineering north star** — reliability · maintainability · production-readiness, **owned**.

**Anti-goal (a named failure, not a preference):** "the PM completed it all" is a **trust failure**.
In the engineer's lens (below) it is *information leakage* + *overexposure* — the PM's process forced
across the boundary. A good handoff is a **deep module**: a simple interface (the bar + the contracts +
the open room) hiding substantial implementation (the RAT, the eval iterations, the error analysis).

## The rubric — 6 build dimensions + 1 cross-cutting axis
| # | Dimension | Owner | What it asserts |
|---|---|---|---|
| 1 | **Prototype-as-spec** | PM | Behavior over frames — real states driven by **real model calls**, never mocked happy-path. |
| 2 | **Interface contracts** | PM bar / **eng how** | Three sub-contracts, not one: **model** (I/O schema · refusal · confidence), **API** (endpoints · auth · versioning · idempotency · error codes · rate limits), **data** (provenance · PII · retention). |
| 3 | **Failure & fallback** | PM bar / **eng how** | The unhappy path as a contract: degradation behavior · the human-in-loop path (not just a `needs_human` field) · safety/refusal policy · cost + latency budget. |
| 4 | **Eval contract** ⭐ | PM | Dataset + slices · metric definition · a **validated** judge (per-class TNR) · a baseline · a **failure taxonomy derived from observed traces** (error analysis), never an asserted number. |
| 5 | **Observability** | PM bar / **eng how** | Traces/spans logged · an online metric · a drift trigger. You cannot operate what you cannot see. |
| 6 | **Versioning & regression** | PM bar / **eng how** | Prompt/model pinning · a regression set kept green · a rollback trigger. AI systems drift; a static spec cannot be operated. |
| 7 | **Ownership & socialization** (cross-cutting) | shared | Each production-readiness dimension names an **engineering owner** and leaves **open room**; ownership transfers **demo-driven and contestable**, organized **by owner/information — not by phase chronology** (that ordering is *temporal decomposition*, a red flag). |

⭐ **Dimension 4 is the load-bearing PM differentiator** — it carries the highest weight in the score-loop.

## The two MUSTs
1. **Earned acceptance.** The eval contract must reference **≥1 executed eval iteration** over a real
   dataset whose failure taxonomy traces to observed spans. **Zero observed iterations ⇒ the spec is
   `incomplete`.** (This is `house-rules.md` rung 8 — *mounted ≠ executing* — applied to acceptance:
   a bar is real only once the loop that produced it has actually run.)
2. **Open room, not completion.** Every production-readiness dimension names an engineering owner and
   carries open room. **A PM-closed dimension with no named owner fails** — the trust check. There is
   **no human sign-off gate**; ownership transfers socially (named owner · open room · demo).

## Score-loop weighting (the bar the build climbs)
Run the scored generate→re-rank loop of `./method.md` against these dimensions until the bar holds.
Weight **dim 4 highest**, then 3/5/6 (the production-readiness half), then 1/2. Stop at target with a
stall guard; publish a cheap render each loop. A grey-case between two dimensions is **shown, not
laundered into one number** (`./method.md` grey-case guard).

## Engineer's lens — grade against *A Philosophy of Software Design*
Whenever this work simulates "what will an engineer think looking at this handoff," judge it against
Ousterhout's *A Philosophy of Software Design* (a verified reference copy lives in the operator's
Ousterhout skill cartridge — cite the book, never paraphrase from memory). The load-bearing tests:
- **Deep vs. shallow module** — does the handoff hide the PM's process behind a simple interface, or is
  the interface as complex as its value (ceremony)?
- **Information hiding vs. leakage / overexposure** — is PM-internal detail forced across the boundary?
- **Pull complexity down · define errors out of existence · design it twice** — applied to the fallback
  and interface dimensions.
- **Not temporal decomposition** — the handoff is organized by information + owner, never by the order
  the PM did the work (RAT → build → audit → close).

## Provenance (public authorities — this is a grounded standard, not an invention)
- *A Philosophy of Software Design*, Ousterhout — the engineer's lens.
- The ML Test Score (Breck et al., Google, 2017) — the four production-readiness categories
  (Features/Data · Model Development · Infrastructure · Monitoring). The common 4-pillar handoff model
  covers ~one of the four; dims 3/5/6 restore the operability half.
- Husain & Shankar, *LLM Evals* (2026) — acceptance is **earned from observed failures** (error
  analysis on real traces), not asserted upfront.
- GitHub Spec Kit (2025) — spec-driven development: the spec generates the implementation.

## Enforcement (sequenced — see the roadmap, not all here yet)
- **Exists today:** dim 4 (`verdict`/`detectors[]`, `failures.jsonl`, `durability`), dim 5 data
  (`prongs/spans.mjs`, `drift`), dim 6 (`tests/regression-cases.md`, `tests/selftest.py`).
- **Ships downstream (after the phase-model DAG restructure):** typed `contract` + `fallback` rows and
  the validators `check_contract`, `check_fallback`, `check_ownership_room`, `check_handoff_completeness`;
  plus the low-fi per-PR demo render (the visible artifact) with vibe-annotation feedback capture. Until
  those land this rubric is a **reminder-tier** guard (`house-rules.md` rung 1) — honest about the gap.
