"""Tests for the repository API endpoints."""
import os
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["DATA_DIR"] = "/tmp/ci_test_api"

from app.main import app
from app.db import init_db


@pytest_asyncio.fixture(scope="module")
async def setup_db():
    await init_db()


@pytest_asyncio.fixture
async def client(setup_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_health(client):
    r = await client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_create_repo_invalid_url(client):
    r = await client.post("/api/repos", json={"source_type": "github", "url": "https://not-github.com/owner/repo"})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_create_repo_invalid_url_subdir(client):
    r = await client.post("/api/repos", json={"source_type": "github", "url": "https://github.com/owner/repo/tree/main"})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_create_repo_valid(client):
    """Creating a valid repo should return 202."""
    r = await client.post("/api/repos", json={
        "source_type": "github",
        "url": "https://github.com/owner/testrepo",
    })
    assert r.status_code == 202
    data = r.json()
    assert data["status"] == "queued"
    assert data["id"]
    return data["id"]


@pytest.mark.asyncio
async def test_list_repos(client):
    r = await client.get("/api/repos")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


@pytest.mark.asyncio
async def test_get_repo_not_found(client):
    r = await client.get("/api/repos/nonexistent-id")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_delete_repo(client):
    # Create a repo first
    r = await client.post("/api/repos", json={
        "source_type": "github",
        "url": "https://github.com/owner/todelete",
    })
    assert r.status_code == 202
    repo_id = r.json()["id"]

    # Delete it
    r2 = await client.delete(f"/api/repos/{repo_id}")
    assert r2.status_code == 204

    # Should be gone
    r3 = await client.get(f"/api/repos/{repo_id}")
    assert r3.status_code == 404
