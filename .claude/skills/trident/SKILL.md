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
3. **Correct** — on fail, return the *specific* failing detector to the Do-er; bounded retries (max 3).
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

**Every build phase opens with its own RAT.** Phase 1 and each correction round (Phase 3) each
run rat.mjs first: the same three first-principles adversarial questions (should I build this? what
is the riskiest assumption I am missing? what is the cheapest probe to falsify it?) before a line
of that phase is written. A new phase with a new risk gets a new RAT.

**Phase 1 — Build**
6. Spawn **Do-er** (Opus): input = task + `IntentCard` (honor must_haves / forbid / pinned_feedback).
   → returns `Output` (the diff/result) + `Spans` (short trace; mark ⊘ root / ⚠ error).

**Phase 2 — Audit**
7. Spawn **Simba**: input = `Output` + `IntentCard` (Output only — never the Do-er's reasoning).
   → returns `DriftFlag` {drifted_from, evidence} or "no drift".
8. Spawn **Auditor** (Sonnet 5): input = `Output`, `Spans`, `DriftFlag`, and the active detectors from
   `failures/failures.jsonl`. Order: deterministic → structural → (only if needed) rubric-judge; **fail closed**.
   → returns `Verdict` [{detector_id, pass|fail, signal_seen}].

**Phase 3 — Correct (max 3 rounds)**
9. If `Verdict` has fails → spawn a fresh **Do-er** with the *specific* failing detector(s) to fix; re-run Phase 2.
   Repeat ≤3. On exhaustion → surface the open `Verdict` to the user; never loop silently (FL-cf016).

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
