#!/usr/bin/env python3
"""census — the cheap end-to-end test: is Trident actually working, or only passing?

WHY THIS IS NOT selftest.py
---------------------------
selftest.py runs every gate against FIXTURES and reports PASS. It answers "do the gates
work?" It cannot answer "were the gates ever applied to real work?" Those come apart, and
when they do the green light is the most dangerous artifact in the repo.

  design-loop, 2026-07-19: 6 of 6 runs showed a green deterministic gate. All 6 had never
  had a craft check or a state check run at all. Absence had taken the shape of a pass.

So this file measures the two distances that let a contract be obeyed on paper and dead in
practice:

  TRANSPORT GAP    an artifact is produced but nothing consumes it, or nothing produces it
                   at all. Symptom: a mechanism with a schema and a validator and 0 records,
                   OR records that no prong and no code ever reads back.
  ENFORCEMENT GAP  a rule is stated somewhere no checker points. Symptom: an invariant whose
                   id appears in house-rules.md and in no executed file.

This file IS the executed check for house-rule 8 ("Mounted != executing: a guard counts as
coverage only once its heartbeat is verified"). Rule 8 is the abstract statement; the EXCHANGE
section below is its heartbeat, asking of every mechanism not "does a checker exist" but "did
anything ever flow through it". Registering itself in EXPLICIT is only permitted because that
registration is verified: the file must name the rule, which is what this paragraph does.

It is cheap on purpose: no model calls, no network, pure file reads. Run it every session.

  python3 tests/census.py            # census + gap list
  python3 tests/census.py --strict   # exit 1 if any gap is open (for CI)

The liveness and consumption logic lives in small named functions (is_genuine_run,
is_consumed, real, transport_verdict) so they are unit-testable and are exercised by the
controls() below, which tests/selftest.py runs as a HARD block. Reverting either audited fix
flips a named control from pass to fail.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STRICT = "--strict" in sys.argv


def _ledger_path():
    """Which ledger the transport census reads. Default = the real ROOT/prongs/prongs.jsonl,
    so normal runs are unchanged. A control can point the census at a crafted fixture WITHOUT
    touching the real ledger via `--ledger PATH` (or `--ledger=PATH`) or the CENSUS_LEDGER env
    var — this is what lets tests/census_durability.py feed known rows and assert the verdict."""
    for i, a in enumerate(sys.argv):
        if a == "--ledger" and i + 1 < len(sys.argv):
            return Path(sys.argv[i + 1])
        if a.startswith("--ledger="):
            return Path(a.split("=", 1)[1])
    env = os.environ.get("CENSUS_LEDGER")
    if env:
        return Path(env)
    return ROOT / "prongs/prongs.jsonl"


LEDGER = _ledger_path()

# Files a checker could live in. A rule is enforced only if it is named in one of these AND
# that file executes. Markdown is excluded by construction: a rule restated in prose is the
# thing we are trying to detect, not evidence against it.
# Two exclusions, both load-bearing:
#   this file  — its keyword table names every rule it looks for, so leaving it in makes the
#                census cite itself as the checker for rules nothing checks. The instrument
#                built to catch vacuous passes was producing one on its first run.
#   prototypes/ — sample app, not part of the harness. It matched rule 10 on the word "leak".
SELF = Path(__file__).resolve()
CODE = sorted(
    p for p in ROOT.rglob("*")
    if p.suffix in {".py", ".mjs", ".js", ".sh"}
    and "node_modules" not in p.parts and ".git" not in p.parts
    and "prototypes" not in p.parts
    and p.resolve() != SELF
)
CODE_TEXT = {p: p.read_text(errors="ignore") for p in CODE}
ALL_CODE = "\n".join(CODE_TEXT.values())


def rel(p):
    return str(Path(p).relative_to(ROOT))


def read_jsonl(p):
    if not p.exists():
        return []
    out = []
    for line in p.read_text().splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return out


# ── 1. MECHANISM TRANSPORT CENSUS ─────────────────────────────────────────────
# For each artifact the contract names: does it have a medium, a schema, a validator, and
# has any real work ever produced AND consumed one? The columns are ordered by how easy they
# are to fake. A file is easy. Records are not. A record that closes a genuine loop and is
# then read back is hardest of all — which is exactly what "live" now means.

# Re-read on every run: a concurrent session may still be appending to prongs.jsonl. The read
# happens here (import time for callers, run time for __main__) so read-dependent logic below
# sees the current ledger, never a stale snapshot.
PRONGS = read_jsonl(LEDGER)
FAILURES = read_jsonl(ROOT / "failures/failures.jsonl")
DECISIONS = read_jsonl(ROOT / "failures/decisions.jsonl")


# FIX #1 — liveness must mean a genuine loop, not a bare append.
# The old real() counted any record whose runId did not start with r-test/fixture/bootstrap as
# real work. A single BUILD-TIME appended row (asm-7c41e0b2, runId "trident-meta") therefore
# flipped AssumptionSet to "live" though no genuine loop ever produced or consumed one: one
# appended row with a plausible runId turned any gap green. A runId is a genuine run ONLY if a
# real IntentCard opened the loop (an `intent` row shares the runId) AND the loop was closed (a
# `close` row shares it). A runId that appears only on a lone artifact is scaffolding, not live.
def is_genuine_run(runId, rows):
    """True only if `runId` names a full loop: it must carry BOTH an `intent` row (a real
    IntentCard opened it) AND a `close` row (the loop finished). A runId seen only on a lone
    artifact — an appended assumptions/probe/override with no intent and no close — is
    scaffolding, and returns False."""
    if not runId:
        return False
    has_intent = any(r.get("kind") == "intent" and r.get("runId") == runId for r in rows)
    has_close = any(r.get("kind") == "close" and r.get("runId") == runId for r in rows)
    return has_intent and has_close


# Records I wrote while BUILDING the gate are not evidence the gate is used. Two discounts, both
# load-bearing: (1) anything whose runId marks it as a fixture or a bootstrap is discounted, or
# the census congratulates itself for its own scaffolding — an additional floor kept from the
# original; (2) a record only counts as real work if its runId is a GENUINE run (intent+close),
# so a bare appended row under a plausible-but-loopless runId is not counted live (FIX #1).
def real(rows, kind):
    hits = [r for r in rows if r.get("kind") == kind]
    boot = [r for r in hits
            if str(r.get("runId", "")).startswith(("r-test", "fixture", "bootstrap"))]
    genuine = [r for r in hits if r not in boot and is_genuine_run(r.get("runId"), rows)]
    return len(genuine), len(boot)


# FIX #2 — deliver the docstring's promise: "produced AND consumed", not merely produced.
# Section 1 used to count records only; "live" meant >= 1 real record, so a kind could be
# produced and read by nothing and still read as live. Consumption is now a first-class test.
def _referenced_ids(rows, exclude_kind):
    """Every string VALUE appearing (recursively) in rows whose kind != exclude_kind, other
    than each row's own `id`. A prong is consumed by the LEDGER when one of these values equals
    an id of a row of the kind under test — verdict.intentCardId -> intent, verdict.resolves ->
    drift, override.overrides -> probe, close.verdictId -> verdict — without hardcoding which
    field carries the reference."""
    refs = set()

    def walk(v):
        if isinstance(v, str):
            refs.add(v)
        elif isinstance(v, list):
            for x in v:
                walk(x)
        elif isinstance(v, dict):
            for x in v.values():
                walk(x)

    for r in rows:
        if r.get("kind") == exclude_kind:
            continue
        for k, v in r.items():
            if k == "id":
                continue  # a row's own id is not a reference to another prong
            walk(v)
    return refs


def is_consumed(kind, rows, code_text):
    """A kind is consumed if EITHER (a) another ledger row references an id of a row of this
    kind (cross-reference), OR (b) an executed code file actually READS rows of this kind
    (filters on `kind == "<kind>"` / `kind != "<kind>"`). Either is a genuine consumer;
    demanding both would wrongly flag a kind consumed only in code as never-consumed."""
    ids = {r.get("id") for r in rows if r.get("kind") == kind} - {None}
    if ids & _referenced_ids(rows, kind):
        return True
    k = re.escape(kind)
    return bool(
        re.search(rf'kind["\']?[^\n]{{0,8}}==\s*["\']{k}["\']', code_text)
        or re.search(rf'kind["\']?[^\n]{{0,8}}!=\s*["\']{k}["\']', code_text)
    )


def transport_verdict(has_medium, real_n, boot_n, consumed):
    """The verdict ladder. FIX #2 inserts the 'produced, never consumed' rung between scaffolding
    and live, so that a kind with real records that nothing reads back is reported as the
    transport gap the docstring always promised, not as live."""
    if not has_medium:
        return "NO MEDIUM: prose only", "no medium"
    if real_n == 0 and boot_n == 0:
        return "never written", "never produced"
    if real_n == 0:
        return f"only {boot_n} bootstrap", "only scaffolding"
    if not consumed:
        return "produced, never consumed", "produced, never consumed"
    return "live", None


MECHANISMS = [
    # name,            medium path,                    schema path,                     kind key
    ("IntentCard",     "prongs/prongs.jsonl",          "prongs/schema.json",            "intent"),
    ("AssumptionSet",  "prongs/prongs.jsonl",          "prongs/schema.json",            "assumptions"),
    ("Phase0 probe",   "prongs/prongs.jsonl",          "prongs/schema.json",            "probe"),
    ("DriftFlag",      "prongs/prongs.jsonl",          "prongs/schema.json",            "drift"),
    ("Verdict",        "prongs/prongs.jsonl",          "prongs/schema.json",            "verdict"),
    ("Override",       "prongs/prongs.jsonl",          "prongs/schema.json",            "override"),
    # ConflictFlag is NOT a separate mechanism: it is a `determination` value on a drift row,
    # already in the schema enum. Listing it as its own kind was a false positive in this
    # census's first run — it counted a name for something as a missing something.
    ("ConflictFlag",   "prongs/prongs.jsonl",          "prongs/schema.json",            "~determination"),
    # RATVerdict got its medium (schema kind `ratverdict`) the same hour this census first
    # reported it homeless, and this table went stale within the hour. A hardcoded inventory
    # drifts from the thing it inventories: the same disease it was built to detect, one
    # level up. close-session.mjs now requires one whenever a probe ran.
    ("RATVerdict",     "prongs/prongs.jsonl",          "prongs/schema.json",            "ratverdict"),
    ("FailureRecord",  "failures/failures.jsonl",      "failures/schema.json",          "*"),
    ("Decision (PD)",  "failures/decisions.jsonl",     "failures/decisions.schema.json", "*"),
]


# ── negative + positive controls for the two audited holes ─────────────────────
# CF-067 style: each control exercises one of the new named functions, so that reverting a fix
# necessarily flips a control. tests/selftest.py runs these as a HARD block (fail the suite).
#   GENUINE-*  guard FIX #1 (gameable liveness). Reverting real() to count any non-boot runId,
#              or loosening is_genuine_run to not require intent+close, flips one of these.
#   CONSUME-*  guard FIX #2 (production != consumption). Reverting transport_verdict to
#              "real>0 => live", or gutting is_consumed, flips one of these.
def controls():
    out = []

    # ── FIX #1 ──────────────────────────────────────────────────────────────────
    # (a) a bare stub row (assumptions, runId r-stub-xyz, NO intent/close for that runId) is
    #     NOT counted genuine; (b) a matching genuine run (intent+close+artifact) IS.
    stub = [{"id": "asmS", "kind": "assumptions", "ts": "t", "runId": "r-stub-xyz",
             "phase": "build", "assumptions": [{"claim": "x", "kill_power": 1}]}]
    out.append(("GENUINE-1 a bare stub (assumptions, runId r-stub-xyz, no intent/close) is NOT a genuine run",
                is_genuine_run("r-stub-xyz", stub) is False))

    genuine = [
        {"id": "iG", "kind": "intent", "ts": "t0", "runId": "r-good", "intent_source": "asked",
         "scope": {"in_scope": ["a"], "out_of_scope": ["b"]}, "goal": "g"},
        {"id": "asmG", "kind": "assumptions", "ts": "t1", "runId": "r-good", "phase": "build",
         "assumptions": [{"claim": "x", "kill_power": 1}]},
        {"id": "cG", "kind": "close", "ts": "t2", "runId": "r-good", "verdictId": "v", "intentCardId": "iG"},
    ]
    out.append(("GENUINE-2 a full loop (intent + artifact + close, same runId) IS a genuine run",
                is_genuine_run("r-good", genuine) is True))

    # end-to-end through real(): the stub counts 0 real-work records; the genuine run counts 1.
    out.append(("GENUINE-3 real() counts the bare stub as 0 real-work assumptions records",
                real(stub, "assumptions") == (0, 0)))
    out.append(("GENUINE-4 real() counts the full-loop assumptions record as 1 real-work record",
                real(genuine, "assumptions") == (1, 0)))

    # ── FIX #2 ──────────────────────────────────────────────────────────────────
    # (a) a produced-but-unconsumed kind is flagged "produced, never consumed"; (b) a consumed
    #     one is "live". Both the is_consumed primitive and the verdict ladder are exercised.
    unconsumed_rows = [{"id": "g1", "kind": "ghostkind", "ts": "t", "runId": "r-good"}]
    out.append(("CONSUME-1 a kind nothing references and no code reads is NOT consumed",
                is_consumed("ghostkind", unconsumed_rows, "") is False))

    consumed_xref = [{"id": "g1", "kind": "ghostkind", "ts": "t", "runId": "r-good"},
                     {"id": "u1", "kind": "user", "ts": "t", "runId": "r-good", "uses": "g1"}]
    out.append(("CONSUME-2a a kind whose id another row references IS consumed (ledger cross-ref)",
                is_consumed("ghostkind", consumed_xref, "") is True))
    out.append(('CONSUME-2b a kind an executed file reads (kind == "ghostkind") IS consumed',
                is_consumed("ghostkind", unconsumed_rows, 'if r.get("kind") == "ghostkind":') is True))

    # the verdict ladder: produced-but-unconsumed is a transport gap; produced-and-consumed is live.
    out.append(("CONSUME-3 a produced-but-unconsumed kind is flagged 'produced, never consumed'",
                transport_verdict(True, 1, 0, False) == ("produced, never consumed", "produced, never consumed")))
    out.append(("CONSUME-4 a produced-AND-consumed kind is 'live'",
                transport_verdict(True, 1, 0, True) == ("live", None)))

    return out


def main():
    print("== TRIDENT CENSUS ==\n")
    print("  Does each named mechanism have a medium, a schema, a validator, and real records"
          " that are ALSO consumed?\n")
    print(f"  {'mechanism':<16} {'medium':<7} {'schema':<7} {'validator':<10} {'records':<9} verdict")
    print(f"  {'-'*16} {'-'*7} {'-'*7} {'-'*10} {'-'*9} {'-'*24}")

    transport_gaps = []
    for name, medium, schema, kind in MECHANISMS:
        has_medium = bool(medium and (ROOT / medium).exists())
        has_schema = bool(schema and (ROOT / schema).exists())
        # A validator counts only if some executable file names this mechanism's kind or name.
        # Credit a validator if code references the mechanism's kind, its display name, OR the
        # file it lives in. Keying on the name alone reported failures.jsonl as unvalidated
        # because no checker says the word "FailureRecord" — it says "failures.jsonl".
        needles = [name]
        if kind and kind not in ("*",) and not kind.startswith("~"):
            needles.append(kind)
        if medium:
            needles.append(Path(medium).name)
        has_val = any(re.search(rf'["\']?{re.escape(n)}["\']?', ALL_CODE) for n in needles)

        if kind and kind.startswith("~"):
            # A determination value, not a kind. Count drift rows carrying it. A determination
            # rides on a drift row that IS consumed (verdict.resolves), so consumed follows the
            # drift kind; moot here since n is 0 in practice.
            field = kind[1:]
            n = len([r for r in PRONGS if r.get(field) == name])
            boot = 0
            consumed = is_consumed("drift", PRONGS, ALL_CODE)
        elif kind == "*":
            # Match on the filename, not the path. Both live under failures/, so a substring
            # test on the directory silently reported decisions.jsonl's count as 64. These logs
            # are consumed by their own validators (validate_prongs reads failures.jsonl; the
            # decisions validator reads decisions.jsonl), so consumption is credited from code.
            rows = DECISIONS if "decisions" in (medium or "") else FAILURES
            n, boot = len(rows), 0
            consumed = bool(medium and re.search(re.escape(Path(medium).name), ALL_CODE))
        elif kind:
            n, boot = real(PRONGS, kind)
            consumed = is_consumed(kind, PRONGS, ALL_CODE)
        else:
            n, boot = 0, 0
            consumed = False

        verdict, gap = transport_verdict(has_medium, n, boot, consumed)

        if gap:
            transport_gaps.append((name, gap))

        rec = f"{n}" + (f" (+{boot}b)" if boot else "")
        print(f"  {name:<16} {'y' if has_medium else 'NO':<7} {'y' if has_schema else 'NO':<7} "
              f"{'y' if has_val else 'NO':<10} {rec:<9} {verdict}")

    # ── 2. ENFORCEMENT CENSUS ─────────────────────────────────────────────────────
    # Parse the invariants straight out of house-rules.md so a newly added rule cannot be
    # silently omitted from its own audit. Hardcoding the list here would reintroduce exactly
    # the drift this is looking for.
    HR = (ROOT / ".claude/skills/references/house-rules.md").read_text()
    invariants = re.findall(r"^(\d+)\.\s+\*\*(.+?)\*\*", HR, re.M)

    # Three outcomes, not two. A binary checked/unchecked would merge "no check exists" with
    # "a check exists but nothing links it to the rule" — different diseases with different
    # cures (write a checker vs. add a reference). This is the CF-065 shape: a measurement must
    # distinguish holds / fails / never evaluated, or absence reads as the nearest good outcome.
    def linked_files(num):
        """A checker that names the rule id. The link is legible from both ends."""
        pats = [rf"house-?rule\s*{num}\b", rf"\bHR-?{num}\b", rf"invariant\s*{num}\b", rf"\brule\s*{num}\b"]
        return [rel(p) for p, t in CODE_TEXT.items()
                if any(re.search(pat, t, re.I) for pat in pats)]

    # Distinctive phrase per rule, used only to detect an UNLABELLED check. Hand-written because
    # the rule titles are too generic to keyword-match ("Reversibility gate" appears nowhere a
    # checker would say it). A miss here understates coverage, which is the safe direction.
    KEYWORDS = {
        "4": [r"acceptance[_ ]artifact"],
        "5": [r"per[- ]dimension", r"binary\s+PASS"],
        "6": [r"reversib", r"blast[_ ]radius"],
        "7": [r"read[_ ]before[_ ]assert"],
        "8": [r"heartbeat"],
        "9": [r"personal[_ ]path", r"personal data"],
        "10": [r"unleaked", r"typed artifact"],
        "12": [r"grader.*subject|subject.*grader", r"fixture[_ ]author"],
        "14": [r"\bTNR\b"],
    }

    def keyword_files(num):
        pats = KEYWORDS.get(num, [])
        if not pats:
            return []
        return [rel(p) for p, t in CODE_TEXT.items()
                if any(re.search(pat, t, re.I) for pat in pats)]

    # Two checkers this scan structurally cannot find on its own:
    #   rule 4  lives in the design-loop repo, outside ROOT, so rglob never sees it
    #   rule 8  IS this file, and this file excludes itself to stop the self-matching that made
    #           its first run cite itself as the checker for four unchecked rules
    # Registering them by hand would be a way to lie, so each entry is VERIFIED: the file must
    # exist and must actually name the rule. An unverifiable registration is dropped, loudly.
    EXPLICIT = {
        "4": ROOT.parent / "design-loop/checks/validate-tasks.mjs",
        "8": SELF,
    }

    def explicit_file(num):
        p = EXPLICIT.get(num)
        if not p or not Path(p).exists():
            return None
        t = Path(p).read_text(errors="ignore")
        if not re.search(rf"house-?rule\s*{num}\b|\bHR-?{num}\b", t, re.I):
            return None  # registered but does not name the rule: not credited
        try:
            return str(Path(p).relative_to(ROOT.parent))
        except ValueError:
            return str(p)

    print("\n\n== ENFORCEMENT: does a checker point at each invariant? ==\n")
    print("  linked   = a checker names the rule id")
    print("  UNLINKED = a check exists but nothing ties it to the rule (fix: add the reference)")
    print("  REMINDER = no executed check at all (fix: write one, or accept it as discipline)\n")
    print(f"  {'#':<4} {'invariant':<44} {'rung':<10} checker")
    print(f"  {'-'*4} {'-'*44} {'-'*10} {'-'*24}")

    enforcement_gaps, unlinked = [], []
    for num, title in invariants:
        t = title if len(title) <= 43 else title[:40] + "..."
        linked = linked_files(num)
        ext = explicit_file(num)
        if linked:
            rung, who = "linked", linked[0]
        elif ext:
            rung, who = "linked", ext
        else:
            kw = keyword_files(num)
            if kw:
                rung, who = "UNLINKED", kw[0]
                unlinked.append((num, title, kw[0]))
            else:
                rung, who = "REMINDER", "no executed check"
                enforcement_gaps.append((num, title))
        print(f"  {num:<4} {t:<44} {rung:<10} {who}")

    # ── 3. DOES THE EXCHANGE ACTUALLY MOVE? ───────────────────────────────────────
    # The census above is static. This is the one dynamic probe: a mechanism is only alive if
    # something produced it and something else consumed it. One-way traffic is a monologue.
    print("\n\n== EXCHANGE: is anything flowing prong to prong? ==\n")

    verdicts = [r for r in PRONGS if r.get("kind") == "verdict"]
    intents = [r for r in PRONGS if r.get("kind") == "intent"]
    drifts = [r for r in PRONGS if r.get("kind") == "drift"]

    hops = [
        ("Simba writes an IntentCard", len(intents) > 0, f"{len(intents)} card(s)"),
        ("Auditor READS it (a verdict cites one)", any(v.get("intentCardId") for v in verdicts),
         f"{len(verdicts)} verdict(s)"),
        ("Simba raises a DriftFlag", len(drifts) > 0, f"{len(drifts)} flag(s)"),
        ("Auditor RULES on it (verdict.resolves)", any(v.get("resolves") for v in verdicts),
         f"{sum(len(v.get('resolves') or []) for v in verdicts)} resolved"),
    ]
    exchange_gaps = []
    for label, ok, detail in hops:
        print(f"  {'ok  ' if ok else 'DEAD'} {label:<42} {detail}")
        if not ok:
            exchange_gaps.append(label)

    # The composer is the root-cause gate for hop 2. Prove it still refuses, here, by running it.
    # A gate believed to work is a reminder; a gate observed to fire is a gate.
    try:
        r = subprocess.run(["node", "prongs/compose-auditor.mjs", "r-no-such-run"],
                           cwd=ROOT, capture_output=True, timeout=15)
        fired = r.returncode == 2
    except Exception:
        fired = False
    print(f"  {'ok  ' if fired else 'DEAD'} compose-auditor refuses with no IntentCard   "
          f"{'exit 2' if fired else 'DID NOT FIRE'}")
    if not fired:
        exchange_gaps.append("compose-auditor no longer refuses")

    # ── 4. THE GAP LIST ───────────────────────────────────────────────────────────
    print("\n\n== GAPS ==\n")

    if transport_gaps:
        print("  TRANSPORT (produced but never consumed, or never produced):")
        for name, why in transport_gaps:
            print(f"    - {name}: {why}")
    if exchange_gaps:
        print("\n  EXCHANGE (a hop that does not move):")
        for g in exchange_gaps:
            print(f"    - {g}")
    if enforcement_gaps:
        print("\n  ENFORCEMENT (stated in house-rules, no executed check anywhere):")
        for num, title in enforcement_gaps:
            print(f"    - {num}: {title}")
    if unlinked:
        print("\n  UNLINKED (a check exists; nothing ties it to the rule. Cheapest gap to close):")
        for num, title, who in unlinked:
            print(f"    - {num}: {title}  -> {who}")

    total = len(transport_gaps) + len(enforcement_gaps) + len(exchange_gaps)
    if not total:
        print("  none open")

    print(f"\n  {len(transport_gaps)} transport | {len(exchange_gaps)} exchange | "
          f"{len(enforcement_gaps)} enforcement | {len(unlinked)} unlinked | {total} blocking")
    print(f"RESULT: {'CLEAN' if total == 0 else f'{total} GAP(S) OPEN'}")
    return 1 if (STRICT and total) else 0


def run_controls():
    """Print the liveness+consumption controls as machine-readable lines and exit nonzero if any
    fail. tests/census_durability.py invokes `census.py --controls` as a SUBPROCESS and requires
    these lines: a reverted (HEAD) census has no --controls handling, so it prints the ordinary
    census instead and the durability control finds no `CONTROL … PASS` lines — which is the
    durability signal. Ledger-independent on purpose (the controls build their own in-memory
    fixtures), so the concurrent writer cannot perturb it."""
    results = controls()
    print("== CENSUS CONTROLS ==")
    ok_all = True
    for name, ok in results:
        print(f"CONTROL {'PASS' if ok else 'FAIL'} :: {name}")
        ok_all = ok_all and bool(ok)
    print(f"RESULT: {'CONTROLS PASS' if ok_all else 'CONTROLS FAIL'}")
    return 0 if ok_all else 1


if __name__ == "__main__":
    if "--controls" in sys.argv:
        sys.exit(run_controls())
    sys.exit(main())
