"""
Context-compaction policy — ENFORCEMENT, not prose (Trident; see references/method.md).

A policy is real only once its check runs and is verified (CF-034). Prose in method.md cannot enforce
itself; these are the deterministic gates the Auditor runs before promoting any compacted WorkingState.
Three method.md SAFETY rules become BLOCK conditions here; the when-to-compact rule is advisory.

Run:  python3 compaction_policy.py   (exit 0 = policy checks hold, nonzero = a violation slipped through)
"""

# --- when to compact (ADVISORY, calibrated from RESULT-05) ---------------------------------------
def should_compact(round_history_chars, artifact_chars):
    """Compact only once the discardable history outweighs the artifact you must carry anyway.
    Below that the contract's fixed overhead loses (RESULT-05: 3-round cut was 31%; per-round history
    overtakes the artifact around round 4, after which each round saves 40%+)."""
    return round_history_chars > artifact_chars

# --- the fail-closed promotion gate (SAFETY-CRITICAL, mandatory) ---------------------------------
def promotion_gate(parse_config_fn, working_state_text, intent_card_text):
    """Return 'PROMOTE' or 'BLOCK: <reason>'. Enforces three method.md rules deterministically."""
    # Rule 1 — invariants pinned OUT-OF-BAND (Simba IntentCard), never folded into the lossy stream.
    if "__" not in intent_card_text or "ValueError" not in intent_card_text:
        return "BLOCK: invariant not pinned in IntentCard"
    # Rule 2 — compact HISTORY, not the artifact: the WorkingState must still carry the artifact.
    if "def parse_config" not in working_state_text:
        return "BLOCK: WorkingState dropped the artifact"
    # Rule 3 — every compaction is gated by an EXECUTABLE invariant check (behavior, not grep; CF-014).
    try:
        parse_config_fn("__proto__: 1")
        return "BLOCK: invariant dropped (compaction unsafe)"   # it did NOT raise -> unsafe
    except ValueError:
        return "PROMOTE"
    except Exception as e:
        return f"BLOCK: unexpected ({e})"

# --- reference artifacts: a good (intact) and a lossy (dropped-invariant) WorkingState ------------
GOOD_SRC = '''
def parse_config(text):
    cfg = {}
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        k, _, v = line.partition(":")
        k = k.strip()
        if k.startswith("__"):
            raise ValueError("illegal key")
        cfg[k] = v.strip()
    return cfg
'''
LOSSY_SRC = '''
def parse_config(text):
    cfg = {}
    for line in text.splitlines():
        if not line.strip():
            continue
        k, _, v = line.partition(":")
        cfg[k.strip()] = v.strip()   # dunder guard lost in compaction
    return cfg
'''
INTENT_OK = 'must_haves: any key beginning with "__" raises ValueError. never weaken it.'
INTENT_BAD = 'must_haves: parse config lines into a dict.'   # invariant NOT pinned

def _fn(src):
    ns = {}
    exec(src, ns)
    return ns["parse_config"]

# --- the tests (this is the PROOF the policy is enforced) -----------------------------------------
def run():
    good, lossy = _fn(GOOD_SRC), _fn(LOSSY_SRC)
    cases = [
        # (name, expected_startswith, actual)
        ("gate PROMOTES an intact compaction",
         "PROMOTE",  promotion_gate(good,  GOOD_SRC,  INTENT_OK)),
        ("gate BLOCKS a dropped invariant",
         "BLOCK",    promotion_gate(lossy, LOSSY_SRC, INTENT_OK)),
        ("gate BLOCKS a WorkingState missing the artifact",
         "BLOCK",    promotion_gate(good,  "notes: refactored things", INTENT_OK)),
        ("gate BLOCKS when the invariant is not pinned out-of-band",
         "BLOCK",    promotion_gate(good,  GOOD_SRC,  INTENT_BAD)),
        ("advisory: do NOT compact when history < artifact",
         "False",    str(should_compact(500, 800))),
        ("advisory: DO compact when history > artifact",
         "True",     str(should_compact(2000, 800))),
    ]
    ok = True
    for name, expected, actual in cases:
        passed = actual.startswith(expected)
        ok = ok and passed
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}  ->  {actual}")
    return ok

if __name__ == "__main__":
    import sys
    print("context-compaction policy enforcement:")
    sys.exit(0 if run() else 1)
