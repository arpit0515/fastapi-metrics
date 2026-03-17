"""LLM API cost tracking for OpenAI and Anthropic."""

from typing import Any


# Pricing per 1M tokens (updated 2025)
OPENAI_PRICING = {
    # GPT-4.5
    "gpt-4.5": {"input": 75.0, "output": 150.0},
    # GPT-4o family
    "gpt-4o-mini": {"input": 0.15, "output": 0.6},
    "gpt-4o": {"input": 2.5, "output": 10.0},
    # GPT-4 family
    "gpt-4-turbo": {"input": 10.0, "output": 30.0},
    "gpt-4": {"input": 30.0, "output": 60.0},
    # GPT-3.5
    "gpt-3.5-turbo": {"input": 0.5, "output": 1.5},
    # o-series reasoning models
    "o3-mini": {"input": 1.1, "output": 4.4},
    "o3": {"input": 10.0, "output": 40.0},
    "o1-mini": {"input": 3.0, "output": 12.0},
    "o1": {"input": 15.0, "output": 60.0},
}

ANTHROPIC_PRICING = {
    # Claude 4.x
    "claude-opus-4": {"input": 15.0, "output": 75.0},
    "claude-sonnet-4": {"input": 3.0, "output": 15.0},
    # Claude 3.x (legacy)
    "claude-3-7-sonnet": {"input": 3.0, "output": 15.0},
    "claude-3-5-sonnet": {"input": 3.0, "output": 15.0},
    "claude-3-5-haiku": {"input": 0.8, "output": 4.0},
    "claude-3-opus": {"input": 15.0, "output": 75.0},
    "claude-3-sonnet": {"input": 3.0, "output": 15.0},
    "claude-3-haiku": {"input": 0.25, "output": 1.25},
}

# Pricing per 1M tokens for Google Gemini
GEMINI_PRICING = {
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
    "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
    "gemini-1.5-pro": {"input": 1.25, "output": 5.0},
    "gemini-1.0-pro": {"input": 0.5, "output": 1.5},
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

    def calculate_gemini_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """Calculate Google Gemini API cost."""
        model_lower = model.lower()
        model_key = model_lower
        sorted_keys = sorted(GEMINI_PRICING.keys(), key=len, reverse=True)
        for key in sorted_keys:
            if key in model_lower:
                model_key = key
                break

        pricing = GEMINI_PRICING.get(model_key)
        if not pricing:
            return 0.0

        return (input_tokens / 1_000_000) * pricing["input"] + (
            output_tokens / 1_000_000
        ) * pricing["output"]

    async def track_gemini_call(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        **labels,
    ):
        """Track Google Gemini API call."""
        cost = self.calculate_gemini_cost(model, input_tokens, output_tokens)

        await self.metrics.track(
            "llm_cost",
            cost,
            provider="gemini",
            model=model,
            **labels,
        )
        await self.metrics.track(
            "llm_tokens_input",
            input_tokens,
            provider="gemini",
            model=model,
            **labels,
        )
        await self.metrics.track(
            "llm_tokens_output",
            output_tokens,
            provider="gemini",
            model=model,
            **labels,
        )
