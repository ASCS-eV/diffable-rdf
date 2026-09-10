"""Execute every documentation block explicitly marked as an example."""

from __future__ import annotations

from dataclasses import dataclass
import ast
from pathlib import Path

import pytest


_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DOCUMENTS = (_PROJECT_ROOT / "README.md", _PROJECT_ROOT / "docs" / "api.md")
_EXAMPLE_MARKER = "<!-- example -->"
_SIGNATURE_MARKER = "<!-- signature -->"


@dataclass(frozen=True)
class PythonBlock:
    """One explicitly classified Python fenced block in a Markdown document."""

    classification: str
    source: str
    line: int


def _is_unsupported_python_fence(line: str) -> bool:
    """Identify Python-like fence spellings outside the documented exact convention."""
    stripped = line.strip()
    if not stripped or stripped[0] not in {"`", "~"}:
        return False
    delimiter = stripped[0]
    delimiter_count = len(stripped) - len(stripped.lstrip(delimiter))
    info = stripped[delimiter_count:].strip().lower()
    return info.startswith("python") and line != "```python"


def extract_python_blocks(markdown: str, document: Path) -> list[PythonBlock]:
    """Extract Python fences whose immediately preceding marker classifies them."""
    blocks: list[PythonBlock] = []
    pending_marker: str | None = None
    lines = markdown.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        if _is_unsupported_python_fence(line):
            raise ValueError(f"{document}:{index + 1}: unsupported Python fence spelling")
        if line in {_EXAMPLE_MARKER, _SIGNATURE_MARKER}:
            if pending_marker is not None:
                raise ValueError(f"{document}:{index + 1}: consecutive Python block markers")
            pending_marker = line
            index += 1
            continue
        if line.startswith("```"):
            language = line[3:].strip()
            start_line = index + 1
            index += 1
            source_lines: list[str] = []
            while index < len(lines) and lines[index] != "```":
                if lines[index].startswith("```"):
                    raise ValueError(f"{document}:{index + 1}: unsupported Python fence closing")
                source_lines.append(lines[index])
                index += 1
            if index == len(lines):
                raise ValueError(f"{document}:{start_line}: unclosed fenced block")
            if language == "python":
                if pending_marker is None:
                    raise ValueError(f"{document}:{start_line}: unclassified Python block")
                classification = "example" if pending_marker == _EXAMPLE_MARKER else "signature"
                blocks.append(PythonBlock(classification, "\n".join(source_lines) + "\n", start_line))
            elif pending_marker is not None:
                raise ValueError(f"{document}:{start_line}: marker must precede a Python block")
            pending_marker = None
            index += 1
            continue
        if pending_marker is not None and line.strip():
            raise ValueError(f"{document}:{index + 1}: marker must immediately precede a Python block")
        index += 1
    if pending_marker is not None:
        raise ValueError(f"{document}: marker has no Python block")
    return blocks


def _documented_python_blocks() -> list[tuple[Path, PythonBlock]]:
    """Read all checked documentation and retain source locations for failures."""
    return [
        (document, block)
        for document in _DOCUMENTS
        for block in extract_python_blocks(document.read_text(encoding="utf-8"), document)
    ]


def test_documentation_classifies_every_python_block() -> None:
    """The checked documents retain eight runnable examples and six signatures."""
    blocks = _documented_python_blocks()
    assert sum(block.classification == "example" for _, block in blocks) == 8
    assert sum(block.classification == "signature" for _, block in blocks) == 6


@pytest.mark.parametrize(
    ("document", "block"),
    [(document, block) for document, block in _documented_python_blocks() if block.classification == "example"],
    ids=lambda value: value.name if isinstance(value, Path) else f"line-{value.line}",
)
def test_documented_example_runs_from_a_neutral_directory(document: Path, block: PythonBlock, python_runner) -> None:
    """Each runnable documentation example succeeds through the selected package target."""
    result = python_runner(block.source, capture_output=True, text=True)
    assert result.returncode == 0, f"{document}:{block.line}\n{result.stderr}"


@pytest.mark.parametrize(
    ("document", "block"),
    [(document, block) for document, block in _documented_python_blocks() if block.classification == "signature"],
    ids=lambda value: value.name if isinstance(value, Path) else f"line-{value.line}",
)
def test_documented_signature_parses(document: Path, block: PythonBlock) -> None:
    """Signature-only blocks remain valid Python without being executed as examples."""
    parsed = ast.parse(block.source.rstrip() + ":\n    pass\n", filename=f"{document}:{block.line}")
    assert len(parsed.body) == 1
    assert isinstance(parsed.body[0], ast.FunctionDef)


def test_broken_documentation_example_fails_in_the_selected_interpreter(python_runner) -> None:
    """A syntax error in a runnable block cannot silently pass the example check."""
    result = python_runner("def broken(\n", capture_output=True, text=True)
    assert result.returncode != 0
    assert "SyntaxError" in result.stderr


@pytest.mark.parametrize(
    ("markdown", "message"),
    [
        ("```python\nprint('missing')\n```\n", "unclassified Python block"),
        (f"{_EXAMPLE_MARKER}\n\n```text\ntext\n```\n", "marker must precede a Python block"),
        (f"{_SIGNATURE_MARKER}\ncontent\n```python\ndef value(): pass\n```\n", "marker must immediately precede"),
        (f"{_EXAMPLE_MARKER}\n{_SIGNATURE_MARKER}\n", "consecutive Python block markers"),
        ("```python\nprint('unfinished')\n", "unclosed fenced block"),
        (f"{_SIGNATURE_MARKER}\n", "marker has no Python block"),
        ("```Python\ndef broken(\n```\n", "unsupported Python fence spelling"),
        ("```PYTHON\ndef broken(\n```\n", "unsupported Python fence spelling"),
        ("```python3\ndef broken(\n```\n", "unsupported Python fence spelling"),
        ("```python linenums\ndef broken(\n```\n", "unsupported Python fence spelling"),
        ('```python title="broken"\ndef broken(\n```\n', "unsupported Python fence spelling"),
        (" ```python\ndef broken(\n ```\n", "unsupported Python fence spelling"),
        ("````python\ndef broken(\n````\n", "unsupported Python fence spelling"),
        ("~~~python\ndef broken(\n~~~\n", "unsupported Python fence spelling"),
    ],
)
def test_extractor_rejects_missing_and_invalid_markers(tmp_path: Path, markdown: str, message: str) -> None:
    """A new Python block must be classified and a marker must name a Python fence."""
    document = tmp_path / "document.md"
    with pytest.raises(ValueError, match=message):
        extract_python_blocks(markdown, document)
