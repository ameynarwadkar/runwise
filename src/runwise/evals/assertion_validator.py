"""
Whitelisted SQL assertion validator and standardized router input representation.
"""

from __future__ import annotations

import re


class UnsafeQueryError(ValueError):
    """Raised when an assertion query contains forbidden statements or mutation verbs."""
    pass


# Strict disallowance of data modification, schema changes, execution of arbitrary commands, or pragma mutations
FORBIDDEN_SQL_PATTERNS = [
    r"(?i)\b(insert|update|delete|drop|alter|create|truncate|replace)\b",
    r"(?i)\b(attach|detach|reindex|vacuum|pragma)\b",
    r";",  # Prevent statement chaining / piggybacked SQL injection
]


def validate_readonly_query(sql: str) -> bool:
    """
    Validates that a SQL assertion query is strictly a read-only SELECT statement.
    
    Raises:
        UnsafeQueryError: If the statement does not start with SELECT or contains mutation verbs.
    """
    stripped = sql.strip()
    if not re.match(r"(?i)^select\b", stripped):
        raise UnsafeQueryError(f"Assertion SQL must begin with SELECT: {sql}")

    for pattern in FORBIDDEN_SQL_PATTERNS:
        if re.search(pattern, stripped):
            raise UnsafeQueryError(f"Prohibited SQL pattern detected in assertion query: {pattern}")

    return True


def normalize_router_input(prompt: str, customer_id: str | None = None) -> str:
    """
    Standardizes request context into a unified string representation for embedding & inference.
    
    This exact formatting MUST be preserved across dataset generation, training feature extraction,
    and production serving to guarantee zero distribution shift.
    """
    cid = customer_id.strip() if (customer_id and customer_id.strip()) else "Anonymous"
    clean_p = prompt.strip()
    return f"Customer: {cid} | User Request: {clean_p}"
