#!/usr/bin/env python3
"""census_durability — the DURABLE gate that makes tests/census.py's two audited fixes stick.

WHY THIS FILE EXISTS (and does NOT live inside census.py)
--------------------------------------------------------
census.py carries two audited fixes:
  FIX #1  liveness = a genuine intent+close loop, not a bare append (is_genuine_run / real).
  FIX #2  "live" = produced AND consumed, with a "produced, never consumed" rung (is_consumed /
          transport_verdict).
Its own controls() prove those functions work — but a control that lives in the same file it
guards reverts WITH that file. prove-durable showed exactly this: reverting census.py deleted
its own guard, and selftest still went green (worse: selftest imported census, and a reverted
census sys.exits at module load, short-circuiting the whole suite to a silent pass).

This file breaks that circularity. It is a SEPARATE file (it does not revert when census.py is
reverted) and it never IMPORTS census — it drives census only as a SUBPROCESS, so a reverted
census's module-level sys.exit cannot contaminate this process or the suite. selftest.py runs
this file as a HARD block. Revert census.py to HEAD and this file fails, which fails selftest:
that is what "durable" means.

HOW IT CATCHES A REVERTED CENSUS (three independent signals)
------------------------------------------------------------
  1. --ledger honored (FIX plumbing): a crafted fixture ledger is fed via `--ledger`. A HEAD
     census has no --ledger support, so it silently reads the REAL ledger and reports the real
     repo's populated mechanisms instead of the empty fixture — a divergence we assert on.
  2. genuine-loop liveness (FIX #1): a full intent+close loop makes its assumptions record read
     "live"; a bare stub (no intent/close for its runId) does NOT.
  3. --controls verdict rung (FIX #2, ledger-independent): `census.py --controls` must emit the
     named liveness+consumption controls all PASS. A HEAD census has no --controls handling and
     emits the ordinary census instead, so the required `CONTROL … PASS` lines are absent.

Run standalone:  python3 tests/census_durability.py   (exit 0 = durable in force, 1 = a hole)
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CENSUS = HERE / "census.py"


def _write_ledger(rows):
    """Write rows to a TEMP fixture ledger (never the real prongs/prongs.jsonl) and return its
    path. The caller unlinks it. Using tempfile keeps the concurrent writer's ledger untouched."""
    fd, path = tempfile.mkstemp(prefix="census_fixture_", suffix=".jsonl")
    with os.fdopen(fd, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    return path


def _run_census(ledger=None, controls=False, timeout=60):
    """Drive census.py as a SUBPROCESS (never import it — a reverted census sys.exits on import).
    Returns (returncode, stdout). Feeds the fixture via BOTH --ledger and CENSUS_LEDGER so the
    control does not depend on which override a future census keeps."""
    cmd = [sys.executable, str(CENSUS)]
    env = dict(os.environ)
    if controls:
        cmd.append("--controls")
    if ledger is not None:
        cmd += ["--ledger", ledger]
        env["CENSUS_LEDGER"] = ledger
    try:
        p = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True,
                           timeout=timeout, env=env)
        return p.returncode, p.stdout + "\n" + p.stderr
    except Exception as e:  # a hung/crashing census is itself a failure signal
        return 999, f"<census subprocess error: {e}>"


def _verdict_for(stdout, mechanism):
    """Pull the transport-table verdict for a mechanism (e.g. 'AssumptionSet') out of census
    stdout. Returns the trailing verdict text, or None if the row/table is absent (a reverted
    census that errored, or emitted no table, yields None — itself a failure)."""
    for line in stdout.splitlines():
        s = line.strip()
        if s.startswith(mechanism + " ") or s.startswith(mechanism + "\t"):
            # columns: name medium schema validator records verdict...
            rest = s[len(mechanism):].strip()
            parts = rest.split()
            # drop medium/schema/validator (y/NO) and the record count, keep the verdict phrase
            # everything after the first 4 whitespace-separated tokens is the verdict text
            return " ".join(parts[4:]).strip() if len(parts) > 4 else ""
    return None


# ── the genuine loop / bare stub fixtures ──────────────────────────────────────
def _genuine_intent_close(run="r-good"):
    return [
        {"id": f"i-{run}", "kind": "intent", "ts": "t0", "runId": run, "intent_source": "asked",
         "scope": {"in_scope": ["a"], "out_of_scope": ["b"]}, "goal": "g"},
        {"id": f"c-{run}", "kind": "close", "ts": "t2", "runId": run,
         "verdictId": "v", "intentCardId": f"i-{run}"},
    ]


