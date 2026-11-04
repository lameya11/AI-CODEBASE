"""Integration test: ingest sample repo ZIP, verify search and impact work."""
import asyncio
import io
import os
import tempfile
import time
import zipfile
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["DATA_DIR"] = "/tmp/ci_integ_test"

from app.main import app
from app.db import init_db


def _build_sample_zip() -> bytes:
    """Build a ZIP of the sample-fullstack project."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        # backend Python files
        zf.writestr("backend/app/database.py", """\
import sqlite3

def get_connection():
    return sqlite3.connect(":memory:")

def run_query(sql, params=()):
    conn = get_connection()
    return conn.execute(sql, params).fetchall()
""")
        zf.writestr("backend/app/users.py", """\
from app.database import get_connection, run_query

def find_user(username):
    return run_query("SELECT * FROM users WHERE username = ?", (username,))

def create_user(username, email):
    return run_query("INSERT INTO users VALUES (?,?)", (username, email))
""")
        zf.writestr("backend/app/auth.py", """\
from app.users import find_user
from app.database import get_connection

def login(username, password):
    user = find_user(username)
    if not user:
        return None
    return {"user": user, "token": "fake-token"}
""")
        zf.writestr("backend/app/main.py", """\
from fastapi import FastAPI
from app.auth import login
from app.users import find_user

app = FastAPI()

@app.post("/login")
def do_login(credentials: dict):
    return login(credentials["username"], credentials["password"])

@app.get("/users")
def list_users():
    return find_user("all")
""")
        zf.writestr("backend/app/config.py", """\
api_key = "sk-live-1234567890abcdef"

def complex_function(x):
    if x == 1: return 1
    if x == 2: return 2
    if x == 3: return 3
    if x == 4: return 4
    if x == 5: return 5
    if x == 6: return 6
    if x == 7: return 7
    if x == 8: return 8
    if x == 9: return 9
    if x == 10: return 10
    if x == 11: return 11
    return x
""")
        zf.writestr("backend/app/reports.py", """\
import os
import csv

def get_report(user_id):
    return run_query(f"SELECT * FROM reports WHERE user_id = {user_id}")
""")
        # frontend files
        zf.writestr("frontend/src/api.js", """\
export async function loginUser(username, password) {
    const r = await fetch('/login', {method: 'POST', body: JSON.stringify({username, password})});
    return r.json();
}
export async function getUsers() {
    const r = await fetch('/users');
    return r.json();
}
""")
        zf.writestr("frontend/src/auth-utils.js", """\
export function isLoggedIn() {
    return !!localStorage.getItem('token');
}
export function logout() {
    localStorage.removeItem('token');
}
""")
        zf.writestr("frontend/src/Login.jsx", """\
import React, { useState } from 'react';
import { loginUser } from './api';
import { isLoggedIn } from './auth-utils';

function Login() {
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');

    const handleLogin = async () => {
        const result = await loginUser(username, password);
        if (result.token) {
            localStorage.setItem('token', result.token);
        }
    };

    return (
        <div>
            <input value={username} onChange={e => setUsername(e.target.value)} />
            <input type="password" value={password} onChange={e => setPassword(e.target.value)} />
            <button onClick={handleLogin}>Login</button>
        </div>
    );
}

export default Login;
""")
        zf.writestr("frontend/src/App.jsx", """\
import React from 'react';
import Login from './Login';

function App() {
    return <Login />;
}

