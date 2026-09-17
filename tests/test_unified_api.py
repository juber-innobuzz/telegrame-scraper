"""Unit and integration tests for the v2 Unified Sliced Scraper API."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.models import ChannelInfo, EngagementMetrics, MediaItem, MessageItem
from main import app

client = TestClient(app)

MOCK_HTML_CHANNEL = """
<!DOCTYPE html>
<html>
<head>
  <meta property="og:title" content="Tech Innovations">
  <meta property="og:description" content="Official channel for software & AI deals. Contact: support@techinnovations.io or +1 (555) 234-5678. Admin: @techadmin">
  <meta property="og:image" content="https://telegram.org/img/avatar.jpg">
</head>
<body>
  <div class="tgme_page_title">Tech Innovations</div>
  <div class="tgme_page_extra">150.5K subscribers</div>
  <div class="tgme_page_description">Official channel for software & AI deals. Contact: support@techinnovations.io or +1 (555) 234-5678. Admin: @techadmin</div>

  <div class="tgme_widget_message" data-post="tech_innovations/101" id="widget_101">
    <div class="tgme_widget_message_text">
      🚀 New Cloud Bot Service Launched! Deal Price: $49 MRP: $199. Apply 20% coupon on checkout.<br/>
      Order here: https://techinnovations.io/buy or chat on WhatsApp: https://wa.me/15552345678<br/>
      #cloud #ai @techadmin
    </div>
    <span class="tgme_widget_message_views">12.5K</span>
  </div>

  <div class="tgme_widget_message" data-post="tech_innovations/102" id="widget_102">
    <div class="tgme_widget_message_forwarded_from_name">Durov Channel</div>
    <div class="tgme_widget_message_text">
      Hiring: Senior Python Developer (Remote). Salary: $120,000 / year in San Francisco.<br/>
      Send CV to jobs@techinnovations.io #hiring #job
    </div>
    <span class="tgme_widget_message_views">8.2K</span>
  </div>
</body>
</html>
"""


@pytest.fixture(autouse=True)
def mock_telegram_http(monkeypatch):
    """Mock the HTTP fetcher for fast, deterministic unit testing."""
    async def mock_fetch_html(url, *args, **kwargs):
        return MOCK_HTML_CHANNEL

    from app.core.http_client import telegram_http_client
    monkeypatch.setattr(telegram_http_client, "fetch_html", mock_fetch_html)


def test_channel_all_slices():
    """Verify requesting ['all'] returns every supported slice."""
    response = client.post("/telegram/channel", json={
        "username": "tech_innovations",
        "include": ["all"],
        "limit": 10,
    })
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["username"] == "tech_innovations"
    assert data["info"]["title"] == "Tech Innovations"
    assert len(data["messages"]) == 2
    assert "leads" in data
    assert len(data["leads"]["emails"]) >= 1
    assert "products" in data
    assert "jobs" in data
    assert "engagement" in data


def test_channel_selective_slices():
    """Verify that only the requested slices are populated."""
    response = client.post("/telegram/channel", json={
        "username": "tech_innovations",
        "include": ["info", "leads", "websites"],
        "limit": 10,
    })
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["info"] is not None
    assert data["leads"] is not None
    assert data["websites"] is not None
    assert data["messages"] is None
    assert data["jobs"] is None
    assert data["products"] is None


def test_channel_query_filter():
    """Verify filtering messages by query."""
    response = client.post("/telegram/channel", json={
        "username": "tech_innovations",
        "include": ["messages", "jobs"],
        "query": "Hiring",
        "limit": 10,
    })
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert len(data["messages"]) == 1
    assert "Hiring" in data["messages"][0]["text"]


def test_post_scrape_by_url():
    """Verify scraping a single post by URL."""
    response = client.post("/telegram/post", json={
        "url": "https://t.me/tech_innovations/101",
        "include": ["messages", "prices", "leads", "links"],
    })
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["username"] == "tech_innovations"
    assert data["message_id"] == 101
    assert len(data["messages"]) == 1
    assert len(data["links"]) >= 1
    assert len(data["leads"]["whatsapp"]) >= 1


def test_post_scrape_by_fields():
    """Verify scraping a single post by username + message_id."""
    response = client.post("/telegram/post", json={
        "username": "tech_innovations",
        "message_id": 102,
        "include": ["messages", "jobs", "locations"],
    })
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["message_id"] == 102
    assert len(data["jobs"]) == 1
    assert "developer" in data["jobs"][0]["roles"]


def test_batch_scrape():
    """Verify scraping multiple channels with delay and watermark support."""
    response = client.post("/telegram/batch", json={
        "usernames": ["tech_innovations", "durov"],
        "include": ["info", "leads", "websites"],
        "limit_per_channel": 5,
        "delay_sec": 0.0,
    })
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["total_channels"] == 2
    assert data["successful"] == 2
    assert len(data["results"]) == 2
    assert data["results"][0]["username"] == "tech_innovations"


def test_search_endpoint():
    """Verify searching for channels and groups."""
    response = client.post("/telegram/search", json={
        "query": "crypto",
        "type": "all",
        "limit": 5,
    })
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["query"] == "crypto"
    assert data["total_results"] > 0
    assert data["channels"] is not None
    assert data["groups"] is not None


def test_channel_flat_format():
    """Verify format='flat' returns exact data.json style rowType array."""
    response = client.post("/telegram/channel", json={
        "username": "tech_innovations",
        "format": "flat",
        "limit": 10,
    })
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 2
    # Check channel row
    channel_row = data[0]
    assert channel_row["rowType"] == "channel"
    assert channel_row["channel"] == "tech_innovations"
    assert channel_row["channelTitle"] == "Tech Innovations"
    assert "subscribers" in channel_row

    # Check post row
    post_row = data[1]
    assert post_row["rowType"] == "post"
    assert "messageId" in post_row
    assert "postUrl" in post_row
    assert "views" in post_row
    assert "author" in post_row
    assert "hasMedia" in post_row


def test_channel_posts_cursor_pagination():
    """Verify GET /api/channel/{username}/posts cursor endpoint."""
    response = client.get("/api/channel/tech_innovations/posts?limit=5")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["username"] == "tech_innovations"
    assert "has_more" in data
    assert len(data["messages"]) == 2
    assert "id" in data["messages"][0]


def test_channel_validate_endpoint():
    """Verify POST /api/channel/validate endpoint."""
    response = client.post("/api/channel/validate", json={
        "username": "tech_innovations"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["is_valid"] is True
    assert data["exists"] is True
    assert data["is_public"] is True
    assert data["channel_status"] == "public"
    assert data["title"] == "Tech Innovations"


def test_health_detailed_endpoint():
    """Verify GET /api/health/detailed telemetry endpoint."""
    response = client.get("/api/health/detailed")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "uptime_seconds" in data
    assert "memory" in data
    assert "system" in data
    assert "http_pool" in data

