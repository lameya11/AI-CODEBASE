"""Ingestion pipeline orchestrator."""
import logging
import shutil
import tempfile
from collections import Counter
from datetime import datetime, UTC
from pathlib import Path
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.config import settings
from app.core.checks import run_all_checks
from app.core.chunker import chunk_file
from app.core.embeddings import get_embedder
from app.core.graph_builder import build_file_graph
from app.core.logging_utils import timed_step
from app.core.parsers import parse_python, parse_js
from app.core.parsers.base import ParseResult
from app.core.scanner import scan_directory
from app.core.vector_store import VectorStore
from app.db.models import Chunk, Dependency, File, Issue, Repository, Symbol

logger = logging.getLogger(__name__)


async def _set_status(
    db: AsyncSession,
    repo_id: str,
    status: str,
    message: str,
    error: Optional[str] = None,
) -> None:
    """Update repo status in the database."""
    result = await db.execute(select(Repository).where(Repository.id == repo_id))
    repo = result.scalar_one_or_none()
    if repo:
        repo.status = status
        repo.status_message = message
        if error:
            repo.error = error
        await db.commit()


async def run_ingestion(
    repo_id: str,
    source_dir: Path,
    db: AsyncSession,
) -> None:
    """
    Orchestrate the full ingestion pipeline for a repository.

    Updates status at each step. Cleans up temp dir when done.
    """
    try:
        await _ingest(repo_id, source_dir, db)
    except Exception as exc:
        logger.exception("Ingestion failed for repo %s", repo_id)
        await _set_status(db, repo_id, "failed", str(exc), error=str(exc))
    finally:
        # Clean up temp source directory
        if source_dir.exists():
            shutil.rmtree(source_dir, ignore_errors=True)


