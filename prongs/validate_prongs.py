#!/usr/bin/env python3
"""validate_prongs — the deterministic gate for prong-to-prong exchange (C0, C1, C2, C3).

Why this file exists, from the RCA:

  mechanism        file  schema  validator   records written
  failures.jsonl    y      y        y            64
  decisions.jsonl   y      y        y             7
  IntentCard        n      n        n             0
  DriftFlag         n      n        n             0

Every Trident mechanism with a file, a schema and a validator got used. Every one defined
only as a prose shape in a markdown skill file decayed to zero. The contract specified an
exchange and never specified a medium, so the orchestrator was the transport and the
transport is a manual step. Manual steps get skipped.

Checks, in house-rule 1 order:

  C0  every record is schema-valid and carries an id            (precondition)
  C1  every verdict names the IntentCard it read, and it exists (root-cause pair with compose)
  C2  every drift row has a matching verdict                    (detection)
  C3  no run follows a failed probe without a logged override   (root-cause)

Every check ships with a negative control that must fire. A gate whose control never fires
is not a gate.

Run:  python3 prongs/validate_prongs.py
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LEDGER = HERE / "prongs.jsonl"
SCHEMA = json.loads((HERE / "schema.json").read_text())


def read(path):
    if not path.exists():
        return []
    out = []
    for i, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            raise SystemExit(f"  unparseable JSON at {path.name}:{i}")
    return out


# ── emptiness ─────────────────────────────────────────────────────────────────
def _blank(v):
    """True if v is present-but-meaningless.

    The original test was `v in (None, "", [])`, which the C0 audit (verdict v-a0d8f024,
    DriftFlag d-c5c84966) defeated with two inputs that sailed through:

        goal:  "   "   -> a whitespace-only string is not ""
        scope: {}      -> an empty dict is not [] (Python: {} != [])

    Both are the same bug: a required field satisfied by something carrying no information.
    A gate that accepts a space bar is not checking that the field was answered.
    """
    if v is None:
        return True
    if isinstance(v, str):
        return not v.strip()
    if isinstance(v, (list, dict, tuple, set)):
        return len(v) == 0
    return False


# ── C0: schema ────────────────────────────────────────────────────────────────
def check_schema(rows):
    problems = []
    seen = set()
    for i, r in enumerate(rows, 1):
        kind = r.get("kind")
        if kind not in SCHEMA["enum"]["kind"]:
            problems.append(f"row {i}: kind {kind!r} not in {SCHEMA['enum']['kind']}")
            continue
        for f in SCHEMA["kinds"][kind]["required"]:
            if f not in r or _blank(r[f]):
                problems.append(f"row {i} ({kind}): missing required field {f!r}")
        rid = r.get("id")
        if rid in seen:
            problems.append(f"row {i}: duplicate id {rid!r}")
        seen.add(rid)
        if kind == "intent" and r.get("intent_source") not in SCHEMA["enum"]["intent_source"]:
            problems.append(f"row {i}: intent_source {r.get('intent_source')!r} invalid")
        if kind == "probe" and r.get("result") not in SCHEMA["enum"]["result"]:
            problems.append(f"row {i}: result {r.get('result')!r} invalid")
    return problems


# ── C0-DEP: the schema still DECLARES the kinds/fields the validators CONSUME ──
# check_fanout_independence reads `fanout` rows; check_deferred_assumption_gate reads the
# `phase` field off `assumptions` rows. Those gates only constrain real rows because check_schema
# rejects a row of a declared kind that is missing a declared-required field. Revert schema.json —
# drop `fanout` from enum.kind, or drop `phase` from the assumptions required list — and check_schema
# stops rejecting a phase-less assumptions row or an unknown fanout kind, so the downstream gate goes
# silently toothless while every green tick still prints. This check pins the dependency: the schema
# must keep declaring what the code consumes. It reads the LIVE schema.json (loaded into SCHEMA), so
# reverting the file to a pre-`phase` HEAD fails HERE, which is what makes the schema edit durable.
#
# SCOPE HONESTY: this gates the DECLARATION, not the rows. It proves schema.json still names the
# kinds/fields the validators depend on; it does not prove any row uses them. That is coverage, not
# correctness — the same coarse-and-forward stance as the other gates.
SCHEMA_DEPENDENCIES = {
    # enum.kind must contain every kind a validator dispatches on
    "kinds": ["assumptions", "fanout", "rca", "durability"],
    # kinds.<name>.required must contain every field a validator reads off that row
    "required": {
        "assumptions": ["phase", "assumptions"],
        "fanout": ["work_units", "independence"],
        "ratverdict": ["phase"],
        # check_rca reads these off an rca row; dropping any from the schema un-gates it
        "rca": ["verdictId", "failing_detector", "failing_span_ref", "root_cause", "target", "fix_hypothesis", "gate"],
        # check_durability_gate reads these off a durability row; dropping any un-gates the phase-close proof
        "durability": ["verdictId", "reverted", "control_flipped"],
    },
}


def check_schema_kinds(rows=None, schema=None):
    """The schema must keep declaring the kinds and required fields the validators consume.
    `rows` is unused (kept for the check_* signature); pass `schema` to exercise a specific schema
    object, else the live schema.json (SCHEMA) is checked. Reverting schema.json so it drops
    `fanout` from enum.kind or `phase` from the assumptions required list makes this fire."""
    s = SCHEMA if schema is None else schema
    problems = []
    enum_kinds = (s.get("enum") or {}).get("kind") or []
    for k in SCHEMA_DEPENDENCIES["kinds"]:
        if k not in enum_kinds:
            problems.append(
                f"schema enum.kind is missing {k!r}: a validator dispatches on it, so dropping it "
                f"silently un-gates {k} rows (check_schema would stop rejecting an unknown kind)"
            )
    kinds = s.get("kinds") or {}
    for kind, fields in SCHEMA_DEPENDENCIES["required"].items():
        req = (kinds.get(kind) or {}).get("required") or []
        for f in fields:
            if f not in req:
                problems.append(
                    f"schema kinds.{kind}.required is missing {f!r}: a validator reads this field, "
                    f"so check_schema must require it or the {kind} gate is toothless"
                )
    return problems


# ── C1: a verdict must name an IntentCard that exists ─────────────────────────
def check_verdict_cites_intent(rows):
    intents = {r["id"] for r in rows if r.get("kind") == "intent"}
    problems = []
    for r in rows:
        if r.get("kind") != "verdict":
            continue
        cited = r.get("intentCardId")
        if not cited:
            problems.append(f"verdict {r.get('id')}: no intentCardId. The Auditor cannot prove it read one")
        elif cited not in intents:
            problems.append(f"verdict {r.get('id')}: cites intentCardId {cited!r} which does not exist")
    return problems


# ── C1b: a verdict must cite the CF detectors it consulted from the failures-log SSOT ──
# The Auditor is DESIGNED to read failures/failures.jsonl, predict which CF modes this task is
# prone to (its AnticipatedFailures primer), and emit a per-detector Verdict =
# {detector_id, result, signal_seen}[] where each detector_id names a CF from the SSOT. Nothing
# PROVED it did: the pre-convention verdicts (v-30e3d80e .. v-c73addfb) carry free-text
# detector_ids ("gate-runs-clean", "intent_gate.py execution") that reference no CF at all, so a
# verdict could be emitted having never opened the SSOT. This gate makes the consultation
# checkable: a verdict must cite >= 1 CF id, and EVERY CF id it cites must EXIST in
# failures.jsonl (cross-referenced live). That deterministically forbids the two failure shapes:
# a verdict that consulted nothing (no CF cited) and a phantom citation (a CF id that isn't real).
#
# SCOPE HONESTY (a green tick must not imply more than it means): this enforces only the
# deterministically-provable part — non-empty detectors, >= 1 real CF cited, no phantom ids. It
# does NOT judge whether the cited CFs are the RELEVANT ones for this task; picking the right
# anticipated failures is the Auditor's judgment, not a mechanizable property. Like C1 and HR-7
# this closes the accident (a verdict that never touched the SSOT), not the lie (citing a real
# but irrelevant CF). It is detection, not root-cause, and house-rule 1 ranks it accordingly.
#
# FORWARD-GATE: verdicts written before this convention existed are not retro-failed. This mirrors
# check_rule6_reversibility's ts-cutoff mechanism exactly. The cutoff sits at the next day-boundary
# after the last pre-convention verdict (v-c73addfb, 2026-07-20T00:53Z) — the same date-boundary
# style as PHASE_FROM — so every existing verdict, and the concurrent doctrine run's 2026-07-20
# verdicts, are grandfathered and the suite stays green. "Gates apply forward" as code, not a note.
DETECTORS_FROM = "2026-07-21T00:00:00Z"


def _known_cf_ids():
    """The CF ids that actually exist in the failures-log SSOT. Loaded live so a citation is
    cross-referenced against the real file rather than a hardcoded list. Resolved from this
    file's location, so it is robust to the caller's cwd. A missing file yields an empty set,
    which fails closed: every citation then reads as phantom."""
    ids = set()
    failures = HERE.parent / "failures" / "failures.jsonl"
    if failures.exists():
        for line in failures.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                cid = json.loads(line).get("id")
            except json.JSONDecodeError:
                continue
            if cid:
                ids.add(cid)
    return ids


def _cited_cf_ids(detectors):
    """The CF ids a verdict cites: every CF-### token appearing in a detector's detector_id."""
    ids = []
    for d in detectors or []:
        ids += re.findall(r"CF-\d{3,}", str(d.get("detector_id", "")))
    return ids


