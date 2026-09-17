# 🔍 Endpoint 4: `POST /telegram/search` (पब्लिक चैनल और ग्रुप डिस्कवरी)

## 📌 1. यह API क्या काम करती है? (Overview)
यह एंडपॉइंट किसी भी विषय (Niche/Topic), कीवर्ड या इंडस्ट्री (जैसे: `crypto`, `ai tools`, `python developers`, `deals`) से संबंधित नए पब्लिक टेलीग्राम चैनल्स और कम्युनिटी ग्रुप्स को खोजने (Discover) का काम करता है।

---

## ⚙️ 2. यह API अंदर से कैसे काम करती है? (Working Mechanism)
1. **Target Query Cleaning:**
   - यूजर द्वारा भेजी गई सर्च स्ट्रिंग (उदा. `"crypto trading"`) को सैनिटाइज और वैलिडेट किया जाता है।
2. **Multi-Source Web Search Queries (`TelegramSearchEngine`):**
   - यह इंजन सर्च इंजनों (Google/DuckDuckGo) के पब्लिक इंडेक्स में `site:t.me <query>` के ज़रिए एक्टिव पब्लिक टेलीग्राम लिंक्स खोजता है।
3. **URL & Entity Disambiguation:**
   - सर्च रिजल्ट्स में से इनवैलिड या प्राइवेट लिंक्स को छांटा जाता है।
   - चैनल (`/s/` या डायरेक्ट हैंडल) और ग्रुप चैट्स को अलग-अलग कैटेगराइज किया जाता है।
4. **Live Metadata Enrichment:**
   - मिले हुए हैंडल्स के पब्लिक पेजों से लाइव टाइटल, बायो (Description), सब्सक्राइबर/मेंबर काउंट और लोगो URL को एक्सट्रैक्ट और फॉर्मेट किया जाता है।
5. **Deduplication & Ranking:**
   - डुप्लीकेट प्रोफाइल्स हटाकर सबसे रिलेवेंट और एक्टिव चैनल्स व ग्रुप्स की लिस्ट JSON रिस्पॉन्स में दी जाती है।

---

## 🔬 3. इसमें कौन-कौन सी तकनीकें (Techniques) इस्तेमाल हो रही हैं?
- **Public Search Index Querying:** ग्लोबल वेब इंडेक्स से टेलीग्राम के पब्लिक यूआरएल को डिस्कवर करना।
- **Subscriber / Member Count Parsing:** स्ट्रिंग एक्सप्रेशंस (जैसे `15.2K members`, `1.2M subscribers`) को इंटीजर और फॉर्मेटेड टेक्स्ट में कन्वर्ट करना।
- **Channel vs Group Classifier:** URL स्ट्रक्चर और पेज मेटाडेटा के आधार पर चैनल और सुपरग्रुप में अंतर पहचानना।
- **Type Filtering:** पेलोड में `type: "channel"`, `type: "group"`, या `type: "all"` के आधार पर अलग-अलग या कंबाइंड रिजल्ट्स देना।

---

## 📥 4. हम क्या-क्या Payload पास कर सकते हैं? (Payload Parameters)

| पैरामीटर (Field) | प्रकार (Type) | ज़रूरी है? | डिफ़ॉल्ट | विकल्प (Allowed Values) / विवरण |
| :--- | :--- | :--- | :--- | :--- |
| `query` | `string` | **हाँ (Required)** | - | सर्च कीवर्ड या टॉपिक (उदा. `crypto trading`, `ai tools`, `fitness`) |
| `type` | `string` | नहीं (Optional) | `"all"` | किस प्रकार का रिजल्ट चाहिए: `"channel"`, `"group"`, या `"all"` |
| `limit` | `integer` | नहीं (Optional) | `10` | कितने अधिकतम रिजल्ट्स चाहिए (1 से 50) |

---

## 📋 5. Request Payload Examples

### 🔹 उदाहरण A: सभी चैनल्स और ग्रुप्स खोजना (All Types)
```json
{
  "query": "crypto signals",
  "type": "all",
  "limit": 5
}
```

### 🔹 उदाहरण B: सिर्फ पब्लिक चैनल्स खोजना (Only Channels)
```json
{
  "query": "artificial intelligence tools",
  "type": "channel",
  "limit": 10
}
```

### 🔹 उदाहरण C: सिर्फ कम्युनिटी डिस्कशन ग्रुप्स खोजना (Only Groups)
```json
{
  "query": "python developer community",
  "type": "group",
  "limit": 8
}
```

---

## 📤 6. Response Payload Example

```json
{
  "status": "success",
  "query": "crypto signals",
  "type": "all",
  "total_results": 2,
  "channels": [
    {
      "username": "cryptosignals_official",
      "title": "Crypto Signals & Market Analysis",
      "description": "Daily Bitcoin & Altcoin technical analysis, spot and futures signals.",
      "subscribers": 84500,
      "subscribers_str": "84.5K subscribers",
      "avatar_url": "https://cdn5.telesco.pe/file/crypto_avatar.jpg",
      "is_verified": true,
      "url": "https://t.me/cryptosignals_official"
    }
  ],
  "groups": [
    {
      "username": "crypto_traders_chat",
      "title": "Crypto Traders Global Group",
      "description": "Discussion community for active crypto and forex traders.",
      "members": 18300,
      "members_str": "18.3K members",
      "avatar_url": "https://cdn5.telesco.pe/file/group_avatar.jpg",
      "url": "https://t.me/crypto_traders_chat"
    }
  ]
}
```

---

## 💻 7. कोड उदाहरण (Code Examples)

### cURL
```bash
curl -X POST "http://localhost:8000/telegram/search" \
     -H "Content-Type: application/json" \
     -d '{
       "query": "ai startups",
       "type": "all",
       "limit": 5
     }'
```

### Python
```python
import requests

url = "http://localhost:8000/telegram/search"
payload = {
    "query": "amazon discount deals",
    "type": "channel",
    "limit": 5
}

response = requests.post(url, json=payload)
data = response.json()

print(f"सर्च कीवर्ड: '{data['query']}' | कुल मिले: {data['total_results']}")
for ch in data.get("channels", []):
    print(f"- {ch['title']} (@{ch['username']}) -> {ch['subscribers_str']}")
```

### JavaScript / Node.js
```javascript
const response = await fetch("http://localhost:8000/telegram/search", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    query: "web development",
    type: "channel",
    limit: 5
  })
});

const result = await response.json();
console.log("Search Results:", result);
```
