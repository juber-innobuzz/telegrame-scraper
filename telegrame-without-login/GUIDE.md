# 🌐 Telegram Public Scraper API (Without Login) — Complete Guide

Stateless, high-performance Telegram Public Scraper running on **Port 8000**.
- **Zero Login Required**: Uses fast HTTPX + BeautifulSoup parser.
- **Zero Ban Risk**: Does not use Telegram user accounts or API keys.
- **Port**: `8000`
- **Swagger Docs**: `http://localhost:8000/docs`
- **Base API Path**: `http://localhost:8000/api/v1/telegram`

---

## 📑 Table of Contents
1. [Quick Start (Docker)](#-quick-start-docker)
2. [API Endpoints](#-api-endpoints)
   - [POST /telegram/channel (Single Channel Scrape)](#1-single-channel-scrape-post-telegramchannel)
   - [GET /telegram/channel/{username}/posts (Cursor Pagination)](#2-cursor-based-message-pagination-get-telegramchannelusernameposts)
   - [POST /telegram/channel/validate (Channel Validation)](#3-channel-validation-post-telegramchannelvalidate)
   - [POST /telegram/post (Single Post Scrape)](#4-single-post-scraper-post-telegrampost)
   - [POST /telegram/search (Channel & Group Search)](#5-channel--group-search-post-telegramsearch)
   - [POST /telegram/batch (Multi-Channel Batch Scrape)](#6-multi-channel-batch-scrape-post-telegrambatch)
   - [GET /telegram/health (Health & Telemetry)](#7-health--system-telemetry-get-telegramhealth)
3. [Data Slices & Formatting Options](#-data-slices--formatting-options)
4. [🔄 Pagination Guide (How to Load More Messages)](#-pagination-guide-how-to-load-more-messages)
   - [Method A: Auto-Pagination Crawler](#method-a-auto-pagination-crawler-simplest)
   - [Method B: Cursor Loop in Python & JavaScript](#method-b-cursor-based-pagination-loop-infinite-scroll)

---

## 🐳 Quick Start (Docker)

```bash
# Build and run the container
docker compose up -d --build

# View logs
docker compose logs -f
```

---

## 🚀 API Endpoints

### 1. Single Channel Scrape (`POST /telegram/channel`)
**Purpose**: Scrapes channel info, posts, direct media CDN links, engagement metrics, leads, and keywords.

- **URL**: `http://localhost:8000/api/v1/telegram/channel`
- **Method**: `POST`
- **Headers**: `Content-Type: application/json`

#### Request Payload:
```json
{
  "username": "cryptodollar123",
  "limit": 50,
  "include": ["all"],
  "format": "sliced",
  "date_from": "2026-01-01",
  "date_to": "2026-12-31",
  "query": "crypto"
}
```

| Field | Type | Required? | Default | Description |
| :--- | :---: | :---: | :---: | :--- |
| `username` | `string` | **Yes** | — | Channel handle (e.g. `durov`, `@telegram`, or `https://t.me/durov`) |
| `limit` | `integer` | No | `50` | Number of posts to scrape (1 to 2000). Automatically paginates older pages. |
| `include` | `array[str]`| No | `["info", "messages"]` | Array of data slices (use `["all"]` for everything) |
| `format` | `string` | No | `"sliced"` | `"sliced"` (rich hierarchical JSON) or `"flat"` (array of rowType objects) |
| `date_from` | `string` | No | `null` | Optional start date filter (`YYYY-MM-DD`) |
| `date_to` | `string` | No | `null` | Optional end date filter (`YYYY-MM-DD`) |
| `query` | `string` | No | `null` | Keyword filter on message text |

#### cURL Example:
```bash
curl -X POST http://localhost:8000/api/v1/telegram/channel \
  -H "Content-Type: application/json" \
  -d '{"username": "durov", "limit": 10, "include": ["all"]}'
```

#### Response:
```json
{
  "status": "success",
  "username": "durov",
  "info": {
    "title": "Pavel Durov",
    "subscribers": 1120000,
    "subscribers_str": "1.12M subscribers",
    "photos_count_str": "16",
    "videos_count_str": "228",
    "avatar_url": "https://cdn4.telesco.pe/file/...",
    "is_verified": true
  },
  "messages": [
    {
      "id": 548,
      "date": "2026-09-11T16:04:02+00:00",
      "text": "Telegram has become the sponsor of Codeforces...",
      "views": "1.12M",
      "has_media": true,
      "media_type": "video",
      "media_url": "https://cdn4.telesco.pe/file/cb8193dd68.mp4?token=..."
    }
  ]
}
```

---

### 2. Cursor-Based Message Pagination (`GET /telegram/channel/{username}/posts`)
**Purpose**: Paginate historical posts batch-by-batch using message IDs as cursors.

- **URL**: `http://localhost:8000/api/v1/telegram/channel/{username}/posts`
- **Method**: `GET`
- **Query Params**:
  - `limit` (*int, default 20*): Number of posts per page
  - `cursor` (*int, optional*): The oldest message ID from the previous batch

#### cURL Example:
```bash
# Page 1: Initial request
curl "http://localhost:8000/api/v1/telegram/channel/cryptodollar123/posts?limit=10"

# Page 2: Fetch next older batch using next_cursor
curl "http://localhost:8000/api/v1/telegram/channel/cryptodollar123/posts?limit=10&cursor=1396"
```

#### Response:
```json
{
  "status": "success",
  "username": "cryptodollar123",
  "limit": 10,
  "cursor": 1396,
  "next_cursor": 1386,
  "has_more": true,
  "count": 10,
  "messages": [...]
}
```

---

### 3. Channel Validation (`POST /telegram/channel/validate`)
**Purpose**: Instant check if a channel handle exists, is public, and returns basic counters.

- **URL**: `http://localhost:8000/api/v1/telegram/channel/validate`
- **Method**: `POST`
- **Payload**:
```json
{
  "username": "durov"
}
```

---

### 4. Single Post Scraper (`POST /telegram/post`)
**Purpose**: Scrapes a single message/post by URL or username + message_id.

- **URL**: `http://localhost:8000/api/v1/telegram/post`
- **Method**: `POST`
- **Payload**:
```json
{
  "url": "https://t.me/durov/1",
  "include": ["all"]
}
```

---

### 5. Channel & Group Search (`POST /telegram/search`)
**Purpose**: Search public Telegram channels and groups by keyword or industry.

- **URL**: `http://localhost:8000/api/v1/telegram/search`
- **Method**: `POST`
- **Payload**:
```json
{
  "query": "crypto",
  "type": "all",
  "limit": 10
}
```

---

### 6. Multi-Channel Batch Scrape (`POST /telegram/batch`)
**Purpose**: Scrape up to 50 channels simultaneously in parallel.

- **URL**: `http://localhost:8000/api/v1/telegram/batch`
- **Method**: `POST`
- **Payload**:
```json
{
  "usernames": ["durov", "telegram", "cryptodollar123"],
  "limit_per_channel": 10,
  "include": ["info", "messages", "leads"],
  "delay_sec": 1.0
}
```

---

### 7. Health & System Telemetry (`GET /telegram/health`)
- `GET /api/v1/telegram/health`: Basic uptime status.
- `GET /api/v1/telegram/health/detailed`: RAM (MB), CPU usage, process PID, and HTTP connection pool metrics.

---

## 🧩 Data Slices & Formatting Options

Pass any combination of these in `include` (or `["all"]`):
- `"info"`: Channel handle, title, bio, subscriber count, avatar CDN URL.
- `"messages"`: Post text, dates, author, view counts, direct media CDN URLs.
- `"engagement"`: Total views analyzed, average views per post.
- `"media"`: Photos, videos (`.mp4`), documents, audio links, durations.
- `"leads"`: Discovered emails, phone numbers, WhatsApp links, `@admin` handles.
- `"links"`: External web links.
- `"websites"`: Clean domains (e.g. `codeforces.com`).
- `"hashtags"` & `"mentions"`: Tag and mention frequencies.
- `"keywords"`: High-frequency extracted keywords.

---

## 🔄 Pagination Guide (How to Load More Messages)

### Method A: Auto-Pagination Crawler (Simplest)
Just increase `limit` in `POST /telegram/channel`. The crawler automatically traverses pages backwards until `limit` is reached.

```python
import requests

res = requests.post("http://localhost:8000/api/v1/telegram/channel", json={
    "username": "cryptodollar123",
    "limit": 100,               # Automatically fetches 5 pages under the hood
    "include": ["info", "messages"]
})

print("Fetched posts:", len(res.json()["messages"]))
```

---

### Method B: Cursor-Based Pagination Loop (Infinite Scroll)

#### Python Implementation:
```python
import requests

def paginate_channel(username: str, max_posts: int = 200):
    url = f"http://localhost:8000/api/v1/telegram/channel/{username}/posts"
    cursor = None
    all_posts = []

    while len(all_posts) < max_posts:
        params = {"limit": 20}
        if cursor:
            params["cursor"] = cursor

        data = requests.get(url, params=params).json()
        messages = data.get("messages", [])
        if not messages:
            break

        all_posts.extend(messages)
        print(f"Collected {len(all_posts)} posts so far...")

        if not data.get("has_more") or not data.get("next_cursor"):
            print("Reached beginning of channel history!")
            break

        cursor = data["next_cursor"]

    return all_posts

# Usage:
posts = paginate_channel("cryptodollar123", max_posts=100)
```

#### JavaScript / React Implementation:
```javascript
async function fetchMorePosts(username, cursor = null) {
  const url = new URL(`http://localhost:8000/api/v1/telegram/channel/${username}/posts`);
  url.searchParams.set("limit", "20");
  if (cursor) url.searchParams.set("cursor", cursor);

  const res = await fetch(url);
  const data = await res.json();

  return {
    messages: data.messages,
    nextCursor: data.next_cursor,
    hasMore: data.has_more
  };
}
```
