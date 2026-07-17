# Result 04 — Loophack, people-first (the shippable event output)

**Event:** Loop Engineering Hackathon (tokens&), Fri Jul 17, SF, one ~8hr day.
Theme: self-directing agent loops (plan→act→observe→self-correct).
**Run by:** Trident (Arm B) — Do-er (Opus) generates, Simba pins intent, Fable Auditor re-scores independently.
**Rubric (people-first):** anchor-fit 0.35 · skill-match 0.30 · feasibility 0.20 · sponsor 0.15.
**Data provenance:** event = uploaded Luma PDF (verified). Anchors = Phase-1 research; items marked
`unverified-fetch` came from search snippets because first-party pages were egress-blocked. No invented facts.

## 🏆 Winner — ZeroTrustMCP (audited 82.2)
An MCP server forked from **Nick Taylor's `mcp-typescript-template`** where every agent tool call is gated
by **Pomerium** OAuth + Zero Trust; the plan→act loop can only invoke authorized tools and **self-corrects
when denied**.

### Build plan (sponsor → feature → resume skill)
| Sponsor tool | Feature it powers | Resume skill hardened |
|---|---|---|
| **Pomerium** (load-bearing; Nick's employer) | policy-gates every MCP tool call; the *deny* signal drives the self-correct step | AI-agents · **reliability** |
| **AWS Bedrock** | hosts the agent + models running the loop | AI-agents |
| *(the loop itself)* | logs + scores every tool call (authz decision, latency, error) | **observability · evals** |

### Anchor → referral path (the actual point of attending)
Built on **Nick Taylor's own template** and *is* the thesis of his talk *"Agentic Access: OAuth gets you
in, Zero Trust keeps you safe."* Nick is a **judge**, a **developer advocate** (paid to engage — the most
reachable of the 11 judges), and **Pomerium is his employer**. Demoing this = showing *his template + his
company's product, leveled up* → highest-probability feedback + a warm referral.

## Scorecard ② (people-first, audited)
| # | Idea | Anchor person | anchor·skill·feas·sponsor | Total |
|---|---|---|---|---|
| 1 | **ZeroTrustMCP** | Nick Taylor (Pomerium) | 90·75·72·92 | **82.2** |
| 2 | codeConvo Loop | Alessandro Amenta (host) | 84·92·62·70 | 79.9 |
| 3 | BenchFirst | Keir Lewis (judge) | 88·88·68·52 | 78.6 |
| 4 | ThresholdRAG | Amey Desai (Nexla) | 65·92·60·88 | 75.6 |
| 5 | ScopeShrink | Nick Taylor | 60·74·52·90 | 67.1 |
| 6 | TokenBurn | Greg Osuri (Akash) | 62·60·62·88 | 65.3 |
| 7 | RateIn Recon | Alessandro Amenta | 72·78·52·40 | 65.0 |
| 8 | HarnessGen | Keir Lewis | 58·85·50·48 | 63.0 |

## Roads-not-taken (why the top contenders lost)
- **codeConvo Loop (2nd):** strong anchor + skill, but a 2023 OpenAI/Weaviate/LangChain stack (dependency
  rot) and Nexla isn't Alessandro's company (no double-win). Best *fallback* if you want a host anchor.
- **BenchFirst (3rd):** Keir's exact thesis + domain, but Lighthouse determinism is noisy in 8hr and
  Metaview isn't load-bearing.
- **ThresholdRAG:** anchor gutted 91→65 — the "his thresholds" were unverifiable Ragas defaults (failed closed, CF-004).
- **ScopeShrink / HarnessGen:** built "a step past" the anchor's literal work → anchor-fit deflated.
- **TokenBurn / RateIn:** decade-old generic libs (near name-drop) / deprecated Assistants v1 + mock-degradable sponsor.

## Honesty notes
- **Ceiling ~82, not ≥85.** Under independent auditing nothing crossed 85 (the sponsor-first run capped ~78
  too) — the auditor won't let anchor + sponsor + feasibility all inflate at once. Stopped here rather than
  chase 85, because chasing it just invites the re-inflation the harness exists to prevent.
- **Grey-cases respected:** the event listed no prize tracks / formal judging criteria → none invented.
- **Affinity:** no IIT/Berkeley/Indian judge tie found; if referrals via shared network are the priority,
  widen the anchor scan to attendees (out of scope here per your "judges only" call).
