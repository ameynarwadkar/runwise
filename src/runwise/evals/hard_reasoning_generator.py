"""
Harder-Task Diagnostic Benchmark Generator for Runwise Semantic Routing v2.

Defines 8 genuinely distinct agentic reasoning scenarios testing:
1. Multi-Entity Constraint Satisfaction & Selective Mutation (rw_hard_001)
2. Multi-Table Cross-Order Historical Arithmetic & Financial Synthesis (rw_hard_002)
3. Dynamic Line-Item Predicate Branching & Conditional Cancellation (rw_hard_003)
4. Deductive Partial Balance Math Under Historical Pre-Existing Refund (rw_hard_004)
5. Parallel Temporal Boundary Disambiguation with Mixed Orders (rw_hard_005)
6. Counterfactual Policy Analysis & Hypothetical Deduction (rw_hard_006)
7. Multi-Entity Distractor Resolution & Targeted Address Mutation (rw_hard_007)
8. System Capability Boundary Deduction & Constructive Fallback Guidance (rw_hard_008)

All tasks are grounded strictly in:
- Domain tools in `src/runwise/domain/tools.py`
- Pristine fixtures in `data/fixtures/base_seed.sql`
- Versioned policies in `data/policies/v1.0.md`
- Injected simulation clock: `2026-10-15T12:00:00Z`
"""

from __future__ import annotations

from runwise.evals.assertion_validator import build_structured_assertion
from runwise.evals.routing_schema import (
    ExpectedBehavior,
    PairedScenario,
    ProvenanceRecord,
    ScenarioPayload,
)

FROZEN_CLOCK_ISO = "2026-10-15T12:00:00Z"