def validate_all():
    """Return [(ok, message), …]. Every message names what a reverted census breaks."""
    out = []

    # ── CONTROL 1 — FIX plumbing: --ledger is honored (a stub-only ledger is empty of intents) ──
    # A HEAD census ignores --ledger and reads the REAL ledger, which always carries intent rows,
    # so it reports IntentCard "live". The fixed census reads our stub-only fixture and reports it
    # as a gap. This flip is robust: a live Trident ledger always has >=1 intent, and the
    # concurrent writer only appends.
    stub_only = [{"id": "asmS", "kind": "assumptions", "ts": "t", "runId": "r-stub-xyz",
                  "phase": "build", "assumptions": [{"claim": "x", "kill_power": 1}]}]
    led = _write_ledger(stub_only)
    try:
        rc, out1 = _run_census(ledger=led)
        v_intent = _verdict_for(out1, "IntentCard")
        ok = (rc == 0 and v_intent is not None and "live" not in v_intent)
        out.append((ok,
                    "DURABLE-LEDGER: census honors --ledger (a stub-only fixture reports IntentCard "
                    "as a gap, not live; a reverted census ignores --ledger and reads the real "
                    f"ledger -> 'live'). got IntentCard={v_intent!r}"))
    finally:
        os.unlink(led)

    # ── CONTROL 2 — FIX #1: a genuine intent+close loop makes its assumptions record LIVE ──
    # is_genuine_run must count a full loop. Fixture: intent + close + an assumptions artifact,
    # all under r-good.
    genuine = _genuine_intent_close("r-good") + [
        {"id": "asmG", "kind": "assumptions", "ts": "t1", "runId": "r-good", "phase": "build",
         "assumptions": [{"claim": "x", "kill_power": 1}]}]
    led = _write_ledger(genuine)
    try:
        rc, out2 = _run_census(ledger=led)
        v_asm = _verdict_for(out2, "AssumptionSet")
        ok = (rc == 0 and v_asm == "live")
        out.append((ok,
                    "DURABLE-GENUINE-live: a full intent+close loop makes its assumptions record "
                    f"'live' (FIX #1). got AssumptionSet={v_asm!r}"))
    finally:
        os.unlink(led)

    # ── CONTROL 3 — FIX #1: a bare stub (assumptions, no intent/close for its runId) is NOT live ──
    # Same run carries a genuine intent loop (so the intent IS live) but the assumptions row sits
    # under a loopless runId. is_genuine_run must discount it: IntentCard live, AssumptionSet gap.
    mixed = _genuine_intent_close("r-good") + [
        {"id": "asmS", "kind": "assumptions", "ts": "t", "runId": "r-stub-xyz", "phase": "build",
         "assumptions": [{"claim": "x", "kill_power": 1}]}]
    led = _write_ledger(mixed)
    try:
        rc, out3 = _run_census(ledger=led)
        v_intent = _verdict_for(out3, "IntentCard")
        v_asm = _verdict_for(out3, "AssumptionSet")
        ok = (rc == 0 and v_intent == "live" and v_asm is not None and "live" not in v_asm)
        out.append((ok,
                    "DURABLE-GENUINE-stub: a bare assumptions stub (no intent/close for its runId) "
                    "is NOT live even when a real intent loop is (FIX #1). got "
                    f"IntentCard={v_intent!r}, AssumptionSet={v_asm!r}"))
    finally:
        os.unlink(led)

    # ── CONTROL 4 — FIX #2 (+#1 functions): --controls emits the named controls, all PASS ──
    # Ledger-independent: census's controls() build their own in-memory fixtures and exercise
    # is_genuine_run / real / is_consumed / transport_verdict directly, including the
    # "produced, never consumed" rung that the real transport table cannot reach (every real kind
    # is code-consumed). A reverted census has no --controls path -> no CONTROL lines -> fails.
    rc, out4 = _run_census(controls=True)
    control_lines = [l for l in out4.splitlines() if l.startswith("CONTROL ")]
    passed = {l.split("::", 1)[1].strip() for l in control_lines if l.startswith("CONTROL PASS ::")}
    failed = [l for l in control_lines if l.startswith("CONTROL FAIL ::")]
    have_genuine = any(n.startswith("GENUINE-") for n in passed)
    have_consume = any(n.startswith("CONSUME-") for n in passed)
    controls_ok = (rc == 0 and "RESULT: CONTROLS PASS" in out4
                   and not failed and have_genuine and have_consume)
    out.append((controls_ok,
                "DURABLE-CONTROLS: `census.py --controls` reports the named liveness+consumption "
                "controls all PASS (>=1 GENUINE-* and >=1 CONSUME-*; a reverted census has no "
                f"--controls path). got rc={rc}, passed={len(passed)}, failed={len(failed)}"))

    return out


def main():
    print("== census durability controls ==")
    results = validate_all()
    all_ok = True
    for ok, msg in results:
        print(("  ok   " if ok else "  FAIL ") + msg)
        all_ok = all_ok and ok
    print(f"\nRESULT: {'DURABLE' if all_ok else 'HOLE OPEN — census.py fixes are ungated'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
