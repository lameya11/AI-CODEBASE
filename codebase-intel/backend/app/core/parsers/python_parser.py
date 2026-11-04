"""Python source file parser using the `ast` module."""
import ast
from pathlib import Path
from typing import Optional

from app.core.parsers.base import CallInfo, ImportInfo, ParseResult, SymbolInfo


def _get_docstring(node: ast.AST) -> Optional[str]:
    """Extract docstring from a function or class node."""
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return None
    if (
        node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
        and isinstance(node.body[0].value.value, str)
    ):
        return node.body[0].value.value.strip()
    return None


def _extract_calls(node: ast.AST) -> list[str]:
    """Collect deduplicated called names from a function body."""
    calls: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            if isinstance(child.func, ast.Name):
                calls.add(child.func.id)
            elif isinstance(child.func, ast.Attribute):
                calls.add(child.func.attr)
    return list(calls)


def _extract_route_decorator(
    decorator: ast.expr,
) -> Optional[tuple[str, str]]:
    """Return (method, path) if the decorator is a FastAPI/Flask route decorator."""
    # Patterns: @app.get("/path"), @router.post("/path"), @name.delete("/path")
    if not isinstance(decorator, ast.Call):
        return None
    func = decorator.func
    if not isinstance(func, ast.Attribute):
        return None
    method = func.attr.lower()
    if method not in ("get", "post", "put", "delete", "patch"):
        return None
    # First positional arg should be a string literal (path)
    if decorator.args and isinstance(decorator.args[0], ast.Constant):
        return method.upper(), str(decorator.args[0].value)
    return None


def parse_python(source: str, file_path: str = "<unknown>") -> ParseResult:
    """Parse Python source and return imports, symbols, calls."""
    try:
        tree = ast.parse(source, filename=file_path)
    except SyntaxError as exc:
        return ParseResult(language="python", parse_error=str(exc))

    imports: list[ImportInfo] = []
    symbols: list[SymbolInfo] = []
    calls: list[CallInfo] = []

    # --- collect imports ---
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(
                    ImportInfo(
                        module=alias.name,
                        alias=alias.asname,
                        names=[alias.asname or alias.name],
                        level=0,
                    )
                )
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            level = node.level or 0
            names = [alias.name for alias in node.names]
            imports.append(
                ImportInfo(module=module, names=names, level=level)
            )

    # --- collect top-level symbols (functions + classes) ---
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            sym = _build_function_symbol(node, parent_name=None)
            symbols.append(sym)
            # calls within this function
            for callee in _extract_calls(node):
                calls.append(CallInfo(caller_symbol=node.name, callee=callee))

        elif isinstance(node, ast.ClassDef):
            class_sym = SymbolInfo(
                name=node.name,
                kind="class",
                start_line=node.lineno,
                end_line=node.end_lineno or node.lineno,
                docstring=_get_docstring(node),
            )
            symbols.append(class_sym)
            # methods
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    method_sym = _build_function_symbol(
                        item, parent_name=node.name
                    )
                    symbols.append(method_sym)
                    for callee in _extract_calls(item):
                        calls.append(
                            CallInfo(
                                caller_symbol=f"{node.name}.{item.name}",
                                callee=callee,
                            )
                        )

    return ParseResult(
        language="python",
        imports=imports,
        symbols=symbols,
        calls=calls,
    )


def _build_function_symbol(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    parent_name: Optional[str],
) -> SymbolInfo:
    """Create a SymbolInfo from a function/async-function AST node."""
    kind = "method" if parent_name else "function"
    route_method: Optional[str] = None
    route_path: Optional[str] = None

    # Check decorators for route annotations
    for decorator in node.decorator_list:
        result = _extract_route_decorator(decorator)
        if result:
            route_method, route_path = result
            kind = "route"
            break

    return SymbolInfo(
        name=node.name,
        kind=kind,
        start_line=node.lineno,
        end_line=node.end_lineno or node.lineno,
        docstring=_get_docstring(node),
        parent_name=parent_name,
        route_method=route_method,
        route_path=route_path,
    )
