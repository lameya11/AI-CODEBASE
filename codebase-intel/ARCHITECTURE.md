# Architecture: Codebase Intelligence Platform

## Overview

This document explains the three core systems in detail: the ingestion pipeline, the RAG (Retrieval-Augmented Generation) flow, and the impact analysis algorithm.

---

## 1. Ingestion Pipeline

When a user submits a GitHub URL or ZIP file, the following steps run in a background task. Each step updates the `status` field of the repository record so the frontend can display progress.

```
User submits URL/ZIP
        │
        ▼
[Step 1: Clone/Extract]
 - GitHub: git clone --depth 1 (with optional token)
 - ZIP: safe extraction (reject traversal, symlinks, oversized)
        │
        ▼
[Step 2: Scan]
 - Walk all files under the directory
 - Apply ignore rules: .git, node_modules, venv, __pycache__, dist...
 - Skip lock files, images, binaries, files > 1 MB
 - Cap at MAX_FILES (default 2000)
        │
        ▼
[Step 3: Parse]
 - Python files: ast module
   • Imports (absolute + relative with level)
   • Functions, classes, methods with line ranges
   • FastAPI route decorators (method + path)
   • Call graph within functions
 - JS/TS files: regex-based (best effort)
   • ES module imports, require, export-from
   • Functions, arrow functions, classes
   • React components (uppercase + JSX)
   • Express routes
        │
        ▼
[Step 4: Build Dependency Graph]
 - File-level DiGraph (NetworkX):
   • Python: resolve dotted module names → file paths
   • JS/TS: resolve relative specifiers with extension variants
   • Unresolved → mark as external nodes
 - Function-level graph: nodes = "file::symbol", edges = calls
        │
        ▼
[Step 5: Static Checks]
 - Secret detection: regex for api_key/password/token assignments,
   AWS AKIA keys, private key headers
 - SQL injection: AST - detect f-strings/concat/format in execute/query calls
 - Unused imports: AST - imports not referenced as ast.Name/ast.Attribute
 - Cyclomatic complexity: count if/for/while/except/with/BoolOp/comprehensions + 1
        │
        ▼
[Step 6: Chunk]
 - Per symbol: one chunk using the symbol's line range (capped at 200 lines)
 - No symbols / unsupported: sliding window (60 lines, 10 overlap)
 - Markdown: split by headings, fallback to sliding window
        │
        ▼
[Step 7: Embed + Index]
 - Embedder: SentenceTransformer all-MiniLM-L6-v2 if available,
   else deterministic HashingEmbedder (128-dim TF-IDF style)
 - All vectors are L2-normalized before storage
 - Vector store: FAISS IndexFlatIP if available, else NumPy dot product
 - Persisted under DATA_DIR/indexes/{repo_id}/
        │
        ▼
[Status = ready]
```

---

## 2. RAG (Retrieval-Augmented Generation) Flow

When a user sends a question, the following pipeline executes:

```
User question
      │
      ▼
[Embed the question]
 - Same embedder used during indexing
 - L2-normalized vector
      │
      ▼
[Vector search]
 - Search per-repo FAISS/NumPy index
 - Return top-K (default 8) chunk IDs with cosine similarity scores
      │
      ▼
[Load chunk metadata from DB]
 - chunk_id → {file_path, symbol_name, start_line, end_line, text}
      │
      ▼
[Add dependency neighbors (up to 3)]
 - Take the top-ranked file
 - Find its direct dependencies (out-edges in the file graph)
 - Add up to 3 chunks from those files, marked as "related: true"
      │
      ▼
[Build prompt within TOKEN_BUDGET]
 - Label each chunk: [file_path:start_line-end_line]
 - Estimate tokens as len(text) / 4
 - Drop lowest-ranked chunks if over budget
 - Truncate last chunk if needed
      │
      ▼
[System prompt]
 "You answer questions about a code repository.
  Use ONLY the provided code context.
  If the answer is not in the context, say so clearly.
  Cite every claim with [path:start-end] references.
  Do not invent files or functions."
      │
      ▼
[Call LLMClient.complete(system, messages)]
 - OpenAI: gpt-4o-mini
 - Anthropic: claude-3-haiku
 - NoOp: returns notice + sources (no API key configured)
      │
      ▼
[Return answer + sources]
 - answer: LLM response text
 - sources: [{file_path, start_line, end_line, snippet, score, related}]
 - llm_configured: bool
 - Saved to chat_messages table
```

**Key design decisions:**
- The system prompt explicitly forbids inventing files or functions
- Token budget is enforced by dropping lowest-ranked chunks, not by truncating the LLM output
- Without an LLM key, sources are still returned so the UI remains useful

---

## 3. Impact Analysis (Reverse BFS)

The goal is to find all files that would be affected by a change to a target file.

**Algorithm:**

```
Input: target file path, file-level DiGraph G, max_depth

1. Build reverse graph G_rev (edge means "is imported by")
   - G has edges: importer → imported
   - G_rev has edges: imported → importer

2. BFS from target in G_rev:
   queue = [(target, depth=0, via=target)]
   visited = {target}

   while queue not empty:
     (node, depth, via) = dequeue

     if depth >= max_depth:
       continue  # Don't expand deeper

     for each predecessor of node in G_rev:
       if predecessor not visited AND not external:
         visited.add(predecessor)
         new_depth = depth + 1
         if new_depth == 1: add to direct list
         else: add to indirect list
         enqueue (predecessor, new_depth, predecessor)

3. Determine impact level:
   HIGH if:
     - affected count >= 10, OR
     - target is an entry point (main.py, app.py, index.*), OR
     - target is a route file (has symbols with kind=route), OR
     - target path/name contains: database, db, auth, session, security, models
   MEDIUM if:
     - affected count 3–9
   LOW if:
     - affected count 0–2
```

**Why BFS (not DFS)?**
- BFS gives us the shortest-path depth, which maps cleanly to "direct" (depth 1) vs "indirect" (depth 2+)
- The visited set prevents infinite loops in cyclic dependency graphs

**Why reverse the graph?**
- The original graph has edges importer → imported
- "Who imports X?" means "who are X's predecessors in the original graph?"
- Reversing the graph turns predecessors into successors, making BFS straightforward

**Depth coloring in the UI:**
- Depth 1 (direct): orange
- Depth 2 (indirect): yellow
- Depth 3+ (transitive): light red
