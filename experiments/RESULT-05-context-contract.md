# RESULT-05 — context-contract: verdict = FAIL (as pre-registered)

Ran the pre-registered `EXP-context-contract.md` as a real Trident loop (fresh Opus Do-er per round × 3
rounds × 2 arms; deterministic tests; independent **Fable** Auditor certified the verdict). Nothing here is
narrated — every number is from a tool call.

## Scorecard (Fable-certified, fail-closed)
| Criterion | Bar | Measured | Verdict |
|---|---|---|---|
| **P1 · efficiency** | Arm B cumulative ≤ 60% of Arm A by R3 | **68.9%** (31.1% cut) | **FAIL** |
| **P2 · intent survives** | Arm B final passes tripwire | `__proto__` → `ValueError` ✓ | PASS |
| **P3 · quality parity** | Arm B features ≥ Arm A | both **4/4** executed tests | PASS |
| **P4 · the gate works** | fires on dropped invariant, passes on intact | BLOCK lossy / PROMOTE intact | PASS |
| **OVERALL** | P1 ∧ P2 ∧ P3 ∧ P4 | — | **FAIL** |

## What actually happened
- **Efficiency didn't clear the bar at 3 rounds.** Context per round: Arm A R2=1410, R3=2601 (cum 4011);
  Arm B R2=1291, R3=1472 (cum 2763). The R3-*alone* cut is 43%, but the pre-registered metric is
  **cumulative**, and cumulative is 31%. The Auditor explicitly refused to let the R3-alone number stand in.
  Reason: at low round counts the **carried artifact (the current code) dominates**, and the discarded
  history (terse notes + prior instructions) is small — so the delta win is real but modest. The 40% cut
  needs **more rounds** or **realistic reasoning/tool-output-heavy history**, which is where accumulation
  actually explodes.
- **Safety and intent held, strongly.** Both arms preserved the `__` tripwire through all rounds. Arm B —
  the one carrying a **pinned IntentCard** — went further and *strengthened* the invariant, extending `__`
  rejection to `[section]` names; Arm A left `[__proto__]` as a gap. (Not pre-registered, so it does not
  upgrade any verdict — but it's a genuine signal that pinning intent keeps it salient.)
- **The gate is the real guarantee.** P4 is deterministic and passed cleanly: a compaction that drops the
  invariant is **blocked by construction**, independent of any single stochastic run. This is why P4, not
  P2, is load-bearing for safety.

## Honest caveats (Auditor-raised)
- **n=1 per arm** — no variance estimate; a single run can't fully separate regime effect from noise.
- **chars are a token proxy**; shared R1 seed means efficiency divergence rests on two rounds.

## Decision (faithful to the pre-registration)
- **Do NOT claim the context-contract as a proven efficiency win.** It is **proven safe and
  quality-preserving**, with a **mandatory** fail-closed gate; its efficiency payoff is **round-count- and
  history-weight-dependent** and did not materialize at 3 rounds with terse history.
- Wire it into `method.md` on those honest terms (safe + gated; efficiency conditional, with the crossover
  noted), not as a 40%-savings headline.
- **Candidate follow-up:** re-run at 6+ rounds and/or with reasoning-heavy per-round output to locate the
  efficiency crossover point. Until then, the efficiency claim stays open.

## Method that made this trustworthy
Pre-registered before running · one variable (context regime), shared seed, steelmanned baseline ·
deterministic runnable ground truth (executed, not grepped — CF-014) · design primed against `failures.jsonl`
(CF-010/014/021/051/056/004) · independent Fable auditor, fail-closed (CF-010/037). See
`references/experiment-method.md`.
