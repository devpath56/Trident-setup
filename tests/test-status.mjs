// test-status — proves the gate dashboard cannot lie green.
//
// status.mjs's one promise is that every ✓ is validate_prongs-confirmed and a ✗ appears exactly
// where the enforcer flagged a row. A dashboard is worthless if it stays green while the ledger is
// broken (the vacuous-green trap, CF-065). This is the RAT probe for status.mjs, wired as a durable
// control instead of asserted once: copy the whole prongs dir to a temp, break the COPY, and demand
// the dashboard turn red at the broken row — the real ledger is never touched.
//
// Run:  node tests/test-status.mjs
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const HERE = path.dirname(new URL(import.meta.url).pathname);
const SRC = path.join(HERE, '..', 'prongs');

let fails = 0;
const check = (label, cond) => { console.log(`  ${cond ? 'ok  ' : 'FAIL'} ${label}`); if (!cond) fails++; };

// A throwaway repo subset so status.mjs invokes the COPIED validate_prongs against the COPIED
// ledger (both resolve relative to the script's own dir). validate_prongs also reads the failures
// SSOT at ../failures/failures.jsonl (C1b), so that dir is copied too or the clean copy goes red for
// the wrong reason. The real prongs.jsonl is never read or written.
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'status-'));
const dst = path.join(tmp, 'prongs');
fs.cpSync(SRC, dst, { recursive: true });
fs.cpSync(path.join(HERE, '..', 'failures'), path.join(tmp, 'failures'), { recursive: true });
const runStatus = () => spawnSync(process.execPath, [path.join(dst, 'status.mjs'), '--plain'], { encoding: 'utf8' }).stdout || '';

console.log('== gate dashboard: cannot lie green ==\n');

// the legend line documents the ✗ glyph, so "is there a ✗" must look at gate rows, not the legend.
const bodyHasFail = (out) => out.split('\n').filter((l) => !l.includes('enforcer flagged')).some((l) => l.includes('✗'));

// ── positive control: the untouched copy is green, no ✗ on any row ─────────────────
const clean = runStatus();
check('clean ledger → dashboard shows the PASS banner', /RESULT PASS/.test(clean));
check('clean ledger → no ✗ on any gate row (nothing flagged)', !bodyHasFail(clean));

// ── the mutant: a verdict citing an IntentCard that does not exist (C1 violation) ──
const ledger = path.join(dst, 'prongs.jsonl');
fs.appendFileSync(ledger, JSON.stringify({
  id: 'v-liar', kind: 'verdict', ts: '2026-07-20T09:00:00Z', runId: 'liar-run',
  intentCardId: 'i-does-not-exist',
  detectors: [{ detector_id: 'd', result: 'pass', signal_seen: 'x' }],
}) + '\n');

const broken = runStatus();
check('broken ledger → enforcer banner flips to FAIL',      /RESULT FAIL/.test(broken));
check('broken ledger → the PASS banner is GONE (no false green)', !/RESULT PASS/.test(broken));
check('broken ledger → a ✗ appears on a gate row (the dashboard went red)', bodyHasFail(broken));
check('broken ledger → the ✗ is on the liar verdict v-liar',
  broken.split('\n').some((l) => l.includes('✗') && l.includes('v-liar')));

fs.rmSync(tmp, { recursive: true, force: true });
console.log(`\nRESULT: ${fails ? `${fails} FAIL` : 'PASS'}`);
process.exit(fails ? 1 : 0);
