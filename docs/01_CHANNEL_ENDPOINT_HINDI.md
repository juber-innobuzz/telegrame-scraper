# 📡 Endpoint 1: `POST /telegram/channel` (पब्लिक चैनल स्क्रैपर)

## 📌 1. यह API क्या काम करती है? (Overview)
यह एंडपॉइंट किसी भी पब्लिक टेलीग्राम चैनल (जैसे `@durov`, `@techdeals`, आदि) का पूरा प्रोफाइल डेटा, हालिया पोस्ट्स और उनमें छुपी बिज़नेस इंफॉर्मेशन (ईमेल्स, फोन नंबर्स, प्रोडक्ट्स, डील्स, कीमतें, सोशल लिंक्स आदि) निकालता है।

---

## ⚙️ 2. यह API अंदर से कैसे काम करती है? (Working Mechanism)
1. **URL Normalization (`normalize_telegram_target`):**
   - अगर यूजर `@username`, `https://t.me/username`, या `https://t.me/s/username` पास करता है, तो सिस्टम उसमें से सिर्फ शुद्ध चैनल हैंडल (`username`) निकालता है।
2. **Channel Header Scrape (`TelegramParser.parse_channel_info`):**
   - `https://t.me/s/<username>` पर रिक्वेस्ट भेजकर चैनल का Title, Description, Subscriber Count, Avatar Image URL और Verified Badge स्टेटस निकाला जाता है।
3. **Pagination & Cursor Crawling (`TelegramPaginationCrawler`):**
   - टेलीग्राम वेब प्रीव्यू एक बार में केवल 20-30 मैसेज दिखाता है।
   - अगर यूजर ने `limit=100` मांगा है, तो API `?before=<last_msg_id>` पैरामीटर का इस्तेमाल करके पिछले पेजों पर जाती है और तब तक मैसेजेस कलेक्ट करती है जब तक लिमिट या डेट रेंज पूरी न हो जाए।
4. **Keyword/Query Filtering:**
   - अगर पेलोड में `query` दिया गया है, तो सिर्फ वही मैसेजेस रखे जाते हैं जिनमें वह कीवर्ड मैच होता है।
5. **Dynamic Slicing Engine (`build_response_slices`):**
   - यूजर ने `include` ऐरे में जो-जो स्लाइस मांगे हैं (जैसे: `leads`, `products`, `prices`, `engagement`), सिर्फ वही एक्सट्रैक्ट करके फाइनल JSON में जोड़े जाते हैं। गैर-ज़रूरी फील्ड्स को प्रोसेस ही नहीं किया जाता, जिससे रिस्पॉन्स बहुत सुपरफास्ट रहता है।

---

## 🔬 3. इसमें कौन-कौन सी तकनीकें (Techniques) इस्तेमाल हो रही हैं?
- **Zero-Login Public Web Scraping:** बिना किसी Telegram API Key (tdlib/telethon), Bot Token या फोन नंबर के सीधे पब्लिक वेब प्रीव्यू `t.me/s/` से डेटा लिया जाता है।
- **User-Agent Rotation & Jitter:** हर रिक्वेस्ट पर रैंडम रियल ब्राउज़र User-Agents और हेडर रोटेट होते हैं ताकि 429 Too Many Requests से बचा जा सके।
- **Exponential Backoff:** अगर टेलीग्राम कभी रेट लिमिट करता है, तो `httpx` क्लाइंट बैकऑफ और रैंडम टाइम डिले (Jitter) के साथ ऑटोमैटिक रिट्राई करता है।
- **Regex & Heuristics NLP Extraction:**
  - **Emails & Phones:** Regex पैटर्न्स से टेक्स्ट में लिखे ईमेल और इंटरनेशनल फोन नंबर्स पकड़ता है।
  - **Products & Prices:** करेंसी सिंबल्स (`₹`, `$`, `€`, `USDT`), डिस्काउंट प्रतिशत और बाय-लिंक्स (Amazon, Flipkart आदि) को पहचानकर स्ट्रक्चर्ड प्रोडक्ट बनाता है।
  - **Engagement Calculator:** व्यूज (`12.5K` -> `12500`), रिएक्शन्स और एवरेज व्यूज कैलकुलेट करता है।

---

## 📥 4. हम क्या-क्या Payload पास कर सकते हैं? (Payload Parameters)

| पैरामीटर (Field) | प्रकार (Type) | ज़रूरी है? | डिफ़ॉल्ट (Default) | विवरण (Description) |
| :--- | :--- | :--- | :--- | :--- |
| `username` | `string` | **हाँ (Required)** | - | चैनल का यूजरनेम (उदा. `durov`) या पूरा URL (`https://t.me/durov`) |
| `include` | `array[string]` | नहीं (Optional) | `["info", "messages"]` | आपको कौन सा डेटा चाहिए। सब चाहिए तो `["all"]` दें। (विकल्प: `info`, `messages`, `engagement`, `leads`, `products`, `services`, `prices`, `websites`, `social_links`, `media`, `links`, `hashtags`, `mentions`, `forwards`, `jobs`, `locations`, `entities`, `keywords`) |
| `limit` | `integer` | नहीं (Optional) | `50` | कितने मैसेजेस स्क्रैप करने हैं (अधिकतम 500) |
| `before_message_id` | `integer` | नहीं (Optional) | `null` | इस मैसेज ID से पुराने पोस्ट्स लोड करने के लिए (Pagination Cursor) |
| `date_from` | `string` | नहीं (Optional) | `null` | इस तारीख के बाद के पोस्ट्स (फॉर्मेट: `YYYY-MM-DD`, उदा. `2026-01-01`) |
| `date_to` | `string` | नहीं (Optional) | `null` | इस तारीख से पहले के पोस्ट्स (फॉर्मेट: `YYYY-MM-DD`, उदा. `2026-12-31`) |
| `query` | `string` | नहीं (Optional) | `null` | मैसेजेस में खास कीवर्ड सर्च करने के लिए (उदा. `discount`, `crypto`) |
| `options` | `object` | नहीं (Optional) | `{}` | एक्सट्रैक्टर सेटिंग्स: `unique_links`, `include_emails`, `include_phones`, `price_currency_filter` |

