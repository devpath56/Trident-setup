// spans — derive the Do-er's `Spans` from its ACTUAL subagent tool-call transcript, not from
// the Do-er's self-narration.
//
// WHY THIS EXISTS (root-cause, not detection — house-rule 1):
// The Do-er used to hand the Auditor a `Spans` array it wrote about itself. A narrated span is a
// claim; CF-046 (narrated-vs-executed) exists to CATCH the gap between what a turn said it did and
// what it actually did — after the fact. This removes the gap at the source: the orchestrator runs
// this over the Do-er subagent's real transcript (the JSONL the surface already produces), and the
// spans the Auditor grades are EXTRACTED from executed tool calls, never authored. narrated ==
// executed by construction. It is the dep-free form of TraceRoot-style auto-instrumentation: no SDK,
// no running service — just a stdlib parser over an artifact that already exists.
//
// It reads the transcript FILE and emits a small array; it never inlines the transcript into a
// prong's context (transcripts are large — that is exactly why this is a script, not a prompt step).
//
// FIELD MAP — a reduced OpenInference span (delivers the phoenix-protocol.md TODO). Each executed
// tool call becomes one span; the Do-er run itself is the root span:
//   span.name    <- tool_use.name (with a 1-based #index so repeats are distinguishable)
//   span.input   <- tool_use.input            (truncated; a span is a pointer, not a copy)
//   span.output  <- matching tool_result.content by tool_use_id (truncated)
//   span.status  <- tool_result.is_error ? "ERROR" : "OK"
//   span.error   <- the tool_result text when is_error (else omitted)
//   role         <- "root" (the Do-er run) | "error" (is_error) | "ok"  — matches ⊘ root / ⚠ error
//   ts           <- the assistant message timestamp
// This is a strict subset of OpenInference, so a future real exporter is a field-rename, not a rewrite.
//
// Usage:
//   node prongs/spans.mjs <transcript.jsonl>            # print the spans as a JSON array
//   node prongs/spans.mjs <transcript.jsonl> --pretty   # 2-space indented
//   node prongs/spans.mjs <transcript.jsonl> --check     # exit 0 iff >=1 span extracted, print a count
import fs from 'node:fs';
import path from 'node:path';

const argv = process.argv.slice(2);
const file = argv.find((a) => !a.startsWith('--'));
const pretty = argv.includes('--pretty');
const checkOnly = argv.includes('--check');

const refuse = (why, fix) => { console.error(`REFUSED: ${why}`); if (fix) console.error(`  ${fix}`); process.exit(2); };
if (!file) refuse('no transcript path', 'usage: node prongs/spans.mjs <transcript.jsonl> [--pretty|--check]');
if (!fs.existsSync(file)) refuse(`transcript not found: ${file}`);

const MAX = 220; // a span is a pointer to the work, not a copy of it
const clip = (v) => {
  if (v == null) return '';
  let s = typeof v === 'string' ? v : JSON.stringify(v);
  s = s.replace(/\s+/g, ' ').trim();
  return s.length > MAX ? s.slice(0, MAX) + '…' : s;
};

// tool_result.content is sometimes a plain string, sometimes a list of {type:"text", text}.
const resultText = (content) => {
  if (typeof content === 'string') return content;
  if (Array.isArray(content)) {
    return content.map((c) => (c && typeof c === 'object' ? (c.text ?? JSON.stringify(c)) : String(c))).join(' ');
  }
  if (content && typeof content === 'object') return content.text ?? JSON.stringify(content);
  return '';
};

const lines = fs.readFileSync(file, 'utf8').split('\n').filter((l) => l.trim());

// Pass 1: index every tool_result by the tool_use_id it answers.
const results = new Map();
for (const l of lines) {
  let o; try { o = JSON.parse(l); } catch { continue; }
  const content = o?.message?.content;
  if (!Array.isArray(content)) continue;
  for (const c of content) {
    if (c && c.type === 'tool_result' && c.tool_use_id) {
      results.set(c.tool_use_id, { is_error: !!c.is_error, text: resultText(c.content) });
    }
  }
}

// Pass 2: one span per executed tool_use, in order. The first user turn (the task) is the root span.
const spans = [];
let firstTask = null;
let idx = 0;
for (const l of lines) {
  let o; try { o = JSON.parse(l); } catch { continue; }
  if (firstTask == null && o.type === 'user') {
    const c = o?.message?.content;
    firstTask = typeof c === 'string' ? c : Array.isArray(c) ? resultText(c) : '';
  }
  const content = o?.message?.content;
  if (o.type !== 'assistant' || !Array.isArray(content)) continue;
  for (const c of content) {
    if (!c || c.type !== 'tool_use') continue;
    idx += 1;
    const r = results.get(c.id);
    const isError = r?.is_error === true;
    spans.push({
      span: `${c.name}#${idx}`,
      input: clip(c.input),
      output: r ? clip(r.text) : '(no result recorded)',
      status: isError ? 'ERROR' : 'OK',
      ...(isError ? { error: clip(r.text) } : {}),
      role: isError ? 'error' : 'ok',
      ts: o.timestamp || '',
    });
  }
}

// The root span: the Do-er run itself. Prepended so the trace has a single ⊘ root, matching the
// CF `trace` convention and OpenInference (a root span with child tool spans under it).
const root = {
  span: 'do-er run',
  input: clip(firstTask || '(task not found in transcript)'),
  output: `${spans.length} tool call(s); ${spans.filter((s) => s.role === 'error').length} error(s)`,
  status: spans.some((s) => s.role === 'error') ? 'ERROR' : 'OK',
  role: 'root',
  ts: '',
};
const out = [root, ...spans];

if (checkOnly) {
  console.log(`ok: extracted ${spans.length} tool span(s) + 1 root from ${path.basename(file)}`);
  process.exit(spans.length >= 1 ? 0 : 1);
}
console.log(pretty ? JSON.stringify(out, null, 2) : JSON.stringify(out));
