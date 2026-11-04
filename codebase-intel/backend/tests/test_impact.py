"""Tests for impact analysis."""
import pytest
import networkx as nx
from app.core.impact import analyze_impact, _is_high_impact_file


def _build_graph(edges: list[tuple[str, str]], nodes: list[str] | None = None) -> nx.DiGraph:
    """Build a simple test graph."""
    G = nx.DiGraph()
    if nodes:
        for n in nodes:
            G.add_node(n, is_external=False)
    for src, tgt in edges:
        G.add_node(src, is_external=False)
        G.add_node(tgt, is_external=False)
        G.add_edge(src, tgt)
    return G


def test_direct_dependent():
    """main.py imports auth.py; auth.py is affected by changes to users.py."""
    G = _build_graph([
        ("app/main.py", "app/auth.py"),
        ("app/auth.py", "app/users.py"),
    ])
    result = analyze_impact("app/users.py", G)
    direct_paths = [d["file_path"] for d in result["direct"]]
    assert "app/auth.py" in direct_paths


def test_indirect_dependent():
    G = _build_graph([
        ("app/main.py", "app/auth.py"),
        ("app/auth.py", "app/users.py"),
        ("app/users.py", "app/database.py"),
    ])
    result = analyze_impact("app/database.py", G)
    indirect_paths = [d["file_path"] for d in result["indirect"]]
    assert "app/main.py" in indirect_paths


def test_cycle_safety():
    """Circular dependencies should not cause infinite loops."""
    G = _build_graph([
        ("a.py", "b.py"),
        ("b.py", "c.py"),
        ("c.py", "a.py"),  # cycle
    ])
    result = analyze_impact("a.py", G)
    # Should complete without infinite loop
    assert result["total_affected"] >= 0


def test_max_depth_respected():
    """Impact should not exceed max_depth."""
    G = _build_graph([
        ("a.py", "b.py"),
        ("b.py", "c.py"),
        ("c.py", "d.py"),
        ("d.py", "e.py"),
    ])
    result = analyze_impact("e.py", G, max_depth=2)
    # Only depth 1 and 2 should be in results
    all_depths = [d["depth"] for d in result["direct"] + result["indirect"]]
    assert all(d <= 2 for d in all_depths)


def test_level_low():
    """Less than 3 affected files -> low."""
    G = _build_graph([("a.py", "b.py")])
    result = analyze_impact("b.py", G)
    assert result["level"] == "low"


def test_level_medium():
    """3-9 affected files -> medium."""
    G = _build_graph([(f"a{i}.py", "target.py") for i in range(5)])
    result = analyze_impact("target.py", G)
    assert result["level"] == "medium"


def test_level_high_count():
    """10+ affected files -> high."""
    G = _build_graph([(f"a{i}.py", "target.py") for i in range(12)])
    result = analyze_impact("target.py", G)
    assert result["level"] == "high"


def test_level_high_database():
    """database.py -> high regardless of affected count."""
    G = _build_graph([("a.py", "app/database.py")])
    result = analyze_impact("app/database.py", G)
    assert result["level"] == "high"


def test_level_high_main():
    """main.py -> high (entry point)."""
    G = _build_graph([], nodes=["main.py"])
    result = analyze_impact("main.py", G)
    assert result["level"] == "high"


def test_external_excluded():
    """External nodes should not appear in affected lists."""
    G = nx.DiGraph()
    G.add_node("app/main.py", is_external=False)
    G.add_node("<external>/fastapi", is_external=True)
    G.add_edge("app/main.py", "<external>/fastapi")
    # Also add an internal dep
    G.add_node("app/auth.py", is_external=False)
    G.add_edge("app/main.py", "app/auth.py")

    result = analyze_impact("app/auth.py", G)
    affected = result["affected_paths"]
    assert not any("<external>" in p for p in affected)


def test_high_impact_file_auth():
    assert _is_high_impact_file("app/auth.py") is True


def test_high_impact_file_db():
    assert _is_high_impact_file("app/db.py") is True


def test_high_impact_entry_point():
    assert _is_high_impact_file("main.py") is True


def test_low_impact_file():
    assert _is_high_impact_file("utils/format.py") is False
