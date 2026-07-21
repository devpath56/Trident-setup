// thread-ledger — Simba's durable INTENT LEDGER, deterministic. Runs on the Stop hook.
//
// Simba is "a durable memory of your intent" whose IntentCard is "re-asserted every loop, not
// regenerated from scratch". This prong is that ledger for a whole session: on every Stop it re-reads
// the session transcript and re-asserts, as a table, WHAT HAPPENED TO EACH USER REQUEST — shipped in a
// PR, research-only, test-failed, logged as a CF, completed, or still open. Completed items sink to the
// bottom so the open threads are always on top.
//
// Two halves, honestly labelled:
//   - request extraction is EXACT   — genuine user prompts carry `promptSource`; tool-results / interrupt
//     markers / system-reminders do not, so they are filtered deterministically.
//   - disposition is HEURISTIC      — inferred from the ACTUAL tool-trace of the request's turns (which
//     tools ran, git/gh calls, failing test results, CF appends), never from prose vibes. Anything the
//     signals can't type defaults to OPEN — never a silent COMPLETED (the Auditor's "default to FAIL,
//     prove the pass" discipline; no silent green).
//
// Usage:
//   node prongs/thread-ledger.mjs stop                         # hook mode: reads {session_id,
//        transcript_path, cwd} as JSON on stdin, writes runs/<session>/thread-ledger.{md,jsonl}
//   node prongs/thread-ledger.mjs stop --transcript <f> --session <id> [--dir <base>]   # manual/test
//   node prongs/thread-ledger.mjs show [--dir <base>]          # print the newest ledger under runs/
//   node prongs/thread-ledger.mjs --selftest                   # non-vacuous classifier+sort assertions
//
// Exit: 0 ok (never blocks the Stop) · 1 selftest failed · 2 usage.
import fs from 'node:fs';
import path from 'node:path';

const argv = process.argv.slice(2);
const cmd = argv[0];
const flag = (k, d) => { const i = argv.indexOf(`--${k}`); return i >= 0 ? argv[i + 1] : d; };
const has = (k) => argv.includes(`--${k}`);
const die = (m, c = 2) => { console.error(m); process.exit(c); };

// ── transcript parsing ─────────────────────────────────────────────────────────
const textOf = (content) => {
  if (typeof content === 'string') return content;
  if (Array.isArray(content)) return content.filter((b) => b && b.type === 'text').map((b) => b.text || '').join(' ');
  return '';
};
// a genuine user request: user-role, has promptSource (synthetic tool/interrupt messages lack it),
// non-empty text, and not an AskUserQuestion answer echo.
const isPrompt = (r) => {
  if (r.type !== 'user' || !r.promptSource) return false;
  const t = textOf(r.message && r.message.content).trim();
  if (!t) return false;
  if (/^Your questions have been answered/.test(t)) return false;
  return true;
};
const rawText = (c) => (typeof c === 'string' ? c : JSON.stringify(c || ''));

