# Install Trident

Trident is a pure skill bundle — no build, no dependencies, no hooks. Install = make the
`.claude/skills/` tree visible to your Claude surface.

## Claude Code (CLI / VS Code) — global skill
Clone the repo and point Claude Code at its skills, or copy the bundle into your user skills dir:

```bash
git clone https://github.com/devpath56/trident-setup.git
# then either work inside the repo, or install globally:
cp -R trident-setup/.claude/skills/{trident,auditor,simba,references} ~/.claude/skills/
```

Invoke with: **"run trident"**, **"audit this work"**, **"watch my intent on this"**, or the
always-on **"log failure"** trigger. In VS Code, the Claude Code extension picks up
`~/.claude/skills/` the same way.

## Surface: Claude Code / VS Code only
Trident's orchestration spawns real **subagents** (Do-er, a Fable Auditor, Simba), so it targets
Claude Code / VS Code where subagents exist — not claude.ai / Cowork. Install stays trivial (a skills
tree, no build, no deps); it's the runtime that needs subagents.

## The failures log — one SSOT across sessions
`log failure` (and variants: "log fail", "log this failure", "record failure") appends the next
`CF-###` to **`failures/failures.jsonl` in this repo** and commits + pushes it. For that to work in a
session, **this repo must be in the session's scope** (add it if not). Every session then writes to
the same canonical file.

In a Claude Code / VS Code session with this repo in scope: `log failure` appends the next `CF-###`,
the Auditor approves it, and it's committed + pushed to the SSOT git file.

Personal specifics never enter the committed record — they go to `failures.local.jsonl` (gitignored).

## Verify the install
Ask: **"run trident on <some work>"** — you should see the loop (Simba IntentCard → Do-er → Auditor
Verdict) reference the failures-log detectors. Ask **"log failure"** on a real mistake — you should
get back `logged CF-### (<title>)`.