def check_verdict_cites_detectors(rows):
    known = _known_cf_ids()
    problems = []
    for v in [r for r in rows if r.get("kind") == "verdict" and r.get("ts", "") >= DETECTORS_FROM]:
        dets = v.get("detectors")
        if _blank(dets):
            problems.append(
                f"verdict {v.get('id')}: empty detectors. The Auditor cannot prove it consulted "
                f"the failures-log SSOT (C1b)"
            )
            continue
        cited = _cited_cf_ids(dets)
        if not cited:
            problems.append(
                f"verdict {v.get('id')}: detectors cite no CF id from the failures log. A verdict "
                f"must name the CF detector(s) it evaluated, proving it read the SSOT (C1b)"
            )
            continue
        phantom = sorted({c for c in cited if c not in known})
        if phantom:
            problems.append(
                f"verdict {v.get('id')}: cites CF id(s) {phantom} absent from failures/failures.jsonl. "
                f"A phantom citation is a claim to have consulted a detector that does not exist (C1b)"
            )
    return problems


# ── C2: no orphan drift ───────────────────────────────────────────────────────
def check_no_orphan_drift(rows):
    # Simba proposes, the Auditor disposes. A flag with no verdict means the proposal was
    # made and nobody ruled on it, which is how the ConflictFlag in this session was lost.
    ruled = {d for r in rows if r.get("kind") == "verdict" for d in (r.get("resolves") or [])}
    problems = []
    for r in rows:
        if r.get("kind") != "drift":
            continue
        if r.get("determination") == "no-drift":
            continue
        if r["id"] not in ruled:
            problems.append(f"drift {r['id']} ({r.get('determination')}): no verdict resolves it")
    return problems


# ── C3: a failed probe blocks every later run unless overridden ───────────────
def check_probe_gate(rows, runs):
    failed = [r for r in rows if r.get("kind") == "probe" and r.get("result") == "FAIL"]
    if not failed:
        return []
    overrides = [r for r in rows if r.get("kind") == "override"]
    problems = []
    for p in failed:
        after = [r for r in runs if r.get("ts", "") > p["ts"]]
        covered = any(o.get("overrides") == p["id"] for o in overrides)
        if after and not covered:
            problems.append(
                f"probe {p['id']} FAILED at {p['ts'][:16]} and {len(after)} run(s) followed "
                f"with no override row. Phase 0 is a hard gate (house-rule 0)"
            )
    return problems


# ── ESCAPE: a close must not carry an un-overridden failing detector ───────────
# check_probe_gate's twin, lifted from probes to detectors. A close cites the authoritative verdict
# (close.verdictId). If THAT verdict still has a result:"fail" detector that was neither overridden
# (an explicit logged decision to proceed past it — the SAME override row, now pointing at a verdict
# + detector_id instead of a probe) nor re-audited green (in which case the latest verdict would show
# it passing), then the session shipped a false-PASS: an ESCAPE. This makes "escapes" computable, and
# because close-session refuses to emit such a close going forward, it makes them impossible at the
# door. Forward-only: closes before DISPOSITION_FROM predate the gate (c0-audit's approved fails were
# ruled non-blocking in prose before the override row existed to record it).
DISPOSITION_FROM = "2026-07-21T00:00:00Z"


def check_detector_gate(rows):
    verdict_by_id = {r["id"]: r for r in rows if r.get("kind") == "verdict" and "id" in r}
    overrides = [r for r in rows if r.get("kind") == "override"]
    problems = []
    for c in rows:
        if c.get("kind") != "close" or c.get("ts", "") < DISPOSITION_FROM:
            continue
        v = verdict_by_id.get(c.get("verdictId"))
        if not v:
            continue
        for d in (v.get("detectors") or []):
            if str(d.get("result", "")).lower() != "fail":
                continue
            did = d.get("detector_id")
            covered = any(o.get("overrides") == v["id"] and o.get("detector_id") == did for o in overrides)
            if not covered:
                problems.append(
                    f"close {c['id']} on verdict {v['id']}: detector {did!r} FAILED and the session "
                    f"closed with no override row — a false-PASS escape. Log an override naming who "
                    f"accepted it and why, or re-audit it green"
                )
    return problems


# ── fan-out independence: parallel work units must be PROVEN independent ───────
# The orchestrator can launch parallel Do-ers, but nothing checked that their independence
# was DISCHARGED (proven) rather than ASSERTED (assumed) before fan-out. This session's gap:
# two work units were launched in parallel on the assumption they were independent, and that
# assumption was never discharged into a record. Restated as a property of a `fanout` artifact
# it becomes checkable. A fan-out of >= 2 units is safe only if independence.status ==
# "discharged" AND the paths each unit touches are pairwise DISJOINT — two units editing the
# same prefix are not independent, whatever the status field claims. A fan-out of < 2 units is
# not a fan-out and passes. Like the C1-C3 gates this is coarse and forward: it gates the
# artifact, not whether the paths listed are the real ones (a unit can under-declare what it
# touches), which is detection, not root-cause.
def _paths_overlap(a, b):
    """True if two path prefixes touch the same tree: equal, or one contains the other."""
    a, b = str(a).strip().strip("/"), str(b).strip().strip("/")
    if not a or not b:
        return False
    return a == b or a.startswith(b + "/") or b.startswith(a + "/")


def check_fanout_independence(rows):
    problems = []
    for r in [r for r in rows if r.get("kind") == "fanout"]:
        units = r.get("work_units") or []
        if len(units) < 2:
            continue  # a single work unit is not a fan-out; nothing to prove independent
        indep = r.get("independence") or {}
        if indep.get("status") != "discharged":
            problems.append(
                f"fanout {r.get('id')}: independence asserted-not-discharged "
                f"(status {indep.get('status')!r}). A parallel launch of {len(units)} work units "
                f"needs independence DISCHARGED before fan-out, not assumed (house-rule 0)"
            )
            continue
        overlaps = []
        for a in range(len(units)):
            for b in range(a + 1, len(units)):
                for x in units[a].get("paths") or []:
                    for y in units[b].get("paths") or []:
                        if _paths_overlap(x, y):
                            pair = sorted({str(x), str(y)})
                            if pair not in overlaps:
                                overlaps.append(pair)
        if overlaps:
            problems.append(
                f"fanout {r.get('id')}: claimed discharged but paths overlap: {overlaps}. "
                f"Work units sharing a prefix are not independent"
            )
    return problems


# ── deferred high-kill assumption gate: an unresolved risky assumption cannot be ──
#    carried silently into the NEXT phase ────────────────────────────────────────
# CF-068's shape: work proceeded on a deferred, unprobed assumption ('the proxy equals the
# source') that later proved false, so the whole build could have rewarded invented content.
# Phase 0 probes exactly ONE riskiest assumption — the cheapest falsifying experiment targets
# it; every other assumption is deferred. A deferred assumption is only safe if it is LOW-kill,
# or it was explicitly resolved: probed later, or accepted through a logged override. A deferred
# HIGH-kill assumption (kill_power >= K) carried into the next phase with no resolution is the
# accident this gate stops. It is COARSE and FORWARD, like C1-C3 and the fan-out gate: it gates
# at PHASE granularity (the deferred high-kill assumption blocks the NEXT phase from starting),
# not per-work-item — that finer 'blocks:[] edge' version was rejected. And it gates the ARTIFACT:
# whether the row honestly reported kill_power, not whether the number is truly right, is
# detection, not root-cause. status resolves the assumption: 'probed' == it WAS the phase's probed
# riskiest; 'overridden' == deferred but explicitly accepted; anything else == deferred-unresolved.
KILL_THRESHOLD = 4  # kill_power >= K counts as "high-kill". Default K=4.


