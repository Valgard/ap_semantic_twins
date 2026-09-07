import re
from pathlib import Path

ACCEPTANCE = Path(__file__).resolve().parent / "ACCEPTANCE.md"
CORPUS = Path(__file__).resolve().parent / "fixtures" / "twin-corpus"

ANCHOR = re.compile(r"`([\w./-]+):(\d+)`")
DEFINITION = re.compile(r"^\s*(def|class|function|public|private|protected|static)\b")


def _pair_cells() -> list[str]:
    lines = ACCEPTANCE.read_text().splitlines()
    header = next(i for i, line in enumerate(lines) if line.startswith("| Pair "))
    rows = lines[header + 2 :]
    return [row.split("|")[1] for row in rows if row.startswith("|")]


def test_every_anchor_in_the_expectations_table_is_a_real_definition_line():
    anchors = [m for cell in _pair_cells() for m in ANCHOR.findall(cell)]
    assert len(anchors) == 10  # five rows, two path:line anchors each
    for path, line_no in anchors:
        target = CORPUS / path
        assert target.is_file(), f"{path} does not exist in the corpus"
        cited = target.read_text().splitlines()[int(line_no) - 1]
        assert DEFINITION.match(cited), (
            f"{path}:{line_no} is not a definition: {cited!r}"
        )
