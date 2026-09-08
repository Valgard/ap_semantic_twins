import shutil
import subprocess
from pathlib import Path

import pytest
from inventory import build_inventory

CORPUS = Path(__file__).resolve().parent / "fixtures" / "twin-corpus"


@pytest.fixture
def corpus_repo(tmp_path: Path) -> Path:
    target = tmp_path / "corpus"
    # The corpus fixture has no .gitignore of its own, so a plain copytree
    # would drag its gitignored __pycache__ directories along, and the
    # following `git add -A` (also with no .gitignore in the tmp repo) would
    # then track those .pyc files -- an interpreter-version-dependent count
    # that does not match the real, git-tracked corpus.
    shutil.copytree(CORPUS, target, ignore=shutil.ignore_patterns("__pycache__"))
    for args in (
        ("init", "-q"),
        ("config", "user.email", "fixture@example.com"),
        ("config", "user.name", "Fixture"),
        ("add", "-A"),
        ("commit", "-q", "-m", "fixture"),
    ):
        subprocess.run(
            ["git", "-C", str(target), *args], check=True, capture_output=True
        )
    return target


def test_corpus_excludes_the_generated_decoy(corpus_repo: Path):
    inventory = build_inventory(corpus_repo)
    kept = {entry["path"] for entry in inventory["files"]}
    assert "generated/Mapper.g.cs" not in kept
    assert inventory["excluded"]["generated"] == 1


def test_corpus_keeps_every_planted_pair(corpus_repo: Path):
    inventory = build_inventory(corpus_repo)
    kept = {entry["path"] for entry in inventory["files"]}
    assert kept == {
        "pricing/checkout.py",
        "pricing/invoice.py",
        "slug/article.py",
        "slug/category.py",
        "ordering/CustomerDto.php",
        "shipping/CustomerDto.php",
        "validation/email.py",
        "validation/postcode.py",
    }


def test_corpus_records_both_languages(corpus_repo: Path):
    inventory = build_inventory(corpus_repo)
    languages = {entry["language"] for entry in inventory["files"]}
    assert languages == {"python", "php"}
