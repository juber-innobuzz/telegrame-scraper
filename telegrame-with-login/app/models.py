"""Single consolidated schema and data models definition for the Telegram Scraper API."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


# --- 1. Core Telegram Entities ---
class MediaItem(BaseModel):
    """Represents a media attachment in a message."""
    type: str = Field(..., description="Type of media: image, video, document, audio")
    url: Optional[str] = Field(None, description="Direct URL or CDN source link")
    thumbnail: Optional[str] = Field(None, description="Thumbnail URL if available")
    file_name: Optional[str] = Field(None, description="Filename for document/audio files")
    mime_type: Optional[str] = Field(None, description="Detected MIME type")
    duration: Optional[str] = Field(None, description="Duration string for video/audio")


class EngagementMetrics(BaseModel):
    """Public engagement counters for a message or channel."""
    views: int = Field(default=0, description="Public view count (integer)")
    views_str: Optional[str] = Field(default=None, description="Raw view count string (e.g., '1.02M', '908K')")
    forwards: int = Field(default=0, description="Number of times forwarded")
    reactions_count: int = Field(default=0, description="Total count of public reactions")
    reactions_breakdown: Dict[str, int] = Field(default_factory=dict, description="Emoji to reaction count map")


class MessageItem(BaseModel):
    """Represents a single Telegram post/message with dual camelCase and snake_case support."""
    id: int = Field(..., description="Unique message ID in the channel/group")
    message_id: Optional[int] = Field(None, description="Alias for id")
    channel_username: str = Field(..., description="Telegram username of the channel or group")
    channel: Optional[str] = Field(None, description="Alias for channel_username")
    channel_title: Optional[str] = Field(None, description="Display title of the channel")
    channelTitle: Optional[str] = Field(None, description="CamelCase alias for channel_title")
    url: str = Field(..., description="Direct web link to the message")
    post_url: Optional[str] = Field(None, description="Alias for url")
    postUrl: Optional[str] = Field(None, description="CamelCase alias for post_url")
    date: Optional[str] = Field(None, description="ISO formatted publication timestamp")
    text: Optional[str] = Field(None, description="Clean textual content of the message")
    author: Optional[str] = Field(None, description="Author / channel signature or owner name")
    views: Optional[str] = Field(None, description="Formatted view count string e.g. '1.02M'")
    has_media: bool = Field(default=False, description="Whether the message has attached media")
    hasMedia: Optional[bool] = Field(None, description="CamelCase alias for has_media")
    media_type: Optional[str] = Field(None, description="Primary media type e.g. 'video', 'photo', 'document'")
    mediaType: Optional[str] = Field(None, description="CamelCase alias for media_type")
    media_url: Optional[str] = Field(None, description="Primary media CDN link")
    mediaUrl: Optional[str] = Field(None, description="CamelCase alias for media_url")
    link: Optional[str] = Field(None, description="Primary external web link attached in the post")
    subscribers: Optional[str] = Field(None, description="Channel subscribers at time of scrape")
    is_forwarded: bool = Field(default=False, description="Whether this message is a forward")
    forward_from: Optional[str] = Field(None, description="Source author or channel of forward")
    engagement: EngagementMetrics = Field(default_factory=EngagementMetrics)
    media: List[MediaItem] = Field(default_factory=list)
    links: List[str] = Field(default_factory=list)
    hashtags: List[str] = Field(default_factory=list)
    mentions: List[str] = Field(default_factory=list)

    def model_post_init(self, __context: Any) -> None:
        """Ensure all aliases are populated seamlessly."""
        if self.message_id is None:
            self.message_id = self.id
        if self.channel is None:
            self.channel = self.channel_username
        if self.post_url is None:
            self.post_url = self.url
        if self.postUrl is None:
            self.postUrl = self.url
        if self.channelTitle is None and self.channel_title:
            self.channelTitle = self.channel_title
        if self.hasMedia is None:
            self.hasMedia = self.has_media
        if self.mediaType is None and self.media_type:
            self.mediaType = self.media_type
        if self.mediaUrl is None and self.media_url:
            self.mediaUrl = self.media_url
        if not self.views and self.engagement and self.engagement.views_str:
            self.views = self.engagement.views_str


class ChannelInfo(BaseModel):
    """Metadata for a public Telegram channel with comprehensive counters and dual-naming support."""
    username: str = Field(..., description="Channel handle/username")
    channel_username: Optional[str] = Field(None, description="Alias for username")
    channelUsername: Optional[str] = Field(None, description="CamelCase alias for channel_username")
    channel: Optional[str] = Field(None, description="Alias for channel handle")
    title: str = Field(..., description="Display title of the channel")
    channel_title: Optional[str] = Field(None, description="Alias for title")
    channelTitle: Optional[str] = Field(None, description="CamelCase alias for channel_title")
    description: Optional[str] = Field(None, description="Channel bio/description")
    channel_description: Optional[str] = Field(None, description="Alias for description")
    channelDescription: Optional[str] = Field(None, description="CamelCase alias for channel_description")
    subscribers: Optional[int] = Field(None, description="Approximate or exact subscriber count (integer)")
    subscribers_str: Optional[str] = Field(None, description="Raw subscriber text (e.g., '9.6M', '145K subscribers')")
    photos_count: Optional[int] = Field(None, description="Total photos count published in channel")
    photos_count_str: Optional[str] = Field(None, description="Raw photos count string (e.g. '16')")
    photosCount: Optional[str] = Field(None, description="CamelCase alias for photos_count_str")
    videos_count: Optional[int] = Field(None, description="Total videos count published in channel")
    videos_count_str: Optional[str] = Field(None, description="Raw videos count string (e.g. '228')")
    videosCount: Optional[str] = Field(None, description="CamelCase alias for videos_count_str")
    links_count: Optional[int] = Field(None, description="Total shared links count in channel")
    links_count_str: Optional[str] = Field(None, description="Raw links count string (e.g. '378')")
    linksCount: Optional[str] = Field(None, description="CamelCase alias for links_count_str")
    files_count: Optional[int] = Field(None, description="Total files/documents count in channel")
    files_count_str: Optional[str] = Field(None, description="Raw files count string")
    audios_count: Optional[int] = Field(None, description="Total audio tracks count in channel")
    audios_count_str: Optional[str] = Field(None, description="Raw audio tracks count string")
    posts_returned: Optional[int] = Field(None, description="Number of posts returned in this scrape session")
    postsReturned: Optional[int] = Field(None, description="CamelCase alias for posts_returned")
    avatar_url: Optional[str] = Field(None, description="Channel avatar image URL")
    is_verified: bool = Field(default=False, description="Whether channel has Telegram verified badge")
    url: str = Field(..., description="Public t.me URL")

    def model_post_init(self, __context: Any) -> None:
        """Ensure all aliases are populated seamlessly."""
        if self.channel_username is None:
            self.channel_username = self.username
        if self.channelUsername is None:
            self.channelUsername = self.username
        if self.channel is None:
            self.channel = self.username
        if self.channel_title is None:
            self.channel_title = self.title
        if self.channelTitle is None:
            self.channelTitle = self.title
        if self.channel_description is None:
            self.channel_description = self.description
        if self.channelDescription is None:
            self.channelDescription = self.description
        if self.photosCount is None and self.photos_count_str:
            self.photosCount = self.photos_count_str
        if self.videosCount is None and self.videos_count_str:
            self.videosCount = self.videos_count_str
        if self.linksCount is None and self.links_count_str:
            self.linksCount = self.links_count_str
        if self.postsReturned is None and self.posts_returned:
            self.postsReturned = self.posts_returned


class GroupInfo(BaseModel):
    """Metadata for a public Telegram group."""
    username: str = Field(..., description="Group handle/username")
    title: str = Field(..., description="Display title of the group")
    description: Optional[str] = Field(None, description="Group description")
    members: Optional[int] = Field(None, description="Approximate member count")
    members_str: Optional[str] = Field(None, description="Raw member string (e.g., 5.4K members)")
    avatar_url: Optional[str] = Field(None, description="Group avatar URL")
    url: str = Field(..., description="Public group URL")


# --- 2. Request & Response Models (v2 Sliced API) ---
class ScrapeOptions(BaseModel):
    """Fine-grained configuration options for extractors and filters."""
    unique_links: bool = Field(default=True, description="Deduplicate extracted URLs")
    exclude_social_from_websites: bool = Field(default=False, description="Exclude social domains from websites slice")
    media_type: str = Field(default="all", description="Filter media slice: all, image, video, document, audio")
    entity_type: str = Field(default="all", description="Filter entity slice: all, business, brand, product, organization, person, location")
    currency_hint: Optional[str] = Field(default=None, description="Optional currency filter (e.g., INR, USD, EUR)")
    product_keywords: Optional[str] = Field(default=None, description="Comma-separated keywords to bias product detection")
    keywords_top_n: int = Field(default=50, ge=1, le=500, description="Max keywords to return in keywords slice")
    include_emails: bool = Field(default=True, description="Extract emails in leads slice")
    include_phones: bool = Field(default=True, description="Extract phone numbers in leads slice")


class ChannelScrapeRequest(BaseModel):
    """Request payload for POST /telegram/channel endpoint."""
    username: str = Field(..., description="Public channel @username or t.me URL")
    include: List[str] = Field(
        default_factory=lambda: ["info", "messages"],
        description="List of data slices to return (e.g. ['info', 'messages', 'leads', 'products']) or ['all']",
    )
    limit: int = Field(default=50, ge=1, le=1000, description="Max public posts to scrape")
    before_message_id: Optional[int] = Field(default=None, description="Cursor: fetch posts before this message ID")
    date_from: Optional[str] = Field(default=None, description="Optional start date YYYY-MM-DD filter")
    date_to: Optional[str] = Field(default=None, description="Optional end date YYYY-MM-DD filter")
    query: Optional[str] = Field(default=None, description="Optional keyword filter on message text")
    format: str = Field(default="sliced", description="Output format: 'sliced' (modern v2 object) or 'flat' (data.json-style flat array of rowType objects)")
    options: Optional[ScrapeOptions] = Field(default_factory=ScrapeOptions)


class PostScrapeRequest(BaseModel):
    """Request payload for POST /telegram/post endpoint."""
    url: Optional[str] = Field(default=None, description="Public post link e.g. https://t.me/durov/1")
    username: Optional[str] = Field(default=None, description="Channel username if URL is omitted")
    message_id: Optional[int] = Field(default=None, description="Message ID if URL is omitted")
    include: List[str] = Field(
        default_factory=lambda: ["messages", "links", "media"],
        description="Slices to derive from this single post or ['all']",
    )
    format: str = Field(default="sliced", description="Output format: 'sliced' or 'flat'")
    options: Optional[ScrapeOptions] = Field(default_factory=ScrapeOptions)


class BatchScrapeRequest(BaseModel):
    """Request payload for POST /telegram/batch endpoint."""
    usernames: List[str] = Field(..., description="List of public channel usernames or URLs")
    include: List[str] = Field(
        default_factory=lambda: ["info", "messages", "leads", "websites"],
        description="Shared data slices to return across all targets or ['all']",
    )
    limit_per_channel: int = Field(default=30, ge=1, le=500, description="Max messages to fetch per channel")
    since_message_id: Optional[Dict[str, int]] = Field(
        default=None,
        description="Map of username -> watermark message ID (only returns newer posts)",
    )
    query: Optional[str] = Field(default=None, description="Optional keyword filter applied per channel")
    date_from: Optional[str] = Field(default=None, description="Optional start date filter")
    date_to: Optional[str] = Field(default=None, description="Optional end date filter")
    format: str = Field(default="sliced", description="Output format: 'sliced' or 'flat'")
    options: Optional[ScrapeOptions] = Field(default_factory=ScrapeOptions)
    delay_sec: float = Field(default=1.5, ge=0.0, le=10.0, description="Delay between channel requests to avoid rate limits")


class ChannelScrapeResponse(BaseModel):
    """Dynamic response containing strictly the requested data slices for a channel."""
    status: str = "success"
    username: str
    requested: List[str]
    info: Optional[Dict[str, Any]] = None
    messages: Optional[List[Dict[str, Any]]] = None
    engagement: Optional[Dict[str, Any]] = None
    media: Optional[List[Dict[str, Any]]] = None
    links: Optional[List[str]] = None
    hashtags: Optional[List[Dict[str, Any]]] = None
    mentions: Optional[List[Dict[str, Any]]] = None
    forwards: Optional[List[Dict[str, Any]]] = None
    leads: Optional[Dict[str, Any]] = None
    websites: Optional[List[Dict[str, Any]]] = None
    social_links: Optional[Dict[str, List[str]]] = None
    products: Optional[List[Dict[str, Any]]] = None
    services: Optional[Dict[str, Any] | List[Dict[str, Any]]] = None
    prices: Optional[List[Dict[str, Any]]] = None
    jobs: Optional[List[Dict[str, Any]]] = None
    locations: Optional[List[Dict[str, Any]]] = None
    entities: Optional[List[Dict[str, Any]]] = None
    keywords: Optional[List[Dict[str, Any]]] = None


class PostScrapeResponse(BaseModel):
    """Dynamic response for single post scraper."""
    status: str = "success"
    url: str
    username: str
    message_id: int
    requested: List[str]
    messages: Optional[List[Dict[str, Any]]] = None
    media: Optional[List[Dict[str, Any]]] = None
    links: Optional[List[str]] = None
    hashtags: Optional[List[Dict[str, Any]]] = None
    mentions: Optional[List[Dict[str, Any]]] = None
    forwards: Optional[List[Dict[str, Any]]] = None
    leads: Optional[Dict[str, Any]] = None
    websites: Optional[List[Dict[str, Any]]] = None
    social_links: Optional[Dict[str, List[str]]] = None
    products: Optional[List[Dict[str, Any]]] = None
    services: Optional[Dict[str, Any] | List[Dict[str, Any]]] = None
    prices: Optional[List[Dict[str, Any]]] = None
    jobs: Optional[List[Dict[str, Any]]] = None
    locations: Optional[List[Dict[str, Any]]] = None
    entities: Optional[List[Dict[str, Any]]] = None
    keywords: Optional[List[Dict[str, Any]]] = None


class BatchScrapeResponse(BaseModel):
    """Batch scraper response schema."""
    status: str = "success"
    total_channels: int
    successful: int
    failed: int
    results: List[Dict[str, Any]]


class SearchRequest(BaseModel):
    """Payload for POST /telegram/search."""
    query: str = Field(..., min_length=1, description="Keyword, topic, or industry to search")
    type: str = Field(default="all", description="Target type: 'channel', 'group', or 'all'")
    limit: int = Field(default=10, ge=1, le=50, description="Max results per category")


class SearchResponse(BaseModel):
    """Response schema for public search."""
    status: str = "success"
    query: str
    type: str
    total_results: int
    channels: Optional[List[Dict[str, Any]]] = None
    groups: Optional[List[Dict[str, Any]]] = None


# --- 3. Enterprise & High-Scale Endpoint Models ---
class ChannelValidateRequest(BaseModel):
    """Payload for POST /channel/validate."""
    username: str = Field(..., description="Telegram channel @username or URL to validate")


class ChannelValidateResponse(BaseModel):
    """Validation response indicating if channel exists and is public."""
    status: str = "success"
    username: str
    is_valid: bool = Field(..., description="Whether username syntax is valid")
    exists: bool = Field(..., description="Whether the channel exists on Telegram")
    is_public: bool = Field(..., description="True if public and viewable without login")
    channel_status: str = Field(..., description="'public', 'private_or_restricted', 'not_found', or 'invalid'")
    title: Optional[str] = Field(None, description="Display title of the channel")
    description: Optional[str] = Field(None, description="Channel bio/description")
    subscribers: Optional[int] = Field(None, description="Subscriber count if public")
    subscribers_str: Optional[str] = Field(None, description="Formatted subscriber string (e.g. '9.6M')")
    avatar_url: Optional[str] = Field(None, description="Avatar image URL")
    is_verified: bool = Field(default=False, description="Whether channel has verified badge")
    url: str = Field(..., description="Canonical t.me link")
    error: Optional[str] = Field(None, description="Error detail if validation failed")


class ChannelPostsCursorResponse(BaseModel):
    """Response schema for cursor-based message pagination (GET /channel/{username}/posts)."""
    status: str = "success"
    username: str
    limit: int
    cursor: Optional[int] = Field(None, description="Current message ID cursor used")
    next_cursor: Optional[int] = Field(None, description="Cursor for the next batch of older posts")
    has_more: bool = Field(..., description="Whether there are more posts to paginate")
    count: int = Field(..., description="Number of posts returned in this page")
    messages: List[Dict[str, Any]] = Field(default_factory=list, description="List of messages in this page")


class HealthDetailedResponse(BaseModel):
    """Response schema for GET /health/detailed."""
    status: str = "healthy"
    service: str
    version: str
    uptime_seconds: float
    system: Dict[str, Any]
    memory: Dict[str, Any]
    cpu: Dict[str, Any]
    http_pool: Dict[str, Any]


# --- 4. User Client & Private Chat Models ---
class UserProfileResponse(BaseModel):
    """Profile information of the logged-in Telegram user."""
    status: str = "success"
    user_id: int = Field(..., description="Unique Telegram user ID")
    first_name: Optional[str] = Field(None, description="First name of the user")
    last_name: Optional[str] = Field(None, description="Last name of the user")
    username: Optional[str] = Field(None, description="Telegram @username handle if set")
    phone: Optional[str] = Field(None, description="User phone number")
    is_bot: bool = Field(default=False, description="Whether this entity is a bot")
    is_premium: bool = Field(default=False, description="Whether user has Telegram Premium")


class DialogLastMessage(BaseModel):
    """Summary of the latest message in a dialog."""
    id: Optional[int] = None
    date: Optional[str] = None
    text: Optional[str] = None
    sender_id: Optional[int] = None
    has_media: bool = False
    media_type: Optional[str] = None


class UserDialogItem(BaseModel):
    """Represents a chat, group, or channel from the user's dialog list."""
    id: int = Field(..., description="Unique chat / peer ID")
    title: str = Field(..., description="Display title or contact name")
    name: Optional[str] = Field(None, description="Alias for title")
    chat_type: str = Field(..., description="'user' (DM), 'group' (group/supergroup), or 'channel' (broadcast)")
    is_user: bool = Field(default=False, description="True if direct 1-on-1 personal chat")
    is_group: bool = Field(default=False, description="True if private or public group")
    is_channel: bool = Field(default=False, description="True if broadcast channel")
    unread_count: int = Field(default=0, description="Unread messages count")
    pinned: bool = Field(default=False, description="Whether chat is pinned")
    archived: bool = Field(default=False, description="Whether chat is archived")
    entity_username: Optional[str] = Field(None, description="Username handle if public")
    last_message: Optional[DialogLastMessage] = None