def _kill_power(entry):
    try:
        return int(entry.get("kill_power"))
    except (TypeError, ValueError):
        return None


def check_deferred_assumption_gate(rows):
    problems = []
    for a in [r for r in rows if r.get("kind") == "assumptions"]:
        phase = a.get("phase")
        run = a.get("runId")
        ts = a.get("ts", "")
        # Did a LATER phase start in this run? A prong row in a DIFFERENT, non-blank phase,
        # timestamped after these assumptions were written, is the next phase beginning.
        next_phase = [
            r for r in rows
            if r.get("runId") == run and r.get("ts", "") > ts
            and not _blank(r.get("phase")) and r.get("phase") != phase
        ]
        if not next_phase:
            continue  # still in the same phase; nothing has been carried forward yet
        nxt = min(next_phase, key=lambda r: r.get("ts", ""))
        for entry in a.get("assumptions") or []:
            kp = _kill_power(entry)
            if kp is None or kp < KILL_THRESHOLD:
                continue  # unranked or low-kill: a deferred low-kill assumption is safe
            status = str(entry.get("status", "")).strip().lower()
            if status in ("probed", "overridden"):
                continue  # resolved: the probed riskiest, or explicitly overridden
            problems.append(
                f"assumptions {a.get('id')} (phase {phase!r}): high-kill assumption "
                f"{entry.get('claim')!r} (kill_power {kp}) is deferred and unresolved "
                f"(status {status or 'none'!r}: not the probed riskiest, no override), yet phase "
                f"{nxt.get('phase')!r} started at {nxt.get('ts','')[:16]}. A deferred high-kill "
                f"assumption blocks the next phase from starting (CF-068, house-rule 0)"
            )
    return problems


# ── house-rules 6, 7, 10, 12 as FIELD checks ──────────────────────────────────
# These four were stated in house-rules.md and enforced by nothing. They describe what a
# model must DO during a turn, which no scanner can observe. Restated as properties of the
# Verdict artifact they become checkable, because a field either carries evidence or it does
# not.
#
# THE HONEST CAVEAT, stated here so a green tick cannot imply more than it means: a field
# check is strictly WEAKER than the rule it stands in for. Rule 7 says "never claim a record
# exists without reading it"; what runs below is "every detector quotes a non-empty signal".
# A model can quote a fabricated signal. This closes the accident, not the lie. Same for the
# other three. They are detection, not root-cause, and house-rule 1 ranks them accordingly.
#
# Rule 6 is scoped FORWARD: verdicts written before the field existed are not retro-failed.
# That is "gates apply forward" as code rather than as a note in a memory file, which is
# where it was first, wrongly, recorded.
RULE6_FROM = "2026-07-19T13:00:00Z"


def check_rule7_signal(rows):
    """HR-7 read before assert: a detector with no observed signal asserted its result."""
    problems = []
    for v in [r for r in rows if r.get("kind") == "verdict"]:
        for d in v.get("detectors") or []:
            if _blank(d.get("signal_seen")):
                problems.append(
                    f"verdict {v['id']} detector {d.get('detector_id')!r}: empty signal_seen. "
                    f"A result with nothing observed behind it is an assertion (house-rule 7)"
                )
    return problems


def check_rule10_unleaked(rows):
    """HR-10 keep the loops unleaked: prongs exchange typed artifacts, never raw reasoning."""
    # Markers that only appear when a prong pasted another prong's scratch into its output.
    leaks = ("<thinking", "chain-of-thought", "my scratchpad", "internal notes:", "raw reasoning")
    problems = []
    for v in [r for r in rows if r.get("kind") == "verdict"]:
        blob = json.dumps(v).lower()
        for m in leaks:
            if m in blob:
                problems.append(f"verdict {v['id']}: contains {m!r}, a leaked-reasoning marker (house-rule 10)")
    return problems


def check_rule12_not_self_graded(rows):
    """HR-12 no self-graded evals: grader != subject. Fail closed when either is unstated."""
    problems = []
    for v in [r for r in rows if r.get("kind") == "verdict"]:
        g, s = v.get("grader_model"), v.get("subject_model")
        if _blank(g) or _blank(s):
            problems.append(
                f"verdict {v['id']}: grader_model/subject_model not both recorded, so "
                f"self-grading cannot be ruled out. Fail closed (house-rule 12)"
            )
        elif str(g).strip().lower() == str(s).strip().lower():
            problems.append(f"verdict {v['id']}: grader_model == subject_model ({g}). Self-graded (house-rule 12)")
    return problems


def check_rule6_reversibility(rows):
    """HR-6 reversibility gate: irreversible actions need explicit approval, per verdict."""
    problems = []
    for v in [r for r in rows if r.get("kind") == "verdict" and r.get("ts", "") >= RULE6_FROM]:
        if "irreversible" not in v:
            problems.append(
                f"verdict {v['id']}: no 'irreversible' field. An empty list is a claim that "
                f"none were taken; a missing field is silence (house-rule 6)"
            )
            continue
        for a in v.get("irreversible") or []:
            if _blank(a.get("approved_by")):
                problems.append(f"verdict {v['id']}: irreversible action {a.get('action')!r} has no approved_by (house-rule 6)")
    return problems


# ── house-rule 0: the RAT opens every phase BEFORE anything is built ──────────
# rat.mjs writes a RATVerdict at the start of a phase. This enforces two things:
#   (a) the RAT is real: riskiest_assumption and cheapest_probe are present and not placeholders
#   (b) nothing is built before its RAT: every probe row (a run/falsify event) must have a
#       RATVerdict in the same run TIMESTAMPED BEFORE it. A probe with no preceding RAT means
#       the phase was built before the riskiest assumption was tested, which is the failure
#       house-rule 0 exists to prevent.
# It gates the artifact and its ordering, not whether the assumption was genuinely the riskiest.
RAT_FROM = "2026-07-19T13:00:00Z"    # rat.mjs shipped; probes before this predate it (forward-only)
PHASE_FROM = "2026-07-20T00:00:00Z"  # RAT-per-phase shipped end of 2026-07-19; work before this
#                                      predates the per-phase gate and is exempt (gates apply forward,
#                                      never backfilled: the durable-push close verdict v-6f0c111c is
#                                      from before this rule and is not retro-tagged with a fake RAT).


def check_rat(rows):
    problems = []
    rats = [r for r in rows if r.get("kind") == "ratverdict"]
    for r in rats:
        for field in ("riskiest_assumption", "cheapest_probe"):
            v = r.get(field, "")
            if _blank(v) or len(str(v).strip()) < 12:
                problems.append(f"ratverdict {r.get('id')}: {field} is empty or a placeholder (house-rule 0)")
        if r.get("push_decision") not in ("proceed", "hold"):
            problems.append(f"ratverdict {r.get('id')}: push_decision must be proceed|hold (house-rule 0)")
    # nothing built before its RAT: a probe in the RAT_FROM..PHASE_FROM window needs SOME RAT
    # before it (the original Phase-0 rule). Forward-only: probes predating rat.mjs are exempt.
    for p in [r for r in rows if r.get("kind") == "probe" and RAT_FROM <= r.get("ts", "") < PHASE_FROM]:
        prior = [r for r in rats if r.get("runId") == p.get("runId") and r.get("ts", "") <= p.get("ts", "")]
        if not prior:
            problems.append(
                f"probe {p.get('id')} at {p.get('ts','')[:16]} has no RATVerdict before it in run "
                f"{p.get('runId')}: something was built/probed before its RAT (house-rule 0)"
            )

    # RAT PER PHASE (not just Phase 0). From PHASE_FROM on, every work artifact (probe = Phase 0,
    # verdict = audit/correct phases) must NAME its phase and be opened by a RATVerdict for that
    # same phase, before it. A single Phase-0 RAT no longer covers the whole run: each phase is
    # opened by its own RAT or its work is rejected. The build phase leaves no row, so it is
    # gated through the verdict that audits it (which carries the phase and needs its RAT).
    for w in [r for r in rows if r.get("kind") in ("probe", "verdict") and r.get("ts", "") >= PHASE_FROM]:
        ph = w.get("phase")
        if _blank(ph):
            problems.append(
                f"{w.get('kind')} {w.get('id')} has no phase label. Every phase's work must name its "
                f"phase so the RAT-per-phase gate can check it (house-rule 0)"
            )
            continue
        opened = [r for r in rats if r.get("runId") == w.get("runId")
                  and r.get("phase") == ph and r.get("ts", "") <= w.get("ts", "")]
        if not opened:
            problems.append(
                f"{w.get('kind')} {w.get('id')} is in phase '{ph}' with no RATVerdict opening that "
                f"phase in run {w.get('runId')}: a RAT opens EVERY phase, not just Phase 0 (house-rule 0)"
            )
    return problems


