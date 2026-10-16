from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class QueryExecuteRequest(BaseModel):
    query: str = Field(..., min_length=1, description="SQL query to safely validate and execute")
    row_limit: Optional[int] = Field(
        default=None,
        ge=1,
        le=100,
        description="Optional limit on maximum rows returned (clamped to 100)",
    )


class QueryExecuteResponse(BaseModel):
    success: bool
    columns: List[str] = Field(default_factory=list)
    rows: List[Dict[str, Any]] = Field(default_factory=list)
    row_count: int = 0
    execution_time_ms: float = 0.0
    executed_query: str = ""
    error: Optional[str] = None