export default App;
""")
    return buf.getvalue()


@pytest_asyncio.fixture(scope="module")
async def setup_db():
    await init_db()


@pytest_asyncio.fixture(scope="module")
async def client(setup_db):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture(scope="module")
async def ingested_repo(client):
    """Upload sample ZIP and wait for ingestion to complete."""
    zip_data = _build_sample_zip()
    r = await client.post(
        "/api/repos/upload",
        files={"file": ("sample.zip", zip_data, "application/zip")},
        data={"name": "sample-fullstack"},
    )
    assert r.status_code == 202
    repo_id = r.json()["id"]

    # Poll for completion
    for _ in range(60):
        await asyncio.sleep(0.5)
        r2 = await client.get(f"/api/repos/{repo_id}")
        status = r2.json()["status"]
        if status in ("ready", "failed"):
            break

    assert r2.json()["status"] == "ready", f"Ingestion failed: {r2.json()}"
    return repo_id


@pytest.mark.asyncio
async def test_ingestion_complete(ingested_repo, client):
    """Repository should reach 'ready' status."""
    r = await client.get(f"/api/repos/{ingested_repo}")
    assert r.json()["status"] == "ready"


@pytest.mark.asyncio
async def test_file_tree(ingested_repo, client):
    """File tree should contain expected files."""
    r = await client.get(f"/api/repos/{ingested_repo}/files")
    assert r.status_code == 200
    paths = [f["path"] for f in r.json()]
    # Should include backend Python files
    assert any("main.py" in p for p in paths)
    assert any("auth.py" in p for p in paths)
    assert any("database.py" in p for p in paths)


@pytest.mark.asyncio
async def test_stats(ingested_repo, client):
    """Stats should show correct file/symbol counts."""
    r = await client.get(f"/api/repos/{ingested_repo}/stats")
    assert r.status_code == 200
    data = r.json()
    assert data["file_count"] >= 5
    assert data["function_count"] >= 3


@pytest.mark.asyncio
async def test_graph(ingested_repo, client):
    """File-level graph should have edges representing imports."""
    r = await client.get(f"/api/repos/{ingested_repo}/graph?level=file")
    assert r.status_code == 200
    data = r.json()
    assert len(data["nodes"]) >= 4
    # Check that there's an edge from main.py to auth.py
    edges = [(e["source"], e["target"]) for e in data["edges"]]
    main_paths = [n["id"] for n in data["nodes"] if "main.py" in n["id"]]
    auth_paths = [n["id"] for n in data["nodes"] if "auth.py" in n["id"]]
    assert main_paths and auth_paths


@pytest.mark.asyncio
async def test_search_login(ingested_repo, client):
    """Searching for 'login' should return relevant chunks."""
    r = await client.get(f"/api/repos/{ingested_repo}/search?q=login&k=5")
    assert r.status_code == 200
    results = r.json()["results"]
    assert len(results) >= 1
    # At least one result should be from auth.py or Login.jsx
    file_paths = [res["file_path"] for res in results]
    assert any("auth" in p or "Login" in p or "main" in p for p in file_paths)


@pytest.mark.asyncio
async def test_chat_no_key(ingested_repo, client):
    """Chat without LLM key should return sources and a notice."""
    r = await client.post(f"/api/repos/{ingested_repo}/chat", json={
        "question": "How does login work?"
    })
    assert r.status_code == 200
    data = r.json()
    assert data["llm_configured"] is False
    assert "No LLM" in data["answer"]
    assert len(data["sources"]) >= 1
    # Every source should have a file_path
    for s in data["sources"]:
        assert s["file_path"]


@pytest.mark.asyncio
async def test_impact_database(ingested_repo, client):
    """Impact analysis for database.py should find dependents."""
    # Find the database.py path from file list
    r = await client.get(f"/api/repos/{ingested_repo}/files")
    files = r.json()
    db_file = next((f for f in files if "database.py" in f["path"]), None)
    assert db_file, "database.py not found in file list"

    r2 = await client.post(f"/api/repos/{ingested_repo}/impact", json={
        "file_path": db_file["path"]
    })
    assert r2.status_code == 200
    data = r2.json()
    assert data["level"] in ("high", "medium", "low")
    assert data["total_affected"] >= 1
    # Direct dependents should include users.py or auth.py
    direct_paths = [d["file_path"] for d in data["direct"]]
    assert any("users.py" in p or "auth.py" in p for p in direct_paths)


@pytest.mark.asyncio
async def test_issues_secret(ingested_repo, client):
    """config.py should have a secret warning."""
    r = await client.get(f"/api/repos/{ingested_repo}/issues")
    assert r.status_code == 200
    issues = r.json()["issues"]
    secret_issues = [i for i in issues if i["type"] == "secret"]
    assert len(secret_issues) >= 1
    # Should be in config.py
    assert any("config.py" in (i.get("file_path") or "") for i in secret_issues)


@pytest.mark.asyncio
async def test_issues_sql_injection(ingested_repo, client):
    """reports.py should have an SQL injection warning."""
    r = await client.get(f"/api/repos/{ingested_repo}/issues")
    issues = r.json()["issues"]
    sql_issues = [i for i in issues if i["type"] == "sql_injection"]
    assert len(sql_issues) >= 1
    assert any("reports.py" in (i.get("file_path") or "") for i in sql_issues)
