# The Trident Method — how Trident runs any task

The reusable method behind the three prongs. Everything else in this repo is an instance of it. Three
pillars: **multiple tightly-scoped loops**, **adversarial agents**, **incentive alignment.** They are not
independent features; each covers a failure the other two can't.

---

## Pillar 1 — multiple tightly-scoped loops (not one big loop)

One long context degrades (FL-cf009) and blends instruction sets (FL-cf011). So the work is split into
**many small, bounded loops**, each with its own todolist and its own isolated context. A loop is small
enough that nothing drifts inside it, and it closes on an **artifact**, never on a handoff.

- **Bounded.** Every loop has a stop rule and a retry cap (Do-er↔Auditor default 3). On exhaustion, surface
  the open `Verdict`; never loop silently, never reroute around the real failure (FL-cf016).
- **No leaks.** A prong sees only the *typed artifacts* it's handed, never another prong's scratch. This is
  the hard contract in `loop-contract.md` — it's what keeps each loop small.
- **Closes on an artifact.** A todo is `completed` only when its acceptance artifact exists (FL-cf025).
- **Phase 0 first.** No loop that builds anything runs until the riskiest-assumption probe passes
  (FL-cf056). The cheapest loop (one probe) gates all the expensive ones.

### The scored generate → re-rank loop (the reusable primitive)
When a loop has to pick a best candidate (ideas, designs, fixes, ranked anything), use this weights-agnostic
template. A task supplies the **sub-scores and their weights**; the mechanics are fixed:

1. **R1** — generate N candidates; score each on the task's weighted sub-scores; show every sub-score + one
   evidence line; keep a **top-k leaderboard** and log the rest to a **roads-not-taken** ledger (never
   silently drop a candidate).
2. **R2+** — keep top-k; generate a few **new** candidates biased toward the leader's strengths while
   **patching the leader's weakest sub-score**; **delta re-score only the new/changed** (carry the rest
   forward — the RAT delta principle applied to scoring, not just prompts).
3. **Stop** at a target score with a stall guard (e.g. ≥85 AND two rounds fail to beat best by >5), or a
   round cap. State the cap; a silently truncated search reads as "explored everything" when it wasn't.
4. **Grey-case guard** — if two sub-scores conflict (a feasibility leader that's anchor-thin), show both and
   name the tension; never launder a conflict into one number (FL-cf004, no silent substitution).

Worked instance with real weights: `pipelines/auto-research.md` Phase 2. The **mechanics live here**; a
pipeline supplies only its rubric. Change the loop mechanics here, not in each pipeline.

---

## Pillar 2 — adversarial agents (nobody grades their own work)

A single agent is optimistic about its own output (FL-cf010): it inflates 15–20 points and declares a false
pass. Trident makes the checks **adversarial**, so a claim has to survive an agent that is *trying to break
it*, not the agent that made it.

- **The judge is a different model.** The Auditor is **Fable**, never the Do-er (Opus). It grades the
  artifact, and it never saw the Do-er's reasoning, so it can't be talked into grading the effort.
- **Refute-by-default.** The Auditor **fails closed**: any claim it can't verify is a fail, not a pass. On a
  hard question, spin independent skeptics and kill the claim unless a majority survives.
- **Deterministic before judged.** Checks run in a fixed order — deterministic (string/grep/schema) →
  structural (acceptance test) → rubric LLM-judge, only for what code can't reach. Never free-form
  self-assessment (FL-cf051, FL-cf010). Push every new detector as high up that ladder as it will go.
- **A loyal counterweight.** Simba reads your intent and the Do-er's *result* and adversarially asks "does
  this still match what the user asked?" — the drift the Auditor's detectors don't cover.

Effect, measured live: under independent auditing nothing crossed ~82; a single self-scoring Opus inflated
its own winner to 86.7 and stopped. The adversary is the difference between an honest score and a flattering
one.

---

## Pillar 3 — incentive alignment (each prong is loyal to a different thing)

Adversarial checks only stay honest if the checkers **can't be captured**. So each prong is deliberately
pointed at a *different* master, and no prong can both do the work and bless it.

| Prong | Loyal to | Must NOT | Why the incentive is split |
|---|---|---|---|
| **Do-er** (Opus) | shipping the task | grade its own output | the maker is the optimist; keep it off the scorecard |
| **Simba** | *you* (the user) | read the Do-er's reasoning, or act on drift itself | if it saw the reasoning it could be argued out of your intent; it stays your memory, not the Do-er's |
| **Auditor** (Fable) | the artifact + the failures log | be the Do-er's model, or grade effort | a different model can't rationalize its own work |

- **Separation of powers.** *"Simba proposes, the Auditor disposes."* Simba detects drift and emits a
  `DriftFlag`; it never edits, never argues, never halts. The Auditor holds the single point of authority
  over the response. One prong finding a problem, a different prong deciding — neither can quietly wave work
  through.
- **The shared incentive is the failures log.** All three read and write one SSOT (`failures.jsonl`). A prong
  is rewarded for turning a real mistake into a check that stops it recurring — so the incentive is to make
  the *next* run better, not to look good on this one. The suite only grows from real errors.
- **Cost is earned, not assumed.** All three prongs fire every loop; the extra round-trips are justified only
  if quality earns them (the experiment's quality-per-token tiebreak is exactly this test).

---

## The method in one line
**Split the work into small bounded loops; in each, let an agent loyal to a different master try to break the
result; and settle every dispute through one authority over one shared failures log** — so drift is caught
early, optimism can't self-certify, and every real mistake becomes a permanent check.

See also: `loop-contract.md` (the no-leak isolation that keeps loops small), `evaluators.md` (CF → check
method), `phoenix-protocol.md` (the eval shapes), `house-rules.md` (the cross-cutting rules every prong obeys).
