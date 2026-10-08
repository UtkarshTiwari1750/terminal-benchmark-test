#!/usr/bin/env bash
# Install the Task QA Runbook v2 skill files for this repository (runbook step 1 + step 2).
#
#   bash qa/install_skill.sh            # run from the repository root
#
# Copies the five appendix files into ~/.claude/skills/task-quality-qa, fills in the
# Configuration paths, and also registers the post-rollout skill under its own name so
# "run task-quality-postrun ..." resolves in Claude Code. Start a new Claude Code
# session afterwards.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILL_DIR="${HOME}/.claude/skills/task-quality-qa"
POST_DIR="${HOME}/.claude/skills/task-quality-postrun"

mkdir -p "$SKILL_DIR" "$POST_DIR"
cp "$REPO/qa/skill/eval_guide.md" "$REPO/qa/skill/dq_audit.py" "$REPO/qa/skill/dq_post.py" "$SKILL_DIR/"
for f in SKILL.md POST_ROLLOUT_SKILL.md; do
  sed -e "s|__REPO__|$REPO|g" -e "s|__SKILL_DIR__|$SKILL_DIR|g" "$REPO/qa/skill/$f" > "$SKILL_DIR/$f"
done
cp "$SKILL_DIR/POST_ROLLOUT_SKILL.md" "$POST_DIR/SKILL.md"
chmod +x "$SKILL_DIR/dq_audit.py" "$SKILL_DIR/dq_post.py"

python3 -c "import ast,sys; [ast.parse(open(p).read()) for p in sys.argv[1:]]" "$SKILL_DIR/dq_audit.py" "$SKILL_DIR/dq_post.py"
echo "Installed to $SKILL_DIR (and $POST_DIR)"
echo "DATA_DIR = $REPO"
echo "Next: start a new Claude Code session in $REPO and say:"
echo "  run task-quality-preflight on $REPO"
