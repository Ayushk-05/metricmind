class SafeSQLError(Exception):
    """Base exception for all safe SQL engine errors."""
    pass


class SQLSecurityError(SafeSQLError):
    """Raised when a query violates security policies or guardrails."""
    pass


class SQLValidationError(SafeSQLError):
    """Raised when a query fails syntax or semantic validation."""
    pass


class SQLExecutionError(SafeSQLError):
    """Raised when a database execution error occurs during query execution."""
    pass
