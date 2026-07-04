# Spec: Delegation mode — judgment charter + triage rule

**Date:** 2026-07-04
**Status:** approved

## Summary

claude-kit Phase 1 only supports "rigor mode" (`/spec` → `/task`). This adds a
first-class **delegation mode** — vague to-dos handled with a hired-SWE's judgment —
plus a triage rule deciding which mode each ask gets. Grounded in research on how top
practitioners work (Cherny, Ronacher, Steinberger, Willison, Huntley, Klaassen): gate
at plan + review, never keystrokes; autonomy is earned by **verifiability**.

## User experience

1. User gives a vague ask ("make the error messages friendlier").
2. Claude triages by **blast radius × verifiability** and states the mode in one line:
   "Treating this as delegation — small blast radius, tests cover it." User can veto
   in either direction.
3. **Delegation:** Claude works autonomously with standing professional defaults
   (security, perf, tests, maintainability) applied without being asked. Ends with a
   PR-style summary: what changed, why, judgment calls made, risks flagged, how verified.
4. **Rigor:** wide blast radius / hard to verify / irreversible / auth-payments-data-money
   → routed through the existing `/spec` interview, then `/task`.
5. After non-trivial work in either mode, Claude proposes 0–2 one-line CLAUDE.md/skill
   additions learned from the task (compounding); user approves/rejects in one line.

Edge cases decided:
- User vetoes rigor → drop to delegation, but the judgment charter still applies
  (violations still get flagged; only the interview is skipped).
- Charter conflicts with speed ("just hack it in") → shortcut is fine but must be
  flagged in the summary, never silent.

## Acceptance criteria

- [ ] `~/.claude/CLAUDE.md` (deployed via `install.sh`) contains: the triage rule, the
      judgment charter with all 4 defaults, the delegation reporting format, and the
      compounding rule — and stays ≤ ~60 lines.
- [ ] A vague ask in a fresh session gets a one-line mode declaration before work starts.
- [ ] Delegation-mode completion ends with a PR-style summary including judgment calls.
- [ ] README documents both modes; roadmap shows Phase 1.5.
- [ ] `diff ~/.claude/CLAUDE.md global/CLAUDE.md` is empty after install.

## Out of scope

- No new skill (`/delegate`) — the charter lives in global CLAUDE.md.
- No enforcement hooks (Phase 3).
- No sandbox / `--dangerously-skip-permissions` posture change.
- No changes to `/spec` or `/task` skills.

## Technical notes

Files: `global/CLAUDE.md` (core change), `README.md` (Two modes section + roadmap),
deployed by existing `install.sh`. Keep CLAUDE.md lean — research consensus is that
bloated instruction files get ignored.

## Open questions

- `~/.claude/settings.json` already allows `Bash(*)` — broader than the intended
  Cherny-style safe list. User to decide: keep as-is or tighten. (Flagged at
  implementation time.)
