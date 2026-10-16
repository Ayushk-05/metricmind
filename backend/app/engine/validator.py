import re
from typing import Optional, Set

from app.core.config import settings
from app.engine.exceptions import SQLSecurityError, SQLValidationError

# Approved analytical tables for MetricMind
APPROVED_TABLES: Set[str] = {
    "customers",
    "products",
    "orders",
    "order_items",
}

# Dangerous / mutating keywords that must never appear in analytical queries
FORBIDDEN_KEYWORDS: Set[str] = {
    "INSERT",
    "UPDATE",
    "DELETE",
    "DROP",
    "ALTER",
    "TRUNCATE",
    "CREATE",
    "REPLACE",
    "GRANT",
    "REVOKE",
    "LOCK",
    "EXECUTE",
    "PREPARE",
    "DEALLOCATE",
    "COPY",
    "VACUUM",
    "ANALYZE",
    "REINDEX",
    "DISCARD",
    "CALL",
    "DO",
    "ATTACH",
    "DETACH",
}

# Dangerous system functions, catalogs, and schemas
DANGEROUS_PATTERNS: Set[str] = {
    "PG_READ_FILE",
    "PG_WRITE_FILE",
    "PG_LS_DIR",
    "PG_SLEEP",
    "PG_TERMINATE_BACKEND",
    "PG_CANCEL_BACKEND",
    "DBLINK",
    "LO_EXPORT",
    "LO_IMPORT",
    "CURRENT_SETTING",
    "SET_CONFIG",
    "PG_CATALOG",
    "INFORMATION_SCHEMA",
    "PG_TOAST",
    "PG_SHADOW",
    "PG_AUTHID",
    "PG_DATABASE",
}


def remove_sql_comments(sql: str) -> str:
    """Safely removes single-line (-- ...) and multi-line (/* ... */) comments

    Preserves text inside single and double quotes.
    """
    result = []
    i = 0
    n = len(sql)
    in_single_quote = False
    in_double_quote = False

    while i < n:
        char = sql[i]

        if char == "'" and not in_double_quote:
            # Check for escaped single quote ''
            if in_single_quote and i + 1 < n and sql[i + 1] == "'":
                result.append("''")
                i += 2
                continue
            in_single_quote = not in_single_quote
            result.append(char)
            i += 1
        elif char == '"' and not in_single_quote:
            in_double_quote = not in_double_quote
            result.append(char)
            i += 1
        elif not in_single_quote and not in_double_quote:
            # Single-line comment --
            if char == "-" and i + 1 < n and sql[i + 1] == "-":
                i += 2
                while i < n and sql[i] != "\n":
                    i += 1
                if i < n and sql[i] == "\n":
                    result.append(" ")
                    i += 1
            # Multi-line comment /* ... */
            elif char == "/" and i + 1 < n and sql[i + 1] == "*":
                i += 2
                while i + 1 < n and not (sql[i] == "*" and sql[i + 1] == "/"):
                    i += 1
                i += 2  # skip */
                result.append(" ")
            else:
                result.append(char)
                i += 1
        else:
            result.append(char)
            i += 1

    return "".join(result).strip()


def extract_tokens_outside_quotes(sql: str) -> list[str]:
    """Tokenizes SQL identifiers and keywords while stripping out string literals."""
    no_strings = re.sub(r"'(?:''|[^'])*'", " ", sql)
    return re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", no_strings)


def extract_cte_names(sql: str) -> Set[str]:
    """Extracts CTE (Common Table Expression) aliases defined in a WITH clause."""
    cte_names = set()
    cleaned = re.sub(r"'(?:''|[^'])*'", " ", sql)
    matches = re.finditer(
        r"(?:WITH|,)\s+([A-Za-z_][A-Za-z0-9_]*)\s+AS\s*\(",
        cleaned,
        re.IGNORECASE,
    )
    for m in matches:
        cte_names.add(m.group(1).lower())
    return cte_names


