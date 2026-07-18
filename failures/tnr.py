#!/usr/bin/env python3
"""TNR calculator + judge-validation gate for Trident rubric judges (enacts PD-002).

WHY: a rubric judge is unvalidated code until measured against human labels. The failure mode is
the *agreeableness bias* — a judge that waves work through scores high TPR while its TNR collapses,
so aggregate accuracy hides a catastrophic false-PASS rate. This module measures TNR per dimension
and gates on it, fail-closed.

THE CONVENTION (get this right or the metric inverts):
  POSITIVE class = PASS (the judge asserts the output is good).
    TP = human PASS & judge PASS   correctly passed good work
    FP = human FAIL & judge PASS   FALSE PASS — bad work shipped  (the dangerous error)
    TN = human FAIL & judge FAIL   correctly caught bad work
    FN = human PASS & judge FAIL   false fail — cheap: a wasted re-loop
  TPR = TP/(TP+FN)   of good items, fraction passed
  TNR = TN/(TN+FP)   of BAD items, fraction caught   <-- the agreeableness-bias detector
  An agreeable judge: high TPR, collapsed TNR (passes everything, catches no defects).

GATE (fail-closed): a judged dimension is VALIDATED only if
  (a) it has >= MIN_NEG hard-negative (human-FAIL) examples — you cannot measure catch-rate with
      nothing to catch (ties to CF-060: hard-negative traps required), AND
  (b) TNR >= TNR_BAR.
Anything else => "not-yet-validated" => its verdict may NOT gate work (fall back to a human check /
a Do-er re-loop). Aggregate accuracy is never sufficient on its own.

Dependency-free. Input: a calibration slice (JSONL), one labeled item per line:
  {"dimension": "...", "item": "...", "human_label": "pass|fail", "judge_verdict": "pass|fail"}

  Report a slice:  python3 failures/tnr.py [slice.jsonl]   (defaults to the synthetic fixture)
  Imported by:     tests/selftest.py (the commit gate exercises the discrimination).
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.join(HERE, "fixtures")
DEFAULT_SLICE = os.path.join(FIXTURES, "calibration_slice.jsonl")

TNR_BAR = 0.60   # a dimension's judge must catch >= 60% of true defects to gate. Tune per risk.
MIN_NEG = 5      # need at least this many hard negatives to measure catch-rate at all.

def _lab(x):
    v = str(x).strip().lower()
    if v not in ("pass", "fail"):
        raise ValueError(f"label must be pass|fail, got {x!r}")
    return v

def load_slice(path):
    """dimension -> list of (human_label, judge_verdict)."""
    dims = {}
    with open(path) as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            dim = r["dimension"]
            dims.setdefault(dim, []).append((_lab(r["human_label"]), _lab(r["judge_verdict"])))
    return dims

def confusion(rows):
    """rows: list of (human_label, judge_verdict). Positive class = PASS."""
    tp = fp = tn = fn = 0
    for human, judge in rows:
        if human == "pass" and judge == "pass": tp += 1
        elif human == "fail" and judge == "pass": fp += 1     # false PASS — the dangerous one
        elif human == "fail" and judge == "fail": tn += 1
        elif human == "pass" and judge == "fail": fn += 1
    return {"tp": tp, "fp": fp, "tn": tn, "fn": fn}

def rate(num, den):
    return None if den == 0 else num / den

def evaluate_dimension(rows, tnr_bar=TNR_BAR, min_neg=MIN_NEG):
    c = confusion(rows)
    n_neg = c["tn"] + c["fp"]            # true negatives = human-FAIL items
    n_pos = c["tp"] + c["fn"]            # true positives = human-PASS items
    tnr = rate(c["tn"], n_neg)
    tpr = rate(c["tp"], n_pos)
    if n_neg < min_neg:
        validated, reason = False, f"not-yet-validated: only {n_neg} hard negatives (need >= {min_neg})"
    elif tnr < tnr_bar:
        validated, reason = False, (f"not-yet-validated: TNR {tnr:.2f} < bar {tnr_bar:.2f} "
                                    f"(agreeableness bias: {c['fp']} false-PASS of {n_neg} true defects)")
    else:
        validated, reason = True, f"validated: TNR {tnr:.2f} >= bar {tnr_bar:.2f}, caught {c['tn']}/{n_neg} defects"
    return {**c, "n_neg": n_neg, "n_pos": n_pos, "tpr": tpr, "tnr": tnr,
            "validated": validated, "reason": reason}

def report(path=DEFAULT_SLICE, tnr_bar=TNR_BAR, min_neg=MIN_NEG):
    return {dim: evaluate_dimension(rows, tnr_bar, min_neg) for dim, rows in load_slice(path).items()}

# --- self-test hook: prove the calculator DISCRIMINATES (consumed by selftest.py) ---
def validate_all():
    checks = []
    def ck(cond, msg): checks.append((bool(cond), msg))
    rep = report(DEFAULT_SLICE)
    good = rep.get("groundedness_good", {})
    agree = rep.get("groundedness_agreeable", {})
    noneg = rep.get("only_positives", {})
    ck(good.get("validated") is True,
       f"TNR gate: a well-calibrated judge is VALIDATED (tnr={good.get('tnr')})")
    ck(agree.get("validated") is False and (agree.get("tnr") or 1) < TNR_BAR,
       f"TNR gate: an AGREEABLE judge (high TPR {agree.get('tpr')}, low TNR {agree.get('tnr')}) is REJECTED (control fired)")
    ck(noneg.get("validated") is False and noneg.get("n_neg", 0) < MIN_NEG,
       "TNR gate: a slice with no hard negatives is not-yet-validated (fail-closed, control fired)")
    return checks

def main(argv):
    path = argv[1] if len(argv) > 1 else DEFAULT_SLICE
    print(f"== TNR judge-validation report :: {os.path.relpath(path, HERE)} "
          f"(bar={TNR_BAR}, min_neg={MIN_NEG}) ==")
    print(f"  {'dimension':28} {'TPR':>5} {'TNR':>5} {'FP':>3} {'neg':>4}  verdict")
    any_bad = False
    for dim, m in report(path).items():
        tpr = "n/a" if m["tpr"] is None else f"{m['tpr']:.2f}"
        tnr = "n/a" if m["tnr"] is None else f"{m['tnr']:.2f}"
        flag = "VALIDATED" if m["validated"] else "NOT-YET"
        any_bad |= not m["validated"]
        print(f"  {dim:28} {tpr:>5} {tnr:>5} {m['fp']:>3} {m['n_neg']:>4}  {flag} — {m['reason']}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
