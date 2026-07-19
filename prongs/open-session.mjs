// open-session — the only supported entrance to a Trident session.
//
// WHAT THIS FIXES
// The census found IntentCard, AssumptionSet, DriftFlag and Verdict each had a file, a
// schema and a validator, and zero records. C0 gave them a medium; compose-auditor forced
// the READ side. Nothing forced the WRITE. Writing one stayed a prose instruction in a skill
// file, and prose instructions to a model decay to zero. So the write moment becomes the
// door: there is no way to be inside a session without having produced an IntentCard,
// because producing one is what opening a session IS.
//
// WHAT THIS CANNOT DO
// It gates the ARTIFACT, not the conversation. Nothing here can force Simba to have really
// asked the user; the fields can be filled in truthfully or not. house-rules.md is honest
// about this and so is this file. What it does remove is the accident: forgetting, running
// out of context, or deciding the answer was obvious. Dishonesty is still reachable; drift
// is not.
//
// Usage:
//   node prongs/open-session.mjs --run <id> --goal "..." \
//        --in "a; b" --out "x; y" [--must "..."] [--forbid "..."] [--riskiest "..."]
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// Ledger path is overridable so the doors can be smoke-tested against a throwaway ledger
// without polluting the real one (Phase 0 probe p-durable: it was hardcoded).
const LEDGER = process.env.PRONGS_PATH || path.join(HERE, 'prongs.jsonl');

const argv = process.argv.slice(2);
const arg = (k) => {
  const i = argv.indexOf(`--${k}`);
  return i >= 0 && argv[i + 1] && !argv[i + 1].startsWith('--') ? argv[i + 1] : null;
};
const list = (k) => (arg(k) || '').split(';').map((s) => s.trim()).filter(Boolean);

const runId = arg('run');
const goal = arg('goal');
const inScope = list('in');
const outScope = list('out');

const refuse = (why, fix) => {
  console.error(`REFUSED: ${why}`);
  if (fix) console.error(`  ${fix}`);
  process.exit(2);
};

if (!runId) refuse('no --run id', 'every prong record is keyed on a run. Pick one and reuse it all session.');
if (!goal) refuse('no --goal', 'house-rule 15: a session may not start from an inferred goal. Ask, then pass the answer.');

// A scope with no exclusions is not a scope. This is the half that gets skipped: people
// answer "what are we doing" readily and never state what is off the table, which is where
// the drift comes from later. Both halves or nothing (house-rule 15, PD-007).
if (!inScope.length) refuse('--in is empty', 'ask verbatim: "what is the scope for this session?"');
if (!outScope.length) {
  refuse(
    '--out is empty',
    'a scope with no exclusions is not a scope. What is explicitly NOT in this session? ' +
    'If the answer is genuinely nothing, say so in words: --out "nothing excluded, stated by user"'
  );
}

// Refuse a goal that reads as a placeholder. Cheap, catches the case where the door is
// opened just to get past the door.
if (goal.trim().length < 12 || /^(tbd|todo|n\/?a|test|stuff|things?)\b/i.test(goal.trim())) {
  refuse(`--goal "${goal}" is a placeholder`, 'the goal is the thing the Auditor grades against. Write the real one.');
}

const rows = fs.existsSync(LEDGER)
  ? fs.readFileSync(LEDGER, 'utf8').split('\n').filter((l) => l.trim()).flatMap((l) => {
      try { return [JSON.parse(l)]; } catch { return []; }
    })
  : [];

const existing = rows.find((r) => r.kind === 'intent' && r.runId === runId);
if (existing) {
  refuse(
    `run ${runId} already has IntentCard ${existing.id}`,
    'reopening would let a session silently swap the goal it is graded against. Use a new --run id.'
  );
}

const card = {
  id: `i-${crypto.randomBytes(4).toString('hex')}`,
  kind: 'intent',
  ts: new Date().toISOString(),
  runId,
  // Stamped 'asked' because this script cannot be reached without the answers being passed
  // in. That is a stronger claim than a model self-reporting the field, and a weaker one
  // than proof the question was spoken. Both are true; the field means the former.
  intent_source: 'asked',
  goal,
  scope: { in_scope: inScope, out_of_scope: outScope },
  must_haves: list('must'),
  forbid: list('forbid'),
  ...(arg('riskiest') ? { intent_riskiest: arg('riskiest') } : {}),
};

fs.appendFileSync(LEDGER, JSON.stringify(card) + '\n');

console.log(`opened ${runId}  ->  IntentCard ${card.id}`);
console.log(`  goal        ${goal}`);
console.log(`  in scope    ${inScope.join(' · ')}`);
console.log(`  out         ${outScope.join(' · ')}`);
if (card.must_haves.length) console.log(`  must have   ${card.must_haves.join(' · ')}`);
if (card.forbid.length) console.log(`  forbidden   ${card.forbid.join(' · ')}`);
console.log(`\n  next: node prongs/compose-auditor.mjs ${runId}`);
console.log(`  exit: node prongs/close-session.mjs ${runId}`);
