"""File scanner: walks a directory, applies ignore rules, detects language."""
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

# Directories to skip entirely
IGNORE_DIRS = {
    ".git", "node_modules", "venv", ".venv", "__pycache__",
    "dist", "build", ".next", "coverage", ".idea", ".vscode",
}

# Lock files and generated assets to skip
IGNORE_FILES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "poetry.lock", "Pipfile.lock",
}

# Image, font and other binary extensions
IGNORE_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico",
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    ".pdf", ".zip", ".tar", ".gz", ".bz2", ".rar",
    ".exe", ".dll", ".so", ".dylib", ".bin",
    ".pyc", ".pyo",
    ".mp4", ".mp3", ".avi", ".mov",
}

SUPPORTED_EXTENSIONS = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".mjs": "javascript",
    ".cjs": "javascript",
}

TEXT_EXTENSIONS = {
    ".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".ini",
    ".cfg", ".env", ".html", ".css", ".xml", ".sh", ".bash",
}


@dataclass
class ScannedFile:
    path: str           # relative path with forward slashes
    absolute_path: Path
    language: Optional[str]
    size: int
    supported: bool


def scan_directory(
    root: Path,
    max_files: int = 2000,
    max_file_bytes: int = 1_048_576,
) -> tuple[list[ScannedFile], bool]:
    """
    Walk `root` and collect files respecting ignore rules and limits.

    Returns (files, hit_cap) where hit_cap is True when MAX_FILES was reached.
    """
    results: list[ScannedFile] = []
    hit_cap = False

    for abs_path in sorted(root.rglob("*")):
        if not abs_path.is_file():
            continue

        # Check if any parent directory is in the ignore set
        rel = abs_path.relative_to(root)
        parts = rel.parts
        if any(p in IGNORE_DIRS for p in parts[:-1]):
            continue
        if parts[0] in IGNORE_DIRS:
            continue

        filename = abs_path.name
        if filename in IGNORE_FILES:
            continue

        ext = abs_path.suffix.lower()
        if ext in IGNORE_EXTENSIONS:
            continue

        size = abs_path.stat().st_size
        if size > max_file_bytes:
            continue

        # Normalize path to forward slashes
        rel_str = "/".join(parts)

        language = SUPPORTED_EXTENSIONS.get(ext)
        supported = language is not None

        results.append(
            ScannedFile(
                path=rel_str,
                absolute_path=abs_path,
                language=language,
                size=size,
                supported=supported,
            )
        )

        if len(results) >= max_files:
            hit_cap = True
            break

    return results, hit_cap


def detect_language(file_path: str) -> Optional[str]:
    """Return the language for a given file path, or None."""
    ext = Path(file_path).suffix.lower()
    return SUPPORTED_EXTENSIONS.get(ext)
