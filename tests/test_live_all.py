"""Live Integration Test Suite for the v2 Telegram Scraper API."""

from __future__ import annotations

import os
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_live_channel_scrape():
    """Test live scraping of @durov with selective data slices."""
    res = client.post("/telegram/channel", json={
        "username": "durov",
        "include": ["info", "messages", "engagement", "leads", "websites", "social_links"],
        "limit": 10,
    })
    assert res.status_code == 200, f"Failed /telegram/channel: {res.status_code} {res.text}"
    data = res.json()
    assert data["status"] == "success"
    assert data["username"] == "durov"
    assert data["info"]["title"] == "Pavel Durov"
    assert len(data["messages"]) > 0
    assert data["engagement"]["total_views"] > 0
    print(f"  [OK] /telegram/channel (@durov): {data['info']['title']} ({data['info']['subscribers_str']}) - {len(data['messages'])} posts")


def test_live_single_post_scrape():
    """Test live single post scraping by URL."""
    res = client.post("/telegram/post", json={
        "url": "https://t.me/durov/1",
        "include": ["messages", "links", "hashtags"],
    })
    assert res.status_code == 200, f"Failed /telegram/post: {res.status_code} {res.text}"
    data = res.json()
    assert data["status"] == "success"
    assert data["username"] == "durov"
    assert data["message_id"] == 1
    assert len(data["messages"]) == 1
    print(f"  [OK] /telegram/post (https://t.me/durov/1): Message #{data['message_id']}")


def test_live_deals_channel_products():
    """Test live product extraction on @deals."""
    res = client.post("/telegram/channel", json={
        "username": "deals",
        "include": ["products", "prices"],
        "limit": 10,
    })
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "products" in data
    print(f"  [OK] /telegram/channel (@deals): Extracted {len(data.get('products', []))} products")


def test_live_batch_channels():
    """Test live batch scraping on multiple channels."""
    res = client.post("/telegram/batch", json={
        "usernames": ["durov", "telegram"],
        "include": ["info", "engagement"],
        "limit_per_channel": 5,
        "delay_sec": 1.0,
    })
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["total_channels"] == 2
    assert data["successful"] == 2
    print(f"  [OK] /telegram/batch: Successfully scraped {data['successful']}/{data['total_channels']} channels")
