<!-- GENERATED FILE — do not hand-edit. Rendered from failures.jsonl. -->
# Failures log (human view)

> Generated from `failures.jsonl` (or the `log failure` trigger). Hand-edits are overwritten.
> Full pattern, enterprise environments, PM implication, and trace live in each JSONL record.

## Index (56 records)

| CF | Title | Tags | Status | Detector | Guard |
|----|-------|------|--------|----------|-------|
| CF-001 | Self-violating rules in generated content | self-violation, hallucination | guarded | deterministic | Lint generated examples against the rule they illustrate in the same pass; grep the exa… |
| CF-002 | Misreading metadata as semantic signal | context-degradation | guarded | structural | Never act on a file's role from its name, timestamp, or node-count; verify semantic rol… |
| CF-003 | Pattern cargo-culting across surfaces | pattern-cargo-culting | guarded | structural | Before reusing a UI element or field at a new surface, ask what decision it enables HER… |
| CF-004 | Hallucinated plausible-sounding facts | hallucination | guarded | hybrid | Never personalize on a fact not pulled from a verified source; every cited entity needs… |
| CF-005 | Bulk refactor introduces subtle boundary brea… | bulk-refactor | guarded | deterministic | After any bulk file op (split/merge/migrate), run build+lint+smoke and check first/last… |
| CF-006 | State loss between tool calls | state-loss, tool-use | guarded | deterministic | Treat every bash call as fresh: use absolute paths or chain cd && cmd in one call. Neve… |
| CF-007 | Literal-vs-meta: answered the surface form, m… | instruction-following | guarded | structural | On ambiguous or high-stakes requests, confirm the goal before building (I read this as … |
| CF-008 | Quick-fix pattern breaks down at scale-of-cha… | pattern-cargo-culting | guarded | structural | When a workaround starts needing its own workarounds, stop and flag the regime change. … |
| CF-009 | Long-session context degradation / forgotten … | context-degradation, instruction-following | guarded | structural | Don't rely on memory for standing rules in long sessions; re-check conventions before h… |
| CF-010 | LLM-as-judge optimism bias | judge-bias | guarded | llm-judge | Never self-assess free-form; score against an explicit rubric with per-dimension scores… |
| CF-011 | Skill / instruction collision when multiple g… | instruction-following | guarded | structural | When skills or instructions overlap, pick one authoritative source per surface and stat… |
| CF-012 | Atomic-undo / mid-build pivot leaves dead code | bulk-refactor | guarded | deterministic | On feature removal, reference-count every artifact added (CSS, state, handlers, markup)… |
| CF-013 | Permission-model confusion: destructive actio… | permission-model, tool-use | guarded | deterministic | Classify each action by reversibility before acting; irreversible actions need explicit… |
| CF-014 | Brittle test selectors (false-pass / false-fa… | bulk-refactor | guarded | deterministic | Use data-testid and exact-id selectors in tests; forbid text or CSS-class matches. Asse… |
| CF-015 | Name-collision: resolved a reference to the w… | hallucination, instruction-following, context-degradation | guarded | deterministic | On any reference matching >1 candidate, rank by primacy (mounted/working-set/named-in-c… |
| CF-016 | Transient backend failure misread as tool def… | tool-use, permission-model, state-loss | guarded | deterministic | Classify tool errors transient vs persistent; bounded retry with backoff before any fal… |
| CF-017 | Context conflation / attribution error (right… | context-degradation, hallucination | guarded | structural | On vague comparators (like in X), read X or ask; never borrow an attribute from a diffe… |
| CF-018 | Training-data entity substitution | hallucination, context-degradation | guarded | deterministic | Workspace namespace beats training-data namespace for any entity in both. Read the work… |
| CF-019 | Spec-literal vs soft-substitution | instruction-following | guarded | deterministic | For restrictive quantifiers (only, none, exactly), implementation must literally satisf… |
| CF-020 | Assumed-homeless / create-before-check (separ… | context-degradation, bulk-refactor | recurred | deterministic | Gate every create behind a placement search (grep/glob candidate homes). A new file req… |
| CF-021 | Single-axis optimization that sacrifices a st… | instruction-following | recurred | structural | Enumerate all objectives, including soft ones (momentum, adoption, trust), before desig… |
| CF-022 | Format substitution: delivered a lookalike in… | instruction-following, format-substitution | recurred | structural | When a format or standard is named, produce that exact format or say up front I can't a… |
| CF-023 | Stated a durable rule only in chat, never per… | instruction-following, state-loss | recurred | deterministic | Any rule, preference, or convention the user sets gets written to the persistent layer … |
| CF-024 | Mis-homed content by name-match, not scope-ma… | context-degradation, instruction-following | recurred | structural | Before filing into an existing home, read its purpose line and confirm its scope covers… |
| CF-025 | Marked a blocked/incomplete task 'completed' … | instruction-following, state-loss | guarded | structural | Before setting any task 'completed', check the work's acceptance test (a verifiable art… |
| CF-026 | No-op on an explicit registered trigger | instruction-following, self-violation | guarded | deterministic | Normalize trigger phrases to intent before matching; never emit a non-response to a non… |
| CF-027 | Same-name package conflation: built from the … | hallucination, tool-use, context-degradation | recurred | deterministic | When a tool/package name could resolve to more than one source, verify lineage (repo UR… |
| CF-028 | No-op recurred one turn after installing its … | instruction-following, self-violation, context-degradation | recurred | deterministic | Enforce the no-op ban at emit-time, not by memory; the invariant is 'every non-empty us… |
| CF-029 | Conflated the writable store with a read-only… | context-degradation, instruction-following, tool-use | recurred | deterministic | Before claiming I can't modify any target, locate its writable instance in the mounted … |
| CF-030 | Answered a scoped question from an out-of-sco… | context-degradation, instruction-following | recurred | structural | For any scoped success/metrics/objective question, resolve the scope to its owning sour… |
| CF-031 | Tooling hardcoded a session-mount absolute pa… | state-loss, tool-use | guarded | deterministic | Tooling resolves project paths relative to __file__ (or a required env var), never a se… |
| CF-032 | Flooded a knowledge base with unvetted genera… | self-violation, instruction-following | guarded | structural | 'Help me learn' = explain in chat, not write pages. Never write learned-content to a KB… |
| CF-033 | No-op recurrence: non-response to a substanti… | self-violation, instruction-following, context-degradation | recurred | deterministic | Before emitting an empty turn, assert the user's last message is genuinely empty/non-su… |
| CF-034 | Prevention guard inert: mounted but never exe… | tool-use, state-loss, self-violation, permission-model | resolved | deterministic | A guard is real only once its execution is verified; treat any config in a mounted fold… |
| CF-035 | Reimplemented a skill method from memory afte… | context-degradation, instruction-following, tool-use, self-violation | recurred | deterministic | When a loader says 'read the SOT at X, else stop': on a failed read, translate X agains… |
| CF-036 | Verification watched the wrong probe path; fa… | tool-use, state-loss, context-degradation | guarded | deterministic | A guard's heartbeat probe and the check that reads it must name ONE agreed path. When v… |
| CF-037 | Confabulated self-process/agency narration as… | hallucination, self-violation | recurred | structural | Any claim about my own actions or cognition must cite a tool call or a conversation-tra… |
| CF-038 | Stated a consumer-relative limit as absolute | hallucination, context-degradation | recurred | structural | Capability/limit claims carry scope. A generation/reasoning trace IS standard platform … |
| CF-039 | Designed a flow on an assumed connector capab… | tool-use, permission-model, context-degradation | guarded | deterministic | Before designing any flow that depends on a connector op (update/delete/overwrite), pro… |
| CF-040 | Propagated a known-corrected attribution over… | context-degradation, hallucination, instruction-following | recurred | structural | An explicit 'prior error / corrected to X' flag in any source is authoritative and over… |
| CF-041 | Baked a host path into a script executed in t… | tool-use, context-degradation | recurred | deterministic | Any path a bash command or a bash-executed script reads or writes must be the execution… |
| CF-042 | Skipped a loaded skill's delivery-format inst… | instruction-following, context-degradation, self-violation | guarded | deterministic | Before emitting the first sentence of any taught chunk under a delivery-format constrai… |
| CF-043 | Used undefined tool-specific styling tokens; … | tool-use, hallucination | guarded | deterministic | Before first use of any tool-specific styling/API surface, read that tool's own referen… |
| CF-044 | Built enforcement on an unverified platform c… | tool-use, permission-model, state-loss | guarded | structural | Before building automation that depends on a host runtime feature, confirm platform sup… |
| CF-045 | Standing global tone instruction never gated;… | instruction-following, self-violation, context-degradation | guarded | deterministic | Standing user-level tone/format rules need the same pre-emission check as skill-scoped … |
| CF-046 | Narrated a write action that was never execut… | self-violation, hallucination, state-loss, instruction-following | guarded | deterministic | A sentence claiming a write action ('Logging X', 'Adding Y') must be followed in the sa… |
| CF-047 | Asserted removal complete while flagged conte… | self-violation, context-degradation, instruction-following | recurred | deterministic | A removal instruction is set-scoped: grep the removed entity (and aliases) across every… |
| CF-048 | Padded a deliverable with an unrequested axis | pattern-cargo-culting, instruction-following | recurred | structural | Before adding any mapping, tag, or axis to a generated deliverable, name in one line th… |
| CF-049 | Compiled a briefing as the wrong persona/genr… | pattern-cargo-culting, instruction-following, context-degradation | guarded | hybrid | When simplifying role/persona-defining prose, re-derive from the canon Persona/Intent l… |
| CF-050 | No-op: session ended on a non-empty redirect … | self-violation, instruction-following, context-degradation | recurred | deterministic | Emit-time: a non-empty last user message never gets an empty turn; a revision of a just… |
| CF-051 | Reached for a non-deterministic guard when a … | judge-bias, pattern-cargo-culting | guarded | structural | Always prefer the deterministic option for the PRIMARY fix. Reliability order: determin… |
| CF-052 | Presented a synthesized paraphrase as a verba… | hallucination, instruction-following | guarded | hybrid | Quotation marks + attribution => text copied VERBATIM; if summarizing, drop the quote m… |
| CF-053 | Executed setup when asked to be walked throug… | instruction-following, permission-model, context-degradation | recurred | structural | On 'understand/explain/walk me through/step by step', mode=EXPLAIN: deliver the per-ste… |
| CF-054 | Answered a project-defined term with the gene… | context-degradation, instruction-following | guarded | structural | Before resolving a project-ambiguous term, check whether loaded project context defines… |
| CF-055 | Shipped a platform-native bundle for an unkno… | tool-use, context-degradation | guarded | structural | For deliverables bound to external/unknown environments ('for my friend', 'portable'), … |
| CF-056 | Started a build before testing the riskiest (… | tool-use, pattern-cargo-culting, permission-model | guarded | structural | Before any build, the Auditor names the single riskiest assumption (kill-power x uncert… |
