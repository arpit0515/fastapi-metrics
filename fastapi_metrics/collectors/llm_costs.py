"""LLM API cost tracking for OpenAI and Anthropic."""

from typing import Any


# Pricing per 1M tokens (as of Dec 2024)
OPENAI_PRICING = {
    "gpt-4": {"input": 30.0, "output": 60.0},
    "gpt-4-turbo": {"input": 10.0, "output": 30.0},
    "gpt-4o": {"input": 2.5, "output": 10.0},
    "gpt-4o-mini": {"input": 0.15, "output": 0.6},
    "gpt-3.5-turbo": {"input": 0.5, "output": 1.5},
    "o1": {"input": 15.0, "output": 60.0},
    "o1-mini": {"input": 3.0, "output": 12.0},
}

ANTHROPIC_PRICING = {
    "claude-3-5-sonnet": {"input": 3.0, "output": 15.0},
    "claude-3-5-haiku": {"input": 0.8, "output": 4.0},
    "claude-3-opus": {"input": 15.0, "output": 75.0},
    "claude-3-sonnet": {"input": 3.0, "output": 15.0},
    "claude-3-haiku": {"input": 0.25, "output": 1.25},
}


class LLMCostTracker:
    """Track LLM API costs."""

    def __init__(self, metrics_instance: Any) -> None:
        self.metrics = metrics_instance

    def calculate_openai_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """Calculate OpenAI API cost."""
        # Normalize model name - check longest matches first to avoid partial matches
        model_lower = model.lower()
        model_key = model_lower

        # Sort by length (longest first) to match specific models before generic ones
        sorted_keys = sorted(OPENAI_PRICING.keys(), key=len, reverse=True)
        for key in sorted_keys:
            if key in model_lower:
                model_key = key
                break

        pricing = OPENAI_PRICING.get(model_key)
        if not pricing:
            # Unknown model, return 0
            return 0.0

        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]

        return input_cost + output_cost

    def calculate_anthropic_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """Calculate Anthropic API cost."""
        # Normalize model name - check longest matches first to avoid partial matches
        model_lower = model.lower()
        model_key = model_lower

        # Sort by length (longest first) to match specific models before generic ones
        sorted_keys = sorted(ANTHROPIC_PRICING.keys(), key=len, reverse=True)
        for key in sorted_keys:
            if key in model_lower:
                model_key = key
                break

        pricing = ANTHROPIC_PRICING.get(model_key)
        if not pricing:
            return 0.0

        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]

        return input_cost + output_cost

    async def track_openai_call(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        **labels,
    ):
        """Track OpenAI API call."""
        cost = self.calculate_openai_cost(model, input_tokens, output_tokens)

        await self.metrics.track(
            "llm_cost",
            cost,
            provider="openai",
            model=model,
            **labels,
        )
        await self.metrics.track(
            "llm_tokens_input",
            input_tokens,
            provider="openai",
            model=model,
            **labels,
        )
        await self.metrics.track(
            "llm_tokens_output",
            output_tokens,
            provider="openai",
            model=model,
            **labels,
        )

    async def track_anthropic_call(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        **labels,
    ):
        """Track Anthropic API call."""
        cost = self.calculate_anthropic_cost(model, input_tokens, output_tokens)

        await self.metrics.track(
            "llm_cost",
            cost,
            provider="anthropic",
            model=model,
            **labels,
        )
        await self.metrics.track(
            "llm_tokens_input",
            input_tokens,
            provider="anthropic",
            model=model,
            **labels,
        )
        await self.metrics.track(
            "llm_tokens_output",
            output_tokens,
            provider="anthropic",
            model=model,
            **labels,
        )