# ── RCA-on-fail: a diagnosis is a fail-closed PROPOSAL grounded in a real failing verdict ──
# Change 3 / TraceRoot's root-cause pillar, bent to house-rule 1. When a Verdict fails, the Auditor
# may emit an `rca` row that localizes the failing span and proposes a targeted fix. It is DETECTION,
# not root-cause (an LLM's analysis, not a made-impossible guard), so it is fail-closed: it can never
# itself pass or apply work. This gate makes that checkable:
#   (a) EVIDENCE — verdictId names a real verdict that actually carries a failing detector. An RCA
#       diagnoses a FAIL; diagnosing a pass (or a phantom verdict) is the accident this forbids.
#   (b) LOCALIZED — failing_detector and failing_span_ref are named (the exact failing span is the
#       whole point; without it the RCA is just a re-dispatch with extra words).
#   (c) REAL DIAGNOSIS — root_cause and fix_hypothesis are present and non-placeholder.
#   (d) TARGETED — target is 'output' (primer to the Do-er) or 'harness' (a CF/PD proposal).
#   (e) FAIL-CLOSED — gate is exactly 'proposal'. Any other value (applied/auto/merge) is rejected:
#       an RCA never auto-applies; a human/the Auditor promotes it through the log-failure gate.
# SCOPE HONESTY: this gates the ARTIFACT, not whether the named cause is the TRUE cause — that is the
# promotion judgment, not a mechanizable property. Detection, not root-cause; house-rule 1 ranks it so.
RCA_TARGETS = ("output", "harness")


def check_rca(rows):
    verdicts = {r.get("id"): r for r in rows if r.get("kind") == "verdict"}
    problems = []
    for r in [r for r in rows if r.get("kind") == "rca"]:
        rid = r.get("id")
        vid = r.get("verdictId")
        v = verdicts.get(vid)
        if not vid or v is None:
            problems.append(
                f"rca {rid}: verdictId {vid!r} names no verdict in the ledger. An RCA must be "
                f"grounded in a real failing verdict, not invented (evidence gate)"
            )
        else:
            failed = [d for d in (v.get("detectors") or []) if str(d.get("result", "")).strip().lower() == "fail"]
            if not failed:
                problems.append(
                    f"rca {rid}: verdict {vid} carries no failing detector. An RCA diagnoses a FAIL, "
                    f"never a pass — diagnosing a clean verdict is the accident this gate forbids"
                )
        for field in ("failing_detector", "failing_span_ref", "root_cause", "fix_hypothesis"):
            if _blank(r.get(field)):
                problems.append(f"rca {rid}: {field} is empty. An RCA must localize and propose (not just assert a fail)")
        for field in ("root_cause", "fix_hypothesis"):
            val = r.get(field)
            if not _blank(val) and len(str(val).strip()) < 12:
                problems.append(f"rca {rid}: {field} is a placeholder ({val!r}), too short to be a real diagnosis")
        if r.get("target") not in RCA_TARGETS:
            problems.append(f"rca {rid}: target {r.get('target')!r} must be one of {list(RCA_TARGETS)} (output=primer, harness=CF/PD proposal)")
        if r.get("gate") != "proposal":
            problems.append(
                f"rca {rid}: gate {r.get('gate')!r} must be 'proposal'. An RCA is fail-closed — it is "
                f"DETECTION, not root-cause, and can never auto-apply a fix (house-rule 1)"
            )
    return problems


# ── PD-009: a silent tool-failure — an error span nobody acknowledged or retried ──
# spans.mjs derives one span per EXECUTED tool call and tags a failed call role="error". The
# a-priori mode (detectors-seed.md PD-009): the Do-er hit a real tool error and neither surfaced
# it in the Output nor retried the tool — the failure was swallowed and the turn shipped as if
# clean. Restated as a property of the extracted Spans it is deterministic: an error span is safe
# only if it was ACKNOWLEDGED in the Output (the failure/tool is named) OR RETRIED (a LATER role=="ok"
# span for the SAME tool). Anything else is a silent tool-error. Coarse-and-forward like the other
# gates: it gates the trace, not whether the acknowledgment was adequate — detection, not root-cause.
_ACK_TOKENS = ("error", "fail", "retr", "could not", "couldn't", "couldnt", "unable",
               "exception", "non-zero", "nonzero", "did not succeed", "errored")


def _span_tool(span):
    """The tool name of a span, from its '<tool>#<idx>' name field (idx makes repeats distinct)."""
    return str(span.get("span", "")).split("#", 1)[0].strip()


def check_no_silent_tool_error(spans, output_text=""):
    """PD-009. FAIL for any role=='error' span that is neither acknowledged in output_text (the
    failure/tool is named) nor retried (a later role=='ok' span for the same tool)."""
    spans = spans or []
    text = (output_text or "").lower()
    problems = []
    for i, s in enumerate(spans):
        if s.get("role") != "error":
            continue
        tool = _span_tool(s)
        retried = any(later.get("role") == "ok" and _span_tool(later) == tool
                      for later in spans[i + 1:])
        if retried:
            continue
        err = str(s.get("error", "")).strip()
        acknowledged = False
        if tool and tool.lower() in text and any(tok in text for tok in _ACK_TOKENS):
            acknowledged = True
        if err and len(err) >= 8 and err[:40].lower() in text:
            acknowledged = True
        if not acknowledged:
            problems.append(
                f"span {s.get('span')!r} is role='error' ({err[:60] or 'no error text'}) but the "
                f"Output neither acknowledges the failure nor retries the tool — a silent tool-error "
                f"(PD-009). Surface it or retry it; a swallowed tool failure ships as if clean"
            )
    return problems


# ── PD-008: a claim/verdict with no tool-call evidence in the same turn ───────────
# The a-priori hallucination proxy (detectors-seed.md PD-008, reusing CF-004/CF-046): a factual or
# result claim with no supporting tool-call in the same turn is narrated, not verified. spans.mjs
# makes the deterministic floor of that checkable: role=="root" is the Do-er run itself, every other
# span is an EXECUTED tool call. A span set carrying ONLY the root (or nothing) is a turn that
# reached a verdict having called no tool — zero evidence. This is the coarse deterministic floor
# under PD-008's llm-judge residue: it cannot judge whether a specific claim is supported, only that
# SOME tool-call evidence exists at all. Detection, not root-cause; house-rule 1 ranks it so.
# RESULT-asserting artifacts must show a tool-call span; reasoning/plan artifacts are EXEMPT.
# A probe result or an Auditor detector-verdict claims "I ran something -> here is the result",
# so it must carry evidence. An intent/assumptions/ratverdict/drift/override/close reasons over
# injected context and legitimately has spans=root-only; gating those would false-positive every
# Simba IntentCard and Auditor RATVerdict (the soundness bug this fix closes).
CLAIM_RESULT_KINDS = {"probe", "verdict"}

def check_claim_has_span(spans, kind="verdict"):
    """PD-008 (SCOPED). FAIL only when a RESULT-asserting artifact (a probe result, an Auditor
    detector-verdict) has ZERO executed tool-call spans: it ran nothing yet claims a result, so it
    is narrated, not verified. Reasoning/plan kinds are EXEMPT (they claim no tool-derived result)."""
    if kind not in CLAIM_RESULT_KINDS:
        return []  # reasoning/plan artifact — no tool-derived result claimed
    tool_spans = [s for s in (spans or []) if s.get("role") != "root"]
    if not tool_spans:
        return [
            f"a {kind} asserts a result but its span set has zero executed tool-call spans (only the "
            "root run, or none): a result claim with no tool-call evidence is narrated, not verified "
            "(PD-008, reuses CF-004/CF-046). The Auditor must RUN the detectors, not narrate them"
        ]
    return []


