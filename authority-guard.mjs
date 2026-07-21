// authority-guard — the deterministic gate for "search for the most authoritative X".
//
// THE ERROR IT ENCODES (CF-075, caught by a human, missed by a decorrelated audit):
//   authority-by-breadth — ranking sources by prestige/age/citation-count and handing back a
//   single unconditional winner, WITHOUT indexing the pick to who is reading and what they must
//   do next. It is how the design-canon audit ranked Williams "more foundational" than Refactoring
//   UI when the two cover the same layer for different readers — and for a builder, the "lesser"
//   one wins.
//
// WHAT A DETERMINISTIC CHECK CAN AND CANNOT DO (be honest about the ceiling):
//   It cannot know whether "Refactoring UI" is the RIGHT answer. That is judgement.
//   It CAN fail a recommendation whose ARGUMENT-SHAPE permits the error — the same move teach-gate
//   makes for teaching and prove-durable makes for durability: find the field whose ABSENCE lets
//   the error hide, then require it. Here those fields are: audience, job, a non-prestige ranking
//   criterion, and at least one alternative with the condition under which IT wins. A rec that
//   carries all four cannot be a bare prestige-ranking; a rec that omits them is where the error
//   lives.
//
// It is also TUNED: when a query names no audience (Devansh's shorthand "most authoritative X"),
// the guard injects the Bay-Area-builder persona from authority-persona.json and says it did, so
// the default is a stated builder-fit axis rather than an unstated prestige one.
//
// Usage:
//   node authority-guard.mjs <recommendation.json>     # a record (see fixtures/authority-good.json)
//   node authority-guard.mjs --json <recommendation.json>   # machine-readable result
//   cat rec.json | node authority-guard.mjs -          # from stdin
//
// Record shape:
//   { query, recommendation, audience?, job, criterion,
//     alternatives: [{ name, wins_when }], verified? }
import fs from 'node:fs';
import path from 'node:path';

const HERE = path.dirname(new URL(import.meta.url).pathname);
const argv = process.argv.slice(2);
const asJson = argv.includes('--json');
const src = argv.find((a) => a !== '--json');

if (!src) {
  console.error('usage: node authority-guard.mjs <recommendation.json> [--json]  (or "-" for stdin)');
  process.exit(2);
}

const raw = src === '-' ? fs.readFileSync(0, 'utf8') : fs.readFileSync(path.resolve(src), 'utf8');
let rec;
try { rec = JSON.parse(raw); } catch (e) { console.error(`not valid JSON: ${e.message}`); process.exit(2); }

const persona = JSON.parse(fs.readFileSync(path.join(HERE, 'authority-persona.json'), 'utf8'));

// ── the lexicons — loaded from authority-lexicon.json (SSOT shared with validate_prongs.py's
// reuse gate, so the JS guard and the Python reuse gate can never drift apart). ────────────────
//   PRESTIGE: ranking words that describe a source's reputation, not its fit to a reader.
//   FIT: words that index the pick to a reader, a job, or a depth — the axis prestige-ranking omits.
//   SUPERLATIVE: an unconditional "there is one winner" claim — legal only if a flip-condition exists.
const LEX = JSON.parse(fs.readFileSync(path.join(HERE, 'authority-lexicon.json'), 'utf8'));
const rx = (arr) => new RegExp(`\\b(${arr.join('|')})\\b`, 'i');
const PRESTIGE = rx(LEX.prestige);
const FIT = rx(LEX.fit);
const SUPERLATIVE = rx(LEX.superlative);

const findings = [];
const fail = (gate, why) => findings.push({ gate, severity: 'fail', why });
const warn = (gate, why) => findings.push({ gate, severity: 'warn', why });

const nonEmpty = (v) => typeof v === 'string' && v.trim().length >= 3;

