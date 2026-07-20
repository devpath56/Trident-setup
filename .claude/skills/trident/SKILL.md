---
name: trident
description: Wrap a working session in a three-prong quality harness — a Do-er (Opus) watched by Simba (durable intent memory + drift detector) and an Auditor (Sonnet 5; deterministic evaluators first, LLM-judge second), over one failures-log SSOT. Trigger on "invoke trident", "run trident", "audit this work"; and — always — owns the normalized "log failure" trigger that appends the next CF-### to the SSOT. Claude Code / VS Code only (spawns real subagents).
---

# trident — the orchestrator

> The reusable method (tightly-scoped loops · adversarial agents · incentive alignment) + the scored
> generate→re-rank primitive: `../references/method.md`.
> Cross-cutting rules live in `../references/house-rules.md` — change them there, never here.
> No-leak isolation: `../references/loop-contract.md`. Eval shapes: `../references/phoenix-protocol.md`.

## Conceptual loop
0. **Phase 0 — riskiest-assumption gate (before ANY build).** Simba → `IntentCard`; Do-er → `AssumptionSet`;
   Auditor → `RATVerdict` (riskiest by kill-power × uncertainty + cheapest probe); Do-er runs the probe.
   **Hard block: no build until it passes.** On fail → stop, report, `log failure`.
1. **Build** — Do-er works only past the gate → `Output` + `Spans`.
2. **Audit** — Simba drift-checks the `Output`; Auditor runs detectors → `Verdict` (deterministic → structural → judge).
3. **Correct** — on fail, the Auditor runs **RCA-on-fail** (localize the span + root cause → an `rca`
   proposal), then re-dispatch the Do-er with that localized primer; bounded retries (max 3).
4. **Close** — on pass, surface to the user; on a NEW failure mode, `log failure`.

## Runbook — what to do when the user says `invoke trident`
**You (this session) are the orchestrator.** You hold no prong's private context; you only pass the
typed artifacts between subagents. Subagents can't spawn subagents, so never wrap the whole harness in
one subagent — orchestrate from here. Keep a todolist of the phases below.

