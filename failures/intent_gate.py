#!/usr/bin/env python3
"""intent_gate — the executed check behind house-rules 15 and 16 (PD-007).

Exists because PD-007 was first logged claiming detector.kind "deterministic" with no code
behind it. The Auditor rejected it under house-rule 11 (no borrowed "deterministic": never
call a verdict deterministic without an executed code artifact in the same turn). This file
is that artifact.

Two gates:
  15. An IntentCard is a valid Phase-0 gate input ONLY if intent_source == "asked".
      Simba must have ASKED the user; an inferred goal fails closed.
  16. A Trident-authored surface must be nested bullets or tables — no prose paragraphs.

Each gate ships with a known-good fixture AND a known-bad control that must actually fire.
A gate whose negative control never fires is not a gate (house-rule 13).

Run:  python3 failures/intent_gate.py
"""
import re
import sys

# --- gate 15 -----------------------------------------------------------------

VALID_SOURCES = {"asked", "inferred"}


def check_intent_source(card):
    """An IntentCard passes only when scope was asked AND the goal came from the user.

    Scope is checked FIRST because it is asked first: "what's the scope for this session?"
    is Simba's question 1, before the goal question and before any prong is spawned. A goal
    pursued across the wrong surface still burns the session.
    """
    if not isinstance(card, dict):
        return False, "IntentCard is not an object"
    src = card.get("intent_source")
    if src is None:
        return False, "intent_source missing — fail closed (house-rule 15)"
    if src not in VALID_SOURCES:
        return False, f"intent_source '{src}' not in {sorted(VALID_SOURCES)}"
    if src != "asked":
        return False, "intent_source == 'inferred' — goal was not asked; return to Simba step 0"

    scope = card.get("scope")
    if not isinstance(scope, dict):
        return False, "scope missing — question 1 ('what's the scope for this session?') was not asked"
    for half in ("in_scope", "out_of_scope"):
        val = scope.get(half)
        if val is None:
            return False, f"scope.{half} missing — a scope with no exclusions is not a scope"
        if isinstance(val, str):
            val = [val] if val.strip() else []
        if not isinstance(val, list) or not [v for v in val if str(v).strip()]:
            return False, f"scope.{half} is empty — both halves must be answered"

    if not str(card.get("goal", "")).strip():
        return False, "intent_source 'asked' but goal is empty"
    return True, "scope asked (both halves) + intent_source == 'asked' with a non-empty goal"


# --- gate 16 -----------------------------------------------------------------

# A line that opens a bullet, table row, heading, quote, or fence is structural, not prose.
STRUCTURAL = re.compile(r"^\s*([-*+•]|\d+[.)]|\||#{1,6}\s|>|```|~~~)")
# A bullet specifically (not a table row/heading): the carve-out lets a bullet carry connected
# multi-sentence reasoning, but not an UNBOUNDED paragraph. A whole paragraph prefixed with "- "
# must not slip through (the cold audit's DriftFlag on this gate). So bullets get a generous cap.
BULLET = re.compile(r"^\s*[-*+•]\s")
# Sentence end: terminal punctuation followed by whitespace + capital, or end of string.
SENTENCE_END = re.compile(r"[.!?][\"')\]]*(\s+(?=[A-Z(\"'])|\s*$)")
PROSE_SENTENCE_LIMIT = 3
# Higher than the prose limit on purpose: 3-4 connected sentences in a bullet are legitimate
# (the carve-out); 6+ is a paragraph wearing a bullet prefix.
BULLET_SENTENCE_LIMIT = 6


def _sentences(line):
    return len(SENTENCE_END.findall(line.strip()))


