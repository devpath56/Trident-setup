#!/usr/bin/env python3
"""test-reuse-authority — the SEPARATE-FILE durability control for the CF-075 reuse-authority axis
inside check_prior_art (PD-015).

Why a separate file (PD-017): check_prior_art's in-file controls live in validate_prongs.controls(),
so reverting validate_prongs.py reverts the check AND its controls together — prove-durable reports
that whole-file revert as GREEN (the fix-and-guard-revert-together leak). Mutation (mutate.py) covers
gutting the function, but not a raw file reversion. This file does NOT revert with validate_prongs.py:
it imports check_prior_art fresh and drives it against the breadth fixture, so reverting the branch in
validate_prongs.py makes THIS go red. Wired into selftest.py -> the reuse-authority wire is durable by
reversion, not only by mutation.

Run:  python3 tests/test-reuse-authority.py
"""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "prongs"))
import validate_prongs as v  # noqa: E402

TS = "2026-07-22T00:00:00Z"  # post PRIOR_ART_FROM, so the forward-gate is active
def rat(reuse):
    return {"kind": "ratverdict", "id": "rv-test", "ts": TS, "prior_art": {"reuse": reuse}}

fails = 0
def check(label, cond):
    global fails
    print(("  ok   " if cond else "  FAIL ") + label)
    if not cond: fails += 1

print("== CF-075 reuse-authority axis is durable (separate-file control, PD-017) ==\n")

# breadth-only reuse pick MUST fire (this is the guard the wire adds; reverting the branch drops it)
breadth = v.check_prior_art([rat("adopt it: the industry standard, the most widely used, canonical choice")])
check("prestige-only reuse pick FIRES the CF-075 axis", bool(breadth))
check("  ...and the message names authority-by-breadth", any("authority-by-breadth" in m for m in breadth))

# a reuse pick that states fit-to-this-repo MUST pass (prestige is a real signal when not alone)
fit = v.check_prior_art([rat("reuse the standard lib: battle-tested and already a dependency in our stack")])
check("fit-justified reuse pick PASSES (breadth + a fit axis)", not fit)

# a build-new scan MUST pass (no prestige claim at all)
build = v.check_prior_art([rat("grepped repo: no existing capability, building new")])
check("build-new scan PASSES (no authority claim)", not build)

# the lexicon SSOT the JS guard shares must exist and carry both axes
lex = json.load(open(ROOT / "authority-lexicon.json"))
check("shared lexicon carries prestige + fit + fit_reuse axes",
      all(k in lex and lex[k] for k in ("prestige", "fit", "fit_reuse")))

print(f"\nRESULT: {'PASS' if not fails else str(fails) + ' FAIL'}")
sys.exit(1 if fails else 0)
