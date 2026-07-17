# auto-research — hackathon idea pipeline (durable, shippable)

**Input:** an event (Luma link / uploaded page) + your resume skills to harden.
**Output:** ranked, evidence-scored project ideas + a winner with a build plan, optimized for the real
goal — **meaningful connections → feedback → referrals**, not just prizes.

Adapted from the people-first hackathon-research methodology (Isha Mishra) and hardened by a live run
(see `../experiments/SESSION-FINDINGS.md`). Runs great wrapped in Trident (independent auditor keeps the
scores honest), or standalone.

## Invoke
> "run auto-research on this event" + the event data (or an uploaded page) + your skills list.

## Phase 0 — Intake (the feasibility gate)
Extract, from the event: sponsors/partner tools, prize tracks, judging criteria, judges + hosts, date/format.
- **Grey-case (no silent substitution):** if prize tracks or judging criteria aren't stated, do NOT invent
  them — score sponsor against the tool list and label any judging inference as inference.
- **Egress reality:** event pages (Luma) and many first-party sites are often blocked by org egress policy.
  On a gateway 403 / `connect_rejected`, STOP fetching and accept a user-paste / uploaded PDF / allowed-host
  mirror. Never fabricate the data (CF-004, CF-058).

## Phase 1 — People → Anchors (do this BEFORE ideating)
For each **judge, mentor, and host** (not just judges — hosts/mentors gate community + referrals), find
**first-party authored work** (their own GitHub, blog, talks) on the event's axis. Marketing/PR doesn't count.
Per anchor record: authored_work (+source), a **build-hook** (a project built ON their work you can demo to
them), and scores: `authored_depth` · `axis_relevance` · `engagement_likelihood`.
- **Affinity** feeds engagement_likelihood: shared **alma-mater / community** (e.g. IIT, Berkeley,
  women-in-tech) → warm intro + referral probability. Score affinity **only on publicly-stated affiliations**
  — never infer ethnicity/gender from a name/photo (CF-004/CF-018). Alma-mater overlap is the strongest signal.
- Research is egress-limited: lean on WebSearch snippets, tag `unverified-fetch`, never fabricate.

## Phase 2 — Generate → Score → Re-rank loop
Each idea must be **anchored on one named person's authored work** (build → demo → feedback → referral).
Score each 0–100 on four sub-scores, **weighted**:

    score = 0.35·anchor_fit + 0.30·skill_match + 0.20·feasibility + 0.15·sponsor_fit

- **anchor_fit (0.35):** genuinely builds on a specific person's real artifact → you'd demo it to them.
  Deflate name-drops and ideas "a step past" their literal work.
- **skill_match (0.30):** fit to your target skills.
- **feasibility (0.20):** one event-day; punish >1 hard subsystem or an uncertain external API.
- **sponsor_fit (0.15):** load-bearing sponsor use; **double-win bonus** when the sponsor IS the anchor
  person's own company (anchor-fit and sponsor-fit align — the pattern that won this run).

Loop mechanics (RAT-style, token-lean) — this is the **scored generate → re-rank loop** from
`../.claude/skills/references/method.md`; the mechanics live there, this pipeline supplies only the rubric above:
1. **R1:** generate 6 ideas; score all; show the four sub-scores + one evidence line each; top-3 leaderboard
   with one-line loss reasons; log the rest to a **roads-not-taken** ledger (never silently drop).
2. **R2+:** keep top-3; generate **3 new** biased toward the leader's strengths, **patching its weakest
   sub-score**; **delta re-score only the new/changed** (carry the rest); update leaderboard + ledger.
3. **Stop** when a candidate ≥85 AND two rounds fail to beat the best by >5, OR after 5 rounds.
4. **Grey-case guard:** if the feasibility leader is anchor/sponsor-thin, show both sub-scores + name the
   tension — never launder it into one number.

## Phase 3 — Output
The winner + a **build plan** mapping each **sponsor tool → feature → resume skill**, PLUS the
**anchor → referral path** (whose work it's built on, why they'll engage, the intro it earns).

**Dual-track build plan (PM ⇄ Engineer):** the winner's build plan is a **two-lane, time-boxed
swimlane** so both roles stay occupied and the feedback loop stays tight:
- **Engineer lane** — builds the loop (fork the anchor's template → wire the sponsor gate → deny→self-correct
  → harden → polish → freeze).
