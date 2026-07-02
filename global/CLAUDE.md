<!-- claude-kit -->
# Global working agreement (claude-kit)

These rules apply in every project unless the project's own CLAUDE.md overrides them.

## Workflow invariants

- **Spec-first.** For any non-trivial feature or change, use the `/spec` skill (interview
  me, write acceptance criteria) before writing code. Trivial fixes and questions are exempt.
- **Durable state lives in files, not conversation.** Any work expected to exceed ~30
  minutes runs through the `/task` skill: a task file in `.claude/tasks/` holds the goal,
  acceptance criteria, next step, and progress log. Re-read it every iteration — never
  work from memory of the task. If context was compacted, re-read the task file and spec
  in full before doing anything else.
- **Done requires evidence.** A claim of completion must come with proof: test output,
  a screenshot, or command output demonstrating each acceptance criterion. "It should
  work now" is not done.
- **Gate at the spec, not the keystrokes.** Once a spec or plan is approved, execute
  autonomously — don't ask for approval at every small step. Still surface destructive,
  irreversible, or money-spending actions before taking them.
- **Blocked beats spinning.** After 3 consecutive failed attempts at the same problem,
  stop, write down what was tried in the task file, and ask me — don't burn an hour
  iterating on a dead end.

## Self-improvement

- If I correct you twice on the same thing, point it out and propose the exact line to
  add to CLAUDE.md (project or global) or the skill to update, so it never happens again.

## Communication

- Concise. Lead with the answer or the decision needed.
- During long autonomous work, the task file's **Next step** and **Progress log** are the
  status channel — keep them current so I can check progress without reading the transcript.

## Project conventions

- If the project has a `PRODUCT.md` (or `docs/PRODUCT.md`), read it before making
  product judgment calls — it defines the vision, non-goals, and quality bar.
- Specs live in `docs/specs/`, task files in `.claude/tasks/`.
