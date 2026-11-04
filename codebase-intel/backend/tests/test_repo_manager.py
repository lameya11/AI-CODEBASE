"""Tests for the repository manager."""
import io
import tempfile
import zipfile
from pathlib import Path
import pytest

from app.core.repo_manager import validate_github_url, extract_zip


# ---- GitHub URL validation ----

def test_valid_github_url():
    assert validate_github_url("https://github.com/owner/repo") is True


def test_valid_github_url_with_git():
    assert validate_github_url("https://github.com/owner/repo.git") is True


def test_invalid_github_url_http():
    assert validate_github_url("http://github.com/owner/repo") is False


def test_invalid_github_url_other_host():
    assert validate_github_url("https://gitlab.com/owner/repo") is False


def test_invalid_github_url_subdirectory():
    assert validate_github_url("https://github.com/owner/repo/tree/main") is False


def test_invalid_github_url_missing_repo():
    assert validate_github_url("https://github.com/owner") is False


def test_invalid_github_url_empty():
    assert validate_github_url("") is False


# ---- ZIP extraction ----

def _make_zip(entries: list[tuple[str, bytes]]) -> Path:
    """Create a ZIP file in a temp location and return its path."""
    tmp = Path(tempfile.mktemp(suffix=".zip"))
    with zipfile.ZipFile(tmp, "w") as zf:
        for name, content in entries:
            zf.writestr(name, content)
    return tmp


def test_normal_zip_extraction():
    z = _make_zip([
        ("app/main.py", b"print('hello')"),
        ("README.md", b"# Hello"),
    ])
    dest = Path(tempfile.mkdtemp())
    try:
        extract_zip(z, dest)
        assert (dest / "app" / "main.py").exists()
        assert (dest / "README.md").exists()
    finally:
        z.unlink(missing_ok=True)
        import shutil; shutil.rmtree(dest, ignore_errors=True)


def test_zip_path_traversal_rejected():
    """ZIP with ../path should be rejected."""
    z = _make_zip([
        ("../evil.py", b"malicious"),
    ])
    dest = Path(tempfile.mkdtemp())
    try:
        with pytest.raises(ValueError, match="traversal|unsafe"):
            extract_zip(z, dest)
    finally:
        z.unlink(missing_ok=True)
        import shutil; shutil.rmtree(dest, ignore_errors=True)


def test_zip_absolute_path_rejected():
    """ZIP with absolute path entry should be rejected."""
    z = Path(tempfile.mktemp(suffix=".zip"))
    # Build a zip with a manual absolute path entry bypassing safety
    with zipfile.ZipFile(z, "w") as zf:
        info = zipfile.ZipInfo("/etc/evil.py")
        zf.writestr(info, b"bad content")
    dest = Path(tempfile.mkdtemp())
    try:
        with pytest.raises(ValueError, match="absolute|unsafe"):
            extract_zip(z, dest)
    finally:
        z.unlink(missing_ok=True)
        import shutil; shutil.rmtree(dest, ignore_errors=True)


def test_zip_oversize_rejected():
    """ZIP that exceeds max bytes should be rejected."""
    # Create a ZIP with one file that's slightly over limit
    large_content = b"x" * 200
    z = _make_zip([("big.bin", large_content)])
    dest = Path(tempfile.mkdtemp())
    try:
        with pytest.raises(ValueError, match="size"):
            extract_zip(z, dest, max_total_bytes=100)
    finally:
        z.unlink(missing_ok=True)
        import shutil; shutil.rmtree(dest, ignore_errors=True)


def test_non_zip_rejected():
    """Non-ZIP file should raise ValueError."""
    tmp = Path(tempfile.mktemp(suffix=".zip"))
    tmp.write_bytes(b"this is not a zip file")
    dest = Path(tempfile.mkdtemp())
    try:
        with pytest.raises((ValueError, zipfile.BadZipFile)):
            extract_zip(tmp, dest)
    finally:
        tmp.unlink(missing_ok=True)
        import shutil; shutil.rmtree(dest, ignore_errors=True)
