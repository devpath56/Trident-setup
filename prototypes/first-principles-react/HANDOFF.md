# Session handoff: test the Agentation hands-free autofetch loop

**Goal:** prove that a LOCAL Claude Code, with `agentation-mcp`, auto-fetches your visual annotations from
the running app and applies them to the exact source, with no copy-paste and no remote session in the loop.

Paste this whole file into a fresh **local** Claude Code session (or just open the repo there and point it
at this file).

## What you're testing
- **Repo:** `devpath56/trident-setup` (branch `main`, canonical) or `devpath56/learn-verify-kit`
  (branch `claude/trident-repo-setup-4pz0jt`).
- **Path:** `prototypes/first-principles-react/`
- **What it is:** a Vite + React app with `<Agentation />` mounted and a stable `id` + `data-anchor` on
  every element, so an annotation's selector maps 1:1 to a source block.

## Prerequisites
- Node 18+ and npm
- **Claude Code installed locally** (desktop/CLI, not the web session)
- A Chromium or Firefox browser

## Setup (once)
1. Get the code:
   ```
   git clone https://github.com/devpath56/trident-setup
   cd trident-setup/prototypes/first-principles-react
   ```
   (existing clone: `git pull` instead)
2. `npm install`
3. Wire the MCP server. **Confirm the exact command at https://www.agentation.com/mcp first** (do not
   trust a guessed one), then add to `~/.claude/settings.json`:
   ```json
   { "mcpServers": { "agentation": { "command": "npx", "args": ["agentation-mcp", "server"] } } }
   ```
   Or just run the **`/agentation`** skill in Claude Code, which wires this for you.
4. Start the app: `npm run dev` -> http://localhost:5173
5. Open Claude Code **in this folder**. Verify the server is live: run `/mcp` (or `claude mcp list`);
   `agentation` should show connected. Restart Claude Code if you edited settings.json after launch.

## Kick off the hands-free loop
In the local Claude Code, send:

> Watch Agentation annotations and apply each one to this repo. For each: use its selector/anchor to
> locate the source (ids like `#d-optimism-lies` map to `src/data.js` / `src/App.jsx`), make the change,
> then mark it resolved. Keep watching for the next one.

That calls `watch_annotations`, which blocks until you annotate.

## The test (pre-registered PASS criteria, fail-closed)
1. In the browser, open the Agentation toolbar and click the **Simba** card (the one showing
   `loyal to: you`).
2. Annotation: *change "loyal to: you" to "answers only to you".*
3. **Do NOT paste anything into Claude.** Wait.

PASS only if ALL hold:
- [ ] the local agent fetched the annotation on its own (no paste)
- [ ] it edited `src/data.js` -> `PRONGS[1].loyal` (the correct field, via the `#p-simba` anchor), not a guess elsewhere
- [ ] the browser hot-reloaded and the card now reads `answers only to you`
- [ ] the annotation shows resolved/acknowledged in Agentation

All four green = the hands-free autofetch loop works. Any miss = FAIL; note which box and see Troubleshooting.

## Anchor map (selector -> source, so the agent lands precisely)
- `#hero` -> `App.jsx` header
- `#d-<slug>` (e.g. `#d-optimism-lies`) -> `data.js` `DERIV[i]` + its `App.jsx` card
- `#p-simba` / `#p-do-er-opus` / `#p-auditor-fable` -> `data.js` `PRONGS[i]`
- `#s-<slug>` (e.g. `#s-compaction`) -> `data.js` `STEPS[i]`
- `#shaft`, `#oneline`, `#h-argument` / `#h-prongs` / `#h-walkthrough` -> `App.jsx` static blocks

## Troubleshooting
- **Agent sees no annotations** -> MCP not connected: run `/mcp`; restart Claude Code after editing
  settings.json; re-confirm the exact `npx` command on agentation.com/mcp.
- **No toolbar in the browser** -> confirm `<Agentation />` is mounted (`src/App.jsx`) and `npm run dev`
  is serving 5173.
- **Agent edits the wrong place** -> feed it the anchor map above; the `id` is ground truth.
- **Install/version error** -> bump `agentation` in `package.json` to the latest major and re-install.
- **Loop stalls** -> the copy-paste fallback still works: annotate, copy for agent, paste into Claude.

## Honest caveats (do not skip)
- Autofetch needs the widget, the MCP server, and Claude Code on the **same machine**. A remote/web
  Claude cannot reach it. This is a local-only test.
- The remote session that built this did **not** run `npm install` or verify the exact MCP command;
  verify both locally before trusting them.
- The static no-build page `../trident-first-principles.html` is the copy-paste fallback if the loop fails.

## Report back
Paste the result (the 4 checkboxes + any error output) into your next message to the remote session.
It gets folded into `method.md`: a feedback loop is only "real" once its check has actually run (CF-034).
