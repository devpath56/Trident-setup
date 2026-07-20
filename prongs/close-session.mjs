// close-session — the only supported exit from a Trident session.
//
// The entrance (open-session) guarantees an IntentCard exists. This guarantees the loop
// actually closed on it. Without an exit gate a session ends by simply stopping, and a
// session that stops looks exactly like a session that finished. That is CF-065's shape:
// absence takes the form of the nearest acceptable outcome.
//
// Refuses unless ALL hold:
//   1. the run has an IntentCard                       (it went through the door)
//   2. a Verdict cites that specific IntentCard        (the Auditor read the real one, C1)
//   3. every DriftFlag has a verdict resolving it      (Simba proposed, Auditor disposed, C2)
//   4. no failed probe is unaccounted for              (C3)
//   5. a RATVerdict exists if any probe was run        (who ranked the assumption is recorded)
//
// Usage:
//   node prongs/close-session.mjs <runId>            # close, or explain why it cannot
//   node prongs/close-session.mjs <runId> --dry-run  # report only, write nothing
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// Overridable for isolated smoke tests (Phase 0 probe p-durable).
const LEDGER = process.env.PRONGS_PATH || path.join(HERE, 'prongs.jsonl');

const argv = process.argv.slice(2);
const runId = argv.find((a) => !a.startsWith('--'));
const dryRun = argv.includes('--dry-run');
if (!runId) {
  console.error('usage: node prongs/close-session.mjs <runId> [--dry-run]');
  process.exit(2);
}

const rows = fs.existsSync(LEDGER)
  ? fs.readFileSync(LEDGER, 'utf8').split('\n').filter((l) => l.trim()).flatMap((l) => {
      try { return [JSON.parse(l)]; } catch { return []; }
    })
  : [];
const mine = rows.filter((r) => r.runId === runId);
const of = (k) => mine.filter((r) => r.kind === k);

const blocks = [];

// 1 ── the run exists at all
const intent = of('intent').at(-1);
if (!intent) {
  blocks.push([
    'no IntentCard for this run',
    'the session never went through the front door. node prongs/open-session.mjs --run ' + runId + ' ...',
  ]);
}

// 2 ── the Auditor ruled, on THIS card
const verdicts = of('verdict');
const onCard = intent ? verdicts.filter((v) => v.intentCardId === intent.id) : [];
if (intent && !verdicts.length) {
  blocks.push(['no Verdict', 'the loop never closed. node prongs/compose-auditor.mjs ' + runId + ' and run the Auditor.']);
} else if (intent && !onCard.length) {
  blocks.push([
    `${verdicts.length} verdict(s) exist but none cites IntentCard ${intent.id}`,
    'a verdict against a different card is a verdict on a different session.',
  ]);
}

// 3 ── nothing Simba raised was left hanging
const ruled = new Set(verdicts.flatMap((v) => v.resolves || []));
const openDrift = of('drift').filter((d) => d.determination !== 'no-drift' && !ruled.has(d.id));
if (openDrift.length) {
  blocks.push([
    `${openDrift.length} unresolved DriftFlag(s): ${openDrift.map((d) => d.id).join(', ')}`,
    'Simba proposes, the Auditor disposes. An unruled flag means the objection was raised and dropped.',
  ]);
}

// 4 ── a failed probe was either honoured or explicitly overridden
const failedProbes = of('probe').filter((p) => p.result === 'FAIL');
const overridden = new Set(of('override').map((o) => o.overrides));
const unhandled = failedProbes.filter((p) => !overridden.has(p.id));
if (unhandled.length) {
  blocks.push([
    `probe ${unhandled.map((p) => p.id).join(', ')} FAILED with no override`,
    'house-rule 0 is a hard block. Either stop, or log an override row naming who decided and why.',
  ]);
}

// 5 ── if a probe ran, someone ranked the assumption. Record who.
if (of('probe').length && !of('ratverdict').length) {
  blocks.push([
    'a probe ran with no RATVerdict',
    'the probe records the result; the RATVerdict records which assumption was judged riskiest and by whom. ' +
    'Without it the ranking is unattributable.',
  ]);
}

// 6 ── every failing detector in the closing verdict is overridden (or was re-audited green).
// check 4's twin, lifted from probes to detectors: closing on a live failing detector is a
// false-PASS escape. The SAME override row that clears a failed probe clears a failed detector,
// pointing at the verdict + detector_id instead. A later passing re-audit makes onCard.at(-1)'s
// detector pass, so it never appears here — only a still-failing detector at the door blocks.
const closingV = onCard.at(-1);
const escaped = closingV
  ? (closingV.detectors || []).filter((d) => String(d.result).toLowerCase() === 'fail' &&
      !of('override').some((o) => o.overrides === closingV.id && o.detector_id === d.detector_id))
  : [];
if (escaped.length) {
  blocks.push([
    `verdict ${closingV.id} still has failing detector(s) with no override: ${escaped.map((d) => d.detector_id).join(', ')}`,
    'a close on a live failing detector is a false-PASS escape. Log an override naming who accepted it and why, or re-audit it green.',
  ]);
}

console.log(`== close ${runId} ==\n`);
const checks = [
  ['IntentCard exists', !!intent, intent?.id],
  ['Verdict cites it', onCard.length > 0, onCard[0]?.id],
  ['no unresolved DriftFlags', openDrift.length === 0, `${of('drift').length} raised`],
  ['no unhandled probe failure', unhandled.length === 0, `${failedProbes.length} failed`],
  ['no un-overridden failing detector', escaped.length === 0, `${escaped.length} escaping`],
  ['RATVerdict recorded if probed', !(of('probe').length && !of('ratverdict').length), `${of('ratverdict').length} rat`],
];
for (const [label, ok, detail] of checks) {
  console.log(`  ${ok ? 'ok  ' : 'BLOCK'} ${label.padEnd(32)} ${detail ?? ''}`);
}

if (blocks.length) {
  console.log('\n  REFUSED to close:\n');
  for (const [why, fix] of blocks) {
    console.log(`    - ${why}`);
    console.log(`      ${fix}`);
  }
  console.log('\n  A session left open is visible. A session that just stopped is not.');
  process.exit(1);
}

if (dryRun) {
  console.log('\n  would close (dry run, nothing written)');
  process.exit(0);
}

const close = {
  id: `c-${crypto.randomBytes(4).toString('hex')}`,
  kind: 'close',
  ts: new Date().toISOString(),
  runId,
  verdictId: onCard.at(-1).id,
  intentCardId: intent.id,
};
fs.appendFileSync(LEDGER, JSON.stringify(close) + '\n');
console.log(`\n  closed  ${close.id}  (verdict ${close.verdictId} on card ${intent.id})`);
