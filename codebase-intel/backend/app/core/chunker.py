"""Code chunker: symbol-based and sliding-window chunking."""
from dataclasses import dataclass
from typing import Optional
import re

from app.core.parsers.base import ParseResult, SymbolInfo

MAX_SYMBOL_LINES = 200
WINDOW_SIZE = 60
WINDOW_OVERLAP = 10


@dataclass
class Chunk:
    """A single code chunk ready for embedding."""
    file_path: str
    symbol_name: Optional[str]
    start_line: int
    end_line: int
    language: Optional[str]
    text: str


def _sliding_window(
    lines: list[str],
    file_path: str,
    language: Optional[str],
    window: int = WINDOW_SIZE,
    overlap: int = WINDOW_OVERLAP,
) -> list[Chunk]:
    """Produce overlapping window chunks over a list of lines (1-indexed output)."""
    chunks: list[Chunk] = []
    n = len(lines)
    if n == 0:
        return chunks

    step = window - overlap
    if step <= 0:
        step = 1

    start = 0
    while start < n:
        end = min(start + window, n)
        text = "\n".join(lines[start:end])
        chunks.append(
            Chunk(
                file_path=file_path,
                symbol_name=None,
                start_line=start + 1,      # 1-based
                end_line=end,              # 1-based inclusive
                language=language,
                text=text,
            )
        )
        if end == n:
            break
        start += step

    return chunks


def _split_by_headings(
    source: str,
    file_path: str,
) -> list[Chunk]:
    """Split a Markdown file by headings, fallback to sliding window."""
    heading_re = re.compile(r"^#{1,6}\s+", re.MULTILINE)
    lines = source.splitlines()
    if not lines:
        return []

    # Find heading positions
    heading_lines: list[int] = []
    for i, line in enumerate(lines):
        if heading_re.match(line):
            heading_lines.append(i)

    if not heading_lines:
        return _sliding_window(lines, file_path, "markdown")

    chunks: list[Chunk] = []
    boundaries = heading_lines + [len(lines)]
    for i, start_idx in enumerate(boundaries[:-1]):
        end_idx = boundaries[i + 1]
        section_lines = lines[start_idx:end_idx]
        if not section_lines:
            continue
        # If section is large, sub-chunk with sliding window
        if len(section_lines) > WINDOW_SIZE:
            sub = _sliding_window(section_lines, file_path, "markdown")
            # Adjust line numbers
            for c in sub:
                c.start_line += start_idx
                c.end_line += start_idx
            chunks.extend(sub)
        else:
            chunks.append(
                Chunk(
                    file_path=file_path,
                    symbol_name=None,
                    start_line=start_idx + 1,
                    end_line=end_idx,
                    language="markdown",
                    text="\n".join(section_lines),
                )
            )

    return chunks


def chunk_file(
    source: str,
    file_path: str,
    parse_result: Optional[ParseResult],
    language: Optional[str] = None,
) -> list[Chunk]:
    """
    Produce chunks for one file.

    Strategy:
      - Markdown: split by headings, fallback to sliding window.
      - Supported code with symbols: one chunk per symbol (capped at 200 lines),
        then sliding window for uncovered regions.
      - Supported code without symbols: sliding window.
      - Unsupported files: sliding window.
    """
    if file_path.endswith(".md"):
        return _split_by_headings(source, file_path)

    lines = source.splitlines()
    if not lines:
        return []

    lang = language or (parse_result.language if parse_result else None)

    if not parse_result or not parse_result.symbols:
        return _sliding_window(lines, file_path, lang)

    chunks: list[Chunk] = []
    covered: set[int] = set()  # 0-based line indices

    for sym in parse_result.symbols:
        start_idx = sym.start_line - 1   # convert to 0-based
        end_idx = sym.end_line           # exclusive 0-based = end_line (inclusive 1-based)

        # Cap at 200 lines
        if (end_idx - start_idx) > MAX_SYMBOL_LINES:
            end_idx = start_idx + MAX_SYMBOL_LINES

        end_idx = min(end_idx, len(lines))
        text = "\n".join(lines[start_idx:end_idx])
        chunks.append(
            Chunk(
                file_path=file_path,
                symbol_name=sym.name,
                start_line=sym.start_line,
                end_line=end_idx,        # 1-based inclusive
                language=lang,
                text=text,
            )
        )
        for idx in range(start_idx, end_idx):
            covered.add(idx)

    # Fill gaps with sliding window
    uncovered: list[tuple[int, int]] = []
    gap_start: Optional[int] = None
    for idx in range(len(lines)):
        if idx not in covered:
            if gap_start is None:
                gap_start = idx
        else:
            if gap_start is not None:
                uncovered.append((gap_start, idx))
                gap_start = None
    if gap_start is not None:
        uncovered.append((gap_start, len(lines)))

    for gap_s, gap_e in uncovered:
        gap_lines = lines[gap_s:gap_e]
        if not gap_lines:
            continue
        sub = _sliding_window(gap_lines, file_path, lang)
        for c in sub:
            c.start_line += gap_s
            c.end_line += gap_s
        chunks.extend(sub)

    return chunks
