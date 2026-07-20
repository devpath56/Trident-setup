#!/usr/bin/env python3
"""Meta-scope gate + validator for the Trident *decisions* ledger (failures/decisions.jsonl).

WHY THIS EXISTS
  The decisions ledger records design decisions about TRIDENT ITSELF (pre-emptive PD-###
  records) — NOT object-level decisions from a session where Trident is merely watching
  someone else's work. This module is the wired-in check that enforces that scope. A rule
  written in a SKILL file is a reminder; only an executed check is a gate (house-rules rung note).

WHAT IT ENFORCES (all fail-closed — any violation => nonzero exit)
  1. Repo identity: we are in the Trident SOURCE repo (marker files present).
  2. Meta-scope: every PD's `applied_in` path is inside Trident's own design tree AND exists on
     disk (narrated != executed). A path outside the tree = an object-level decision => rejected.
  3. Schema-lite: each PD line parses and carries the required fields; ids are unique PD-###.
  4. Detector reality: the PD-001 binary-verdict detector is exercised against fixtures, INCLUDING
     a known-bad control that MUST fail — a detector that never fires is not a guard.

Dependency-free (stdlib only), per the no-build guardrail.
  Run standalone:  python3 failures/validate_decisions.py
  Imported by:     tests/selftest.py (so the commit gate covers the ledger too).
"""
import json, os, re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LEDGER = os.path.join(HERE, "decisions.jsonl")
SCHEMA = os.path.join(HERE, "decisions.schema.json")
FIXTURES = os.path.join(HERE, "fixtures")

# --- 1. repo identity: are we working ON Trident (its source repo), not just with it? ---
_MARKERS = (".claude/skills/trident/SKILL.md", "failures/failures.jsonl", "failures/decisions.schema.json")
def repo_is_trident_source(root=ROOT):
    return all(os.path.exists(os.path.join(root, m)) for m in _MARKERS)

# --- 2. meta-scope: the ONLY files a Trident meta-decision may touch ---
# Widen this list only when Trident's own design genuinely grows a new home. Everything else is
# object-level and must not be logged here.
_ALLOWED_PREFIXES = (".claude/skills/", "failures/", "tests/", "prongs/")
_ALLOWED_ROOT_FILES = {"CLAUDE.md", "README.md", "ARCHITECTURE.md", "INSTALL.md"}

def _norm(path):
    """Normalize to a repo-relative path. Strips a single leading './' PREFIX — NOT a char-set
    (lstrip('./') would eat the leading dot of '.claude', a subtle and dangerous bug)."""
    p = path.strip()
    if p.startswith("./"):
        p = p[2:]
    return p

def in_design_tree(path):
    """True iff `path` is a repo-relative file inside Trident's own design tree."""
    if not isinstance(path, str) or not path.strip():
        return False
    if os.path.isabs(path):                      # absolute path — also breaks the no-external-path rule
        return False
    p = _norm(path)
    if ".." in p.split("/"):                      # no escaping the tree
        return False
    if p in _ALLOWED_ROOT_FILES:
        return True
    return p.startswith(_ALLOWED_PREFIXES)

def meta_scope_violations(rec):
    """Return a list of reasons this record is NOT a valid Trident meta-decision (empty = ok)."""
    reasons = []
    if rec.get("scope") != "trident-meta":
        reasons.append(f"scope != 'trident-meta' (got {rec.get('scope')!r}) — not marked a meta-decision")
    ai = rec.get("applied_in")
    if not isinstance(ai, list) or not ai:
        reasons.append("applied_in missing/empty — a meta-decision must name the Trident design files it changed")
    else:
        for p in ai:
            if not in_design_tree(p):
                reasons.append(f"applied_in {p!r} is OUTSIDE Trident's own design tree "
                               f"=> object-level decision, does not belong in this ledger")
            elif not os.path.exists(os.path.join(ROOT, _norm(p))):
                reasons.append(f"applied_in {p!r} does not exist on disk (narrated != executed)")
    return reasons