PRIOR_ART_FROM = "2026-07-21T00:00:00Z"
def check_prior_art(rows):
    """PD-015 prior-art gate. A ratverdict OPENS a build (house-rule 0). A build dated >= cutoff must
    record `prior_art.reuse` — the in-repo reuse-scan result — so a phase cannot open without first
    asking 'does this capability already exist here?' (the buy-vs-build finding, generalized to
    reuse-first). Forward-only: existing ratverdicts are grandfathered, never retro-failed."""
    out = []
    for r in [x for x in rows if x.get("kind") == "ratverdict" and x.get("ts", "") >= PRIOR_ART_FROM]:
        pa = r.get("prior_art") or {}
        if not str(pa.get("reuse") or "").strip():
            out.append(f"ratverdict {r.get('id')}: no prior_art.reuse. A build must record the in-repo "
                       "reuse scan (does this already exist?) before the phase opens (prior-art gate, PD-015)")
    return out


_DESIGN_KINDS = {"ratverdict", "intent", "assumptions"}
def check_design_prong_no_execution(spans, kind="ratverdict"):
    """PD-016 capability separation. A design/reasoning prong (ratverdict/intent/assumptions) must
    SPECIFY a probe, not RUN it — the orchestrator executes. Execution spans (Bash/shell) in its
    transcript mean the prong ran the probe itself: that is the 82k-forgery-in-a-prong leak, where a
    reasoning agent burned tokens doing work a 2k orchestrator bash call should own. Reuses spans.mjs
    output; scoped to design kinds so build prongs (verdict) that legitimately execute are exempt."""
    if kind not in _DESIGN_KINDS:
        return []
    execs = [s.get("span") for s in (spans or [])
             if str(s.get("span", "")).lower().startswith(("bash", "shell"))]
    if execs:
        return [f"a {kind} design prong has execution spans {execs}: it RAN a probe instead of "
                "specifying it. Design prongs are read-only; the orchestrator executes (PD-016)"]
    return []


DURABILITY_FROM = "2026-07-21T00:00:00Z"
def check_durability_gate(rows):
    """PD-017 phase-close bookend to HR-0 (which OPENS a phase). A phase that SHIPPED A GUARD — a
    verdict that `resolves` a CF, i.e. a real fix, which by Trident discipline becomes a check — must
    also carry a `durability` record proving the guard holds: revert the fix and a NAMED control
    flips red. Its absence is the fix-and-guard-revert-together leak (the census incident: the guard
    reverted with the fix and the baseline went silently green). Conditional by design: it fires ONLY
    on resolves-verdicts, so RAT/audit phases that shipped no fix are exempt (no-op ban). Pre-emptive
    guards (PDs) are covered by mutation (mutate.py); this gate covers FIX-driven guards, which
    mutation does not. Forward-only from the cutoff so existing resolved verdicts are grandfathered."""
    out = []
    durs = [r for r in rows if r.get("kind") == "durability"]
    for v in [r for r in rows if r.get("kind") == "verdict"
              and str(r.get("resolves") or "").strip() and r.get("ts", "") >= DURABILITY_FROM]:
        match = [d for d in durs if d.get("verdictId") == v.get("id")
                 and str(d.get("reverted") or "").strip() and str(d.get("control_flipped") or "").strip()]
        if not match:
            out.append(f"verdict {v.get('id')} resolves {v.get('resolves')!r} (ships a guard) but has no "
                       "durability proof: a fix that adds a guard must show the guard flips red when the "
                       "fix is reverted (prove-durable, PD-017 phase-close gate). No matching durability record")
    return out


RCA_ON_FAIL_FROM = "2026-07-21T00:00:00Z"
def check_rca_on_fail(rows):
    """PD-018 — the deterministic RCA-on-fail trigger. Every FAIL forces a diagnosis: a verdict's failing
    detector must be met by EITHER an `rca` grounded in that verdict (root cause + fix proposal) OR an
    `override` that explicitly accepts it. Neither = an UN-DIAGNOSED fail — which is exactly where a
    symptom-patch (fix this passage) silently stands in for a root-cause fix (fix the substrate). RCA was
    optional (check_rca only validates ones that exist); this makes it COMPULSORY on failure, so you
    diagnose the cause before you fix. Forward-only; overridden detectors are an accepted exception, not
    an un-diagnosed fail."""
    rcas = [r for r in rows if r.get("kind") == "rca"]
    overrides = [r for r in rows if r.get("kind") == "override"]
    out = []
    for v in rows:
        if v.get("kind") != "verdict" or v.get("ts", "") < RCA_ON_FAIL_FROM:
            continue
        failing = [d for d in (v.get("detectors") or []) if str(d.get("result", "")).strip().lower() == "fail"]
        if not failing:
            continue
        diagnosed = any(r.get("verdictId") == v.get("id") for r in rcas)
        all_accepted = all(
            any(o.get("overrides") == v.get("id") and o.get("detector_id") == d.get("detector_id")
                for o in overrides)
            for d in failing)
        if not diagnosed and not all_accepted:
            out.append(f"verdict {v.get('id')} has failing detector(s) "
                       f"{[d.get('detector_id') for d in failing]} with neither an rca (diagnosis) nor an "
                       "override (acceptance): a fail must trigger a root-cause RCA before any fix — "
                       "diagnose the cause, never patch the symptom (RCA-on-fail trigger, PD-018)")
    return out


