import os
import subprocess
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


def test_check_after_clean_copy_install_exits_zero(fake_home: FakeHome):
    fake_home.run("--mode", "copy")
    result = fake_home.run("--check")
    assert result.returncode == 0


def test_check_detects_drift_in_deployed_skill_md(fake_home: FakeHome):
    fake_home.run("--mode", "copy")
    (_skill_dest(fake_home.path) / "SKILL.md").write_text("tampered\n")
    result = fake_home.run("--check")
    assert result.returncode == 1
    assert "drift: SKILL.md differs from the deployed copy" in result.stderr


def test_check_detects_drift_in_deployed_taxonomy(fake_home: FakeHome):
    fake_home.run("--mode", "copy")
    (_skill_dest(fake_home.path) / "references" / "taxonomy.md").write_text(
        "tampered\n"
    )
    result = fake_home.run("--check")
    assert result.returncode == 1
    assert "drift: references/ differs from the deployed copy" in result.stderr


def test_check_detects_drift_in_deployed_inventory_script(fake_home: FakeHome):
    fake_home.run("--mode", "copy")
    (_skill_dest(fake_home.path) / "scripts" / "inventory.py").write_text("tampered\n")
    result = fake_home.run("--check")
    assert result.returncode == 1
    assert "drift: scripts/inventory.py differs from the deployed copy" in result.stderr


def test_check_flags_agent_replaced_after_symlink_install(fake_home: FakeHome):
    fake_home.run("--mode", "symlink")
    agent_dest = _agent_dest(fake_home.path)
    agent_dest.unlink()
    agent_dest.write_text("tampered\n")
    result = fake_home.run("--check")
    assert result.returncode == 1
    assert (
        "drift: semantic-twin-hunter.md differs from the deployed copy" in result.stderr
    )


def test_check_with_nothing_installed_reports_not_installed(fake_home: FakeHome):
    result = fake_home.run("--check")
    assert result.returncode == 1
    assert "not installed" in result.stderr


def test_empty_home_aborts_and_creates_nothing(fake_home: FakeHome):
    result = fake_home.run("--mode", "copy", home_override="")
    assert result.returncode != 0
    assert "HOME must be set and non-empty" in result.stderr
    assert list(fake_home.path.iterdir()) == []


def test_unknown_mode_or_unknown_flag_exits_two(fake_home: FakeHome):
    result = fake_home.run("--mode", "bogus")
    assert result.returncode == 2

    result = fake_home.run("--frobnicate")
    assert result.returncode == 2


def test_gitignore_instruction_only_in_symlink_mode(fake_home: FakeHome):
    symlink_result = fake_home.run("--mode", "symlink")
    assert "~/.claude/.gitignore" in symlink_result.stdout

    copy_result = fake_home.run("--mode", "copy")
    assert "~/.claude/.gitignore" not in copy_result.stdout


def test_check_reports_a_broken_symlink_rather_than_not_installed(fake_home: FakeHome):
    skill_dest = _skill_dest(fake_home.path)
    skill_dest.parent.mkdir(parents=True, exist_ok=True)
    skill_dest.symlink_to(fake_home.path / "nonexistent-target")

    result = fake_home.run("--check")
    assert result.returncode == 1
    assert "not installed" not in result.stderr
    assert "broken symlink" in result.stderr
