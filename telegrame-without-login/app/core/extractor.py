"""Business Intelligence, NLP and Regex Extraction Engine for Telegram Content."""

from __future__ import annotations

import re
from collections import Counter
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urlparse

from app.models import MessageItem

# Common social domain patterns
SOCIAL_PATTERNS = {
    "instagram": re.compile(r"https?://(?:www\.)?instagram\.com/[a-zA-Z0-9_\.]+", re.I),
    "facebook": re.compile(r"https?://(?:www\.)?facebook\.com/[a-zA-Z0-9_\.]+", re.I),
    "linkedin": re.compile(r"https?://(?:www\.)?linkedin\.com/(?:in|company)/[a-zA-Z0-9_\-]+", re.I),
    "youtube": re.compile(r"https?://(?:www\.)?(?:youtube\.com/(?:c/|channel/|user/|@)?|youtu\.be/)[a-zA-Z0-9_\-]+", re.I),
    "x": re.compile(r"https?://(?:www\.)?(?:twitter\.com|x\.com)/[a-zA-Z0-9_]+", re.I),
    "tiktok": re.compile(r"https?://(?:www\.)?tiktok\.com/@[a-zA-Z0-9_\.]+", re.I),
}

# Common currency symbols & codes
CURRENCY_REGEX = re.compile(
    r"(?:(\$|€|£|¥|₹|₽|₩|TON|USDT|USDC|BTC|ETH|USD|EUR|GBP|INR|RUB|AED)\s*([0-9]+(?:[\.,][0-9]{1,4})?))|"
    r"(?:([0-9]+(?:[\.,][0-9]{1,4})?)\s*(\$|€|£|¥|₹|₽|₩|TON|USDT|USDC|BTC|ETH|USD|EUR|GBP|INR|RUB|AED))",
    re.I,
)

# Job posting indicators & keywords
JOB_ROLES = [
    "developer", "engineer", "designer", "manager", "architect", "lead", "specialist",
    "analyst", "consultant", "director", "marketer", "copywriter", "recruiter",
    "administrator", "assistant", "trader", "accountant", "moderator", "operator"
]

JOB_TYPES = {
    "remote": re.compile(r"\b(remote|work from home|wfh|telecommute)\b", re.I),
    "full_time": re.compile(r"\b(full[- ]?time|permanent)\b", re.I),
    "part_time": re.compile(r"\b(part[- ]?time)\b", re.I),
    "contract": re.compile(r"\b(contract|freelance|bounty|project[- ]based)\b", re.I),
    "internship": re.compile(r"\b(intern|internship|trainee)\b", re.I),
}

# Location reference list (Sample top tech hubs / global business cities & countries)
LOCATIONS = [
    "United States", "USA", "UK", "United Kingdom", "Germany", "France", "Canada", "Australia",
    "India", "Singapore", "UAE", "Dubai", "Japan", "Switzerland", "Netherlands", "Estonia",
    "Cyprus", "Hong Kong", "Brazil", "New York", "San Francisco", "London", "Berlin",
    "Paris", "Toronto", "Sydney", "Bangalore", "Mumbai", "Tokyo", "Zurich", "Amsterdam"
]


