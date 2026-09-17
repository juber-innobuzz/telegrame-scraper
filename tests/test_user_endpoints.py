"""Tests for Telegram User Client & Private Chat endpoints."""

import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_user_me_route_registered():
    """Verify that /user/me route is registered and mounted in docs/app."""
    routes = [route.path for route in app.routes]
    assert "/api/v1/telegram/user/me" in routes or "/user/me" in routes


def test_user_dialogs_route_registered():
    """Verify that /user/dialogs route is registered and mounted."""
    routes = [route.path for route in app.routes]
    assert "/api/v1/telegram/user/dialogs" in routes or "/user/dialogs" in routes


def test_user_messages_route_registered():
    """Verify that /user/chats/{chat_id}/messages route is registered."""
    routes = [route.path for route in app.routes]
    assert any("chats/{chat_id}/messages" in r for r in routes)
