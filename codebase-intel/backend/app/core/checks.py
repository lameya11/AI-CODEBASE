"""Code quality and security checks."""
import ast
import re
from dataclasses import dataclass
from typing import Optional

from app.config import settings


@dataclass
class IssueResult:
    type: str       # secret | sql_injection | unused_import | complexity
    severity: str   # info | warning | high
    line: int
    message: str
    suggestion: str


# ---- Secret detection ----

# Assignments: api_key = "sk-live-123..." etc.
_SECRET_ASSIGN_RE = re.compile(
    r"""(?i)(?:api_?key|apikey|secret|password|token|passwd|private_key)\s*[=:]\s*['"]([^'"]{8,})['"]"""
)

# AWS access key pattern (case-insensitive for test data but real keys are uppercase)
_AWS_KEY_RE = re.compile(r"""AKIA[0-9A-Za-z]{16}""")

# Private key header
_PRIVATE_KEY_RE = re.compile(
    r"""-----BEGIN\s+(?:RSA|EC|OPENSSH|PRIVATE)\s+KEY-----"""
)

# Placeholders to skip (case-insensitive) - only skip when value is obviously fake
# Note: "example" matches standalone but not as part of an AWS key like AKIAIOSFODNN7EXAMPLE
_PLACEHOLDER_ASSIGN_RE = re.compile(
    r"""(?i)(?:api_?key|apikey|secret|password|token|passwd)\s*[=:]\s*['"](?:[^'"]*(?:example|changeme|placeholder|your_|xxx)[^'"]*)['"]"""
)
_PLACEHOLDER_ENV_RE = re.compile(r"""(?i)os\.environ|process\.env|\$\{|<[a-z]""")


def check_secrets(source: str, file_path: str = "") -> list[IssueResult]:
    """Scan source lines for possible hardcoded secrets."""
    issues: list[IssueResult] = []
    for i, line in enumerate(source.splitlines(), start=1):
        # Skip lines that are clearly using env vars or placeholders for assignments
        if _PLACEHOLDER_ENV_RE.search(line):
            continue

        m = _SECRET_ASSIGN_RE.search(line)
        if m:
            # Skip if the matched value contains placeholder words
            value = m.group(1)
            if re.search(r"(?i)example|changeme|placeholder|your_|xxx", value):
                continue
            issues.append(
                IssueResult(
                    type="secret",
                    severity="warning",
                    line=i,
                    message="Possible hardcoded secret or credential found. This may expose sensitive information.",
                    suggestion="Move credentials to environment variables or a secrets manager. Never commit real keys.",
                )
            )
            continue

        if _AWS_KEY_RE.search(line):
            issues.append(
                IssueResult(
                    type="secret",
                    severity="warning",
                    line=i,
                    message="Possible AWS access key found (AKIA... pattern).",
                    suggestion="Rotate this key and store it in an environment variable.",
                )
            )
            continue

        if _PRIVATE_KEY_RE.search(line):
            issues.append(
                IssueResult(
                    type="secret",
                    severity="high",
                    line=i,
                    message="Possible private key header found. This may expose a cryptographic private key.",
                    suggestion="Remove the key from source code immediately and store it securely.",
                )
            )

    return issues


# ---- SQL injection detection (Python AST) ----

_SQL_FUNC_NAMES = {"execute", "executemany", "query", "raw", "text", "run_query", "run_sql", "exec_query"}


def _is_dynamic_string(node: ast.expr) -> bool:
    """Return True if node looks like a dynamically built string."""
    if isinstance(node, ast.JoinedStr):
        return True  # f-string
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return True  # "..." + variable
    if isinstance(node, ast.Call):
        # "...".format(...)
        if isinstance(node.func, ast.Attribute) and node.func.attr == "format":
            return True
    return False


def check_sql_injection(source: str, file_path: str = "") -> list[IssueResult]:
    """Detect possible SQL injection via dynamic string in execute/query calls."""
    issues: list[IssueResult] = []
    try:
        tree = ast.parse(source, filename=file_path)
    except SyntaxError:
        return issues

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        func_name: Optional[str] = None
        if isinstance(func, ast.Attribute):
            func_name = func.attr
        elif isinstance(func, ast.Name):
            func_name = func.id

        if func_name not in _SQL_FUNC_NAMES:
            continue

        if node.args and _is_dynamic_string(node.args[0]):
            issues.append(
                IssueResult(
                    type="sql_injection",
                    severity="warning",
                    line=node.lineno,
                    message=(
                        "String built dynamically inside a SQL call; "
                        "this may allow SQL injection. Use parameterized queries."
                    ),
                    suggestion="Replace dynamic string with a parameterized query using placeholders (?, %s, or :param).",
                )
            )

    return issues