# --- 4. PD-001 detector: a judge verdict must be per-dimension binary, never numeric/Likert ---
_NUMERIC = re.compile(r'\b\d+\s*/\s*\d+\b|\bscore\b|\blikert\b|\d+\s*out of\s*\d+', re.I)
def verdict_is_binary(verdict):
    """The executed form of PD-001. Return (ok, reason)."""
    dims = verdict.get("dimensions")
    if not isinstance(dims, list) or not dims:
        return False, "no per-dimension list"
    for d in dims:
        name = d.get("name", "?")
        v = str(d.get("verdict", "")).strip().lower()
        if v not in ("pass", "fail"):
            return False, f"dimension {name!r}: verdict {v!r} is not binary pass/fail"
        for k, val in d.items():
            if k in ("name", "verdict", "rationale"):
                continue
            if isinstance(val, bool):
                continue
            if isinstance(val, (int, float)):
                return False, f"dimension {name!r}: numeric field {k}={val!r} (scores banned)"
            if isinstance(val, str) and _NUMERIC.search(val):
                return False, f"dimension {name!r}: score-like value {k}={val!r}"
    return True, "ok"

# --- assembling the checks ---
def _load_jsonl(path):
    out = []
    with open(path) as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            out.append((i, json.loads(line)))
    return out

def _load_fixture(name):
    return json.load(open(os.path.join(FIXTURES, name)))

def validate_all():
    """Yield (ok: bool, msg: str) checks. Consumed by selftest.py and by main()."""
    checks = []
    def ck(cond, msg): checks.append((bool(cond), msg))

    ck(repo_is_trident_source(), "repo identity: this IS the Trident source repo (log decisions here only)")

    schema = json.load(open(SCHEMA))
    required = schema["required"]

    ids = []
    for i, r in _load_jsonl(LEDGER):
        rid = r.get("id", "?")
        ids.append(rid)
        miss = [k for k in required if k not in r]
        ck(not miss, f"{rid}: has all required fields" + (f" (missing {miss})" if miss else ""))
        ck(re.fullmatch(r"PD-\d{3,}", rid) is not None, f"{rid}: id format PD-###")
        ck(r.get("kind") == "decision", f"{rid}: kind == 'decision' (not an observed failure)")
        scope_reasons = meta_scope_violations(r)
        if scope_reasons:
            for reason in scope_reasons:
                ck(False, f"{rid}: META-SCOPE {reason}")
        else:
            ck(True, f"{rid}: meta-scope ok (touches only Trident's own design tree)")
    ck(len(ids) == len(set(ids)), "no duplicate PD numbers")

    # detector reality — the gate must actually fire on known-bad input (CF-060)
    ok_good, _ = verdict_is_binary(_load_fixture("verdict_good_binary.json"))
    ck(ok_good, "PD-001 detector: PASSES a clean per-dimension binary verdict")
    ok_bad, why = verdict_is_binary(_load_fixture("verdict_bad_numeric.json"))
    ck(not ok_bad, f"PD-001 detector: FAILS the known-bad numeric verdict (control fired: {why})")

    # meta-scope gate must reject an object-level PD (known-bad control)
    oos = _load_fixture("pd_out_of_scope.json")
    ck(bool(meta_scope_violations(oos)),
       "meta-scope gate: REJECTS an out-of-scope (object-level) PD (control fired)")

    return checks

def main():
    print("== Trident decisions-ledger validator ==")
    fails = 0
    for ok, msg in validate_all():
        print(("  ok   " if ok else "  FAIL ") + msg)
        fails += 0 if ok else 1
    print(f"\nRESULT: {'PASS' if not fails else f'FAIL ({fails} checks)'}")
    return 1 if fails else 0

if __name__ == "__main__":
    raise SystemExit(main())
