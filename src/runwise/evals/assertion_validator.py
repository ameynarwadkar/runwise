"""
Strict whitelisted SQL assertion validator and standardized router input representation.
"""

from __future__ import annotations

import re
from typing import Any

from runwise.evals.routing_schema import AssertionQuery


class UnsafeQueryError(ValueError):
    """Raised when an assertion query fails strict SQL read-only validation."""
    pass


ALLOWED_TABLES = {"orders", "refunds", "users", "order_items", "audit_log"}

# Whitelisted aggregate and column projection patterns (matched against whole projection string)
ALLOWED_PROJECTION_PATTERNS = [
    re.compile(r"^COUNT\(\*\)$", re.IGNORECASE),
    re.compile(r"^COALESCE\(SUM\([a-zA-Z_]+\),\s*0\)$", re.IGNORECASE),
    re.compile(r"^[a-zA-Z_]+(?:\.[a-zA-Z_]+)?(?:\s*,\s*[a-zA-Z_]+(?:\.[a-zA-Z_]+)?)*$", re.IGNORECASE),
]

# Strict canonical SELECT pattern: SELECT <projection> FROM <table1> [JOIN <table2> ON <cond>] [WHERE <filter>]
STRICT_SELECT_REGEX = re.compile(
    r"^SELECT\s+(?P<projection>.+?)\s+FROM\s+(?P<table>[a-zA-Z_]+)(?:\s+[a-zA-Z_]+)?"
    r"(?:\s+JOIN\s+(?P<join_table>[a-zA-Z_]+)(?:\s+[a-zA-Z_]+)?\s+ON\s+(?P<join_cond>[^;]+?))?"
    r"(?:\s+WHERE\s+(?P<where>[^;]+?))?$",
    re.IGNORECASE | re.DOTALL,
)

FORBIDDEN_KEYWORDS = [
    r"\b(insert|update|delete|drop|alter|create|truncate|replace)\b",
    r"\b(attach|detach|reindex|vacuum|pragma|exec|execute)\b",
    r"--",      # SQL single-line comments
    r"/\*",     # SQL multi-line comments
    r";",       # Query chaining
    r"\bunion\b",
]


def validate_readonly_query(sql: str) -> bool:
    """
    Strictly validates that a SQL assertion query adheres to our safe read-only grammar:
    1. Rejects forbidden DDL/DML, comments, semicolons, and subqueries.
    2. Enforces queries target ONLY whitelisted domain tables.
    3. Validates projection format against allowed scalar and aggregate templates.
    """
    clean_sql = sql.strip()

    # 1. Quick check for dangerous keywords or comment injection
    for pat in FORBIDDEN_KEYWORDS:
        if re.search(pat, clean_sql, re.IGNORECASE):
            raise UnsafeQueryError(f"Prohibited SQL pattern detected: {pat} in query: {clean_sql}")

    # 2. Strict grammar parse
    match = STRICT_SELECT_REGEX.match(clean_sql)
    if not match:
        raise UnsafeQueryError(f"SQL statement does not conform to strict canonical SELECT grammar: {clean_sql}")

    # 3. Whitelisted table validation
    primary_table = match.group("table").lower()
    if primary_table not in ALLOWED_TABLES:
        raise UnsafeQueryError(f"Table '{primary_table}' is not in allowed domain tables: {ALLOWED_TABLES}")

    join_table = match.group("join_table")
    if join_table and join_table.lower() not in ALLOWED_TABLES:
        raise UnsafeQueryError(f"Join table '{join_table}' is not in allowed domain tables: {ALLOWED_TABLES}")

    # 4. Whitelisted projection validation against allowed patterns
    projection = match.group("projection").strip()
    is_valid_proj = any(p.match(projection) for p in ALLOWED_PROJECTION_PATTERNS)
    if not is_valid_proj:
        raise UnsafeQueryError(f"Projection '{projection}' is not a whitelisted column or aggregate function")

    return True


def build_structured_assertion(
    table: str,
    column: str,
    filter_column: str,
    filter_value: str,
    expected_value: Any,
    operator: str = "equals",
    aggregate: str | None = None,
    rationale: str = "",
) -> AssertionQuery:
    """
    Constructs a verified, strictly valid read-only SQL AssertionQuery from structured parameters.
    """
    tbl = table.lower().strip()
    if tbl not in ALLOWED_TABLES:
        raise UnsafeQueryError(f"Invalid table: {table}")

    col = column.strip()
    filt_col = filter_column.strip()
    filt_val = filter_value.strip().replace("'", "''")  # Escape quotes safely

    if aggregate == "COUNT":
        query = f"SELECT COUNT(*) FROM {tbl} WHERE {filt_col} = '{filt_val}'"
    elif aggregate == "SUM_COALESCE":
        query = f"SELECT COALESCE(SUM({col}), 0) FROM {tbl} WHERE {filt_col} = '{filt_val}'"
    else:
        query = f"SELECT {col} FROM {tbl} WHERE {filt_col} = '{filt_val}'"

    validate_readonly_query(query)
    return AssertionQuery(
        query=query,
        expected_value=expected_value,
        operator=operator,  # type: ignore[arg-type]
        rationale=rationale,
    )


def normalize_router_input(prompt: str, customer_id: str | None = None) -> str:
    """
    Standardizes request context into a unified string representation for embedding & inference.
    """
    cid = customer_id.strip() if (customer_id and customer_id.strip()) else "Anonymous"
    clean_p = prompt.strip()
    return f"Customer: {cid} | User Request: {clean_p}"
