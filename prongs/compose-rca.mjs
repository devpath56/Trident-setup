// compose-rca — builds the Auditor's RCA-on-fail prompt from prong artifacts on disk, and REFUSES
// to build one unless a real FAILING verdict exists for the run (the evidence gate).
//
// This is the root-cause half, not the detection half (house-rule 1): a validator that notices
// afterward that an rca cited a clean verdict is useful; a composer that cannot produce an RCA
// prompt without a real failing verdict makes that accident impossible. Same shape as
// compose-auditor.mjs, which cannot emit an audit prompt without an IntentCard.
//
// WHAT THE RCA IS (Change 3 / TraceRoot's root-cause pillar, bent to Trident): when a Verdict fails,
// instead of a blind re-dispatch, localize the failure (which span, which detector, why) and propose
// a targeted fix — 'output' (a primer for the fresh Do-er) or 'harness' (a CF/PD proposal routed
// through the log-failure Auditor-approval gate). It is fail-closed: gate is always 'proposal'. An
// RCA never auto-applies a fix; a human/the Auditor promotes it.
//
// Usage:
//   node prongs/compose-rca.mjs <runId>            # emit the RCA prompt
//   node prongs/compose-rca.mjs <runId> --check    # exit 2 if there is no failing verdict, print nothing
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const LEDGER = process.env.PRONGS_PATH || path.join(HERE, 'prongs.jsonl');
const FAILURES = path.join(HERE, '..', 'failures', 'failures.jsonl');

const argv = process.argv.slice(2);
const runId = argv.find((a) => !a.startsWith('--'));
const checkOnly = argv.includes('--check');

if (!runId) {
  console.error('usage: node prongs/compose-rca.mjs <runId> [--check]');
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

// ── EVIDENCE GATE. No failing verdict, no RCA. An RCA diagnoses a FAIL, never a pass.
const failed = (v) => (v.detectors || []).some((d) => String(d.result || '').toLowerCase() === 'fail');
const verdict = forRun('verdict').filter(failed).at(-1);
if (!verdict) {
  console.error(`REFUSED: run ${runId} has no verdict with a failing detector in ${path.relative(process.cwd(), LEDGER)}`);
  console.error(`  An RCA diagnoses a FAIL. With no failing verdict there is nothing to diagnose —`);
  console.error(`  diagnosing a clean pass is the accident this gate exists to stop (house-rule 1).`);
  console.error(`  Run the audit first (Phase 2); an RCA opens only when a detector actually fails.`);
  process.exit(2);
}

const intent = forRun('intent').at(-1);
const fails = (verdict.detectors || []).filter((d) => String(d.result || '').toLowerCase() === 'fail');

// Pull the guard text for each failing CF detector, so the RCA is anchored to what the detector
// was defending — not just its id. The RCA reasons about WHY that guard's signal fired.
const failures = read(FAILURES);
const cfById = new Map(failures.map((f) => [f.id, f]));
const guardFor = (detectorId) => {
  const m = String(detectorId || '').match(/CF-\d{3,}/);
  const cf = m && cfById.get(m[0]);
  return cf ? `${cf.title} — guard: ${cf.guard}` : '(no CF guard on record; detector is free-text)';
};

if (checkOnly) {
  console.log(`ok: run ${runId} has a failing verdict (${verdict.id}, ${fails.length} failing detector(s))`);
  process.exit(0);
}

const line = (o) => `- ${o}`;
console.log(`You are the **Auditor**, running your **RCA-on-fail** sub-phase (Sonnet 5, never the Do-er's model).

Read your contract at .claude/skills/auditor/SKILL.md ("RCA-on-fail") and .claude/skills/references/house-rules.md.

A Verdict for run ${runId} FAILED. Before Phase-3 re-dispatch, localize the failure and propose ONE
targeted fix. You see the Output, the extracted Spans (run \`node prongs/spans.mjs <transcript>\`), the
IntentCard, and the failing detectors below — never the Do-er's chain-of-thought (no-leak, house-rule 10).

## Failing Verdict ${verdict.id}
${fails.map((d) => line(`${d.detector_id}: ${d.signal_seen ?? '(no signal recorded)'}` +
  (d.span_ref ? `  [span: ${d.span_ref}]` : '  [span: NOT localized — find it in the Spans]'))).join('\n')}

## What each failing detector was defending
${fails.map((d) => line(guardFor(d.detector_id))).join('\n')}

${intent ? `## IntentCard ${intent.id}   (source: ${intent.intent_source})
- goal: ${intent.goal}
- in scope: ${(intent.scope?.in_scope ?? []).join(' · ') || '(none recorded)'}
${(intent.must_haves ?? []).map((m) => line(`must have: ${m}`)).join('\n')}
${(intent.forbid ?? []).map((m) => line(`FORBIDDEN: ${m}`)).join('\n')}` : '## IntentCard\n- none on record for this run'}

## Your task
For the failing verdict, produce a localized root-cause and ONE fix proposal.
- **Localize:** name the exact failing span (from the Spans) — the tool call whose output/error
  produced the signal. If the verdict already carries a span_ref, confirm or correct it.
- **Root cause:** WHY the signal fired — one specific, falsifiable sentence. Not "the Do-er made a
  mistake"; name the mechanism.
- **Target ONE lane:**
  - \`output\` — the failure is in this run's artifact. Your fix_hypothesis becomes the *specific*
    primer for the fresh Do-er in Phase 3 (the failing detector + the span + the cause), not "try again".
  - \`harness\` — the failure is a mode the harness should have caught and did not. Draft a CF (or PD)
    proposal and route it through \`log failure\` (Auditor-approves, then commits). NEVER auto-commit here.

## Output
Nested bullets and a table only (house-rule 16).
- a table: | failing_detector | failing_span | root_cause | target | fix_hypothesis |

Then append your RCA to prongs/prongs.jsonl as one JSON line:
{"id":"rca-<short>","kind":"rca","ts":"<iso>","runId":"${runId}","verdictId":"${verdict.id}","failing_detector":"${fails[0]?.detector_id ?? '...'}","failing_span_ref":"<span id>","root_cause":"...","target":"output|harness","fix_hypothesis":"...","gate":"proposal"}

\`gate\` MUST be "proposal": an RCA is DETECTION, not root-cause — it can never itself pass or apply
work (house-rule 1). validate_prongs check_rca rejects any other gate value, an rca with no failing
verdict, a missing failing_span_ref, or a placeholder root_cause. Fail closed: if you cannot localize
the failure to a span, say so in root_cause and target \`output\` for a human-guided re-loop — never fabricate a span.`);
