// checkpoint — the human-in-loop OBSERVABILITY + control layer for an agent loop, Claude-Code-native.
//
// Between iterations of a loop (eval -> deficiency -> retrieve -> fix -> re-eval) the human needs full
// observability + control so they feel in command. This is the subscription-native realization (files +
// re-invocation, NO API / OTel-exporter / collector), CONFORMING TO three authorities (urls in the PD
// authority record, failures/decisions.jsonl):
//
//   OpenTelemetry GenAI semantic conventions  -> the decision-graph is captured as spans (via spans.mjs)
//     with a `gen_ai.operation.name`; observability is the *executed* trace, not narration.
//   LangGraph human-in-the-loop               -> every iteration is a CHECKPOINT (resumable state);
//     a pause is `interrupt()` (write-checkpoint + exit); resume via approve/edit/reject/respond;
//     `parent` is time-travel / rollback.
//   Anthropic trustworthy agents              -> transparency (show the plan), stopping conditions,
//     PAUSE-BEFORE-IRREVERSIBLE, propose != dispose (nothing auto-applies; the human disposes).
//
// The load-bearing split: observability is CONTINUOUS (a checkpoint every round), control is DISCRETE
// (pause only at consequential / irreversible steps).
//
// Usage:
//   node prongs/checkpoint.mjs write  --run <id> --iter <n> [--dir <base>] [--transcript <f>]
//        [--op eval|invoke_agent|execute_tool] [--deficiency ..] [--query ..] [--source ..] [--cite ..]
//        [--fix ..] [--metric ..] [--before ..] [--after ..] [--bar ..] [--max <n>] [--converged]
//        [--pause | --irreversible]                    # pause => interrupt: prints card, exit 3
//   node prongs/checkpoint.mjs resume --run <id> [--dir <base>]
//        ( --approve | --edit <file> | --reject "<why>" | --rollback <iter> )   # LangGraph decision types
//   node prongs/checkpoint.mjs show   --run <id> [--dir <base>]                 # the observability timeline
//
// Exit: 0 ok · 2 usage/precondition · 3 INTERRUPTED (a pause — resume required).
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

const argv = process.argv.slice(2);
const cmd = argv[0];
const flag = (k, d) => { const i = argv.indexOf(`--${k}`); return i >= 0 ? argv[i + 1] : d; };
const has = (k) => argv.includes(`--${k}`);
const die = (m, c = 2) => { console.error(m); process.exit(c); };

const BASE = path.resolve(flag('dir', process.cwd()));
const runDir = (run) => path.join(BASE, 'runs', run);
const ledger = (run) => path.join(runDir(run), 'checkpoints.jsonl');
const HERE = path.dirname(new URL(import.meta.url).pathname);

const readCkpts = (run) => {
  const f = ledger(run);
  if (!fs.existsSync(f)) return [];
  return fs.readFileSync(f, 'utf8').split('\n').filter((l) => l.trim()).map((l) => JSON.parse(l));
};
const append = (run, rec) => {
  fs.mkdirSync(runDir(run), { recursive: true });
  fs.appendFileSync(ledger(run), JSON.stringify(rec) + '\n');
};

// the human-readable observability card (transparency — Anthropic)
function card(c) {
  const L = [`\n── checkpoint ${c.runId} #${c.iteration}  [${c.status}]  (${c['gen_ai.operation.name']}) ──`];
  const d = c.decision || {};
  if (d.deficiency) L.push(`  deficiency : ${d.deficiency}`);
  if (d.retrieve && d.retrieve.query) L.push(`  retrieve   : "${d.retrieve.query}"  ${d.retrieve.cite || ''}`);
  if (d.proposed_fix) L.push(`  fix        : ${d.proposed_fix}`);
  const dl = c.delta || {};
  if (dl.metric) L.push(`  delta      : ${dl.metric}  ${dl.before ?? '?'} -> ${dl.after ?? '?'}  (bar ${dl.bar ?? '?'})`);
  if (c.spans && c.spans.length) L.push(`  spans      : ${c.spans.length} executed (${c.spans.filter((s) => s.role === 'error').length} err) — not narrated`);
  if (c.stop) L.push(`  stop       : ${c.stop.converged ? 'CONVERGED — bar met' : `round ${c.iteration}/${c.stop.max_iterations}`}`);
  if (c.parent != null) L.push(`  parent     : #${c.parent}  (rollback point)`);
  if (c.human) L.push(`  disposed   : ${c.human.decision}${c.human.note ? ` — ${c.human.note}` : ''}`);
  if (c.awaiting) L.push(`  ⏸ AWAITING : ${c.awaiting.join(' | ')}   →  node prongs/checkpoint.mjs resume --run ${c.runId} --<decision>`);
  return L.join('\n');
}

