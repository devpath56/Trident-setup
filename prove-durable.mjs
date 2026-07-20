// prove-durable — for every change since the last commit, prove it is gated, or expose that
// it is a silent edit that will decay.
//
// THE DEFINITION, made executable:
//   A change is DURABLE iff an executed check fails when the change is reverted.
//   Anything else is prose or a lucky edit: it reverts with every gate still green, so nothing
//   stops it drifting back. This whole harness exists because that decay is the default.
//
// It does by script what you otherwise do by hand: revert each change, run the checks, see if
// anything notices. Two modes, because "reverting" means two different things:
//
//   modified file  -> restore it to HEAD, run the check command. If the suite goes RED, the
//                     change is gated. If it stays GREEN, the edit is ungated (silent-revert).
//   new file       -> move it aside, run the check command. If the suite goes RED, something
//                     depends on it (a wired checker). If it stays GREEN, nothing calls it: a
//                     checker with no trigger, the exact rot this repo keeps finding.
//
// Requires git, because durability-by-reversion needs a baseline to revert TO. A repo with no
// history cannot be proven durable at all, which is itself a finding this reports rather than
// hides.
//
// Usage:
//   node prove-durable.mjs [--repo <dir>] [--check "<cmd>"] [--base <ref>]
//   defaults: repo = cwd, base = HEAD, check = auto-detected
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const argv = process.argv.slice(2);
const flag = (k, d) => { const i = argv.indexOf(`--${k}`); return i >= 0 ? argv[i + 1] : d; };
const REPO = path.resolve(flag('repo', process.cwd()));
const BASE = flag('base', 'HEAD');
let CHECK = flag('check', null);

const git = (...a) => spawnSync('git', ['-C', REPO, ...a], { encoding: 'utf8' });
const die = (msg, code = 2) => { console.error(msg); process.exit(code); };

// ── preconditions ─────────────────────────────────────────────────────────────
if (git('rev-parse', '--is-inside-work-tree').status !== 0) {
  die(`\n  ${REPO} is not a git repository.\n` +
      `  Durability by reversion needs a baseline to revert to, and there is none.\n` +
      `  THIS IS ITSELF A DURABILITY GAP: no history means no diff, no baseline, no proof.\n` +
      `  Enable it:  git -C ${REPO} init && git -C ${REPO} add -A && git -C ${REPO} commit -m baseline\n`, 3);
}

// Auto-detect the check command if not given: prefer the repo's own gate.
if (!CHECK) {
  if (fs.existsSync(path.join(REPO, 'tests/selftest.py'))) CHECK = 'python3 tests/selftest.py';
  else if (fs.existsSync(path.join(REPO, 'package.json'))) {
    const pkg = JSON.parse(fs.readFileSync(path.join(REPO, 'package.json'), 'utf8'));
    if (pkg.scripts?.['verify-render']) CHECK = 'npm run -s verify-render';
    else if (pkg.scripts?.test) CHECK = 'npm test --silent';
  }
  if (!CHECK) die(`  could not auto-detect a check command. Pass --check "<cmd>"`);
}

const runCheck = () => {
  const r = spawnSync('bash', ['-c', CHECK], { cwd: REPO, encoding: 'utf8', timeout: 180_000 });
  return { green: r.status === 0, code: r.status };
};

// ── changed files ─────────────────────────────────────────────────────────────
const lines = (s) => s.split('\n').map((l) => l.trim()).filter(Boolean);
// Noise that is never a durability target: OS cruft, logs, lockfiles, vendored deps.
const NOISE = /(^|\/)(\.DS_Store|.*\.log|package-lock\.json|node_modules\/)/;
const modified = [...new Set([
  ...lines(git('diff', '--name-only', BASE).stdout),
  ...lines(git('diff', '--name-only', '--cached').stdout),
])].filter((f) => !NOISE.test(f));
const SELF = path.basename(new URL(import.meta.url).pathname);
const untracked = lines(git('ls-files', '--others', '--exclude-standard').stdout)
  .filter((f) => !NOISE.test(f) && path.basename(f) !== SELF);  // a tool does not audit itself

if (!modified.length && !untracked.length) {
  console.log(`\n  no changes since ${BASE}. Nothing to prove.\n`);
  process.exit(0);
}

// ── baseline must be green, or the proof is meaningless ───────────────────────
console.log(`\n  prove-durable · ${path.basename(REPO)} · vs ${BASE}`);
console.log(`  check: ${CHECK}\n`);
process.stdout.write(`  baseline (all changes in place)... `);
const base = runCheck();
console.log(base.green ? 'GREEN' : `RED (exit ${base.code})`);
if (!base.green) {
  die(`\n  The suite is already red WITH your changes. Durability is undefined until it is green.\n` +
      `  Fix the suite first, then prove durability.\n`, 1);
}

// ── restore safety: whatever we perturb, we put back, even on crash ───────────
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'durable-'));
const restores = [];
const cleanup = () => { for (const f of restores.splice(0)) { try { f(); } catch {} } };
process.on('exit', cleanup);
process.on('SIGINT', () => { cleanup(); process.exit(130); });

const results = [];

