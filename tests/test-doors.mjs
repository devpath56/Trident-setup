// test-doors — exercises the session doors (open / compose / close) end to end against a
// THROWAWAY ledger, so the guarantees the doors claim are proven every run instead of trusted.
//
// prove-durable found open/close/compose-session were ORPHANS: real gates that nothing
// invoked, so they would rot. This is the trigger that makes them durable. Removing any door
// script now fails selftest (selftest runs this), which is the whole definition of durable.
//
// Isolation: PRONGS_PATH points every door at a temp file (Phase 0 probe p-durable). The real
// prongs/prongs.jsonl is never touched.
//
// Run:  node tests/test-doors.mjs
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const HERE = path.dirname(new URL(import.meta.url).pathname);
const P = (f) => path.join(HERE, '..', 'prongs', f);
const ledger = path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'doors-')), 'prongs.jsonl');

const run = (script, args) =>
  spawnSync(process.execPath, [P(script), ...args],
    { encoding: 'utf8', env: { ...process.env, PRONGS_PATH: ledger } });

let fails = 0;
const check = (label, cond) => { console.log(`  ${cond ? 'ok  ' : 'FAIL'} ${label}`); if (!cond) fails++; };
const append = (o) => fs.appendFileSync(ledger, JSON.stringify(o) + '\n');

console.log('== session doors: open / compose / close, isolated ledger ==\n');

// ── open-session refusals (each control must exit 2) ──────────────────────────
check('open REFUSES with no goal',
  run('open-session.mjs', ['--run', 'r', '--in', 'a', '--out', 'b']).status === 2);
check('open REFUSES with empty out_of_scope (a scope with no exclusions is not a scope)',
  run('open-session.mjs', ['--run', 'r', '--goal', 'a real goal here', '--in', 'a']).status === 2);
check('open REFUSES a placeholder goal',
  run('open-session.mjs', ['--run', 'r', '--goal', 'TBD', '--in', 'a', '--out', 'b']).status === 2);

// ── open accepts a well-formed session (positive control) ─────────────────────
const opened = run('open-session.mjs',
  ['--run', 'r', '--goal', 'prove the doors hold end to end', '--in', 'the doors', '--out', 'everything else']);
check('open ACCEPTS a well-formed session', opened.status === 0);
check('open REFUSES reopening the same run (goal cannot be silently swapped)',
  run('open-session.mjs', ['--run', 'r', '--goal', 'a different goal', '--in', 'x', '--out', 'y']).status === 2);

const intentId = (fs.readFileSync(ledger, 'utf8').split('\n').filter(Boolean)
  .map((l) => JSON.parse(l)).find((x) => x.kind === 'intent' && x.runId === 'r') || {}).id;

// ── compose-auditor is the C1 root-cause gate ─────────────────────────────────
check('compose REFUSES with no IntentCard (exit 2)',
  run('compose-auditor.mjs', ['no-such-run']).status === 2);
check('compose EMITS a prompt once an IntentCard exists',
  run('compose-auditor.mjs', ['r']).status === 0);

// ── close-session refusals ────────────────────────────────────────────────────
check('close REFUSES with no verdict', run('close-session.mjs', ['r']).status === 1);

// a verdict citing a DIFFERENT card must not satisfy close
append({ id: 'v-wrong', kind: 'verdict', ts: '2026-07-20T00:00:00Z', runId: 'r',
         intentCardId: 'i-nonexistent', detectors: [{ detector_id: 'd', result: 'pass', signal_seen: 'x' }] });
check('close REFUSES a verdict citing the wrong IntentCard', run('close-session.mjs', ['r']).status === 1);

// the real verdict, citing the real card
append({ id: 'v-right', kind: 'verdict', ts: '2026-07-20T00:01:00Z', runId: 'r',
         intentCardId: intentId, detectors: [{ detector_id: 'd', result: 'pass', signal_seen: 'observed' }] });
check('close SUCCEEDS once a verdict cites the real IntentCard', run('close-session.mjs', ['r']).status === 0);

fs.rmSync(path.dirname(ledger), { recursive: true, force: true });
console.log(`\nRESULT: ${fails ? `${fails} FAIL` : 'PASS'}`);
process.exit(fails ? 1 : 0);
