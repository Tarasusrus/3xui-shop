"""Thin async client for the Crypto Pay API (@CryptoBot).

Docs: https://help.crypt.bot/crypto-pay-api

Only the endpoints needed by the poll-based gateway are implemented:
- createInvoice — issue an invoice, returns a `bot_invoice_url` to pay in Telegram.
- getInvoices  — list invoices (used by the background poller to detect paid ones).

No webhook / signature verification: payment status is read from the authorized
getInvoices call (the bot runs in polling mode, there is no public HTTPS endpoint).
Raw HTTP via aiohttp — no third-party SDK, so there is no import/signature drift.
"""

import logging
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)

MAINNET_BASE_URL = "https://pay.crypt.bot/api"
TESTNET_BASE_URL = "https://testnet-pay.crypt.bot/api"

_DEFAULT_TIMEOUT_SEC = 30


class CryptoPayAPIError(Exception):
    """Raised when the Crypto Pay API returns ok=false or an unexpected payload."""


class CryptoPayAPI:
    def __init__(
        self,
        token: str,
        testnet: bool = False,
        timeout_sec: int = _DEFAULT_TIMEOUT_SEC,
    ) -> None:
        self.token = token
        self.base_url = TESTNET_BASE_URL if testnet else MAINNET_BASE_URL
        self.timeout = aiohttp.ClientTimeout(total=timeout_sec)
        self._session: aiohttp.ClientSession | None = None

    @property
    def _headers(self) -> dict[str, str]:
        return {"Crypto-Pay-API-Token": self.token}

    def _get_session(self) -> aiohttp.ClientSession:
        """Lazily create a reusable session bound to the running event loop.

        Reused across polls/requests to avoid a fresh TCP/TLS handshake each time.
        Recreated transparently if it was closed. Must be created inside the loop,
        so it is built on first use rather than in __init__.
        """
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=self.timeout, headers=self._headers
            )
        return self._session

    async def close(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()
            self._session = None

    async def _request(self, method: str, params: dict[str, Any]) -> Any:
        """POST to a Crypto Pay method, returning the `result` field.

        Raises CryptoPayAPIError on ok=false or malformed responses. Network/HTTP
        errors propagate as aiohttp exceptions — callers decide how to handle them.
        """
        url = f"{self.base_url}/{method}"
        session = self._get_session()
        async with session.post(url, json=params) as resp:
            payload = await resp.json()

        if not isinstance(payload, dict) or not payload.get("ok"):
            error = payload.get("error") if isinstance(payload, dict) else payload
            raise CryptoPayAPIError(f"Crypto Pay {method} failed: {error}")

        return payload.get("result")

    async def create_invoice(
        self,
        amount: float | int | str,
        fiat: str,
        payload: str,
        description: str | None = None,
        expires_in: int | None = None,
    ) -> dict[str, Any]:
        """Create a fiat-priced invoice.

        Returns {"invoice_id": int, "bot_invoice_url": str, "status": str}.
        Raises CryptoPayAPIError / aiohttp errors on failure.
        """
        params: dict[str, Any] = {
            "currency_type": "fiat",
            "fiat": fiat,
            "amount": str(amount),
            "payload": payload,
        }
        if description is not None:
            params["description"] = description
        if expires_in is not None:
            params["expires_in"] = expires_in

        result = await self._request("createInvoice", params)
        return {
            "invoice_id": result["invoice_id"],
            "bot_invoice_url": result["bot_invoice_url"],
            "status": result["status"],
        }

    async def get_invoices(
        self,
        status: str | None = None,
        invoice_ids: list[int] | list[str] | None = None,
        offset: int = 0,
        count: int = 100,
    ) -> list[dict[str, Any]]:
        """List invoices. Returns [] on any network/API error (poller resilience).

        status: 'active' | 'paid' | 'expired' (omit for all).
        invoice_ids: restrict to these invoice ids.
        """
        params: dict[str, Any] = {"offset": offset, "count": count}
        if status is not None:
            params["status"] = status
        if invoice_ids:
            params["invoice_ids"] = ",".join(str(i) for i in invoice_ids)

        try:
            result = await self._request("getInvoices", params)
        except (aiohttp.ClientError, CryptoPayAPIError, TimeoutError) as exception:
            logger.error(f"Crypto Pay getInvoices failed: {exception}")
            return []

        if isinstance(result, dict):
            return result.get("items", [])
        if isinstance(result, list):
            return result
        return []
