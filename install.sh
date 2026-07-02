#!/usr/bin/env bash
# claude-kit installer — copies skills and global CLAUDE.md into ~/.claude.
# Idempotent: re-run after any edit to the kit.
set -euo pipefail

KIT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="${CLAUDE_DIR:-$HOME/.claude}"
MARKER="<!-- claude-kit -->"

mkdir -p "$CLAUDE_DIR/skills"

# --- skills ---
for skill in "$KIT_DIR"/skills/*/; do
  name="$(basename "$skill")"
  mkdir -p "$CLAUDE_DIR/skills/$name"
  cp -r "$skill". "$CLAUDE_DIR/skills/$name/"
  echo "installed skill: /$name"
done

# --- global CLAUDE.md ---
target="$CLAUDE_DIR/CLAUDE.md"
if [ -f "$target" ] && ! grep -q "$MARKER" "$target" \
   && [ "$(grep -cv '^[[:space:]]*$' "$target" || true)" -gt 0 ]; then
  mkdir -p "$CLAUDE_DIR/backups"
  backup="$CLAUDE_DIR/backups/CLAUDE.md.$(date +%Y%m%d-%H%M%S).bak"
  cp "$target" "$backup"
  echo "backed up existing global CLAUDE.md -> $backup"
fi
cp "$KIT_DIR/global/CLAUDE.md" "$target"
echo "installed global CLAUDE.md"

echo "done. restart Claude Code sessions to pick up new skills."
