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

    no_cite = [{"id": "v1", "kind": "verdict", "ts": "t", "runId": "r", "detectors": []}]
    out.append(("C1 rejects a verdict with no intentCardId", bool(check_verdict_cites_intent(no_cite))))

    ghost = [{"id": "i1", "kind": "intent", "ts": "t", "runId": "r", "intent_source": "asked",
              "scope": {}, "goal": "g"},
             {"id": "v1", "kind": "verdict", "ts": "t", "runId": "r", "intentCardId": "NOPE",
              "detectors": []}]
    out.append(("C1 rejects a verdict citing a nonexistent IntentCard", bool(check_verdict_cites_intent(ghost))))

    orphan = [{"id": "d1", "kind": "drift", "ts": "t", "runId": "r",
               "determination": "DriftFlag", "drifted_from": "goal"}]
    out.append(("C2 rejects an unresolved drift flag", bool(check_no_orphan_drift(orphan))))

    probe = [{"id": "p1", "kind": "probe", "ts": "2026-01-01T00:00:00Z", "runId": "r",
              "riskiest": "x", "result": "FAIL"}]
    out.append(("C3 blocks a run after a failed probe", bool(check_probe_gate(probe, [{"ts": "2026-01-02T00:00:00Z"}]))))

    ok_override = probe + [{"id": "o1", "kind": "override", "ts": "2026-01-01T01:00:00Z",
                            "runId": "r", "overrides": "p1", "reason": "accepted the risk"}]
    out.append(("C3 allows it once an override is logged", not check_probe_gate(ok_override, [{"ts": "2026-01-02T00:00:00Z"}])))

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
    return out


def main():
    rows = read(LEDGER)
    runs_path = Path("design-runs.jsonl")
    runs = read(runs_path) if runs_path.exists() else []

    print("== Trident prong-exchange validator (C0-C3) ==")
    failed = 0

    for name, probs in [
        ("C0 schema + ids", check_schema(rows)),
        ("C1 verdict cites a real IntentCard", check_verdict_cites_intent(rows)),
        ("C2 no orphan drift flags", check_no_orphan_drift(rows)),
        ("C3 failed probe blocks later runs", check_probe_gate(rows, runs)),
        ("HR-7 every detector quotes a signal", check_rule7_signal(rows)),
        ("HR-10 no leaked reasoning in a verdict", check_rule10_unleaked(rows)),
        ("HR-12 grader is not the subject", check_rule12_not_self_graded(rows)),
        ("HR-6 irreversible actions are approved", check_rule6_reversibility(rows)),
        ("HR-0 RAT opens each phase before any build", check_rat(rows)),
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