- **PM lane** — builds the eval + story **one slice ahead** (freeze acceptance cases → benchmark → score each
  slice vs acceptance → map features→resume-skills → demo script → approach the anchor with working evidence).
- **Sync every ~90 min** at a named checkpoint; the rule is **"the PM's eval of the last slice is the
  Engineer's next input."** Nobody idle; loop-engineering applied to the team. Emit it as its own artifact.

**Output format:** deliver as a **concise visual artifact (< 200 words)** — nested bullets, tables, and a
small theme-aware infographic — not a prose wall. Every checkpoint/leaderboard uses the same format.

**Per-anchor + decision set:** for the top-N anchors, emit **one artifact per person** — their best idea
(loop diagram · sponsor→feature→skill · anchor→referral) **plus a `🎯 Target intel` block** (role/reach ·
the authored artifact to build on · background · how to approach · affinity, with honesty flags on any
`unverified-fetch` item) — **plus one comparison artifact** (head-to-head table + a "pick this if…" guide)
so the user chooses.

**Preferred single deliverable — the drill-down:** collapse the whole decision into **one self-contained
clickable HTML** with three levels: **targets (ranked, with rubric-why + a unique insight + authored work)
→ click a target to expand its ideas (1 audited best + 2 alternates, ranked) → click an idea for its
details + the PM⇄Engineer dual-track build plan.** Native nested `<details>`, data-driven render, no
external assets (CSP-safe). Audited ideas carry a `✓ audited` badge; fresh ideas a `fresh, unaudited`
badge; keep the honesty flags. Worked example: `examples/loophack-drilldown.html`.

**Design taste — apply the `taste-skill`** (anti-slop frontend rules, github.com/leonxlnx/taste-skill,
`skills/taste-skill/SKILL.md`). Non-negotiables that bit us: **zero em-dashes anywhere**, **no scoring
bars with filled background tracks** (use monospace numeric readouts), **no section-number eyebrows**,
one dominant accent, off-white/off-black tokens (never `#000`/`#fff`), avoid Inter as default, theme-lock
one mode, and run its **pre-flight checklist** before publishing. If a brand is named (e.g. GrowthX:
cream `#F1EEE9` · ink `#080A0D` · yellow `#FFE57B` accent · pink `#FFC3D6` semantic), use that palette
deliberately and say so in a comment.

## Hands-free readiness — gated autonomy, not full
The pipeline runs itself between **three unavoidable human touchpoints** — everything else (research,
ideation, scoring, all artifacts, the dual-track build plan) runs unattended to "artifact set complete":
1. **Feed the event data** once at the start — blocked pages (Luma & first-party sites 403 at the gateway,
   CF-058) can't be fetched unattended; paste/upload is a HARD stop.
2. **Resolve a flagged objective conflict** — only fires if stated params clash with the reference method
   (CF-057); otherwise silent.
3. **Pick from the top-3** — the DECIDE step is the user's taste, not the score's (a HARD stop by design).

Residual risks to surface, never hide: inflated winner (mitigated by independent Fable audit, fail-closed),
unverified anchor intel (tag every `unverified-fetch`), and **stale facts** (anchors/events perish — add a
freshness note on any fact older than the event cycle). Emit a **hands-free readiness artifact** (failure
modes + the 3 gates) so the user knows exactly where it will pause.

## Honest-scoring guardrails (learned the hard way)
- **Independent audit beats self-score.** A self-scoring agent inflates ~15–20 pts (double-counts name-dropped
  sponsors) and will declare a false ≥85. Have a *different* model re-score; **fail closed** on any claim you
  can't verify (CF-004, CF-010). Expect an honest ceiling around ~80, not 90+.
- **Cross-check params vs. methodology at intake.** If the user gives explicit weights AND a reference
  methodology, confirm they agree before running — a wrong rubric wastes every downstream round (CF-057).
  *The biggest risk is the objective being wrong, not the scoring.*

## Templates
- `report.md` — Phase 0–1 summary (event packet + anchor table), ends "NEEDS YOU: confirm framing/anchor".
- `roads-not-taken.md` — dropped ideas + why + a revisit trigger.
- `build-plan.md` — winner, sponsor→feature→skill map, anchor→referral path, grey-case notes.
- `dual-track.md` — PM ⇄ Engineer swimlane (time-boxed lanes + ~90-min sync checkpoints).
- `hands-free.md` — failure-modes table + the 3 gated touchpoints (where it pauses unattended).