// ── 1. structural completeness — the fields whose absence hides the error ───────
if (!nonEmpty(rec.recommendation)) fail('no-recommendation', 'record names no recommendation to check');
if (!nonEmpty(rec.job)) fail('no-job', 'no job-to-be-done: an authority is authoritative FOR a task; unstated task = unindexed pick');
if (!nonEmpty(rec.criterion)) fail('no-criterion', 'no ranking criterion stated; an unstated axis is almost always prestige');

// ── 2. audience — inject the tuned persona when the query names none ─────────────
let appliedPersona = false;
if (!nonEmpty(rec.audience)) {
  rec.audience = persona.persona + ' (default)';
  appliedPersona = true;
  warn('audience-defaulted', `no audience named; applied the tuned default "${persona.persona}" and its axis: ${persona.authority_axis}`);
}

// ── 3. authority-by-breadth — the CF-075 catch ──────────────────────────────────
// A criterion that reads on prestige alone, with no fit term, IS the error.
if (nonEmpty(rec.criterion) && PRESTIGE.test(rec.criterion) && !FIT.test(rec.criterion)) {
  fail('authority-by-breadth',
    `criterion "${rec.criterion}" ranks by prestige/breadth with no reader/job/depth axis — CF-075. Re-index to who is reading and what they must DO (persona axis: ${persona.authority_axis}).`);
}

// ── 4. flip-condition — an absolute ranking with no "the other wins when" ────────
const alts = Array.isArray(rec.alternatives) ? rec.alternatives : [];
if (alts.length === 0) {
  fail('no-alternative',
    'no alternative named. A single unconditional winner is the smell: name >=1 alternative and the condition under which IT wins (proves the context axis was considered).');
} else {
  const noFlip = alts.filter((a) => !nonEmpty(a?.wins_when));
  if (noFlip.length) {
    fail('no-flip-condition',
      `${noFlip.length} alternative(s) carry no "wins_when": ${noFlip.map((a) => a?.name || '?').join(', ')}. An alternative with no context under which it wins is decoration, not a real comparison.`);
  }
}

// ── 5. superlative-guard — an unconditional superlative needs a boundary ─────────
const superText = `${rec.recommendation || ''} ${rec.criterion || ''} ${rec.rationale || ''}`;
const hasFlip = alts.some((a) => nonEmpty(a?.wins_when));
if (SUPERLATIVE.test(superText) && !hasFlip) {
  const m = superText.match(SUPERLATIVE);
  fail('unconditional-superlative',
    `"${m[0]}" is an unconditional superlative with no flip-condition anywhere. Superlatives are legal only paired with the boundary where they stop being true.`);
}

// ── 6. verification of the load-bearing citation ────────────────────────────────
if (rec.verified === false) {
  warn('unverified', 'recommendation flagged unverified — a mis-attributed authority is worse than none; verify the primary source before it ships.');
}

// ── verdict ─────────────────────────────────────────────────────────────────────
const fails = findings.filter((f) => f.severity === 'fail');
const warns = findings.filter((f) => f.severity === 'warn');
const pass = fails.length === 0;

if (asJson) {
  console.log(JSON.stringify({ pass, appliedPersona, audience: rec.audience, findings }, null, 2));
} else {
  console.log(`\n== authority-guard: ${rec.query || rec.recommendation || '(unnamed query)'} ==\n`);
  console.log(`  recommendation : ${rec.recommendation || '(none)'}`);
  console.log(`  audience       : ${rec.audience}${appliedPersona ? '  [persona-injected]' : ''}`);
  console.log(`  criterion      : ${rec.criterion || '(none)'}\n`);
  for (const f of findings) console.log(`  ${f.severity === 'fail' ? 'FAIL' : 'warn'}  ${f.gate}: ${f.why}`);
  if (!findings.length) console.log('  (no findings)');
  console.log(`\nRESULT: ${pass ? 'PASS' : `FAIL (${fails.length})`}${warns.length ? ` · ${warns.length} warn` : ''}`);
}

process.exit(pass ? 0 : 1);
