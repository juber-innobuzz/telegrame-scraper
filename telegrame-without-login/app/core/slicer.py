"""Slice Engine: Orchestrates on-demand extraction slices with zero redundant computation."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set
from app.core.extractor import BusinessExtractor
from app.models import ChannelInfo, MessageItem, ScrapeOptions


ALL_SUPPORTED_SLICES = {
    "info",
    "messages",
    "engagement",
    "media",
    "links",
    "hashtags",
    "mentions",
    "forwards",
    "leads",
    "websites",
    "social_links",
    "products",
    "services",
    "prices",
    "jobs",
    "locations",
    "entities",
    "keywords",
}


def build_flat_response_rows(
    target: str,
    channel_info: Optional[ChannelInfo],
    messages: List[MessageItem],
) -> List[Dict[str, Any]]:
    """Generate exact flat array format matching data.json / Apify tabular schema."""
    rows: List[Dict[str, Any]] = []

    # 1. Channel row
    ch_title = channel_info.title if channel_info else target
    ch_sub_str = channel_info.subscribers_str if channel_info else None
    
    rows.append({
        "ok": True,
        "rowType": "channel",
        "channel": (channel_info.username if channel_info else target),
        "channelTitle": ch_title,
        "channelUsername": (channel_info.username if channel_info else target),
        "channelDescription": (channel_info.description if channel_info else None),
        "subscribers": ch_sub_str,
        "photosCount": (channel_info.photos_count_str if channel_info else None),
        "videosCount": (channel_info.videos_count_str if channel_info else None),
        "linksCount": (channel_info.links_count_str if channel_info else None),
        "postsReturned": len(messages),
    })

    # 2. Post rows
    for m in messages:
        rows.append({
            "ok": True,
            "rowType": "post",
            "channel": m.channel_username or target,
            "messageId": m.id,
            "postUrl": m.url,
            "text": m.text,
            "date": m.date,
            "views": m.views or (m.engagement.views_str if m.engagement else None) or (f"{m.engagement.views}" if m.engagement and m.engagement.views else None),
            "author": m.author or ch_title,
            "hasMedia": m.has_media,
            "mediaType": m.media_type,
            "mediaUrl": m.media_url,
            "link": m.link,
            "channelTitle": m.channel_title or ch_title,
            "subscribers": ch_sub_str,
        })

    return rows


def build_response_slices(
    target: str,
    channel_info: Optional[ChannelInfo],
    messages: List[MessageItem],
    include: List[str],
    options: Optional[ScrapeOptions] = None,
) -> Dict[str, Any]:
    """Execute only the requested extractors and assemble the dynamic slice dictionary."""
    opts = options or ScrapeOptions()
    include_set: Set[str] = set(include)
    if "all" in include_set:
        include_set = ALL_SUPPORTED_SLICES.copy()

    # Populate channel info postsReturned
    if channel_info:
        channel_info.posts_returned = len(messages)
        channel_info.postsReturned = len(messages)

    response_payload: Dict[str, Any] = {
        "username": target,
        "requested": list(include_set),
    }

    # 1. Info Slice
    if "info" in include_set:
        response_payload["info"] = channel_info.model_dump() if channel_info else None

    # 2. Messages Slice
    if "messages" in include_set:
        response_payload["messages"] = [m.model_dump() for m in messages]

    # 3. Engagement Slice
    if "engagement" in include_set:
        response_payload["engagement"] = BusinessExtractor.extract_engagement_summary(messages)

    # 4. Media Slice
    if "media" in include_set:
        media_items = []
        for msg in messages:
            for item in msg.media:
                if opts.media_type != "all" and item.type != opts.media_type:
                    continue
                media_items.append({
                    "type": item.type,
                    "url": item.url,
                    "thumbnail": item.thumbnail,
                    "file_name": item.file_name,
                    "duration": item.duration,
                    "source_message_id": msg.id,
                    "date": msg.date,
                })
        response_payload["media"] = media_items

    # 5. Links Slice
    if "links" in include_set:
        response_payload["links"] = BusinessExtractor.extract_all_links(messages)

    # 6. Hashtags Slice
    if "hashtags" in include_set:
        all_hashtags = {}
        for msg in messages:
            for tag in msg.hashtags:
                all_hashtags[tag] = all_hashtags.get(tag, 0) + 1
        response_payload["hashtags"] = [{"tag": f"#{k}", "count": v} for k, v in all_hashtags.items()]

    # 7. Mentions Slice
    if "mentions" in include_set:
        all_mentions = {}
        for msg in messages:
            for mention in msg.mentions:
                all_mentions[mention] = all_mentions.get(mention, 0) + 1
        response_payload["mentions"] = [{"mention": f"@{k}", "count": v} for k, v in all_mentions.items()]

    # 8. Forwards Slice
    if "forwards" in include_set:
        fwd_list = []
        for msg in messages:
            if msg.is_forwarded:
                fwd_list.append({
                    "message_id": msg.id,
                    "source": msg.forward_from,
                    "date": msg.date,
                    "text_preview": (msg.text[:100] + "...") if msg.text and len(msg.text) > 100 else msg.text,
                })
        response_payload["forwards"] = fwd_list

    # 9. Leads Slice
    if "leads" in include_set:
        response_payload["leads"] = BusinessExtractor.extract_leads(
            messages,
            include_emails=opts.include_emails,
            include_phones=opts.include_phones,
        )

    # 10. Websites Slice
    if "websites" in include_set:
        response_payload["websites"] = BusinessExtractor.extract_websites(messages)

    # 11. Social Links Slice
    if "social_links" in include_set:
        response_payload["social_links"] = BusinessExtractor.extract_social_links(messages)

    # 12. Products Slice
    if "products" in include_set:
        response_payload["products"] = BusinessExtractor.extract_products(
            messages,
            custom_keywords=opts.product_keywords,
        )

    # 13. Services Slice
    if "services" in include_set:
        response_payload["services"] = BusinessExtractor.extract_services(messages)

    # 14. Prices Slice
    if "prices" in include_set:
        response_payload["prices"] = BusinessExtractor.extract_prices(
            messages,
            currency=opts.currency_hint,
        )

    # 15. Jobs Slice
    if "jobs" in include_set:
        response_payload["jobs"] = BusinessExtractor.extract_jobs(messages)

    # 16. Locations Slice
    if "locations" in include_set:
        response_payload["locations"] = BusinessExtractor.extract_locations(messages)

    # 17. Entities Slice
    if "entities" in include_set:
        response_payload["entities"] = BusinessExtractor.extract_entities(
            messages,
            entity_type=opts.entity_type,
        )

    # 18. Keywords Slice
    if "keywords" in include_set:
        response_payload["keywords"] = BusinessExtractor.extract_keywords(
            messages,
            top_n=opts.keywords_top_n,
        )

    return response_payload
