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
check(not leaks, "no personal paths in the SSOT" + (f" (found {leaks})" if leaks else ""))

# --- summary ---
kd = {}
for r in records: kd[r["detector"]["kind"]] = kd.get(r["detector"]["kind"], 0) + 1
print(f"\n  {len(records)} records | detector mix: " +
      ", ".join(f"{k}:{v}" for k, v in sorted(kd.items())))
print(f"  {len(rc_ids)} regression cases wired")
print(("\nRESULT: PASS" if not fails else f"\nRESULT: FAIL ({len(fails)} checks)"))
sys.exit(1 if fails else 0)