if (cmd === 'write') {
  const run = flag('run') || die('--run required');
  const iter = parseInt(flag('iter', '0'), 10);
  const transcript = flag('transcript', null);
  let spans = [];
  if (transcript) {
    if (!fs.existsSync(transcript)) die(`transcript not found: ${transcript}`);
    const r = spawnSync('node', [path.join(HERE, 'spans.mjs'), transcript], { encoding: 'utf8' });
    if (r.status === 0) { try { spans = JSON.parse(r.stdout); } catch { /* leave empty */ } }
  }
  const pause = has('pause') || has('irreversible');
  const rec = {
    runId: run, iteration: iter, ts: new Date().toISOString(),
    parent: flag('parent', null) != null ? parseInt(flag('parent'), 10) : null,
    'gen_ai.operation.name': has('irreversible') ? 'promote' : flag('op', 'eval'),
    decision: { deficiency: flag('deficiency', null), retrieve: { query: flag('query', null), source: flag('source', null), cite: flag('cite', null) }, proposed_fix: flag('fix', null) },
    spans,
    delta: { before: flag('before', null), after: flag('after', null), metric: flag('metric', null), bar: flag('bar', null), distance: null },
    stop: { converged: has('converged'), max_iterations: parseInt(flag('max', '3'), 10), reason: flag('reason', null) },
    status: pause ? 'interrupted' : 'running',
    awaiting: pause ? ['approve', 'edit', 'reject'] : null,
    human: null,
  };
  append(run, rec);
  console.log(card(rec));
  process.exit(pause ? 3 : 0); // exit 3 = interrupted (the LangGraph pause); resume required
}

if (cmd === 'resume') {
  const run = flag('run') || die('--run required');
  const ck = readCkpts(run);
  if (!ck.length) die(`no checkpoints for run ${run}`);
  const last = ck[ck.length - 1];
  let decision = null, note = null, parent = last.iteration;
  if (has('approve')) decision = 'approved';
  else if (has('edit')) { decision = 'edited'; note = flag('edit'); }
  else if (has('reject')) { decision = 'rejected'; note = flag('reject'); }
  else if (has('rollback')) { decision = 'rollback'; parent = parseInt(flag('rollback'), 10); }
  else die('resume needs one of: --approve | --edit <file> | --reject "<why>" | --rollback <iter>');
  const rec = {
    runId: run, iteration: last.iteration + 1, ts: new Date().toISOString(), parent,
    'gen_ai.operation.name': 'eval',
    decision: last.decision, spans: [], delta: last.delta, stop: last.stop,
    status: decision === 'rollback' ? 'running' : decision,
    awaiting: null, human: { decision, note },
  };
  append(run, rec);
  console.log(`resumed ${run}: ${decision}${note ? ` (${note})` : ''}${decision === 'rollback' ? ` -> from #${parent}` : ''}`);
  process.exit(0);
}

if (cmd === 'show') {
  const run = flag('run') || die('--run required');
  const ck = readCkpts(run);
  if (!ck.length) die(`no checkpoints for run ${run}`, 0);
  ck.forEach((c) => console.log(card(c)));
  process.exit(0);
}

die('usage: checkpoint.mjs write|resume|show --run <id> [--dir <base>] ...');