class BusinessExtractor:
    """Extracts structured business intelligence from Telegram messages."""

    @staticmethod
    def extract_all_links(messages: List[MessageItem], domain_filter: Optional[str] = None) -> List[str]:
        """Extract and optionally filter URLs from posts."""
        all_links = []
        for msg in messages:
            all_links.extend(msg.links)
        
        all_links = list(dict.fromkeys(all_links))
        if domain_filter:
            clean_dom = domain_filter.lower().strip()
            all_links = [l for l in all_links if clean_dom in urlparse(l).netloc.lower()]
        return all_links

    @staticmethod
    def extract_websites(messages: List[MessageItem]) -> List[Dict[str, Any]]:
        """Extract commercial / business website domains from links."""
        excluded_domains = {
            "t.me", "telegram.me", "instagram.com", "facebook.com", "twitter.com",
            "x.com", "linkedin.com", "youtube.com", "youtu.be", "tiktok.com",
            "google.com", "apple.com"
        }
        
        websites = []
        seen = set()
        for msg in messages:
            for link in msg.links:
                try:
                    parsed = urlparse(link)
                    domain = parsed.netloc.lower()
                    if not domain or any(ex in domain for ex in excluded_domains):
                        continue
                    if domain not in seen:
                        seen.add(domain)
                        websites.append({
                            "url": link,
                            "domain": domain,
                            "source_message_id": msg.id,
                            "date": msg.date,
                        })
                except Exception:
                    continue
        return websites

    @staticmethod
    def extract_social_links(messages: List[MessageItem], platform: str = "all") -> Dict[str, List[str]]:
        """Extract and categorize social media links."""
        results: Dict[str, List[str]] = {p: [] for p in SOCIAL_PATTERNS}
        target_platforms = list(SOCIAL_PATTERNS.keys()) if platform.lower() == "all" else [platform.lower()]

        for msg in messages:
            for link in msg.links:
                for plat in target_platforms:
                    pat = SOCIAL_PATTERNS.get(plat)
                    if pat and pat.search(link):
                        if link not in results[plat]:
                            results[plat].append(link)

        if platform.lower() != "all" and platform.lower() in results:
            return {platform.lower(): results[platform.lower()]}
        return results

    @staticmethod
    def extract_jobs(
        messages: List[MessageItem],
        keyword: Optional[str] = None,
        location: Optional[str] = None,
        job_type: str = "all",
    ) -> List[Dict[str, Any]]:
        """Extract job listings, roles, and compensation from messages."""
        jobs = []
        kw_re = re.compile(rf"\b{re.escape(keyword)}\b", re.I) if keyword else None
        loc_re = re.compile(rf"\b{re.escape(location)}\b", re.I) if location else None

        for msg in messages:
            if not msg.text:
                continue
            text = msg.text

            # Filter keyword/location if requested
            if kw_re and not kw_re.search(text):
                continue
            if loc_re and not loc_re.search(text):
                continue

            # Check if text looks like a genuine job posting
            has_hiring = bool(re.search(r"\b(hiring|looking for|vacancy|job|we need|position|career|apply|wanted|join our team|salary|compensation)\b", text, re.I))
            matched_roles = []
            for role in JOB_ROLES:
                # Avoid "AI Assistant" matching as a job role
                if role == "assistant" and re.search(r"\bai assistant\b", text, re.I):
                    continue
                if re.search(rf"\b{role}\b", text, re.I):
                    matched_roles.append(role)
            
            # Only consider as job if hiring context is present or explicit tech role is found
            if has_hiring and matched_roles:
                # Detect job types
                detected_types = []
                for j_type, pat in JOB_TYPES.items():
                    if pat.search(text):
                        detected_types.append(j_type)
                if not detected_types:
                    detected_types.append("full_time")

                # Filter by job_type if specified
                if job_type != "all" and job_type not in detected_types:
                    continue

                # Extract price/salary if mentioned
                price_match = CURRENCY_REGEX.search(text)
                salary = price_match.group(0) if price_match else None

                jobs.append({
                    "message_id": msg.id,
                    "date": msg.date,
                    "roles": matched_roles,
                    "job_types": detected_types,
                    "salary": salary,
                    "preview": text[:200] + ("..." if len(text) > 200 else ""),
                    "full_text": text,
                    "url": msg.url,
                })
        return jobs

    @staticmethod
    def extract_prices(
        messages: List[MessageItem],
        keyword: Optional[str] = None,
        currency: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Extract prices, currencies, and commercial figures from posts."""
        prices = []
        kw_re = re.compile(rf"\b{re.escape(keyword)}\b", re.I) if keyword else None
        curr_upper = currency.upper().strip() if currency else None

        for msg in messages:
            if not msg.text:
                continue
            text = msg.text

            if kw_re and not kw_re.search(text):
                continue

            for match in CURRENCY_REGEX.finditer(text):
                raw = match.group(0).strip()
                c1, a1, a2, c2 = match.groups()
                curr_symbol = (c1 or c2 or "").upper()
                amount_str = a1 or a2 or "0"

                if curr_upper and curr_upper not in curr_symbol and curr_symbol not in curr_upper:
                    continue

                prices.append({
                    "raw_price": raw,
                    "currency": curr_symbol,
                    "amount": amount_str,
                    "message_id": msg.id,
                    "date": msg.date,
                    "context": text[max(0, match.start() - 40): min(len(text), match.end() + 40)].strip(),
                    "url": msg.url,
                })
        return prices

    @staticmethod
    def extract_products_and_services(
        messages: List[MessageItem],
        keyword: Optional[str] = None,
        category: Optional[str] = None,
        extract_type: str = "product",
    ) -> List[Dict[str, Any]]:
        """Extract product or service offerings with embedded price details and links."""
        results = []
        kw_re = re.compile(rf"\b{re.escape(keyword)}\b", re.I) if keyword else None

        service_indicators = re.compile(r"\b(service|services|consulting|development|audit|design|hosting|marketing|subscription|bot|management)\b", re.I)
        product_indicators = re.compile(r"\b(product|release|version|launch|token|app|software|device|course|guide|item|buy|sale|discount|deal|loot|mrp|price)\b", re.I)

        for msg in messages:
            if not msg.text:
                continue
            text = msg.text

            if kw_re and not kw_re.search(text):
                continue

            target_pattern = service_indicators if extract_type == "service" else product_indicators
            match = target_pattern.search(text)
            if match or (keyword and kw_re.search(text)):
                # Extract all prices associated with this product/message
                msg_prices = []
                for p_match in CURRENCY_REGEX.finditer(text):
                    raw = p_match.group(0).strip()
                    c1, a1, a2, c2 = p_match.groups()
                    curr_symbol = (c1 or c2 or "").upper()
                    amount_str = a1 or a2 or "0"
                    msg_prices.append({
                        "raw_price": raw,
                        "currency": curr_symbol,
                        "amount": amount_str,
                    })

                # Extract specific price fields: deal price, MRP, discount info
                deal_price_m = re.search(r"(?:deal price|price|at|for|only)\s*[:\s]*([₹\$€£¥₽₩][0-9\.,]+|[0-9\.,]+\s*[₹\$€£¥₽₩]|(?:TON|USDT|BTC|ETH|USD|EUR)\s*[0-9\.,]+|[0-9\.,]+\s*(?:TON|USDT|BTC|ETH|USD|EUR))", text, re.I)
                mrp_m = re.search(r"mrp\s*[:\s]*([₹\$€£¥₽₩][0-9\.,]+|[0-9\.,]+\s*[₹\$€£¥₽₩]|(?:TON|USDT|BTC|ETH|USD|EUR)\s*[0-9\.,]+|[0-9\.,]+\s*(?:TON|USDT|BTC|ETH|USD|EUR))", text, re.I)
                discount_m = re.search(r"(?:apply|coupon|discount|off|save)\s*[:\s]*([0-9]+%|[₹\$€£¥₽₩][0-9\.,]+|[0-9\.,]+\s*[₹\$€£¥₽₩]|(?:TON|USDT|BTC|ETH|USD|EUR)\s*[0-9\.,]+)", text, re.I)

                deal_price = deal_price_m.group(1).strip() if deal_price_m else (msg_prices[0]["raw_price"] if msg_prices else None)
                mrp = mrp_m.group(1).strip() if mrp_m else None
                discount_info = discount_m.group(0).strip() if discount_m else None
                primary_currency = msg_prices[0]["currency"] if msg_prices else None

                # Clean product title / name from the first meaningful line
                first_line = text.split("\n")[0]
                clean_title = re.sub(r"^[^\w]+", "", first_line).strip()
                if len(clean_title) < 3 and len(text.split("\n")) > 1:
                    clean_title = re.sub(r"^[^\w]+", "", text.split("\n")[1]).strip()

                # Collect media details attached to this message
                media_items = [
                    {
                        "type": item.type,
                        "url": item.url,
                        "thumbnail": item.thumbnail,
                        "file_name": item.file_name,
                        "duration": item.duration,
                    }
                    for item in msg.media
                    if item.url
                ]

                results.append({
                    "name": clean_title if clean_title else f"{extract_type.title()} #{msg.id}",
                    "type": extract_type,
                    "category": category or "general",
                    "keyword_matched": match.group(0) if match else (keyword or extract_type),
                    "price_details": {
                        "deal_price": deal_price,
                        "mrp": mrp,
                        "discount_info": discount_info,
                        "currency": primary_currency,
                        "all_prices": msg_prices,
                    },
                    "buy_links": msg.links,
                    "media": media_items,
                    "message_id": msg.id,
                    "date": msg.date,
                    "text_preview": text[:200] + ("..." if len(text) > 200 else ""),
                    "url": msg.url,
                })
        return results

    @staticmethod
    def extract_products(messages: List[MessageItem], custom_keywords: Optional[str] = None) -> List[Dict[str, Any]]:
        """Convenience wrapper for extracting products."""
        return BusinessExtractor.extract_products_and_services(messages, keyword=custom_keywords, extract_type="product")

    @staticmethod
    def extract_services(messages: List[MessageItem], custom_keywords: Optional[str] = None) -> List[Dict[str, Any]]:
        """Convenience wrapper for extracting services."""
        return BusinessExtractor.extract_products_and_services(messages, keyword=custom_keywords, extract_type="service")

    @staticmethod
    def extract_entities(messages: List[MessageItem], entity_type: str = "all", keyword: Optional[str] = None) -> List[Dict[str, Any]]:
        """Convenience wrapper for extracting entities and brand mentions."""
        return BusinessExtractor.extract_businesses_and_entities(messages, entity_type=entity_type, keyword=keyword)

    @staticmethod
    def extract_locations(
        messages: List[MessageItem],
        country: Optional[str] = None,
        city: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Extract geographical and business location mentions."""
        locations = []
        target_locations = [country or city] if (country or city) else LOCATIONS

        for msg in messages:
            if not msg.text:
                continue
            text = msg.text

            for loc in target_locations:
                if re.search(rf"\b{re.escape(loc)}\b", text, re.I):
                    locations.append({
                        "location": loc,
                        "message_id": msg.id,
                        "date": msg.date,
                        "context": text[:150],
                        "url": msg.url,
                    })
        return locations

    @staticmethod
    def extract_businesses_and_entities(
        messages: List[MessageItem],
        entity_type: str = "all",
        keyword: Optional[str] = None,
        industry: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Extract named entities, corporate mentions, and brand names."""
        entities = []
        seen = set()

        # Regex for capitalized entity names or company indicators
        biz_pattern = re.compile(r"\b([A-Z][a-zA-Z0-9_\s&]{2,25}(?:Inc|LLC|Corp|Ltd|Technologies|Group|Capital|Labs|Ventures|Studio|Network|Foundation))\b")

        for msg in messages:
            if not msg.text:
                continue
            text = msg.text

            if keyword and keyword.lower() not in text.lower():
                continue

            # Extract business corporations
            for match in biz_pattern.finditer(text):
                name = match.group(1).strip()
                if name not in seen:
                    seen.add(name)
                    entities.append({
                        "name": name,
                        "type": "business",
                        "industry": industry or "Technology / Business",
                        "source_message_id": msg.id,
                        "date": msg.date,
                    })

            # Extract mentions (@brand) as entities
            for mention in msg.mentions:
                if mention not in seen:
                    seen.add(mention)
                    entities.append({
                        "name": f"@{mention}",
                        "type": "brand",
                        "industry": industry or "Telegram Channel/Brand",
                        "source_message_id": msg.id,
                        "date": msg.date,
                    })

        if entity_type != "all":
            entities = [e for e in entities if e.get("type") == entity_type]
        return entities

    @staticmethod
    def extract_keywords_frequency(messages: List[MessageItem], limit: int = 100) -> List[Dict[str, Any]]:
        """Extract frequent keywords and n-grams from messages."""
        stopwords = {
            "the", "and", "to", "of", "a", "in", "is", "that", "for", "it", "as", "was",
            "with", "on", "are", "by", "this", "be", "at", "from", "or", "an", "your",
            "we", "you", "our", "all", "can", "will", "more", "https", "http", "t.me"
        }
        words = []
        for msg in messages:
            if msg.text:
                clean_words = re.findall(r"\b[a-zA-Z]{3,20}\b", msg.text.lower())
                words.extend([w for w in clean_words if w not in stopwords])

        counter = Counter(words)
        return [{"keyword": k, "frequency": v} for k, v in counter.most_common(limit)]

    @staticmethod
    def extract_keywords(messages: List[MessageItem], top_n: int = 50) -> List[Dict[str, Any]]:
        """Convenience wrapper for extracting top keywords."""
        return BusinessExtractor.extract_keywords_frequency(messages, limit=top_n)

    @staticmethod
    def extract_forwards(messages: List[MessageItem]) -> List[Dict[str, Any]]:
        """Extract posts that were forwarded from other channels or users."""
        forwards = []
        for msg in messages:
            if msg.is_forwarded or msg.forward_from:
                forwards.append({
                    "message_id": msg.id,
                    "forward_from": msg.forward_from,
                    "date": msg.date,
                    "text_preview": msg.text[:200] if msg.text else "",
                    "url": msg.url,
                })
        return forwards

    @staticmethod
    def extract_engagement_summary(messages: List[MessageItem]) -> Dict[str, Any]:
        """Compute overall public engagement summary for a collection of posts."""
        total_views = sum(m.engagement.views for m in messages)
        total_reactions = sum(m.engagement.reactions_count for m in messages)
        avg_views = round(total_views / max(1, len(messages)), 2)

        reactions_breakdown: Dict[str, int] = {}
        for msg in messages:
            for emoji, count in msg.engagement.reactions_breakdown.items():
                reactions_breakdown[emoji] = reactions_breakdown.get(emoji, 0) + count

        return {
            "total_posts_analyzed": len(messages),
            "total_views": total_views,
            "average_views_per_post": avg_views,
            "total_reactions": total_reactions,
            "reactions_breakdown": reactions_breakdown,
        }

    @staticmethod
    def extract_leads(
        messages: List[MessageItem],
        include_emails: bool = True,
        include_phones: bool = True,
        unique: bool = True,
    ) -> Dict[str, Any]:
        """Extract actionable B2B contacts and lead generation artifacts."""
        email_re = re.compile(r"\b[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+\b")
        phone_re = re.compile(r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}\b")
        
        emails = []
        phones = []
        whatsapp = []
        telegram_contacts = []

        seen_emails = set()
        seen_phones = set()
        seen_wa = set()
        seen_tg = set()

        for msg in messages:
            if msg.text:
                if include_emails:
                    for em in email_re.findall(msg.text):
                        em_clean = em.strip().lower()
                        if not unique or em_clean not in seen_emails:
                            seen_emails.add(em_clean)
                            emails.append({"email": em_clean, "source_message_id": msg.id, "date": msg.date})

                if include_phones:
                    for ph in phone_re.findall(msg.text):
                        digits = re.sub(r"[^\d+]", "", ph)
                        if len(digits) >= 9 and len(digits) <= 15 and not digits.startswith("202"):
                            if not unique or digits not in seen_phones:
                                seen_phones.add(digits)
                                phones.append({"phone": ph.strip(), "source_message_id": msg.id, "date": msg.date})

            for link in msg.links:
                if "wa.me" in link or "whatsapp.com" in link:
                    if not unique or link not in seen_wa:
                        seen_wa.add(link)
                        whatsapp.append({"url": link, "source_message_id": msg.id, "date": msg.date})

            for m in msg.mentions:
                m_clean = m.strip()
                if m_clean.lower() not in ["channel", "admin", "join", "group", "bot"]:
                    if not unique or m_clean.lower() not in seen_tg:
                        seen_tg.add(m_clean.lower())
                        telegram_contacts.append({
                            "handle": f"@{m_clean}",
                            "url": f"https://t.me/{m_clean}",
                            "source_message_id": msg.id,
                            "date": msg.date,
                        })

        return {
            "total_leads_found": len(emails) + len(phones) + len(whatsapp) + len(telegram_contacts),
            "emails": emails,
            "phones": phones,
            "whatsapp": whatsapp,
            "telegram_contacts": telegram_contacts,
        }
