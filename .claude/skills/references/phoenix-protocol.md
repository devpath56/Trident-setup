# Phoenix protocol — the eval shapes Trident borrows (SKELETON)

We are pure-skill, so Trident does **not execute** `phoenix.evals`. It adopts Arize Phoenix's *shapes*
so that (a) the design is grounded in a real, current eval framework rather than invented, and (b) the
same records pipe into a live Phoenix instance later with no reshaping (the optional Python harness,
out of scope by the pure-skill decision).

## The four Phoenix capabilities → Trident equivalents
| Phoenix | Trident equivalent |
|---|---|
| **Tracing** (OTel/OpenInference spans: input, output, status, error, tokens) | the Do-er's `Spans`; the CF `trace` field |
| **Evaluation** (code-based / LLM-based / human-label evaluators) | the Auditor's deterministic+structural / Sonnet 5-judge / your approval |
| **Datasets** (curate failure cases) | `failures.jsonl` — the curated failure SSOT |
| **Experiments** (run evaluators over a dataset) | re-running detectors over the SSOT as a regression suite (`tests/`) |

## The loop is the same loop
Phoenix: **trace → evaluate → curate failures into a dataset → iterate on prompts.**
Trident: Do-er traces → Auditor evaluates → new failure logged to the SSOT → guards/detectors iterate.

## Span shape (OpenInference-compatible)
A CF `trace` entry — `{span, note, role}` — is a reduced OpenInference span. The `role: root|error|ok`
marks the root-cause and error spans, matching your existing `⊘ root / ⚠ error` convention. This is
deliberately a strict subset of the OpenInference schema so a future exporter is a field-rename, not a rewrite.

## The extractor is real: `prongs/spans.mjs` (delivers the field map below)
The Do-er's `Spans` are **not** self-narrated — they are extracted from its executed subagent transcript by
`prongs/spans.mjs` (stdlib Node, no SDK). This is the dep-free form of TraceRoot-style auto-instrumentation:
narrated == executed by construction, so the CF-046 gap cannot open (root-cause, not detection — house-rule 1).

Field map — one executed tool call → one reduced OpenInference span; the Do-er run is the root span:
| OpenInference span field | source in the transcript |
|---|---|
| `span` (name) | `tool_use.name` + a 1-based `#index` (repeats stay distinct) |
| `input` | `tool_use.input` (clipped — a span points at the work, it does not copy it) |
| `output` | the matching `tool_result.content` by `tool_use_id` (clipped) |
| `status` | `tool_result.is_error ? "ERROR" : "OK"` |
| `error` | the `tool_result` text when `is_error` (else omitted) |
| `role` | `root` (the Do-er run) · `error` (is_error) · `ok` — the `⊘ root / ⚠ error` convention |
| `ts` | the assistant message `timestamp` |

Exercised by `tests/test-spans.mjs` (wired into `tests/selftest.py`), including the discrimination control
that a non-error result yields no error span. A real Phoenix exporter is now a field-rename over this shape.

Sources (current Phoenix feature set, retrieved 2026-07):
- Arize Phoenix docs — <https://arize.com/docs/phoenix>
- Phoenix tracing + evaluations guide (2026) — <https://qaskills.sh/blog/arize-phoenix-llm-observability-tracing-evaluations-2026>
