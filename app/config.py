"""Application configuration with secret-safe validation."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment / .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "SLM + Frontier Device Monitoring Patterns"
    demo_mode: bool = True
    log_level: str = "INFO"

    # SLM
    slm_provider: Literal["ollama", "demo"] = "ollama"
    slm_model: str = "llama3.2"
    slm_base_url: str = "http://localhost:11434"
    slm_timeout_seconds: float = 60.0

    # Frontier
    frontier_provider: Literal["azure_openai", "demo"] = "azure_openai"
    frontier_model: str = "gpt-4o"
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_api_version: str = "2024-08-01-preview"
    azure_openai_deployment: str = ""

    # LangSmith
    langsmith_enabled: bool = False
    langsmith_tracing: bool = False
    langsmith_api_key: str = ""
    langsmith_project: str = "slm-frontier-device-monitoring"
    langsmith_endpoint: str = "https://api.smith.langchain.com"

    # Illustrative pricing (USD per 1K tokens) — NOT factual market prices
    illustrative_slm_input_cost_per_1k: float = 0.0001
    illustrative_slm_output_cost_per_1k: float = 0.0002
    illustrative_frontier_input_cost_per_1k: float = 0.005
    illustrative_frontier_output_cost_per_1k: float = 0.015

    confidence_threshold: float = Field(default=0.85, ge=0.0, le=1.0)

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_base_url: str = "http://localhost:8000"

    @field_validator("azure_openai_api_key", "langsmith_api_key", mode="before")
    @classmethod
    def strip_secrets(cls, value: object) -> str:
        if value is None:
            return ""
        return str(value).strip()

    @property
    def pricing_disclaimer(self) -> str:
        return "Illustrative pricing — configure using current provider pricing."

    def effective_demo_mode(self) -> bool:
        """Force demo mode when live providers are not configured."""
        if self.demo_mode:
            return True
        frontier_ready = bool(
            self.azure_openai_endpoint
            and self.azure_openai_api_key
            and self.azure_openai_deployment
        )
        return not frontier_ready

    def langsmith_active(self) -> bool:
        return bool(
            self.langsmith_enabled
            and self.langsmith_tracing
            and self.langsmith_api_key
        )

    def public_status(self) -> dict:
        """Safe configuration status without secrets."""
        return {
            "app_name": self.app_name,
            "demo_mode": self.effective_demo_mode(),
            "slm_provider": "demo" if self.effective_demo_mode() else self.slm_provider,
            "slm_model": self.slm_model,
            "frontier_provider": (
                "demo" if self.effective_demo_mode() else self.frontier_provider
            ),
            "frontier_model": self.frontier_model,
            "langsmith_enabled": self.langsmith_enabled,
            "langsmith_active": self.langsmith_active(),
            "langsmith_project": self.langsmith_project,
            "confidence_threshold": self.confidence_threshold,
            "pricing_disclaimer": self.pricing_disclaimer,
            "azure_configured": bool(
                self.azure_openai_endpoint and self.azure_openai_deployment
            ),
            "secrets_present": {
                "azure_api_key": bool(self.azure_openai_api_key),
                "langsmith_api_key": bool(self.langsmith_api_key),
            },
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