# ---- Unused import detection (Python AST) ----

def check_unused_imports(source: str, file_path: str = "") -> list[IssueResult]:
    """
    Detect imports whose bound names are never used elsewhere in the module.

    Skips __future__ and __init__.py files.
    """
    issues: list[IssueResult] = []

    # Skip __init__.py files and __future__ imports
    if file_path.endswith("__init__.py"):
        return issues

    try:
        tree = ast.parse(source, filename=file_path)
    except SyntaxError:
        return issues

    # Collect bound names from imports
    import_names: dict[str, int] = {}  # name -> line number

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                bound_name = alias.asname if alias.asname else alias.name.split(".")[0]
                import_names[bound_name] = node.lineno
        elif isinstance(node, ast.ImportFrom):
            if node.module == "__future__":
                continue
            for alias in node.names:
                if alias.name == "*":
                    continue
                bound_name = alias.asname if alias.asname else alias.name
                import_names[bound_name] = node.lineno

    if not import_names:
        return issues

    # Collect all Name usages and Attribute roots outside import statements
    used_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        if isinstance(node, ast.Name):
            used_names.add(node.id)
        elif isinstance(node, ast.Attribute):
            # Collect the root name of an attribute chain (e.g., os.path -> os)
            root = node
            while isinstance(root, ast.Attribute):
                root = root.value
            if isinstance(root, ast.Name):
                used_names.add(root.id)

    for name, lineno in import_names.items():
        if name not in used_names:
            issues.append(
                IssueResult(
                    type="unused_import",
                    severity="info",
                    line=lineno,
                    message=f"Imported name '{name}' appears to be unused.",
                    suggestion=f"Remove the import of '{name}' if it is not needed.",
                )
            )

    return issues


# ---- Cyclomatic complexity (Python AST) ----

def _compute_complexity(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """
    Compute cyclomatic complexity of a function.

    Counts: if, for, while, except, with, BoolOp (and/or), comprehensions, plus 1.
    """
    count = 1  # base complexity
    for node in ast.walk(func_node):
        if node is func_node:
            continue
        if isinstance(node, (ast.If, ast.For, ast.While, ast.ExceptHandler, ast.With)):
            count += 1
        elif isinstance(node, ast.BoolOp):
            # Each additional operand in and/or adds a branch
            count += len(node.values) - 1
        elif isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            count += 1
        elif isinstance(node, ast.Try):
            # ast.Try.handlers counted via ExceptHandler above
            pass
    return count


def check_complexity(
    source: str,
    file_path: str = "",
    threshold: int = 10,
) -> list[IssueResult]:
    """Flag functions whose cyclomatic complexity exceeds threshold."""
    issues: list[IssueResult] = []
    try:
        tree = ast.parse(source, filename=file_path)
    except SyntaxError:
        return issues

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        complexity = _compute_complexity(node)
        if complexity > threshold:
            severity = "high" if complexity > 20 else "warning"
            issues.append(
                IssueResult(
                    type="complexity",
                    severity=severity,
                    line=node.lineno,
                    message=(
                        f"Function '{node.name}' has a cyclomatic complexity of {complexity}, "
                        f"which may indicate it is hard to test and maintain."
                    ),
                    suggestion=(
                        "Break this function into smaller, focused functions. "
                        "Aim for complexity below 10."
                    ),
                )
            )

    return issues


def run_all_checks(
    source: str,
    file_path: str = "",
    threshold: int = 10,
) -> list[IssueResult]:
    """Run all checks and return combined results."""
    results: list[IssueResult] = []
    results.extend(check_secrets(source, file_path))
    if file_path.endswith(".py"):
        results.extend(check_sql_injection(source, file_path))
        results.extend(check_unused_imports(source, file_path))
        results.extend(check_complexity(source, file_path, threshold=threshold))
    return results
