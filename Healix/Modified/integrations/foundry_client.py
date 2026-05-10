# ============================================================
#  HEALIX Azure AI Foundry Client — integrations/foundry_client.py
#  Wraps Azure-hosted OpenAI (AzureChatOpenAI) as the primary LLM.
#  Falls back gracefully when not configured.
# ============================================================

import logging
from datetime import datetime, timezone
from typing import Optional, Dict

logger = logging.getLogger("healix.foundry")


class FoundryClient:
    """Azure AI Foundry LLM wrapper (Foundry-hosted OpenAI models)."""

    def __init__(self, config):
        """
        Args:
            config: AzureFoundryConfig instance from config.py
        """
        self.config = config
        self._available = False
        self._llm = None
        self._embeddings = None
        self._initialize()

    def _initialize(self):
        """Try to build AzureChatOpenAI and AzureOpenAIEmbeddings instances."""
        if not self.config or not self.config.is_configured:
            logger.info("FoundryClient: Not configured. Running without Azure AI Foundry.")
            return

        try:
            from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings

            self._llm = AzureChatOpenAI(
                azure_endpoint=self.config.endpoint,
                api_key=self.config.api_key,
                azure_deployment=self.config.deployment_name,
                openai_api_version=self.config.api_version,
                temperature=0.1,
            )
            self._embeddings = AzureOpenAIEmbeddings(
                azure_endpoint=self.config.endpoint,
                api_key=self.config.api_key,
                azure_deployment=self.config.embedding_deployment,
                openai_api_version=self.config.api_version,
            )
            self._available = True
            logger.info(
                f"FoundryClient: Initialized. Deployment={self.config.deployment_name}, "
                f"Endpoint={self.config.endpoint}"
            )
        except Exception as e:
            logger.error(f"FoundryClient: Initialization failed: {e}")
            self._available = False

    @property
    def is_available(self) -> bool:
        return self._available

    @property
    def llm(self):
        """Return the AzureChatOpenAI instance (or None if not available)."""
        return self._llm

    @property
    def embeddings(self):
        """Return the AzureOpenAIEmbeddings instance (or None if not available)."""
        return self._embeddings

    async def chat(self, message: str, system_prompt: Optional[str] = None) -> Dict:
        """Direct chat call to the Foundry LLM, bypassing RAG.

        Returns a dict with keys: answer, model, provider, timestamp
        """
        if not self._available or not self._llm:
            return self._demo_response(message)

        import asyncio
        from langchain_core.messages import SystemMessage, HumanMessage

        try:
            messages = []
            if system_prompt:
                messages.append(SystemMessage(content=system_prompt))
            messages.append(HumanMessage(content=message))

            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._llm.invoke(messages)
            )
            return {
                "answer": result.content,
                "model": self.config.deployment_name,
                "provider": "azure_foundry",
                "timestamp": _now(),
            }
        except Exception as e:
            logger.error(f"FoundryClient.chat error: {e}")
            return {
                "answer": f"Foundry LLM error: {e}",
                "model": self.config.deployment_name,
                "provider": "azure_foundry",
                "timestamp": _now(),
            }

    def get_model_info(self) -> Dict:
        """Return metadata about the configured Foundry model."""
        return {
            "provider": "azure_foundry",
            "deployment": self.config.deployment_name if self.config else "",
            "endpoint": self.config.endpoint if self.config else "",
            "api_version": self.config.api_version if self.config else "",
            "embedding_deployment": self.config.embedding_deployment if self.config else "",
            "available": self._available,
        }

    def _demo_response(self, message: str) -> Dict:
        return {
            "answer": (
                f"Azure AI Foundry is not configured. "
                f"Set AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, and "
                f"AZURE_OPENAI_DEPLOYMENT_NAME environment variables to enable real AI responses.\n\n"
                f"Your message was: {message}"
            ),
            "model": "demo",
            "provider": "demo",
            "timestamp": _now(),
        }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
