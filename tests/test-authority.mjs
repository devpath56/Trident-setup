// test-authority — the durability control for authority-guard (CF-075).
//
// A checker is only real if a KNOWN-BAD input fails it and a KNOWN-GOOD input passes. This asserts
// both directions on the committed fixtures, so gutting authority-guard (deleting the prestige
// check, the flip-condition check, or the superlative check) makes a fixture behave wrong and
// reddens this suite. Wired into selftest.py, that is what makes the guard durable rather than an
// orphan (CF-073). No network, no model — pure structural discrimination.
//
// Run:  node tests/test-authority.mjs
import { spawnSync } from 'node:child_process';
import path from 'node:path';

const HERE = path.dirname(new URL(import.meta.url).pathname);
const ROOT = path.join(HERE, '..');
const guard = (fixture) => spawnSync('node', ['authority-guard.mjs', `fixtures/${fixture}`, '--json'],
  { cwd: ROOT, encoding: 'utf8' });

let fails = 0;
const check = (label, cond) => { console.log(`  ${cond ? 'ok  ' : 'FAIL'} ${label}`); if (!cond) fails++; };

console.log('== authority-guard: prestige-ranking fails, builder-fit passes ==\n');

const good = guard('authority-good.json');
const goodJson = JSON.parse(good.stdout || '{}');
check('the builder-fit recommendation PASSES (exit 0)', good.status === 0);
check('  ...with no failing findings', (goodJson.findings || []).every((f) => f.severity !== 'fail'));

const slop = guard('authority-slop.json');
const slopJson = JSON.parse(slop.stdout || '{}');
const gates = (slopJson.findings || []).filter((f) => f.severity === 'fail').map((f) => f.gate);
check('the prestige-ranked recommendation FAILS (exit 1)', slop.status === 1);
// the three distinct reasoning errors the slop fixture encodes — each must be independently caught,
// so removing any one check from the guard flips one of these red.
check('  ...caught authority-by-breadth (the CF-075 error)', gates.includes('authority-by-breadth'));
check('  ...caught the missing flip-condition / no-alternative', gates.includes('no-alternative') || gates.includes('no-flip-condition'));
check('  ...caught the unconditional superlative', gates.includes('unconditional-superlative'));

// the tuning: an audience-less query must inject the Bay-Area-builder persona (not silently pass).
check('an audience-less query injects the tuned persona', slopJson.appliedPersona === true);

console.log(`\nRESULT: ${fails ? `${fails} FAIL` : 'PASS'}`);
process.exit(fails ? 1 : 0);
