"""Tests for Asynchronous Task Queue and Multi-Account Session Pool."""

import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_jobs_routes_registered():
    """Verify all job queue and pool routes are mounted."""
    routes = [route.path for route in app.routes]
    assert any("/jobs/scrape-chat" in r for r in routes)
    assert any("/jobs/scrape-batch" in r for r in routes)
    assert any("/jobs/{job_id}" in r for r in routes)
    assert any("/pool/status" in r for r in routes)
    assert any("/pool/add-session" in r for r in routes)


def test_pool_status_endpoint():
    """Verify /pool/status returns expected schema."""
    response = client.get("/api/v1/telegram/pool/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "total_accounts" in data
    assert "available_accounts" in data
    assert isinstance(data["accounts"], list)


def test_list_jobs_endpoint():
    """Verify /jobs listing endpoint works."""
    response = client.get("/api/v1/telegram/jobs")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_job_not_found_404():
    """Verify requesting a non-existent job ID returns 404."""
    response = client.get("/api/v1/telegram/jobs/non-existent-uuid-12345")
    assert response.status_code == 404
