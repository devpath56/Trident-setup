# Failures log — the SSOT, its schema, and the `log failure` protocol (SKELETON)

One file, one truth: `failures/failures.jsonl`. Cross-session, git-tracked, JSONL.

## Why JSONL (not a JSON array, not one big markdown file)
- **Append is one line.** A JSON array or a markdown file must be re-read and rewritten to add an
  entry — the "big file" cost. JSONL appends; numbering reads only the last line.
- **Machine-readable** for the Auditor's detectors; the `trace` field is a Phoenix-shaped span array.
- **Clean diffs** — one changed line per entry.
- A human-readable `FAILURES.md` is **generated** from the JSONL, never hand-edited.

## Record schema
Authoritative: `failures/schema.json`. Required fields: `id, title, tags, status, guard, pattern,
detector`. `detector` = `{kind, check, signal}` with `kind ∈ deterministic|structural|llm-judge|hybrid`.
Optional: `date, related, pm_implication, trace, origin`.

## Numbering (never slows as the log grows)
`id = CF-(max existing + 1)`, from the **last line only** (or `tail`). Never full-read to number.
Never reuse a number. One record per distinct failure.

## The `log failure` protocol (owned by the `trident` skill)
1. Normalize the trigger (`log failure` = `log fail` = `record failure` …) — FL-cf026.
2. Confirm the Trident repo (holding this SSOT) is in scope. If not: say so, stop (no divergent copy).
3. Draft the record from the incident. **Sanitize:** the committed line has no names, paths, or company
   references. Raw specifics → `failures.local.jsonl` (gitignored) if you want them kept privately.
4. Push the detector as high up the ladder as possible (deterministic > structural > judge > reminder).
5. Auditor approves (schema-valid, detector present, no personal data).
6. Append the line, commit, push. Confirm `logged CF-### (<title>)` to the user (FL-cf046 — no silent skip).

## Public/private split
- `failures.jsonl` — committed, sanitized, the shippable IP (pattern + guard + detector + pm_implication).
- `failures.local.jsonl` — gitignored, raw incidents. Never leaves the machine unless you say so.

## Observed vs pre-emptive (the CF / PD split)
The CF SSOT only ever grows from a **real observed failure** — never a hypothetical (the core discipline).
Forward-looking design decisions that pre-empt a *predicted* failure — typically informed by an external
authority — go in a **parallel ledger**, never into `failures.jsonl` masquerading as an incident:
- `decisions.jsonl` (schema: `decisions.schema.json`) — `PD-###` records. Each carries the `guard`, a
  `detector` (so it is promotable), the `authority` that grounds it, and a `promotion_trigger`: the exact
  observed event that would convert it into a real CF.
- **Promotion:** when a PD's `promotion_trigger` actually fires, append a normal `CF-###` via the `log
  failure` protocol (`related: [PD-xxx]`) and set the PD's `status: promoted`. That is the only path a
  pre-emptive decision becomes a guarded failure. The CF number space and the PD number space never mix.

### The meta-scope is a WIRED gate, not a reminder (`validate_decisions.py`)
The decisions ledger records decisions about **Trident itself**, never object-level decisions from a
session Trident is watching. This is enforced deterministically, fail-closed, by
`failures/validate_decisions.py` (dependency-free; run standalone and inside `tests/selftest.py`):
- **Repo identity** — refuses unless run in the Trident source repo (marker files present).
- **Meta-scope** — every PD's `applied_in` path must be inside Trident's own design tree
  (`.claude/skills/`, `failures/`, `tests/`, core root docs) **and exist on disk**; a path pointing at a
  watched app's source is an object-level decision and is rejected. `scope` must be `"trident-meta"`.
- **Detector reality** — the PD-001 binary-verdict detector is exercised against a clean fixture and a
  known-bad numeric control that MUST fail; the meta-scope gate is exercised against an out-of-scope PD
  that MUST be rejected. A gate that never fires is not a gate (CF-060).
Widen the allowed design tree only when Trident genuinely grows a new home — it is one list in the
validator, deliberately small so the ledger cannot drift into a general-purpose decision log.

> TODO after approval: migrate all historical CFs into `failures.jsonl` (sanitized) with a
> different-model auditor pass on each (FL-cf052), and generate the first `FAILURES.md`.
