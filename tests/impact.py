#!/usr/bin/env python3
"""impact — does Trident catch real defects in real runs, or only pass its own tests?

WHY THIS IS NOT census.py (which is not selftest.py)
----------------------------------------------------
selftest asks "do the gates work?" (fixtures). census asks "were the gates ever applied?"
(transport/enforcement gaps). Neither asks the outward question Trident exists for: across real
Do-er sessions, is the audit actually happening and is it holding? Trident has near-maxed its
internal scores while that outward number has a sample size of ~4 and is measured by nothing —
the exact Goodhart census was built to prevent, one level up.

This is a RATCHET, not a threshold. It prints a scoreboard next to census and, under --strict,
BLOCKS if any headline number regresses vs a committed baseline (impact-baseline.json). Raising
the baseline is an explicit, logged act (--set-baseline), never silent. Forward-only, applied to
every tracked number: outward metrics may not fall, census gaps may not rise.

SCOPE
Track A (audit_rate + census non-regression) is the always-on lead. Track B (escapes,
prevention_integrity) is now computable too: rather than a new per-detector `disposition` field, the
existing `override` row was generalized to accept a verdict + `detector_id` (the same primitive that
clears a failed probe now clears a failed detector). So an `escape` = a genuine close whose cited
verdict still carries an un-overridden failing detector — deterministic, and forward-only from
DISPOSITION_FROM so c0-audit's prose-approved fails are exempt rather than misclassified.
prevention_integrity stays None (not a vacuous 1.0) until a genuine run closes after the cutoff;
per PD-013 it becomes the lead once it populates.

  python3 tests/impact.py                 # scoreboard + RESULT (non-blocking on values)
  python3 tests/impact.py --strict        # exit 1 if any headline number regressed (CI / pre-commit)
  python3 tests/impact.py --set-baseline  # explicitly raise the ratchet to the current numbers
  python3 tests/impact.py --controls      # positive+negative control per metric (mutation discipline)
  python3 tests/impact.py --ledger PATH --baseline PATH   # isolated (tests)

The metric functions are small and named so gutting one flips a control (the census/mutate
discipline). Genuine-run filtering REUSES census.is_genuine_run (intent AND close), so fixture and
bootstrap rows never inflate impact — no duplicated definition.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import census  # reuse: is_genuine_run, read_jsonl, and the --ledger/CENSUS_LEDGER resolution


# ── where the ledger and baseline live (both overridable for isolated tests) ──────────────
def _flag(name, default):
    for i, a in enumerate(sys.argv):
        if a == name and i + 1 < len(sys.argv):
            return a and sys.argv[i + 1]
        if a.startswith(name + "="):
            return a.split("=", 1)[1]
    return default


# census resolves LEDGER from the SAME argv at import (so --ledger/CENSUS_LEDGER already applied).
LEDGER = census.LEDGER
BASELINE = Path(_flag("--baseline", str(HERE / "impact-baseline.json")))
CENSUS_PY = HERE / "census.py"

CF_ID = re.compile(r"CF-\d{3,}")
# Track B cutoff: escapes/localized/prevention_integrity are measured only over closes on/after this
# (mirrors validate_prongs.DISPOSITION_FROM). Pre-cutoff closes predate the override-disposition
# door, so c0-audit's prose-approved fails are exempt rather than counted as escapes (forward-only).
DISPOSITION_FROM = "2026-07-21T00:00:00Z"


# ── metrics (each deterministic, each computable from the current schema) ──────────────────
def genuine_runs(rows):
    """Run ids that opened with an intent AND closed through the door (census.is_genuine_run)."""
    ids = {r.get("runId") for r in rows if r.get("runId")}
    return sorted(rid for rid in ids if census.is_genuine_run(rid, rows))


def _verdicts_of(rows, runId):
    return [r for r in rows if r.get("kind") == "verdict" and r.get("runId") == runId]


def _fail_detectors(verdict):
    # verdict detectors store result lowercase ('pass'/'fail'); compare case-insensitively.
    return [d for d in (verdict.get("detectors") or []) if str(d.get("result", "")).lower() == "fail"]


def runs_audited(rows, genuine):
    """Genuine runs carrying at least one verdict — the audit actually ran on real work."""
    return [rid for rid in genuine if _verdicts_of(rows, rid)]


def self_heal(rows, genuine):
    """rca rows with target 'harness' on genuine runs — a fail routed back to harden the harness."""
    g = set(genuine)
    return [r for r in rows
            if r.get("kind") == "rca" and r.get("target") == "harness" and r.get("runId") in g]


def recurrences(rows, genuine):
    """A CF id that appears as a FAILING detector in >= 2 genuine runs = a prevention miss.
    Scoped to CF-shaped detector ids ONLY: free-text detector ids carry no CF identity and are
    out of scope by construction (reported, never silently folded in)."""
    g = set(genuine)
    seen = {}  # cf id -> set(runId)
    for v in rows:
        if v.get("kind") != "verdict" or v.get("runId") not in g:
            continue
        for d in _fail_detectors(v):
            for cf in CF_ID.findall(str(d.get("detector_id", ""))):
                seen.setdefault(cf, set()).add(v.get("runId"))
    return sorted(cf for cf, runset in seen.items() if len(runset) >= 2)


# ── Track B: escape / localization / prevention_integrity (needs the override-disposition field) ──
def _post_cutoff_closes(rows, genuine):
    g = set(genuine)
    return [c for c in rows if c.get("kind") == "close" and c.get("runId") in g
            and c.get("ts", "") >= DISPOSITION_FROM]


def _verdict(rows, vid):
    return next((v for v in rows if v.get("kind") == "verdict" and v.get("id") == vid), None)


def _uncovered_fails(rows, verdict):
    """Failing detectors in `verdict` that no override row accepts — the escape set for that verdict."""
    ovr = [o for o in rows if o.get("kind") == "override"]
    return [d for d in (verdict.get("detectors") or [])
            if str(d.get("result", "")).lower() == "fail"
            and not any(o.get("overrides") == verdict.get("id") and o.get("detector_id") == d.get("detector_id")
                        for o in ovr)]


def escapes(rows, genuine):
    """Post-cutoff genuine closes whose cited verdict still carries an un-overridden failing detector —
    a false-PASS that shipped. 0 by construction going forward (close-session refuses such a close)."""
    n = 0
    for c in _post_cutoff_closes(rows, genuine):
        v = _verdict(rows, c.get("verdictId"))
        if v and _uncovered_fails(rows, v):
            n += 1
    return n


def prevention_integrity(rows, genuine):
    """Of post-cutoff genuine AUDITED closes, the fraction with NO escape AND every failing detector
    localized (a span_ref, or an rca pinning it). None until there is >=1 post-cutoff audited close —
    a vacuous 1.0 over zero runs would be the exact CF-065 shape this metric exists to avoid."""
    rcas = [r for r in rows if r.get("kind") == "rca"]
    audited = [(c, _verdict(rows, c.get("verdictId"))) for c in _post_cutoff_closes(rows, genuine)]
    audited = [(c, v) for c, v in audited if v]
    if not audited:
        return None
    good = 0
    for c, v in audited:
        fails = [d for d in (v.get("detectors") or []) if str(d.get("result", "")).lower() == "fail"]
        localized = all(d.get("span_ref") or any(rc.get("verdictId") == v.get("id")
                        and rc.get("failing_detector") == d.get("detector_id") for rc in rcas) for d in fails)
        if not _uncovered_fails(rows, v) and localized:
            good += 1
    return round(good / len(audited), 4)


def census_gap_feed(ledger):
    """Run census.py as a subprocess against the SAME ledger and parse its tally line — the
    established census-as-subprocess pattern, no invasive refactor. Returns a dict or None."""
    try:
        r = subprocess.run([sys.executable, str(CENSUS_PY), "--ledger", str(ledger)],
                           capture_output=True, text=True, cwd=str(ROOT))
    except Exception:
        return None
    m = re.search(r"(\d+) transport \| (\d+) exchange \| (\d+) enforcement \| (\d+) unlinked \| (\d+) blocking",
                 r.stdout)
    if not m:
        return None
    return {"transport_gaps": int(m.group(1)), "exchange_gaps": int(m.group(2)),
            "enforcement_gaps": int(m.group(3)), "unlinked": int(m.group(4))}


def snapshot(rows=None, ledger=None):
    """The whole headline panel as one dict. Absent census feed leaves gap keys None (not 0, so a
    missing feed can never look like 'no gaps')."""
    ledger = ledger or LEDGER
    rows = census.read_jsonl(ledger) if rows is None else rows
    g = genuine_runs(rows)
    audited = runs_audited(rows, g)
    snap = {
        "runs_genuine": len(g),
        "runs_audited": len(audited),
        "audit_rate": round(len(audited) / len(g), 4) if g else 0.0,
        "self_heal": len(self_heal(rows, g)),
        "recurrences": len(recurrences(rows, g)),
        "escapes": escapes(rows, g),
        "prevention_integrity": prevention_integrity(rows, g),
    }
    feed = census_gap_feed(ledger)
    snap.update(feed if feed else {"transport_gaps": None, "exchange_gaps": None,
                                    "enforcement_gaps": None, "unlinked": None})
    return snap


# ── the ratchet: no headline number regresses vs the committed baseline ────────────────────
# direction: '+' may not fall (more is better), '-' may not rise (fewer is better).
DIRECTION = {
    "runs_genuine": "+", "runs_audited": "+", "audit_rate": "+", "self_heal": "+",
    "prevention_integrity": "+", "recurrences": "-", "escapes": "-",
    "transport_gaps": "-", "exchange_gaps": "-", "enforcement_gaps": "-", "unlinked": "-",
}
# audit_rate is the operative lead while prevention_integrity has no post-cutoff data (it is None until
# a genuine run closes after DISPOSITION_FROM). Per PD-013 it becomes the lead once it populates.
LEAD = "audit_rate"
EPS = 1e-9


def regressions(snap, base):
    """List of (metric, direction, base_val, now_val) that moved the wrong way. A None on either
    side is skipped (an unmeasured census feed is not a regression, and not a free pass either —
    it simply is not ratcheted this run; the panel shows it as '?')."""
    out = []
    for k, dirn in DIRECTION.items():
        b, n = base.get(k), snap.get(k)
        if b is None or n is None:
            continue
        if dirn == "+" and n < b - EPS:
            out.append((k, dirn, b, n))
        if dirn == "-" and n > b + EPS:
            out.append((k, dirn, b, n))
    return out


# ── controls: gut a metric, a control flips (mutation discipline, mirrors census.controls) ──
def controls():
    out = []
    intent = lambda rid: {"id": f"i-{rid}", "kind": "intent", "runId": rid, "intent_source": "asked"}
    close = lambda rid: {"id": f"c-{rid}", "kind": "close", "runId": rid, "verdictId": f"v-{rid}"}
    verdict = lambda rid, dets: {"id": f"v-{rid}", "kind": "verdict", "runId": rid,
                                 "intentCardId": f"i-{rid}", "detectors": dets}

    # GENUINE: an intent-only stub (no close) is not a genuine run.
    stub = [intent("s1")]
    out.append(("GENUINE a run with no close is NOT genuine", genuine_runs(stub) == []))
    full = [intent("g1"), verdict("g1", [{"detector_id": "x", "result": "pass"}]), close("g1")]
    out.append(("GENUINE an intent+close run IS genuine", genuine_runs(full) == ["g1"]))

    # AUDITED: a genuine run WITH a verdict is audited; without, not.
    unaud = [intent("u1"), close("u1")]
    out.append(("AUDITED a genuine run with a verdict counts", runs_audited(full, genuine_runs(full)) == ["g1"]))
    out.append(("AUDITED a genuine run with NO verdict does not", runs_audited(unaud, genuine_runs(unaud)) == []))

    # SELF-HEAL: rca target harness counts; target output does not.
    heal = full + [{"id": "rc1", "kind": "rca", "runId": "g1", "target": "harness"}]
    nheal = full + [{"id": "rc2", "kind": "rca", "runId": "g1", "target": "output"}]
    out.append(("SELF-HEAL an rca target=harness counts", len(self_heal(heal, genuine_runs(heal))) == 1))
    out.append(("SELF-HEAL an rca target=output does NOT", len(self_heal(nheal, genuine_runs(nheal))) == 0))

    # RECURRENCE: same CF failing in 2 genuine runs = a recurrence; in 1 = not.
    two = [intent("a"), verdict("a", [{"detector_id": "CF-046", "result": "fail"}]), close("a"),
           intent("b"), verdict("b", [{"detector_id": "CF-046", "result": "fail"}]), close("b")]
    one = [intent("a"), verdict("a", [{"detector_id": "CF-046", "result": "fail"}]), close("a")]
    out.append(("RECURRENCE a CF failing in 2 genuine runs is a recurrence", recurrences(two, genuine_runs(two)) == ["CF-046"]))
    out.append(("RECURRENCE a CF failing in only 1 run is not", recurrences(one, genuine_runs(one)) == []))
    # free-text detector ids are out of scope (never counted as a recurrence).
    freetext = [intent("a"), verdict("a", [{"detector_id": "gate-runs-clean", "result": "fail"}]), close("a"),
                intent("b"), verdict("b", [{"detector_id": "gate-runs-clean", "result": "fail"}]), close("b")]
    out.append(("RECURRENCE a free-text detector id is out of scope", recurrences(freetext, genuine_runs(freetext)) == []))

    # ESCAPE / PREVENTION: a post-cutoff close on an un-overridden failing detector is an escape.
    ev = lambda rid, ts, res: {"id": f"v-{rid}", "kind": "verdict", "ts": ts, "runId": rid,
                               "intentCardId": f"i-{rid}", "detectors": [{"detector_id": "CF-046", "result": res}]}
    cl = lambda rid, ts: {"id": f"c-{rid}", "kind": "close", "ts": ts, "runId": rid, "verdictId": f"v-{rid}"}
    esc = [intent("e"), ev("e", "2026-07-21T00:00:00Z", "fail"), cl("e", "2026-07-21T01:00:00Z")]
    out.append(("ESCAPE a post-cutoff close with an un-overridden fail counts", escapes(esc, genuine_runs(esc)) == 1))
    esc_ok = esc + [{"id": "o-e", "kind": "override", "ts": "2026-07-21T00:30:00Z", "runId": "e",
                     "overrides": "v-e", "detector_id": "CF-046", "reason": "accepted"}]
    out.append(("ESCAPE an override on the verdict+detector clears it", escapes(esc_ok, genuine_runs(esc_ok)) == 0))
    pre = [intent("p"), ev("p", "2026-07-19T00:00:00Z", "fail"), cl("p", "2026-07-19T01:00:00Z")]
    out.append(("ESCAPE a pre-cutoff close is exempt (forward-only)", escapes(pre, genuine_runs(pre)) == 0))
    clean = [intent("q"), ev("q", "2026-07-21T00:00:00Z", "pass"), cl("q", "2026-07-21T01:00:00Z")]
    out.append(("PREVENTION a clean post-cutoff audited close scores 1.0", prevention_integrity(clean, genuine_runs(clean)) == 1.0))
    out.append(("PREVENTION an escaping close scores 0.0", prevention_integrity(esc, genuine_runs(esc)) == 0.0))
    out.append(("PREVENTION is None with no post-cutoff close (not a vacuous 1.0)", prevention_integrity(pre, genuine_runs(pre)) is None))

    # RATCHET: a below-baseline snapshot regresses; at/above does not.
    base = {"runs_genuine": 4, "audit_rate": 1.0, "recurrences": 0, "transport_gaps": 2}
    below = {"runs_genuine": 3, "audit_rate": 1.0, "recurrences": 0, "transport_gaps": 2}
    worse = {"runs_genuine": 4, "audit_rate": 1.0, "recurrences": 0, "transport_gaps": 5}
    at = {"runs_genuine": 4, "audit_rate": 1.0, "recurrences": 0, "transport_gaps": 2}
    out.append(("RATCHET a dropped genuine run regresses", any(k == "runs_genuine" for k, *_ in regressions(below, base))))
    out.append(("RATCHET a risen census gap regresses", any(k == "transport_gaps" for k, *_ in regressions(worse, base))))
    out.append(("RATCHET an at-baseline snapshot does NOT regress", regressions(at, base) == []))
    return out


# ── output ────────────────────────────────────────────────────────────────────────────────
def _fmt(v):
    return "?" if v is None else (f"{v:.4f}" if isinstance(v, float) else str(v))


def print_panel(snap, base):
    regs = {k for k, *_ in regressions(snap, base)} if base else set()
    print(f"\n== impact scoreboard ==  (lead: {LEAD}={_fmt(snap.get(LEAD))})")
    print(f"  {'metric':<18} {'value':>8}  {'baseline':>8}  {'dir':>3}  vs")
    for k, dirn in DIRECTION.items():
        b = base.get(k) if base else None
        flag = "REGRESSED" if k in regs else ("ok" if base else "—")
        print(f"  {k:<18} {_fmt(snap.get(k)):>8}  {_fmt(b):>8}  {dirn:>3}  {flag}")
    if any(snap.get(k) is None for k in ("transport_gaps", "exchange_gaps", "enforcement_gaps", "unlinked")):
        print("  note: census gap feed unavailable this run ('?') — those numbers are not ratcheted.")
    if snap.get("prevention_integrity") is None:
        print("  note: prevention_integrity is '?' until a genuine run closes after the disposition "
              "cutoff — a vacuous 1.0 over zero runs would be the exact shape it exists to avoid.")


def main():
    snap = snapshot()
    base = json.loads(BASELINE.read_text()) if BASELINE.exists() else {}

    if "--set-baseline" in sys.argv:
        BASELINE.write_text(json.dumps(snap, indent=2, sort_keys=True) + "\n")
        print_panel(snap, snap)
        print(f"\nbaseline RAISED → {BASELINE.name} (explicit)")
        print("RESULT: BASELINE SET")
        return 0

    print_panel(snap, base)
    regs = regressions(snap, base) if base else []
    strict = "--strict" in sys.argv
    if not base:
        print("\nRESULT: NO BASELINE (run --set-baseline to seed the ratchet)")
        return 1 if strict else 0
    if regs:
        print(f"\n  {len(regs)} REGRESSION(S) vs baseline:")
        for k, dirn, b, n in regs:
            print(f"    {k}: {_fmt(b)} -> {_fmt(n)} (may not {'fall' if dirn == '+' else 'rise'})")
        print("RESULT: REGRESSED" + ("" if strict else "  (non-blocking; run --strict to enforce)"))
        return 1 if strict else 0
    print("\nRESULT: HELD (no headline number regressed)")
    return 0


def run_controls():
    print("== IMPACT CONTROLS ==")
    ok_all = True
    for name, ok in controls():
        print(f"  {'CONTROL PASS' if ok else 'CONTROL FAIL'} :: {name}")
        ok_all = ok_all and ok
    print(f"RESULT: {'CONTROLS PASS' if ok_all else 'CONTROLS FAIL'}")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(run_controls() if "--controls" in sys.argv else main())
