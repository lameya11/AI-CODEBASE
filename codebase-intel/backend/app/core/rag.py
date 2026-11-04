"""RAG pipeline: retrieve -> neighbors -> prompt -> LLM -> citations."""
import json
import logging
from typing import Optional

from app.config import settings
from app.core.embeddings import get_embedder
from app.core.llm_client import LLMClient
from app.core.vector_store import VectorStore

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You answer questions about a code repository. "
    "Use ONLY the provided code context. "
    "If the answer is not in the context, say so clearly. "
    "Cite every claim with file_path:line references in the form [path:start-end]. "
    "Do not invent files or functions."
)


def _estimate_tokens(text: str) -> int:
    """Approximate token count as chars / 4."""
    return len(text) // 4


def build_context(
    search_results: list[dict],
    dependency_chunks: list[dict],
    token_budget: int,
) -> tuple[list[dict], str]:
    """
    Build the prompt context string from search results and dependency neighbors.

    Enforces token_budget. Drops/truncates lowest-ranked chunks first.
    Returns (annotated_sources, context_text).
    """
    all_chunks: list[dict] = []

    for r in search_results:
        all_chunks.append({**r, "related": False})
    for r in dependency_chunks:
        all_chunks.append({**r, "related": True})

    context_parts: list[str] = []
    used_chunks: list[dict] = []
    budget_remaining = token_budget

    for chunk in all_chunks:
        label = f"[{chunk['file_path']}:{chunk['start_line']}-{chunk['end_line']}]"
        snippet = chunk.get("text") or chunk.get("snippet", "")
        block = f"{label}\n```\n{snippet}\n```"
        cost = _estimate_tokens(block)

        if cost <= budget_remaining:
            context_parts.append(block)
            used_chunks.append(chunk)
            budget_remaining -= cost
        else:
            # Truncate to fit
            available_chars = budget_remaining * 4
            if available_chars > 100:
                truncated_snippet = snippet[:available_chars]
                block = f"{label}\n```\n{truncated_snippet}\n... [truncated]\n```"
                context_parts.append(block)
                used_chunks.append({**chunk, "snippet": truncated_snippet})
                budget_remaining = 0
            break

    return used_chunks, "\n\n".join(context_parts)


def run_rag(
    question: str,
    repo_id: str,
    vector_store: VectorStore,
    chunk_map: dict[int, dict],  # chunk_id -> {file_path, symbol_name, start_line, end_line, text}
    file_graph,                  # nx.DiGraph
    llm_client: LLMClient,
    history: Optional[list[dict]] = None,
    top_k: int = 8,
    token_budget: int = 6000,
) -> dict:
    """
    Full RAG pipeline.

    1. Retrieve top-k chunks for the question.
    2. Add dependency neighbor chunks from the top-ranked file.
    3. Build prompt within token budget.
    4. Call LLM (or NoOp).
    5. Return answer + sources.
    """
    embedder = get_embedder()

    # Step 1: retrieve
    raw_results = vector_store.search(question, k=top_k, embedder=embedder)
    search_chunks: list[dict] = []
    for r in raw_results:
        cid = r["chunk_id"]
        if cid not in chunk_map:
            continue
        c = chunk_map[cid]
        search_chunks.append({
            **c,
            "score": r["score"],
            "rank": r["rank"],
            "related": False,
        })

    # Step 2: dependency neighbors of the top-ranked file
    dep_chunks: list[dict] = []
    if search_chunks and file_graph is not None:
        top_file = search_chunks[0]["file_path"]
        neighbor_files: list[str] = []
        try:
            for _, tgt in file_graph.out_edges(top_file):
                if not file_graph.nodes.get(tgt, {}).get("is_external"):
                    neighbor_files.append(tgt)
        except Exception:
            pass

        # Collect up to 3 chunks from neighbor files
        added = 0
        for cid, c in chunk_map.items():
            if added >= 3:
                break
            if c["file_path"] in neighbor_files:
                dep_chunks.append({**c, "score": 0.0, "rank": 999, "related": True})
                added += 1

    # Step 3: build context
    used_sources, context_text = build_context(search_chunks, dep_chunks, token_budget)

    if not context_text:
        context_text = "No relevant code sections found."

    # Step 4: call LLM
    messages: list[dict] = []
    if history:
        messages.extend(history[-12:])  # last 6 turns = 12 messages

    messages.append({"role": "user", "content": f"{question}\n\n---\nCode context:\n{context_text}"})

    answer, model = llm_client.complete(SYSTEM_PROMPT, messages)

    # Format sources for response
    sources = []
    for s in used_sources:
        sources.append({
            "file_path": s.get("file_path", ""),
            "start_line": s.get("start_line", 0),
            "end_line": s.get("end_line", 0),
            "symbol_name": s.get("symbol_name"),
            "snippet": (s.get("text") or s.get("snippet", ""))[:300],
            "score": s.get("score", 0.0),
            "related": s.get("related", False),
        })

    return {
        "answer": answer,
        "sources": sources,
        "model": model if llm_client.is_configured else None,
        "llm_configured": llm_client.is_configured,
    }
