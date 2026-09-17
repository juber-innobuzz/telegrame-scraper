# ⚡ Enterprise & High-Scale API Endpoints Guide (हिंदी / Hinglish)

यह डॉक्यूमेंट **Enterprise-Scale Telegram Scraper API** के 3 नए एडवांस एंडपॉइंट्स, उनके काम करने का तरीका (Working Mechanism), रिक्वेस्ट/रिस्पॉन्स पेलोड्स, और डिस्ट्रीब्यूटेड आर्किटेक्चर फ्लो को समझाता है।

---

## 📑 विषय-सूची (Table of Contents)
1. [🏗️ डिस्ट्रीब्यूटेड प्रोडक्शन आर्किटेक्चर (System Blueprint)](#1-डिस्ट्रीब्यूटेड-प्रोडक्शन-आर्किटेक्चर)
2. [🔹 1. GET /api/channel/{username}/posts (Cursor-based Pagination)](#-1-get-apichannelusernameposts-कर्सर-पेजिनेशन)
3. [🔹 2. POST /api/channel/validate (Pre-Flight Channel Validator)](#-2-post-apichannelvalidate-प्री-फ्लाइट-चैनल-वैलिडेटर)
4. [🔹 3. GET /api/health/detailed (System Telemetry & Monitoring)](#-3-get-apihealthdetailed-सिस्टम-टेलीमेट्री-व-मॉनिटरिंग)
5. [💻 कोड उदाहरण (cURL, Python, JavaScript)](#5-कोड-उदाहरण)

---

## 1. डिस्ट्रीब्यूटेड प्रोडक्शन आर्किटेक्चर

हाई-ट्रैफिक कमर्शियल स्क्रैपिंग के लिए यह सिस्टम एक स्केलेबल पाइपलाइन की तरह काम करता है:

```
Client Request (Frontend / Mobile App / Cron Job)
      ↓
API Gateway (FastAPI / Rate Limiting & Input Sanitization)
      ↓
Queue Layer (Redis Queue / BullMQ / Celery for Async Jobs)
      ↓
Worker Pool (Async Workers / Browser Engine with Anti-Block Backoff)
      ↓
Cache & Storage Layer (MongoDB / Redis Cache + Post Deduplication)
      ↓
Fast Structured Response (Sliced JSON or Flat Array)
```

---

## 🔹 1. `GET /api/channel/{username}/posts` (कर्सर पेजिनेशन)

### 📌 यह क्या काम करता है?
यह एंडपॉइंट एक साथ पूरा डेटा लोड करने के बजाय **टुकड़ों (Chunks) में पेज-दर-पेज** पोस्ट्स लोड करता है। यह मोबाइल ऐप्स और वेब फ्रंटएंड में **Infinite Scroll** और बैकग्राउंड डेटाबेस सिंक के लिए सबसे बेस्ट है।

### ⚙️ यह कैसे काम करता है?
1. जब आप पहली बार कॉल करते हैं (बिना `cursor` के), तो यह सबसे हालिया 20 पोस्ट्स लाता है।
2. रिस्पॉन्स में सबसे पुराने पोस्ट की ID **`next_cursor`** में मिलती है (उदा. `next_cursor: 440`) और **`has_more: true`** मिलता है।
3. अगले पेज के लिए आप `?cursor=440` भेजते हैं, जिससे उसके ठीक पुराने पोस्ट्स लोड हो जाते हैं।

### 📥 Query Parameters:
| पैरामीटर | प्रकार | डिफ़ॉल्ट | विवरण |
| :--- | :--- | :--- | :--- |
| `username` *(Path)* | `string` | **Required** | चैनल यूजरनेम (उदा. `telegram`, `durov`) |
| `cursor` *(Query)* | `integer` | `null` | इस मैसेज ID से पुराने पोस्ट्स लोड करें |
| `limit` *(Query)* | `integer` | `20` | एक पेज में कितने पोस्ट्स चाहिए (1 से 100) |
| `format` *(Query)* | `string` | `"sliced"` | `"sliced"` (नेस्टेड JSON) या `"flat"` (data.json स्टाइल) |
| `query` *(Query)* | `string` | `null` | पोस्ट्स में टेक्स्ट कीवर्ड सर्च |

### 📤 Response Example (`format="sliced"`):
```json
{
  "status": "success",
  "username": "telegram",
  "limit": 5,
  "cursor": null,
  "next_cursor": 455,
  "has_more": true,
  "count": 5,
  "messages": [
    {
      "id": 460,
      "message_id": 460,
      "channel_username": "telegram",
      "url": "https://t.me/telegram/460",
      "date": "2026-08-26T19:12:34+00:00",
      "text": "For all the info from today's update...",
      "author": "Telegram News",
      "views": "1.02M",
      "has_media": false,
      "media_type": null,
      "media_url": null,
      "link": "https://telegram.org/blog/welcome-messages-buttons-TG-13"
    }
  ]
}
```

---

## 🔹 2. `POST /api/channel/validate` (प्री-फ्लाइट चैनल वैलिडेटर)

### 📌 यह क्या काम करता है?
भारी स्क्रैपिंग टास्क या लंबी बैच प्रोसेसिंग शुरू करने से पहले, यह एंडपॉइंट **सिर्फ 0.1-0.2 सेकंड** में यह चेक कर लेता है कि:
* चैनल Telegram पर मौजूद है या नहीं।
* चैनल **पब्लिक (Public)** है या **प्राइवेट/इनवाइट-ओनली (Private)**।
* चैनल बैन या डिलीट तो नहीं हुआ है।

### 📥 Request Payload:
```json
{
  "username": "telegram"
}
```

### 📤 Response Examples:

#### ✅ 1. पब्लिक चैनल होने पर (Public Channel):
```json
{
  "status": "success",
  "username": "telegram",
  "is_valid": true,
  "exists": true,
  "is_public": true,
  "channel_status": "public",
  "title": "Telegram News",
  "description": "The official Telegram on Telegram. Much recursion. Very Telegram. Wow.",
  "subscribers": 9600000,
  "subscribers_str": "9.6M subscribers",
  "avatar_url": "https://cdn5.telesco.pe/file/avatar.jpg",
  "is_verified": true,
  "url": "https://t.me/telegram",
  "error": null
}
```

#### 🔒 2. प्राइवेट/इनवाइट-ओनली चैनल होने पर (Private Channel):
```json
{
  "status": "success",
  "username": "secret_crypto_vip",
  "is_valid": true,
  "exists": true,
  "is_public": false,
  "channel_status": "private_or_restricted",
  "title": "VIP Crypto Group",
  "subscribers": null,
  "subscribers_str": null,
  "avatar_url": "https://cdn5.telesco.pe/file/avatar.jpg",
  "is_verified": false,
  "url": "https://t.me/secret_crypto_vip",
  "error": "Channel is private or requires invite link to view"
}
```

#### ❌ 3. चैनल न मिलने पर (Not Found):
```json
{
  "status": "success",
  "username": "random_fake_channel_99999",
  "is_valid": true,
  "exists": false,
  "is_public": false,
  "channel_status": "not_found",
  "title": null,
  "subscribers": null,
  "subscribers_str": null,
  "avatar_url": null,
  "is_verified": false,
  "url": "https://t.me/random_fake_channel_99999",
  "error": "Channel does not exist on Telegram"
}
```

---

## 🔹 3. `GET /api/health/detailed` (सिस्टम टेलीमेट्री व मॉनिटरिंग)

### 📌 यह क्या काम करता है?
यह प्रोडक्शन मॉनिटरिंग (Datadog, Prometheus, Grafana, या Health Checkers) के लिए लाइव सिस्टम टेलीमेट्री और रिसोर्स मेट्रिक्स देता है:
* **Memory/RAM Usage:** प्रोसेस का RSS (Resident Set Size) और VMS MB में, और सिस्टम की बची हुई RAM।
* **CPU Load:** प्रोसेस CPU % और सिस्टम कोर काउंट।
* **HTTP Client Connection Pool:** एक्टिव कनेक्शन्स, टाइमआउट्स और कीप-अलाइव लिमिट्स।
* **Uptime:** सर्वर कितने सेकंड से बिना रुके चल रहा है।

### 📤 Response Example:
```json
{
  "status": "healthy",
  "service": "Telegram Business Scraper API",
  "version": "1.0.0",
  "uptime_seconds": 384.25,
  "system": {
    "os": "Windows",
    "os_release": "10.0.26200",
    "python_version": "3.11.9",
    "pid": 24820
  },
  "memory": {
    "process_rss_mb": 45.18,
    "process_vms_mb": 58.74,
    "system_total_gb": 15.69,
    "system_available_gb": 3.42,
    "system_memory_used_percent": 78.2
  },
  "cpu": {
    "process_cpu_percent": 0.0,
    "cpu_cores_logical": 12,
    "cpu_cores_physical": 6,
    "system_cpu_percent": 12.4
  },
  "http_pool": {
    "request_timeout_sec": 15,
    "max_connections": 50,
    "max_keepalive_connections": 20,
    "status": "active"
  }
}
```

---

## 5. कोड उदाहरण

### 💻 1. Infinite Scroll Pagination (Python)
```python
import requests

username = "telegram"
cursor = None
page = 1

while page <= 3:
    url = f"http://localhost:8000/api/channel/{username}/posts"
    params = {"limit": 10}
    if cursor:
        params["cursor"] = cursor
        
    res = requests.get(url, params=params).json()
    print(f"--- Page {page} (Posts: {res['count']}) ---")
    for msg in res["messages"]:
        print(f"Msg #{msg['id']} | Views: {msg['views']} | Date: {msg['date'][:10]}")
    
    if not res["has_more"] or not res["next_cursor"]:
        break
    cursor = res["next_cursor"]
    page += 1
```

### 💻 2. Fast Channel Validation (JavaScript / Node.js)
```javascript
const checkChannel = async (username) => {
  const response = await fetch("http://localhost:8000/api/channel/validate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username })
  });
  
  const result = await response.json();
  if (result.is_public) {
    console.log(`✅ ${result.title} is PUBLIC with ${result.subscribers_str}`);
  } else {
    console.log(`⚠️ Channel Status: ${result.channel_status} (${result.error})`);
  }
};

await checkChannel("telegram");
await checkChannel("non_existent_ch_123");
```

### 💻 3. System Health Check (cURL)
```bash
curl -X GET "http://localhost:8000/api/health/detailed"
```