# ── negative controls ─────────────────────────────────────────────────────────
def controls():
    out = []
    # check_schema has five distinct rejection branches. It shipped with ONE control, and that
    # one was compound (four fields missing at once), so it fired on the first branch and never
    # exercised the other four. The C0 audit (DriftFlag d-4d1dd0d6) found they worked only
    # because the Auditor hand-tested them, not because the suite did. One control per branch,
    # each isolating a single defect so a passing control names exactly which branch is alive.
    ok = {"id": "x1", "kind": "intent", "ts": "t", "runId": "r1",
          "intent_source": "asked", "scope": {"in_scope": ["a"], "out_of_scope": ["b"]}, "goal": "a real goal"}
    out.append(("C0 accepts a well-formed record (positive control)", not check_schema([ok])))

    out.append(("C0 rejects a record with no id",
                bool(check_schema([{k: v for k, v in ok.items() if k != "id"}]))))
    out.append(("C0 rejects an unknown kind",
                bool(check_schema([{**ok, "kind": "widget"}]))))
    out.append(("C0 rejects a duplicate id",
                bool(check_schema([ok, {**ok, "ts": "t2"}]))))
    out.append(("C0 rejects an invalid intent_source",
                bool(check_schema([{**ok, "intent_source": "guessed"}]))))
    out.append(("C0 rejects an invalid probe result",
                bool(check_schema([{"id": "p1", "kind": "probe", "ts": "t", "runId": "r1",
                                    "riskiest": "x", "result": "MAYBE"}]))))

    # The two the audit actually broke. These are regression controls for d-c5c84966.
    out.append(("C0 rejects a whitespace-only required string (audit d-c5c84966)",
                bool(check_schema([{**ok, "goal": "   "}]))))
    out.append(("C0 rejects an empty dict in a required field (audit d-c5c84966)",
                bool(check_schema([{**ok, "scope": {}}]))))

    # --- C0-DEP: the schema still declares the kinds/fields the validators consume ---
    # Each control injects a schema object so a rejection branch can be isolated without touching
    # the live schema.json. sk() returns a FRESH fully-conformant schema each call, so a negative
    # control can drop exactly one dependency. The 'phase' branch is the field this session added,
    # so it is the branch that fires when schema.json is reverted to HEAD.
    sk = lambda: {"enum": {"kind": ["assumptions", "fanout", "rca", "durability"]},
                  "kinds": {"assumptions": {"required": ["phase", "assumptions"]},
                            "fanout": {"required": ["work_units", "independence"]},
                            "ratverdict": {"required": ["phase"]},
                            "rca": {"required": ["verdictId", "failing_detector", "failing_span_ref",
                                                 "root_cause", "target", "fix_hypothesis", "gate"]},
                            "durability": {"required": ["verdictId", "reverted", "control_flipped"]}}}
    out.append(("C0-DEP accepts a schema declaring every consumed kind+field (positive control)",
                not check_schema_kinds(schema=sk())))
    _no_fanout = sk(); _no_fanout["enum"]["kind"].remove("fanout")
    out.append(("C0-DEP rejects a schema whose enum.kind drops 'fanout'",
                bool(check_schema_kinds(schema=_no_fanout))))
    _no_phase = sk(); _no_phase["kinds"]["assumptions"]["required"].remove("phase")
    out.append(("C0-DEP rejects a schema whose assumptions.required drops 'phase' (the durable field)",
                bool(check_schema_kinds(schema=_no_phase))))
    _no_indep = sk(); _no_indep["kinds"]["fanout"]["required"].remove("independence")
    out.append(("C0-DEP rejects a schema whose fanout.required drops 'independence'",
                bool(check_schema_kinds(schema=_no_indep))))
    _no_rca = sk(); _no_rca["enum"]["kind"].remove("rca")
    out.append(("C0-DEP rejects a schema whose enum.kind drops 'rca'",
                bool(check_schema_kinds(schema=_no_rca))))
    _no_span = sk(); _no_span["kinds"]["rca"]["required"].remove("failing_span_ref")
    out.append(("C0-DEP rejects a schema whose rca.required drops 'failing_span_ref' (the localizing field)",
                bool(check_schema_kinds(schema=_no_span))))

    no_cite = [{"id": "v1", "kind": "verdict", "ts": "t", "runId": "r", "detectors": []}]
    out.append(("C1 rejects a verdict with no intentCardId", bool(check_verdict_cites_intent(no_cite))))

    ghost = [{"id": "i1", "kind": "intent", "ts": "t", "runId": "r", "intent_source": "asked",
              "scope": {}, "goal": "g"},
             {"id": "v1", "kind": "verdict", "ts": "t", "runId": "r", "intentCardId": "NOPE",
              "detectors": []}]
    out.append(("C1 rejects a verdict citing a nonexistent IntentCard", bool(check_verdict_cites_intent(ghost))))

    # --- C1b: a verdict must cite the CF detectors it consulted from the failures-log SSOT ---
    # real_cf is derived from the live SSOT so the positive control cites an id that genuinely
    # exists; the negatives cite empty/free-text/phantom to prove each rejection branch fires.
    real_cf = next(iter(sorted(_known_cf_ids())), "CF-010")
    cd = lambda **kw: {"id": "vcd", "kind": "verdict", "ts": "2026-07-21T00:00:00Z", "runId": "r",
                       "intentCardId": "i1",
                       "detectors": [{"detector_id": real_cf, "result": "pass",
                                      "signal_seen": "observed: the cited CF detector was evaluated"}],
                       **kw}
    out.append(("C1b accepts a post-cutoff verdict citing a real CF id (positive control)",
                not check_verdict_cites_detectors([cd()])))
    out.append(("C1b rejects a post-cutoff verdict with empty detectors",
                bool(check_verdict_cites_detectors([cd(detectors=[])]))))
    out.append(("C1b rejects a post-cutoff verdict that cites NO CF id (free-text detector only)",
                bool(check_verdict_cites_detectors([cd(detectors=[{"detector_id": "gate-runs-clean",
                                                                   "result": "pass", "signal_seen": "x"}])]))))
    out.append(("C1b rejects a phantom CF citation (a CF id not in the SSOT)",
                bool(check_verdict_cites_detectors([cd(detectors=[{"detector_id": "CF-99999",
                                                                   "result": "pass", "signal_seen": "x"}])]))))
    out.append(("C1b does NOT retro-fail a verdict written before the CF-citation convention (forward-gate)",
                not check_verdict_cites_detectors([cd(ts="2026-07-20T00:00:00Z",
                                                      detectors=[{"detector_id": "gate-runs-clean",
                                                                  "result": "pass", "signal_seen": "x"}])])))

    orphan = [{"id": "d1", "kind": "drift", "ts": "t", "runId": "r",
               "determination": "DriftFlag", "drifted_from": "goal"}]
    out.append(("C2 rejects an unresolved drift flag", bool(check_no_orphan_drift(orphan))))

    probe = [{"id": "p1", "kind": "probe", "ts": "2026-01-01T00:00:00Z", "runId": "r",
              "riskiest": "x", "result": "FAIL"}]
    out.append(("C3 blocks a run after a failed probe", bool(check_probe_gate(probe, [{"ts": "2026-01-02T00:00:00Z"}]))))

    ok_override = probe + [{"id": "o1", "kind": "override", "ts": "2026-01-01T01:00:00Z",
                            "runId": "r", "overrides": "p1", "reason": "accepted the risk"}]
    out.append(("C3 allows it once an override is logged", not check_probe_gate(ok_override, [{"ts": "2026-01-02T00:00:00Z"}])))

    # --- ESCAPE: a close must not carry an un-overridden failing detector (detector-gate twin) ---
    esc_v = {"id": "ve", "kind": "verdict", "ts": "2026-07-21T00:00:00Z", "runId": "r", "intentCardId": "i",
             "detectors": [{"detector_id": "CF-046", "result": "fail", "signal_seen": "x"}]}
    esc_close = {"id": "ce", "kind": "close", "ts": "2026-07-21T01:00:00Z", "runId": "r", "verdictId": "ve"}
    out.append(("ESCAPE a post-cutoff close with an un-overridden failing detector fires",
                bool(check_detector_gate([esc_v, esc_close]))))
    esc_ovr = {"id": "oe", "kind": "override", "ts": "2026-07-21T00:30:00Z", "runId": "r",
               "overrides": "ve", "detector_id": "CF-046", "reason": "accepted, non-blocking"}
    out.append(("ESCAPE an override on the verdict+detector clears it",
                not check_detector_gate([esc_v, esc_close, esc_ovr])))
    pre_v = {"id": "vp", "kind": "verdict", "ts": "2026-07-19T00:00:00Z", "runId": "r", "intentCardId": "i",
             "detectors": [{"detector_id": "CF-046", "result": "fail", "signal_seen": "x"}]}
    pre_close = {"id": "cp", "kind": "close", "ts": "2026-07-19T00:00:00Z", "runId": "r", "verdictId": "vp"}
    out.append(("ESCAPE does NOT retro-fail a close that predates the gate (forward-only)",
                not check_detector_gate([pre_v, pre_close])))

    # --- fan-out independence: prove parallel work units are independent before launch ---
    fo = lambda **kw: {"id": "fo1", "kind": "fanout", "ts": "2026-07-20T00:00:00Z", "runId": "r",
                       "work_units": [{"name": "A", "paths": ["alpha/"]},
                                      {"name": "B", "paths": ["beta/"]}],
                       "independence": {"status": "discharged", "evidence": "disjoint trees; no shared state"},
                       **kw}
    out.append(("FAN-OUT accepts a discharged fan-out with disjoint paths (positive control)",
                not check_fanout_independence([fo()])))
    out.append(("FAN-OUT passes a single-unit fanout (< 2 units is not a fan-out)",
                not check_fanout_independence([fo(work_units=[{"name": "A", "paths": ["alpha/"]}])])))
    out.append(("FAN-OUT rejects independence asserted-not-discharged",
                bool(check_fanout_independence([fo(independence={"status": "asserted", "evidence": "assumed independent"})]))))
    out.append(("FAN-OUT rejects a discharged claim whose paths overlap",
                bool(check_fanout_independence([fo(work_units=[{"name": "A", "paths": ["shared/"]},
                                                               {"name": "B", "paths": ["shared/sub"]}])]))))

    # --- deferred high-kill assumption gate (CF-068): an unresolved risky assumption cannot
    #     be carried silently into the next phase ---
    da = lambda **kw: {"id": "asmX", "kind": "assumptions", "ts": "2026-07-20T00:00:00Z",
                       "runId": "rda", "phase": "explore",
                       "assumptions": [{"claim": "the proxy approximates the source",
                                        "kill_power": 5, "uncertainty": "high", "status": "deferred"}],
                       **kw}
    next_phase_row = {"id": "ratNext", "kind": "ratverdict", "ts": "2026-07-20T02:00:00Z",
                      "runId": "rda", "phase": "build", "riskiest_assumption": "x" * 15,
                      "cheapest_probe": "y" * 15, "gate": "hard", "push_decision": "proceed"}

    out.append(("GATE-ASM rejects a deferred high-kill assumption once the next phase starts",
                bool(check_deferred_assumption_gate([da(), next_phase_row]))))
    out.append(("GATE-ASM passes when that high-kill assumption WAS the probed riskiest (positive control)",
                not check_deferred_assumption_gate(
                    [da(assumptions=[{"claim": "c", "kill_power": 5, "status": "probed"}]), next_phase_row])))
    out.append(("GATE-ASM passes when the deferred assumption was explicitly overridden",
                not check_deferred_assumption_gate(
                    [da(assumptions=[{"claim": "c", "kill_power": 5, "status": "overridden"}]), next_phase_row])))
    out.append(("GATE-ASM passes a deferred LOW-kill assumption (below the threshold)",
                not check_deferred_assumption_gate(
                    [da(assumptions=[{"claim": "c", "kill_power": 1, "status": "deferred"}]), next_phase_row])))
    out.append(("GATE-ASM does not fire while still in the SAME phase (no next phase started)",
                not check_deferred_assumption_gate([da()])))

    # --- house-rules 6, 7, 10, 12 ---
    def v(**kw):
        base = {"id": "vX", "kind": "verdict", "ts": "2026-07-20T00:00:00Z", "runId": "r",
                "intentCardId": "i1", "detectors": [{"detector_id": "d", "result": "pass",
                "signal_seen": "observed: exit 2"}], "grader_model": "sonnet",
                "subject_model": "opus", "irreversible": []}
        base.update(kw)
        return [base]

    out.append(("HR-7 accepts a detector that quotes a signal (positive control)", not check_rule7_signal(v())))
    out.append(("HR-7 rejects a detector with an empty signal_seen",
                bool(check_rule7_signal(v(detectors=[{"detector_id": "d", "result": "pass", "signal_seen": "  "}])))))
    out.append(("HR-10 rejects a verdict carrying leaked reasoning",
                bool(check_rule10_unleaked(v(note="my scratchpad said the build was fine")))))
    out.append(("HR-12 accepts grader != subject (positive control)", not check_rule12_not_self_graded(v())))
    out.append(("HR-12 rejects grader == subject",
                bool(check_rule12_not_self_graded(v(grader_model="opus")))))
    out.append(("HR-12 fails closed when the models are unstated",
                bool(check_rule12_not_self_graded(v(grader_model=None)))))
    out.append(("HR-6 rejects a post-cutoff verdict with no irreversible field",
                bool(check_rule6_reversibility([{k: x for k, x in v()[0].items() if k != "irreversible"}]))))
    out.append(("HR-6 rejects an irreversible action with no approved_by",
                bool(check_rule6_reversibility(v(irreversible=[{"action": "force-push"}])))))
    out.append(("HR-6 does NOT retro-fail a verdict written before the field existed",
                not check_rule6_reversibility([{k: x for k, x in v(ts="2026-07-19T12:00:00Z")[0].items()
                                                if k != "irreversible"}])))

    # --- house-rule 0: RAT opens each phase ---
    def rat(**kw):
        base = {"id": "ratX", "kind": "ratverdict", "ts": "2026-07-20T00:00:00Z", "runId": "r",
                "phase": "build", "riskiest_assumption": "the ledger path is hardcoded so tests pollute it",
                "cheapest_probe": "grep the door scripts for an env override", "gate": "hard",
                "push_decision": "proceed"}
        base.update(kw)
        return base
    pr = lambda **kw: {"id": "pX", "kind": "probe", "ts": "2026-07-20T01:00:00Z", "runId": "r",
                       "phase": "build", "riskiest": "x", "result": "PASS", **kw}
    vr = lambda **kw: {"id": "vX", "kind": "verdict", "ts": "2026-07-20T03:00:00Z", "runId": "r",
                       "phase": "audit", **kw}

    out.append(("HR-0 accepts a well-formed RAT + a same-phase probe after it (positive control)",
                not check_rat([rat(), pr()])))
    out.append(("HR-0 rejects a RAT with a placeholder riskiest_assumption",
                bool(check_rat([rat(riskiest_assumption="TBD")]))))
    out.append(("HR-0 rejects a RAT with an empty cheapest_probe",
                bool(check_rat([rat(cheapest_probe="")]))))
    out.append(("HR-0 rejects a RAT with an invalid push_decision",
                bool(check_rat([rat(push_decision="maybe")]))))
    out.append(("HR-0 rejects a probe with NO RAT before it (built before the RAT)",
                bool(check_rat([pr()]))))
    out.append(("HR-0 rejects a probe whose only RAT comes AFTER it",
                bool(check_rat([rat(ts="2026-07-20T02:00:00Z"), pr()]))))
    out.append(("HR-0 does NOT retro-fail work that predates the gate (gates apply forward)",
                not check_rat([pr(ts="2026-07-19T10:00:00Z", phase=None)])))
    # RAT PER PHASE
    out.append(("HR-0 accepts an audit verdict opened by its own phase RAT",
                not check_rat([rat(phase="audit", ts="2026-07-20T02:00:00Z"), vr()])))
    out.append(("HR-0 rejects an audit verdict whose only RAT is for a DIFFERENT phase (build)",
                bool(check_rat([rat(phase="build"), vr()]))))
    out.append(("HR-0 rejects a forward work artifact with NO phase label",
                bool(check_rat([pr(phase=None)]))))

    # --- RCA-on-fail: a fail-closed proposal grounded in a real failing verdict ---
    # The positive control pairs a real failing verdict with a well-formed rca; each negative
    # breaks exactly one gate branch (no evidence / diagnosing a pass / not fail-closed / bad
    # target / placeholder), so gutting check_rca flips at least one.
    failing_v = {"id": "vF", "kind": "verdict", "ts": "2026-07-21T00:00:00Z", "runId": "r",
                 "intentCardId": "i1",
                 "detectors": [{"detector_id": "CF-046", "result": "fail",
                                "signal_seen": "narrated a write with no matching tool call",
                                "span_ref": "Bash#3"}]}
    rc = lambda **kw: {"id": "rcaX", "kind": "rca", "ts": "2026-07-21T00:00:00Z", "runId": "r",
                       "verdictId": "vF", "failing_detector": "CF-046", "failing_span_ref": "Bash#3",
                       "root_cause": "the write was narrated but the Bash#3 tool call was never issued",
                       "target": "output",
                       "fix_hypothesis": "re-dispatch the Do-er to actually issue the write at span Bash#3",
                       "gate": "proposal", **kw}
    out.append(("RCA accepts a well-formed proposal grounded in a real failing verdict (positive control)",
                not check_rca([failing_v, rc()])))
    out.append(("RCA rejects an rca whose verdictId names no verdict (no evidence)",
                bool(check_rca([rc(verdictId="v-nope")]))))
    out.append(("RCA rejects diagnosing a verdict with NO failing detector (an RCA is for a FAIL)",
                bool(check_rca([{**failing_v, "detectors": [{"detector_id": "CF-046", "result": "pass",
                                                             "signal_seen": "ok"}]}, rc()]))))
    out.append(("RCA rejects gate != 'proposal' (fail-closed: no auto-apply)",
                bool(check_rca([failing_v, rc(gate="applied")]))))
    out.append(("RCA rejects an invalid target",
                bool(check_rca([failing_v, rc(target="everything")]))))
    out.append(("RCA rejects a placeholder root_cause",
                bool(check_rca([failing_v, rc(root_cause="TBD")]))))
    out.append(("RCA rejects a missing failing_span_ref (the localizing field)",
                bool(check_rca([failing_v, rc(failing_span_ref="  ")]))))

    # --- PD-009: a silent (unacknowledged, unretried) tool-error span must be caught ---
    # Fixture spans in the spans.mjs shape: role root|error|ok, name '<tool>#<idx>'.
    _root = {"span": "root#0", "role": "root", "status": "OK"}
    _err = {"span": "Bash#2", "role": "error", "status": "ERROR",
            "error": "npm ERR! build failed with exit code 1"}
    out.append(("PD-009 fires on an unacknowledged, unretried error span (silent tool-failure)",
                bool(check_no_silent_tool_error([_root, _err], output_text="all good, shipping it"))))
    out.append(("PD-009 passes when the error is acknowledged in the Output (positive control)",
                not check_no_silent_tool_error(
                    [_root, _err],
                    output_text="the Bash step errored with a non-zero exit; reporting it, not proceeding")))
    out.append(("PD-009 passes when the tool was retried to a later ok span (positive control)",
                not check_no_silent_tool_error(
                    [_root, _err, {"span": "Bash#3", "role": "ok", "status": "OK"}])))

    # --- PD-008: a verdict/claim with no executed tool-call span is narrated, not verified ---
    _ok = {"span": "Read#1", "role": "ok", "status": "OK"}
    out.append(("PD-008 fires when a RESULT artifact (probe) has only the root run (no tool-call evidence)",
                bool(check_claim_has_span([_root], "probe"))))
    out.append(("PD-008 fires on an empty span set for a result artifact (no tool call at all)",
                bool(check_claim_has_span([], "verdict"))))
    out.append(("PD-008 passes when a result artifact has >=1 executed tool-call span (positive control)",
                not check_claim_has_span([_root, _ok], "verdict")))
    out.append(("PD-008 EXEMPTS a reasoning artifact (intent, root-only spans) — no false-positive on Simba/Auditor verdicts",
                not check_claim_has_span([_root], "intent")))

    # PD-015 prior-art gate
    _rat_old = {"kind": "ratverdict", "id": "rv-old", "ts": "2026-07-20T00:00:00Z"}
    _rat_ok = {"kind": "ratverdict", "id": "rv-ok", "ts": "2026-07-22T00:00:00Z",
               "prior_art": {"reuse": "grepped repo: no existing capability, building new"}}
    _rat_bad = {"kind": "ratverdict", "id": "rv-bad", "ts": "2026-07-22T00:00:00Z"}
    out.append(("PD-015 FIRES when a post-cutoff ratverdict records no prior_art.reuse (control fired)",
                bool(check_prior_art([_rat_bad]))))
    out.append(("PD-015 passes a ratverdict that records the in-repo reuse scan (positive control)",
                not check_prior_art([_rat_ok])))
    out.append(("PD-015 does NOT retro-fail a pre-cutoff ratverdict (forward-gate only)",
                not check_prior_art([_rat_old])))

    # PD-016 capability separation (design prong must not execute)
    _bash_span = {"span": "Bash#1", "role": "ok", "status": "OK"}
    out.append(("PD-016 FIRES when a design prong (ratverdict) has an execution (Bash) span (control fired)",
                bool(check_design_prong_no_execution([_root, _bash_span], "ratverdict"))))
    out.append(("PD-016 passes a design prong with only root/read spans (positive control)",
                not check_design_prong_no_execution([_root, _ok], "ratverdict")))
    out.append(("PD-016 EXEMPTS a build prong (verdict) that legitimately executes",
                not check_design_prong_no_execution([_root, _bash_span], "verdict")))

    # PD-017 phase-close durability gate
    _res_v = {"kind": "verdict", "id": "v-res", "ts": "2026-07-22T00:00:00Z", "resolves": "CF-999"}
    _dur_ok = {"kind": "durability", "id": "d-1", "ts": "2026-07-22T00:01:00Z", "verdictId": "v-res",
               "reverted": "undid the census --ledger fix", "control_flipped": "DURABLE-LEDGER"}
    _res_v_old = {"kind": "verdict", "id": "v-old", "ts": "2026-07-20T00:00:00Z", "resolves": "CF-000"}
    _plain_v = {"kind": "verdict", "id": "v-plain", "ts": "2026-07-22T00:00:00Z"}
    out.append(("PD-017 FIRES when a guard-shipping (resolves) verdict has no durability proof (control fired)",
                bool(check_durability_gate([_res_v]))))
    out.append(("PD-017 passes when the resolves-verdict has a matching durability record (positive control)",
                not check_durability_gate([_res_v, _dur_ok])))
    out.append(("PD-017 does NOT fire on a resolves-verdict before the cutoff (forward-gate only)",
                not check_durability_gate([_res_v_old])))
    out.append(("PD-017 EXEMPTS a verdict that resolves nothing — no fix, no durability owed (no-op ban)",
                not check_durability_gate([_plain_v])))

    # PD-018 RCA-on-fail trigger
    _v_fail = {"kind": "verdict", "id": "v-f", "ts": "2026-07-22T00:00:00Z",
               "detectors": [{"detector_id": "CF-001", "result": "fail"}]}
    _rca = {"kind": "rca", "id": "rca-f", "verdictId": "v-f"}
    _ovr = {"kind": "override", "id": "ov-f", "overrides": "v-f", "detector_id": "CF-001"}
    _v_pass = {"kind": "verdict", "id": "v-p", "ts": "2026-07-22T00:00:00Z",
               "detectors": [{"detector_id": "CF-001", "result": "pass"}]}
    _v_old = {"kind": "verdict", "id": "v-o", "ts": "2026-07-20T00:00:00Z",
              "detectors": [{"detector_id": "CF-001", "result": "fail"}]}
    out.append(("PD-018 FIRES on a failing verdict with no rca and no override (un-diagnosed fail)",
                bool(check_rca_on_fail([_v_fail]))))
    out.append(("PD-018 passes when the failing verdict is diagnosed by an rca (positive control)",
                not check_rca_on_fail([_v_fail, _rca])))
    out.append(("PD-018 passes when the failing detector is explicitly overridden (accepted, not un-diagnosed)",
                not check_rca_on_fail([_v_fail, _ovr])))
    out.append(("PD-018 EXEMPTS a clean verdict — no fail, no RCA owed",
                not check_rca_on_fail([_v_pass])))
    out.append(("PD-018 does NOT retro-fire on a pre-cutoff failing verdict (forward-gate)",
                not check_rca_on_fail([_v_old])))
    return out


