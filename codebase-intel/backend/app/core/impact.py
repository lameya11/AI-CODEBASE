"""Impact analysis: reverse BFS on the file dependency graph."""
from collections import deque
from typing import Optional

import networkx as nx

# Entry point patterns indicating high-impact files
_ENTRY_POINT_NAMES = {"main.py", "app.py", "index.py", "server.py"}
_ENTRY_POINT_PREFIXES = ("index.", "App.")

# Path fragments that indicate database/auth modules
_HIGH_IMPACT_FRAGMENTS = {"database", "db", "auth", "session", "security", "models"}


def _is_high_impact_file(file_path: str) -> bool:
    """Return True if this file is inherently high-impact by name/role."""
    filename = file_path.split("/")[-1].lower()

    # Entry points
    if filename in _ENTRY_POINT_NAMES:
        return True
    for prefix in _ENTRY_POINT_PREFIXES:
        if filename.startswith(prefix.lower()):
            return True

    # Database / auth modules
    name_without_ext = filename.rsplit(".", 1)[0]
    if name_without_ext in _HIGH_IMPACT_FRAGMENTS:
        return True
    for fragment in _HIGH_IMPACT_FRAGMENTS:
        if fragment in file_path.lower():
            return True

    return False


def analyze_impact(
    target: str,
    file_graph: nx.DiGraph,
    parse_results: dict | None = None,
    max_depth: int = 4,
) -> dict:
    """
    Perform reverse BFS to find all files that import (directly or indirectly)
    the target file.

    Args:
        target:       The file path to analyze (relative, forward slashes).
        file_graph:   The file-level DiGraph (edges: importer -> imported).
        parse_results: Optional parse results to check for route symbols.
        max_depth:    Maximum BFS depth (capped at 10 in the API layer).

    Returns a dict with keys:
        target, level, total_affected, direct, indirect,
        affected_paths, explanation, disclaimer
    """
    max_depth = min(max_depth, 10)

    # Reverse graph: edge means "is imported by"
    rev = file_graph.reverse(copy=False)

    # BFS
    visited: set[str] = set()
    queue: deque[tuple[str, int, str]] = deque()  # (node, depth, via)
    queue.append((target, 0, target))
    visited.add(target)

    direct: list[dict] = []
    indirect: list[dict] = []

    while queue:
        node, depth, via = queue.popleft()

        # Don't expand beyond max_depth
        if depth >= max_depth:
            continue

        for predecessor in rev.successors(node):
            if predecessor in visited:
                continue
            # Skip external nodes
            if file_graph.nodes.get(predecessor, {}).get("is_external"):
                continue
            visited.add(predecessor)
            new_depth = depth + 1
            entry = {
                "file_path": predecessor,
                "depth": new_depth,
                "distance_via": via,
            }
            if new_depth == 1:
                direct.append(entry)
            else:
                indirect.append(entry)
            queue.append((predecessor, new_depth, predecessor))

    affected_count = len(direct) + len(indirect)

    # Determine impact level
    has_route = False
    if parse_results:
        target_result = parse_results.get(target)
        if target_result:
            has_route = any(s.kind == "route" for s in target_result.symbols)

    is_critical = _is_high_impact_file(target)
    if affected_count >= 10 or is_critical or has_route:
        level = "high"
    elif affected_count >= 3:
        level = "medium"
    else:
        level = "low"

    # Build explanation
    role = ""
    if is_critical:
        role = " (entry point or core module)"
    elif has_route:
        role = " (route file)"

    if affected_count == 0:
        explanation = f"Changing '{target}'{role} affects no other files within the analyzed depth."
    elif affected_count == 1:
        explanation = (
            f"Changing '{target}'{role} directly affects 1 file. "
            f"Impact level is {level}."
        )
    else:
        explanation = (
            f"Changing '{target}'{role} affects {len(direct)} file(s) directly "
            f"and {len(indirect)} file(s) indirectly ({affected_count} total). "
            f"Impact level is {level}."
        )

    return {
        "target": target,
        "level": level,
        "total_affected": affected_count,
        "direct": direct,
        "indirect": indirect,
        "affected_paths": [e["file_path"] for e in direct + indirect],
        "explanation": explanation,
        "disclaimer": (
            "Estimate based on static imports and calls. "
            "Runtime and dynamic dependencies are not detected."
        ),
    }
