"""Security headers middleware smoke test (T10.1)."""

from __future__ import annotations

import os

import pytest
from httpx import ASGITransport, AsyncClient

# Ensure SECRET_KEY before importing app
os.environ.setdefault("SECRET_KEY", "test-secret-for-security-headers")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("DATABASE_TYPE", "sqlite")


@pytest.mark.asyncio
async def test_health_has_security_headers() -> None:
    from app.config import clear_settings_cache
    from app.database import reset_engine
    from app.main import app

    clear_settings_cache()
    reset_engine()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"
    assert "strict-origin" in (resp.headers.get("Referrer-Policy") or "")
    assert "max-age=" in (resp.headers.get("Strict-Transport-Security") or "")
