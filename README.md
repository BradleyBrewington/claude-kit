# claude-kit

A personal, project-agnostic Claude Code workflow toolkit. Install once, and every
project you open a terminal in has the same spec-first, compaction-proof,
evidence-driven workflow.

## Why

Three failure modes this kit exists to kill:

1. **Compaction amnesia** — tasks longer than ~1 hour lose the original prompt when
   the conversation gets compacted, and iteration stalls. Fix: the task lives in a
   file (`/task`), the conversation is disposable.
2. **Vision → prompt → implementation drift** — you compress an idea into one prompt,
   Claude fills the gaps with guesses. Fix: Claude interviews *you* and writes a spec
   with acceptance criteria (`/spec`); you correct a one-page doc, not a diff.
3. **Micromanagement** — without written acceptance criteria and an evidence contract,
   you have to watch the process. Fix: gate at the spec, review outcomes.

## Structure

```
claude-kit/
├── install.sh          # copies everything into ~/.claude (idempotent, re-runnable)
├── global/
│   └── CLAUDE.md       # → ~/.claude/CLAUDE.md — personal invariants, loaded in every session
└── skills/
    ├── spec/           # /spec — interview → spec with acceptance criteria
    └── task/           # /task — durable task file + compaction-proof execution loop
```

## Install

```bash
bash install.sh
```

Re-run any time you edit the kit. Existing `~/.claude/CLAUDE.md` content is backed up
to `~/.claude/backups/` before being replaced (unless it's already the kit's file).

## Usage

Day-to-day loop in any project:

```
/spec dark mode toggle          # Claude interviews you, writes docs/specs/<date>-dark-mode.md
# ...you read the spec, fix what it got wrong, approve...
/task docs/specs/2026-07-02-dark-mode.md    # creates .claude/tasks/dark-mode.md, executes in a loop
# ...walk away; check the task file's Progress log / Next step from anywhere...
```

To resume an interrupted or compacted task (same session or a fresh one):

```
/task .claude/tasks/dark-mode.md
```

## Roadmap

- **Phase 1 (this):** `/spec`, `/task`, global CLAUDE.md, installer
- **Phase 2:** `/new-project` (interview → PRODUCT.md → scaffold → gh repo), `/ship`, `/review` (fresh-context PR review)
- **Phase 3:** `/qa-journey` (project-agnostic polish loop driven by a per-project `docs/journeys.md` manifest), enforcement hooks in settings.json, PR evidence template
- **Phase 4:** scheduled agents (nightly QA, CI-side review via GitHub Actions)

## Design rules

- **CLAUDE.md files hold invariants and pointers; skills hold procedures.** Keep the
  global file under ~40 lines and any project CLAUDE.md under ~60.
- **Anything that must survive an hour lives in a file, not in context.**
- **If you correct Claude twice on the same thing, it becomes a line in CLAUDE.md, a
  skill, or a hook.**
