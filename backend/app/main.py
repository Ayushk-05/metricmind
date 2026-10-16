from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.deps import get_db
from app.engine import (
    execute_safe_sql,
    SQLSecurityError,
    SQLValidationError,
    SQLExecutionError,
)
from app.schemas.query import QueryExecuteRequest, QueryExecuteResponse

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
)

@app.get("/")
def root():
    return {"message": "MetricMind API is running"}

@app.get("/health")
def health():
    return {"status": "healthy"}

@app.get("/health/db")
def health_db(db: Session = Depends(get_db)):
    """Verifies that the database connection is operational."""
    try:
        db.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected"}
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failed",
        ) from exc

@app.post("/api/v1/query/execute", response_model=QueryExecuteResponse)
def execute_query(
    request: QueryExecuteRequest,
    db: Session = Depends(get_db),
):
    """Safely executes an analytical SQL query against approved MetricMind tables."""
    try:
        result = execute_safe_sql(
            db=db,
            sql=request.query,
            row_limit=request.row_limit,
        )
        return QueryExecuteResponse(
            success=True,
            columns=result.columns,
            rows=result.rows,
            row_count=result.row_count,
            execution_time_ms=result.execution_time_ms,
            executed_query=result.executed_query,
        )
    except (SQLSecurityError, SQLValidationError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except SQLExecutionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc