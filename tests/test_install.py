import os
import shutil
import subprocess
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
INSTALL_SH = str(REPO_ROOT / "scripts" / "install.sh")


def _skill_dest(home: Path) -> Path:
    return home / ".claude" / "skills" / "semantic-twins"


def _agent_dest(home: Path) -> Path:
    return home / ".claude" / "agents" / "semantic-twin-hunter.md"


def _tamper(path: Path, content: str) -> None:
    """Overwrite a deployed destination, refusing to write through a symlink.

    A symlink-mode deployment makes $SKILL_DEST/$AGENT_DEST point into the
    real repository checkout; a plain write_text() there would follow the
    link and edit the checkout itself instead of the fake deployment.
    """
    assert not path.is_symlink(), f"refusing to write through a symlink: {path}"
    path.write_text(content)


class FakeHome(NamedTuple):
    """A fresh fake `$HOME` plus a helper that invokes install.sh against it."""

    path: Path
    run: Callable[..., "subprocess.CompletedProcess[str]"]


@pytest.fixture
def fake_home(tmp_path: Path) -> FakeHome:
    home = tmp_path / "home"
    home.mkdir()

    def run(
        *args: str, home_override: str | None = None
    ) -> "subprocess.CompletedProcess[str]":
        env = os.environ.copy()
        env["HOME"] = home_override if home_override is not None else str(home)
        return subprocess.run(
            [INSTALL_SH, *args],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

    return FakeHome(path=home, run=run)


def test_symlink_mode_creates_symlinks_at_both_destinations(fake_home: FakeHome):
    result = fake_home.run("--mode", "symlink")
    assert result.returncode == 0
    assert _skill_dest(fake_home.path).is_symlink()
    assert _agent_dest(fake_home.path).is_symlink()


def test_symlink_targets_resolve_to_the_repository(fake_home: FakeHome):
    fake_home.run("--mode", "symlink")
    assert _skill_dest(fake_home.path).resolve() == REPO_ROOT.resolve()
    assert (
        _agent_dest(fake_home.path).resolve()
        == (REPO_ROOT / "agents" / "semantic-twin-hunter.md").resolve()
    )


def test_running_installer_through_the_deployed_symlink_does_not_destroy_it(
    fake_home: FakeHome,
):
    # The single most important test in this file. Before the fix, REPO was
    # computed with a logical `cd`, so invoking install.sh through the
    # deployed symlink (the most natural place a user finds it) made REPO
    # equal to the symlink path itself: `rm -rf "$SKILL_DEST"` then deleted
    # the deployment, and `ln -sfn "$REPO" "$SKILL_DEST"` recreated it as a
    # dead, self-referential link -- with exit 0 and a success message.
    fake_home.run("--mode", "symlink")
    skill_dest = _skill_dest(fake_home.path)
    deployed_install_sh = str(skill_dest / "scripts" / "install.sh")

    env = os.environ.copy()
    env["HOME"] = str(fake_home.path)
    result = subprocess.run(
        [deployed_install_sh],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert skill_dest.is_symlink()
    assert skill_dest.resolve() == REPO_ROOT.resolve()
    assert (skill_dest / "SKILL.md").exists()


def _copy_real_checkout(dest: Path) -> None:
    """Copy the parts of this repository install.sh cares about into `dest`,
    so it looks like a real (non-symlinked) checkout placed there -- e.g. by
    `git clone` or a plain file copy, never installed through this script."""
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy(REPO_ROOT / "SKILL.md", dest / "SKILL.md")
    shutil.copytree(REPO_ROOT / "references", dest / "references")
    shutil.copytree(REPO_ROOT / "scripts", dest / "scripts")
    shutil.copytree(REPO_ROOT / "agents", dest / "agents")


def test_running_installer_from_a_real_checkout_placed_under_claude_refuses(
    fake_home: FakeHome,
):
    # The guard's other half. `cd -P` defeats REPO == SKILL_DEST only when
    # SKILL_DEST is a symlink to resolve *through*; a real checkout placed
    # directly at $HOME/.claude/skills/semantic-twins (cloned or copied there
    # by hand, never installed through this script) has no symlink to
    # resolve, so REPO physically equals SKILL_DEST. Without the categorical
    # guard, running install.sh from there would make `rm -rf "$SKILL_DEST"`
    # delete this very checkout and recreate it as a dead, self-referential
    # link -- silently, with exit 0.
    skill_dest = _skill_dest(fake_home.path)
    _copy_real_checkout(skill_dest)
    marker = (skill_dest / "SKILL.md").read_text()

    deployed_install_sh = str(skill_dest / "scripts" / "install.sh")
    env = os.environ.copy()
    env["HOME"] = str(fake_home.path)
    result = subprocess.run(
        [deployed_install_sh],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "must be run from the repository checkout" in result.stderr
    assert skill_dest.is_dir()
    assert not skill_dest.is_symlink()
    assert (skill_dest / "SKILL.md").read_text() == marker


def test_copy_mode_deploys_scripts_directory_with_only_inventory(fake_home: FakeHome):
    result = fake_home.run("--mode", "copy")
    assert result.returncode == 0
    skill_dest = _skill_dest(fake_home.path)
    assert not skill_dest.is_symlink()
    deployed_scripts = sorted(p.name for p in (skill_dest / "scripts").iterdir())
    assert deployed_scripts == ["inventory.py"]


def test_check_after_symlink_install_exits_zero(fake_home: FakeHome):
    fake_home.run("--mode", "symlink")
    result = fake_home.run("--check")
    assert result.returncode == 0
    assert "skill: symlink, cannot drift" in result.stdout


def test_symlink_install_after_copy_replaces_the_stale_copy_directory(
    fake_home: FakeHome,
):
    # The copy -> symlink direction of the destroy-before-verify family: a
    # prior copy-mode deployment leaves a real directory at SKILL_DEST, and
    # `rm -rf "$SKILL_DEST" "$AGENT_DEST"` must remove it before `ln -sfn`
    # runs. Drop "$SKILL_DEST" from that rm -rf and `ln -sfn "$REPO"
    # "$SKILL_DEST"` treats the still-present real directory as a place to
    # link *into* (ln's directory-target behaviour), nesting a dead symlink
    # at $SKILL_DEST/semantic-twins instead of replacing $SKILL_DEST itself.
    fake_home.run("--mode", "copy")
    result = fake_home.run("--mode", "symlink")
    assert result.returncode == 0

    skill_dest = _skill_dest(fake_home.path)
    assert skill_dest.is_symlink()
    assert skill_dest.resolve() == REPO_ROOT.resolve()

    check_result = fake_home.run("--check")
    assert check_result.returncode == 0


@pytest.mark.skipif(
    hasattr(os, "geteuid") and os.geteuid() == 0,
    reason="root bypasses directory permission checks",
)
def test_a_failed_build_leaves_the_previous_deployment_intact(fake_home: FakeHome):
    # install.sh now builds the new deployment into a staging directory
    # beside the destinations and only swaps it in once the build is
    # complete. Force the build phase itself to fail -- by making
    # $HOME/.claude read-only, so even creating the staging directory is
    # refused -- and confirm neither destination was touched: no half
    # deletion, no half replacement.
    fake_home.run("--mode", "copy")
    skill_dest = _skill_dest(fake_home.path)
    agent_dest = _agent_dest(fake_home.path)
    skill_marker = (skill_dest / "SKILL.md").read_text()
    agent_marker = agent_dest.read_text()

    claude_dir = fake_home.path / ".claude"
    claude_dir.chmod(0o555)
    try:
        result = fake_home.run("--mode", "symlink")
    finally:
        claude_dir.chmod(0o755)

    assert result.returncode != 0
    assert skill_dest.is_dir()
    assert not skill_dest.is_symlink()
    assert (skill_dest / "SKILL.md").read_text() == skill_marker
    assert agent_dest.is_file()
    assert not agent_dest.is_symlink()
    assert agent_dest.read_text() == agent_marker


def test_check_after_clean_copy_install_exits_zero(fake_home: FakeHome):
    fake_home.run("--mode", "copy")
    result = fake_home.run("--check")
    assert result.returncode == 0


def test_check_with_requested_mode_matching_deployment_exits_zero(
    fake_home: FakeHome,
):
    fake_home.run("--mode", "copy")
    result = fake_home.run("--check", "--mode", "copy")
    assert result.returncode == 0


def test_check_flags_mode_mismatch_between_requested_and_deployed(
    fake_home: FakeHome,
):
    fake_home.run("--mode", "symlink")
    result = fake_home.run("--check", "--mode", "copy")
    assert result.returncode == 1
    assert "drift: skill deployed as symlink, copy requested" in result.stderr
    assert "drift: agent deployed as symlink, copy requested" in result.stderr


def test_check_flags_copy_deployment_when_symlink_requested(fake_home: FakeHome):
    # The reverse direction of test_check_flags_mode_mismatch_between_requested_and_deployed:
    # deployed as copy, --check --mode symlink requested. Both the skill and
    # agent "deployed as copy, symlink requested" branches must fire.
    fake_home.run("--mode", "copy")
    result = fake_home.run("--check", "--mode", "symlink")
    assert result.returncode == 1
    assert "drift: skill deployed as copy, symlink requested" in result.stderr
    assert "drift: agent deployed as copy, symlink requested" in result.stderr


def test_check_detects_a_symlink_pointing_at_the_wrong_target(fake_home: FakeHome):
    fake_home.run("--mode", "symlink")
    skill_dest = _skill_dest(fake_home.path)
    wrong_target = fake_home.path
    skill_dest.unlink()
    skill_dest.symlink_to(wrong_target)

    result = fake_home.run("--check")
    assert result.returncode == 1
    assert "drift: skill symlink points to" in result.stderr
    assert str(wrong_target.resolve()) in result.stderr
    assert str(REPO_ROOT.resolve()) in result.stderr


def test_check_reports_missing_destination_rather_than_differs(fake_home: FakeHome):
    fake_home.run("--mode", "copy")
    _agent_dest(fake_home.path).unlink()

    result = fake_home.run("--check")
    assert result.returncode == 1
    assert "missing: agent not deployed" in result.stderr
    assert "differs from the deployed copy" not in result.stderr


def test_check_reports_missing_skill_with_nonzero_status(fake_home: FakeHome):
    # Mirror of test_check_reports_missing_destination_rather_than_differs,
    # deleting the skill side instead of the agent side. Both branches print
    # their "missing" message independently of whether they also set
    # status=1, so a passing exit code here is the only signal that the
    # skill's own missing-destination branch (not just the agent's) sets it.
    fake_home.run("--mode", "copy")
    shutil.rmtree(_skill_dest(fake_home.path))

    result = fake_home.run("--check")
    assert result.returncode == 1
    assert "missing: skill not deployed" in result.stderr


def test_check_detects_drift_in_deployed_skill_md(fake_home: FakeHome):
    fake_home.run("--mode", "copy")
    _tamper(_skill_dest(fake_home.path) / "SKILL.md", "tampered\n")
    result = fake_home.run("--check")
    assert result.returncode == 1
    assert "drift: SKILL.md differs from the deployed copy" in result.stderr


def test_check_detects_drift_in_deployed_taxonomy(fake_home: FakeHome):
    fake_home.run("--mode", "copy")
    _tamper(_skill_dest(fake_home.path) / "references" / "taxonomy.md", "tampered\n")
    result = fake_home.run("--check")
    assert result.returncode == 1
    assert "drift: references/ differs from the deployed copy" in result.stderr


def test_check_detects_drift_in_a_references_subdirectory(fake_home: FakeHome):
    # references/examples/notes.txt sits one level below references/ itself,
    # so a non-recursive comparison ("Common subdirectories: ... examples")
    # would never look inside it and miss the tamper. Only a recursive diff
    # (-r) descends far enough to catch it.
    fake_home.run("--mode", "copy")
    _tamper(
        _skill_dest(fake_home.path) / "references" / "examples" / "notes.txt",
        "tampered\n",
    )
    result = fake_home.run("--check")
    assert result.returncode == 1
    assert "drift: references/ differs from the deployed copy" in result.stderr


def test_check_detects_drift_in_deployed_inventory_script(fake_home: FakeHome):
    fake_home.run("--mode", "copy")
    _tamper(_skill_dest(fake_home.path) / "scripts" / "inventory.py", "tampered\n")
    result = fake_home.run("--check")
    assert result.returncode == 1
    assert "drift: scripts/inventory.py differs from the deployed copy" in result.stderr


def test_check_detects_an_unexpected_file_in_deployed_scripts(fake_home: FakeHome):
    # Plants both a visible and a hidden leftover. Without `shopt -s dotglob`
    # in install.sh's --check comparison, the glob that walks the deployed
    # scripts/ directory never matches the dotfile at all, so its drift line
    # never gets a chance to print -- a test that only plants the visible
    # leftover.py cannot tell dotglob apart from no dotglob.
    scripts_dir = _skill_dest(fake_home.path) / "scripts"
    fake_home.run("--mode", "copy")
    scripts_dir.joinpath("leftover.py").write_text("X = 1\n")
    scripts_dir.joinpath(".leftover.py").write_text("Y = 1\n")
    result = fake_home.run("--check")
    assert result.returncode == 1
    assert "drift: unexpected file in deployed scripts/: leftover.py" in result.stderr
    assert "drift: unexpected file in deployed scripts/: .leftover.py" in result.stderr


def test_check_detects_an_unexpected_entry_at_the_deployed_skill_top_level(
    fake_home: FakeHome,
):
    # The same extras sweep as test_check_detects_an_unexpected_file_in_deployed_scripts,
    # one level up: a stray entry directly under $SKILL_DEST (a references2/
    # left by an older version, say) sits outside SKILL.md/references/
    # scripts and would otherwise go unnoticed.
    skill_dest = _skill_dest(fake_home.path)
    fake_home.run("--mode", "copy")
    (skill_dest / "leftover_dir").mkdir()
    (skill_dest / ".leftover").write_text("Z = 1\n")
    result = fake_home.run("--check")
    assert result.returncode == 1
    assert (
        "drift: unexpected entry in deployed skill directory: leftover_dir"
        in result.stderr
    )
    assert (
        "drift: unexpected entry in deployed skill directory: .leftover"
        in result.stderr
    )


def test_check_distinguishes_a_diff_failure_from_ordinary_drift(fake_home: FakeHome):
    # A file-vs-directory mismatch makes `diff` itself fail (exit 2), which
    # must not be reported as ordinary content drift (exit 1) -- otherwise a
    # genuine comparison failure (e.g. a permission error) would be silently
    # folded into "differs". Using a directory instead of chmod keeps this
    # reproducible regardless of the user running the tests (root bypasses
    # permission checks, but not a type mismatch).
    fake_home.run("--mode", "copy")
    agent_dest = _agent_dest(fake_home.path)
    agent_dest.unlink()
    agent_dest.mkdir()
    result = fake_home.run("--check")
    assert result.returncode == 1
    assert "check failed: could not compare semantic-twin-hunter.md" in result.stderr
    assert (
        "drift: semantic-twin-hunter.md differs from the deployed copy"
        not in result.stderr
    )


def test_check_flags_agent_replaced_after_symlink_install(fake_home: FakeHome):
    fake_home.run("--mode", "symlink")
    agent_dest = _agent_dest(fake_home.path)
    agent_dest.unlink()
    _tamper(agent_dest, "tampered\n")
    result = fake_home.run("--check")
    assert result.returncode == 1
    assert (
        "drift: semantic-twin-hunter.md differs from the deployed copy" in result.stderr
    )


def test_check_normalises_a_symlink_target_reached_through_a_non_physical_path(
    fake_home: FakeHome,
):
    # resolve_file_symlink runs the agent symlink's target directory through
    # `cd -P`/`pwd -P`, the same physical resolution $REPO already went
    # through, so a target recorded via a non-physical route still compares
    # equal to $REPO. macOS's /tmp -> /private/tmp is the real-world case
    # named in install.sh's own comment: reproduce it by placing an alias
    # symlink directly under /tmp that points at this repository's agents/
    # directory, then recording the deployed agent symlink's target through
    # that alias instead of through $REPO directly.
    fake_home.run("--mode", "symlink")
    agent_dest = _agent_dest(fake_home.path)
    agent_dest.unlink()

    alias = Path("/tmp") / f"semantic-twins-agent-alias-{uuid.uuid4().hex}"
    alias.symlink_to(REPO_ROOT / "agents")
    try:
        agent_dest.symlink_to(alias / "semantic-twin-hunter.md")
        result = fake_home.run("--check")
        assert result.returncode == 0
        assert "agent: symlink, cannot drift" in result.stdout
    finally:
        alias.unlink()


def test_check_with_nothing_installed_reports_not_installed(fake_home: FakeHome):
    result = fake_home.run("--check")
    assert result.returncode == 1
    assert "not installed" in result.stderr


def test_empty_home_aborts_and_creates_nothing(fake_home: FakeHome):
    result = fake_home.run("--mode", "copy", home_override="")
    assert result.returncode != 0
    assert "HOME must be set and non-empty" in result.stderr
    # With HOME="", the destinations would resolve under "/.claude/...",
    # outside the fixture's fake home -- asserting the fake home stayed
    # empty would be vacuously true regardless of what the script did.
    # Assert the real target path was never created instead.
    assert not Path("/.claude/skills/semantic-twins").exists()


def test_unknown_mode_or_unknown_flag_exits_two(fake_home: FakeHome):
    result = fake_home.run("--mode", "bogus")
    assert result.returncode == 2

    result = fake_home.run("--frobnicate")
    assert result.returncode == 2

    result = fake_home.run("--mode")
    assert result.returncode == 2


def test_gitignore_instruction_only_in_symlink_mode(fake_home: FakeHome):
    symlink_result = fake_home.run("--mode", "symlink")
    assert "~/.claude/.gitignore" in symlink_result.stdout
    assert "installed in symlink mode" in symlink_result.stdout

    copy_result = fake_home.run("--mode", "copy")
    assert "~/.claude/.gitignore" not in copy_result.stdout
    assert "installed in copy mode" in copy_result.stdout


def test_check_reports_a_broken_symlink_rather_than_not_installed(fake_home: FakeHome):
    skill_dest = _skill_dest(fake_home.path)
    skill_dest.parent.mkdir(parents=True, exist_ok=True)
    skill_dest.symlink_to(fake_home.path / "nonexistent-target")

    result = fake_home.run("--check")
    assert result.returncode == 1
    assert "not installed" not in result.stderr
    assert "broken symlink" in result.stderr
    # Naming the destination too: "broken symlink" alone would still pass if
    # the skill and agent messages were swapped, since both mention it.
    assert "skill directory" in result.stderr


def test_check_reports_a_broken_agent_symlink(fake_home: FakeHome):
    fake_home.run("--mode", "symlink")
    agent_dest = _agent_dest(fake_home.path)
    agent_dest.unlink()
    agent_dest.symlink_to(fake_home.path / "nonexistent-target")

    result = fake_home.run("--check")
    assert result.returncode == 1
    assert "drift: semantic-twin-hunter.md is a broken symlink" in result.stderr
