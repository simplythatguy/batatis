"""Prices the benchmark ledger uses, with where each number came from.

USD per 1M tokens. OpenAI prices are the Standard tier (no priority tier, no batch): the model was run with no
``service_tier`` set. Reasoning tokens are billed as output tokens and arrive inside ``completion_tokens``.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class Price:
    input: Decimal
    output: Decimal
    cached_input: Decimal | None = None
    source: str = ''


PRICES: dict[str, Price] = {
    # developers.openai.com/api/docs/pricing, read 2026-10-21 and again by this run: gpt-6-luna Standard, short context
    # (up to 272K input tokens) $0.10 in, $0.01 cached in, $0.50 out; above 272K input tokens $0.20 / $0.02 / $0.75.
    # Every benchmark prompt is under 60K tokens, so the short-context pair applies. The reservation (worst case)
    # uses the long-context pair so the hard stop can never be crossed by a pricing-tier mistake.
    'gpt-6-luna': Price(Decimal('0.10'), Decimal('0.50'), Decimal('0.01'),
                        'developers.openai.com/api/docs/pricing (Standard tier, <=272K input), read 2026-10-21'),
    # Jev: $0.042 per million input tokens measured in docs/research/2026-10-20-vision/jev-benchmark/README.md;
    # Jev answers are a few tokens each, so output is priced the same. The user set no Jev spend limit.
    'jev-1.13.0': Price(Decimal('0.042'), Decimal('0.042'), None, 'jev-benchmark README (2026-10-20)'),
    'jev-1.14.0': Price(Decimal('0.042'), Decimal('0.042'), None, 'assumed equal to jev-1.13.0'),
}
# Worst-case pair used only when reserving budget before a call.
WORST_CASE: dict[str, Price] = {
    'gpt-6-luna': Price(Decimal('0.20'), Decimal('0.75'), None, 'long-context tier, over-estimate for every call'),
}
USD_CAD = Decimal('1.4097')           # Bank of Canada FXUSDCAD used by PR #43 (2026-10-19); only for display


def price_for(model: str) -> Price:
    if model not in PRICES:
        raise KeyError(f'no verified price for {model!r}; add it to pricing.PRICES with its source before calling it')
    return PRICES[model]


def cost_usd(model: str, input_tokens: int, output_tokens: int, cached_tokens: int = 0, *,
             cached_discount: bool = False) -> Decimal:
    """Cost of one call from the provider's reported usage.

    Cached input tokens are billed at the full input price unless ``cached_discount`` is set. The benchmark leaves
    it off: a production request is a new prompt, so crediting the discount that repeats of the same prompt happen
    to get would understate the cost per case.
    """
    p = price_for(model)
    uncached = input_tokens
    total = Decimal(0)
    if cached_discount and p.cached_input is not None and cached_tokens:
        uncached = max(0, input_tokens - cached_tokens)
        total += Decimal(cached_tokens) * p.cached_input
    total += Decimal(uncached) * p.input + Decimal(output_tokens) * p.output
    return total / Decimal(1_000_000)


def worst_case_usd(model: str, max_input_tokens: int, max_output_tokens: int) -> Decimal:
    p = WORST_CASE.get(model) or price_for(model)
    return (Decimal(max_input_tokens) * p.input + Decimal(max_output_tokens) * p.output) / Decimal(1_000_000)


def input_token_upper_bound(text: str) -> int:
    """A bound for the reservation, not an estimate: one token per two UTF-8 bytes, which every real tokenizer beats
    on English and code text (about four characters per token)."""
    return (len(text.encode('utf-8')) + 1) // 2


def input_token_estimate(text: str) -> int:
    """A typical count (about four characters per token), for the expected-spend check, never for the stop."""
    return max(1, len(text) // 4)
