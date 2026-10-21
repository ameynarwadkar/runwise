"""
Token Economics & Cost Modeling Engine.

Implements cost analytics and capacity projections:
1. Provider Price Cards: Official per-million token rates for Gemini 2.5 Flash, Pro, etc.
2. Unit Economics: Cost per request and cost per 1,000 successful requests.
3. Cost Dominance Analysis: Evaluates input vs output token cost distribution.
4. Volume Projections: Estimates monthly expenditure at target daily request volumes.
"""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class ModelPriceCard(BaseModel):
    """Token pricing card per 1,000,000 tokens in USD."""
    model_identifier: str
    input_per_million_usd: float
    output_per_million_usd: float

    @property
    def input_per_token_usd(self) -> float:
        return self.input_per_million_usd / 1_000_000.0

    @property
    def output_per_token_usd(self) -> float:
        return self.output_per_million_usd / 1_000_000.0


# Official Google Cloud Vertex AI & Gemini Pricing (October 2026)
PRICING_REGISTRY: dict[str, ModelPriceCard] = {
    # Gemini 2.5 Flash: $0.075 / 1M input, $0.300 / 1M output
    "gemini-2.5-flash": ModelPriceCard(
        model_identifier="gemini-2.5-flash",
        input_per_million_usd=0.075,
        output_per_million_usd=0.300,
    ),
    "vertex_ai/gemini-2.5-flash": ModelPriceCard(
        model_identifier="vertex_ai/gemini-2.5-flash",
        input_per_million_usd=0.075,
        output_per_million_usd=0.300,
    ),
    # Gemini 2.5 Pro: $1.250 / 1M input, $5.000 / 1M output
    "gemini-2.5-pro": ModelPriceCard(
        model_identifier="gemini-2.5-pro",
        input_per_million_usd=1.250,
        output_per_million_usd=5.000,
    ),
    "vertex_ai/gemini-2.5-pro": ModelPriceCard(
        model_identifier="vertex_ai/gemini-2.5-pro",
        input_per_million_usd=1.250,
        output_per_million_usd=5.000,
    ),
}

DEFAULT_PRICE_CARD = PRICING_REGISTRY["vertex_ai/gemini-2.5-flash"]


def get_price_card(model: str) -> ModelPriceCard:
    """Resolves price card for model name, falling back to flash pricing."""
    if model in PRICING_REGISTRY:
        return PRICING_REGISTRY[model]
    for key, card in PRICING_REGISTRY.items():
        if key in model or model in key:
            return card
    return DEFAULT_PRICE_CARD


class CostBreakdown(BaseModel):
    """Detailed unit economics for an agent execution or evaluation suite."""
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    prompt_cost_usd: float
    completion_cost_usd: float
    total_cost_usd: float
    input_cost_ratio: float       # Percentage of total cost driven by input tokens
    cost_per_1k_successes: float   # Cost per 1,000 successful requests at given success_rate
    projected_monthly_10k_daily: float  # Projected cost at 10,000 requests / day (30-day month)
    projected_monthly_100k_daily: float # Projected cost at 100,000 requests / day (30-day month)


def calculate_cost_breakdown(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    success_rate: float = 1.0,
) -> CostBreakdown:
    """
    Computes rigorous unit economics and capacity cost projections.
    
    Parameters:
    -----------
    model: Model identifier.
    prompt_tokens: Input tokens consumed.
    completion_tokens: Generated output tokens.
    success_rate: Observed availability (e.g. 0.99 = 99%).
    """
    card = get_price_card(model)
    prompt_cost = prompt_tokens * card.input_per_token_usd
    completion_cost = completion_tokens * card.output_per_token_usd
    total_cost = prompt_cost + completion_cost

    # Input dominance: what % of dollar cost was input tokens?
    input_ratio = (prompt_cost / total_cost) if total_cost > 0 else 0.0

    # Cost per 1,000 successful requests:
    # Requires (1,000 / success_rate) total attempts to yield 1,000 successes
    safe_rate = max(0.01, min(1.0, success_rate))
    effective_reqs_per_1k = 1000.0 / safe_rate
    cost_per_1k = effective_reqs_per_1k * total_cost

    # Monthly projections (30 days)
    monthly_10k = 10_000 * 30 * total_cost
    monthly_100k = 100_000 * 30 * total_cost

    return CostBreakdown(
        model=card.model_identifier,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=prompt_tokens + completion_tokens,
        prompt_cost_usd=round(prompt_cost, 7),
        completion_cost_usd=round(completion_cost, 7),
        total_cost_usd=round(total_cost, 7),
        input_cost_ratio=round(input_ratio, 4),
        cost_per_1k_successes=round(cost_per_1k, 4),
        projected_monthly_10k_daily=round(monthly_10k, 2),
        projected_monthly_100k_daily=round(monthly_100k, 2),
    )

