# Session findings — Loophack live-run (evidence for shipping)

Running log from driving Trident (Arm B) on a real task: build an auto-research pipeline
(Luma event → ranked build ideas + why) for the Loop Engineering Hackathon. Two purposes:
**(A)** evidence-based CF/guard updates for Trident; **(B)** hardening the auto-research pipeline
into a durable, shippable artifact. Appended live; refine at session end.

## A · Trident CF candidates (evidence-based, from this run)

- **CF-057 (candidate) — Guardian pinned stated params but missed they conflict with the user's own supplied methodology.**
  Simba pinned the user's scoring weights (0.4 sponsor / 0.35 skill / 0.25 feasibility) verbatim, but the
  user had *also* supplied a people-first methodology (Isha's config). The two conflict (sponsor-first vs
  people-first); Simba never surfaced it — the user caught it 5 rounds in. *Guard:* when the user supplies
  BOTH explicit params AND a reference methodology, Simba cross-checks them and surfaces conflicts BEFORE
  the loop runs. Detector: structural (params-vs-methodology consistency check at intake).

- **CF-058 (candidate) — Target host blocked by org egress policy; auto-fetch cannot be retried around.**
  luma.com (and nickyt.co, nexla.com, metaview.ai, LinkedIn) returned 403 CONNECT at the egress gateway.
  Persistent policy denial — not bot-blocking, not a config bug. *Guard:* the pipeline's Phase-0 treats
  "target host may be egress-blocked" as a known feasibility risk; on a gateway 403, STOP and accept
  user-paste / uploaded PDF / an allowed-host mirror — never fabricate the data (CF-004). Detector:
  deterministic (proxy status `connect_rejected` → request paste, don't retry).

- **Auditor value CONFIRMED (CF-010 guard, live).** Do-er self-scored ideas were inflated ~15–20 pts vs
  the independent Fable auditor (sponsor name-drops like "Akash-for-batch-compute" deflated). In the v1
  A/B, single-Opus self-scored its winner to 86.7 and stopped; Trident's audit honestly capped at ~78.

- **CF-059 (candidate) — Sub-score scale drift.** The Do-er returned sub-scores on a 0–1 scale in one
  round and 0–100 in others. *Guard:* deterministic scale/schema check on every scored artifact before
  aggregation; normalize or reject.

- **Meta-finding — wrong objective beats execution rigor.** The largest failure mode this session was the
  *rubric being wrong*, not the scoring. No amount of Do-er/Auditor rigor fixes a mis-specified goal; the
  human stays the intent authority. Trident's job is to surface the objective conflict early (see CF-057),
  not to optimize harder.

## B · Auto-research pipeline learnings (for shipping)

- **People-first** (Isha's method): research anchors (judges/mentors/hosts) BEFORE ideating; anchor-fit is
  the top-weighted dimension. Final rubric: **anchor-fit 0.35 · skill-match 0.30 · feasibility 0.20 · sponsor 0.15.**
- **Anchor build-hook = build ON a person's authored work** (their repo/blog/talk) so you can demo it to
  them → real feedback → referral bond. This is the actual point of attending.
- **The "double-win" pattern:** anchor on a judge whose company is also a sponsor (Nick Taylor/Pomerium,
  Amey Desai/Nexla) → anchor-fit and sponsor-fit align instead of fighting.
- **Affinity heuristic** (shared IIT / Berkeley / Indian-tech / women-in-tech → warm intro + referral):
  came up THIN among the judges (no IIT/Berkeley match). Widen to mentors/hosts/attendees. Score affinity
  only on publicly-stated affiliations — never infer ethnicity/gender from a name (CF-004/CF-018).
- **Grey-cases (no silent substitution):** the event listed no prize tracks and no formal judging criteria
  → do NOT invent them; score sponsor against the tool list, label judging emphasis as inference.
- **Research is egress-limited:** many first-party pages 403 at the gateway → lean on WebSearch snippets,
  tag `unverified-fetch`, never fabricate.
- **Delta re-scoring (RAT-style):** re-score only new/changed ideas each round; keep top-3 + 3 new; keep a
  roads-not-taken ledger + a convergence ledger; stop at ≥85+stall or 5 rounds.

## C · Experiment v1 (banked)

Trident vs single-Opus on the sponsor-first rubric. Arm A (single Opus): winner self-scored **86.7**,
stopped R4. Arm B (Trident): winner audited **78.1**, ran to the 5-round cap, never faked ≥85. Findings:
(1) the independent auditor prevented the inflated win; (2) both optimized the wrong rubric — the human
caught it. Superseded by the people-first re-run as the real deliverable.
