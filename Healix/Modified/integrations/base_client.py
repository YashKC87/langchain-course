# ============================================================
#  HEALIX Microsoft Base Client — integrations/base_client.py
#  Abstract base class for all Microsoft API integrations.
#  Handles MSAL auth, token caching, retry, and demo fallback.
# ============================================================

import logging
import time
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime, timezone

import httpx
from msal import ConfidentialClientApplication

logger = logging.getLogger("healix.integrations")


class MicrosoftBaseClient:
    """Base class for Microsoft Graph and Azure API clients."""

    GRAPH_BASE = "https://graph.microsoft.com/v1.0"
    SCOPE = "https://graph.microsoft.com/.default"

    def __init__(self, tenant_id: str, client_id: str, client_secret: str):
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self._msal_app: Optional[ConfidentialClientApplication] = None
        self._token_cache: Dict[str, Any] = {}
        self._available = False
        self._http_client: Optional[httpx.AsyncClient] = None

    async def initialize(self) -> bool:
        """Attempt to authenticate with Azure AD. Returns False if credentials missing."""
        if not (self.tenant_id and self.client_id and self.client_secret):
            logger.warning(f"{self.__class__.__name__}: No Azure credentials configured. Demo mode.")
            return False

        try:
            self._msal_app = ConfidentialClientApplication(
                client_id=self.client_id,
                client_credential=self.client_secret,
                authority=f"https://login.microsoftonline.com/{self.tenant_id}",
            )
            # Test token acquisition
            token = self._acquire_token(self.SCOPE)
            if token:
                self._available = True
                self._http_client = httpx.AsyncClient(timeout=30.0)
                logger.info(f"{self.__class__.__name__}: Authenticated successfully.")
                return True
            else:
                logger.error(f"{self.__class__.__name__}: Token acquisition failed.")
                return False
        except Exception as e:
            logger.error(f"{self.__class__.__name__}: Init failed: {e}")
            return False

    @property
    def is_available(self) -> bool:
        return self._available

    def _acquire_token(self, scope: Optional[str] = None) -> Optional[str]:
        """Acquire token from MSAL with caching."""
        if not self._msal_app:
            return None

        target_scope = scope or self.SCOPE
        scopes = [target_scope] if isinstance(target_scope, str) else target_scope

        # Check cache
        cache_key = "|".join(scopes)
        cached = self._token_cache.get(cache_key)
        if cached and cached["expires_at"] > time.time() + 60:
            return cached["access_token"]

        # Try silent acquisition first
        result = self._msal_app.acquire_token_silent(scopes, account=None)
        if not result:
            result = self._msal_app.acquire_token_for_client(scopes=scopes)

        if result and "access_token" in result:
            self._token_cache[cache_key] = {
                "access_token": result["access_token"],
                "expires_at": time.time() + result.get("expires_in", 3600),
            }
            return result["access_token"]

        error = result.get("error_description", "Unknown error") if result else "No result"
        logger.error(f"Token acquisition failed: {error}")
        return None

    async def _request(self, method: str, url: str, scope: Optional[str] = None,
                       json_body: Optional[dict] = None, params: Optional[dict] = None,
                       max_retries: int = 3) -> Optional[Dict]:
        """HTTP request with auth header, retry with exponential backoff."""
        if not self._available or not self._http_client:
            return None

        token = self._acquire_token(scope)
        if not token:
            return None

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        for attempt in range(max_retries):
            try:
                response = await self._http_client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=json_body,
                    params=params,
                )

                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 204:
                    return {"status": "success"}
                elif response.status_code == 429:
                    # Rate limited — back off
                    retry_after = int(response.headers.get("Retry-After", 2 ** attempt))
                    logger.warning(f"Rate limited. Retrying after {retry_after}s")
                    await asyncio.sleep(retry_after)
                    continue
                elif response.status_code in (502, 503, 504):
                    # Transient server error — retry
                    await asyncio.sleep(2 ** attempt)
                    continue
                else:
                    logger.error(f"API error {response.status_code}: {response.text[:500]}")
                    return None

            except httpx.TimeoutException:
                logger.warning(f"Timeout on attempt {attempt + 1}/{max_retries}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                continue
            except Exception as e:
                logger.error(f"Request failed: {e}")
                return None

        return None

    async def _get(self, path: str, params: Optional[dict] = None,
                   base_url: Optional[str] = None) -> Optional[Dict]:
        url = f"{base_url or self.GRAPH_BASE}{path}"
        return await self._request("GET", url, params=params)

    async def _post(self, path: str, json_body: Optional[dict] = None,
                    base_url: Optional[str] = None) -> Optional[Dict]:
        url = f"{base_url or self.GRAPH_BASE}{path}"
        return await self._request("POST", url, json_body=json_body)

    async def _patch(self, path: str, json_body: Optional[dict] = None,
                     base_url: Optional[str] = None) -> Optional[Dict]:
        url = f"{base_url or self.GRAPH_BASE}{path}"
        return await self._request("PATCH", url, json_body=json_body)

    async def close(self):
        if self._http_client:
            await self._http_client.aclose()

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()
