# 🎯 Endpoint 2: `POST /telegram/post` (सिंगल पोस्ट स्क्रैपर)

## 📌 1. यह API क्या काम करती है? (Overview)
यह एंडपॉइंट किसी एक खास टेलीग्राम पोस्ट या मैसेज (जैसे: `https://t.me/durov/123`) का इन-डेप्थ विश्लेषण (In-depth Analysis) करता है। इससे उस मैसेज का टेक्स्ट, मीडिया, व्यूज, रिएक्शन्स, फॉरवर्ड सोर्स, कीमतें, प्रोडक्ट्स और कॉन्टैक्ट लीड्स निकाली जाती हैं।

---

## ⚙️ 2. यह API अंदर से कैसे काम करती है? (Working Mechanism)
1. **Target Parsing (`parse_post_target`):**
   - यूजर या तो डायरेक्ट पोस्ट का URL दे सकता है (जैसे `https://t.me/deals/679569` या `https://t.me/s/deals/679569`),
   - या फिर अलग से `username` और `message_id` दे सकता है।
2. **Post Widget Embed Scrape (`build_message_embed_url`):**
   - API टेलीग्राम के ऑफिशियल विजेट एम्बेड URL `https://t.me/<username>/<message_id>?embed=1` से उस पोस्ट का डायरेक्ट HTML फेच करती है।
3. **HTML DOM Parser (`TelegramParser.parse_messages`):**
   - मैसेज का टेक्स्ट, टाइमस्टैम्प, व्यूज (views count), रिएक्शन्स (reaction emojis + counts), अटैचमेंट्स (images, videos, documents), हैशटैग्स और एक्सटर्नल लिंक्स पार्स किए जाते हैं।
4. **Fallback Crawler Mechanism:**
   - अगर किसी कारणवश टेलीग्राम एम्बेड विजेट रेंडर नहीं करता, तो API ऑटोमैटिक बैकअप के रूप में चैनल हिस्ट्री क्रॉलर का इस्तेमाल करके `before=<id+1>` के साथ उस खास मैसेज को फेच कर लेती है।
5. **Dynamic Slices Construction (`build_response_slices`):**
   - यूजर के `include` पैरामीटर के हिसाब से Derived Intelligence (जैसे `products`, `prices`, `leads`, `media`) जनरेट की जाती है।

---

## 🔬 3. इसमें कौन-कौन सी तकनीकें (Techniques) इस्तेमाल हो रही हैं?
- **Telegram Widget Embed Engine:** बिना किसी लॉगिन के टेलीग्राम के ऑफिशियल पब्लिक एम्बेड प्रीव्यू फ्रेम का इस्तेमाल करता है।
- **Resilient Fallback Strategy:** अगर डायरेक्ट एम्बेड ब्लॉक या फेल हो, तो चैनल हिस्ट्री क्रॉलिंग से ग्रेसफुल रिकवरी करता है।
- **Media Link Extraction:** फोटो, वीडियो, स्टिकर्स, और फाइल्स के हाई-रिज़ॉल्यूशन CDN URL निकालता है (`https://cdn5.telesco.pe/file/...`)।
- **Rich Engagement Analytics:** व्यूज के साथ-साथ हर रिएक्शन इमोजी (🔥, 👍, ❤️, 👏, 🎉) का अलग-अलग ब्रेकडाउन काउंट करता है।

---

## 📥 4. हम क्या-क्या Payload पास कर सकते हैं? (Payload Parameters)

| पैरामीटर (Field) | प्रकार (Type) | ज़रूरी है? | डिफ़ॉल्ट | विवरण (Description) |
| :--- | :--- | :--- | :--- | :--- |
| `url` | `string` | **हाँ** (या username+message_id) | `null` | पोस्ट का पूरा URL (उदा. `https://t.me/deals/679569` या `t.me/durov/1`) |
| `username` | `string` | वैकल्पिक | `null` | चैनल यूजरनेम (अगर `url` न दिया हो) |
| `message_id` | `integer` | वैकल्पिक | `null` | मैसेज ID नंबर (अगर `url` न दिया हो) |
| `include` | `array[string]` | नहीं (Optional) | `["messages"]` | क्या-क्या डेटा चाहिए (उदा. `["messages", "products", "prices", "media", "leads", "links"]` या `["all"]`) |
| `options` | `object` | नहीं (Optional) | `{}` | एक्सट्रैक्टर ऑप्शन्स (`unique_links`, `include_emails`, आदि) |

---

## 📋 5. Request Payload Examples

