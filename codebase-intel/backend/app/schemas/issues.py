"""Issues schemas."""
from typing import Optional
from pydantic import BaseModel


class IssueResponse(BaseModel):
    id: int
    repo_id: str
    file_id: int
    file_path: Optional[str] = None
    type: str
    severity: str
    line: int
    message: str
    suggestion: str

    model_config = {"from_attributes": True}


class IssuesListResponse(BaseModel):
    issues: list[IssueResponse]
    total: int
    counts_by_type: dict[str, int]
    counts_by_severity: dict[str, int]
