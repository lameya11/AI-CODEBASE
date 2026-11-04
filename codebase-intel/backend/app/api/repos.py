"""Repository CRUD endpoints."""
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.core.ingestion import run_ingestion
from app.core.repo_manager import clone_github_repo, validate_github_url
from app.db import get_db
from app.db.models import Repository
from app.schemas.repo import RepoCreateGitHub, RepoResponse

router = APIRouter(prefix="/repos", tags=["repos"])


async def _get_repo_or_404(repo_id: str, db: AsyncSession) -> Repository:
    result = await db.execute(select(Repository).where(Repository.id == repo_id))
    repo = result.scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=404, detail=f"Repository '{repo_id}' not found")
    return repo


@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=RepoResponse)
async def create_repo_github(
    body: RepoCreateGitHub,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Create a repo from a GitHub URL. Returns immediately; ingestion runs in background."""
    name = body.name or body.url.rstrip("/").split("/")[-1]
    repo = Repository(
        id=str(uuid.uuid4()),
        name=name,
        source_type="github",
        source_url=body.url,
        status="queued",
        status_message="Queued for analysis",
        warnings=[],
    )
    db.add(repo)
    await db.commit()
    await db.refresh(repo)

    repo_id = repo.id
    url = body.url

    async def _run():
        from app.db import SessionLocal
        async with SessionLocal() as bg_db:
            # Clone to temp dir
            tmp = Path(tempfile.mkdtemp(prefix="ci_clone_"))
            try:
                from app.db.models import Repository as Repo2
                from sqlalchemy import select as sel
                r2 = (await bg_db.execute(sel(Repo2).where(Repo2.id == repo_id))).scalar_one_or_none()
                if r2:
                    r2.status = "cloning"
                    r2.status_message = "Cloning repository..."
                    await bg_db.commit()

                clone_github_repo(url, tmp, token=settings.GITHUB_TOKEN or None)
                await run_ingestion(repo_id, tmp, bg_db)
            except Exception as exc:
                error_msg = str(exc)
                r2 = (await bg_db.execute(sel(Repo2).where(Repo2.id == repo_id))).scalar_one_or_none()
                if r2:
                    r2.status = "failed"
                    r2.status_message = error_msg
                    r2.error = error_msg
                    await bg_db.commit()
                if tmp.exists():
                    shutil.rmtree(tmp, ignore_errors=True)

    background_tasks.add_task(_run)
    return repo


@router.post("/upload", status_code=status.HTTP_202_ACCEPTED, response_model=RepoResponse)
async def create_repo_zip(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    name: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
):
    """Create a repo from a ZIP upload."""
    if file.content_type not in ("application/zip", "application/x-zip-compressed", "application/octet-stream"):
        # Be lenient with content-type, check extension
        if not (file.filename or "").endswith(".zip"):
            raise HTTPException(status_code=400, detail="Only ZIP files are accepted")

    repo_name = name or (file.filename or "uploaded").replace(".zip", "")
    repo = Repository(
        id=str(uuid.uuid4()),
        name=repo_name,
        source_type="zip",
        source_url=None,
        status="queued",
        status_message="Queued for analysis",
        warnings=[],
    )
    db.add(repo)
    await db.commit()
    await db.refresh(repo)

    # Save ZIP to a temp file
    tmp_zip = Path(tempfile.mktemp(suffix=".zip"))
    contents = await file.read()
    tmp_zip.write_bytes(contents)

    repo_id = repo.id

    async def _run():
        from app.db import SessionLocal
        from app.core.repo_manager import extract_zip
        async with SessionLocal() as bg_db:
            tmp_dir = Path(tempfile.mkdtemp(prefix="ci_zip_"))
            try:
                from app.db.models import Repository as Repo2
                from sqlalchemy import select as sel
                r2 = (await bg_db.execute(sel(Repo2).where(Repo2.id == repo_id))).scalar_one_or_none()
                if r2:
                    r2.status = "cloning"
                    r2.status_message = "Extracting ZIP..."
                    await bg_db.commit()

                extract_zip(tmp_zip, tmp_dir, max_total_bytes=settings.MAX_ZIP_BYTES)
                await run_ingestion(repo_id, tmp_dir, bg_db)
            except Exception as exc:
                error_msg = str(exc)
                r2 = (await bg_db.execute(sel(Repo2).where(Repo2.id == repo_id))).scalar_one_or_none()
                if r2:
                    r2.status = "failed"
                    r2.status_message = error_msg
                    r2.error = error_msg
                    await bg_db.commit()
                if tmp_dir.exists():
                    shutil.rmtree(tmp_dir, ignore_errors=True)
            finally:
                if tmp_zip.exists():
                    tmp_zip.unlink(missing_ok=True)

    background_tasks.add_task(_run)
    return repo


@router.get("", response_model=list[RepoResponse])
async def list_repos(db: AsyncSession = Depends(get_db)):
    """List all repositories."""
    result = await db.execute(select(Repository).order_by(Repository.created_at.desc()))
    return result.scalars().all()


@router.get("/{repo_id}", response_model=RepoResponse)
async def get_repo(repo_id: str, db: AsyncSession = Depends(get_db)):
    """Get a single repository by ID."""
    return await _get_repo_or_404(repo_id, db)


@router.delete("/{repo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_repo(repo_id: str, db: AsyncSession = Depends(get_db)):
    """Delete a repository and all its related data."""
    repo = await _get_repo_or_404(repo_id, db)
    await db.delete(repo)
    await db.commit()

    # Remove vector index directory
    index_dir = settings.get_data_dir() / "indexes" / repo_id
    if index_dir.exists():
        shutil.rmtree(index_dir, ignore_errors=True)


@router.post("/{repo_id}/reanalyze", status_code=status.HTTP_202_ACCEPTED, response_model=RepoResponse)
async def reanalyze_repo(
    repo_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Re-run ingestion for an existing repository."""
    repo = await _get_repo_or_404(repo_id, db)
    if repo.source_type != "github":
        raise HTTPException(status_code=400, detail="Re-analysis is only supported for GitHub repos")
    if not repo.source_url:
        raise HTTPException(status_code=400, detail="No source URL stored for this repository")

    repo.status = "queued"
    repo.status_message = "Re-queued for analysis"
    repo.error = None
    await db.commit()
    await db.refresh(repo)

    url = repo.source_url

    async def _run():
        import tempfile
        from app.db import SessionLocal
        async with SessionLocal() as bg_db:
            tmp = Path(tempfile.mkdtemp(prefix="ci_reclone_"))
            try:
                from app.db.models import Repository as Repo2
                from sqlalchemy import select as sel
                r2 = (await bg_db.execute(sel(Repo2).where(Repo2.id == repo_id))).scalar_one_or_none()
                if r2:
                    r2.status = "cloning"
                    r2.status_message = "Re-cloning repository..."
                    await bg_db.commit()
                clone_github_repo(url, tmp, token=settings.GITHUB_TOKEN or None)
                await run_ingestion(repo_id, tmp, bg_db)
            except Exception as exc:
                r2 = (await bg_db.execute(sel(Repo2).where(Repo2.id == repo_id))).scalar_one_or_none()
                if r2:
                    r2.status = "failed"
                    r2.status_message = str(exc)
                    r2.error = str(exc)
                    await bg_db.commit()
                if tmp.exists():
                    shutil.rmtree(tmp, ignore_errors=True)

    background_tasks.add_task(_run)
    return repo
