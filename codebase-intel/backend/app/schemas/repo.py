"""Repository schemas."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, field_validator, model_validator
import re


_GITHUB_RE = re.compile(
    r"^https://github\.com/([a-zA-Z0-9_.-]+)/([a-zA-Z0-9_.-]+?)(?:\.git)?/?$"
)


class RepoCreateGitHub(BaseModel):
    source_type: str = "github"
    url: str
    name: Optional[str] = None

    @field_validator("url")
    @classmethod
    def validate_github_url(cls, v: str) -> str:
        if not _GITHUB_RE.match(v):
            raise ValueError(
                "URL must be a valid GitHub repository URL "
                "(https://github.com/owner/repo)"
            )
        return v


class RepoResponse(BaseModel):
    id: str
    name: str
    source_type: str
    source_url: Optional[str]
    status: str
    status_message: Optional[str]
    error: Optional[str]
    file_count: int
    line_count: int
    language_breakdown: Optional[dict]
    warnings: Optional[list]
    created_at: datetime
    updated_at: datetime
    last_analyzed_at: Optional[datetime]

    model_config = {"from_attributes": True}