def main():
    rows = read(LEDGER)
    runs_path = Path("design-runs.jsonl")
    runs = read(runs_path) if runs_path.exists() else []

    print("== Trident prong-exchange validator (C0-C3) ==")
    failed = 0

    for name, probs in [
        ("C0 schema + ids", check_schema(rows)),
        ("C0-DEP schema still declares the kinds/fields the validators consume", check_schema_kinds(rows)),
        ("C1 verdict cites a real IntentCard", check_verdict_cites_intent(rows)),
        ("C1b verdict cites real CF detectors from the failures-log SSOT", check_verdict_cites_detectors(rows)),
        ("C2 no orphan drift flags", check_no_orphan_drift(rows)),
        ("C3 failed probe blocks later runs", check_probe_gate(rows, runs)),
        ("ESCAPE closed verdict has no un-overridden failing detector", check_detector_gate(rows)),
        ("FAN-OUT independence discharged + paths disjoint before parallel launch", check_fanout_independence(rows)),
        ("GATE-ASM deferred high-kill assumption blocks the next phase (CF-068)", check_deferred_assumption_gate(rows)),
        ("HR-7 every detector quotes a signal", check_rule7_signal(rows)),
        ("HR-10 no leaked reasoning in a verdict", check_rule10_unleaked(rows)),
        ("HR-12 grader is not the subject", check_rule12_not_self_graded(rows)),
        ("HR-6 irreversible actions are approved", check_rule6_reversibility(rows)),
        ("HR-0 RAT opens each phase before any build", check_rat(rows)),
        ("PRIOR-ART build records the in-repo reuse scan before opening (PD-015)", check_prior_art(rows)),
        ("DURABILITY a guard-shipping phase proves the guard flips on revert (PD-017)", check_durability_gate(rows)),
        ("RCA on-fail diagnosis is a fail-closed proposal grounded in a real failing verdict", check_rca(rows)),
        ("RCA-ON-FAIL every failing verdict triggers a root-cause RCA or an explicit override — no symptom-patch (PD-018)", check_rca_on_fail(rows)),
    ]:
        if probs:
            failed += 1
            print(f"  FAIL {name}")
            for p in probs:
                print(f"       {p}")
        else:
            print(f"  ok   {name}")

    print("\n  negative controls (each must fire):")
    for name, fired in controls():
        print(f"    {'ok  ' if fired else 'FAIL'} {name}")
        if not fired:
            failed += 1

    print(f"\n  {len(rows)} prong record(s) in {LEDGER.name}")
    print(f"RESULT: {'PASS' if failed == 0 else 'FAIL'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
