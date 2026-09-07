#!/usr/bin/env bash
# Deploy the semantic-twins skill and agent into ~/.claude.
# The repo stays the source of truth in both modes.
set -euo pipefail

: "${HOME:?HOME must be set and non-empty}"

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILL_DEST="$HOME/.claude/skills/semantic-twins"
AGENT_DEST="$HOME/.claude/agents/semantic-twin-hunter.md"
DEFAULT_MODE=symlink

usage() {
    echo "usage: install.sh [--mode symlink|copy] [--check]" >&2
    exit 2
}

mode="$DEFAULT_MODE"
check_only=0
while [ $# -gt 0 ]; do
    case "$1" in
        --mode) mode="${2:-}"; shift 2 ;;
        --check) check_only=1; shift ;;
        *) usage ;;
    esac
done

if [ "$mode" != symlink ] && [ "$mode" != copy ]; then
    usage
fi

if [ "$check_only" -eq 1 ]; then
    if [ ! -e "$SKILL_DEST" ] && [ ! -e "$AGENT_DEST" ]; then
        echo "not installed" >&2
        exit 1
    fi

    status=0

    # Each destination is judged on its own. A symlink cannot drift; a copy can.
    # Judging them together lets a symlinked skill vouch for a stale agent copy.
    if [ -L "$SKILL_DEST" ]; then
        echo "skill: symlink, cannot drift"
    elif diff -rq "$REPO/SKILL.md" "$SKILL_DEST/SKILL.md" >/dev/null 2>&1; then
        echo "skill: copy in sync"
    else
        echo "drift: SKILL.md differs from the deployed copy" >&2
        status=1
    fi

    if [ -L "$AGENT_DEST" ]; then
        echo "agent: symlink, cannot drift"
    elif diff -q "$REPO/agents/semantic-twin-hunter.md" "$AGENT_DEST" >/dev/null 2>&1; then
        echo "agent: copy in sync"
    else
        echo "drift: semantic-twin-hunter.md differs from the deployed copy" >&2
        status=1
    fi

    exit "$status"
fi

mkdir -p "$HOME/.claude/skills" "$HOME/.claude/agents"
rm -rf "$SKILL_DEST" "$AGENT_DEST"

if [ "$mode" = symlink ]; then
    ln -sfn "$REPO" "$SKILL_DEST"
    ln -sfn "$REPO/agents/semantic-twin-hunter.md" "$AGENT_DEST"
else
    mkdir -p "$SKILL_DEST"
    cp "$REPO/SKILL.md" "$SKILL_DEST/SKILL.md"
    cp -R "$REPO/references" "$SKILL_DEST/references"
    cp -R "$REPO/scripts" "$SKILL_DEST/scripts"
    cp "$REPO/agents/semantic-twin-hunter.md" "$AGENT_DEST"
fi

echo "installed in $mode mode"
echo "restart Claude Code, then run /semantic-twins"