class UserDialogsResponse(BaseModel):
    """Response schema for GET /user/dialogs."""
    status: str = "success"
    total_dialogs: int = Field(..., description="Number of dialogs returned")
    limit: int
    filter_type: Optional[str] = Field(None, description="Applied filter: 'user', 'group', 'channel', or None")
    dialogs: List[UserDialogItem] = Field(default_factory=list)


class PrivateMessageItem(BaseModel):
    """Represents a message extracted from a private chat, group, or channel."""
    id: int = Field(..., description="Unique message ID within this chat")
    chat_id: int = Field(..., description="Chat ID where message was posted")
    date: Optional[str] = Field(None, description="ISO timestamp of message")
    text: Optional[str] = Field(None, description="Textual message content")
    sender_id: Optional[int] = Field(None, description="User ID of the sender")
    sender_name: Optional[str] = Field(None, description="Sender display name")
    sender_username: Optional[str] = Field(None, description="Sender @username")
    is_outgoing: bool = Field(default=False, description="True if sent by authenticated user")
    is_reply: bool = Field(default=False, description="True if message is a reply")
    reply_to_msg_id: Optional[int] = Field(None, description="Replied message ID")
    has_media: bool = Field(default=False, description="True if media attachment present")
    media_type: Optional[str] = Field(None, description="Type of media (e.g. Photo, Document, Video)")
    views: Optional[int] = Field(None, description="View count if available")
    forwards: Optional[int] = Field(None, description="Forward count if available")
    pinned: bool = Field(default=False, description="Whether message is pinned")


