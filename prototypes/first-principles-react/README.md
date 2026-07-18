# Trident first-principles: Agentation feedback loop (React + Vite)

The first-principles explainer, wired for **Agentation** so a local Claude Code auto-fetches your visual
annotations instead of you pasting markdown.

## The two packages (this is the crux)
- **`agentation`**: the in-page toolbar (a React component, `<Agentation />`, already mounted in `App.jsx`).
- **`agentation-mcp`**: the MCP server that lets Claude Code **auto-fetch** annotations. This is the piece
  that removes copy-paste. It is not a page dependency; it runs via `npx`.

## Setup (autofetch, hands-free)
Fastest path in Claude Code: run the **`/agentation`** skill: it installs the widget, wires it in, and
recommends the MCP setup. Or do it manually:

1. Install and run locally:
   ```
   npm install
   npm run dev            # http://localhost:5173
   ```
2. Add the MCP server to `~/.claude/settings.json`:
   ```json
   { "mcpServers": { "agentation": { "command": "npx", "args": ["agentation-mcp", "server"] } } }
   ```
   (Confirm the exact invocation on https://www.agentation.com/mcp; do not guess it.)
3. Open the app, click any element with the toolbar, write a note.
4. In your local Claude Code, the loop is hands-free:
   ```
   watch_annotations()  → blocks until you annotate
      → Claude reads the batch (selector + note + computed styles)
      → edits the code, marks each in-progress, then resolved
      → loops back to watch_annotations()
   ```

## Why the round-trip is tight
Every element carries a stable `id` + `data-anchor` (see `src/App.jsx`): `#d-optimism-lies`
(`DERIV[2]`), `#p-simba`, `#s-compaction`, `#hero`, `#shaft`, `#oneline`. Agentation captures the
selector, so Claude greps straight to the exact source block. No guessing which of six cards you meant.

## Where the content lives
`src/data.js` holds the copy (DERIV / PRONGS / STEPS); `src/App.jsx` renders it; `src/styles.css` is the
design (taste-skill: single accent, no em-dashes, theme-aware). Edit `data.js` to change wording.

## Notes
- Autofetch requires the widget, the MCP server, and Claude Code on the **same machine** (the MCP server
  reads a local annotation store). A remote/web Claude session can't reach it; run this loop locally.
- Versions in `package.json` are caret ranges; bump `agentation` if a newer major ships.
- The static, no-build version of this page is `../trident-first-principles.html` (browser-extension /
  copy-paste loop, no npm).
