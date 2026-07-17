# Result 01 — Trident vs bare Opus · slugify `acronyms` feature

**Task:** add `acronyms=[...]` to `python-slugify` (preserve given casing; whole-word, case-insensitive).
Real OSS repo, hidden 5-case acceptance grade neither arm saw. n=1.

| Layer | Arm A — bare Opus | Arm B — Trident |
|---|---|---|
| Validity gate (existing 82 tests) | ✅ 82/82 | ✅ 82/82 |
| Hidden acceptance (the gate) | ✅ 5/5 | ✅ 5/5 |
| Quality bonus (strict whole-word) | ✅ 1/1 | ✅ 1/1 |
| ① Corrections you'd send (primary) | 0 | 0 |
| ② Process-defect ledger | none surfaced | none to catch |
| ③ Cost | 1 subagent · ~33k tok | 4 subagents · ~148k tok (~4.5×) |

**Verdict (validity → fewer prompts/faster → quality-per-token):** tie on outcome (0 corrections each);
**Arm A wins the tiebreak** — identical 5/5 at ~⅕ the tokens.

**Takeaway:** on a well-specified feature, a single strong Opus agent already succeeds, so Trident's
harness spent ~4.5× the tokens for an identical result. The harness only earns its cost when the bare
agent would actually drift, miss an edge case, or chase an infeasible approach (cf. CF-021, CF-051).

**Verified positives (not asserted):** the design executed end-to-end with real subagents (Simba
IntentCard → Do-er AssumptionSet → Fable RATVerdict → build); the **Phase-0 gate ran a real falsifying
probe** (re-verified against local code: `NASAxyz` correctly stayed one token), and it named the right
riskiest assumption (whole-word token boundaries) before any build.

**Caveat:** Arm B's Phase-2 audit was not run — the hidden grade served as the check — so the ~4.5×
is a floor, not the full harness cost. Design implication: pick harder, drift-prone tasks to test the
thesis (see Result 02).
