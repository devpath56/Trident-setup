// test-impact — proves the outward-impact ratchet actually discriminates, and is durable.
//
// impact.py's promise: under --strict it exits 1 when a headline number regresses vs the committed
// baseline, and 0 when it holds. A ratchet that never fails is a scoreboard pretending to be a gate.
// This is the RAT probe wired as a durable control (the census_durability.py-as-subprocess pattern):
// seed a baseline on a crafted GENUINE ledger, then mutate a COPY and demand --strict flip. The real
// prongs.jsonl and the committed impact-baseline.json are never touched (--ledger + --baseline isolate).
//
// Run:  node tests/test-impact.mjs
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const HERE = path.dirname(new URL(import.meta.url).pathname);
const IMPACT = path.join(HERE, 'impact.py');

let fails = 0;
const check = (label, cond) => { console.log(`  ${cond ? 'ok  ' : 'FAIL'} ${label}`); if (!cond) fails++; };

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'impact-'));
const ledger = path.join(tmp, 'ledger.jsonl');
const baseline = path.join(tmp, 'baseline.json');
const row = (o) => JSON.stringify(o);
// two genuine runs (intent+close), both audited with a passing verdict.
const genuine = (rid) => [
  row({ id: `i-${rid}`, kind: 'intent', ts: `2026-07-20T0${rid}:00:00Z`, runId: rid, intent_source: 'asked' }),
  row({ id: `v-${rid}`, kind: 'verdict', ts: `2026-07-20T0${rid}:01:00Z`, runId: rid, intentCardId: `i-${rid}`,
        detectors: [{ detector_id: 'x', result: 'pass', signal_seen: 'ok' }] }),
  row({ id: `c-${rid}`, kind: 'close', ts: `2026-07-20T0${rid}:02:00Z`, runId: rid, verdictId: `v-${rid}` }),
].join('\n');

const impact = (args) => spawnSync('python3', [IMPACT, '--ledger', ledger, '--baseline', baseline, ...args],
  { encoding: 'utf8' });

console.log('== outward-impact ratchet: discriminates + durable ==\n');

// ── seed a baseline on a 2-genuine-run ledger ─────────────────────────────────────
fs.writeFileSync(ledger, genuine('1') + '\n' + genuine('2') + '\n');
const seed = impact(['--set-baseline']);
check('baseline seeds on a genuine ledger (exit 0)', seed.status === 0);
const base = JSON.parse(fs.readFileSync(baseline, 'utf8'));
check('baseline recorded 2 genuine runs', base.runs_genuine === 2);
check('baseline recorded audit_rate 1.0', base.audit_rate === 1.0);

// ── HELD: unchanged ledger passes --strict ────────────────────────────────────────
check('unchanged ledger HOLDS under --strict (exit 0)', impact(['--strict']).status === 0);

// ── REGRESS 1: drop a genuine run → runs_genuine falls → --strict fails ────────────
fs.writeFileSync(ledger, genuine('1') + '\n');
const dropped = impact(['--strict']);
check('dropping a genuine run REGRESSES under --strict (exit 1)', dropped.status === 1);
check('  and names runs_genuine as the regression', /runs_genuine: 2 -> 1/.test(dropped.stdout));

// ── REGRESS 2: add an unaudited genuine run → audit_rate falls → --strict fails ────
fs.writeFileSync(ledger, genuine('1') + '\n' + genuine('2') + '\n' +
  [row({ id: 'i-3', kind: 'intent', ts: '2026-07-20T03:00:00Z', runId: '3', intent_source: 'asked' }),
   row({ id: 'c-3', kind: 'close', ts: '2026-07-20T03:02:00Z', runId: '3', verdictId: 'v-3' })].join('\n') + '\n');
const unaudited = impact(['--strict']);
check('an unaudited new run drops audit_rate → REGRESSES (exit 1)', unaudited.status === 1);
check('  and names audit_rate as the regression', /audit_rate/.test(unaudited.stdout));

// ── non-strict is a scoreboard: same regression does NOT fail without --strict ─────
check('same regression is non-blocking WITHOUT --strict (exit 0)', impact([]).status === 0);

// ── DURABILITY: gutting impact.py reddens the run (blocking-on-executed) ───────────
const missing = spawnSync('python3', [path.join(tmp, 'nope-impact.py'), '--strict'], { encoding: 'utf8' });
check('a missing impact.py exits nonzero (deleting it reddens selftest)', missing.status !== 0);

fs.rmSync(tmp, { recursive: true, force: true });
console.log(`\nRESULT: ${fails ? `${fails} FAIL` : 'PASS'}`);
process.exit(fails ? 1 : 0);