function extract(rows) {
  const reqs = [];
  let cur = null;
  for (const r of rows) {
    if (isPrompt(r)) {
      const t = textOf(r.message.content).trim();
      cur = { text: t.replace(/\s+/g, ' ').slice(0, 90), ts: r.timestamp || null,
              tools: [], bash: [], edits: [], asst: '', results: [], interrupted: false };
      reqs.push(cur);
      continue;
    }
    if (!cur) continue;
    if (r.type === 'assistant') {
      for (const b of (r.message && r.message.content) || []) {
        if (!b || typeof b !== 'object') continue;
        if (b.type === 'text') cur.asst += ' ' + (b.text || '');
        if (b.type === 'tool_use') {
          cur.tools.push(b.name);
          if (b.name === 'Bash') cur.bash.push((b.input && b.input.command) || '');
          if (['Edit', 'Write', 'NotebookEdit'].includes(b.name)) cur.edits.push((b.input && b.input.file_path) || '');
        }
      }
    } else if (r.type === 'user') {
      const c = r.message && r.message.content;
      if (/\[Request interrupted by user/.test(rawText(c))) cur.interrupted = true;
      if (Array.isArray(c)) for (const b of c) {
        if (b && b.type === 'tool_result')
          cur.results.push({ err: !!b.is_error, text: (typeof b.content === 'string' ? b.content : JSON.stringify(b.content || '')).slice(0, 4000) });
      }
    }
  }
  return reqs;
}

// ── deterministic disposition (from the trace) ──────────────────────────────────
const TEST_CMD = /\b(pytest|npm\s+test|jest|gate\.py|gate_durability|score\.py|rag_eval|craft\.py|--selftest|\btests?\b)/i;
const RANK = { 'TEST-FAILED': 0, 'OPEN': 1, 'COMPLETED': 2, 'SHIPPED': 3, 'LOGGED': 4, 'RESEARCH-ONLY': 5 };

function classify(q) {
  const bash = q.bash.join('\n');
  const res = q.results.map((r) => r.text).join('\n');
  const txt = q.asst + '\n' + res;
  const mutated = q.edits.length > 0;
  const usedTool = q.tools.length > 0;

  const shipped = /\b(git\s+commit|git\s+push|gh\s+pr\s+create)\b/.test(bash) ||
    /\bPR\s?#\d+/.test(q.asst) || /github\.com\/[^\s)]+\/pull\/\d+/.test(txt);
  const logged = /failures\/[^\s'"]*\.jsonl/.test(bash) || /appended\s+CF-\d+/i.test(txt) ||
    /CF-\d+[^\n]*failures\.jsonl/i.test(res);
  const failedTest = q.bash.some((c) => TEST_CMD.test(c)) &&
    (q.results.some((r) => r.err) || /\b(FAIL|Traceback|AssertionError|Error:)\b/.test(res));

  let status, evidence = '—';
  if (shipped) {
    status = 'SHIPPED';
    const m = q.asst.match(/PR\s?#\d+/) || txt.match(/pull\/(\d+)/) || bash.match(/git\s+commit/);
    evidence = m ? (m[0].startsWith('PR') ? m[0] : m[1] ? `PR #${m[1]}` : 'commit') : 'commit';
  } else if (logged) {
    status = 'LOGGED';
    const m = txt.match(/CF-\d+/);
    evidence = m ? m[0] : 'CF';
  } else if (failedTest) {
    status = 'TEST-FAILED';
    evidence = (q.bash.find((c) => TEST_CMD.test(c)) || '').slice(0, 40);
  } else if (q.interrupted && !mutated) {
    status = 'OPEN'; evidence = 'interrupted';
  } else if (mutated) {
    status = 'COMPLETED';
    evidence = [...new Set(q.edits.map((f) => (f || '').split('/').pop()))].filter(Boolean).slice(0, 3).join(', ') || 'edited';
  } else if (usedTool) {
    status = 'RESEARCH-ONLY'; evidence = `${q.tools.length} read-only tool call(s)`;
  } else if (q.asst.trim()) {
    status = 'RESEARCH-ONLY'; evidence = 'answered';
  } else {
    status = 'OPEN';
  }
  return { status, evidence };
}

function build(reqs) {
  const rows = reqs.map((q, i) => { const c = classify(q); return { n: i + 1, request: q.text, ...c, interrupted: q.interrupted, tools: [...new Set(q.tools)], ts: q.ts }; });
  // stable sort by rank: open/failed on top, completed-like at the bottom
  return rows.map((r, i) => [r, i]).sort((a, b) => (RANK[a[0].status] - RANK[b[0].status]) || (a[1] - b[1])).map(([r]) => r);
}

// ── rendering ───────────────────────────────────────────────────────────────────
const esc = (s) => String(s).replace(/\|/g, '\\|');
function renderMd(rows, sid, ts) {
  const open = rows.filter((r) => r.status === 'OPEN' || r.status === 'TEST-FAILED').length;
  const counts = {};
  for (const r of rows) counts[r.status] = (counts[r.status] || 0) + 1;
  const tally = Object.entries(counts).map(([k, v]) => `${k}:${v}`).join(' · ');
  const L = [
    `# Thread ledger — session \`${sid}\``,
    ``,
    `_re-asserted on Stop (Simba intent ledger) · ${ts} · ${rows.length} requests · **${open} open** · ${tally}_`,
    ``,
    `| # | request | status | evidence |`,
    `|---|---------|--------|----------|`,
    ...rows.map((r) => `| ${r.n} | ${esc(r.request)} | ${r.status} | ${esc(r.evidence)} |`),
    ``,
    `> disposition is heuristic (inferred from the executed tool-trace); request text is exact. Unclassifiable → OPEN, never a silent COMPLETED.`,
    ``,
  ];
  return L.join('\n');
}

// ── modes ─────────────────────────────────────────────────────────────────────
function runStop() {
  let payload = {};
  if (has('transcript')) payload = { transcript_path: flag('transcript'), session_id: flag('session', 'adhoc'), cwd: flag('dir', process.cwd()) };
  else { try { payload = JSON.parse(fs.readFileSync(0, 'utf8') || '{}'); } catch { payload = {}; } }

  const out = { suppressOutput: true };
  const tp = payload.transcript_path;
  if (!tp || !fs.existsSync(tp)) { process.stdout.write(JSON.stringify(out)); process.exit(0); } // never block the Stop
  const base = path.resolve(flag('dir', payload.cwd || process.cwd()));
  const sid = String(payload.session_id || 'session').replace(/[^\w.-]/g, '_');

  const rows = build(extract(fs.readFileSync(tp, 'utf8').split('\n').filter((l) => l.trim()).map((l) => { try { return JSON.parse(l); } catch { return null; } }).filter(Boolean)));
  const lastTs = (() => { try { const ls = fs.readFileSync(tp, 'utf8').trimEnd().split('\n'); for (let i = ls.length - 1; i >= 0; i--) { const o = JSON.parse(ls[i]); if (o.timestamp) return o.timestamp; } } catch { /* */ } return new Date().toISOString(); })();

  const dir = path.join(base, 'runs', sid);
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, 'thread-ledger.md'), renderMd(rows, sid, lastTs));            // idempotent overwrite
  fs.writeFileSync(path.join(dir, 'thread-ledger.jsonl'), rows.map((r) => JSON.stringify(r)).join('\n') + '\n');

  const open = rows.filter((r) => r.status === 'OPEN' || r.status === 'TEST-FAILED').length;
  if (open > 0) out.systemMessage = `🧭 ${open} open thread(s) — runs/${sid}/thread-ledger.md`;
  process.stdout.write(JSON.stringify(out));
  process.exit(0);
}

function runShow() {
  const base = path.resolve(flag('dir', process.cwd()));
  const runs = path.join(base, 'runs');
  if (!fs.existsSync(runs)) die('no runs/ dir yet', 0);
  let best = null, bestT = 0;
  for (const d of fs.readdirSync(runs)) {
    const f = path.join(runs, d, 'thread-ledger.md');
    if (fs.existsSync(f)) { const t = fs.statSync(f).mtimeMs; if (t > bestT) { bestT = t; best = f; } }
  }
  if (!best) die('no thread-ledger.md found', 0);
  process.stdout.write(fs.readFileSync(best, 'utf8'));
}

function selftest() {
  const mk = (o) => ({ text: 't', ts: null, tools: [], bash: [], edits: [], asst: '', results: [], interrupted: false, ...o });
  const cases = [
    ['shipped', mk({ bash: ['git commit -m x'], asst: 'done' }), 'SHIPPED'],
    ['pr-text', mk({ asst: 'opened PR #42' }), 'SHIPPED'],
    ['logged', mk({ bash: ['python3 - <<PY\nopen("failures/failures.jsonl","a")\nPY'], asst: 'appended CF-077' }), 'LOGGED'],
    ['testfail', mk({ bash: ['python3 engine/gate.py x'], results: [{ err: true, text: 'BLOCK' }] }), 'TEST-FAILED'],
    ['testfail-txt', mk({ bash: ['pytest'], results: [{ err: false, text: 'AssertionError: nope' }] }), 'TEST-FAILED'],
    ['research', mk({ tools: ['Read', 'Grep'], asst: 'here is the answer' }), 'RESEARCH-ONLY'],
    ['answered', mk({ asst: 'ok' }), 'RESEARCH-ONLY'],
    ['completed', mk({ tools: ['Write'], edits: ['prongs/x.mjs'] }), 'COMPLETED'],
    ['open-intr', mk({ interrupted: true, asst: 'was mid...' }), 'OPEN'],
    ['empty', mk({}), 'OPEN'],
  ];
  let ok = true;
  for (const [name, q, want] of cases) {
    const got = classify(q).status;
    if (got !== want) { console.error(`  FAIL ${name}: want ${want} got ${got}`); ok = false; }
  }
  // sort: a completed must never precede an open/test-failed
  const sorted = build([mk({ tools: ['Write'], edits: ['a'] }), mk({ interrupted: true, asst: 'x' })]);
  if (!(sorted[0].status === 'OPEN')) { console.error(`  FAIL sort: open item not on top (got ${sorted[0].status})`); ok = false; }
  // non-vacuous: a wrong expectation must fail
  if (classify(mk({ bash: ['git commit'] })).status !== 'SHIPPED') { console.error('  FAIL sanity'); ok = false; }
  console.log(ok ? 'selftest: PASS (10 classify cases + sort + sanity)' : 'selftest: FAIL');
  process.exit(ok ? 0 : 1);
}

// ── dispatch ────────────────────────────────────────────────────────────────────
if (has('selftest')) selftest();
else if (cmd === 'stop') runStop();
else if (cmd === 'show') runShow();
else die('usage: thread-ledger.mjs stop | show | --selftest   (see header)');
