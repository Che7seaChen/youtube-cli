from __future__ import annotations

import urllib.parse
from typing import Any


def _thumbnail_list(raw: dict[str, Any]) -> list[dict[str, Any]]:
    thumbnails = raw.get("thumbnails") or []
    return [{"url": item.get("url"), "height": item.get("height"), "width": item.get("width")} for item in thumbnails]


def _channel(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": raw.get("channel_id") or raw.get("uploader_id"),
        "title": raw.get("channel") or raw.get("uploader"),
        "handle": raw.get("uploader_id"),
    }


def _entry_url(raw: dict[str, Any]) -> str | None:
    return (
        raw.get("webpage_url")
        or raw.get("url")
        or raw.get("channel_url")
        or raw.get("uploader_url")
    )


def _entry_id(raw: dict[str, Any]) -> str | None:
    direct = raw.get("id")
    if direct:
        return direct
    url = _entry_url(raw)
    if not url:
        return None
    parsed = urllib.parse.urlparse(url)
    query = urllib.parse.parse_qs(parsed.query)
    if "v" in query:
        return query["v"][0]
    if "list" in query:
        return query["list"][0]
    if parsed.path.startswith("/watch"):
        return None
    last = parsed.path.rstrip("/").split("/")[-1]
    return last or None


def _thumbnail_url(raw: dict[str, Any]) -> str | None:
    if raw.get("thumbnail"):
        return raw.get("thumbnail")
    thumbnails = raw.get("thumbnails") or []
    if thumbnails:
        return thumbnails[0].get("url")
    return None


def _entry_type(raw: dict[str, Any]) -> str:
    url = _entry_url(raw) or ""
    if raw.get("_type") == "playlist" or "/playlist" in url:
        return "playlist"
    if "/channel/" in url or "/@" in url or raw.get("ie_key") == "YoutubeTab":
        return "channel"
    return "video"


def normalize_video(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": raw.get("id"),
        "url": raw.get("webpage_url") or raw.get("original_url"),
        "title": raw.get("title"),
        "description": raw.get("description"),
        "channel": _channel(raw),
        "duration_seconds": raw.get("duration"),
        "published_at": raw.get("upload_date"),
        "view_count": raw.get("view_count"),
        "like_count": raw.get("like_count"),
        "comment_count": raw.get("comment_count"),
        "tags": raw.get("tags") or [],
        "is_live": raw.get("is_live", False),
        "availability": raw.get("availability"),
        "thumbnails": _thumbnail_list(raw),
        "chapters": [
            {
                "title": chapter.get("title"),
                "start_seconds": chapter.get("start_time"),
                "end_seconds": chapter.get("end_time"),
            }
            for chapter in raw.get("chapters") or []
        ],
        "subtitles_available": {
            "manual": bool(raw.get("subtitles")),
            "auto": bool(raw.get("automatic_captions")),
        },
    }


def normalize_channel(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": raw.get("channel_id") or raw.get("id"),
        "title": raw.get("channel") or raw.get("title"),
        "handle": raw.get("uploader_id"),
        "url": raw.get("webpage_url"),
        "description": raw.get("description"),
        "subscriber_count": raw.get("channel_follower_count"),
        "video_count": raw.get("playlist_count"),
        "is_verified": bool(raw.get("channel_is_verified")),
        "avatar_url": (raw.get("thumbnails") or [{}])[0].get("url"),
    }


def normalize_playlist(raw: dict[str, Any], limit: int | None = None) -> dict[str, Any]:
    entries = list(raw.get("entries") or [])
    if limit is not None:
        entries = entries[:limit]
    return {
        "id": raw.get("id"),
        "title": raw.get("title"),
        "url": raw.get("webpage_url") or raw.get("original_url"),
        "channel": {
            "id": raw.get("channel_id"),
            "title": raw.get("channel"),
        },
        "item_count": raw.get("playlist_count") or len(entries),
        "items": [normalize_feed_item(entry) for entry in entries],
    }


def normalize_formats(raw: dict[str, Any]) -> dict[str, Any]:
    formats: list[dict[str, Any]] = []
    for item in raw.get("formats") or []:
        formats.append(
            {
                "format_id": item.get("format_id"),
                "ext": item.get("ext"),
                "resolution": item.get("resolution") or item.get("format_note"),
                "vcodec": item.get("vcodec"),
                "acodec": item.get("acodec"),
                "fps": item.get("fps"),
                "filesize": item.get("filesize") or item.get("filesize_approx"),
                "protocol": item.get("protocol"),
            }
        )
    return {"video_id": raw.get("id"), "formats": formats}


def normalize_feed_item(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": _entry_type(raw),
        "id": _entry_id(raw),
        "title": raw.get("title"),
        "url": _entry_url(raw),
        "channel": _channel(raw),
        "published_at": raw.get("upload_date"),
        "duration_seconds": raw.get("duration"),
        "thumbnail_url": _thumbnail_url(raw),
        "view_count": raw.get("view_count"),
    }


def normalize_comment(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": raw.get("id"),
        "text": raw.get("text"),
        "author": raw.get("author"),
        "author_id": raw.get("author_id"),
        "author_url": raw.get("author_url"),
        "like_count": raw.get("like_count"),
        "is_pinned": bool(raw.get("is_pinned")),
        "is_favorited": bool(raw.get("is_favorited")),
        "parent": raw.get("parent"),
        "timestamp": raw.get("timestamp"),
    }