class PrivateMessagesResponse(BaseModel):
    """Response schema for GET /user/chats/{chat_id}/messages."""
    status: str = "success"
    chat_id: int = Field(..., description="Target chat ID")
    chat_title: Optional[str] = Field(None, description="Title of the chat")
    count: int = Field(..., description="Number of messages returned in this batch")
    limit: int
    next_offset_id: Optional[int] = Field(None, description="Cursor for the next batch of older messages")
    has_more: bool = Field(default=False, description="Whether more historical messages exist")
    messages: List[PrivateMessageItem] = Field(default_factory=list)


class ChatDetailResponse(BaseModel):
    """Detailed metadata for a specific chat or group."""
    status: str = "success"
    id: int
    title: str
    chat_type: str
    username: Optional[str] = None
    participants_count: Optional[int] = None
    description: Optional[str] = None
    is_creator: bool = False
    is_admin: bool = False


# --- 5. Asynchronous Job Queue & Session Pool Models ---
class JobSubmitRequest(BaseModel):
    """Request payload to submit an asynchronous scraping job."""
    chat_id: Union[int, str] = Field(..., description="Target chat ID, @username, or private link")
    limit: int = Field(default=100, ge=1, le=50000, description="Target number of messages to scrape")
    search_query: Optional[str] = Field(None, description="Optional keyword filter")


