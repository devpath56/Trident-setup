# Result 02 — Trident vs bare Opus · slugify `max_words` (drift-trap task)

**Task:** add `max_words=N` to `python-slugify`, deliberately built to trip a cold agent:
an early "**don't touch `max_length`**" constraint (recency trap) + a buried **restrictive** requirement
(`max_words=0` must return `""`, the CF-019 trap that `if max_words:` gets wrong). Hidden 5-case grade. n=1.

| Layer | Arm A — bare Opus | Arm B — Trident |
|---|---|---|
| Validity gate (existing 82 tests) | ✅ 82/82 | ✅ 82/82 |
| Hidden acceptance (incl. `=0 → ""`) | ✅ 5/5 | ✅ 5/5 |
| Quality bonus (custom separator) | ✅ 1/1 | ✅ 1/1 |
| ① Corrections you'd send | 0 | 0 |
| ② Process-defect ledger | none surfaced (handled `is not None` itself) | none to catch |
| ③ Cost | 1 subagent · ~32k tok | 3 subagents · ~115k tok (~3.6×) |

**Verdict:** tie on outcome; **Arm A wins quality-per-token** again. The trap did not fool a strong Do-er
— bare Opus used `is not None` and preserved the `max_length` path unprompted.

**What Trident *did* show:** its planning step (Do-er AssumptionSet) explicitly surfaced the exact trap
pre-build — "use `is not None`, not `if max_words:`, else 0 becomes a no-op" (kill 5, unc 1) — and Simba
pinned the early "don't touch max_length" constraint as `pinned_feedback`. The harness saw the risks;
it just didn't need to *catch* anything, because the Do-er didn't slip.

## Cross-experiment conclusion (Exp-1 + Exp-2)
Two clean n=1 runs, same result: **with Opus as the Do-er, on well-specified single-shot tasks, the
harness is pure overhead (~3.6–4.5×) and changes no outcome.** The Auditor's catch-value cannot appear
when the Do-er makes no error.

**Therefore the value hypotheses these experiments do NOT test — and the next ones must:**
1. **Cost-effectiveness:** a *cheaper/weaker* Do-er (Haiku/Sonnet) + Auditor catch, vs expensive Opus
   alone. The real economic case is "cheap Do-er the harness makes reliable," not "Opus + overhead."
2. **Simba's core job:** recency-bias drift over a *long multi-turn* session — untested here, since these
   are single-shot. Simba's memory can't pay off in one turn.
3. **Genuinely ambiguous intent**, where the bare agent guesses wrong and Simba/the RAT gate force alignment.

Honest bottom line: Trident has **not** earned its cost on anything tested so far. That's a real finding,
not a failure of the experiment — it sharpens where the harness must prove itself next.
