// Content for the first-principles explainer. Plain data; App.jsx renders it.
// Every rendered element gets a stable id + data-anchor derived from these, so an Agentation
// annotation's captured selector maps 1:1 to a source block.

export const slug = (s) => s.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '')

export const DERIV = [
  { fail: 'Intent decays under recency', conseq: 'early goals get buried', what: 'The model weights recent tokens most, so the goal and the corrections you made early quietly lose salience as the session grows.', ev: 'CF-009 / 042 / 045', resp: "An agent whose only job is to hold your intent, loyal to you, re-asserted every loop so it can't be buried.", tag: 'Simba' },
  { fail: 'One long context rots', conseq: 'degradation + instruction collision', what: 'A single growing window fills with history, superseded versions, and tool output; signal-to-noise falls and instruction sets blend.', ev: 'CF-009 / 011', resp: "Split the work into many small bounded loops, each rehydrated from typed artifacts, with no prong seeing another's scratch.", tag: 'scoped loops + context-contract' },
  { fail: 'Optimism lies', conseq: 'the maker grades itself high', what: "A model assessing its own output inflates 15 to 20 points and declares done when it isn't.", ev: 'CF-010', resp: 'A judge that is a different model, running deterministic checks before any rubric-judge, and failing closed.', tag: 'Auditor · Fable' },
  { fail: 'Wrong objective is costliest', conseq: 'build the wrong thing, correctly', what: 'The goal can be mis-specified from the start or drift mid-session; every downstream round then optimizes the wrong target.', ev: 'CF-057', resp: 'Gate both feasibility and intent-consistency before any build begins; hard-block on a conflict.', tag: 'Phase-0 gate' },
  { fail: 'Compaction can drop an invariant', conseq: 'a must-have lost while summarizing', what: 'Compressing context to save tokens can silently delete a hard requirement that lived only in the discarded history.', ev: 'CF-042 / 045', resp: 'Keep invariants out-of-band, and run each invariant as an executable check before promoting a compacted state.', tag: 'fail-closed gate' },
  { fail: 'Failures repeat', conseq: 'no memory across sessions', what: 'The same mistake recurs because nothing turned the last one into a durable check.', ev: 'the SSOT', resp: 'One shared failures log; every real mistake becomes a permanent deterministic guard the Auditor runs.', tag: 'failures.jsonl' },
]

export const PRONGS = [
  { n: 'Do-er · Opus', loyal: 'loyal to: shipping', detail: 'Does the actual work. Deliberately kept off its own scorecard, because the maker is the optimist.', never: 'never grades its own output' },
  { n: 'Simba', loyal: 'loyal to: you', detail: "Holds a durable IntentCard, reads the Do-er's output (never its reasoning), and flags drift from your intent.", never: 'never edits, argues, or acts on drift itself. It proposes; the Auditor disposes.' },
  { n: 'Auditor · Fable', loyal: 'loyal to: the artifact', detail: 'A different model from the Do-er. Runs deterministic detectors first, a rubric-judge last, and decides the response to drift.', never: "never free-form self-assessment, and never the Do-er's model" },
]

export const STEPS = [
  { phase: 'Phase 0', h: "Prove it's feasible and correctly aimed, before building", p: "Simba pins the IntentCard (goal + the __ must-have + 'never weaken it'). The Do-er lists assumptions; the Auditor names the riskiest and the cheapest probe.", real: "probe: extract + execute a Do-er's code → passed, so the build proceeds" },
  { phase: 'Loops 1–3', h: 'Build one feature per bounded loop, rehydrating context', p: "Each round the Do-er sees only the frozen packet + current code + this round's delta, not the whole transcript.", real: 'measured: accumulate +1191 chars/round · contract +181/round' },
  { phase: 'Drift guard', h: 'The pinned intent keeps the must-have salient', p: "Because the invariant lived in Simba's IntentCard, out-of-band and re-asserted, it stayed in view as features piled on. The contract arm defended it proactively.", real: 'contract arm extended __ rejection to [section] names · full-history arm left [__proto__] open' },
  { phase: 'Compaction', h: 'Past the crossover, compact history behind a gate', p: 'Once per-round history outweighs the artifact (around round 4), drop the history. Before promoting, execute the invariant. A lossy compaction is blocked by construction.', real: 'cut 31% at R3 → 43% at R4 → 56% at R6 · gate: BLOCK lossy, PROMOTE intact (6/6)' },
  { phase: 'Audit + close', h: 'A different model certifies, fail-closed; a new failure becomes a check', p: 'The Fable Auditor ran the deterministic tests and certified the verdict, refusing to let an unregistered bonus finding upgrade it.', real: 'verdict honored the pre-registered bar: efficiency FAIL, safety PASS' },
]