class JobSubmitResponse(BaseModel):
    """Immediate response after queuing a job."""
    status: str = "queued"
    job_id: str = Field(..., description="Unique UUID tracking ID for this job")
    chat_id: Union[int, str]
    target_limit: int
    message: str = "Job successfully queued. Check status via GET /jobs/{job_id}"
    status_url: str


class BatchJobSubmitRequest(BaseModel):
    """Request payload to submit multiple scraping jobs concurrently."""
    chats: List[Union[int, str]] = Field(..., description="List of chat IDs or usernames to scrape")
    limit_per_chat: int = Field(default=100, ge=1, le=10000, description="Max messages per chat")


class BatchJobSubmitResponse(BaseModel):
    """Response after queuing a batch of scrape jobs."""
    status: str = "queued"
    total_jobs: int
    jobs: List[Dict[str, Any]]


class JobStatusResponse(BaseModel):
    """Detailed status and progress for a queued/active scraping job."""
    job_id: str
    chat_id: Union[int, str]
    target_limit: int
    status: str = Field(..., description="'queued', 'processing', 'completed', 'failed', or 'rate_limited_retry'")
    progress_percent: float
    messages_scraped: int
    assigned_session_id: Optional[str] = None
    error_message: Optional[str] = None
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class JobResultResponse(BaseModel):
    """Full dataset result of a completed scraping job."""
    status: str = "success"
    job_id: str
    chat_id: Union[int, str]
    total_messages: int
    completed_at: Optional[str]
    messages: List[PrivateMessageItem] = Field(default_factory=list)


