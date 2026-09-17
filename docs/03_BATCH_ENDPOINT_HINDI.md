# 📦 Endpoint 3: `POST /telegram/batch` (मल्टी-चैनल बैच स्क्रैपर)

## 📌 1. यह API क्या काम करती है? (Overview)
यह एंडपॉइंट एक ही API कॉल में एक साथ 10, 20 या 50 टेलीग्राम चैनलों की लिस्ट को स्क्रैप करने की सुविधा देता है। इसमें स्मार्ट टाइम-डिले (Delay), वॉटरमार्क फ़िल्टरिंग (`since_message_id`), और हर चैनल के लिए अलग-अलग एरर हैंडलिंग होती है ताकि एक चैनल फेल होने पर बाकी बंद न हों।

---

## ⚙️ 2. यह API अंदर से कैसे काम करती है? (Working Mechanism)
1. **Array Iteration & Target Cleanup:**
   - यूजर द्वारा भेजी गई चैनलों की लिस्ट (`usernames: ["durov", "telegram", "techdeals"]`) को एक-एक करके नॉर्मलाइज़ किया जाता है।
2. **Per-Channel Scraping Loop:**
   - हर चैनल के लिए चैनल हेडर (अगर `info` मांगा गया है) और हालिया मैसेजेस क्रॉल किए जाते हैं।
3. **Incremental Watermark Filtering (`since_message_id`):**
   - अगर यूजर ने वॉटरमार्क डिक्शनरी पास की है (जैसे: `{"durov": 250}`), तो API सिर्फ वही मैसेजेस रखती है जिनका `message_id > 250` हो। इससे आपको हर बार पुराना डुप्लीकेट डेटा नहीं मिलता, सिर्फ नए पोस्ट मिलते हैं।
4. **Resilient Try-Catch Isolation:**
   - अगर कोई चैनल डिलीट हो चुका है, बैन है या प्राइवेट है, तो उस चैनल के रिस्पॉन्स में `status: "error"` दर्ज होता है, लेकिन बाकी चैनलों की प्रोसेसिंग बिना रुके चलती रहती है।
5. **Anti-Flood Rate-Limiting Delay (`delay_sec`):**
   - हर चैनल को प्रोसेस करने के बीच में यूजर द्वारा तय किया गया गैप (उदा. `1.5` सेकंड) का ऑटोमैटिक स्लीप (`asyncio.sleep`) दिया जाता है।
6. **Aggregated Results & Stats:**
   - अंत में `total_channels`, `successful`, `failed`, और सभी चैनलों का स्लाइस्ड डेटा एक स्ट्रक्चर्ड JSON में लौटता है।

---

## 🔬 3. इसमें कौन-कौन सी तकनीकें (Techniques) इस्तेमाल हो रही हैं?
- **Asynchronous Batch Execution:** Python `asyncio` के साथ नॉन-ब्लॉकिंग HTTP फेचिंग।
- **Rate-Limiting Interleaved Jitter:** टेलीग्राम IP ब्लॉकिंग से बचने के लिए बीच-बीच में स्मूथ थ्रॉटल डिले।
- **Incremental Polling Architecture:** `since_message_id` वॉटरमार्क का इस्तेमाल करके सिर्फ फ्रेश/नया डेटा लेना (डेटाबेस सिंक और क्रॉन जॉब्स के लिए बेस्ट)।
- **Fault-Tolerant Partial Success:** पूरे बैच को क्रैश किए बिना फेलियर वाले चैनल को अलग मार्क करना।

---

## 📥 4. हम क्या-क्या Payload पास कर सकते हैं? (Payload Parameters)

| पैरामीटर (Field) | प्रकार (Type) | ज़रूरी है? | डिफ़ॉल्ट | विवरण (Description) |
| :--- | :--- | :--- | :--- | :--- |
| `usernames` | `array[string]` | **हाँ (Required)** | - | चैनलों के यूजरनेम या लिंक्स की लिस्ट (उदा. `["durov", "telegram"]`) |
| `include` | `array[string]` | नहीं (Optional) | `["info", "messages"]` | सभी चैनलों के लिए कौन-कौन से स्लाइस चाहिए (उदा. `["info", "leads", "engagement"]`) |
| `limit_per_channel` | `integer` | नहीं (Optional) | `20` | प्रति चैनल अधिकतम कितने मैसेजेस स्क्रैप करने हैं (अधिकतम 100) |
| `delay_sec` | `number` | नहीं (Optional) | `1.0` | दो चैनलों के बीच कितने सेकंड का इंतज़ार करना है (Anti-Flood Rate Limit) |
| `since_message_id` | `object` | नहीं (Optional) | `null` | किस चैनल से किस ID के बाद के नए मैसेज चाहिए (उदा. `{"durov": 250}`) |
| `date_from` | `string` | नहीं (Optional) | `null` | स्टार्ट डेट फ़िल्टर (`YYYY-MM-DD`) |
| `date_to` | `string` | नहीं (Optional) | `null` | एंड डेट फ़िल्टर (`YYYY-MM-DD`) |
| `query` | `string` | नहीं (Optional) | `null` | सभी चैनलों के पोस्ट में कीवर्ड फ़िल्टर |
| `options` | `object` | नहीं (Optional) | `{}` | एक्सट्रैक्टर ऑप्शन्स (`unique_links`, `include_emails`, आदि) |

