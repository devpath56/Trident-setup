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

> TODO after approval: migrate all historical CFs into `failures.jsonl` (sanitized) with a
> different-model auditor pass on each (FL-cf052), and generate the first `FAILURES.md`.
