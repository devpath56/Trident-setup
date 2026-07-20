// status — the Trident gate dashboard. Read-only. The instrument panel the loop was missing.
//
// WHY THIS EXISTS
// validate_prongs.py answers one bit: is the whole ledger valid. That is the warning light, not
// the dashboard. It cannot tell you WHICH phase you are in, which gate is next, or why a run is
// stuck — so a live session felt like driving a Ferrari blind. This computes the phase/gate ladder
// per run and renders it, and for open runs names the exact NEXT gate to clear.
//
// THE ONE HONESTY RULE (do not break)
// This file NEVER decides pass/fail on its own authority. It computes STRUCTURE only — which
// artifacts a run has, which phase they belong to, what comes next. Every ✓/✗ VERDICT is
// delegated to validate_prongs.py: the dashboard runs it, parses its FAIL blocks, and paints ✗
// exactly where the enforcer put a problem. If it computed gates itself it would be a second
// source of truth that drifts green while the enforcer is red — the vacuous-dashboard trap
// (CF-065). tests/test-status.mjs proves this by corrupting a copied ledger and demanding the ✗.
//
// Usage:
//   node prongs/status.mjs              # every run, newest last, + the open run's next gate
//   node prongs/status.mjs <runId>      # focus one run
//   node prongs/status.mjs --plain      # no color (also auto-off when piped / NO_COLOR)
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const LEDGER = process.env.PRONGS_PATH || path.join(HERE, 'prongs.jsonl');
const argv = process.argv.slice(2);
const focusRun = argv.find((a) => !a.startsWith('--'));
const noColor = argv.includes('--plain') || process.env.NO_COLOR || !process.stdout.isTTY;

// ── color ─────────────────────────────────────────────────────────────────────
const C = (code) => (s) => (noColor ? s : `\x1b[${code}m${s}\x1b[0m`);
const green = C('32'), red = C('31'), yellow = C('33'), dim = C('2'), bold = C('1'), cyan = C('36');

// ── read the ledger ─────────────────────────────────────────────────────────────
const rows = fs.existsSync(LEDGER)
  ? fs.readFileSync(LEDGER, 'utf8').split('\n').filter((l) => l.trim()).map((l, i) => {
      try { return { ...JSON.parse(l), _line: i + 1 }; } catch { return null; }
    }).filter(Boolean)
  : [];

if (!rows.length) {
  console.log(dim(`  no prong records in ${path.basename(LEDGER)} — no session has opened yet.`));
  process.exit(0);
}

// id → row, and line → row, so a validate_prongs problem can be pinned to a run/phase.
const byId = new Map(rows.map((r) => [r.id, r]));

// ── delegate the verdict: run the real enforcer, attribute its FAILs ──────────────
// The dashboard paints ✗ only where THIS says there is a problem. Never on its own opinion.
const enforcer = spawnSync('python3', [path.join(HERE, 'validate_prongs.py')], { encoding: 'utf8' });
const enfOut = (enforcer.stdout || '') + (enforcer.stderr || '');
const enfPassed = enforcer.status === 0;

// Parse FAIL blocks: "  FAIL <gate>" then indented "       <problem>" lines. Pull any artifact id
// or "row N" out of each problem and map it to the run it belongs to.
const problemRuns = new Set();      // runIds the enforcer flagged
const problemIds = new Set();       // artifact ids the enforcer flagged
const controlBroken = [];           // negative controls that failed = the CHECKER itself is broken
for (const line of enfOut.split('\n')) {
  const ctl = line.match(/^ {4}FAIL\s+(.+)$/);
  if (ctl) { controlBroken.push(ctl[1].trim()); continue; }
  const prob = line.match(/^ {7}(.+)$/);            // a problem detail line under a FAIL gate
  if (!prob) continue;
  const text = prob[1];
  // Any id-shaped token (kind-prefix + suffix): v-30e3d80e AND human ids like v-liar. Junk tokens
  // (e.g. "house-rule") simply never match a real row in byId, so over-capture is harmless.
  for (const m of text.matchAll(/\b([a-z]{1,10}-[a-z0-9][\w-]*)\b/gi)) {
    problemIds.add(m[1]);
    const r = byId.get(m[1]); if (r) problemRuns.add(r.runId);
  }
  const rowM = text.match(/^row (\d+)/);
  if (rowM) { const r = rows.find((x) => x._line === +rowM[1]); if (r) { problemIds.add(r.id); problemRuns.add(r.runId); } }
}

// A verdict/probe/rca/drift/ratverdict/intent is clean unless the enforcer named it.
const flagged = (r) => problemIds.has(r?.id);