---

## 📋 5. Request Payload Examples

### 🔹 उदाहरण A: बेसिक जानकारी और पोस्ट्स (Basic Info & Messages)
```json
{
  "username": "durov",
  "include": ["info", "messages"],
  "limit": 5
}
```

### 🔹 उदाहरण B: बिज़नेस लीड्स और ई-कॉमर्स प्रोडक्ट्स निकालना (Leads + Products + Prices)
```json
{
  "username": "loot_deals_india",
  "include": ["info", "products", "prices", "leads", "engagement", "social_links"],
  "limit": 20,
  "options": {
    "unique_links": true,
    "include_emails": true,
    "include_phones": true
  }
}
```

### 🔹 उदाहरण C: डेट रेंज और कीवर्ड फिल्टर (Date Filter + Query)
```json
{
  "username": "tech_jobs",
  "include": ["jobs", "leads", "messages"],
  "limit": 50,
  "date_from": "2026-01-01",
  "date_to": "2026-06-30",
  "query": "python developer"
}
```

---

## 📤 6. Response Payload Example

```json
{
  "status": "success",
  "username": "loot_deals_india",
  "requested": ["info", "products", "leads", "engagement"],
  "info": {
    "username": "loot_deals_india",
    "title": "Online Loot Deals & Discounts",
    "description": "Daily Amazon & Flipkart Deals. Contact @lootadmin or loot@deals.com",
    "subscribers": 145000,
    "subscribers_str": "145K subscribers",
    "avatar_url": "https://cdn5.telesco.pe/file/avatar.jpg",
    "is_verified": false,
    "url": "https://t.me/loot_deals_india"
  },
  "engagement": {
    "total_posts_analyzed": 5,
    "total_views": 18200,
    "average_views_per_post": 3640.0,
    "total_reactions": 95,
    "reactions_breakdown": {
      "🔥": 60,
      "👍": 35
    }
  },
  "leads": {
    "total_leads_found": 2,
    "emails": [
      { "email": "loot@deals.com", "source_message_id": 105, "date": "2026-09-08T10:00:00+00:00" }
    ],
    "phones": [],
    "whatsapp": [],
    "telegram_contacts": [
      { "handle": "@lootadmin", "url": "https://t.me/lootadmin", "source_message_id": 105, "date": "2026-09-08T10:00:00+00:00" }
    ]
  },
  "products": [
    {
      "name": "Wireless Bluetooth Earbuds 50hr Playtime",
      "type": "product",
      "category": "electronics",
      "keyword_matched": "deal",
      "price_details": {
        "deal_price": "₹899",
        "mrp": "₹2,999",
        "discount_info": "70% off",
        "currency": "₹",
        "all_prices": [
          { "raw_price": "₹899", "currency": "₹", "amount": "899" },
          { "raw_price": "₹2,999", "currency": "₹", "amount": "2,999" }
        ]
      },
      "buy_links": ["https://amazon.in/dp/B00EXAMPLE?tag=affiliate-21"],
      "media": [
        { "type": "image", "url": "https://cdn5.telesco.pe/file/earbuds.jpg", "thumbnail": null, "file_name": null, "duration": null }
      ],
      "message_id": 105,
      "date": "2026-09-08T10:00:00+00:00",
      "url": "https://t.me/loot_deals_india/105"
    }
  ]
}
```

---

## 💻 7. कोड उदाहरण (Code Examples)

### cURL
```bash
curl -X POST "http://localhost:8000/telegram/channel" \
     -H "Content-Type: application/json" \
     -d '{
       "username": "durov",
       "include": ["info", "engagement", "leads"],
       "limit": 10
     }'
```

### Python
```python
import requests

url = "http://localhost:8000/telegram/channel"
payload = {
    "username": "loot_deals_india",
    "include": ["info", "products", "leads", "engagement"],
    "limit": 15,
    "options": {
        "unique_links": True,
        "include_emails": True
    }
}

response = requests.post(url, json=payload)
data = response.json()

print(f"चैनल: {data['info']['title']}")
print(f"सब्सक्राइबर्स: {data['info']['subscribers_str']}")
print(f"कुल प्रोडक्ट्स मिले: {len(data.get('products', []))}")
```

### JavaScript / Node.js
```javascript
const response = await fetch("http://localhost:8000/telegram/channel", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    username: "durov",
    include: ["info", "messages", "engagement"],
    limit: 5
  })
});

const result = await response.json();
console.log("Channel Data:", result);
```
