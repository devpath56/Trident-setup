# Seed detector catalog — the a-priori failure taxonomy (from TraceRoot)

Trident's CF detectors are all **learned from real observed failures** — precise, but blind to modes
Trident has not hit yet. This file seeds coverage for modes an AI-agent observability layer expects
*a priori*, taken from TraceRoot's Detectors taxonomy (hallucination · tool-failure · logic-error ·
safety-violation · intent-drift). It is the watch-list the Auditor's **AnticipatedFailures** primer can
draw from at intake, before any of these fires.

**These are NOT CF records.** The CF SSOT (`failures/failures.jsonl`) only ever grows from a real
observed failure (CLAUDE.md discipline). An a-priori mode goes here and into the **PD ledger**
(`failures/decisions.jsonl`, PD-008…PD-012) as a *pre-emptive* decision with a `promotion_trigger`. The
first time the mode is actually observed, `log failure` promotes it to a real `CF-###` with a proper
detector authored as high up the ladder as possible (CF-061), and `related: [PD-xxx]`.

**Guardrail (non-negotiable).** Any of these that lands as an `llm-judge` detector must clear
`failures/tnr.py` (TNR ≥ bar, ≥ MIN_NEG hard negatives) before its verdict can *pass* work (PD-002).
Import TraceRoot's **coverage**, not its trust model — TraceRoot's judge-detectors have no
agreeableness-bias validation; Trident's do, and that gate stays in force.

## The five seed modes

| # | mode | today's rung | promotion target (highest rung reachable) |
|---|---|---|---|
| PD-008 | **hallucination / unverifiable claim** | llm-judge (fail-closed until TNR-validated) | hybrid — deterministic proxy: a factual/result claim with no tool-call or cited source in the same turn (reuse CF-004 / CF-046), llm-judge on the semantic residue |
| PD-009 | **tool-failure (silent)** | reminder | structural/deterministic — `prongs/spans.mjs` already surfaces `role:"error"`; wire a check that FAILS when an error span is unacknowledged/unretried in the Output |
| PD-010 | **logic-error / self-contradiction** | reminder | hybrid — deterministic where the contradiction is between two typed artifacts (plan vs result); llm-judge, TNR-gated, on prose reasoning |
| PD-011 | **safety-violation** | reminder | structural — reuse house-rule 6: an irreversible/prohibited action with no `approved_by`; llm-judge residue for softer policy breaches |
| PD-012 | **intent-drift** | reminder (cross-checks Simba) | already partly covered — Simba's tier-1 detector + the `DriftFlag.determination` enum; this seed adds the a-priori *anticipation* so Simba watches for it before it fires |

## How the Auditor uses this
At intake, the Auditor predicts which of these **this task** is prone to (a fetch-heavy task → tool-failure;
a scoring/ideation task → hallucination + intent-drift) and folds them into the `AnticipatedFailures` primer
it hands Simba — exactly as it already does for CF modes (`auditor/SKILL.md`). The seed catalog just widens
the anticipation set beyond what Trident has already been burned by.

Source: TraceRoot Detectors taxonomy — <https://traceroot.ai/docs/getting-started/introduction> (public docs).
