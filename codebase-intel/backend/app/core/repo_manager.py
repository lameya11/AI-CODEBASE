"""Repository manager: GitHub clone and ZIP extraction."""
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Optional

from app.core.logging_utils import timed_step

# Strict GitHub URL pattern: https://github.com/owner/repo (no subdirectory)
_GITHUB_RE = re.compile(
    r"^https://github\.com/([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+?)(?:\.git)?/?$"
)


def validate_github_url(url: str) -> bool:
    """Return True if url is a valid GitHub repository URL."""
    return bool(_GITHUB_RE.match(url))


def _build_clone_url(url: str, token: Optional[str]) -> str:
    """Insert GitHub token into URL without logging it."""
    if not token:
        return url
    # https://TOKEN@github.com/owner/repo
    return url.replace("https://", f"https://{token}@", 1)


def _strip_token(text: str, token: Optional[str]) -> str:
    """Remove token from error messages."""
    if token and token in text:
        return text.replace(token, "***")
    return text


def clone_github_repo(url: str, dest: Path, token: Optional[str] = None, timeout: int = 120) -> None:
    """
    Shallow-clone a GitHub repository to `dest`.

    The token is passed via an authenticated URL and is never logged.
    Raises RuntimeError with the token stripped from the message on failure.
    """
    clone_url = _build_clone_url(url, token)
    cmd = ["git", "clone", "--depth", "1", clone_url, str(dest)]

    with timed_step("git_clone"):
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    if result.returncode != 0:
        err = _strip_token(result.stderr or result.stdout, token)
        raise RuntimeError(f"Git clone failed: {err}")


def extract_zip(zip_path: Path, dest: Path, max_total_bytes: int = 209_715_200) -> None:
    """
    Safely extract a ZIP archive.

    Rejects:
    - Entries with absolute paths
    - Entries containing ".." components
    - Symlinks (entries with external attributes indicating symlinks)
    - Total uncompressed size exceeding max_total_bytes

    Raises ValueError on unsafe content, zipfile.BadZipFile on invalid ZIP.
    """
    if not zipfile.is_zipfile(zip_path):
        raise ValueError("File is not a valid ZIP archive")

    with zipfile.ZipFile(zip_path, "r") as zf:
        # Safety checks before extracting anything
        total_size = 0
        for info in zf.infolist():
            name = info.filename

            # Reject absolute paths
            if name.startswith("/") or name.startswith("\\"):
                raise ValueError(f"Unsafe ZIP entry (absolute path): {name}")

            # Reject path traversal
            parts = Path(name).parts
            if ".." in parts:
                raise ValueError(f"Unsafe ZIP entry (path traversal): {name}")

            # Reject symlinks (Unix external attributes)
            # The high 4 bits of external_attr >> 16 hold the Unix file type.
            unix_mode = (info.external_attr >> 16) & 0xF000
            if unix_mode == 0xA000:  # 0xA000 = S_IFLNK
                raise ValueError(f"Unsafe ZIP entry (symlink): {name}")

            total_size += info.file_size
            if total_size > max_total_bytes:
                raise ValueError(
                    f"ZIP total uncompressed size exceeds {max_total_bytes} bytes"
                )

        zf.extractall(dest)

    # If the ZIP extracted into a single top-level directory, use that as root
    # (so the caller sees a consistent layout)
    entries = list(dest.iterdir())
    if len(entries) == 1 and entries[0].is_dir():
        # Move contents up one level
        inner = entries[0]
        for item in inner.iterdir():
            shutil.move(str(item), str(dest / item.name))
        inner.rmdir()