### 🔹 उदाहरण A: डायरेक्ट URL से प्रोडक्ट और मीडिया निकालना
```json
{
  "url": "https://t.me/deals/679569",
  "include": [
    "messages",
    "products",
    "prices",
    "media",
    "leads",
    "links"
  ]
}
```

### 🔹 उदाहरण B: Username और Message ID पास करके स्क्रैप करना
```json
{
  "username": "durov",
  "message_id": 150,
  "include": [
    "messages",
    "engagement",
    "links",
    "media"
  ]
}
```

---

## 📤 6. Response Payload Example

```json
{
  "status": "success",
  "url": "https://t.me/deals/679569",
  "username": "deals",
  "message_id": 679569,
  "requested": ["messages", "products", "prices", "media", "leads"],
  "messages": [
    {
      "id": 679569,
      "channel_username": "deals",
      "url": "https://t.me/deals/679569",
      "date": "2026-09-08T08:36:03+00:00",
      "text": "JaipurCrafts Wooden Key Holder\nDeal Price ₹284\nMRP ₹1,999 (85% OFF)\n🛒 Buy Now: https://amazon.in/dp/B07JKXSHY2",
      "is_forwarded": false,
      "forward_from": null,
      "engagement": {
        "views": 4820,
        "forwards": 12,
        "reactions_count": 34,
        "reactions_breakdown": {
          "🔥": 24,
          "👍": 10
        }
      },
      "media": [
        {
          "type": "image",
          "url": "https://cdn5.telesco.pe/file/sample_image.jpg",
          "thumbnail": null,
          "file_name": null,
          "duration": null
        }
      ],
      "links": [
        "https://amazon.in/dp/B07JKXSHY2"
      ],
      "hashtags": [],
      "mentions": []
    }
  ],
  "products": [
    {
      "name": "JaipurCrafts Wooden Key Holder",
      "type": "product",
      "category": "general",
      "keyword_matched": "deal",
      "price_details": {
        "deal_price": "₹284",
        "mrp": "₹1,999",
        "discount_info": "85% OFF",
        "currency": "₹",
        "all_prices": [
          { "raw_price": "₹284", "currency": "₹", "amount": "284" },
          { "raw_price": "₹1,999", "currency": "₹", "amount": "1,999" }
        ]
      },
      "buy_links": ["https://amazon.in/dp/B07JKXSHY2"],
      "media": [
        { "type": "image", "url": "https://cdn5.telesco.pe/file/sample_image.jpg", "thumbnail": null, "file_name": null, "duration": null }
      ],
      "message_id": 679569,
      "date": "2026-09-08T08:36:03+00:00",
      "url": "https://t.me/deals/679569"
    }
  ],
  "prices": [
    {
      "raw_price": "₹284",
      "currency": "₹",
      "amount": "284",
      "message_id": 679569,
      "date": "2026-09-08T08:36:03+00:00",
      "context": "Deal Price ₹284 MRP ₹1,999 (85% OFF)",
      "url": "https://t.me/deals/679569"
    }
  ],
  "media": [
    {
      "type": "image",
      "url": "https://cdn5.telesco.pe/file/sample_image.jpg",
      "thumbnail": null,
      "file_name": null,
      "duration": null,
      "source_message_id": 679569,
      "date": "2026-09-08T08:36:03+00:00"
    }
  ],
  "leads": {
    "total_leads_found": 0,
    "emails": [],
    "phones": [],
    "whatsapp": [],
    "telegram_contacts": []
  }
}
```

---

## 💻 7. कोड उदाहरण (Code Examples)

### cURL
```bash
curl -X POST "http://localhost:8000/telegram/post" \
     -H "Content-Type: application/json" \
     -d '{
       "url": "https://t.me/deals/679569",
       "include": ["messages", "products", "prices", "media"]
     }'
```

### Python
```python
import requests

url = "http://localhost:8000/telegram/post"
payload = {
    "url": "https://t.me/deals/679569",
    "include": ["messages", "products", "prices", "media", "engagement"]
}

response = requests.post(url, json=payload)
data = response.json()

print(f"पोस्ट URL: {data['url']}")
if data.get("products"):
    prod = data["products"][0]
    print(f"प्रोडक्ट: {prod['name']}")
    print(f"डील प्राइस: {prod['price_details']['deal_price']}")
```

### JavaScript / Node.js
```javascript
const response = await fetch("http://localhost:8000/telegram/post", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    url: "https://t.me/deals/679569",
    include: ["messages", "products", "prices", "media"]
  })
});

const result = await response.json();
console.log("Post Analysis:", result);
```
