# ============================================================
#  HEALIX Configuration — config.py
#  Centralized configuration with Pydantic validation.
#  Reads from .env file and provides typed config objects.
# ============================================================

import os
from typing import List, Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()


class AzureConfig(BaseModel):
    """Azure AD / Entra ID app registration credentials."""
    tenant_id: str = ""
    client_id: str = ""
    client_secret: str = ""

    @property
    def is_configured(self) -> bool:
        return bool(self.tenant_id and self.client_id and self.client_secret)


class SentinelConfig(BaseModel):
    """Microsoft Sentinel / Log Analytics workspace settings."""
    workspace_id: str = ""
    resource_group: str = ""
    subscription_id: str = ""

    @property
    def is_configured(self) -> bool:
        return bool(self.workspace_id and self.subscription_id)


class AzureFoundryConfig(BaseModel):
    """Azure AI Foundry (Azure-hosted OpenAI) settings."""
    endpoint: str = ""
    api_key: str = ""
    deployment_name: str = ""
    embedding_deployment: str = "text-embedding-3-small"
    api_version: str = "2024-02-01"

    @property
    def is_configured(self) -> bool:
        return bool(self.endpoint and self.api_key and self.deployment_name)


class OllamaConfig(BaseModel):
    """On-prem LLM served via Ollama (OpenAI-compatible API).

    Used for fully local/air-gapped inference, e.g. Gemma 3.
    Ollama exposes an OpenAI-compatible endpoint at {base_url}/v1.
    """
    base_url: str = "http://localhost:11434"
    model: str = "gemma3"
    embed_model: str = "nomic-embed-text"
    enabled: bool = False

    @property
    def is_configured(self) -> bool:
        return bool(self.enabled and self.base_url and self.model)


class AWSConfig(BaseModel):
    """AWS credentials for EC2/CloudWatch agentless polling."""
    access_key_id: str = ""
    secret_access_key: str = ""
    region: str = "us-east-1"

    @property
    def is_configured(self) -> bool:
        return bool(self.access_key_id and self.secret_access_key)


class IntegrationAPIConfig(BaseModel):
    """External integration API settings (versioned /api/v1/* endpoints)."""
    api_key: str = ""
    rate_limit_per_minute: int = 100


class AlertDeliveryConfig(BaseModel):
    """Alert notification channel settings."""
    teams_webhook_url: str = ""
    smtp_host: str = "smtp.office365.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    alert_email_recipients: List[str] = Field(default_factory=list)

    @property
    def teams_configured(self) -> bool:
        return bool(self.teams_webhook_url)

    @property
    def email_configured(self) -> bool:
        return bool(self.smtp_user and self.smtp_password and self.alert_email_recipients)


class HealixConfig(BaseModel):
    """Root configuration for the HEALIX platform."""
    openai_api_key: str = ""
    azure: AzureConfig = Field(default_factory=AzureConfig)
    sentinel: SentinelConfig = Field(default_factory=SentinelConfig)
    foundry: AzureFoundryConfig = Field(default_factory=AzureFoundryConfig)
    ollama: OllamaConfig = Field(default_factory=OllamaConfig)
    aws: AWSConfig = Field(default_factory=AWSConfig)
    integration_api: IntegrationAPIConfig = Field(default_factory=IntegrationAPIConfig)
    alert_delivery: AlertDeliveryConfig = Field(default_factory=AlertDeliveryConfig)
    db_path: str = "./healix.db"
    log_level: str = "INFO"
    polling_interval: int = 60
    demo_mode: str = "auto"  # "auto", "always", "never"

    @property
    def is_demo_mode(self) -> bool:
        if self.demo_mode == "always":
            return True
        if self.demo_mode == "never":
            return False
        # auto: demo if no Azure credentials
        return not self.azure.is_configured


def load_config() -> HealixConfig:
    """Load configuration from environment variables."""
    # Parse email recipients from comma-separated string
    recipients_str = os.getenv("ALERT_EMAIL_RECIPIENTS", "")
    recipients = [r.strip() for r in recipients_str.split(",") if r.strip()]

    return HealixConfig(
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        azure=AzureConfig(
            tenant_id=os.getenv("AZURE_TENANT_ID", ""),
            client_id=os.getenv("AZURE_CLIENT_ID", ""),
            client_secret=os.getenv("AZURE_CLIENT_SECRET", ""),
        ),
        sentinel=SentinelConfig(
            workspace_id=os.getenv("SENTINEL_WORKSPACE_ID", ""),
            resource_group=os.getenv("SENTINEL_RESOURCE_GROUP", ""),
            subscription_id=os.getenv("SENTINEL_SUBSCRIPTION_ID", ""),
        ),
        foundry=AzureFoundryConfig(
            endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", ""),
            api_key=os.getenv("AZURE_OPENAI_API_KEY", ""),
            deployment_name=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", ""),
            embedding_deployment=os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-small"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01"),
        ),
        ollama=OllamaConfig(
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            model=os.getenv("OLLAMA_MODEL", "gemma3"),
            embed_model=os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text"),
            enabled=os.getenv("LLM_PROVIDER", "").lower() == "ollama",
        ),
        aws=AWSConfig(
            access_key_id=os.getenv("AWS_ACCESS_KEY_ID", ""),
            secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY", ""),
            region=os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
        ),
        integration_api=IntegrationAPIConfig(
            api_key=os.getenv("HEALIX_API_KEY", ""),
            rate_limit_per_minute=int(os.getenv("HEALIX_API_RATE_LIMIT", "100")),
        ),
        alert_delivery=AlertDeliveryConfig(
            teams_webhook_url=os.getenv("TEAMS_WEBHOOK_URL", ""),
            smtp_host=os.getenv("SMTP_HOST", "smtp.office365.com"),
            smtp_port=int(os.getenv("SMTP_PORT", "587")),
            smtp_user=os.getenv("SMTP_USER", ""),
            smtp_password=os.getenv("SMTP_PASSWORD", ""),
            alert_email_recipients=recipients,
        ),
        db_path=os.getenv("HEALIX_DB_PATH", "./healix.db"),
        log_level=os.getenv("HEALIX_LOG_LEVEL", "INFO"),
        polling_interval=int(os.getenv("HEALIX_POLLING_INTERVAL_SECONDS", "60")),
        demo_mode=os.getenv("HEALIX_DEMO_MODE", "auto"),
    )