async def _ingest(repo_id: str, source_dir: Path, db: AsyncSession) -> None:
    """Internal ingestion logic."""

    # ---- Step 1: Scan ----
    await _set_status(db, repo_id, "parsing", "Scanning files...")
    with timed_step("scan"):
        files, hit_cap = scan_directory(
            source_dir,
            max_files=settings.MAX_FILES,
            max_file_bytes=settings.MAX_FILE_BYTES,
        )

    result = await db.execute(select(Repository).where(Repository.id == repo_id))
    repo = result.scalar_one_or_none()
    if not repo:
        return

    warnings = list(repo.warnings or [])
    if hit_cap:
        warnings.append(f"File cap ({settings.MAX_FILES}) reached. Some files were not analyzed.")
        repo.warnings = warnings

    # ---- Step 2: Parse ----
    await _set_status(db, repo_id, "parsing", f"Parsing {len(files)} files...")

    # Delete existing records for re-analysis
    await db.execute(delete(Chunk).where(Chunk.repo_id == repo_id))
    await db.execute(delete(Issue).where(Issue.repo_id == repo_id))
    await db.execute(delete(Dependency).where(Dependency.repo_id == repo_id))
    await db.execute(delete(Symbol).where(Symbol.file_id.in_(
        select(File.id).where(File.repo_id == repo_id)
    )))
    await db.execute(delete(File).where(File.repo_id == repo_id))
    await db.commit()

    parse_results: dict[str, ParseResult] = {}
    file_db_rows: dict[str, File] = {}  # path -> File DB row
    lang_counter: Counter = Counter()
    total_lines = 0

    for sf in files:
        source = ""
        try:
            source = sf.absolute_path.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:
            logger.warning("Could not read %s: %s", sf.path, exc)

        line_count = source.count("\n") + 1 if source else 0
        total_lines += line_count

        db_file = File(
            repo_id=repo_id,
            path=sf.path,
            language=sf.language,
            size=sf.size,
            line_count=line_count,
            supported=sf.supported,
        )
        db.add(db_file)
        await db.flush()  # get the assigned id
        file_db_rows[sf.path] = db_file

        if not sf.supported or not source:
            continue

        lang_counter[sf.language or "unknown"] += 1

        # Parse
        try:
            if sf.language == "python":
                pr = parse_python(source, sf.path)
            else:
                pr = parse_js(source, sf.path)
        except Exception as exc:
            logger.warning("Parser error for %s: %s", sf.path, exc)
            db_file.parse_error = str(exc)
            continue

        if pr.parse_error:
            db_file.parse_error = pr.parse_error

        parse_results[sf.path] = pr

        # Persist symbols
        for sym in pr.symbols:
            db.add(Symbol(
                file_id=db_file.id,
                name=sym.name,
                kind=sym.kind,
                start_line=sym.start_line,
                end_line=sym.end_line,
                docstring=sym.docstring,
                parent_name=sym.parent_name,
                route_method=sym.route_method,
                route_path=sym.route_path,
            ))

    await db.commit()

    # ---- Step 3: Build graph ----
    await _set_status(db, repo_id, "graph_building", "Building dependency graph...")
    with timed_step("graph_build"):
        file_graph = build_file_graph(parse_results)

    # Persist dependencies
    for importer_path, imported_path, data in file_graph.edges(data=True):
        importer_file = file_db_rows.get(importer_path)
        imported_file = file_db_rows.get(imported_path)
        is_external = file_graph.nodes.get(imported_path, {}).get("is_external", False)

        if importer_file is None:
            continue

        db.add(Dependency(
            repo_id=repo_id,
            source_file_id=importer_file.id,
            target_file_id=imported_file.id if imported_file else None,
            target_module=imported_path,
            kind="import",
            is_external=is_external,
        ))

    await db.commit()

    # ---- Step 4: Static checks ----
    await _set_status(db, repo_id, "parsing", "Running static checks...")
    for sf in files:
        if not sf.supported:
            continue
        try:
            source = sf.absolute_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        db_file = file_db_rows.get(sf.path)
        if not db_file:
            continue
        issues = run_all_checks(source, sf.path, threshold=settings.COMPLEXITY_THRESHOLD)
        for iss in issues:
            db.add(Issue(
                repo_id=repo_id,
                file_id=db_file.id,
                type=iss.type,
                severity=iss.severity,
                line=iss.line,
                message=iss.message,
                suggestion=iss.suggestion,
            ))
    await db.commit()

    # ---- Step 5: Chunk and index ----
    await _set_status(db, repo_id, "indexing", "Building vector index...")

    index_dir = settings.get_index_dir(repo_id)
    vector_store = VectorStore(repo_id=repo_id, index_dir=index_dir)
    vector_store.clear()

    embedder = get_embedder()
    batch_chunk_ids: list[int] = []
    batch_texts: list[str] = []
    BATCH_SIZE = 64

    for sf in files:
        if not sf.supported:
            continue
        try:
            source = sf.absolute_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        db_file = file_db_rows.get(sf.path)
        if not db_file:
            continue
        pr = parse_results.get(sf.path)
        chunks = chunk_file(source, sf.path, pr, language=sf.language)

        for c in chunks:
            db_chunk = Chunk(
                repo_id=repo_id,
                file_id=db_file.id,
                symbol_name=c.symbol_name,
                start_line=c.start_line,
                end_line=c.end_line,
                language=c.language,
                text=c.text,
            )
            db.add(db_chunk)
            await db.flush()
            batch_chunk_ids.append(db_chunk.id)
            batch_texts.append(c.text)

            if len(batch_texts) >= BATCH_SIZE:
                vector_store.add(batch_chunk_ids, batch_texts, embedder)
                batch_chunk_ids = []
                batch_texts = []

    if batch_texts:
        vector_store.add(batch_chunk_ids, batch_texts, embedder)

    await db.commit()

    # ---- Finalize ----
    result = await db.execute(select(Repository).where(Repository.id == repo_id))
    repo = result.scalar_one_or_none()
    if repo:
        repo.status = "ready"
        repo.status_message = "Analysis complete"
        repo.file_count = len(files)
        repo.line_count = total_lines
        repo.language_breakdown = dict(lang_counter)
        repo.last_analyzed_at = datetime.now(UTC)
        await db.commit()

    logger.info("Ingestion complete for repo %s: %d files, %d lines", repo_id, len(files), total_lines)
