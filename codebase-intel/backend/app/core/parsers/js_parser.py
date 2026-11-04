"""JavaScript/TypeScript parser using regex (best-effort)."""
import re
from typing import Optional

from app.core.parsers.base import CallInfo, ImportInfo, ParseResult, SymbolInfo

# ---- import patterns ----
_RE_IMPORT_FROM = re.compile(
    r"""import\s+(?:(?:type\s+)?(?:\*\s+as\s+\w+|\{[^}]*\}|\w+)(?:\s*,\s*(?:\{[^}]*\}|\w+))?)\s+from\s+['"]([^'"]+)['"]""",
    re.MULTILINE,
)
_RE_REQUIRE = re.compile(r"""require\s*\(\s*['"]([^'"]+)['"]\s*\)""")
_RE_EXPORT_FROM = re.compile(
    r"""export\s+(?:\*|(?:\{[^}]*\}))\s+from\s+['"]([^'"]+)['"]""", re.MULTILINE
)
_RE_IMPORT_BARE = re.compile(
    r"""import\s+['"]([^'"]+)['"]""", re.MULTILINE
)

# ---- function patterns ----
_RE_FUNC_DECL = re.compile(r"""^(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(""", re.MULTILINE)
_RE_ARROW_FUNC = re.compile(
    r"""^(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?(?:\([^)]*\)|[^=\s]+)\s*=>""",
    re.MULTILINE,
)
_RE_FUNC_EXPR = re.compile(
    r"""^(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?function""",
    re.MULTILINE,
)
_RE_DEFAULT_FUNC = re.compile(
    r"""^export\s+default\s+(?:async\s+)?function(?:\s+(\w+))?\s*\(""", re.MULTILINE
)

# ---- class pattern ----
_RE_CLASS = re.compile(r"""^(?:export\s+)?(?:default\s+)?class\s+(\w+)""", re.MULTILINE)

# ---- route patterns ----
_RE_ROUTE = re.compile(
    r"""(?:router|app)\.(get|post|put|delete|patch)\s*\(\s*['"]([^'"]+)['"]""",
    re.IGNORECASE,
)

# ---- call pattern ----
_RE_CALL = re.compile(r"""(\w+)\s*\(""")


def _find_end_line(lines: list[str], start: int) -> int:
    """
    Find the closing brace of a block starting near `start` (1-based line number).
    Uses brace counting. Returns the line where depth returns to 0, or EOF.
    """
    depth = 0
    found_open = False
    for i, line in enumerate(lines[start - 1 :], start=start):
        depth += line.count("{") - line.count("}")
        if depth > 0:
            found_open = True
        if found_open and depth <= 0:
            return i
    return len(lines)


def _is_jsx_or_tsx(file_path: str) -> bool:
    return file_path.endswith((".jsx", ".tsx"))


def parse_js(source: str, file_path: str = "<unknown>") -> ParseResult:
    """Parse JavaScript/TypeScript source using regex patterns (best-effort)."""
    lines = source.splitlines()
    is_jsx = _is_jsx_or_tsx(file_path)

    imports: list[ImportInfo] = []
    symbols: list[SymbolInfo] = []
    calls: list[CallInfo] = []

    # ---- imports ----
    for m in _RE_IMPORT_FROM.finditer(source):
        imports.append(ImportInfo(module=m.group(1), names=[]))
    for m in _RE_REQUIRE.finditer(source):
        imports.append(ImportInfo(module=m.group(1), names=[]))
    for m in _RE_EXPORT_FROM.finditer(source):
        imports.append(ImportInfo(module=m.group(1), names=[]))
    for m in _RE_IMPORT_BARE.finditer(source):
        imports.append(ImportInfo(module=m.group(1), names=[]))

    # ---- functions and components ----
    def _add_func_symbol(name: str, start: int, source_chunk: str) -> None:
        end = _find_end_line(lines, start)
        is_component = (
            is_jsx
            and name[0].isupper()
            and ("return (" in source_chunk or "<" in source_chunk)
        )
        kind = "component" if is_component else "function"
        sym = SymbolInfo(name=name, kind=kind, start_line=start, end_line=end)
        symbols.append(sym)
        # extract calls within the symbol's lines
        body = "\n".join(lines[start - 1 : end])
        for cm in _RE_CALL.finditer(body):
            callee = cm.group(1)
            if callee not in ("function", "if", "while", "for", "switch", "catch"):
                calls.append(CallInfo(caller_symbol=name, callee=callee))

    for m in _RE_FUNC_DECL.finditer(source):
        start_line = source[: m.start()].count("\n") + 1
        _add_func_symbol(m.group(1), start_line, source)

    for m in _RE_ARROW_FUNC.finditer(source):
        start_line = source[: m.start()].count("\n") + 1
        _add_func_symbol(m.group(1), start_line, source)

    for m in _RE_FUNC_EXPR.finditer(source):
        start_line = source[: m.start()].count("\n") + 1
        _add_func_symbol(m.group(1), start_line, source)

    for m in _RE_DEFAULT_FUNC.finditer(source):
        start_line = source[: m.start()].count("\n") + 1
        name = m.group(1) or "default"
        _add_func_symbol(name, start_line, source)

    # ---- classes ----
    for m in _RE_CLASS.finditer(source):
        start_line = source[: m.start()].count("\n") + 1
        end_line = _find_end_line(lines, start_line)
        symbols.append(
            SymbolInfo(name=m.group(1), kind="class", start_line=start_line, end_line=end_line)
        )

    # ---- routes ----
    for m in _RE_ROUTE.finditer(source):
        start_line = source[: m.start()].count("\n") + 1
        method = m.group(1).upper()
        path = m.group(2)
        # Try to find a nearby function name to attach it to
        func_name = f"route_{method.lower()}_{path.replace('/', '_').strip('_')}"
        symbols.append(
            SymbolInfo(
                name=func_name,
                kind="route",
                start_line=start_line,
                end_line=start_line,
                route_method=method,
                route_path=path,
            )
        )

    # deduplicate imports by module
    seen: set[str] = set()
    unique_imports: list[ImportInfo] = []
    for imp in imports:
        if imp.module not in seen:
            seen.add(imp.module)
            unique_imports.append(imp)

    return ParseResult(
        language="javascript",
        imports=unique_imports,
        symbols=symbols,
        calls=calls,
    )