---

## 📋 5. Request Payload Examples

### 🔹 उदाहरण A: मल्टी-चैनल बेसिक बैच
```json
{
  "usernames": [
    "durov",
    "telegram"
  ],
  "include": [
    "info",
    "engagement",
    "leads",
    "websites"
  ],
  "limit_per_channel": 10,
  "delay_sec": 1.5
}
```

### 🔹 उदाहरण B: इंक्रीमेंटल वॉटरमार्क पोलिंग (सिर्फ नए पोस्ट्स के लिए)
```json
{
  "usernames": [
    "techdeals",
    "crypto_news"
  ],
  "include": [
    "products",
    "prices",
    "leads"
  ],
  "limit_per_channel": 30,
  "since_message_id": {
    "techdeals": 45120,
    "crypto_news": 18900
  },
  "delay_sec": 2.0
}
```

---

## 📤 6. Response Payload Example

```json
{
  "status": "success",
  "total_channels": 2,
  "successful": 2,
  "failed": 0,
  "results": [
    {
      "status": "success",
      "username": "durov",
      "requested": ["info", "engagement", "leads"],
      "info": {
        "username": "durov",
        "title": "Pavel Durov",
        "description": "Thoughts from the creator of Telegram.",
        "subscribers": 2800000,
        "subscribers_str": "2.8M subscribers",
        "avatar_url": "https://cdn5.telesco.pe/file/avatar_durov.jpg",
        "is_verified": true,
        "url": "https://t.me/durov"
      },
      "engagement": {
        "total_posts_analyzed": 10,
        "total_views": 18500000,
        "average_views_per_post": 1850000.0,
        "total_reactions": 420000,
        "reactions_breakdown": { "❤️": 210000, "🔥": 150000, "👍": 60000 }
      },
      "leads": {
        "total_leads_found": 0,
        "emails": [],
        "phones": [],
        "whatsapp": [],
        "telegram_contacts": []
      }
    },
    {
      "status": "success",
      "username": "telegram",
      "requested": ["info", "engagement", "leads"],
      "info": {
        "username": "telegram",
        "title": "Telegram News",
        "description": "Official news about Telegram features and updates.",
        "subscribers": 6500000,
        "subscribers_str": "6.5M subscribers",
        "avatar_url": "https://cdn5.telesco.pe/file/avatar_tg.jpg",
        "is_verified": true,
        "url": "https://t.me/telegram"
      },
      "engagement": {
        "total_posts_analyzed": 10,
        "total_views": 32000000,
        "average_views_per_post": 3200000.0,
        "total_reactions": 850000,
        "reactions_breakdown": { "🎉": 450000, "🔥": 400000 }
      },
      "leads": {
        "total_leads_found": 0,
        "emails": [],
        "phones": [],
        "whatsapp": [],
        "telegram_contacts": []
      }
    }
  ]
}
```

---

## 💻 7. कोड उदाहरण (Code Examples)

### Python (Automated Cron Sync Job)
```python
import requests

url = "http://localhost:8000/telegram/batch"
payload = {
    "usernames": ["durov", "telegram", "techinsider"],
    "include": ["info", "engagement", "leads"],
    "limit_per_channel": 15,
    "delay_sec": 1.5,
    "since_message_id": {
        "durov": 240,
        "telegram": 510
    }
}

res = requests.post(url, json=payload)
data = res.json()

print(f"कुल चैनल: {data['total_channels']} | सफल: {data['successful']} | फेल: {data['failed']}")
for ch in data["results"]:
    if ch["status"] == "success":
        print(f"-> {ch['info']['title']}: {ch['info']['subscribers_str']}")
```

### JavaScript / Node.js
```javascript
const response = await fetch("http://localhost:8000/telegram/batch", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    usernames: ["durov", "telegram"],
    include: ["info", "leads", "engagement"],
    limit_per_channel: 10,
    delay_sec: 1.0
  })
});

const result = await response.json();
console.log(`Success: ${result.successful}/${result.total_channels}`);
```