class AccountStatusItem(BaseModel):
    """Health metrics for an individual session in the pool."""
    session_id: str
    name: str
    status: str
    user_id: Optional[int] = None
    first_name: Optional[str] = None
    username: Optional[str] = None
    phone: Optional[str] = None
    is_available: bool
    total_requests: int
    total_messages_scraped: int
    flood_wait_count: int
    cooldown_remaining_seconds: int


class PoolStatusResponse(BaseModel):
    """Overview of all active and sleeping sessions in the session pool."""
    status: str = "success"
    total_accounts: int
    available_accounts: int
    accounts: List[AccountStatusItem] = Field(default_factory=list)


class AddSessionRequest(BaseModel):
    """Payload to add a new account session string dynamically at runtime."""
    session_id: str = Field(..., description="Unique alphanumeric identifier for this session")
    session_string: str = Field(..., description="Telethon StringSession base64 string")
    name: str = Field(default="Secondary Account", description="Friendly label for the account")


# --- 6. Telegram Authentication API Models ---
class AuthSendCodeRequest(BaseModel):
    """Payload to request a login OTP code."""
    phone_number: str = Field(..., description="Phone number with country code (e.g. '+917011186517')")


class AuthSendCodeResponse(BaseModel):
    """Response after sending OTP code."""
    status: str = "code_sent"
    auth_session_id: str = Field(..., description="Temporary session identifier for this login attempt")
    phone_number: str
    phone_code_hash: str
    is_code_via_app: bool = Field(default=True, description="True if sent to Telegram app, False if SMS")
    timeout: int = Field(default=120, description="Seconds until code expires")
    message: str = "Verification code sent to Telegram app / SMS."


