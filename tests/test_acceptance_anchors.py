import re
from pathlib import Path

import pytest

ACCEPTANCE = Path(__file__).resolve().parent / "ACCEPTANCE.md"
CORPUS = Path(__file__).resolve().parent / "fixtures" / "twin-corpus"

ANCHOR = re.compile(r"`([\w./-]+):(\d+)`")
# `abstract`/`final` are class modifiers, not definitions on their own — they only
# count when directly followed by one of the real definition keywords, so a bare
# `final $x = 5;` still falls through to no match.
DEFINITION = re.compile(
    r"^\s*(?:(?:abstract|final)\s+)*"
    r"(def|class|interface|trait|function|public|private|protected|static)\b"
)


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


@pytest.mark.parametrize(
    "line",
    [
        "class Foo",
        "final class Foo",
        "abstract class Foo",
        "interface Foo",
        "trait Foo",
        "    public static function fromRow(array $row): self",
        "private function bar()",
        "abstract public function process();",
    ],
)
def test_definition_regex_recognises_php_declaration_forms(line):
    assert DEFINITION.match(line), f"expected a definition match: {line!r}"


def test_php_class_declaration_in_the_corpus_is_recognised_as_a_definition():
    """The line the corrected `CustomerDto` anchor actually points at.

    `final class CustomerDto` was the gap this regex used to miss — PHP's
    `final` modifier sits in front of `class`, and the old alternation only
    matched a line starting with one bare keyword.
    """
    cited = (CORPUS / "ordering" / "CustomerDto.php").read_text().splitlines()[4]
    assert cited == "final class CustomerDto"
    assert DEFINITION.match(cited)


@pytest.mark.parametrize(
    "line",
    [
        "// Deliberately separate from Ordering\\CustomerDto: the shipping context must not",
        "{",
        "    $dto = new self();",
        "final $x = 5;",
        "namespace Ordering;",
    ],
)
def test_definition_regex_still_rejects_non_definition_lines(line):
    assert not DEFINITION.match(line), f"expected no definition match: {line!r}"


def test_neighbouring_non_definition_lines_in_the_same_corpus_file_are_rejected():
    """The comment line directly above the class, and the opening brace below it.

    Proves the widened regex only picked up the genuine PHP declaration forms
    and did not simply loosen matching for every line in that file.
    """
    ordering_lines = (CORPUS / "ordering" / "CustomerDto.php").read_text().splitlines()
    assert ordering_lines[5] == "{"
    assert not DEFINITION.match(ordering_lines[5])

    shipping_lines = (CORPUS / "shipping" / "CustomerDto.php").read_text().splitlines()
    comment_line = shipping_lines[4]
    assert comment_line.startswith("// Deliberately separate")
    assert not DEFINITION.match(comment_line)
