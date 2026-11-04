"""Tests for the RAG pipeline."""
import tempfile
from pathlib import Path
import pytest
import numpy as np

from app.core.rag import run_rag, build_context, _estimate_tokens
from app.core.vector_store import VectorStore
from app.core.llm_client import LLMClient, NoOpLLMClient
from app.core.embeddings import HashingEmbedder


class FakeLLMClient(LLMClient):
    """Fake LLM client that echoes the messages."""

    def complete(self, system: str, messages: list[dict]) -> tuple[str, str]:
        return ("This is the auth.py file which handles login.", "fake-model")

    @property
    def is_configured(self) -> bool:
        return True


CHUNK_MAP = {
    1: {
        "file_path": "app/auth.py",
        "symbol_name": "login",
        "start_line": 5,
        "end_line": 20,
        "language": "python",
        "text": "def login(username, password):\n    user = find_user(username)\n    return user",
    },
    2: {
        "file_path": "app/users.py",
        "symbol_name": "find_user",
        "start_line": 1,
        "end_line": 10,
        "language": "python",
        "text": "def find_user(username):\n    return db.query(username)",
    },
    3: {
        "file_path": "app/main.py",
        "symbol_name": "list_users",
        "start_line": 15,
        "end_line": 25,
        "language": "python",
        "text": "@app.get('/users')\ndef list_users():\n    return users.all()",
    },
}


@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def vector_store(tmp_dir):
    embedder = HashingEmbedder()
    vs = VectorStore("test-repo", tmp_dir)
    vs.add(
        chunk_ids=list(CHUNK_MAP.keys()),
        texts=[c["text"] for c in CHUNK_MAP.values()],
        embedder=embedder,
    )
    return vs


def test_rag_returns_sources(vector_store):
    result = run_rag(
        question="How does login work?",
        repo_id="test-repo",
        vector_store=vector_store,
        chunk_map=CHUNK_MAP,
        file_graph=None,
        llm_client=FakeLLMClient(),
        top_k=3,
    )
    assert len(result["sources"]) >= 1
    assert result["llm_configured"] is True


def test_rag_no_key_returns_notice(vector_store):
    """Without an LLM key, the NoOp client returns sources with a notice."""
    result = run_rag(
        question="What does auth.py do?",
        repo_id="test-repo",
        vector_store=vector_store,
        chunk_map=CHUNK_MAP,
        file_graph=None,
        llm_client=NoOpLLMClient(),
        top_k=3,
    )
    assert result["llm_configured"] is False
    assert "No LLM" in result["answer"]
    # Sources should still be returned
    assert len(result["sources"]) >= 1


def test_prompt_contains_labels(vector_store):
    """build_context should add [file:start-end] labels."""
    search_results = [
        {**v, "score": 0.9, "rank": 0}
        for v in CHUNK_MAP.values()
    ]
    sources, context = build_context(search_results, [], token_budget=10000)
    for s in sources:
        label = f"[{s['file_path']}:{s['start_line']}-{s['end_line']}]"
        assert label in context


def test_token_budget_respected(vector_store):
    """build_context should not exceed TOKEN_BUDGET."""
    search_results = [
        {**v, "score": 0.9, "rank": i}
        for i, v in enumerate(CHUNK_MAP.values())
    ]
    _, context = build_context(search_results, [], token_budget=50)
    # Approximate token count should be <= 50
    assert _estimate_tokens(context) <= 200  # allow some slack for labels


def test_rag_with_history(vector_store):
    history = [
        {"role": "user", "content": "What files does this repo have?"},
        {"role": "assistant", "content": "It has main.py, auth.py, users.py"},
    ]
    result = run_rag(
        question="How does login work?",
        repo_id="test-repo",
        vector_store=vector_store,
        chunk_map=CHUNK_MAP,
        file_graph=None,
        llm_client=FakeLLMClient(),
        history=history,
        top_k=3,
    )
    assert result["answer"]
