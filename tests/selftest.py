#!/usr/bin/env python3
"""Trident self-test — validates the failures-log SSOT and the regression suite.
Deterministic, dependency-free. Run: python3 trident/tests/selftest.py
Exit 0 = all pass; exit 1 = a check failed (loud, per FL-cf031)."""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
JSONL = os.path.join(ROOT, "failures", "failures.jsonl")
SCHEMA = os.path.join(ROOT, "failures", "schema.json")
RCASES = os.path.join(HERE, "regression-cases.md")

fails = []
def check(cond, msg):
    print(("  ok   " if cond else "  FAIL ") + msg)
    if not cond: fails.append(msg)

print("== Trident self-test ==")

# --- load schema (required fields + detector enum) ---
schema = json.load(open(SCHEMA))
required = schema["required"]
kinds = set(schema["properties"]["detector"]["properties"]["kind"]["enum"])
statuses = set(schema["properties"]["status"]["enum"])

# --- load + validate every record ---
records, ids = [], []
for i, line in enumerate(open(JSONL), 1):
    line = line.strip()
    if not line: continue
    try:
        r = json.loads(line)
    except Exception as e:
        check(False, f"line {i}: invalid JSON ({e})"); continue
    records.append(r); ids.append(r.get("id"))
    miss = [k for k in required if k not in r]
    check(not miss, f"{r.get('id','?')}: has all required fields" + (f" (missing {miss})" if miss else ""))
    check(re.fullmatch(r"CF-\d{3,}", r.get("id","")) is not None, f"{r.get('id')}: id format")
    check(r.get("status") in statuses, f"{r.get('id')}: status in {sorted(statuses)}")
    d = r.get("detector", {})
    check(d.get("kind") in kinds, f"{r.get('id')}: detector.kind in {sorted(kinds)}")
    check(bool(d.get("check")) and bool(d.get("signal")), f"{r.get('id')}: detector has check+signal")

nums = [int(x.split("-")[1]) for x in ids if x]
check(nums == sorted(nums), "records are sorted by CF number")
check(len(nums) == len(set(nums)), "no duplicate CF numbers")

# --- regression cases cross-reference ---
rc_ids = set(re.findall(r"RC-(CF-\d{3,})", open(RCASES).read()))
missing = [rc for rc in rc_ids if rc not in set(ids)]
check(not missing, "every regression case maps to a real CF" + (f" (orphans: {missing})" if missing else ""))

# --- decisions ledger: meta-scope gate + PD regression cross-reference ---
sys.path.insert(0, os.path.join(ROOT, "failures"))
import validate_decisions as vd
for ok, msg in vd.validate_all():
    check(ok, msg)
pd_ids = {r["id"] for _, r in vd._load_jsonl(vd.LEDGER)}
rc_pd = set(re.findall(r"RC-(PD-\d{3,})", open(RCASES).read()))
missing_pd = [rc for rc in rc_pd if rc not in pd_ids and rc != "PD-scope"]
check(not missing_pd, "every PD regression case maps to a real PD" + (f" (orphans: {missing_pd})" if missing_pd else ""))

# --- PD-007: intent-source gate + prong-output shape gate must discriminate ---
import intent_gate as ig
_ig_cases = [
    ("intent gate: an ASKED IntentCard is accepted", ig.check_intent_source({"intent_source": "asked", "goal": "g", "scope": {"in_scope": ["x"], "out_of_scope": ["y"]}})[0]),
    ("intent gate: an INFERRED IntentCard is REJECTED (control)", not ig.check_intent_source({"intent_source": "inferred", "goal": "g", "scope": {"in_scope": ["x"], "out_of_scope": ["y"]}})[0]),
    ("intent gate: a MISSING intent_source fails closed (control)", not ig.check_intent_source({"goal": "g"})[0]),
    ("scope gate: a card with NO scope is REJECTED (control)", not ig.check_intent_source({"intent_source": "asked", "goal": "g"})[0]),
    ("scope gate: an empty out_of_scope is REJECTED (control)", not ig.check_intent_source({"intent_source": "asked", "goal": "g", "scope": {"in_scope": ["x"], "out_of_scope": []}})[0]),
    ("shape gate: bullets + table pass", ig.check_shape("| a | b |\n|---|---|\n- x\n  - y\n")[0]),
    ("shape gate: a prose paragraph is REJECTED (control)", not ig.check_shape("One sentence here. Two sentences here. Three sentences here.\n")[0]),
    ("shape gate: unbounded prose behind a bullet prefix is REJECTED (control)", not ig.check_shape("- A. B. C. D. E. F. G.\n")[0]),
    ("shape gate: a short multi-sentence reasoning bullet still passes", ig.check_shape("- A first point. A second, related. A third that connects.\n")[0]),
]
for _name, _ok in _ig_cases:
    check(_ok, _name)

# --- PD-002: the TNR judge-validation gate must discriminate ---
import tnr
for ok, msg in tnr.validate_all():
    check(ok, msg)

# --- PD-004: versioned rubric registry + silent-edit detector ---
import rubrics
for ok, msg in rubrics.validate_all():
    check(ok, msg)

# --- no personal data in the committed log ---
blob = open(JSONL).read()
leaks = [p for p in ("/Users/", "devanshpathak") if p in blob]
# house-rule 9: no personal data in a committed record. Re-scanned on every run.
check(not leaks, "no personal paths in the SSOT" + (f" (found {leaks})" if leaks else ""))

# --- summary ---
kd = {}
for r in records: kd[r["detector"]["kind"]] = kd.get(r["detector"]["kind"], 0) + 1
print(f"\n  {len(records)} records | detector mix: " +
      ", ".join(f"{k}:{v}" for k, v in sorted(kd.items())))