class AuthVerifyCodeRequest(BaseModel):
    """Payload to submit OTP verification code."""
    auth_session_id: str = Field(..., description="Temporary auth_session_id returned from /auth/send-code")
    phone_number: str = Field(..., description="Phone number with country code")
    phone_code_hash: str = Field(..., description="phone_code_hash returned from /auth/send-code")
    code: str = Field(..., description="OTP code received in Telegram app or SMS")
    password: Optional[str] = Field(None, description="2FA cloud password if enabled")
    session_name: Optional[str] = Field(default="My Telegram Account", description="Friendly name for the account")
    auto_add_to_pool: bool = Field(default=True, description="Automatically add account to the active Session Pool")


class AuthVerify2FARequest(BaseModel):
    """Payload to submit 2FA cloud password."""
    auth_session_id: str = Field(..., description="Temporary auth_session_id")
    password: str = Field(..., description="2-Step Verification cloud password")
    session_name: Optional[str] = Field(default="My Telegram Account", description="Friendly name for the account")
    auto_add_to_pool: bool = Field(default=True, description="Automatically add account to the active Session Pool")


class AuthVerifyResponse(BaseModel):
    """Response after verifying code or 2FA."""
    status: str = Field(..., description="'authenticated' or '2fa_required'")
    auth_session_id: Optional[str] = None
    session_id: Optional[str] = None
    session_string: Optional[str] = None
    message: str
    user: Optional[Dict[str, Any]] = None


class AuthLogoutRequest(BaseModel):
    """Payload to log out and disconnect a session."""
    session_id: str = Field(..., description="Session identifier to disconnect and remove from pool")


class AuthStatusResponse(BaseModel):
    """Overview of authentication status across all accounts."""
    status: str = "success"
    is_authenticated: bool
    total_accounts: int
    accounts: List[Dict[str, Any]] = Field(default_factory=list)