def format_cost_table(stable_cost: CostBreakdown, trimmed_cost: CostBreakdown | None = None) -> str:
    """Formats markdown comparison table for README and reports."""
    if trimmed_cost:
        model_trimmed = f"`{trimmed_cost.model}`"
        prompt_trimmed = f"{trimmed_cost.prompt_tokens:,}"
        prompt_delta = f"{((trimmed_cost.prompt_tokens - stable_cost.prompt_tokens) / stable_cost.prompt_tokens * 100):+.1f}%"
        comp_trimmed = f"{trimmed_cost.completion_tokens:,}"
        cost_req_trimmed = f"${trimmed_cost.total_cost_usd:.6f}"
        cost_req_delta = f"{((trimmed_cost.total_cost_usd - stable_cost.total_cost_usd) / stable_cost.total_cost_usd * 100):+.1f}%"
        cost_1k_trimmed = f"**${trimmed_cost.cost_per_1k_successes:.4f}**"
        cost_1k_delta = f"**{((trimmed_cost.cost_per_1k_successes - stable_cost.cost_per_1k_successes) / stable_cost.cost_per_1k_successes * 100):+.1f}%**"
        m10k_trimmed = f"${trimmed_cost.projected_monthly_10k_daily:,.2f}"
        m10k_delta = f"{((trimmed_cost.projected_monthly_10k_daily - stable_cost.projected_monthly_10k_daily) / stable_cost.projected_monthly_10k_daily * 100):+.1f}%"
        m100k_trimmed = f"${trimmed_cost.projected_monthly_100k_daily:,.2f}"
        m100k_delta = f"{((trimmed_cost.projected_monthly_100k_daily - stable_cost.projected_monthly_100k_daily) / stable_cost.projected_monthly_100k_daily * 100):+.1f}%"
        input_share_trimmed = f"{trimmed_cost.input_cost_ratio * 100:.1f}%"
    else:
        model_trimmed = f"`{stable_cost.model}`"
        prompt_trimmed = "—"
        prompt_delta = "—"
        comp_trimmed = "—"
        cost_req_trimmed = "—"
        cost_req_delta = "—"
        cost_1k_trimmed = "—"
        cost_1k_delta = "—"
        m10k_trimmed = "—"
        m10k_delta = "—"
        m100k_trimmed = "—"
        m100k_delta = "—"
        input_share_trimmed = "—"

    lines = [
        "| Metric | Stable Baseline | Optimized / Trimmed | Delta |",
        "| :--- | :---: | :---: | :---: |",
        f"| **Model** | `{stable_cost.model}` | {model_trimmed} | — |",
        f"| **Prompt (Input) Tokens** | {stable_cost.prompt_tokens:,} | {prompt_trimmed} | {prompt_delta} |",
        f"| **Completion Tokens** | {stable_cost.completion_tokens:,} | {comp_trimmed} | — |",
        f"| **Cost per Request** | ${stable_cost.total_cost_usd:.6f} | {cost_req_trimmed} | {cost_req_delta} |",
        f"| **Cost per 1,000 Successes** | **${stable_cost.cost_per_1k_successes:.4f}** | {cost_1k_trimmed} | {cost_1k_delta} |",
        f"| **Monthly (10k req/day)** | ${stable_cost.projected_monthly_10k_daily:,.2f} | {m10k_trimmed} | {m10k_delta} |",
        f"| **Monthly (100k req/day)** | ${stable_cost.projected_monthly_100k_daily:,.2f} | {m100k_trimmed} | {m100k_delta} |",
        f"| **Input Cost Share** | {stable_cost.input_cost_ratio * 100:.1f}% | {input_share_trimmed} | Input dominates |",
    ]
    return "\n".join(lines)
