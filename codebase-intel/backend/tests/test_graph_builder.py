"""Tests for the dependency graph builder."""
import pytest
import networkx as nx
from app.core.graph_builder import build_file_graph, _resolve_python_import, _resolve_js_import
from app.core.parsers.base import ImportInfo, ParseResult


def _make_parse_result(language: str, imports: list[ImportInfo]) -> ParseResult:
    return ParseResult(language=language, imports=imports)


def test_python_file_edge():
    """app/main.py imports from app/auth -> edge should be created."""
    parse_results = {
        "app/main.py": _make_parse_result("python", [
            ImportInfo(module="app.auth", names=["login"], level=0),
        ]),
        "app/auth.py": _make_parse_result("python", []),
        "app/users.py": _make_parse_result("python", []),
    }
    G = build_file_graph(parse_results)
    assert G.has_edge("app/main.py", "app/auth.py")


def test_python_relative_import():
    """Relative import from app/auth.py: 'from .users import ...' -> app/users.py."""
    parse_results = {
        "app/auth.py": _make_parse_result("python", [
            ImportInfo(module="users", names=["find_user"], level=1),
        ]),
        "app/users.py": _make_parse_result("python", []),
    }
    G = build_file_graph(parse_results)
    assert G.has_edge("app/auth.py", "app/users.py")


def test_js_relative_import():
    """JS: import from './api' resolves to src/api.js."""
    parse_results = {
        "src/App.jsx": _make_parse_result("javascript", [
            ImportInfo(module="./api", names=[]),
        ]),
        "src/api.js": _make_parse_result("javascript", []),
    }
    G = build_file_graph(parse_results)
    assert G.has_edge("src/App.jsx", "src/api.js")


def test_external_node_created():
    """External import creates an is_external node."""
    parse_results = {
        "app/main.py": _make_parse_result("python", [
            ImportInfo(module="fastapi", names=["FastAPI"], level=0),
        ]),
    }
    G = build_file_graph(parse_results)
    ext_nodes = [n for n in G.nodes if G.nodes[n].get("is_external")]
    assert len(ext_nodes) >= 1


def test_external_excluded_from_internal():
    """Internal repo files should not have is_external=True."""
    parse_results = {
        "app/main.py": _make_parse_result("python", []),
        "app/auth.py": _make_parse_result("python", []),
    }
    G = build_file_graph(parse_results)
    for path in ["app/main.py", "app/auth.py"]:
        assert not G.nodes[path].get("is_external", False)


def test_resolve_python_import_direct():
    all_paths = {"app/users.py", "app/auth.py", "app/main.py"}
    resolved = _resolve_python_import("app.users", 0, "app/main.py", all_paths)
    assert resolved == "app/users.py"


def test_resolve_python_import_init():
    all_paths = {"app/__init__.py", "app/users.py"}
    resolved = _resolve_python_import("app", 0, "main.py", all_paths)
    assert resolved == "app/__init__.py"


def test_resolve_js_relative():
    all_paths = {"src/api.js", "src/App.jsx"}
    resolved = _resolve_js_import("./api", "src/App.jsx", all_paths)
    assert resolved == "src/api.js"


def test_js_index_resolution():
    all_paths = {"src/components/index.js", "src/App.jsx"}
    resolved = _resolve_js_import("./components", "src/App.jsx", all_paths)
    assert resolved == "src/components/index.js"


def test_graph_has_all_repo_nodes():
    parse_results = {
        "a.py": _make_parse_result("python", []),
        "b.py": _make_parse_result("python", []),
        "c.py": _make_parse_result("python", []),
    }
    G = build_file_graph(parse_results)
    for p in ["a.py", "b.py", "c.py"]:
        assert p in G
