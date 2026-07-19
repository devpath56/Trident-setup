// rat — the Riskiest-Assumption Test. Opens a Trident phase by forcing the first-principles
// adversarial question BEFORE anything is built (house-rule 0).
//
// WHY IT IS THE PHASE-OPENER, not a gate on a separate "phase" object:
// The RAT probe for this very feature found that "phase" is prose only, zero presence in the
// schema or ledger. A gate keyed on a phase notion that does not exist would decay to prose.
// So the RAT IS the phase boundary: a phase has started iff a RATVerdict exists for it, exactly
// as a session has started iff an IntentCard exists. Nothing external to detect.
//
// It answers three questions, in the operator's own words, adversarially:
//   1. Should I build/push this?                (push_decision: proceed | hold)
//   2. What is the riskiest assumption I am missing?
//   3. What is the cheapest probe that would falsify it?
//
// WHAT IT CANNOT DO: it gates the ARTIFACT, not the honesty. The fields must be present and
// non-placeholder; it cannot force the assumption to be the genuinely riskiest one. Same limit
// as intent_source=asked. The value is removing the ACCIDENT of building before thinking.
//
// Usage:
//   node rat.mjs --run <id> --phase <name>                       # print the RAT questions
//   node rat.mjs --run <id> --phase <name> --riskiest "..." \
//        --probe "..." --push proceed|hold [--gate hard|soft]    # record the RATVerdict
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const LEDGER = process.env.PRONGS_PATH || path.join(HERE, 'prongs.jsonl');

const argv = process.argv.slice(2);
const arg = (k) => { const i = argv.indexOf(`--${k}`); return i >= 0 && argv[i + 1] && !argv[i + 1].startsWith('--') ? argv[i + 1] : null; };
const runId = arg('run');
const phase = arg('phase');

const refuse = (why, fix) => { console.error(`REFUSED: ${why}`); if (fix) console.error(`  ${fix}`); process.exit(2); };
if (!runId) refuse('no --run id');
if (!phase) refuse('no --phase name', 'every RAT opens a named phase, e.g. --phase build');

const rows = fs.existsSync(LEDGER)
  ? fs.readFileSync(LEDGER, 'utf8').split('\n').filter((l) => l.trim()).flatMap((l) => { try { return [JSON.parse(l)]; } catch { return []; } })
  : [];

const riskiest = arg('riskiest');
const probe = arg('probe');
const push = arg('push');

// Print mode: no answers yet. Emit the adversarial prompt and stop.
if (!riskiest && !probe && !push) {
  console.log(`RAT for phase "${phase}" of run ${runId}. Answer before building anything.\n`);
  console.log(`Use first principles and adversarial verification. Strip the change to what must`);
  console.log(`be true, then attack the weakest link.\n`);
  console.log(`  1. Should I build/push this?            --push proceed|hold`);
  console.log(`  2. Riskiest assumption I am missing?    --riskiest "..."`);
  console.log(`     (the one that, if wrong, wastes the whole phase)`);
  console.log(`  3. Cheapest probe that would falsify it? --probe "..."`);
  console.log(`     (the smallest experiment; run it BEFORE the build, log its result as a probe row)\n`);
  console.log(`Then record:`);
  console.log(`  node prongs/rat.mjs --run ${runId} --phase ${phase} \\`);
  console.log(`    --push proceed --riskiest "<...>" --probe "<...>" [--gate hard]`);
  process.exit(0);
}

// Record mode: guard every field, then write.
if (!push || !['proceed', 'hold'].includes(push)) refuse('--push must be proceed or hold', 'this is the should-I-build answer');
if (!riskiest || riskiest.trim().length < 12 || /^(tbd|todo|n\/?a|none|test)\b/i.test(riskiest.trim()))
  refuse(`--riskiest "${riskiest ?? ''}" is empty or a placeholder`, 'name the assumption that would waste the phase if wrong');
if (!probe || probe.trim().length < 12 || /^(tbd|todo|n\/?a|none|test)\b/i.test(probe.trim()))
  refuse(`--probe "${probe ?? ''}" is empty or a placeholder`, 'name the cheapest falsifying experiment');

if (rows.some((r) => r.kind === 'ratverdict' && r.runId === runId && r.phase === phase))
  refuse(`phase "${phase}" of run ${runId} already has a RATVerdict`, 're-opening would let the riskiest assumption be swapped silently. Use a new --phase.');

if (push === 'hold') {
  console.log(`RAT says HOLD on phase "${phase}". Recording the decision; do not build.`);
}

const rat = {
  id: `rat-${crypto.randomBytes(4).toString('hex')}`,
  kind: 'ratverdict',
  ts: new Date().toISOString(),
  runId,
  phase,
  riskiest_assumption: riskiest,
  cheapest_probe: probe,
  gate: arg('gate') || 'hard',
  push_decision: push,
  ranked_by: 'operator via rat.mjs',
};
fs.appendFileSync(LEDGER, JSON.stringify(rat) + '\n');
console.log(`RAT recorded ${rat.id}  phase="${phase}"  push=${push}`);
console.log(`  riskiest: ${riskiest}`);
console.log(`  probe:    ${probe}`);
console.log(`\n  next: run the probe, log its result as a probe row, THEN build.`);
