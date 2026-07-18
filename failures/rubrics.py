#!/usr/bin/env python3
"""Versioned judge-rubric registry + silent-edit detector (enacts PD-004).

WHY: a judge rubric that is edited in place, untracked, is criteria drift you can't see — a criterion
shifts, verdicts flip, and no one can tell whether the judge or the work changed. So each judged
dimension's binary rubric lives here as a tracked artifact, versioned, bound to the calibration slice
that validated it (PD-002). A change is only legitimate if it bumps the version AND re-records the
content hash AND its calibration dimension still clears the TNR gate.

THE SILENT-EDIT DETECTOR (deterministic):
  content_hash = sha256(criterion \\x00 version). Stored in the rubric. If someone edits `criterion`
  without bumping `version` / re-recording the hash, the recomputed hash mismatches -> FLAGGED.
  A rubric is "gate-ready" only if: hash matches AND criterion is binary (names PASS and FAIL) AND its
  calibration dimension is TNR-validated by tnr.py. Anything else => not-gate-ready, fail-closed.

Dependency-free (stdlib only).
  Check the registry:  python3 failures/rubrics.py
  Imported by:         tests/selftest.py
"""
import hashlib, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)          # so `import tnr` works standalone and under selftest
import tnr

REGISTRY = os.path.join(HERE, "rubrics")     # one .json per judged dimension
FIXTURES = os.path.join(HERE, "fixtures")

def content_hash(rubric):
    """Semantic fingerprint of a rubric: its criterion + version. Edit the criterion without bumping
    the version and this changes, exposing the silent edit."""
    payload = f"{rubric.get('criterion','')}\x00{rubric.get('version','')}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

def _resolve(path):
    return path if os.path.isabs(path) else os.path.join(HERE, path)

def check_rubric(r):
    """Return a list of reasons this rubric is NOT gate-ready (empty = gate-ready)."""
    reasons = []
    for k in ("dimension", "version", "criterion", "type", "calibration_slice", "calibration_dimension", "validated"):
        if k not in r:
            reasons.append(f"missing field {k!r}")
    if reasons:
        return reasons
    if r["type"] != "binary":
        reasons.append(f"type {r['type']!r} != 'binary' (PD-001: judges are binary per dimension)")
    crit = r["criterion"].upper()
    if "PASS" not in crit or "FAIL" not in crit:
        reasons.append("criterion does not name both PASS and FAIL (not a binary criterion)")
    stored = r["validated"].get("content_hash")
    if stored != content_hash(r):
        reasons.append("stale content_hash: criterion/version changed without re-validation (silent criteria drift)")
    # the rubric's calibration dimension must actually clear the TNR gate (PD-002)
    slice_path = _resolve(r["calibration_slice"])
    if not os.path.exists(slice_path):
        reasons.append(f"calibration_slice {r['calibration_slice']!r} not found")
    else:
        dims = tnr.load_slice(slice_path)
        rows = dims.get(r["calibration_dimension"])
        if not rows:
            reasons.append(f"calibration_dimension {r['calibration_dimension']!r} not in slice")
        else:
            ev = tnr.evaluate_dimension(rows,
                                        r["validated"].get("tnr_bar", tnr.TNR_BAR),
                                        r["validated"].get("min_neg", tnr.MIN_NEG))
            if not ev["validated"]:
                reasons.append(f"calibration dimension not TNR-validated ({ev['reason']})")
    return reasons

def load_registry():
    out = []
    if os.path.isdir(REGISTRY):
        for name in sorted(os.listdir(REGISTRY)):
            if name.endswith(".json"):
                out.append((name, json.load(open(os.path.join(REGISTRY, name)))))
    return out

# --- self-test hook: real rubrics are gate-ready; a tampered one is flagged (CF-060 control) ---
def validate_all():
    checks = []
    def ck(cond, msg): checks.append((bool(cond), msg))
    reg = load_registry()
    ck(len(reg) >= 1, "rubric registry has >= 1 versioned rubric")
    for name, r in reg:
        reasons = check_rubric(r)
        ck(not reasons, f"rubric {name}: gate-ready" + (f" (issues: {reasons})" if reasons else ""))
    tampered = json.load(open(os.path.join(FIXTURES, "rubric_tampered.json")))
    ck(bool(check_rubric(tampered)),
       "silent-edit detector: FLAGS a rubric whose criterion changed without re-validation (control fired)")
    return checks

def main():
    print("== Trident judge-rubric registry ==")
    fails = 0
    for ok, msg in validate_all():
        print(("  ok   " if ok else "  FAIL ") + msg)
        fails += 0 if ok else 1
    print(f"\nRESULT: {'PASS' if not fails else f'FAIL ({fails} checks)'}")
    return 1 if fails else 0

if __name__ == "__main__":
    raise SystemExit(main())