def extract_referenced_tables(sql: str) -> Set[str]:
    """Extracts table names referenced in FROM and JOIN clauses."""
    cleaned = re.sub(r"'(?:''|[^'])*'", " ", sql)
    tables = set()

    # Match JOIN <table_name>
    join_pattern = r"\b(?:JOIN)\s+([A-Za-z_][A-Za-z0-9_\.]*)"
    for match in re.finditer(join_pattern, cleaned, re.IGNORECASE):
        tbl = match.group(1).strip()
        if not tbl.startswith("("):
            tbl_name = tbl.split(".")[-1].lower()
            tables.add(tbl_name)

    # Match FROM <table_name(s)> up to next clause boundary
    from_pattern = r"\bFROM\s+([A-Za-z0-9_\.,\s]+?)(?=\b(?:WHERE|GROUP\s+BY|ORDER\s+BY|HAVING|LIMIT|WINDOW|UNION|INTERSECT|EXCEPT|JOIN|LEFT\s+JOIN|RIGHT\s+JOIN|INNER\s+JOIN|FULL\s+JOIN|CROSS\s+JOIN)\b|\)|\s*$)"
    for match in re.finditer(from_pattern, cleaned, re.IGNORECASE):
        from_part = match.group(1)
        items = from_part.split(",")
        for item in items:
            tokens = item.strip().split()
            if tokens:
                candidate = tokens[0].strip()
                if candidate and not candidate.startswith("("):
                    tbl_name = candidate.split(".")[-1].lower()
                    tables.add(tbl_name)

    return tables


def apply_limit_guardrail(sql: str, default_limit: int, max_limit: int) -> str:
    """Enforces row limit: adds default limit if missing, or clamps existing limit to max_limit."""
    limit_match = re.search(r"\bLIMIT\s+(\d+)\b", sql, re.IGNORECASE)
    if limit_match:
        current_limit = int(limit_match.group(1))
        if current_limit > max_limit:
            sql = (
                sql[: limit_match.start()]
                + f"LIMIT {max_limit}"
                + sql[limit_match.end() :]
            )
        return sql

    return f"{sql} LIMIT {default_limit}"


def validate_safe_sql(
    sql: str,
    allowed_tables: Optional[Set[str]] = None,
    default_limit: Optional[int] = None,
    max_limit: Optional[int] = None,
) -> str:
    """Validates that a SQL query is safe, read-only, references approved tables,

    and enforces limit guardrails.

    Returns the sanitized, limit-enforced SQL query.
    Raises SQLSecurityError or SQLValidationError if security checks fail.
    """
    if not sql or not sql.strip():
        raise SQLValidationError("Query cannot be empty.")

    # 1. Clean comments and strip whitespace
    cleaned = remove_sql_comments(sql).strip()
    if not cleaned:
        raise SQLValidationError("Query is empty after comment removal.")

    # 2. Check for multiple statements / semicolon injection
    if cleaned.endswith(";"):
        cleaned = cleaned[:-1].strip()

    no_strings = re.sub(r"'(?:''|[^'])*'", " ", cleaned)
    if ";" in no_strings:
        raise SQLSecurityError("Multiple statements are not permitted.")

    # 3. Check for forbidden keywords and dangerous patterns first
    tokens = extract_tokens_outside_quotes(cleaned)
    upper_tokens = [t.upper() for t in tokens]

    for token in upper_tokens:
        if token in FORBIDDEN_KEYWORDS:
            raise SQLSecurityError(
                f"Forbidden operation '{token}' is not permitted in analytical queries."
            )
        if token in DANGEROUS_PATTERNS:
            raise SQLSecurityError(
                f"Access to restricted system function or catalog '{token}' is blocked."
            )

    # 4. Check allowed statement start (SELECT or WITH)
    upper_start = cleaned.lstrip()[:10].upper()
    if not (upper_start.startswith("SELECT") or upper_start.startswith("WITH")):
        raise SQLSecurityError(
            "Only SELECT queries and read-only WITH (CTE) queries are permitted."
        )

    # 5. Check approved tables
    effective_allowed = (
        set(t.lower() for t in allowed_tables)
        if allowed_tables is not None
        else APPROVED_TABLES
    )

    cte_names = extract_cte_names(cleaned)
    all_allowed = effective_allowed | cte_names

    referenced_tables = extract_referenced_tables(cleaned)
    for table in referenced_tables:
        if table not in all_allowed:
            raise SQLSecurityError(
                f"Access to table '{table}' is not permitted. "
                f"Approved tables: {', '.join(sorted(effective_allowed))}."
            )

    # 6. Apply row limit guardrail
    def_limit = (
        default_limit
        if default_limit is not None
        else settings.DEFAULT_QUERY_ROW_LIMIT
    )
    m_limit = (
        max_limit if max_limit is not None else settings.MAX_QUERY_ROW_LIMIT
    )

    safe_sql = apply_limit_guardrail(cleaned, def_limit, m_limit)
    return safe_sql