def check_shape(text, sentence_limit=PROSE_SENTENCE_LIMIT):
    """Reject any surface containing a prose paragraph.

    A prose paragraph = a run of consecutive NON-STRUCTURAL lines whose combined sentence
    count reaches sentence_limit. It must be measured per BLOCK, not per line: prose wraps,
    so a three-sentence paragraph can carry one sentence on each of three lines and no single
    line ever trips a line-based check. (The first version of this function was line-based;
    its negative control never fired, which is how the bug surfaced — house-rule 13.)

    Verbatim quoted evidence and connected judge reasoning stay compliant when carried INSIDE
    a bullet or table cell, since any line opening with a bullet/pipe/heading is structural.
    """
    if not isinstance(text, str):
        return False, "surface is not text"
    in_fence = False
    block, block_start = [], 0
    for n, raw in enumerate(text.splitlines(), start=1):
        line = raw.rstrip()
        if re.match(r"^\s*(```|~~~)", line):
            in_fence = not in_fence
            block = []
            continue
        structural = in_fence or not line.strip() or bool(STRUCTURAL.match(line))
        if structural:
            block = []
            # A bullet may carry connected reasoning, but not unbounded prose: prefixing a whole
            # paragraph with "- " must not exempt it from the sentence count.
            if BULLET.match(line) and _sentences(line) >= BULLET_SENTENCE_LIMIT:
                return False, (f"line {n}: {_sentences(line)} sentences crammed into one bullet "
                               f"(unbounded prose behind a bullet prefix)")
            continue
        if not block:
            block_start = n
        block.append(line)
        total = sum(_sentences(l) for l in block)
        if total >= sentence_limit:
            return False, f"line {block_start}: prose paragraph ({total} sentences, not in a bullet or table)"
    return True, "nested bullets and tables only — no prose paragraph found"


# --- self-test: every gate needs a control that actually fires ----------------

SCOPE_OK = {"in_scope": ["design-loop/"], "out_of_scope": ["the 3 localhost:5173 annotations"]}
GOOD_CARD = {"intent_source": "asked", "scope": SCOPE_OK, "goal": "ship the annotation trigger and use it"}
BAD_CARD = {"intent_source": "inferred", "scope": SCOPE_OK, "goal": "probably wants more observability"}
NO_SRC_CARD = {"scope": SCOPE_OK, "goal": "something"}
NO_SCOPE_CARD = {"intent_source": "asked", "goal": "something"}
HALF_SCOPE_CARD = {"intent_source": "asked", "scope": {"in_scope": ["design-loop/"], "out_of_scope": []}, "goal": "something"}

GOOD_SURFACE = """| detector | verdict |
|---|---|
| D1 | PASS |

- finding
  - evidence: the user said "only nested bullets". That is a literal restriction. It governs output.
"""

BAD_SURFACE = """The loop is now substantially more observable than it was. Every run writes a row to the
ledger and the dashboard renders it. This means you can see what happened without reading logs.
"""


def main():
    checks = []

    ok, msg = check_intent_source(GOOD_CARD)
    checks.append(("intent gate: an ASKED IntentCard is accepted", ok, msg))

    ok, msg = check_intent_source(BAD_CARD)
    checks.append(("intent gate: an INFERRED IntentCard is REJECTED (control)", (not ok), msg))

    ok, msg = check_intent_source(NO_SRC_CARD)
    checks.append(("intent gate: a MISSING intent_source fails closed (control)", (not ok), msg))

    ok, msg = check_intent_source(NO_SCOPE_CARD)
    checks.append(("scope gate: a card with NO scope is REJECTED (control)", (not ok), msg))

    ok, msg = check_intent_source(HALF_SCOPE_CARD)
    checks.append(("scope gate: scope with an empty out_of_scope is REJECTED (control)", (not ok), msg))

    ok, msg = check_shape(GOOD_SURFACE)
    checks.append(("shape gate: bullets + table + quoted evidence passes", ok, msg))

    ok, msg = check_shape(BAD_SURFACE)
    checks.append(("shape gate: a prose paragraph is REJECTED (control)", (not ok), msg))

    failed = 0
    print("== Trident intent/shape gate (house-rules 15, 16 — PD-007) ==")
    for name, passed, detail in checks:
        print(f"  {'ok  ' if passed else 'FAIL'} {name}" + (f" ({detail})" if not passed else ""))
        if not passed:
            failed += 1

    print(f"\nRESULT: {'PASS' if failed == 0 else 'FAIL'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