// ── glyphs (structure from us, verdict from the enforcer) ─────────────────────────
const G = {
  pass: () => green('✓'),
  fail: () => red('✗'),
  next: () => yellow('○'),
  block: () => red('⊘'),
  na: () => dim('·'),
};

// ── group rows by run, in first-seen order ───────────────────────────────────────
const runOrder = [];
const runs = new Map();
for (const r of rows) {
  if (!runs.has(r.runId)) { runs.set(r.runId, []); runOrder.push(r.runId); }
  runs.get(r.runId).push(r);
}
runOrder.sort((a, b) => (runs.get(a)[0].ts || '').localeCompare(runs.get(b)[0].ts || ''));

const K = (arr, kind) => arr.filter((r) => r.kind === kind);
const phaseOf = (r) => r.phase || 'phase-0';

// ── the gate ladder for one run ───────────────────────────────────────────────────
function renderRun(runId) {
  const mine = runs.get(runId).slice().sort((a, b) => (a.ts || '').localeCompare(b.ts || ''));
  const intents = K(mine, 'intent');
  const rats = K(mine, 'ratverdict');
  const probes = K(mine, 'probe');
  const overrides = K(mine, 'override');
  const verdicts = K(mine, 'verdict');
  const drifts = K(mine, 'drift');
  const rcas = K(mine, 'rca');
  const closes = K(mine, 'close');
  const closed = closes.length > 0;
  const tsRange = `${(mine[0].ts || '').slice(0, 10)}`;

  // header + validity for this run (from the enforcer, not our opinion)
  const runFlagged = problemRuns.has(runId);
  const state = closed ? cyan('● closed') : yellow('◐ open');
  const valid = runFlagged ? red('gate FAIL') : (enfPassed ? green('gates hold') : dim('—'));
  console.log(`\n${bold('▸ ' + runId)}  ${dim(tsRange)}  ${state}  ${valid}`);

  const line = (glyph, label, detail) =>
    console.log(`  ${glyph}  ${label.padEnd(20)} ${detail ? dim(detail) : ''}`);

  // G1 · INTENT (C1) — one per run
  if (intents.length) {
    const it = intents[0];
    const asked = it.intent_source === 'asked';
    line(flagged(it) || !asked ? G.fail() : G.pass(), 'intent',
      `${it.id} · source:${it.intent_source}${asked ? '' : red(' (must be asked)')}`);
  } else {
    line(closed ? G.fail() : G.next(), 'intent', 'Simba ASK → IntentCard (house-rule 15)');
  }

  // phases, ordered by when their RAT opened; rows with no phase bucket under phase-0
  const phaseNames = [...new Set([
    ...rats.map((r) => r.phase || 'phase-0'),
    ...probes.map(phaseOf), ...verdicts.map(phaseOf),
  ])];
  // keep phase-0 first, then by first ts of the phase's rat
  const firstTs = (p) => (rats.find((r) => (r.phase || 'phase-0') === p) || {}).ts || '';
  phaseNames.sort((a, b) => (a === 'phase-0' ? '' : firstTs(a)).localeCompare(b === 'phase-0' ? '' : firstTs(b)));

  // present-row verdict is delegated: ✗ iff the enforcer named this id, else ✓. We NEVER
  // author a FAIL from our own reading of a rule (forward-gating etc. is the enforcer's to know).
  const mark = (row) => (flagged(row) ? G.fail() : G.pass());

  for (const ph of phaseNames) {
    console.log(`  ${dim('│ phase ' + bold(ph))}`);
    const rat = rats.find((r) => (r.phase || 'phase-0') === ph);
    const phProbes = probes.filter((r) => phaseOf(r) === ph);
    const phVerdicts = verdicts.filter((r) => phaseOf(r) === ph);

    // G2 · RAT (HR-0) — opens the phase. A missing RAT is NOT ours to call a failure: if the
    // enforcer required one it flags the work row below (its ✗ carries the truth). We only note
    // the absence, neutrally.
    if (rat) line(mark(rat), '│ rat', `${rat.id} · push:${rat.push_decision || '?'}`);
    else if (phProbes.length || phVerdicts.length) line(G.na(), '│ rat', 'no RAT opened this phase (pre-gate if enforcer is green)');

    // G3 · PROBE (C3). enfPassed guarantees any FAIL is override-covered (else C3 would fail),
    // so a self-authored ⊘ only appears when the enforcer itself is red.
    for (const p of phProbes) {
      const failed = p.result === 'FAIL';
      const glyph = flagged(p) ? G.fail() : (failed && !enfPassed) ? G.block() : G.pass();
      line(glyph, '│ probe', `${p.id} · ${p.result}${failed ? dim(' (override on file)') : ''}`);
    }

    // G4 · VERDICT. Glyph from the enforcer. Failing detectors on a green/closed run are RESOLVED
    // findings, not a live failure — only an OPEN run frames them as "RCA next" (in → next).
    for (const v of phVerdicts) {
      const dets = v.detectors || [];
      const fails = dets.filter((d) => d.result === 'fail');
      const note = fails.length
        ? (closed || enfPassed ? dim(` (${fails.length} findings resolved)`) : yellow(` (${fails.length} failing → RCA)`))
        : '';
      line(mark(v), '│ verdict', `${v.id} · ${dets.length - fails.length}/${dets.length} detectors${note}`);
      // G6 · RCA — show the row only when one exists, or when an OPEN run owes one.
      const rca = rcas.find((rc) => rc.verdictId === v.id);
      if (rca) line(mark(rca), '│ rca', `${rca.id} · target:${rca.target} · gate:${rca.gate}`);
      else if (fails.length && !closed) line(G.next(), '│ rca', yellow('failing verdict owes an RCA proposal'));
    }
  }

  // G5 · DRIFT (C2) — present rows delegate; an OPEN run with an unresolved drift shows it as next.
  for (const d of drifts) {
    const resolved = verdicts.length > 0;
    const glyph = flagged(d) ? G.fail() : resolved ? G.pass() : (closed ? G.pass() : G.next());
    line(glyph, 'drift', `${d.id} · ${d.determination}${(!resolved && !closed) ? yellow(' · needs a verdict (C2)') : ''}`);
  }

  // G7 · CLOSE (the door)
  line(closed ? mark(closes[0]) : G.next(),
    'close', closed ? `${closes[0].id} · session ended through the door` : dim('session still open'));

  // → NEXT GATE — the whole point of the dashboard for a live run
  if (!closed) console.log(`  ${yellow('→ next: ' + nextGate({ intents, rats, probes, overrides, verdicts, drifts, rcas }))}`);
}