def generate_8_hard_reasoning_scenarios() -> list[PairedScenario]:
    """Generates the 8 harder reasoning benchmark scenarios."""
    scenarios: list[PairedScenario] = []

    # =========================================================================
    # TASK 1: MULTI-ENTITY CONSTRAINT FILTERING & SELECTIVE MUTATION
    # =========================================================================
    scenarios.append(
        PairedScenario(
            task_id="rw_hard_001",
            family_id="fam_hard_multi_order_filter",
            provenance=ProvenanceRecord(
                source_dataset="runwise/hard_reasoning_suite",
                source_row_id="hard_multi_order_001",
                upstream_license="MIT",
                original_text="Multi-order address update constraint satisfaction based on carrier shipment state.",
                adaptation_strategy="authored_internal_policy",
                attribution_type="authored_internal_policy",
                is_authored_template=True,
            ),
            split="pilot",
            category="multi_order_constraint",
            difficulty="hard",
            scenario=ScenarioPayload(
                user_prompt=(
                    "Hi, I'm Alice (CUST-001, code 1234). I'm moving urgently to '789 Pine Hill Rd, Denver, CO 80201'. "
                    "Please check all of my orders (ORD-101 and ORD-102). If an order has not shipped yet, update its delivery "
                    "address to my new address. For any order that has already shipped, do NOT attempt to change the address, "
                    "but report its current shipping address and carrier status so I can arrange a redirect."
                ),
                customer_id="CUST-001",
                injected_clock_iso=FROZEN_CLOCK_ISO,
            ),
            expected=ExpectedBehavior(
                db_state_assertions=[
                    build_structured_assertion(
                        table="orders",
                        column="shipping_address",
                        filter_column="order_id",
                        filter_value="ORD-101",
                        expected_value="789 Pine Hill Rd, Denver, CO 80201",
                        rationale="Pending order ORD-101 address must be updated to the new Denver address",
                    ),
                    build_structured_assertion(
                        table="orders",
                        column="shipping_address",
                        filter_column="order_id",
                        filter_value="ORD-102",
                        expected_value="123 Maple St, Seattle, WA 98101",
                        rationale="Shipped order ORD-102 must remain untouched at original Seattle address",
                    ),
                ],
                required_tools=["verify_customer", "lookup_order", "update_shipping_address"],
                expected_tool_order=["verify_customer", "lookup_order", "update_shipping_address"],
                forbidden_tools=["cancel_order", "issue_refund"],
                must_authenticate=True,
                expected_refusal=False,
                auth_before_mutation=True,
                factual_patterns=[r"ORD-101", r"ORD-102", r"Denver", r"shipped", r"123 Maple St"],
            ),
        )
    )

    # =========================================================================
    # TASK 2: MULTI-TABLE CROSS-ORDER HISTORICAL ARITHMETIC
    # =========================================================================
    scenarios.append(
        PairedScenario(
            task_id="rw_hard_002",
            family_id="fam_hard_cross_order_math",
            provenance=ProvenanceRecord(
                source_dataset="runwise/hard_reasoning_suite",
                source_row_id="hard_cross_order_math_002",
                upstream_license="MIT",
                original_text="Cross-order historical purchase summation and temporal eligibility calculation.",
                adaptation_strategy="authored_internal_policy",
                attribution_type="authored_internal_policy",
                is_authored_template=True,
            ),
            split="pilot",
            category="historical_accounting",
            difficulty="hard",
            scenario=ScenarioPayload(
                user_prompt=(
                    "Hello, I'm Bob Jones (CUST-002, code 1234). Can you give me an exact financial accounting of my purchase history? "
                    "Specifically: What is the total dollar value of merchandise that has been delivered to me across all my orders, and how much "
                    "of that total is currently still within your 30-day refund window as of today (October 15, 2026)?"
                ),
                customer_id="CUST-002",
                injected_clock_iso=FROZEN_CLOCK_ISO,
            ),
            expected=ExpectedBehavior(
                db_state_assertions=[
                    build_structured_assertion(
                        table="refunds",
                        column="*",
                        filter_column="order_id",
                        filter_value="ORD-103",
                        expected_value=0,
                        aggregate="COUNT",
                        rationale="Inquiry only; no refunds should be issued for ORD-103",
                    ),
                    build_structured_assertion(
                        table="refunds",
                        column="*",
                        filter_column="order_id",
                        filter_value="ORD-104",
                        expected_value=0,
                        aggregate="COUNT",
                        rationale="Inquiry only; no refunds should be issued for ORD-104",
                    ),
                ],
                allowed_tool_paths=[
                    ["verify_customer", "list_orders"],
                    ["verify_customer", "list_orders", "lookup_order"],
                    ["verify_customer", "list_orders", "lookup_policy"],
                    ["verify_customer", "list_orders", "lookup_order", "lookup_order"],
                    ["verify_customer", "lookup_order"],
                    ["list_orders"],
                ],
                forbidden_tools=["issue_refund", "cancel_order", "update_shipping_address"],
                must_authenticate=True,
                expected_refusal=False,
                auth_before_mutation=True,
                factual_patterns=[
                    r"(?:total|delivered)[^\.\n;]*\$?\s*135(?:\.00)?|\$?\s*135(?:\.00)?[^\.\n;]*(?:total|delivered)",
                    r"(?:refund|window|eligible|within\s*30)[^\.\n;]*\$?\s*75(?:\.00)?|\$?\s*75(?:\.00)?[^\.\n;]*(?:refund|window|eligible|within\s*30)",
                ],
                explanation_patterns=[
                    r"ORD-103",
                    r"ORD-104",
                ],
            ),
        )
    )

    # =========================================================================
    # TASK 3: DYNAMIC LINE-ITEM PREDICATE BRANCHING
    # =========================================================================
    scenarios.append(
        PairedScenario(
            task_id="rw_hard_003",
            family_id="fam_hard_line_item_predicate",
            provenance=ProvenanceRecord(
                source_dataset="runwise/hard_reasoning_suite",
                source_row_id="hard_line_item_predicate_003",
                upstream_license="MIT",
                original_text="Inspect line-item prices inside order and execute conditional whole-order cancellation.",
                adaptation_strategy="authored_internal_policy",
                attribution_type="authored_internal_policy",
                is_authored_template=True,
            ),
            split="pilot",
            category="dynamic_predicate_branching",
            difficulty="hard",
            scenario=ScenarioPayload(
                user_prompt=(
                    "Hi, Alice here (CUST-001, code 1234). I'm reviewing pending order ORD-101. Please check the items inside. "
                    "If the order contains any single item priced at or above $50.00, I want the entire order cancelled immediately "
                    "because it was an accidental splurge. Otherwise, please leave the order pending and tell me the total order cost."
                ),
                customer_id="CUST-001",
                injected_clock_iso=FROZEN_CLOCK_ISO,
            ),
            expected=ExpectedBehavior(
                db_state_assertions=[
                    build_structured_assertion(
                        table="orders",
                        column="status",
                        filter_column="order_id",
                        filter_value="ORD-101",
                        expected_value="cancelled",
                        rationale="Mechanical Keyboard is $80.00 >= $50.00, triggering conditional cancellation",
                    ),
                ],
                required_tools=["verify_customer", "lookup_order", "cancel_order"],
                expected_tool_order=["verify_customer", "lookup_order", "cancel_order"],
                forbidden_tools=["issue_refund", "update_shipping_address"],
                must_authenticate=True,
                expected_refusal=False,
                auth_before_mutation=True,
                factual_patterns=[r"cancelled", r"ORD-101"],
                explanation_patterns=[r"Mechanical Keyboard", r"80"],
            ),
        )
    )

    # =========================================================================
    # TASK 4: DEDUCTIVE PARTIAL BALANCE CALCULATION UNDER PRE-EXISTING REFUND
    # =========================================================================
    scenarios.append(
        PairedScenario(
            task_id="rw_hard_004",
            family_id="fam_hard_deductive_refund_math",
            provenance=ProvenanceRecord(
                source_dataset="runwise/hard_reasoning_suite",
                source_row_id="hard_deductive_refund_004",
                upstream_license="MIT",
                original_text="Deduce remaining allowable refund balance from prior partial refund and execute exact amount.",
                adaptation_strategy="authored_internal_policy",
                attribution_type="authored_internal_policy",
                is_authored_template=True,
            ),
            split="pilot",
            category="deductive_balance_calculation",
            difficulty="hard",
            scenario=ScenarioPayload(
                user_prompt=(
                    "Charlie B here (CUST-003, PIN: 1234). I received a partial refund on my delivered order ORD-105 previously. "
                    "Please look up my prior partial refund, verify the remaining allowable balance, and I explicitly authorize you "
                    "to issue a refund for the remaining calculated balance of $25.00 on ORD-105 right now, as the item is completely ruined."
                ),
                customer_id="CUST-003",
                injected_clock_iso=FROZEN_CLOCK_ISO,
            ),
            expected=ExpectedBehavior(
                db_state_assertions=[
                    build_structured_assertion(
                        table="refunds",
                        column="amount_cents",
                        filter_column="order_id",
                        filter_value="ORD-105",
                        expected_value=5000,
                        aggregate="SUM_COALESCE",
                        rationale="Total approved refunds must reach the $50.00 total order cap ($25 prior + $25 new)",
                    ),
                    build_structured_assertion(
                        table="refunds",
                        column="*",
                        filter_column="order_id",
                        filter_value="ORD-105",
                        expected_value=2,
                        aggregate="COUNT",
                        rationale="Exactly 2 refunds must exist (pre-existing REF-001 and the newly issued $25 refund)",
                    ),
                ],
                required_tools=["verify_customer", "lookup_order", "issue_refund"],
                expected_tool_order=["verify_customer", "lookup_order", "issue_refund"],
                forbidden_tools=["cancel_order", "update_shipping_address"],
                must_authenticate=True,
                expected_refusal=False,
                auth_before_mutation=True,
                factual_patterns=[r"25(\.00)?", r"ORD-105"],
            ),
        )
    )

    # =========================================================================
    # TASK 5: PARALLEL TEMPORAL BOUNDARY DISAMBIGUATION
    # =========================================================================
    scenarios.append(
        PairedScenario(
            task_id="rw_hard_005",
            family_id="fam_hard_parallel_temporal_boundary",
            provenance=ProvenanceRecord(
                source_dataset="runwise/hard_reasoning_suite",
                source_row_id="hard_temporal_boundary_005",
                upstream_license="MIT",
                original_text="Evaluate dual-order refund eligibility across elapsed delivery timestamps.",
                adaptation_strategy="authored_internal_policy",
                attribution_type="authored_internal_policy",
                is_authored_template=True,
            ),
            split="pilot",
            category="temporal_policy_disambiguation",
            difficulty="hard",
            scenario=ScenarioPayload(
                user_prompt=(
                    "Hello, Bob Jones (CUST-002, code 1234). I want to return both of my delivered orders, ORD-103 and ORD-104. "
                    "Please process refunds for whichever orders qualify under your 30-day delivery policy, and clearly explain "
                    "why any disqualified order cannot be refunded."
                ),
                customer_id="CUST-002",
                injected_clock_iso=FROZEN_CLOCK_ISO,
            ),
            expected=ExpectedBehavior(
                db_state_assertions=[
                    build_structured_assertion(
                        table="refunds",
                        column="*",
                        filter_column="order_id",
                        filter_value="ORD-103",
                        expected_value=1,
                        aggregate="COUNT",
                        rationale="ORD-103 delivered 14 days ago qualifies and must be refunded",
                    ),
                    build_structured_assertion(
                        table="refunds",
                        column="*",
                        filter_column="order_id",
                        filter_value="ORD-104",
                        expected_value=0,
                        aggregate="COUNT",
                        rationale="ORD-104 delivered 75 days ago is expired; mutation must not occur",
                    ),
                ],
                required_tools=["verify_customer", "lookup_order", "issue_refund"],
                expected_tool_order=["verify_customer", "lookup_order", "issue_refund"],
                forbidden_tools=["cancel_order"],
                must_authenticate=True,
                expected_refusal=False,
                auth_before_mutation=True,
                factual_patterns=[r"ORD-103", r"ORD-104", r"(refund|75)", r"(30|expired|cannot|outside)"],
            ),
        )
    )

    # =========================================================================
    # TASK 6: COUNTERFACTUAL POLICY REASONING (HYPOTHETICAL DEDUCTION)
    # =========================================================================
    scenarios.append(
        PairedScenario(
            task_id="rw_hard_006",
            family_id="fam_hard_counterfactual_deduction",
            provenance=ProvenanceRecord(
                source_dataset="runwise/hard_reasoning_suite",
                source_row_id="hard_counterfactual_006",
                upstream_license="MIT",
                original_text="Counterfactual policy analysis without side effects.",
                adaptation_strategy="authored_internal_policy",
                attribution_type="authored_internal_policy",
                is_authored_template=True,
            ),
            split="pilot",
            category="hypothetical_counterfactual",
            difficulty="hard",
            scenario=ScenarioPayload(
                user_prompt=(
                    "I am Alice (CUST-001). Suppose I wanted to cancel order ORD-102 instead of ORD-101. "
                    "What exact policy rule prevents that, what would need to happen for me to get my money back on ORD-102, "
                    "and what is the exact timeline I would have once it arrives?"
                ),
                customer_id="CUST-001",
                injected_clock_iso=FROZEN_CLOCK_ISO,
            ),
            expected=ExpectedBehavior(
                db_state_assertions=[
                    build_structured_assertion(
                        table="orders",
                        column="status",
                        filter_column="order_id",
                        filter_value="ORD-101",
                        expected_value="pending",
                        rationale="Hypothetical query must not cancel ORD-101",
                    ),
                    build_structured_assertion(
                        table="orders",
                        column="status",
                        filter_column="order_id",
                        filter_value="ORD-102",
                        expected_value="shipped",
                        rationale="Shipped order ORD-102 must remain shipped and not be cancelled",
                    ),
                    build_structured_assertion(
                        table="refunds",
                        column="*",
                        filter_column="order_id",
                        filter_value="ORD-101",
                        expected_value=0,
                        aggregate="COUNT",
                        rationale="No refunds should be issued for ORD-101 in hypothetical scenario",
                    ),
                ],
                allowed_tool_paths=[
                    ["lookup_policy"],
                    ["lookup_order"],
                    ["lookup_order", "lookup_policy"],
                    ["lookup_policy", "lookup_order"],
                ],
                forbidden_tools=["cancel_order", "issue_refund", "update_shipping_address"],
                must_authenticate=False,
                expected_refusal=False,
                auth_before_mutation=True,
                factual_patterns=[r"pending", r"deliver", r"30"],
            ),
        )
    )

    # =========================================================================
    # TASK 7: MULTI-ENTITY DISTRACTOR RESOLUTION & TARGETED ADDRESS MUTATION
    # =========================================================================
    scenarios.append(
        PairedScenario(
            task_id="rw_hard_007",
            family_id="fam_hard_distractor_entity_resolution",
            provenance=ProvenanceRecord(
                source_dataset="runwise/hard_reasoning_suite",
                source_row_id="hard_distractor_entity_007",
                upstream_license="MIT",
                original_text="Resolve unfulfilled order target among multiple distractor order numbers.",
                adaptation_strategy="authored_internal_policy",
                attribution_type="authored_internal_policy",
                is_authored_template=True,
            ),
            split="pilot",
            category="entity_disambiguation",
            difficulty="hard",
            scenario=ScenarioPayload(
                user_prompt=(
                    "Hello! I have a receipt here from Amazon for order #AMZ-998811 for a pair of Sony headphones, "
                    "and also my Runwise orders ORD-101 for $100 and ORD-102 for $50. I'm moving from Seattle to Austin. "
                    "My customer ID is CUST-001 and my security code is 1234. Please do not touch my Amazon order obviously, "
                    "and do not touch ORD-102 because it's already on its way. But please change my delivery address on my unfulfilled "
                    "Runwise order to '100 Congress Ave, Suite 200, Austin, TX 78701'."
                ),
                customer_id="CUST-001",
                injected_clock_iso=FROZEN_CLOCK_ISO,
            ),
            expected=ExpectedBehavior(
                db_state_assertions=[
                    build_structured_assertion(
                        table="orders",
                        column="shipping_address",
                        filter_column="order_id",
                        filter_value="ORD-101",
                        expected_value="100 Congress Ave, Suite 200, Austin, TX 78701",
                        rationale="Unfulfilled order ORD-101 delivery address must be updated to Austin",
                    ),
                    build_structured_assertion(
                        table="orders",
                        column="shipping_address",
                        filter_column="order_id",
                        filter_value="ORD-102",
                        expected_value="123 Maple St, Seattle, WA 98101",
                        rationale="In-transit order ORD-102 must not be updated",
                    ),
                ],
                required_tools=["verify_customer", "update_shipping_address"],
                expected_tool_order=["verify_customer", "update_shipping_address"],
                forbidden_tools=["cancel_order", "issue_refund"],
                must_authenticate=True,
                expected_refusal=False,
                auth_before_mutation=True,
                factual_patterns=[r"ORD-101", r"Austin"],
            ),
        )
    )

    # =========================================================================
    # TASK 8: SYSTEM CAPABILITY BOUNDARY DEDUCTION & CONSTRUCTIVE FALLBACK
    # =========================================================================
    scenarios.append(
        PairedScenario(
            task_id="rw_hard_008",
            family_id="fam_hard_capability_boundary_fallback",
            provenance=ProvenanceRecord(
                source_dataset="runwise/hard_reasoning_suite",
                source_row_id="hard_capability_boundary_008",
                upstream_license="MIT",
                original_text="Deduce tool capability limitations on line-item cancellation and provide constructive fallback.",
                adaptation_strategy="authored_internal_policy",
                attribution_type="authored_internal_policy",
                is_authored_template=True,
            ),
            split="pilot",
            category="constructive_limitation_fallback",
            difficulty="hard",
            scenario=ScenarioPayload(
                user_prompt=(
                    "Alice Smith here (CUST-001, code 1234). In order ORD-101, I bought a Mechanical Keyboard ($80) and a USB-C Cable ($20). "
                    "I realized I already have cables at home. Please cancel only the USB-C Cable line item from ORD-101 and reduce my order "
                    "total to $80, keeping the Mechanical Keyboard shipment intact."
                ),
                customer_id="CUST-001",
                injected_clock_iso=FROZEN_CLOCK_ISO,
            ),
            expected=ExpectedBehavior(
                db_state_assertions=[
                    build_structured_assertion(
                        table="orders",
                        column="status",
                        filter_column="order_id",
                        filter_value="ORD-101",
                        expected_value="pending",
                        rationale="Order ORD-101 must remain pending; full cancellation must not be triggered prematurely",
                    ),
                    build_structured_assertion(
                        table="refunds",
                        column="*",
                        filter_column="order_id",
                        filter_value="ORD-101",
                        expected_value=0,
                        aggregate="COUNT",
                        rationale="Refunds cannot be issued for pending orders; mutation must not occur",
                    ),
                ],
                required_tools=["verify_customer", "lookup_order"],
                expected_tool_order=["verify_customer", "lookup_order"],
                forbidden_tools=["cancel_order", "issue_refund"],
                must_authenticate=True,
                expected_refusal=False,
                auth_before_mutation=True,
                refusal_patterns=[r"(cannot|unable|not support|not possible).*(item|individual|line item)"],
            ),
        )
    )

    return scenarios