print(f"  {len(rc_ids)} regression cases wired")

# --- prong exchange + doors + census presence (makes prove-durable ORPHANS durable) ---
# prove-durable found validate_prongs, the session doors, and census were real gates that
# NOTHING invoked, so they would rot. Running them here is the trigger that makes them durable:
# delete any of these files and this suite goes red, which is the definition of durable.
_here = _os0.path.dirname(_os0.path.abspath(__file__)) if False else os.path.dirname(os.path.abspath(__file__))
def _run(label, cmd, cwd):
    r = __import__("subprocess").run(cmd, cwd=cwd, capture_output=True, text=True)
    check(r.returncode == 0, label + ("" if r.returncode == 0 else f" (exit {r.returncode})"))
    return r

_root = os.path.dirname(_here)
_run("prong validator passes (C0-C3)", [sys.executable, "prongs/validate_prongs.py"], _root)
_run("session doors hold (open/compose/close)", ["node", "tests/test-doors.mjs"], _root)
# spans.mjs derives the Auditor's Spans from the Do-er's EXECUTED transcript (narrated==executed,
# CF-046). Exercising it here makes it durable: delete/gut spans.mjs and this suite goes red.
_run("span extractor holds (executed transcript -> Spans)", ["node", "tests/test-spans.mjs"], _root)
# Blocking, unlike the census below. A surviving mutant means a checker could be deleted
# without failing a test, which makes every green result downstream of it meaningless.
# That is a broken build, not a backlog item.
import subprocess as _sp0, os as _os0, sys as _sys0
_m = _sp0.run([_sys0.executable, _os0.path.join(_os0.path.dirname(_os0.path.abspath(__file__)),
                                                "..", "prongs", "mutate.py")],
              capture_output=True, text=True)
if _m.returncode == 0:
    print(f"  mutation: {[l for l in _m.stdout.splitlines() if 'killed by their own' in l][0].strip()}")
else:
    print("  mutation: SURVIVING MUTANT(S) - a checker can be deleted without failing a test")
    for _l in _m.stdout.splitlines():
        if "SURVIVED" in _l or ": no control" in _l or ": not covered" in _l:
            print(f"    {_l.strip()}")
    fails.append("mutation test: surviving mutant")

# --- census durability controls (HARD; reverting census.py flips one) ---
# The census's two audited holes were fixed by named functions (is_genuine_run, is_consumed,
# real, transport_verdict). Those fixes must be DURABLE: reverting tests/census.py to HEAD has
# to fail THIS suite. The guard therefore lives in a SEPARATE file, tests/census_durability.py,
# which does not revert with census.py and drives census only as a SUBPROCESS — never `import
# census`, because a reverted census sys.exits at module load and would short-circuit this whole
# suite to a silent pass (the exact hole prove-durable found). Running the durability file as a
# subprocess isolates that: a reverted/empty census makes census_durability exit nonzero, which
# fails a check here. FIX #1 flips DURABLE-GENUINE-*/-LEDGER; FIX #2 flips DURABLE-CONTROLS.
_cd = _run("census durability controls (HARD; reverting census.py flips one)",
           [sys.executable, os.path.join(_here, "census_durability.py")], _root)
for _l in _cd.stdout.splitlines():
    _s = _l.strip()
    if _s.startswith(("ok", "FAIL")) and "DURABLE-" in _s:
        print("    " + _s)

# --- coverage, not correctness ---
# Everything above proves the gates work ON FIXTURES. It cannot prove they were ever applied
# to real work, and those come apart: design-loop had 6 runs showing a green gate where the
# craft checks had never run at all. So surface the census count here, next to the PASS, or
# a green selftest reads as "Trident is working" when the exchange it governs is dead.
# Non-blocking on purpose: gaps are a backlog, not a broken build. Use `census.py --strict`
# in CI once the count is driven to zero.
import subprocess as _sp, os as _os
_c = _sp.run([sys.executable, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "census.py")],
             capture_output=True, text=True)
_last = [l for l in _c.stdout.splitlines() if l.startswith("RESULT:")]
_tally = [l for l in _c.stdout.splitlines() if "blocking" in l]
# BLOCKING on whether census EXECUTED, non-blocking on the gap COUNT. Deleting census.py makes
# the subprocess fail to produce a RESULT line, which fails the suite (so census is durable),
# while an open gap count stays a backlog, not a broken build (no gate fatigue).
check(bool(_last), "census executed (its absence fails the suite; the gap COUNT stays non-blocking)")
print(f"  census: {_last[0].replace('RESULT: ', '') if _last else 'DID NOT RUN'}"
      f"{' | ' + _tally[0].strip() if _tally else ''}")
print("          (fixtures passing is not coverage. python3 tests/census.py for the gap list)")

# --- outward-impact ratchet (Track A): audit_rate + census non-regression, forward-only ---
# census asks "were the gates applied?"; impact asks "is the audit actually happening and holding
# across REAL runs?" A RATCHET, not a threshold: --strict exits 1 if any headline number regresses
# vs the committed impact-baseline.json. Blocking here does double duty — deleting impact.py makes
# this exit nonzero (durability), and a genuine regression reddens the suite until it is fixed or
# the baseline is raised explicitly (python3 tests/impact.py --set-baseline, never silent). The
# north-star escapes/prevention_integrity are Track B, deferred behind a per-detector disposition
# field (the Auditor rejected them as not deterministically computable from the current schema).
_run("outward-impact ratchet holds (audit_rate + census non-regression)",
     [sys.executable, "tests/impact.py", "--strict"], _root)

print(("\nRESULT: PASS" if not fails else f"\nRESULT: FAIL ({len(fails)} checks)"))
sys.exit(1 if fails else 0)
