---
name: task
description: Execute long-running work from a durable task file that survives context compaction. Use for any implementation expected to exceed ~30 minutes, when the user runs /task, or to resume an interrupted/compacted task. Argument - a spec path, an existing task file path, or a plain description.
---

# /task — compaction-proof execution loop

Long conversations get compacted and lose the original instructions; work then drifts or
stalls. Fix: the task lives in a **file**; the conversation is disposable. A fresh session
pointed at the task file must be able to continue seamlessly.

## Starting

Interpret the argument:
- **Existing task file** (`.claude/tasks/*.md`) → resume: read it fully, read the linked
  spec, continue from **Next step**. Do not re-plan finished work.
- **Spec path or description** → create `.claude/tasks/<slug>.md` from the template below.
  Copy acceptance criteria verbatim from the spec. If there is no spec and the work is
  non-trivial, suggest `/spec` first; if the user declines, draft acceptance criteria
  yourself and get them confirmed before starting.

### Task file template

```markdown
# Task: <title>

**Spec:** docs/specs/<file> (or "none")
**Status:** in_progress | blocked | done
**Created:** YYYY-MM-DD

## Goal
One paragraph. The WHY, not just the what — enough that a fresh session makes the same
judgment calls.

## Acceptance criteria
- [ ] Copied from the spec, verbatim. Checked off only with evidence noted inline.

## Constraints
Hard rules for this task: files not to touch, approaches ruled out and why, budget/limits.

## Plan
- [ ] Increment 1 — each increment ends in a verifiable state (test passes, page renders)
- [ ] Increment 2 ...

## Next step
> ONE line: the single next action. A post-compaction resume reads this line first.
> Keep it current at all times.

## Progress log (append-only)
- YYYY-MM-DD HH:MM — what was done, what was verified, anything surprising
```

## Execution loop

Repeat until done:

1. **Re-read the task file.** Every iteration, from disk, not from memory. This is the
   entire point of the skill — memory of the task is untrustworthy; the file is truth.
2. **Do exactly one increment** from the Plan.
3. **Verify it** — run the test, build, or check the page. An increment without
   verification doesn't count as progress.
4. **Update the file:** append a Progress log entry, update **Next step**, check off any
   acceptance criteria met (note the evidence inline, e.g. "✓ pytest 42 passed").
5. **Commit** if in a git repo — small, atomic, conventional message.

Hard rules:

- Update the file BEFORE starting any long or risky operation, so an interruption
  mid-operation still leaves an accurate resume point.
- **If you notice compaction occurred** (conversation summary appears, or earlier details
  feel missing): stop, re-read the task file AND the spec in full, then continue from
  **Next step**. Never guess at what the task was.
- **3-strikes rule:** after 3 consecutive failed attempts at the same problem, set
  Status: blocked, write what was tried and why it failed into the file, and ask the user.
  Don't spin.
- Scope discipline: if you discover adjacent problems, log them in the task file under a
  "Discovered" note (or file an issue) — don't fix them inside this task.

## Completion

1. Verify EVERY acceptance criterion, evidence noted inline next to each checkbox.
2. Set **Status: done**, final Progress log entry.
3. Report to the user: what shipped, evidence per criterion, anything discovered but not
   done. If a spec was used, update its Status to implemented.
