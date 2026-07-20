// test-spans — exercises prongs/spans.mjs against a THROWAWAY transcript so the extractor's
// guarantees are proven every run, not trusted. Removing spans.mjs (or gutting it) fails selftest,
// which is what makes the "narrated == executed" span source durable (same discipline as test-doors).
//
// The point being defended (Change 2 / CF-046): the Auditor's `Spans` must come from EXECUTED tool
// calls, not the Do-er's narration. So the controls assert exactly that: a tool call that happened
// shows up as a span; an error result surfaces as role "error"; and — the discrimination that makes
// this a test and not a mirror — a transcript whose result is NOT an error yields NO error span.
//
// Run:  node tests/test-spans.mjs
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const HERE = path.dirname(new URL(import.meta.url).pathname);
const SPANS = path.join(HERE, '..', 'prongs', 'spans.mjs');
const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'spans-'));

let fails = 0;
const check = (label, cond) => { console.log(`  ${cond ? 'ok  ' : 'FAIL'} ${label}`); if (!cond) fails++; };

// Build a minimal transcript in the REAL shape: assistant lines carry tool_use blocks; user lines
// carry tool_result blocks matched by tool_use_id; one result is an error.
const transcript = (errored) => [
  { type: 'user', message: { content: 'Do the task: build the thing and run the check.' }, timestamp: '2026-07-20T00:00:00Z' },
  { type: 'assistant', message: { content: [{ type: 'text', text: 'On it.' }] }, timestamp: '2026-07-20T00:00:01Z' },
  { type: 'assistant', message: { content: [{ type: 'tool_use', id: 'tu-1', name: 'Bash', input: { command: 'make build' } }] }, timestamp: '2026-07-20T00:00:02Z' },
  { type: 'user', message: { content: [{ type: 'tool_result', tool_use_id: 'tu-1', is_error: false, content: 'build ok' }] }, timestamp: '2026-07-20T00:00:03Z' },
  { type: 'assistant', message: { content: [{ type: 'tool_use', id: 'tu-2', name: 'Bash', input: { command: 'make test' } }] }, timestamp: '2026-07-20T00:00:04Z' },
  { type: 'user', message: { content: [{ type: 'tool_result', tool_use_id: 'tu-2', is_error: errored, content: errored ? 'FAIL: 1 test failed' : 'all tests passed' }] }, timestamp: '2026-07-20T00:00:05Z' },
].map((o) => JSON.stringify(o)).join('\n') + '\n';

const write = (name, body) => { const p = path.join(dir, name); fs.writeFileSync(p, body); return p; };
const spans = (p, extra = []) => {
  const r = spawnSync(process.execPath, [SPANS, p, ...extra], { encoding: 'utf8' });
  return { status: r.status, out: r.stdout, err: r.stderr };
};

console.log('== span extractor: derive Spans from an executed transcript ==\n');

// ── refusal control: no transcript file → exit 2 ──────────────────────────────
check('REFUSES a missing transcript (exit 2)', spans(path.join(dir, 'nope.jsonl')).status === 2);

// ── the errored transcript ────────────────────────────────────────────────────
const errPath = write('err.jsonl', transcript(true));
const er = spans(errPath);
check('emits valid JSON (exit 0)', er.status === 0);
const arr = er.status === 0 ? JSON.parse(er.out) : [];
const tool = arr.filter((s) => s.role !== 'root');

check('prepends exactly one root span', arr.filter((s) => s.role === 'root').length === 1);
check('extracts one span per EXECUTED tool call (2 tool_use blocks → 2 spans)', tool.length === 2);
check('a tool call that happened appears as a span (Bash#1 executed)', tool.some((s) => s.span === 'Bash#1'));
check('the input is the REAL executed input (make build), not a narration',
  tool.some((s) => s.input.includes('make build')));
check('an error tool_result surfaces as role "error" / status "ERROR"',
  tool.some((s) => s.role === 'error' && s.status === 'ERROR'));
check('the root span rolls up the error (status ERROR)',
  arr.find((s) => s.role === 'root')?.status === 'ERROR');

// ── discrimination control: flip the error off → NO error span ────────────────
const okPath = write('ok.jsonl', transcript(false));
const okArr = JSON.parse(spans(okPath).out);
check('CONTROL: a transcript with no error result yields NO error span',
  !okArr.some((s) => s.role === 'error'));
check('CONTROL: the same run\'s root span rolls up OK when nothing errored',
  okArr.find((s) => s.role === 'root')?.status === 'OK');

// ── --check mode: exit 0 iff >=1 tool span ────────────────────────────────────
check('--check exits 0 when tool spans exist', spans(okPath, ['--check']).status === 0);
const noTools = write('empty.jsonl',
  JSON.stringify({ type: 'user', message: { content: 'just a message, no tools' }, timestamp: 't' }) + '\n');
check('--check exits nonzero when the transcript has no tool calls', spans(noTools, ['--check']).status !== 0);

fs.rmSync(dir, { recursive: true, force: true });
console.log(`\nRESULT: ${fails ? `${fails} FAIL` : 'PASS'}`);
process.exit(fails ? 1 : 0);
