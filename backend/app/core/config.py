"""Application configuration from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Agent Metering & Observability Control Center"
    app_env: str = "development"
    api_prefix: str = "/api/v1"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000"

    database_url: str = "sqlite+aiosqlite:///./data/control_center.db"
    secret_store_path: str = "./data/secrets"

    # Content capture defaults — prompts/responses OFF by default
    content_capture_enabled: bool = False
    pii_redaction_enabled: bool = True
    telemetry_sampling_rate: float = 1.0

    # Auto refresh default (seconds)
    default_auto_refresh_seconds: int = 30

    # Runaway detection defaults
    runaway_steps_warning: int = 8
    runaway_steps_high: int = 13
    runaway_steps_critical: int = 21
    runaway_retry_threshold: int = 5
    runaway_fallback_threshold: int = 3
    runaway_duration_ms_threshold: int = 300_000

    # Latency thresholds (ms)
    latency_warning_ms: int = 2_000
    latency_critical_ms: int = 10_000

    # Telemetry freshness
    telemetry_stale_seconds: int = 120
    telemetry_offline_seconds: int = 600

    # Retention (days)
    telemetry_retention_days: int = 30

    # Auth (dev: simple role header; production: JWT/OIDC)
    auth_enabled: bool = False
    default_role: str = "platform_administrator"

    # Telemetry ingest — auto-enable configured integrations on startup
    telemetry_auto_enable: bool = False
    azure_auto_enable: bool = False
    otel_exporter_otlp_endpoint: str = "http://localhost:4318"
    otel_exporter_otlp_protocol: str = "http/protobuf"
    control_center_ingest_url: str = (
        "http://localhost:8000/api/v1/telemetry/otlp?integration_id=otel"
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
