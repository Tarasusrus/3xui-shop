"""
Regression test for 3xui-shop-70.

The 3x-ui panel is self-hosted on a bare IP without a valid TLS certificate.
py3xui 0.6.0 defaults `use_tls_verify=True`, so login failed with
CERTIFICATE_VERIFY_FAILED, the server pool stayed empty and no VPN could be
provisioned. `_add_server` must construct AsyncApi with use_tls_verify=False.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import app.bot.services.server_pool as sp


@pytest.mark.asyncio
async def test_add_server_disables_tls_verify(monkeypatch):
    api_instance = MagicMock()
    api_instance.login = AsyncMock()
    api_ctor = MagicMock(return_value=api_instance)
    monkeypatch.setattr(sp, "AsyncApi", api_ctor)
    monkeypatch.setattr(sp.Server, "update", AsyncMock())

    session_cm = MagicMock()
    session_cm.__aenter__ = AsyncMock(return_value=MagicMock())
    session_cm.__aexit__ = AsyncMock(return_value=False)

    config = SimpleNamespace(
        xui=SimpleNamespace(USERNAME="u", PASSWORD="p", TOKEN=None),
    )
    service = sp.ServerPoolService(config=config, session=MagicMock(return_value=session_cm))

    server = SimpleNamespace(id=1, host="http://172.86.123.156:37521", name="Dallas", online=False)
    await service._add_server(server)

    api_ctor.assert_called_once()
    assert api_ctor.call_args.kwargs["use_tls_verify"] is False
    assert server.id in service._servers  # login succeeded → added to pool


def _service_with_api(monkeypatch, *, login_ok):
    api_instance = MagicMock()
    if login_ok:
        api_instance.login = AsyncMock()
    else:
        api_instance.login = AsyncMock(side_effect=Exception("404 /csrf-token"))
    api_ctor = MagicMock(return_value=api_instance)
    monkeypatch.setattr(sp, "AsyncApi", api_ctor)
    config = SimpleNamespace(xui=SimpleNamespace(USERNAME="u", PASSWORD="p", TOKEN=None))
    return sp.ServerPoolService(config=config, session=MagicMock()), api_ctor


@pytest.mark.asyncio
async def test_probe_connection_true_on_login_success(monkeypatch):
    service, api_ctor = _service_with_api(monkeypatch, login_ok=True)
    ok = await service.probe_connection("https://172.86.123.156:37521/xr4admin")
    assert ok is True
    assert api_ctor.call_args.kwargs["use_tls_verify"] is False


@pytest.mark.asyncio
async def test_probe_connection_false_on_login_failure(monkeypatch):
    """Bare host without base-path → login raises → probe rejects it (3xui-shop-71)."""
    service, _ = _service_with_api(monkeypatch, login_ok=False)
    ok = await service.probe_connection("http://172.86.123.156:37521")
    assert ok is False
