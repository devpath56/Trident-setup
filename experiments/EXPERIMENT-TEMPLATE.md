# Trident vs bare Opus — experiment result format (pre-registered)

Fill the pre-registration block **before** running. Freeze it. Then run both arms and fill the rest.
The point is honest measurement: define how we judge before we see the output (guards CF-010, CF-021).

Job under test = **shipping a medium-complexity OSS feature.**

---

## 0 · Pre-registration (frozen before the run)
| Field | Value |
|---|---|
| Feature | repo · issue # · one-line spec |
| "Medium complexity" because | ~N files touched · ≥1 design decision · ≥1 real feasibility risk |
| Acceptance criteria (the validity gate) | ☐ criterion 1 ☐ criterion 2 ☐ tests pass ☐ suite still green |
| Budget cap (identical per arm) | tokens · turns · wall-clock |
| Hypothesis | "Trident reaches an accepted feature in fewer user prompts and less wall-clock, at competitive quality-per-token." |

## Setup — measure the harness, not luck
- **Identical task, identical Do-er model (Opus), identical tools, identical budget cap.** The only
  variable is the wrapper: bare Opus (**Arm A**) vs Opus-inside-Trident (**Arm B**).
- **Blind, deterministic-anchored judge**: a model that produced neither arm scores the rubric without
  knowing which is which; the deterministic layers (tests, defect detectors) are computed mechanically
  first and the judge cannot override them (CF-010, CF-051).

## User-proxy protocol — how "user prompts" are counted
The same "user" behavior is applied to both arms so the count is fair and reproducible:
- Gives the initial spec once, verbatim, identical to both arms.
- Answers a **direct question** minimally (one line), no volunteered help.
- Issues a **correction** *only* when the arm produces something that violates a frozen acceptance
  criterion — never style nudges.
- Every user-proxy message is counted and typed: **clarification · correction · unblock.**
- Who plays it: a scripted minimal-intervention proxy (default) or you live — set in pre-registration.

## Decision hierarchy (frozen)
1. **Validity gate** — feature meets acceptance criteria + tests pass. An arm that fails this cannot win.
2. **PRIMARY — autonomy + speed** — fewer **user prompts to accepted-done**, and faster wall-clock.
3. **SECONDARY / tiebreak — quality per token** — decides only when (2) is ~tied.

---

## 1 · Autonomy & speed — PRIMARY (decides the winner)
| Metric | Arm A (Opus) | Arm B (Trident) | winner |
|---|---|---|---|
| **User prompts to accepted-done** (count) | | | fewer |
| — clarifications | | | |
| — **corrections** | | | ← Trident should cut these |
| — unblocks | | | |
| **Wall-clock to accepted-done** | | | faster |
| Your hands-on time | | | |

## 2 · Validity gate — deterministic, must pass to count
| Signal | Arm A | Arm B |
|---|---|---|
| Feature tests pass (n/total) | | |
| Full suite still green | | |
| Acceptance criteria met | ☐☐☐ | ☐☐☐ |

## 3 · Process-defect ledger — *explains* the prompt gap (run failures.jsonl detectors on both transcripts)
Each correction the user-proxy had to send in Arm A should map to a CF the harness caught in Arm B.
| CF | Failure mode | Fired in A? | Fired in B? | evidence line |
|---|---|---|---|---|
| CF-056 | built before testing feasibility | | | |
| CF-046 | narrated ≠ executed | | | |
| CF-025 | false "done" | | | |
| CF-004 | hallucinated fact/API | | | |
| CF-048 | scope padding | | | |
| … | … | | | |
| | **Total defects (fewer = better)** | **A:** | **B:** | |

## 4 · Quality — blind judge, per-dimension (0–3), each with an evidence line
| Dimension | A | B | maps to |
|---|---|---|---|
| Correctness (edge cases included) | | | — |
| Scope fidelity (no padding / no missing must-have) | | | CF-048 |
| Verification integrity (real tests, no false done) | | | CF-025, CF-046 |
| Code quality / simplicity | | | — |
| Safety (no destructive/irreversible misstep) | | | CF-013 |

## 5 · Cost & quality-per-token — SECONDARY / tiebreak
| | Arm A | Arm B |
|---|---|---|
| Tokens (in/out) | | |
| Agent-turns | | |
| Wasted tokens (discarded/infeasible paths) | | | ← the Phase-0 gate's target |
| Quality-per-token = (Layer-4 total + gate pass) ÷ tokens | | |
| Cost multiple (B ÷ A) | 1× | |

## Verdict
Apply the frozen decision hierarchy. State, concretely:
- **Winner** and the margin on the primary metric (prompts + speed).
- **Why** — tie each Arm-A correction to the CF Trident caught internally (Layer 3), so the prompt gap has a mechanism.
- **Where Trident cost more for no gain** — honest, named. (A harness that adds turns but doesn't cut user prompts is a loss under this rubric.)
