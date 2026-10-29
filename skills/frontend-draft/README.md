# Draft Studio

Edit a frontend visually, then let your agent implement the changes in its source.

```powershell
py -3 "$HOME/.claude/skills/frontend-draft/studio.py" C:/path/to/project
```

Open the **studio URL** printed in `STUDIO READY`.

For **React/Next/Vite**, click **Select element**, click the page, and use the text
or style controls. **Select parent** targets the containing layout. **Hide element**
previews a removal. **Undo** reverses the last preview edit. Press Escape to use the
app normally. Click **Save changes**, then tell your agent **“apply my visual changes”**.

The agent reads `.draft-studio/changes.json` inside the draft and applies your
requests to JSX/TSX and CSS. Saved requests include the route, selector, original
and desired values, and surrounding rendered context. Browser edits do not rewrite
React components automatically. HMR remains available; a rerender may reset a
temporary preview, while saved requests stay on disk.

For **static HTML**, the existing **Design mode → Save** workflow still writes the
edited HTML directly to the disposable draft.

Targets: local directory, `owner/repo`, Git URL, or `scratch`. Optional flags:
`--port`, `--name`, `--workspace`, and `--fresh` (discards the existing draft).
Original source is preserved; promote only after reviewing the result.

The server uses Python's standard library and loopback-only access for framework
editing. It proxies normal HTTP and HMR websockets without changing framework
configuration. Framework dependencies are installed with npm in the draft.

Supported visual edits: text-only elements, colors, font size/weight, spacing,
width, corner radius, text alignment, display, and hiding elements. Canvas,
cross-origin iframes, closed shadow roots, and arbitrary JSX drag-and-drop are not
supported. Strict CSP may block the injected editor. Test the actual target app
before relying on behavior beyond Next App Router or Vite React.

Files: `studio.py` starts the session; `draft_server.py` serves static drafts;
`framework_server.py` proxies framework previews and stores requests;
`framework_editor.js` provides the browser editor. See `SKILL.md` for the agent loop.

Run the server/storage regression checks with:

```text
py -3 -m unittest discover -s tests -v
```
