---
name: frontend-draft
description: Start a shared editable frontend draft for a local site, GitHub repo, or new page. The user edits the rendered UI; the agent applies the intent to source. Supports static HTML and React/Next/Vite previews, visual text/style edits, saved change requests, and live reload. Use for draft studio or direct visual site-editing requests.
---

# Frontend Draft Studio

The user changes the preview directly instead of describing every change. Work in
the disposable draft; the real project remains untouched until promotion.

The self-contained tool lives beside this file: `studio.py`, `draft_server.py`,
`framework_server.py`, and `framework_editor.js`. Use Python 3 (`py -3` on Windows),
plus Git and, for framework apps, Node/npm. Remote repositories use `gh` or Git.

## Start

Run in the background; it blocks while serving:

```text
py -3 <skill-dir>/studio.py <TARGET> [--port N] [--workspace DIR] [--name NAME]
```

TARGET is a local path, `.`, `owner/repo`, a Git URL, or `scratch`. Read the printed
`STUDIO READY` block and give the user its **open** URL. Keep its **draft** path.
Framework mode uses a separate backend port; open the studio URL, not the backend.

Existing drafts persist. `--fresh` discards that draft and builds from source again;
do not use it when edits need preserving. Choose the project's artifacts/workspace
folder for generated work when local workspace instructions specify one.

## Modes

- **Static/scratch:** Design mode edits the rendered HTML. Save writes HTML to
  the draft. Read `git diff` for the user's intent, then finish the implementation.
- **Framework (React/Next/Vite):** Select element, edit text or styles, or hide an
  element. Save changes writes `.draft-studio/changes.json` in the draft. JSX/TSX
  is not overwritten with rendered DOM. File edits and normal HMR still work.

The framework editor supports text-only elements, colors, font size/weight,
spacing, width, corner radius, text alignment, display, and hiding an element.
Select parent targets a container. Escape exits selection so links/buttons work
normally. Text inside nested markup must be selected at its text-only child.
Preview edits can be reset by app rerenders; saved requests remain on disk.

## Apply the user's edits

1. Read `.draft-studio/changes.json` if present, **including untracked files**,
   then `git diff` and `git status`. The saved requests are the instruction; don't
   ask the user to describe the same edits again. Record the batch revision.
2. Each request contains route, DOM selector, element tag, before/after, style
   property when relevant, and rendered context. Locate the actual component,
   data, or CSS using that context. Selectors identify the preview, not necessarily
   a one-to-one JSX node. Check shared components and repeated list items before
   deciding whether a change should affect one instance or all instances.
3. Implement in the draft's real source. Preserve React state, event handlers,
   server/client boundaries, and the existing styling system. A hide request is
   intent to remove/hide that UI, not permission to delete unrelated functionality.
   Do not copy the editor host, scripts, or temporary inline previews into source.
4. Run relevant checks. After implementing the recorded batch, acknowledge exactly
   its revision:
   ```text
   py -3 <skill-dir>/framework_server.py --dir <draft> --ack <REVISION>
   ```
   If newer edits arrived, acknowledgment fails: re-read the file and reconcile
   rather than clearing the user's new work. Refresh the preview after a successful
   acknowledgment and verify the actual source result, so temporary DOM previews
   cannot hide implementation bugs. Commit the draft changes.
5. Briefly report what changed and hand the draft back. This is a turn-based agent
   workflow, not an autonomous watcher: the user says “apply my visual changes”.

## Limits and promotion

Next App Router and Vite React are exercised by the validation workflow.
Other dev servers may work but are not guaranteed. Canvas, cross-origin iframes,
closed shadow roots, and arbitrary drag-and-drop JSX restructuring are unsupported.
Strict CSP can block editor injection; report that rather than weakening the app's
policy. Styling is a visual request; the agent must decide the appropriate source edit.

Only edit the draft during a session. Promote changed source files to the original
project when the user requests/approves promotion; exclude `.draft-studio/`, build
artifacts, and tooling. Follow the project's normal commit/PR/deployment process.
Ctrl+C stops the studio and its dev-server child tree. If force-terminating a
background launcher, terminate its child tree too. Saved drafts persist.
