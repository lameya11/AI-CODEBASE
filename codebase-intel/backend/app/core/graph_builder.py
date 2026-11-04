"""Graph builder: file-level and function-level NetworkX DiGraphs."""
from pathlib import Path, PurePosixPath
from typing import Optional

import networkx as nx

from app.core.parsers.base import ImportInfo, ParseResult

# Extensions to try when resolving JS/TS relative imports
_JS_EXTENSIONS = [".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"]


def _resolve_python_import(
    module: str,
    level: int,
    importer_path: str,
    all_paths: set[str],
) -> Optional[str]:
    """
    Try to resolve a Python import to a file path in the repository.

    Returns the relative forward-slash path string if found, else None.

    Handles the case where files are stored with a prefix directory (e.g.,
    backend/app/main.py imports from app.database, and the file is at
    backend/app/database.py). Uses the importer's directory prefix to try
    sibling resolution as well as exact path matching.
    """
    if level > 0:
        # Relative import: go up `level` directories from the importer
        parts = importer_path.split("/")
        # level=1 means same package, level=2 means parent, etc.
        base_parts = parts[: -(level)]  # strip file name and go up
        if module:
            candidate_parts = base_parts + module.split(".")
        else:
            candidate_parts = base_parts
    else:
        if not module:
            return None
        candidate_parts = module.split(".")

    # Try exact path first
    joined = "/".join(candidate_parts)
    for candidate in [f"{joined}.py", f"{joined}/__init__.py"]:
        if candidate in all_paths:
            return candidate

    # Try with the importer's directory prefix (handles ZIP repos with extra top dir)
    # e.g., importer is "backend/app/users.py", module is "app.database"
    # -> try "backend/app/database.py"
    importer_parts = importer_path.split("/")
    # Walk up directories of the importer looking for a match
    for depth in range(1, len(importer_parts)):
        prefix = "/".join(importer_parts[:depth])
        for candidate in [f"{prefix}/{joined}.py", f"{prefix}/{joined}/__init__.py"]:
            if candidate in all_paths:
                return candidate

    return None


def _resolve_js_import(
    specifier: str,
    importer_path: str,
    all_paths: set[str],
) -> Optional[str]:
    """
    Try to resolve a JS/TS relative import specifier to a file in the repo.

    Returns None if the specifier is not relative or the target is not found.
    """
    if not specifier.startswith("."):
        return None  # external package

    importer_dir = "/".join(importer_path.split("/")[:-1])
    # Normalize the path
    base = str(PurePosixPath(importer_dir) / specifier) if importer_dir else specifier.lstrip("./")

    # Try with and without extensions, and index variants
    candidates: list[str] = []
    for ext in _JS_EXTENSIONS:
        candidates.append(f"{base}{ext}")
        candidates.append(f"{base}/index{ext}")

    # Also try the specifier as-is if it already has an extension
    candidates.append(base)

    for c in candidates:
        # Normalize PurePosixPath to remove ".." etc.
        try:
            normalized = str(PurePosixPath(c))
        except Exception:
            continue
        if normalized in all_paths:
            return normalized

    return None


def build_file_graph(
    parse_results: dict[str, ParseResult],
) -> nx.DiGraph:
    """
    Build a file-level directed graph.

    Nodes are file paths. Edges go from importer to imported.
    External dependencies are added as leaf nodes with is_external=True.
    """
    G = nx.DiGraph()
    all_paths = set(parse_results.keys())

    for path in all_paths:
        G.add_node(path, is_external=False, language=parse_results[path].language)

    for importer_path, result in parse_results.items():
        for imp in result.imports:
            # Try to resolve
            if imp.level > 0 or not imp.module.startswith("."):
                resolved = _resolve_python_import(
                    imp.module, imp.level, importer_path, all_paths
                )
            else:
                resolved = None

            if resolved is None and result.language in ("javascript", "typescript"):
                resolved = _resolve_js_import(imp.module, importer_path, all_paths)
            elif resolved is None and result.language == "python":
                resolved = _resolve_python_import(
                    imp.module, imp.level, importer_path, all_paths
                )

            if resolved:
                G.add_edge(importer_path, resolved, kind="import")
            else:
                # External node (group by top-level package name)
                pkg = imp.module.split(".")[0] if imp.module else imp.module
                if pkg and not pkg.startswith("."):
                    ext_node = f"<external>/{pkg}"
                    G.add_node(ext_node, is_external=True, language=None)
                    G.add_edge(importer_path, ext_node, kind="import")

    return G


def build_function_graph(
    parse_results: dict[str, ParseResult],
    file_graph: nx.DiGraph,
) -> nx.DiGraph:
    """
    Build a function-level directed graph.

    Nodes are "file_path::symbol_name". Edges represent calls.
    Best-effort: unresolved calls are dropped.
    """
    G = nx.DiGraph()

    # Build lookup: symbol_name -> set of "file::symbol" nodes
    name_to_nodes: dict[str, list[str]] = {}
    for path, result in parse_results.items():
        for sym in result.symbols:
            node_id = f"{path}::{sym.name}"
            G.add_node(node_id, file_path=path, symbol_name=sym.name, kind=sym.kind)
            name_to_nodes.setdefault(sym.name, []).append(node_id)

    # Build edges from call records
    for path, result in parse_results.items():
        for call in result.calls:
            caller_node = f"{path}::{call.caller_symbol}"
            if caller_node not in G:
                continue
            # Resolve callee: first look in same file, then in imported files
            callee_nodes = _resolve_callee(
                call.callee, path, parse_results, file_graph
            )
            for callee_node in callee_nodes:
                if callee_node in G:
                    G.add_edge(caller_node, callee_node, kind="call")

    return G


def _resolve_callee(
    callee_name: str,
    importer_path: str,
    parse_results: dict[str, ParseResult],
    file_graph: nx.DiGraph,
) -> list[str]:
    """Try to resolve a callee name to function-level graph node(s)."""
    candidates: list[str] = []

    # Same file first
    for sym in parse_results.get(importer_path, ParseResult(language="")).symbols:
        if sym.name == callee_name:
            candidates.append(f"{importer_path}::{callee_name}")

    # Imported files
    for _, target, data in file_graph.out_edges(importer_path, data=True):
        if file_graph.nodes[target].get("is_external"):
            continue
        target_result = parse_results.get(target)
        if not target_result:
            continue
        for sym in target_result.symbols:
            if sym.name == callee_name:
                candidates.append(f"{target}::{callee_name}")

    return candidates
