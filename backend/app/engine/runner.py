import time
from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime, date
from typing import Any, Dict, List, Optional, Set

from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.engine.exceptions import SQLExecutionError
from app.engine.validator import validate_safe_sql


@dataclass
class QueryResult:
    """Encapsulates the structured output of a safely executed SQL query."""
    columns: List[str]
    rows: List[Dict[str, Any]]
    row_count: int
    execution_time_ms: float
    executed_query: str


def _serialize_cell_value(val: Any) -> Any:
    """Converts database-specific types (Decimal, datetime) into JSON-serializable primitives."""
    if isinstance(val, Decimal):
        return float(val)
    if isinstance(val, (datetime, date)):
        return val.isoformat()
    return val


def execute_safe_sql(
    db: Session,
    sql: str,
    allowed_tables: Optional[Set[str]] = None,
    row_limit: Optional[int] = None,
    timeout_seconds: Optional[int] = None,
) -> QueryResult:
    """Validates and executes a SQL query safely within a read-only transaction.

    Enforces allowed tables, row limits, timeouts, and structured output formatting.
    Raises SQLSecurityError, SQLValidationError, or SQLExecutionError.
    """
    # 1. Validate SQL and apply row limit guardrail
    def_limit = row_limit if row_limit is not None else settings.DEFAULT_QUERY_ROW_LIMIT
    safe_sql = validate_safe_sql(
        sql=sql,
        allowed_tables=allowed_tables,
        default_limit=def_limit,
        max_limit=settings.MAX_QUERY_ROW_LIMIT,
    )

    t_sec = timeout_seconds if timeout_seconds is not None else settings.QUERY_TIMEOUT_SECONDS

    # 2. Execute with safety guardrails and timing
    start_time = time.perf_counter()

    try:
        bind = db.get_bind()
        dialect_name = bind.dialect.name if bind is not None else ""

        # Set read-only transaction and statement timeout for PostgreSQL
        if dialect_name == "postgresql":
            timeout_ms = int(t_sec * 1000)
            db.execute(text(f"SET LOCAL statement_timeout = {timeout_ms}"))
            db.execute(text("SET TRANSACTION READ ONLY"))

        # Execute query
        cursor = db.execute(text(safe_sql))
        columns = list(cursor.keys()) if cursor.returns_rows else []
        raw_rows = cursor.fetchall() if cursor.returns_rows else []

        # Convert rows to serializable dictionaries
        rows = [
            {col: _serialize_cell_value(val) for col, val in zip(columns, row)}
            for row in raw_rows
        ]

        execution_time_ms = round((time.perf_counter() - start_time) * 1000, 2)

        return QueryResult(
            columns=columns,
            rows=rows,
            row_count=len(rows),
            execution_time_ms=execution_time_ms,
            executed_query=safe_sql,
        )

    except SQLAlchemyError as exc:
        db.rollback()
        # Cleanly extract error message without exposing connection parameters
        err_msg = str(getattr(exc, "orig", exc))
        raise SQLExecutionError(f"Database query execution failed: {err_msg}") from exc
    except Exception as exc:
        db.rollback()
        raise SQLExecutionError(f"Unexpected query execution error: {str(exc)}") from exc
    finally:
        # Guarantee session rollback to ensure clean connection state
        try:
            db.rollback()
        except Exception:
            pass
