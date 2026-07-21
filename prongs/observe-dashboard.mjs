// observe-dashboard — the human-in-loop OBSERVABILITY VIEW for an agent loop (PD-020).
//
// Renders a run's runs/<id>/checkpoints.jsonl (written by checkpoint.mjs) as a static, self-contained
// HTML timeline: one card per iteration showing the decision (transparency), the delta vs the bar
// (progress), the executed spans (OTel GenAI / spans.mjs — ▸ tools · ⚠ errors), the stop conditions,
// and the LangGraph HITL disposition (approve/edit/reject/rollback). Continuous observability made
// skimmable. Claude-Code-native: no server, no external asset (offline-safe), theme-aware.
//
// Usage:
//   node prongs/observe-dashboard.mjs --run <id> [--dir <base>] [--out <file>]   # write/emit HTML
//   node prongs/observe-dashboard.mjs --selftest                                  # prove it renders
// Exit: 0 ok · 2 usage/precondition.
import fs from 'node:fs';
import path from 'node:path';

const argv = process.argv.slice(2);
const flag = (k, d) => { const i = argv.indexOf(`--${k}`); return i >= 0 ? argv[i + 1] : d; };
const has = (k) => argv.includes(`--${k}`);
const die = (m, c = 2) => { console.error(m); process.exit(c); };

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) =>
  ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

// ── the render: checkpoints[] -> a self-contained HTML string ────────────────────────────────────
function render(run, ck) {
  const disposed = ck.filter((c) => c.human && c.human.decision).length;
  const interrupts = ck.filter((c) => c.status === 'interrupted').length;
  const converged = ck.some((c) => c.stop && c.stop.converged);
  const cards = ck.map((c) => {
    const d = c.decision || {};
    const dl = c.delta || {};
    const st = c.stop || {};
    const spans = c.spans || [];
    const errs = spans.filter((s) => s.role === 'error').length;
    const rows = [];
    if (d.deficiency) rows.push(['deficiency', esc(d.deficiency)]);
    if (d.retrieve && d.retrieve.query)
      rows.push(['retrieve', `<code>${esc(d.retrieve.query)}</code> ${esc(d.retrieve.cite || '')}`]);
    if (d.proposed_fix) rows.push(['fix', esc(d.proposed_fix)]);
    if (dl.metric)
      rows.push(['delta', `${esc(dl.metric)}: <b>${esc(dl.before ?? '?')}</b> &rarr; <b>${esc(dl.after ?? '?')}</b> <span class="bar">bar ${esc(dl.bar ?? '?')}</span>`]);
    if (spans.length)
      rows.push(['spans', `${spans.length} executed${errs ? ` · <span class="err">⚠ ${errs} error${errs > 1 ? 's' : ''}</span>` : ''} <span class="muted">— executed, not narrated</span>`]);
    if (st.converged) rows.push(['stop', 'CONVERGED — bar met']);
    else if (st.max_iterations) rows.push(['stop', `round ${c.iteration} / ${esc(st.max_iterations)}`]);
    if (c.parent != null) rows.push(['parent', `#${esc(c.parent)} <span class="muted">(rollback point)</span>`]);
    if (c.human && c.human.decision)
      rows.push(['disposed', `<b>${esc(c.human.decision)}</b>${c.human.note ? ` — ${esc(c.human.note)}` : ''}`]);
    const awaiting = c.awaiting && c.awaiting.length
      ? `<div class="awaiting">⏸ AWAITING: ${c.awaiting.map(esc).join(' · ')} <span class="muted">— resume to dispose</span></div>` : '';
    return `<article class="ck ${esc(c.status)}">
      <header><span class="it">#${esc(c.iteration)}</span>
        <span class="op">${esc(c['gen_ai.operation.name'])}</span>
        <span class="badge ${esc(c.status)}">${esc(c.status)}</span>
        <time>${esc(c.ts)}</time></header>
      <dl>${rows.map(([k, v]) => `<div><dt>${esc(k)}</dt><dd>${v}</dd></div>`).join('')}</dl>
      ${awaiting}
    </article>`;
  }).join('\n');

  return `<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>observe · ${esc(run)}</title>
<style>
  :root{--bg:#fff;--fg:#16181d;--mut:#5b616e;--line:#d8dbe0;--card:#f7f8fa;--acc:#1a56db;
        --ok:#0a7d33;--warn:#b45309;--err:#c02626;--int:#7c3aed}
  @media(prefers-color-scheme:dark){:root{--bg:#111318;--fg:#e8eaed;--mut:#9aa0ac;--line:#2b2f38;
        --card:#191c22;--acc:#6aa0ff;--ok:#4ade80;--warn:#fbbf24;--err:#f87171;--int:#c084fc}}
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--fg);
       font:15px/1.5 ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
  main{max-width:860px;margin:0 auto;padding:2rem 1.25rem}
  h1{font-size:1.3rem;margin:0 0 .25rem}
  .sub{color:var(--mut);margin:0 0 1.5rem;font-size:.92rem}
  .sum{display:flex;flex-wrap:wrap;gap:.5rem;margin-bottom:1.75rem}
  .pill{border:1px solid var(--line);border-radius:999px;padding:.2rem .7rem;font-size:.82rem;color:var(--mut)}
  .pill b{color:var(--fg)}
  .ck{border:1px solid var(--line);border-left:3px solid var(--mut);border-radius:10px;
      background:var(--card);padding:.9rem 1.1rem;margin:0 0 .8rem}
  .ck.interrupted{border-left-color:var(--int)} .ck.approved{border-left-color:var(--ok)}
  .ck.rejected{border-left-color:var(--err)} .ck.edited{border-left-color:var(--warn)}
  .ck.running{border-left-color:var(--acc)}
  .ck header{display:flex;align-items:center;gap:.6rem;flex-wrap:wrap;margin-bottom:.5rem}
  .it{font-weight:700} .op{font-family:ui-monospace,monospace;font-size:.82rem;color:var(--acc)}
  time{margin-left:auto;color:var(--mut);font-size:.78rem;font-variant-numeric:tabular-nums}
  .badge{font-size:.72rem;text-transform:uppercase;letter-spacing:.03em;padding:.1rem .5rem;
         border-radius:5px;border:1px solid currentColor}
  .badge.interrupted{color:var(--int)} .badge.approved{color:var(--ok)}
  .badge.rejected{color:var(--err)} .badge.edited{color:var(--warn)} .badge.running{color:var(--acc)}
  dl{margin:0;display:grid;grid-template-columns:max-content 1fr;gap:.15rem .9rem}
  dl>div{display:contents} dt{color:var(--mut);font-size:.85rem} dd{margin:0}
  code{font-family:ui-monospace,monospace;font-size:.85em;background:var(--bg);
       border:1px solid var(--line);border-radius:4px;padding:.02rem .3rem}
  .bar{color:var(--mut);font-size:.82rem;margin-left:.4rem} .muted{color:var(--mut)} .err{color:var(--err)}
  .awaiting{margin-top:.5rem;color:var(--int);font-size:.86rem}
  footer{color:var(--mut);font-size:.78rem;margin-top:2rem;border-top:1px solid var(--line);padding-top:.8rem}
</style></head><body><main>
  <h1>observe · <code>${esc(run)}</code></h1>
  <p class="sub">human-in-loop checkpoint timeline — continuous observability, discrete control (PD-020)</p>
  <div class="sum">
    <span class="pill"><b>${ck.length}</b> checkpoint${ck.length === 1 ? '' : 's'}</span>
    <span class="pill"><b>${interrupts}</b> interrupt${interrupts === 1 ? '' : 's'}</span>
    <span class="pill"><b>${disposed}</b> disposed</span>
    <span class="pill">${converged ? '<b>converged</b> — bar met' : 'in progress'}</span>
  </div>
  ${cards}
  <footer>LangGraph HITL · OpenTelemetry GenAI semconv · Anthropic trustworthy agents — conformance in Trident PD-020.</footer>
</main></body></html>`;
}

// ── selftest: render a synthetic run, assert the view is non-vacuous ──────────────────────────────
function selftest() {
  const ck = [
    { runId: 'demo', iteration: 0, ts: 't0', 'gen_ai.operation.name': 'execute_tool', status: 'interrupted',
      decision: { deficiency: 'S14 recall', retrieve: { query: 'exception masking', cite: '[Ch10]' }, proposed_fix: 'inject S14' },
      spans: [{ role: 'ok' }, { role: 'error' }], delta: { metric: 'S14', before: 'False', after: 'True', bar: 'pass' },
      stop: { converged: false, max_iterations: 3 }, awaiting: ['approve', 'edit', 'reject'], human: null },
    { runId: 'demo', iteration: 1, ts: 't1', 'gen_ai.operation.name': 'eval', status: 'approved', parent: 0,
      decision: {}, spans: [], delta: {}, stop: { converged: true, max_iterations: 3 }, human: { decision: 'approved' } },
  ];
  const html = render('demo', ck);
  const must = ['execute_tool', 'S14', 'False', 'True', '⚠ 1 error', 'CONVERGED', 'approved',
                'rollback point', 'AWAITING', 'PD-020'];
  const missing = must.filter((m) => !html.includes(m));
  if (missing.length) die(`selftest FAIL — view missing: ${missing.join(', ')}`, 2);
  if (html.length < 1500) die('selftest FAIL — rendered HTML implausibly short', 2);
  console.log(`observe-dashboard selftest: ok — ${must.length} signals present, ${html.length} bytes rendered`);
  process.exit(0);
}

if (has('selftest')) selftest();

const run = flag('run') || die('usage: observe-dashboard.mjs --run <id> [--dir <base>] [--out <file>] | --selftest');
const base = path.resolve(flag('dir', process.cwd()));
const ledger = path.join(base, 'runs', run, 'checkpoints.jsonl');
if (!fs.existsSync(ledger)) die(`no checkpoint ledger for run ${run}: ${ledger}`);
const ck = fs.readFileSync(ledger, 'utf8').split('\n').filter((l) => l.trim()).map((l) => JSON.parse(l));
if (!ck.length) die(`run ${run} has no checkpoints`, 2);
const html = render(run, ck);
const out = flag('out', null);
if (out) {
  fs.writeFileSync(out, html);
  console.log(`observe-dashboard: ${ck.length} checkpoint(s) -> ${out}`);
} else {
  process.stdout.write(html);
}
process.exit(0);
