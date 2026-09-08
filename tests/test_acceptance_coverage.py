import re
import shutil
import subprocess
from pathlib import Path

import pytest
from inventory import build_inventory

ACCEPTANCE = Path(__file__).resolve().parent / "ACCEPTANCE.md"
CORPUS = Path(__file__).resolve().parent / "fixtures" / "twin-corpus"
SKILL = Path(__file__).resolve().parent.parent / "SKILL.md"
AGENT = Path(__file__).resolve().parent.parent / "agents" / "semantic-twin-hunter.md"

# Maps the English label ACCEPTANCE.md's `Excluded:` line uses for each
# counter to the JSON key `build_inventory` returns it under -- the same nine
# reasons, in the same order, that scripts/inventory.py's `excluded` dict
# uses.
EXCLUDED_LABELS = {
    "by path rule": "path_rule",
    "unsupported extension": "unsupported_extension",
    "generated": "generated",
    "symlink": "symlink",
    "submodule": "submodule",
    "untracked": "untracked",
    "missing": "missing",
    "undecodable": "undecodable",
    "permission denied": "permission_denied",
}

# The seven exclusion reasons that also get a per-path list -- the doc's
# "<Label> files:" lines, mapped to the excluded_paths key each one pins.
FILE_LIST_LABELS = {
    "Generated files": "generated",
    "Symlink files": "symlink",
    "Submodule files": "submodule",
    "Untracked files": "untracked",
    "Missing files": "missing",
    "Undecodable files": "undecodable",
    "Permission denied files": "permission_denied",
}


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


def _bullet(text: str, label: str) -> str:
    """The text of one `- `Label:` ...` Coverage bullet, up to its em dash."""
    match = re.search(rf"`{re.escape(label)}:`([^\n]*)", text)
    assert match, f"no {label!r} line found in ACCEPTANCE.md"
    return match.group(1).split("—")[0]


def test_examined_files_count_matches_a_real_inventory_run(corpus_repo):
    inventory = build_inventory(corpus_repo)
    segment = _bullet(ACCEPTANCE.read_text(), "Examined")
    examined = int(re.search(r"`(\d+)`", segment).group(1))
    assert examined == inventory["totals"]["files"]


def test_chunks_line_matches_a_real_inventory_run(corpus_repo):
    inventory = build_inventory(corpus_repo)
    segment = _bullet(ACCEPTANCE.read_text(), "Chunks")
    numbers = [int(n) for n in re.findall(r"`(\d+)`", segment)]
    assert (
        len(numbers) == 6
    )  # dispatched, totals.chunks, returned units, nothing, unparseable, mismatches
    (
        dispatched,
        totals_chunks,
        returned_units,
        returned_nothing,
        unparseable,
        mismatches,
    ) = numbers
    assert totals_chunks == inventory["totals"]["chunks"]
    assert dispatched == inventory["totals"]["chunks"]
    # Every file in this corpus defines a named unit, so a healthy run's
    # chunk count that "returned at least one unit" equals every file.
    assert returned_units == inventory["totals"]["files"]
    assert returned_nothing == 0
    assert unparseable == 0
    assert mismatches == 0


def test_excluded_counters_match_a_real_inventory_run(corpus_repo):
    inventory = build_inventory(corpus_repo)
    segment = _bullet(ACCEPTANCE.read_text(), "Excluded")
    pairs = re.findall(r"`(\d+)`\s+([a-z ]+?)(?:,|$)", segment)
    documented = {label.strip(): int(count) for count, label in pairs}
    assert set(documented) == set(EXCLUDED_LABELS), (
        "ACCEPTANCE.md's Excluded line must name exactly the nine counters "
        "scripts/inventory.py's excluded dict uses"
    )
    for label, key in EXCLUDED_LABELS.items():
        assert documented[label] == inventory["excluded"][key], (
            f"Excluded: {label} does not match a real inventory run"
        )


def test_unsupported_extensions_histogram_matches_a_real_inventory_run(corpus_repo):
    inventory = build_inventory(corpus_repo)
    assert inventory["unsupported_extensions"] == {}
    assert "`Unsupported extensions: none`" in ACCEPTANCE.read_text()


@pytest.mark.parametrize("label,key", FILE_LIST_LABELS.items())
def test_excluded_path_list_matches_a_real_inventory_run(corpus_repo, label, key):
    inventory = build_inventory(corpus_repo)
    text = ACCEPTANCE.read_text()
    match = re.search(rf"`{re.escape(label)}: ([^`]*)`", text)
    assert match, f"no {label!r} line found in ACCEPTANCE.md"
    raw = match.group(1)
    documented = [] if raw == "none" else [p.strip() for p in raw.split(",")]
    assert documented == inventory["excluded_paths"][key]


# --- B3: the consolidation figure and the headings this document quotes ---

QUOTED_HEADINGS = [
    ("## Defects: divergent twins", SKILL),
    ("## Debt: stable twins", SKILL),
    ("### Scope", AGENT),
    ("### Checked and refuted", AGENT),
]


@pytest.mark.parametrize(
    "heading,source",
    QUOTED_HEADINGS,
    ids=[f"{h}@{s.name}" for h, s in QUOTED_HEADINGS],
)
def test_quoted_heading_exists_in_its_source(heading, source):
    lines = source.read_text().splitlines()
    assert any(line.startswith(heading) for line in lines), (
        f"ACCEPTANCE.md quotes {heading!r} from {source.name}, "
        f"but no such heading exists there"
    )


def test_consolidation_figure_matches_the_fixture_spans():
    article_lines = (CORPUS / "slug" / "article.py").read_text().splitlines()
    category_lines = (CORPUS / "slug" / "category.py").read_text().splitlines()

    slugify_start = 1 + next(
        i for i, line in enumerate(article_lines) if line.startswith("def slugify")
    )
    to_url_key_start = 1 + next(
        i for i, line in enumerate(category_lines) if line.startswith("def to_url_key")
    )
    # Both functions run to the end of their file -- slugify is the last
    # statement in article.py, and to_url_key is the only function in
    # category.py.
    slugify_span = len(article_lines) - slugify_start + 1
    to_url_key_span = len(category_lines) - to_url_key_start + 1

    consolidation = (slugify_span + to_url_key_span) - max(
        slugify_span, to_url_key_span
    )
    assert slugify_span == 4
    assert to_url_key_span == 12
    assert consolidation == 4

    assert f"Consolidation: ~{consolidation} lines" in ACCEPTANCE.read_text()
