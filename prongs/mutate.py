#!/usr/bin/env python3
"""mutate — tests the tests. Breaks each checker on purpose and demands the controls notice.

WHY THIS EXISTS
The C0 audit did not read validate_prongs.py and conclude the controls were real. Reading
cannot establish that: a control wired to live logic and a control hardcoded to True are
visually identical on the page, and I read mine three times without seeing the difference.
What the Auditor did instead was delete a checker's body and watch the controls flip to FAIL.

That move was performed once, by hand, by a model that happened to think of it. This file is
that move, automated, run every time. The distinction matters and is the whole point of the
file: a finding an auditor produced once is a fact about one afternoon; the same finding
wired into a script is a property of the repo.

It also replaces a rule I first recorded as prose in a memory file, which was the same
mistake one level up: writing "rules decay unless checked" as an unchecked rule (CF-001,
self-violating rules in generated content). House-rule 1 ranks a written reminder last for
a reason.

HOW IT WORKS
For each check function:
  1. replace it with a stub returning [] (finds nothing, ever)
  2. re-run controls()
  3. at least one control MUST flip from pass to fail

A checker whose destruction changes nothing is not being tested. In mutation-testing terms
the mutant SURVIVED, and a surviving mutant is a hole in the suite, not in the code.

Run:  python3 prongs/mutate.py
"""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

# Load validate_prongs fresh for each mutation, so one mutation cannot leak into the next.
def load():
    spec = importlib.util.spec_from_file_location("vp", HERE / "validate_prongs.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def control_results(mod):
    """{control name: did it fire}. controls() resolves check_* through module globals at
    call time, so replacing an attribute on the module is enough to mutate what it exercises."""
    return {name: fired for name, fired in mod.controls()}


BASE = control_results(load())

# Every check function that controls() exercises. A checker absent from this list is a
# checker whose controls nothing verifies, so the list itself is checked below.
TARGETS = ["check_schema", "check_schema_kinds", "check_verdict_cites_intent", "check_verdict_cites_detectors",
           "check_no_orphan_drift", "check_probe_gate", "check_detector_gate",
           "check_fanout_independence", "check_deferred_assumption_gate", "check_rule7_signal",
           "check_rule10_unleaked", "check_rule12_not_self_graded", "check_rule6_reversibility", "check_rat",
           "check_rca"]

print("== mutation test: break each checker, confirm its controls notice ==\n")
print(f"  baseline: {sum(BASE.values())}/{len(BASE)} controls firing\n")

survivors = []
for fn in TARGETS:
    mod = load()
    if not hasattr(mod, fn):
        survivors.append((fn, "function does not exist"))
        print(f"  MISSING {fn}")
        continue

    # The mutant: a checker that finds nothing, no matter what it is given. This is the
    # single most dangerous real-world failure, because its output is indistinguishable
    # from a clean bill of health.
    setattr(mod, fn, lambda *a, **k: [])

    after = control_results(mod)
    flipped = [n for n in BASE if BASE[n] and not after.get(n, False)]

    if flipped:
        print(f"  ok      {fn:<28} killed by {len(flipped)} control(s)")
        for n in flipped[:3]:
            print(f"            {n}")
    else:
        survivors.append((fn, "no control changed when this checker was gutted"))
        print(f"  SURVIVED {fn:<27} nothing noticed")

# A checker with no controls at all would never appear as a survivor, because it was never
# in TARGETS. So verify TARGETS covers every check_* the module defines: otherwise this
# file passes by not looking, which is the exact vacuous-pass shape it exists to prevent.
mod = load()
defined = sorted(n for n in dir(mod) if n.startswith("check_"))
unlisted = [n for n in defined if n not in TARGETS]
if unlisted:
    print(f"\n  UNCOVERED: {len(unlisted)} check function(s) not in TARGETS, so no mutant was run:")
    for n in unlisted:
        print(f"    {n}")
    survivors.extend((n, "not covered by any mutant") for n in unlisted)

print()
if survivors:
    print(f"  {len(survivors)} SURVIVING MUTANT(S). Each is a checker you could delete without failing a test:\n")
    for fn, why in survivors:
        print(f"    {fn}: {why}")
    print("\nRESULT: FAIL")
    sys.exit(1)

print(f"  {len(TARGETS)}/{len(TARGETS)} checkers killed by their own controls")
print("  every control is wired to real logic, not hardcoded")
print("RESULT: PASS")
