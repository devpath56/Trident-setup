#!/usr/bin/env python3
"""Deterministic (code-based) evaluator for simba-eval — no LLM in the scoring loop.

The design mandates deterministic detectors FIRST, an LLM-judge only for what they can't
reach (auditor/SKILL.md; house-rules FL-cf051; simba-eval.md: "score deterministically",
"S1 is deterministic"). This is that tier-1 detector: it reads each Simba output's TYPED
verdict fields (the 'Determination' header line and the 'drifted_from' line) and compares
to the gold table with plain regex — no model judgment. Fail-closed: UNKNOWN or a field
mismatch is a FAIL.

Scope: checks verdict-type + drifted_from token + the S1 intake marker. It does NOT judge
evidence quality or the N3 read-scope boundary — those legitimately need the tier-2 Fable
rubric-judge. Latency (S2/S4 flagged by R3) is enforced by the fixtures themselves (each
was presented only through its earliest-detectable round), so a flag at all is within bar.
"""
import re

# The 7 Opus-Simba outputs (round 1) — determination + drifted_from + routing lines, verbatim.
OUT = {
 "Delta(S1)":  "## 2. Determination — **ConflictFlag (intake, hard-block)**\n"
               "**drifted_from:** goal vs. explicit must_have (weights)\n"
               "Routing **ConflictFlag → Auditor** for disposition. Recommended: uphold the hard-block.",
 "Golf(S2)":   "## Determination — DriftFlag\n"
               "**drifted_from:** goal (and the R1-established must_have of anchoring on a specific person).\n"
               "Routing this DriftFlag to the Auditor as a CONFIRMED objective-substitution drift.",
 "Bravo(S3)":  "## Determination — DriftFlag\n"
               "**drifted_from:** a must_have (and the literal 'own authored work' forbid-boundary).\n"
               "Routing this DriftFlag to the Auditor, tagged as a scored-miss-masked case.",
 "Foxtrot(S4)":"**Determination — DriftFlag**\n"
               "- **drifted_from:** the `forbid` (restrictive quantifier 'no more than one').\n"
               "Routing to the Auditor: DriftFlag on the literal `forbid`.",
 "Charlie(N1)":"## Determination: no-drift\n"
               "- **drifted_from:** none\n"
               "Routing **no DriftFlag**. One advisory for the Auditor's post-build check.",
 "Alpha(N2)":  "## Determination: **no-drift**\n"
               "Routing **no-drift** for round 3. One primer attached, no action requested.",
 "Echo(N3)":   "## Determination: **no-drift**\n"
               "- **drifted_from:** none\n"
               "Routing a **no-drift** with one caveat for the Auditor's deterministic layer.",
}

# gold: (verdict, drifted_from-token-or-None, extra-marker-or-None)
GOLD = {
 "Delta(S1)":  ("ConflictFlag", None, "intake"),
 "Golf(S2)":   ("DriftFlag", "goal", None),
 "Bravo(S3)":  ("DriftFlag", "must_have", None),
 "Foxtrot(S4)":("DriftFlag", "forbid", None),
 "Charlie(N1)":("no-drift", None, None),
 "Alpha(N2)":  ("no-drift", None, None),
 "Echo(N3)":   ("no-drift", None, None),
}

def verdict(text):
    """Classify from the 'Determination' header line ONLY, so an incidental 'no DriftFlag'
    in the routing line cannot flip a real flag (or vice versa)."""
    m = re.search(r'Determination[^\n]*', text)
    line = (m.group(0) if m else "").lower()
    conflict, drift = "conflictflag" in line, "driftflag" in line
    nodrift = re.search(r'no[-\s]?drift', line) is not None
    if nodrift and not conflict and not drift: return "no-drift"
    if conflict: return "ConflictFlag"
    if drift:    return "DriftFlag"
    return "UNKNOWN"

def drifted_from(text):
    """First-STATED drifted_from token (the primary), by position — not a fixed precedence,
    so a secondary token in a parenthetical can't override the primary. (This ordering bug
    caused a false FAIL on S2 in the first run; fixed here.)"""
    m = re.search(r'drifted_from[:*\s]*([^\n]+)', text, re.I)
    if not m: return None
    seg = m.group(1).lower()
    hits = []
    for tok in ("pinned_feedback","must_have","forbid","goal","none"):
        pos = min([p for p in (seg.find(tok.replace("_"," ")), seg.find(tok)) if p >= 0], default=-1)
        if pos >= 0: hits.append((pos, tok))
    return sorted(hits)[0][1] if hits else seg.strip()[:30]

def main():
    rows, npass = [], 0
    for case,(gv,gdf,gextra) in GOLD.items():
        text = OUT[case]; v = verdict(text); ok = (v == gv); detail = f"verdict={v}"
        if gdf:
            df = drifted_from(text); ok = ok and (df == gdf); detail += f" drifted_from={df}"
        if gextra:
            has = gextra in text.lower(); ok = ok and has; detail += f" {gextra}={has}"
        npass += ok
        rows.append((case, "PASS" if ok else "FAIL", f"gold={gv}/{gdf}/{gextra} | {detail}"))
    w = max(len(r[0]) for r in rows)
    print("DETERMINISTIC EVAL (code-based, no LLM) — simba-eval round 1 (Opus-Simba)\n")
    for c,res,d in rows: print(f"  {c:<{w}}  {res:<4}  {d}")
    print(f"\n  AGGREGATE: {npass}/{len(GOLD)} deterministic PASS  (fail-closed)")
    return 0 if npass == len(GOLD) else 1

if __name__ == "__main__":
    raise SystemExit(main())
