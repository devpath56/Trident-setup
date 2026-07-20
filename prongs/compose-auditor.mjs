// compose-auditor — builds the Auditor's prompt from prong artifacts on disk, and REFUSES
// to build one if the artifacts are absent (C1).
//
// This is the root-cause half of the fix, not the detection half. A validator that notices
// afterwards that a verdict cited no IntentCard is useful; a composer that cannot produce a
// prompt without reading one makes the omission impossible. House-rule 1 ranks
// deterministic root-cause above deterministic detection for exactly this reason.
//
// The RCA said the orchestrator was the transport, and a manual transport step gets skipped.
// This removes the orchestrator from the path: the prompt is a function of the files.
//
// Usage:
//   node prongs/compose-auditor.mjs <runId>            # emit the prompt
//   node prongs/compose-auditor.mjs <runId> --check    # exit 2 if inputs are missing, print nothing
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
// Overridable for isolated smoke tests (Phase 0 probe p-durable).
const LEDGER = process.env.PRONGS_PATH || path.join(HERE, 'prongs.jsonl');
const FAILURES = path.join(HERE, '..', 'failures', 'failures.jsonl');

const argv = process.argv.slice(2);
const runId = argv.find((a) => !a.startsWith('--'));
const checkOnly = argv.includes('--check');

if (!runId) {
  console.error('usage: node prongs/compose-auditor.mjs <runId> [--check]');
  process.exit(2);
}

const read = (p) =>
  fs.existsSync(p)
    ? fs.readFileSync(p, 'utf8').split('\n').filter((l) => l.trim()).flatMap((l) => {
        try { return [JSON.parse(l)]; } catch { return []; }
      })
    : [];

const rows = read(LEDGER);
const forRun = (kind) => rows.filter((r) => r.kind === kind && r.runId === runId);

// ── C1 GATE. No IntentCard, no prompt. Not a warning.
const intent = forRun('intent').at(-1);
if (!intent) {
  console.error(`REFUSED: no IntentCard for run ${runId} in ${path.relative(process.cwd(), LEDGER)}`);
  console.error(`  The Auditor grades Output against intent. Without an IntentCard it would be`);
  console.error(`  grading against whatever it infers, which is the failure this gate exists to stop.`);
  console.error(`  Write one first: Simba step 0 (house-rule 15).`);
  process.exit(2);
}
if (intent.intent_source !== 'asked') {
  console.error(`REFUSED: IntentCard ${intent.id} has intent_source="${intent.intent_source}"`);
  console.error(`  An inferred goal is not a valid gate input (house-rule 15). Ask, then rewrite it.`);
  process.exit(2);
}

const assumptions = forRun('assumptions').at(-1);
const probe = forRun('probe').at(-1);
const drifts = forRun('drift').filter((d) => d.determination !== 'no-drift');

// ── AnticipatedFailures. The Auditor is the prong that reads the failures log; it predicts
// which CF modes THIS task is prone to and hands the list to Simba. 64 records existed all
// session and were never read for this purpose, because nothing composed them into a prompt.
const failures = read(FAILURES);
const taskText = `${intent.goal} ${JSON.stringify(intent.scope ?? {})}`.toLowerCase();
const anticipated = failures
  .map((f) => {
    const tags = (f.tags ?? []).join(' ');
    const hits = (f.tags ?? []).filter((t) => taskText.includes(t.split('-')[0])).length;
    return { id: f.id, title: f.title, tags, hits };
  })
  .filter((f) => f.hits > 0)
  .slice(0, 5);

if (checkOnly) {
  console.log(`ok: run ${runId} has an IntentCard (${intent.id}, source=${intent.intent_source})`);
  process.exit(0);
}

const line = (o) => `- ${o}`;
console.log(`You are the **Auditor**, the Sonnet 5 judge prong of Trident.

Read your contract at .claude/skills/auditor/SKILL.md and .claude/skills/references/house-rules.md.

## IntentCard ${intent.id}   (source: ${intent.intent_source})
This is what the user actually asked for. You grade the Output against THIS, not against your
own reading of the task.
- goal: ${intent.goal}
- in scope: ${(intent.scope?.in_scope ?? []).join(' · ') || '(none recorded)'}
- out of scope: ${(intent.scope?.out_of_scope ?? []).join(' · ') || '(none recorded)'}
${(intent.must_haves ?? []).map((m) => line(`must have: ${m}`)).join('\n')}
${(intent.forbid ?? []).map((m) => line(`FORBIDDEN: ${m}`)).join('\n')}
${intent.intent_riskiest ? line(`riskiest intent assumption: ${intent.intent_riskiest}`) : ''}

${assumptions ? `## AssumptionSet ${assumptions.id}
${(assumptions.assumptions ?? []).slice(0, 8).map((a) =>
  line(`[kill ${a.kill_power} × unc ${a.uncertainty}] ${a.assumption}`)).join('\n')}` : '## AssumptionSet\n- none recorded for this run'}

${probe ? `## Phase 0 probe ${probe.id}: ${probe.result}
- riskiest: ${probe.riskiest}
${probe.result === 'FAIL' ? '- **The probe FAILED.** A build past a failed probe needs a logged override row.' : ''}` : ''}

${drifts.length ? `## DriftFlags awaiting your decision
Simba proposes, you dispose. Each of these needs a ruling: re-inject, send back, or block.
An unresolved flag is an orphan and fails C2.
${drifts.map((d) => line(`${d.id} — ${d.determination} on ${d.drifted_from}: ${d.evidence ?? ''}`)).join('\n')}` : '## DriftFlags\n- none raised'}

${anticipated.length ? `## AnticipatedFailures: modes THIS task is prone to
Drawn from the failures ledger. Watch for these specifically.
${anticipated.map((f) => line(`${f.id}: ${f.title}`)).join('\n')}` : ''}

## Your output
Nested bullets and a table only, no prose paragraphs (house-rule 16).
- a table: | detector | PASS/FAIL | signal_seen | span_ref |
- on every FAIL, put the Spans entry that produced the signal in span_ref (the exact failing span);
  a pass may leave it blank
- a ruling on every DriftFlag above, by id
- then one line: APPROVED or REJECTED, with a one-line reason

Then append your Verdict to prongs/prongs.jsonl as one JSON line:
{"id":"v-<short>","kind":"verdict","ts":"<iso>","runId":"${runId}","phase":"audit","intentCardId":"${intent.id}","resolves":[${drifts.map((d) => `"${d.id}"`).join(',')}],"detectors":[{"detector_id":"...","result":"pass|fail","signal_seen":"...","span_ref":"<span id on a fail>"}],"grader_model":"sonnet","subject_model":"opus","irreversible":[]}

The \`phase\` field is REQUIRED: the audit is its own phase and must be opened by its own RAT.
Before you rule, confirm a RATVerdict for phase "audit" of this run exists (run
\`node prongs/rat.mjs --run ${runId} --phase audit ...\` if not). validate_prongs HR-0 rejects a
verdict in a phase with no RAT opening it: a RAT opens EVERY phase, not just Phase 0.

The \`irreversible\` field is REQUIRED (house-rule 6). It lists any irreversible action you took
(you should take none: you verify, you do not mutate), each as {action, approved_by}. An empty
list is the honest value for a read-only audit; a MISSING field fails the gate, because silence
is not the same as "none taken". \`grader_model\`/\`subject_model\` are required by house-rule 12.

Fail closed: if you cannot verify something by execution, it is a FAIL.`);
