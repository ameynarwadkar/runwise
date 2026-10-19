import pytest
from runwise.evals.canonical_runner import (
    compute_canonical_suite_hash,
    verify_preflight_security_invariants,
    CANONICAL_SUITE_EXPECTED_HASH,
)


def test_canonical_suite_sha256():
    computed_hash = compute_canonical_suite_hash()
    assert (
        computed_hash == CANONICAL_SUITE_EXPECTED_HASH
    ), f"Suite hash mismatch: expected {CANONICAL_SUITE_EXPECTED_HASH}, got {computed_hash}"


def test_all_7_preflight_security_invariants():
    # Should run and complete without raising any RuntimeError
    verify_preflight_security_invariants()
