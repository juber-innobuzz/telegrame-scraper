"""DOM and OpenGraph Parser for Telegram Web Previews and Embed Widgets."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from app.models import (
    ChannelInfo,
    EngagementMetrics,
    GroupInfo,
    MediaItem,
    MessageItem,
)


def parse_numeric_shorthand(text: Optional[str]) -> int:
    """Parse subscriber or view counts formatted with K, M, B, spaces, or words.
    
    Examples:
        - '12.5Ksubscribers' -> 12500
        - '1.2K' -> 1200
        - '10.8Msubscribers' -> 10800000
        - '96 378 members, 4 152 online' -> 96378
        - '12 345' -> 12345
        - '500' -> 500
    """
    if not text:
        return 0

    clean = text.strip().replace("\xa0", " ")
    
    # 1. Check for multiplier shorthand (e.g. 10.8M, 12.5K, 2.5B, 12.5Ksubscribers)
    match_mult = re.search(r"([\d\.]+)\s*([KMBkmb])(?:subscribers|members|views|online|\b|\s|$|,)", clean, re.I)
    if match_mult:
        try:
            val = float(match_mult.group(1))
            s = match_mult.group(2).upper()
            if s == "K":
                return int(val * 1_000)
            elif s == "M":
                return int(val * 1_000_000)
            elif s == "B":
                return int(val * 1_000_000_000)
        except ValueError:
            pass

    # 2. Extract leading number group from the first clause before commas
    first_clause = clean.split(",")[0]
    digits_part = re.sub(r"\b(members?|subscribers?|views?|online|reactions?)\b", "", first_clause, flags=re.I).strip()
    first_num = re.search(r"(\d[\d\s]*)", digits_part)
    if first_num:
        nc = first_num.group(1).replace(" ", "")
        if nc.isdigit():
            return int(nc)

    return 0


def extract_links_from_text(text: str) -> List[str]:
    """Extract full HTTP/HTTPS URLs from raw text."""
    if not text:
        return []
    url_pattern = re.compile(r"https?://[^\s<>\"')]+", re.IGNORECASE)
    return list(dict.fromkeys(url_pattern.findall(text)))


def extract_hashtags_from_text(text: str) -> List[str]:
    """Extract hashtags (#tag) from text."""
    if not text:
        return []
    hashtag_pattern = re.compile(r"#([a-zA-Z0-9_\u0080-\uffff]+)")
    return list(dict.fromkeys(hashtag_pattern.findall(text)))


def extract_mentions_from_text(text: str) -> List[str]:
    """Extract user or channel @mentions from text."""
    if not text:
        return []
    mention_pattern = re.compile(r"@([a-zA-Z0-9_]{3,32})")
    return list(dict.fromkeys(mention_pattern.findall(text)))


def clean_telegram_message_text(text_el: Any) -> Optional[str]:
    """Cleanly extract text from Telegram message element preserving linebreaks and natural word spacing."""
    if not text_el:
        return None
    import copy
    el = copy.copy(text_el)
    
    # Replace explicit linebreaks (<br>, <p>, <div>) with newlines
    for br in el.find_all(["br", "p", "div"]):
        br.replace_with(f"\n{br.get_text()}\n" if br.name in ["p", "div"] else "\n")
    
    raw = el.get_text()
    
    # Clean whitespace line by line
    raw_lines = raw.split("\n")
    cleaned_lines = []
    prev_blank = False
    for line in raw_lines:
        s = line.strip()
        if not s:
            if not prev_blank and cleaned_lines:
                cleaned_lines.append("")
                prev_blank = True
        else:
            cleaned_lines.append(s)
            prev_blank = False
            
    return "\n".join(cleaned_lines).strip() or None


class TelegramParser:
    """Parser for Telegram HTML structures (channels, groups, and individual messages)."""

    @staticmethod
    def parse_channel_info(html: str, target_username: str) -> ChannelInfo:
        """Extract metadata for a public channel including media asset counters."""
        soup = BeautifulSoup(html, "html.parser")
        
        # 1. Title
        title = None
        title_el = (
            soup.find("div", class_="tgme_channel_info_header_title")
            or soup.find("div", class_="tgme_page_title")
            or soup.find("span", dir="auto")
        )
        if title_el:
            title = title_el.get_text(strip=True)
        if not title:
            og_title = soup.find("meta", property="og:title")
            title = og_title["content"].strip() if og_title and og_title.get("content") else target_username

        # 2. Description
        desc = None
        desc_el = (
            soup.find("div", class_="tgme_channel_info_description")
            or soup.find("div", class_="tgme_page_description")
        )
        if desc_el:
            desc = desc_el.get_text(separator="\n", strip=True)
        if not desc:
            og_desc = soup.find("meta", property="og:description")
            if og_desc and og_desc.get("content"):
                desc = og_desc["content"].strip()

        # 3. Subscribers and Media Counters (photos, videos, links, files)
        subscribers = None
        subscribers_str = None
        photos_count = None
        photos_count_str = None
        videos_count = None
        videos_count_str = None
        links_count = None
        links_count_str = None
        files_count = None
        files_count_str = None
        audios_count = None
        audios_count_str = None

        counter_el = (
            soup.find("div", class_="tgme_channel_info_counter")
            or soup.find("div", class_="tgme_page_extra")
        )
        if counter_el:
            subscribers_str = counter_el.get_text(strip=True)
            subscribers = parse_numeric_shorthand(subscribers_str)

        # Parse extra counter items across header
        header_text = soup.get_text(separator=" ", strip=True)
        
        # Photos
        p_match = re.search(r"([\d\.,\s]+[KMBkmb]?)\s*photos?", header_text, re.I)
        if p_match:
            photos_count_str = p_match.group(1).strip()
            photos_count = parse_numeric_shorthand(photos_count_str)

        # Videos
        v_match = re.search(r"([\d\.,\s]+[KMBkmb]?)\s*videos?", header_text, re.I)
        if v_match:
            videos_count_str = v_match.group(1).strip()
            videos_count = parse_numeric_shorthand(videos_count_str)

        # Links
        l_match = re.search(r"([\d\.,\s]+[KMBkmb]?)\s*links?", header_text, re.I)
        if l_match:
            links_count_str = l_match.group(1).strip()
            links_count = parse_numeric_shorthand(links_count_str)

        # Files
        f_match = re.search(r"([\d\.,\s]+[KMBkmb]?)\s*files?", header_text, re.I)
        if f_match:
            files_count_str = f_match.group(1).strip()
            files_count = parse_numeric_shorthand(files_count_str)

        # Audios
        a_match = re.search(r"([\d\.,\s]+[KMBkmb]?)\s*(?:audios?|audio files?)", header_text, re.I)
        if a_match:
            audios_count_str = a_match.group(1).strip()
            audios_count = parse_numeric_shorthand(audios_count_str)

        # 4. Avatar URL
        avatar_url = None
        avatar_el = soup.find("img", class_="tgme_page_photo_image")
        if avatar_el and avatar_el.get("src"):
            avatar_url = avatar_el["src"]
        if not avatar_url:
            og_image = soup.find("meta", property="og:image")
            if og_image and og_image.get("content"):
                avatar_url = og_image["content"]

        # 5. Verified
        is_verified = bool(
            soup.find("i", class_=re.compile(r"verified-icon|tgme_verified_badge"))
        )

        return ChannelInfo(
            username=target_username,
            title=title or target_username,
            description=desc,
            subscribers=subscribers,
            subscribers_str=subscribers_str,
            photos_count=photos_count,
            photos_count_str=photos_count_str,
            videos_count=videos_count,
            videos_count_str=videos_count_str,
            links_count=links_count,
            links_count_str=links_count_str,
            files_count=files_count,
            files_count_str=files_count_str,
            audios_count=audios_count,
            audios_count_str=audios_count_str,
            avatar_url=avatar_url,
            is_verified=is_verified,
            url=f"https://t.me/{target_username}",
        )

    @staticmethod
    def parse_group_info(html: str, target_username: str) -> GroupInfo:
        """Extract metadata for a public group/supergroup."""
        soup = BeautifulSoup(html, "html.parser")
        
        # Title
        title_el = (
            soup.find("div", class_="tgme_page_title")
            or soup.find("div", class_="tgme_channel_info_header_title")
        )
        title = title_el.get_text(strip=True) if title_el else target_username

        # Description
        desc_el = (
            soup.find("div", class_="tgme_page_description")
            or soup.find("div", class_="tgme_channel_info_description")
        )
        desc = desc_el.get_text(separator="\n", strip=True) if desc_el else None

        # Members
        members = None
        members_str = None
        extra_el = soup.find("div", class_="tgme_page_extra")
        if extra_el:
            members_str = extra_el.get_text(strip=True)
            members = parse_numeric_shorthand(members_str)

        # Avatar
        avatar_url = None
        avatar_el = soup.find("img", class_="tgme_page_photo_image")
        if avatar_el and avatar_el.get("src"):
            avatar_url = avatar_el["src"]

        return GroupInfo(
            username=target_username,
            title=title,
            description=desc,
            members=members,
            members_str=members_str,
            avatar_url=avatar_url,
            url=f"https://t.me/{target_username}",
        )

    @staticmethod
    def parse_messages(html: str, channel_username: str) -> List[MessageItem]:
        """Parse all message elements from Telegram public web preview HTML."""
        soup = BeautifulSoup(html, "html.parser")
        message_elements = soup.find_all("div", class_=re.compile(r"tgme_widget_message\b"))
        
        # Channel title if present
        channel_title = None
        title_el = soup.find("div", class_="tgme_channel_info_header_title") or soup.find("div", class_="tgme_page_title")
        if title_el:
            channel_title = title_el.get_text(strip=True)

        results: List[MessageItem] = []
        for msg_el in message_elements:
            parsed = TelegramParser._parse_single_message_element(msg_el, channel_username, channel_title)
            if parsed:
                results.append(parsed)

        return results

    @staticmethod
    def _parse_single_message_element(
        msg_el: Any,
        fallback_username: str,
        fallback_channel_title: Optional[str] = None,
    ) -> Optional[MessageItem]:
        """Parse a single .tgme_widget_message element into MessageItem."""
        # Post ID
        data_post = msg_el.get("data-post", "")
        if "/" in data_post:
            channel_user, post_id_str = data_post.split("/", 1)
            try:
                msg_id = int(post_id_str)
            except ValueError:
                return None
        else:
            channel_user = fallback_username
            msg_id_match = re.search(r"\d+", msg_el.get("id", ""))
            if msg_id_match:
                msg_id = int(msg_id_match.group(0))
            else:
                return None

        # Author / Owner Signature
        author = None
        author_el = (
            msg_el.find("a", class_="tgme_widget_message_owner_name")
            or msg_el.find("span", class_="tgme_widget_message_from_author")
            or msg_el.find("div", class_="tgme_widget_message_author_name")
        )
        if author_el:
            author = author_el.get_text(strip=True)
        elif fallback_channel_title:
            author = fallback_channel_title

        # Timestamp
        date_iso = None
        time_el = msg_el.find("time", class_="time")
        if time_el and time_el.get("datetime"):
            date_iso = time_el["datetime"]

        # Text formatting
        text = None
        text_el = msg_el.find("div", class_="tgme_widget_message_text")
        if text_el:
            text = clean_telegram_message_text(text_el)

        # Forwarded from
        is_forwarded = False
        forward_from = None
        fwd_el = msg_el.find("a", class_="tgme_widget_message_forwarded_from_name")
        if fwd_el:
            is_forwarded = True
            forward_from = fwd_el.get_text(strip=True)

        # Engagement (Views, Reactions)
        views = 0
        views_str = None
        views_el = msg_el.find("span", class_="tgme_widget_message_views")
        if views_el:
            views_str = views_el.get_text(strip=True)
            views = parse_numeric_shorthand(views_str)

        reactions_breakdown: Dict[str, int] = {}
        total_reactions = 0
        react_elements = msg_el.find_all("div", class_="tgme_reaction")
        for r_el in react_elements:
            emoji_el = r_el.find("span", class_="tgme_reaction_emoji")
            count_el = r_el.find("span", class_="tgme_reaction_count")
            emoji = emoji_el.get_text(strip=True) if emoji_el else "👍"
            r_count = parse_numeric_shorthand(count_el.get_text(strip=True)) if count_el else 1
            reactions_breakdown[emoji] = reactions_breakdown.get(emoji, 0) + r_count
            total_reactions += r_count

        engagement = EngagementMetrics(
            views=views,
            views_str=views_str,
            forwards=0,
            reactions_count=total_reactions,
            reactions_breakdown=reactions_breakdown,
        )

        # Media extraction
        media: List[MediaItem] = []
        
        # 1. Photos
        photo_elements = msg_el.find_all(class_=re.compile(r"tgme_widget_message_photo_wrap"))
        for p_el in photo_elements:
            style = p_el.get("style", "")
            img_match = re.search(r"background-image:url\(['\"]?(.*?)['\"]?\)", style)
            if img_match:
                media.append(MediaItem(type="photo", url=img_match.group(1)))

        # 2. Videos
        video_elements = msg_el.find_all("video", class_="tgme_widget_message_video")
        for v_el in video_elements:
            src = v_el.get("src")
            duration_el = msg_el.find("time", class_="message_video_duration")
            dur = duration_el.get_text(strip=True) if duration_el else None
            media.append(MediaItem(type="video", url=src, duration=dur))

        # 3. Documents
        doc_elements = msg_el.find_all("div", class_="tgme_widget_message_document_wrap")
        for d_el in doc_elements:
            title_el = d_el.find("div", class_="tgme_widget_message_document_title")
            extra_el = d_el.find("div", class_="tgme_widget_message_document_extra")
            filename = title_el.get_text(strip=True) if title_el else None
            media.append(MediaItem(type="document", file_name=filename, mime_type=extra_el.get_text(strip=True) if extra_el else None))

        # 4. Voice / Audio
        voice_elements = msg_el.find_all("audio", class_="tgme_widget_message_voice")
        for a_el in voice_elements:
            media.append(MediaItem(type="audio", url=a_el.get("src")))

        # Links, Hashtags, Mentions
        links = []
        if text_el:
            for a_tag in text_el.find_all("a", href=True):
                href = a_tag["href"]
                if href.startswith("http"):
                    links.append(href)
        if text:
            links.extend(extract_links_from_text(text))
        links = list(dict.fromkeys(links))

        hashtags = extract_hashtags_from_text(text or "")
        mentions = extract_mentions_from_text(text or "")

        has_media = len(media) > 0
        media_type = media[0].type if media else None
        media_url = media[0].url if media else None
        primary_link = links[0] if links else None

        return MessageItem(
            id=msg_id,
            message_id=msg_id,
            channel_username=channel_user,
            channel=channel_user,
            channel_title=fallback_channel_title,
            channelTitle=fallback_channel_title,
            url=f"https://t.me/{channel_user}/{msg_id}",
            post_url=f"https://t.me/{channel_user}/{msg_id}",
            postUrl=f"https://t.me/{channel_user}/{msg_id}",
            date=date_iso,
            text=text,
            author=author,
            views=views_str,
            has_media=has_media,
            hasMedia=has_media,
            media_type=media_type,
            mediaType=media_type,
            media_url=media_url,
            mediaUrl=media_url,
            link=primary_link,
            is_forwarded=is_forwarded,
            forward_from=forward_from,
            engagement=engagement,
            media=media,
            links=links,
            hashtags=hashtags,
            mentions=mentions,
        )
