"""Tests for the chunker."""
import pytest
from app.core.chunker import chunk_file, _sliding_window
from app.core.parsers.base import ParseResult, SymbolInfo


PYTHON_SOURCE = """\
def greet(name):
    '''Greet someone.'''
    return f"Hello, {name}"


def farewell(name):
    return f"Goodbye, {name}"


class Greeter:
    def hello(self):
        return "hi"
"""


def test_symbol_chunks():
    """Each symbol should produce its own chunk."""
    from app.core.parsers.python_parser import parse_python
    pr = parse_python(PYTHON_SOURCE)
    chunks = chunk_file(PYTHON_SOURCE, "test.py", pr, language="python")
    symbol_names = [c.symbol_name for c in chunks if c.symbol_name]
    assert "greet" in symbol_names
    assert "farewell" in symbol_names


def test_sliding_window_overlap():
    """Sliding window should produce overlapping chunks."""
    lines = [f"line {i}" for i in range(100)]
    chunks = _sliding_window(lines, "test.py", "python", window=60, overlap=10)
    assert len(chunks) >= 2
    # Second chunk should start before first chunk ends
    assert chunks[1].start_line < chunks[0].end_line + 1


def test_sliding_window_no_gap():
    """All lines should be covered."""
    lines = [f"line {i}" for i in range(50)]
    chunks = _sliding_window(lines, "test.py", "python", window=20, overlap=5)
    # All lines 1..50 should appear in at least one chunk
    covered = set()
    for c in chunks:
        for i in range(c.start_line, c.end_line + 1):
            covered.add(i)
    for i in range(1, 51):
        assert i in covered


def test_empty_file():
    chunks = chunk_file("", "test.py", None)
    assert chunks == []


def test_markdown_heading_split():
    md = """\
# Introduction

Some text here.

## Section 1

Content of section 1.

## Section 2

Content of section 2.
"""
    chunks = chunk_file(md, "README.md", None)
    assert len(chunks) >= 3  # One per heading


def test_chunk_line_numbers():
    """Chunks should have valid start/end line numbers."""
    from app.core.parsers.python_parser import parse_python
    pr = parse_python(PYTHON_SOURCE)
    chunks = chunk_file(PYTHON_SOURCE, "test.py", pr)
    for c in chunks:
        assert c.start_line >= 1
        assert c.end_line >= c.start_line


def test_large_symbol_capped():
    """Symbols > 200 lines should be capped."""
    long_body = "\n".join(f"    x = {i}" for i in range(250))
    source = f"def huge_func():\n{long_body}\n"
    from app.core.parsers.python_parser import parse_python
    pr = parse_python(source)
    chunks = chunk_file(source, "test.py", pr)
    sym_chunks = [c for c in chunks if c.symbol_name == "huge_func"]
    assert sym_chunks
    assert sym_chunks[0].end_line - sym_chunks[0].start_line <= 200
