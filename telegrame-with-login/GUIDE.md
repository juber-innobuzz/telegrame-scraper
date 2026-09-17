# 🔐 Telegram MTProto & Auth Service (With Login) — Complete Guide

Enterprise Telegram MTProto Authentication, Multi-Account Session Pool, and Private Chat Scraper running on **Port 8001**.
- **Protocols**: Official Telegram binary MTProto protocol (Telethon) + Redis background queue.
- **Port**: `8001` (Redis mapped to `6380:6379`)
- **Swagger Docs**: `http://localhost:8001/docs`
- **Base API Path**: `http://localhost:8001/api/v1/telegram`

---

## 📑 Table of Contents
1. [Quick Start (Docker & Redis)](#-quick-start-docker--redis)
2. [Authentication Lifecycle Endpoints](#-1-authentication-lifecycle-endpoints)
   - [POST /auth/send-code (Request OTP)](#1-request-login-otp-post-authsend-code)
   - [POST /auth/verify-code (Submit OTP & Register Session)](#2-verify-otp-and-register-session-post-authverify-code)
   - [POST /auth/verify-2fa (Submit Cloud Password)](#3-verify-2fa-cloud-password-post-authverify-2fa)
   - [GET /auth/status (Overview of Accounts)](#4-auth-status-overview-get-authstatus)
   - [POST /auth/logout (Disconnect Session)](#5-logout-session-post-authlogout)
3. [User Client & Private Data Endpoints](#-2-user-client--private-data-endpoints)
   - [GET /user/me (User Profile)](#1-get-logged-in-profile-get-userme)
   - [GET /user/dialogs (DMs & Groups List)](#2-fetch-chats--dialogs-get-userdialogs)
   - [GET /user/chats/{chat_id}/messages (Private Chat History)](#3-fetch-private-chat-messages-get-userchatschat_idmessages)
4. [Session Pool & Multi-Account Management](#-3-session-pool--multi-account-management)
   - [GET /pool/status (Health & Cooldown Monitoring)](#1-session-pool-status-get-poolstatus)
   - [POST /pool/add-session (Dynamic Account Addition)](#2-add-session-at-runtime-post-pooladd-session)
5. [Enterprise Async Redis Scraping Queue](#-4-enterprise-async-redis-scraping-queue)
   - [POST /jobs/scrape-chat (Enqueue Job)](#1-enqueue-scraping-job-post-jobsscrape-chat)
   - [GET /jobs/{job_id} (Poll Progress)](#2-poll-job-status-get-jobsjob_id)
   - [GET /jobs/{job_id}/result (Download Dataset)](#3-download-scraped-dataset-get-jobsjob_idresult)

---

## 🐳 Quick Start (Docker & Redis)

1. Ensure `.env` contains your Telegram credentials:
   ```env
   TELEGRAM_API_ID=12345678
   TELEGRAM_API_HASH=your_api_hash_here
   TELEGRAM_SESSION_STRING=your_string_session_optional
   ```

2. Start the Docker container and Redis service:
   ```bash
   docker compose up -d --build
   ```

---

## 🔑 1. Authentication Lifecycle Endpoints

### 1. Request Login OTP (`POST /auth/send-code`)
**Purpose**: Sends an OTP login code to the user's Telegram app or SMS.

- **URL**: `http://localhost:8001/api/v1/telegram/auth/send-code`
- **Method**: `POST`
- **Payload**:
```json
{
  "phone_number": "+91XXXXXXXXXX"
}
```

#### cURL Example:
```bash
curl -X POST http://localhost:8001/api/v1/telegram/auth/send-code \
  -H "Content-Type: application/json" \
  -d '{"phone_number": "+917011186517"}'
```

#### Response:
```json
{
  "status": "code_sent",
  "auth_session_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "phone_number": "+917011186517",
  "phone_code_hash": "a1b2c3d4e5f6",
  "is_code_via_app": true,
  "timeout": 120,
  "message": "Verification code sent to your Telegram app or SMS."
}
```

---

### 2. Verify OTP and Register Session (`POST /auth/verify-code`)
**Purpose**: Submits the OTP code. If 2FA is required, returns `status: "2fa_required"`. Otherwise completes authentication and automatically registers the new account into the multi-account Session Pool.

- **URL**: `http://localhost:8001/api/v1/telegram/auth/verify-code`
- **Method**: `POST`
- **Payload**:
```json
{
  "auth_session_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "phone_number": "+917011186517",
  "phone_code_hash": "a1b2c3d4e5f6",
  "code": "12345",
  "session_name": "Account 1",
  "auto_add_to_pool": true
}
```

#### Response (Success):
```json
{
  "status": "authenticated",
  "session_id": "session_acc_1",
  "session_string": "1BJWap1wBu...",
  "message": "Successfully authenticated as Amir Khan",
  "user": {
    "user_id": 123456789,
    "first_name": "Amir",
    "username": "amir_marketing"
  }
}
```

---

### 3. Verify 2FA Cloud Password (`POST /auth/verify-2fa`)
**Purpose**: Submits the 2-step verification password if the account has 2FA enabled.

- **URL**: `http://localhost:8001/api/v1/telegram/auth/verify-2fa`
- **Method**: `POST`
- **Payload**:
```json
{
  "auth_session_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "password": "my_cloud_password",
  "session_name": "Account 1",
  "auto_add_to_pool": true
}
```

---

### 4. Auth Status Overview (`GET /auth/status`)
**Purpose**: Real-time status of all active accounts in memory.

- **URL**: `http://localhost:8001/api/v1/telegram/auth/status`
- **Method**: `GET`

```bash
curl http://localhost:8001/api/v1/telegram/auth/status
```

---

### 5. Logout Session (`POST /auth/logout`)
- **URL**: `http://localhost:8001/api/v1/telegram/auth/logout`
- **Payload**: `{"session_id": "session_acc_1"}`

---

## 👤 2. User Client & Private Data Endpoints

### 1. Get Logged-in Profile (`GET /user/me`)
- **URL**: `http://localhost:8001/api/v1/telegram/user/me`
- **Method**: `GET`

#### Response:
```json
{
  "status": "success",
  "user_id": 123456789,
  "first_name": "Amir",
  "last_name": "Khan",
  "username": "amir_originals",
  "phone": "+917011186517",
  "is_premium": true
}
```

---

### 2. Fetch Chats & Dialogs (`GET /user/dialogs`)
**Purpose**: Returns all recent conversations, DMs, private groups, and unread counters.

- **URL**: `http://localhost:8001/api/v1/telegram/user/dialogs`
- **Query Params**:
  - `limit` (*default 50*): Max dialogs
  - `filter_type` (*optional*): `"user"` (DMs only), `"group"`, `"channel"`

#### cURL Example:
```bash
curl "http://localhost:8001/api/v1/telegram/user/dialogs?limit=10&filter_type=user"
```

---

### 3. Fetch Private Chat Messages (`GET /user/chats/{chat_id}/messages`)
**Purpose**: Extracts message history from any private chat, DM, or closed group.

- **URL**: `http://localhost:8001/api/v1/telegram/user/chats/{chat_id}/messages`
- **Query Params**:
  - `limit` (*default 50*): Max messages per batch
  - `offset_id` (*optional*): Cursor message ID for older messages

#### cURL Example:
```bash
curl "http://localhost:8001/api/v1/telegram/user/chats/777000/messages?limit=20"
```

---

## 🏊 3. Session Pool & Multi-Account Management

### 1. Session Pool Status (`GET /pool/status`)
**Purpose**: Live metrics on account load balancing, requests dispatched, messages collected, and FloodWait cooldown countdowns.

- **URL**: `http://localhost:8001/api/v1/telegram/pool/status`
- **Method**: `GET`

#### Response:
```json
{
  "status": "success",
  "total_accounts": 2,
  "available_accounts": 2,
  "accounts": [
    {
      "session_id": "primary",
      "name": "Primary Account",
      "is_available": true,
      "total_requests": 142,
      "total_messages_scraped": 3500,
      "flood_wait_count": 0,
      "cooldown_remaining_seconds": 0
    }
  ]
}
```

---

### 2. Add Session at Runtime (`POST /pool/add-session`)
- **URL**: `http://localhost:8001/api/v1/telegram/pool/add-session`
- **Payload**:
```json
{
  "session_id": "acc_2",
  "session_string": "1BJWap1wBu...",
  "name": "Secondary Worker Account"
}
```

---

## ⚡ 4. Enterprise Async Redis Scraping Queue

For scraping thousands of messages without blocking HTTP requests:

### 1. Enqueue Scraping Job (`POST /jobs/scrape-chat`)
- **URL**: `http://localhost:8001/api/v1/telegram/jobs/scrape-chat`
- **Payload**:
```json
{
  "chat_id": 777000,
  "limit": 5000,
  "search_query": "code"
}
```

#### Response:
```json
{
  "status": "queued",
  "job_id": "e2a4a758-2e38-4e78-9eb2-d49e6f3df18a",
  "target_limit": 5000,
  "status_url": "/api/v1/telegram/jobs/e2a4a758-2e38-4e78-9eb2-d49e6f3df18a"
}
```

---

### 2. Poll Job Status (`GET /jobs/{job_id}`)
- **URL**: `http://localhost:8001/api/v1/telegram/jobs/{job_id}`

#### Response:
```json
{
  "job_id": "e2a4a758-2e38-4e78-9eb2-d49e6f3df18a",
  "status": "processing",
  "progress_percent": 64.5,
  "messages_scraped": 3225
}
```

---

### 3. Download Scraped Dataset (`GET /jobs/{job_id}/result`)
- **URL**: `http://localhost:8001/api/v1/telegram/jobs/{job_id}/result`
- Downloads full message array once `status` reaches `"completed"`.
