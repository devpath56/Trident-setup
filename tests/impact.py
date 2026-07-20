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

SCOPE (Track A — computable TODAY, deterministically, from the current schema)
The Auditor rejected the original north-star `prevention_integrity` because its input `escapes`
rests on fields the ledger does not record (no per-detector resolution status; override targets a
probe, not a detector; no supersede link) and would misclassify the one real accepted-fail on file
(c0-audit). So `escapes`, `localized`, and `prevention_integrity` are DEFERRED to Track B, behind a
per-detector `disposition` schema field. This file tracks only what is computable without judgment.

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
    }
    feed = census_gap_feed(ledger)
    snap.update(feed if feed else {"transport_gaps": None, "exchange_gaps": None,
                                    "enforcement_gaps": None, "unlinked": None})
    return snap


# ── the ratchet: no headline number regresses vs the committed baseline ────────────────────
# direction: '+' may not fall (more is better), '-' may not rise (fewer is better).
DIRECTION = {
    "runs_genuine": "+", "runs_audited": "+", "audit_rate": "+", "self_heal": "+",
    "recurrences": "-", "transport_gaps": "-", "exchange_gaps": "-",
    "enforcement_gaps": "-", "unlinked": "-",
}
LEAD = "audit_rate"  # the number the scoreboard sorts by (NOT prevention_integrity — see header)
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
    print("  note: escapes / localized / prevention_integrity are Track B (need a per-detector "
          "disposition field); not measured here.")


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