// modified files: revert to baseline, expect the suite to notice. A file that was ADDED since
// BASE has no baseline version, so `git checkout BASE -- f` errors ("pathspec did not match")
// and silently no-ops, which used to report the file as UNGATED even when a gate would catch
// its removal. Detect that case and REMOVE the file instead (the new-file probe), so an
// older --base gives the same honest answer as --base HEAD.
for (const f of modified) {
  const abs = path.join(REPO, f);
  if (!fs.existsSync(abs)) continue; // deleted file; skip
  const keep = path.join(tmp, f.replace(/[/\\]/g, '__'));
  fs.copyFileSync(abs, keep);
  const undo = () => fs.copyFileSync(keep, abs);
  restores.push(undo);

  const existedAtBase = git('cat-file', '-e', `${BASE}:${f}`).status === 0;
  if (existedAtBase) {
    // Revert the WORKING TREE ONLY. `git checkout BASE -- f` also STAGES the base blob in the index
    // and never un-stages it — undo() below restores the file but not the index, so the index is
    // left holding the base version. A caller's later `git checkout -- .` then restores that base
    // content and silently drops the change (this corrupted two commits before it was found). Write
    // the base blob straight to the file; the index is never touched. `buffer` preserves exact bytes.
    const blob = spawnSync('git', ['-C', REPO, 'show', `${BASE}:${f}`], { encoding: 'buffer', maxBuffer: 1 << 26 });
    fs.writeFileSync(abs, blob.stdout);
    process.stdout.write(`  revert ${f} ... `);
  } else {
    fs.rmSync(abs);                          // added since BASE: no baseline, so remove it
    process.stdout.write(`  remove ${f} (new since base) ... `);
  }
  const r = runCheck();
  console.log(r.green ? 'still GREEN  (UNGATED)' : `RED  (gated)`);
  results.push({ file: f, kind: existedAtBase ? 'modified' : 'new', durable: !r.green,
                 isCode: /\.(mjs|js|py|sh|ts)$/.test(f) });

  undo();                                    // restore my change
  restores.splice(restores.indexOf(undo), 1);
}

// new files: remove, expect the suite to notice IF anything depends on it.
for (const f of untracked) {
  if (f.startsWith('.git')) continue;
  const abs = path.join(REPO, f);
  const keep = path.join(tmp, 'new__' + f.replace(/[/\\]/g, '__'));
  fs.copyFileSync(abs, keep);
  const undo = () => fs.copyFileSync(keep, abs);
  restores.push(undo);

  fs.rmSync(abs);
  process.stdout.write(`  remove ${f} ... `);
  const r = runCheck();
  const isCode = /\.(mjs|js|py|sh|ts)$/.test(f);
  console.log(r.green ? `still GREEN  (${isCode ? 'ORPHAN: nothing calls it' : 'not read by the check'})` : `RED  (wired)`);
  results.push({ file: f, kind: 'new', durable: !r.green, isCode });

  undo();
  restores.splice(restores.indexOf(undo), 1);
}

fs.rmSync(tmp, { recursive: true, force: true });

// ── gate-reality layer: are the checks that "noticed" themselves real? ────────
// A change can look durable because a check went red, while that check is hardcoded and would
// go red at anything. If the repo ships a mutation tester, run it so a durable verdict is not
// resting on a fake gate.
let mutation = null;
if (fs.existsSync(path.join(REPO, 'prongs/mutate.py'))) {
  const m = spawnSync('python3', ['prongs/mutate.py'], { cwd: REPO, encoding: 'utf8', timeout: 120_000 });
  mutation = m.status === 0;
}

// ── scorecard ─────────────────────────────────────────────────────────────────
console.log(`\n  ── scorecard ─────────────────────────────────────`);
for (const r of results) {
  const tag = r.durable ? 'DURABLE ' : (r.kind === 'new' ? (r.isCode ? 'ORPHAN  ' : 'UNREAD  ') : 'UNGATED ');
  console.log(`  ${tag} ${r.kind.padEnd(8)} ${r.file}`);
}
if (mutation !== null) {
  console.log(`\n  gate-reality (mutate.py): ${mutation ? 'PASS, the gates are real' : 'FAIL, a gate is hardcoded'}`);
}

const weak = results.filter((r) => !r.durable);
console.log('');
if (weak.length) {
  console.log(`  ${weak.length} of ${results.length} change(s) will NOT persist:`);
  for (const r of weak) {
    const why = r.kind !== 'new' ? 'reverts with every gate green. Add a check with a negative control'
      : r.isCode ? 'a checker nothing calls. Wire it into the check command'
      : 'a data/content file the check never reads. Gate it, or accept it is not load-bearing';
    console.log(`    - ${r.file}: ${why}`);
  }
}
const allDurable = weak.length === 0 && mutation !== false;
console.log(`\n  ${results.length - weak.length}/${results.length} durable` +
  (mutation === false ? '  (but a gate is hardcoded: treat durable verdicts as suspect)' : ''));
console.log(`RESULT: ${allDurable ? 'ALL CHANGES DURABLE' : 'DURABILITY GAPS OPEN'}\n`);
process.exit(allDurable ? 0 : 1);
