"""
Unit Tests for Token Economics and Cost Modeling Engine.
"""

from runwise.service.cost import (
    calculate_cost_breakdown,
    format_cost_table,
    get_price_card,
)


def test_pricing_lookup_and_defaults():
    card_flash = get_price_card("vertex_ai/gemini-2.5-flash")
    assert card_flash.input_per_million_usd == 0.075
    assert card_flash.output_per_million_usd == 0.300

    card_pro = get_price_card("gemini-2.5-pro")
    assert card_pro.input_per_million_usd == 1.250
    assert card_pro.output_per_million_usd == 5.000

    card_fallback = get_price_card("unknown-model-name")
    assert card_fallback.model_identifier == "vertex_ai/gemini-2.5-flash"


def test_cost_calculation_math():
    # 10,000 prompt tokens * $0.075/1M = $0.00075
    # 1,000 completion tokens * $0.300/1M = $0.00030
    # Total = $0.00105
    breakdown = calculate_cost_breakdown(
        model="gemini-2.5-flash",
        prompt_tokens=10_000,
        completion_tokens=1_000,
        success_rate=1.0,
    )
    assert abs(breakdown.prompt_cost_usd - 0.00075) < 1e-6
    assert abs(breakdown.completion_cost_usd - 0.00030) < 1e-6
    assert abs(breakdown.total_cost_usd - 0.00105) < 1e-6
    assert abs(breakdown.cost_per_1k_successes - 1.050) < 1e-3


def test_cost_per_thousand_adjusts_for_availability():
    # If success rate is 50%, it requires 2,000 requests to get 1,000 successes
    b_100 = calculate_cost_breakdown("gemini-2.5-flash", prompt_tokens=1000, completion_tokens=100, success_rate=1.0)
    b_50 = calculate_cost_breakdown("gemini-2.5-flash", prompt_tokens=1000, completion_tokens=100, success_rate=0.50)
    assert abs(b_50.cost_per_1k_successes - (b_100.cost_per_1k_successes * 2)) < 1e-5


def test_monthly_projection_calculation():
    breakdown = calculate_cost_breakdown("gemini-2.5-flash", prompt_tokens=1000, completion_tokens=100)
    # 10k/day * 30 days * cost_per_req
    expected_10k = 300_000 * breakdown.total_cost_usd
    assert abs(breakdown.projected_monthly_10k_daily - expected_10k) < 0.05


def test_format_cost_table_markdown():
    b_base = calculate_cost_breakdown("gemini-2.5-flash", prompt_tokens=650, completion_tokens=60)
    b_opt = calculate_cost_breakdown("gemini-2.5-flash", prompt_tokens=450, completion_tokens=60)
    table = format_cost_table(b_base, b_opt)
    assert "Stable Baseline" in table
    assert "Optimized / Trimmed" in table
    assert "-30.8%" in table