// what gate does an OPEN run have to clear next? first unmet gate wins.
function nextGate({ intents, rats, probes, overrides, verdicts, drifts, rcas }) {
  if (!intents.length) return 'Simba ASK the user their intent → IntentCard (asked)';
  const failedUncovered = probes.find((p) => p.result === 'FAIL' && !overrides.some((o) => o.overrides === p.id));
  if (failedUncovered) return `probe ${failedUncovered.id} FAILED — log an override with a reason, or STOP (C3)`;
  const badVerdict = verdicts.find((v) => (v.detectors || []).some((d) => d.result === 'fail') && !rcas.some((rc) => rc.verdictId === v.id));
  if (badVerdict) return `verdict ${badVerdict.id} has a failing detector — run compose-rca.mjs (RCA before re-dispatch)`;
  const openDrift = drifts.find(() => verdicts.length === 0);
  if (openDrift) return `drift ${openDrift.id} unresolved — the Auditor must dispose it with a verdict (C2)`;
  if (!rats.length) return 'open the phase with its RAT — node prongs/rat.mjs (house-rule 0)';
  if (!verdicts.length) return 'run the phase probe / build, then the Auditor verdict';
  return 'close the session — node prongs/close-session.mjs <runId>';
}

// ── render ────────────────────────────────────────────────────────────────────────
console.log(bold('\n══ Trident gate dashboard ══') + dim(`  ${rows.length} records · ${runOrder.length} runs · ${path.basename(LEDGER)}`));
if (controlBroken.length) {
  console.log(red(`\n  ⚠ ENFORCER SELF-CHECK BROKEN — ${controlBroken.length} negative control(s) failed. The dashboard's ✓ cannot be trusted until validate_prongs is fixed:`));
  controlBroken.slice(0, 5).forEach((c) => console.log(red(`     ${c}`)));
}
const toShow = focusRun ? runOrder.filter((r) => r === focusRun) : runOrder;
if (focusRun && !toShow.length) { console.log(red(`\n  no run "${focusRun}". runs: ${runOrder.join(', ')}`)); process.exit(1); }
toShow.forEach(renderRun);

// legend + honest banner
console.log(dim(`\n  ${G.pass()} clear   ${G.fail()} enforcer flagged   ${G.next()} next / pending   ${G.block()} blocked   ${G.na()} n/a`));
console.log(`  ${enfPassed && !controlBroken.length ? green('enforcer: RESULT PASS — every gate shown green is validate_prongs-confirmed') : red('enforcer: RESULT FAIL — see ✗ above; run python3 prongs/validate_prongs.py for detail')}`);
