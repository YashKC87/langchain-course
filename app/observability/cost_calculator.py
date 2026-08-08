"""Illustrative cost calculator — not factual provider pricing."""

from __future__ import annotations

from app.config import Settings, get_settings
from app.models.model_interface import ModelType


class CostCalculator:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    @property
    def disclaimer(self) -> str:
        return self.settings.pricing_disclaimer

    def estimate(
        self,
        *,
        model_type: ModelType,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        if model_type == ModelType.FRONTIER:
            in_rate = self.settings.illustrative_frontier_input_cost_per_1k
            out_rate = self.settings.illustrative_frontier_output_cost_per_1k
        elif model_type == ModelType.SLM:
            in_rate = self.settings.illustrative_slm_input_cost_per_1k
            out_rate = self.settings.illustrative_slm_output_cost_per_1k
        else:
            return 0.0
        cost = (input_tokens / 1000.0) * in_rate + (output_tokens / 1000.0) * out_rate
        return round(cost, 6)

    def estimate_total_tokens(self, model_type: ModelType, total_tokens: int) -> float:
        # Split roughly 65/35 input/output when only totals are known
        input_tokens = int(total_tokens * 0.65)
        output_tokens = total_tokens - input_tokens
        return self.estimate(
            model_type=model_type,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
