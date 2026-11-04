"""Tests for the vector store."""
import os
import tempfile
from pathlib import Path
import pytest
import numpy as np

from app.core.vector_store import VectorStore
from app.core.embeddings import HashingEmbedder


@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def embedder():
    return HashingEmbedder()


def test_add_and_search(tmp_dir, embedder):
    vs = VectorStore("test-repo", tmp_dir)
    vs.add(
        chunk_ids=[1, 2, 3],
        texts=["login function authentication", "database query helper", "user profile page"],
        embedder=embedder,
    )
    results = vs.search("login authentication", k=3, embedder=embedder)
    assert len(results) >= 1
    assert results[0]["chunk_id"] in [1, 2, 3]


def test_top_k_ordering(tmp_dir, embedder):
    """Top result should be closest to query."""
    vs = VectorStore("test-repo", tmp_dir)
    vs.add(
        chunk_ids=[1, 2, 3],
        texts=[
            "authentication login password user",
            "database sql query table",
            "config settings environment",
        ],
        embedder=embedder,
    )
    results = vs.search("login user authentication", k=3, embedder=embedder)
    assert len(results) >= 1
    # Scores should be in descending order
    scores = [r["score"] for r in results]
    assert scores == sorted(scores, reverse=True)


def test_persistence(tmp_dir, embedder):
    """Index should survive a save/load cycle."""
    vs1 = VectorStore("test-repo", tmp_dir)
    vs1.add(chunk_ids=[10, 20], texts=["hello world", "foo bar"], embedder=embedder)

    vs2 = VectorStore("test-repo", tmp_dir)
    results = vs2.search("hello", k=2, embedder=embedder)
    ids = [r["chunk_id"] for r in results]
    assert 10 in ids or 20 in ids


def test_empty_search(tmp_dir, embedder):
    vs = VectorStore("test-repo", tmp_dir)
    results = vs.search("anything", k=5, embedder=embedder)
    assert results == []


def test_clear(tmp_dir, embedder):
    vs = VectorStore("test-repo", tmp_dir)
    vs.add(chunk_ids=[1, 2], texts=["text one", "text two"], embedder=embedder)
    vs.clear()
    results = vs.search("text", k=5, embedder=embedder)
    assert results == []


def test_k_limit(tmp_dir, embedder):
    vs = VectorStore("test-repo", tmp_dir)
    vs.add(
        chunk_ids=list(range(10)),
        texts=[f"text {i}" for i in range(10)],
        embedder=embedder,
    )
    results = vs.search("text", k=3, embedder=embedder)
    assert len(results) <= 3
