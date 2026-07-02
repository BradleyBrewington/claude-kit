---
name: spec
description: Interview the user about a feature or product idea, then write a spec with verifiable acceptance criteria. Use before implementing any non-trivial feature, when the user runs /spec, or when they describe something they want built that would take more than ~30 minutes.
---

# /spec — turn a fuzzy idea into an approved, verifiable spec

Purpose: close the gap between what the user imagines, what they say, and what gets
built. The user should NOT have to fully articulate the idea up front — your job is to
extract it by interviewing, then write it down so precisely that implementation needs no
further product decisions.

The argument (if any) is the feature idea, e.g. `/spec dark mode toggle`.

## Process

### 1. Gather context BEFORE asking anything

- Read `PRODUCT.md` or `docs/PRODUCT.md` if it exists — vision, users, non-goals, quality bar.
- Skim the parts of the codebase the feature would touch, so your questions are informed
  and specific, not generic.
- Check `docs/specs/` for related or superseded specs.

### 2. Interview the user

Use the AskUserQuestion tool. 2-4 questions per round, at most 3 rounds — this is an
interview, not an interrogation. Cover whichever of these actually matter for the idea:

- **Behavior:** what does the user see and do, step by step? What's the happy path?
- **Edge cases:** propose 2-3 concrete edge cases and ask how each should behave.
- **Scope boundary:** propose things that could plausibly be included and ask which are
  explicitly OUT (out-of-scope lists prevent both gold-plating and disappointment).
- **Data/state:** what persists, where, what migrates?
- **Quality bar:** prototype-rough or production-polished? Performance/a11y expectations?
- **Success:** how will the user check this works — what would they click/run first?

Rules:
- Only ask questions whose answers would change what you build. If the codebase or
  PRODUCT.md already answers it, don't ask.
- Prefer concrete options with trade-offs over open-ended questions ("A: modal, B: inline
  panel — B is less code but crowds the page") — options are faster to answer and expose
  your assumptions so the user can veto them.
- State the assumptions you're making and let the user correct them.

### 3. Write the spec

Write to `docs/specs/YYYY-MM-DD-<slug>.md` (create the directory if needed):

```markdown
# Spec: <title>

**Date:** YYYY-MM-DD
**Status:** draft | approved | implemented

## Summary
2-3 sentences: what this is and why it's worth building.

## User experience
A concrete walkthrough of the happy path, written as what the user sees and does.
Include edge-case behavior decided in the interview.

## Acceptance criteria
- [ ] Each criterion independently verifiable by a test, command, or screenshot
- [ ] Written so a fresh session with no other context could check it
- [ ] Includes the edge cases, not just the happy path

## Out of scope
- Explicitly excluded items from the interview. This section is load-bearing.

## Technical notes
Constraints, affected files/modules, data changes. Brief — this is a spec, not a plan.

## Open questions
Anything unresolved, marked with who needs to answer it.
```

Acceptance criteria are the most important section. Bad: "dark mode works." Good: "toggling
dark mode in settings persists across reload; all pages listed in journeys render without
white-flash; toggle is keyboard accessible."

### 4. Review loop

Present the spec file path and a compressed summary. Ask the user to read the actual file
and correct it. Iterate until they approve, then set **Status: approved**.

### 5. Hand off — do NOT implement

Implementation is a separate step with its own skill. End with:

> Spec approved: `docs/specs/<file>`. Run `/task docs/specs/<file>` (here or in a fresh
> session) to execute it.
