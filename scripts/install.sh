#!/usr/bin/env bash
# Deploy the semantic-twins skill and agent into ~/.claude.
# The repo stays the source of truth in both modes.
set -euo pipefail
shopt -s nullglob

: "${HOME:?HOME must be set and non-empty}"

REPO="$(cd -P "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
SKILL_DEST="$HOME/.claude/skills/semantic-twins"
AGENT_DEST="$HOME/.claude/agents/semantic-twin-hunter.md"
DEFAULT_MODE=symlink
# The single source of truth for what copy mode deploys under scripts/.
# Both the copy step and the --check comparison read this list, so there is
# only ever one place that says what belongs there.
DEPLOYED_SCRIPTS=(inventory.py)

usage() {
    echo "usage: install.sh [--mode symlink|copy] [--check]" >&2
    exit 2
}

# A wrong REPO must never reach rm -rf. The deployed copy
# (~/.claude/skills/semantic-twins/scripts/install.sh) is the most natural
# place a user finds this script; without physical resolution above, running
# it from there would make REPO the symlink itself, so `rm -rf "$SKILL_DEST"`
# deletes the deployment and `ln -sfn "$REPO" "$SKILL_DEST"` recreates it as a
# dead, self-referential link -- silently, with exit 0. `cd -P` already
# defeats that for a symlinked deployment by resolving through it to the real
# repository; this guard is the categorical backstop for any other way REPO
# could end up inside the deployed tree.
home_real="$(cd -P "$HOME" 2>/dev/null && pwd -P)" || home_real="$HOME"
case "$REPO" in
    "$home_real/.claude" | "$home_real/.claude"/*)
        echo "install.sh must be run from the repository checkout, not from a deployed copy under $home_real/.claude ($REPO)" >&2
        exit 1
        ;;
esac

mode="$DEFAULT_MODE"
mode_given=0
check_only=0
while [ $# -gt 0 ]; do
    case "$1" in
        --mode) [ $# -ge 2 ] || usage; mode="$2"; mode_given=1; shift 2 ;;
        --check) check_only=1; shift ;;
        *) usage ;;
    esac
done

if [ "$mode" != symlink ] && [ "$mode" != copy ]; then
    usage
fi

resolve_file_symlink() {
    # Physically resolve a one-hop symlink to a regular file, without
    # depending on GNU-only `readlink -f` (unavailable on stock macOS).
    # Directory symlinks (SKILL_DEST) are resolved with `cd -P`/`pwd -P`
    # instead, since you cannot `cd` into a file.
    #
    # Both branches below run the target's directory through `cd -P`/`pwd -P`
    # -- the same physical resolution $REPO already went through. An absolute
    # target left as found (the previous behaviour) can name the same
    # directory as $REPO through a different path (e.g. /tmp/... vs.
    # /private/tmp/... on macOS) and compare unequal, reporting drift against
    # a link that is not actually wrong.
    link="$1"
    target="$(readlink "$link")"
    case "$target" in
        /*) target_dir="$(dirname "$target")" ;;
        *) target_dir="$(dirname "$link")/$(dirname "$target")" ;;
    esac
    printf '%s/%s\n' \
        "$(cd -P "$target_dir" && pwd -P)" \
        "$(basename "$target")"
}

check_diff() {
    # Compare two paths with `diff`, distinguishing "differs" (exit 1) from
    # "diff itself could not compare them" (any other exit -- an unreadable
    # file, a file compared against a directory, ...), so a real comparison
    # failure is never silently reported as ordinary drift. Prints nothing
    # and returns 0 when the paths match; otherwise prints the appropriate
    # message, sets `status=1`, and returns 1.
    # $1 = diff flags (e.g. "-q" or "-rq"), $2 = left path, $3 = right path,
    # $4 = name to use in messages (e.g. "SKILL.md", "scripts/inventory.py")
    #
    # `diff_rc=$?` must be captured via `cmd || diff_rc=$?`, not read back
    # after a plain `if cmd; then ... fi`: per POSIX, an `if` whose condition
    # is false and has no matching branch exits 0 itself, not with the
    # condition's own exit status.
    diff_rc=0
    diff "$1" "$2" "$3" >/dev/null 2>&1 || diff_rc=$?
    if [ "$diff_rc" -eq 0 ]; then
        return 0
    fi
    if [ "$diff_rc" -eq 1 ]; then
        echo "drift: $4 differs from the deployed copy" >&2
    else
        echo "check failed: could not compare $4 ($2 vs $3)" >&2
    fi
    status=1
    return 1
}

if [ "$check_only" -eq 1 ]; then
    skill_present=0
    [ -e "$SKILL_DEST" ] || [ -L "$SKILL_DEST" ] && skill_present=1
    agent_present=0
    [ -e "$AGENT_DEST" ] || [ -L "$AGENT_DEST" ] && agent_present=1

    if [ "$skill_present" -eq 0 ] && [ "$agent_present" -eq 0 ]; then
        echo "not installed" >&2
        exit 1
    fi

    status=0

    # Each destination is judged on its own: a symlinked skill must not vouch
    # for a stale agent copy. A symlink cannot drift in content, but it can
    # break or point somewhere else; a copy can drift.
    if [ -L "$SKILL_DEST" ] && [ ! -e "$SKILL_DEST" ]; then
        echo "drift: the skill directory is a broken symlink" >&2
        status=1
    elif [ -L "$SKILL_DEST" ] && [ "$mode_given" -eq 1 ] && [ "$mode" = copy ]; then
        echo "drift: skill deployed as symlink, copy requested" >&2
        status=1
    elif [ -L "$SKILL_DEST" ]; then
        skill_target="$(cd -P "$SKILL_DEST" && pwd -P)"
        if [ "$skill_target" = "$REPO" ]; then
            echo "skill: symlink, cannot drift"
        else
            echo "drift: skill symlink points to $skill_target, expected $REPO" >&2
            status=1
        fi
    elif [ ! -e "$SKILL_DEST" ]; then
        echo "missing: skill not deployed" >&2
        status=1
    elif [ "$mode_given" -eq 1 ] && [ "$mode" = symlink ]; then
        echo "drift: skill deployed as copy, symlink requested" >&2
        status=1
    else
        if check_diff "-rq" "$REPO/SKILL.md" "$SKILL_DEST/SKILL.md" "SKILL.md"; then
            echo "skill: copy in sync"
        fi

        if check_diff "-rq" "$REPO/references" "$SKILL_DEST/references" "references/"; then
            echo "references: copy in sync"
        fi

        # Compare exactly the deploy list (DEPLOYED_SCRIPTS), then separately
        # confirm the deployed scripts/ directory has nothing beyond it --
        # a leftover from an older version would otherwise go unnoticed.
        scripts_ok=1
        for script_name in "${DEPLOYED_SCRIPTS[@]}"; do
            if ! check_diff "-q" "$REPO/scripts/$script_name" "$SKILL_DEST/scripts/$script_name" "scripts/$script_name"; then
                scripts_ok=0
            fi
        done
        # dotglob only for this one glob, restored right after -- a hidden
        # leftover (e.g. .leftover.py) must count as unexpected too, but the
        # rest of the script must not start matching dotfiles elsewhere.
        # `shopt -p dotglob` itself exits 1 when the option is currently
        # unset (the common case), which would trip `set -e` right here --
        # the `|| true` keeps the captured value without losing that status.
        dotglob_previously="$(shopt -p dotglob)" || true
        shopt -s dotglob
        for deployed_entry in "$SKILL_DEST/scripts"/*; do
            entry_name="$(basename "$deployed_entry")"
            entry_known=0
            for script_name in "${DEPLOYED_SCRIPTS[@]}"; do
                if [ "$entry_name" = "$script_name" ]; then
                    entry_known=1
                    break
                fi
            done
            if [ "$entry_known" -eq 0 ]; then
                echo "drift: unexpected file in deployed scripts/: $entry_name" >&2
                status=1
                scripts_ok=0
            fi
        done
        eval "$dotglob_previously"
        if [ "$scripts_ok" -eq 1 ]; then
            echo "scripts: copy in sync"
        fi
    fi

    if [ -L "$AGENT_DEST" ] && [ ! -e "$AGENT_DEST" ]; then
        echo "drift: semantic-twin-hunter.md is a broken symlink" >&2
        status=1
    elif [ -L "$AGENT_DEST" ] && [ "$mode_given" -eq 1 ] && [ "$mode" = copy ]; then
        echo "drift: agent deployed as symlink, copy requested" >&2
        status=1
    elif [ -L "$AGENT_DEST" ]; then
        agent_target="$(resolve_file_symlink "$AGENT_DEST")"
        expected_agent_target="$REPO/agents/semantic-twin-hunter.md"
        if [ "$agent_target" = "$expected_agent_target" ]; then
            echo "agent: symlink, cannot drift"
        else
            echo "drift: agent symlink points to $agent_target, expected $expected_agent_target" >&2
            status=1
        fi
    elif [ ! -e "$AGENT_DEST" ]; then
        echo "missing: agent not deployed" >&2
        status=1
    elif [ "$mode_given" -eq 1 ] && [ "$mode" = symlink ]; then
        echo "drift: agent deployed as copy, symlink requested" >&2
        status=1
    elif check_diff "-q" "$REPO/agents/semantic-twin-hunter.md" "$AGENT_DEST" "semantic-twin-hunter.md"; then
        echo "agent: copy in sync"
    fi

    exit "$status"
fi

mkdir -p "$HOME/.claude/skills" "$HOME/.claude/agents"
rm -rf "$SKILL_DEST" "$AGENT_DEST"

if [ "$mode" = symlink ]; then
    ln -sfn "$REPO" "$SKILL_DEST"
    ln -sfn "$REPO/agents/semantic-twin-hunter.md" "$AGENT_DEST"
else
    mkdir -p "$SKILL_DEST" "$SKILL_DEST/scripts"
    cp "$REPO/SKILL.md" "$SKILL_DEST/SKILL.md"
    cp -R "$REPO/references" "$SKILL_DEST/references"
    for script_name in "${DEPLOYED_SCRIPTS[@]}"; do
        cp "$REPO/scripts/$script_name" "$SKILL_DEST/scripts/$script_name"
    done
    cp "$REPO/agents/semantic-twin-hunter.md" "$AGENT_DEST"
fi

echo "installed in $mode mode"

if [ "$mode" = symlink ]; then
    echo "add /agents/semantic-twin-hunter.md to ~/.claude/.gitignore: ~/.claude/agents/ is tracked, and this symlink is machine-specific"
fi

echo "restart Claude Code, then run /semantic-twins"