Models: **Simba** = Sonnet 5 · **Do-er** = Opus · **Auditor** = Sonnet 5 (never the Do-er's model).
Simba and the Auditor share a model, so the two watcher prongs are correlated — the no-self-grading invariant
still holds (both grade the Opus Do-er's Output, neither grades its own work), and deterministic detectors
carry the real decorrelation. Simba stays independent of the build by reading Output-only, never the Do-er's
reasoning (PD-006).

**Phase 0 — RAT gate**
0. **Simba ASKS the user their intent — first, always, before anything else** (house-rule 15, PD-007).
   - Spawn **Simba** in *ask mode*: it reads their messages only to find the **gaps**, then returns
     **2–4 questions** — and **question 1 is always "what's the scope for this session?"**, pulling
     both `in_scope` and `out_of_scope`. Every other question is a decision that changes what gets built.
   - Put those questions to the user and **wait**. Do not spawn the Do-er, do not rank assumptions,
     do not build. An unanswered intent question is a hard block.
   - Reading an inferred goal back for confirmation is **not** asking — it anchors them to the guess.
1. Spawn **Simba** again with the user's *answers* + their messages as corroboration.
   → returns `IntentCard` {intent_source, goal, must_haves, forbid, pinned_feedback, intent_riskiest}.
   - `intent_source` must be `asked`. If it is `inferred`, the Auditor **fails closed** → return to step 0.
   - **Exception, narrowly scoped** (house-rule 15) — an instruction to skip the ask counts only if it:
     (a) names *skipping the intent question* specifically — a generic "go ahead", "ok", or "do it" is
     **not** a waiver and must never be read as one; (b) is scoped to the decision at hand, **never** a
     standing waiver for the session; and (c) is re-confirmed when a materially new decision arises that
     the original instruction did not cover. Record the instruction verbatim in `pinned_feedback`.
2. Spawn **Do-er** (Opus): input = the task. → returns `AssumptionSet` — every capability/platform/feasibility
   assumption, each tagged {type, kill_power 1–5, uncertainty 1–5}. **It does not build yet.**
3. Spawn **Auditor** (Sonnet 5): input = `AssumptionSet` + `IntentCard`. → returns `RATVerdict`
   {riskiest (max kill_power × uncertainty), probe (the smallest command/read that could prove it impossible), pass_criteria}.
   - **Record it with `node prongs/rat.mjs --run <id> --phase <name> --push proceed|hold --riskiest "..." --probe "..."`.**
     The RAT is the phase-opener: a phase has started only once its RATVerdict exists (there is no
     separate "phase" object to gate, the RAT IS the boundary). rat.mjs refuses placeholders.
4. Run the probe (directly, or a scoped Do-er). Evaluate against `pass_criteria`. Log its result as a `probe` row.
5. **GATE:** fail → **STOP**, report to the user, `log failure`. pass → continue. *(Never skip this.)*
   - **Enforced deterministically:** `validate_prongs.py` HR-0 rejects any `probe` row with no
     `ratverdict` before it in the same run. Nothing can be built or probed before its RAT.

**Prior-art & capability separation (PD-015 / PD-016) — the two token-leak fixes:**
- **Reuse-first (PD-015):** before a *build* RAT opens, run an in-repo reuse scan (`grep` for the
  capability) and record the result on the RATVerdict as `prior_art.reuse` — the order is
  **reuse > buy > build**. `validate_prongs.py check_prior_art` forward-gates: a post-cutoff
  `ratverdict` with no `prior_art.reuse` fails. Buy-search is triage-gated — reach for it only when
  reuse finds nothing *and* the build is non-trivial.
- **Design prongs are read-only (PD-016):** Simba/Auditor design artifacts (`ratverdict` / `intent` /
  `assumptions`) SPECIFY a probe; the orchestrator (or a build prong) EXECUTES it. Spawn design
  prongs **without Bash**. `validate_prongs.py check_design_prong_no_execution` backstops: a design
  artifact whose spans include an execution (Bash) span fails — a reasoning agent must not spend 82k
  running a probe a 2k orchestrator bash call should own.

**Every phase opens with its own RAT, not just Phase 0.** Phase 1 (build), Phase 2 (audit), and
each correction round (Phase 3) each run rat.mjs first with their own `--phase`: the same three
first-principles adversarial questions (should I build this? what is the riskiest assumption I am
missing? what is the cheapest probe to falsify it?) before a line of that phase is written.
**Enforced:** every work artifact (a `probe` for Phase 0, a `verdict` for audit/correct) carries a
`phase`, and `validate_prongs.py` HR-0 rejects any that has no RATVerdict for that same phase before
it. A single Phase-0 RAT no longer covers the run. Forward-only: work predating the gate is exempt.

**Every phase that SHIPPED A GUARD closes with `/prove-durable` (PD-017) — the bookend to HR-0.**
If a phase produced a `verdict` that `resolves` a CF (a real fix, which by Trident discipline becomes
a check), that fix must be shown *durable* before the phase closes: **revert the fix and confirm a
named control flips red.** Record it as a `durability` row {`verdictId` → the resolving verdict,
`reverted` → the fix undone, `control_flipped` → the control that went red}. **Enforced:**
`validate_prongs.py check_durability_gate` rejects a resolves-verdict with no matching durability
record. **Conditional by design** — it fires ONLY on guard-shipping phases, so a RAT or a clean audit
(no fix) closes without ceremony (no-op ban). Pre-emptive guards (PDs) are exempt here because
mutation (`mutate.py`) already proves each new check is killed by its own control; this gate covers
the class mutation cannot — reverting the *actual fix in the actual file* and confirming the *real*
suite flips (the fix-and-guard-revert-together leak). Forward-only from the cutoff.

**Phase 1 — Build**
6. Spawn **Do-er** (Opus): input = task + `IntentCard` (honor must_haves / forbid / pinned_feedback).
   → returns `Output` (the diff/result). The Do-er's `Spans` are **not** taken from its self-narration:
   derive them from the Do-er subagent's **actual tool-call transcript** with
   `node prongs/spans.mjs <transcript.jsonl>` (reduced OpenInference spans; ⊘ root / ⚠ error). narrated ==
   executed by construction — the CF-046 gap cannot open because the trace is captured, not authored. The
   extractor reads the transcript FILE; never paste the transcript into a prong's context.

**Phase 2 — Audit**
7. Spawn **Simba**: input = `Output` + `IntentCard` (Output only — never the Do-er's reasoning).
   → returns `DriftFlag` {drifted_from, evidence} or "no drift".
8. Spawn **Auditor** (Sonnet 5): input = `Output`, the **extracted `Spans`** (from `prongs/spans.mjs`, step 6),
   `DriftFlag`, and the active detectors from `failures/failures.jsonl`. Order: deterministic → structural →
   (only if needed) rubric-judge; **fail closed**.
   → returns `Verdict` [{detector_id, pass|fail, signal_seen, span_ref?}] — on a fail, `span_ref` names the
   Spans entry that produced the signal (the exact failing span), so Phase 3 corrects a location, not a guess.

**Phase 3 — Correct (max 3 rounds)**
9. If `Verdict` has fails → **RCA first, then re-dispatch. RCA is COMPULSORY on any fail, not optional.**
   - **RCA:** spawn the **Auditor** in RCA-on-fail mode — `node prongs/compose-rca.mjs <runId>` (refuses
     with no failing verdict). It localizes the failing span, names the root cause, and emits an `rca`
     row `{…, target: output|harness, gate:"proposal"}`. Fail-closed: an RCA is a proposal, never an
     auto-fix (house-rule 1).
   - **Enforced (PD-018):** this was doctrine but only a *reminder* — a rule in a SKILL file is a
     reminder, only an executed check is a gate. `validate_prongs.py check_rca_on_fail` now makes it a
     GATE: a verdict with a failing detector must be met by an `rca` that diagnoses it **or** an
     `override` that explicitly accepts it — neither is an un-diagnosed fail, and it rejects the ledger.
     This is what forces you to **fix the diagnosis, not the symptom**: no jumping from a fail straight
     to a patch without a recorded root cause. (Forward-only.)
   - **Re-dispatch (target=output):** spawn a fresh **Do-er** with the RCA's `fix_hypothesis` — the
     *specific* failing detector **plus the span and the cause** (a localized primer, not "try again",
     FL-cf007). Re-run Phase 2. Repeat ≤3. On exhaustion → surface the open `Verdict` + `rca` to the
     user; never loop silently (FL-cf016).
   - **Self-heal (target=harness):** if the RCA finds a mode the harness should have caught, route its
     proposal through `log failure` (Auditor-approves → commit) — the compounding loop, landing a
     *proposal*, never an auto-commit.

**Phase 4 — Close**
10. On pass → surface `Output` to the user. If a NEW failure mode appeared that no CF covers → `log failure`.

## Trigger: `log failure` (and variants) — the SSOT owner
Normalize to intent (FL-cf026): `log failure` = `log fail` = `log this failure` = `log the fail` = `record failure`.
1. Locate the SSOT `failures/failures.jsonl` in the **Trident repo**. If it's not in session scope, say so
   in one line and stop — don't write a divergent copy (FL-cf034).
2. Read the **last line only** for max `CF-###`; next id = max + 1 (never full-read, never reuse).
3. Append one **sanitized** record (schema: `failures/schema.json`). Personal specifics go to
   `failures.local.jsonl` (gitignored), never the committed line (FL-cf013, FL-cf052).
4. **Auditor approves** the record (schema-valid, detector deterministic-where-possible, no personal data).
5. `python3 tests/selftest.py` must pass, then commit + push the SSOT to the Trident repo.
6. Confirm back: `logged CF-### (<title>)` — a silent skip is impossible (FL-cf046).

## Trigger: `log decision` (and variants) — the META-scoped decisions ledger
Normalize to intent: `log decision` = `log a decision` = `record decision` = `log this as a decision`.
This writes a `PD-###` to `failures/decisions.jsonl` — a *pre-emptive design decision about Trident
itself*, **not** an observed failure and **not** an object-level decision from a session Trident is watching.
1. **Meta-scope check first.** A decision is loggable here ONLY if it changes Trident's **own** design tree
   (`.claude/skills/`, `failures/`, `tests/`, core root docs). A decision about the app/work being watched
   does **not** go here — say so in one line and stop. This is the whole point of the ledger being separate.
2. Number from the last `PD-` line (separate space from `CF-`); draft the record (schema:
   `failures/decisions.schema.json`) with `scope: "trident-meta"`, an `authority`, a `detector`, the
   `applied_in` files, and a `promotion_trigger`.
3. **Gate (deterministic, fail-closed):** `python3 failures/validate_decisions.py` must pass — it rejects
   any PD whose `applied_in` escapes the design tree or doesn't exist on disk. Then `python3 tests/selftest.py`.
4. Auditor approves; append, commit, push. Confirm `logged PD-### (<title>)`.
5. **Promotion:** a PD becomes a real `CF-###` only when its `promotion_trigger` is actually observed —
   then run `log failure` with `related: [PD-xxx]` and set the PD `status: promoted` (`references/failures-log.md`).

## Surface
Claude Code / VS Code only — the loop spawns real subagents (Do-er, Sonnet 5 Auditor, Simba). With this
repo in scope, `log failure` appends → Auditor-approves → commits + pushes the SSOT. Never claim a write
happened if it didn't (FL-cf046). `log decision` is the meta-scoped sibling — Trident's own design only,
gated by `validate_decisions.py`.

## Output shape (house-rule 16)
Every Trident-authored surface — orchestrator reports, `IntentCard`, `AssumptionSet`, `RATVerdict`,
`Verdict`, `DriftFlag` — is **nested bullets or tables only**.
- No prose paragraphs, no essay narration, no scene-setting.
- A field that needs explaining gets a **sub-bullet**, not a sentence of commentary.
- Comparisons, per-detector results, and assumption rankings go in a **table**.
- Why: prong outputs are artifacts that get diffed between loops; prose hides structure and lets an
  unattributed claim ride along as if it were a finding.

## Hard guardrails (do not break)
- **Ask intent before you infer it** — Simba owns step 0 of every new session (house-rule 15, PD-007).
- **Nested bullets and tables only** in every prong output (house-rule 16).
- No build, no deps — installs as a plain skills tree; orchestration uses subagents (Claude Code / VS Code).
- No personal data or external paths in any committed record — re-scan before commit.
- Deterministic detectors before any LLM-judge (FL-cf051). The judge (Sonnet 5) is never the Do-er (Opus).
- Phase 0 is a hard gate — no build before the riskiest-assumption probe passes (FL-cf056).
