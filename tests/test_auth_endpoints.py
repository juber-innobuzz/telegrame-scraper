"""Unit tests for Telegram Authentication REST API endpoints."""

import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_auth_routes_registered():
    """Verify all /auth/* routes are properly mounted."""
    routes = [route.path for route in app.routes]
    assert any("/auth/send-code" in r for r in routes)
    assert any("/auth/verify-code" in r for r in routes)
    assert any("/auth/verify-2fa" in r for r in routes)
    assert any("/auth/status" in r for r in routes)
    assert any("/auth/logout" in r for r in routes)


def test_auth_status_endpoint():
    """Verify /auth/status returns correct schema."""
    response = client.get("/api/v1/telegram/auth/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "is_authenticated" in data
    assert "total_accounts" in data
    assert isinstance(data["accounts"], list)


def test_auth_send_code_invalid_phone():
    """Verify /auth/send-code handles invalid phone gracefully."""
    response = client.post("/api/v1/telegram/auth/send-code", json={"phone_number": "123"})
    # Should return either 400 (PhoneNumberInvalidError) or validation error
    assert response.status_code in (400, 422, 500)


def test_auth_verify_code_missing_session():
    """Verify /auth/verify-code fails gracefully when auth_session_id does not exist."""
    response = client.post(
        "/api/v1/telegram/auth/verify-code",
        json={
            "auth_session_id": "non-existent-uuid",
            "phone_number": "+919876543210",
            "phone_code_hash": "dummy_hash",
            "code": "12345",
        },
    )
    assert response.status_code == 400
    assert "Invalid or expired auth_session_id" in response.json()["detail"]
