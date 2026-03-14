from __future__ import annotations

import contextlib
import os
import io
import json
import random
import re
import shutil
import ssl
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from http.cookiejar import MozillaCookieJar
from pathlib import Path
from typing import Any

import yt_dlp
import yt_dlp.cookies

from ..config import AuthConfig, RateLimitConfig, RetryConfig, normalize_mode
from ..errors import YoutubeCliError, map_provider_error
from ..normalize import (
    normalize_channel,
    normalize_comment,
    normalize_feed_item,
    normalize_formats,
    normalize_playlist,
    normalize_video,
)
from ..subtitles import parse_json3, parse_vtt, write_subtitle_file
from ..translation import build_translator, translate_segments
from ..reverse import YoutubeWriteClient

FEED_URLS = {
    "favorites": ":ytfav",
    "subscriptions": ":ytsubs",
    "watch_later": ":ytwatchlater",
    "history": ":ythistory",
    "recommendations": ":ytrec",
    "notifications": ":ytnotif",
}

DEFAULT_VIDEO_FORMAT = "bv*+ba/b"
DEFAULT_VIDEO_FALLBACKS = [
    DEFAULT_VIDEO_FORMAT,
    "22/18",
    "18",
    "b[ext=mp4]/b",
]
DEFAULT_AUDIO_FALLBACKS = ["140", "251", "250", "249", "139", "bestaudio"]
DEFAULT_VIDEO_FORMAT_SORT = ["proto:https", "ext:mp4:m4a", "codec:h264:aac"]
QUALITY_HEIGHTS = {
    "2160p": 2160,
    "1440p": 1440,
    "1080p": 1080,
    "720p": 720,
    "480p": 480,
    "360p": 360,
}
SEARCH_SP = {
    "channel": "EgIQAg%253D%253D",
    "playlist": "EgIQAw%253D%253D",
}
YT_INITIAL_DATA_PATTERNS = (
    re.compile(r"var ytInitialData = (\{.*?\});", re.DOTALL),
    re.compile(r"ytInitialData\s*=\s*(\{.*?\});", re.DOTALL),
)


def _parse_retry_sleep_expr(expr: str):
    number_re = r"\d+(?:\.\d+)?"
    match = re.fullmatch(
        rf"(?:(linear|exp)=)?({number_re})(?::({number_re})?)?(?::({number_re}))?",
        expr.strip(),
    )
    if not match:
        raise ValueError(f"invalid retry sleep expression: {expr}")
    op, start, limit, step = match.groups()
    if op == "exp":
        return lambda n: min(float(start) * (float(step or 2) ** n), float(limit or "inf"))
    default_step = start if op or limit else 0
    return lambda n: min(float(start) + float(step or default_step) * n, float(limit or "inf"))


class YtDlpProvider:
    def __init__(
        self,
        auth: AuthConfig | None = None,
        *,
        mode: str = "balanced",
        rate_limit: RateLimitConfig | None = None,
        retry: RetryConfig | None = None,
        no_check_certificate: bool = False,
    ) -> None:
        self.auth = auth
        self.mode = normalize_mode(mode)
        self.rate_limit = rate_limit or RateLimitConfig()
        self.retry = retry or RetryConfig()
        self.no_check_certificate = no_check_certificate
        self._auth_fallback_notice_keys: set[tuple[str, str]] = set()

    def _cookies_from_browser(self) -> tuple[str, ...] | None:
        if not self.auth or not self.auth.browser:
            return None
        if self.auth.container is not None:
            return (
                self.auth.browser,
                self.auth.profile,
                None,
                self.auth.container,
            )
        if self.auth.profile is not None:
            return (self.auth.browser, self.auth.profile)
        return (self.auth.browser,)


    def _effective_sleep_interval(self) -> float | None:
        if self.rate_limit.sleep_interval is not None:
            return self.rate_limit.sleep_interval
        if self.mode == "safe":
            return 1.0
        if self.mode == "balanced":
            return 0.4
        return None

    def _effective_max_sleep_interval(self) -> float | None:
        if self.rate_limit.max_sleep_interval is not None:
            return self.rate_limit.max_sleep_interval
        if self.mode == "safe":
            return 2.5
        if self.mode == "balanced":
            return 1.2
        return None

    def _effective_task_jitter_seconds(self) -> float:
        if self.rate_limit.task_jitter_seconds is not None:
            try:
                return max(0.0, float(self.rate_limit.task_jitter_seconds))
            except (TypeError, ValueError):
                return 0.0
        if self.mode == "safe":
            return 1.2
        if self.mode == "balanced":
            return 0.3
        return 0.0

    def _maybe_sleep_between_tasks(self, index: int) -> None:
        if index <= 0:
            return
        jitter = self._effective_task_jitter_seconds()
        if jitter <= 0:
            return
        time.sleep(random.uniform(0.0, jitter))

    def _base_opts(self, *, use_auth: bool = True) -> dict[str, Any]:
        opts: dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
        }
        if use_auth and self.auth:
            if self.auth.cookies_file:
                opts["cookiefile"] = self.auth.cookies_file
            elif self.auth.browser:
                cookies_from_browser = self._cookies_from_browser()
                if cookies_from_browser:
                    opts["cookiesfrombrowser"] = cookies_from_browser
        if self.no_check_certificate:
            opts["nocheckcertificate"] = True
        js_runtimes = os.getenv("YOUTUBE_CLI_JS_RUNTIMES")
        if js_runtimes:
            runtimes = [item.strip().lower() for item in js_runtimes.split(",") if item.strip()]
            if runtimes:
                opts["js_runtimes"] = {runtime: {} for runtime in runtimes}
        remote_components = os.getenv("YOUTUBE_CLI_REMOTE_COMPONENTS")
        if remote_components:
            components = [item.strip() for item in remote_components.split(",") if item.strip()]
            if components:
                opts["remote_components"] = components
        sleep_interval = self._effective_sleep_interval()
        if sleep_interval is not None:
            opts["sleep_interval"] = sleep_interval
            max_sleep_interval = self._effective_max_sleep_interval()
            if max_sleep_interval is not None:
                opts["max_sleep_interval"] = max_sleep_interval
            if self.rate_limit.sleep_interval_requests:
                opts["sleep_interval_requests"] = self.rate_limit.sleep_interval_requests
        return opts

    def _extract(
        self,
        target: str,
        *,
        flat: bool = False,
        download: bool = False,
        use_auth: bool = True,
        **extra: Any,
    ) -> dict[str, Any]:
        opts = self._base_opts(use_auth=use_auth)
        opts.update(extra)
        if flat:
            opts["extract_flat"] = True
        if download:
            opts["skip_download"] = False
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(target, download=download)
        except Exception as exc:  # pragma: no cover - exercised via CLI tests/mocks
            raise map_provider_error(exc) from exc
        if not isinstance(info, dict):
            raise YoutubeCliError("provider_error", "yt-dlp 返回了无法识别的数据结构。", source="yt_dlp")
        return info

    def _extract_with_auth_fallback(self, target: str, *, use_auth: bool, **extra: Any) -> dict[str, Any]:
        try:
            if use_auth:
                return self._call_silently(
                    self._extract,
                    target,
                    use_auth=True,
                    quiet=True,
                    no_warnings=True,
                    **extra,
                )
            return self._extract(target, use_auth=False, **extra)
        except YoutubeCliError as exc:
            if not (use_auth and self._should_retry_without_auth(exc)):
                raise
            self._emit_auth_fallback_notice(stage="提取字幕/视频信息", reason=exc.message)
            try:
                return self._extract(target, use_auth=False, **extra)
            except YoutubeCliError:
                raise exc

    def status(self) -> dict[str, Any]:
        return {
            "provider": "yt_dlp",
            "yt_dlp_version": getattr(yt_dlp.version, "__version__", None),
            "ffmpeg_available": shutil.which("ffmpeg") is not None,
            "ffprobe_available": shutil.which("ffprobe") is not None,
            "aria2c_available": shutil.which("aria2c") is not None,
            "auth_configured": self.auth is not None,
            "auth_mode": "cookies_file" if self.auth and self.auth.cookies_file else "browser" if self.auth else None,
            "browser": self.auth.browser if self.auth else None,
            "profile": self.auth.profile if self.auth else None,
            "container": self.auth.container if self.auth else None,
            "cookies_file": self.auth.cookies_file if self.auth else None,
            "mode": self.mode,
            "rate_limit": {
                "sleep_interval": self._effective_sleep_interval(),
                "max_sleep_interval": self._effective_max_sleep_interval(),
                "sleep_interval_requests": self.rate_limit.sleep_interval_requests,
                "task_jitter_seconds": self._effective_task_jitter_seconds(),
            },
            "no_check_certificate": self.no_check_certificate,
        }

    def export_cookies(self, output_path: Path) -> dict[str, Any]:
        if not self.auth or not self.auth.browser:
            raise YoutubeCliError(
                "auth_required",
                "导出 cookies 需要浏览器登录态。",
                hint="先运行 `youtube login --browser chrome` 并确保已登录。",
                source="yt_dlp",
            )
        cookies_from_browser = self._cookies_from_browser()
        if not cookies_from_browser:
            raise YoutubeCliError(
                "auth_required",
                "无法读取浏览器 Cookie。",
                hint="检查浏览器名称、profile 或 container 是否正确。",
                source="yt_dlp",
            )
        try:
            cookie_jar = yt_dlp.cookies.load_cookies(None, cookies_from_browser)
        except Exception as exc:  # pragma: no cover - exercised via live validation
            raise YoutubeCliError(
                "auth_required",
                "无法读取浏览器 Cookie，当前登录态不可用于导出。",
                hint="确认浏览器已登录 YouTube，或尝试指定正确的 profile/container。",
                source="yt_dlp",
            ) from exc
        output_path.parent.mkdir(parents=True, exist_ok=True)
        export_jar = MozillaCookieJar()
        count = 0
        for cookie in cookie_jar:
            export_jar.set_cookie(cookie)
            count += 1
        try:
            export_jar.save(str(output_path), ignore_discard=True, ignore_expires=True)
        except OSError as exc:
            raise YoutubeCliError(
                "config_write_failed",
                f"无法写入 cookies 文件: {output_path}",
                hint="检查路径权限，或换到可写目录后重试。",
                source="yt_dlp",
            ) from exc
        return {
            "exported": True,
            "path": str(output_path),
            "cookie_count": count,
        }

    def validate_auth(self) -> dict[str, Any]:
        if not self.auth:
            raise YoutubeCliError(
                "auth_required",
                "当前没有可用的登录配置。",
                hint="先运行 `youtube login --browser chrome`。",
                source="yt_dlp",
            )
        info = self._extract(FEED_URLS["subscriptions"], flat=True, use_auth=True)
        entries = list(info.get("entries") or [])
        return {
            "authenticated": True,
            "sample_size": len(entries),
            "sample_channel": entries[0].get("channel") if entries else None,
        }

    def whoami(self) -> dict[str, Any]:
        status = self.status()
        probes = self._auth_capabilities()
        homepage = self._homepage_auth_state()
        status.update(
            {
                "authenticated": any(item["accessible"] for item in probes.values()),
                "capabilities": probes,
                "homepage": homepage,
            }
        )
        return status

    def video(self, target: str, *, use_auth: bool = False) -> dict[str, Any]:
        return normalize_video(self._extract_with_auth_fallback(target, use_auth=use_auth))

    def formats(self, target: str, *, use_auth: bool = False) -> dict[str, Any]:
        return normalize_formats(self._extract_with_auth_fallback(target, use_auth=use_auth))

    def subtitles(
        self,
        target: str,
        *,
        language: str | None = None,
        auto: bool = False,
        use_auth: bool = False,
    ) -> dict[str, Any]:
        info = self._extract_with_auth_fallback(target, use_auth=use_auth)
        tracks = info.get("automatic_captions") if auto else info.get("subtitles")
        kind = "auto" if auto else "manual"
        return self._extract_subtitle_track(
            target=target,
            info=info,
            tracks=tracks,
            language=language,
            kind=kind,
            auto=auto,
            use_auth=use_auth,
        )

    def subtitle_with_fallback(
        self,
        target: str,
        *,
        language: str | None = None,
        prefer_auto: bool = False,
        use_auth: bool = False,
    ) -> dict[str, Any]:
        info = self._extract_with_auth_fallback(target, use_auth=use_auth)
        attempts = [("auto", True), ("manual", False)] if prefer_auto else [("manual", False), ("auto", True)]
        last_error: YoutubeCliError | None = None
        for kind, auto in attempts:
            tracks = info.get("automatic_captions") if auto else info.get("subtitles")
            try:
                return self._extract_subtitle_track(
                    target=target,
                    info=info,
                    tracks=tracks,
                    language=language,
                    kind=kind,
                    auto=auto,
                    use_auth=use_auth,
                )
            except YoutubeCliError as exc:
                if exc.code != "subtitle_unavailable":
                    raise
                last_error = exc
        if last_error:
            raise last_error
        raise YoutubeCliError("subtitle_unavailable", "当前视频没有可用字幕。", source="yt_dlp")

    def _extract_subtitle_track(
        self,
        *,
        target: str,
        info: dict[str, Any],
        tracks: dict[str, Any] | None,
        language: str | None,
        kind: str,
        auto: bool,
        use_auth: bool,
    ) -> dict[str, Any]:
        if not tracks:
            raise YoutubeCliError(
                "subtitle_unavailable",
                "当前视频没有可用字幕。",
                hint=None if auto else "尝试 `--auto` 获取自动字幕。",
                source="yt_dlp",
            )
        selected_language = language or next(iter(tracks.keys()))
        candidates = tracks.get(selected_language)
        if not candidates:
            raise YoutubeCliError(
                "subtitle_unavailable",
                f"语言 `{selected_language}` 的字幕不存在。",
                hint=f"可用语言: {', '.join(sorted(tracks))}",
                source="yt_dlp",
            )
        candidate = next(
            (
                item
                for preferred_ext in ("json3", "srv3", "srv2", "srv1", "ttml", "vtt")
                for item in candidates
                if item.get("ext") == preferred_ext
            ),
            candidates[0],
        )
        url = candidate.get("url")
        if not url:
            raise YoutubeCliError("provider_error", "字幕轨道缺少可下载 URL。", source="yt_dlp")
        ssl_context = None
        if self.no_check_certificate:
            ssl_context = ssl._create_unverified_context()
        try:
            with urllib.request.urlopen(url, context=ssl_context) as response:
                content = response.read().decode("utf-8", errors="replace")
        except Exception as exc:  # pragma: no cover - exercised via live validation
            mapped = map_provider_error(exc)
            if mapped.code == "rate_limited":
                mapped.hint = (
                    "字幕轨道请求被限流。重试时可加 `--use-auth`，或稍后再试。"
                    if not use_auth
                    else "字幕轨道请求即使带认证仍被限流。请稍后重试，或换一个视频验证。"
                )
            elif mapped.code == "auth_required":
                mapped.hint = (
                    "该字幕轨道需要有效登录态。重试时可加 `--use-auth` 并确认 `youtube login --check` 成功。"
                )
            raise mapped from exc
        return {
            "video_id": info.get("id"),
            "language": selected_language,
            "kind": kind,
            "format": candidate.get("ext") or "vtt",
            "segments": self._parse_subtitle_content(content, ext=candidate.get("ext")),
            "raw_url": url,
        }

    def search(self, query: str, *, limit: int = 10, search_type: str = "video") -> list[dict[str, Any]]:
        if search_type == "video":
            info = self._extract(f"ytsearch{limit}:{query}", flat=True, use_auth=False)
        else:
            sp = SEARCH_SP.get(search_type)
            if sp is None:
                raise YoutubeCliError(
                    "unsupported_operation",
                    f"不支持的搜索类型: {search_type}",
                    source="youtube_cli",
                )
            url = (
                "https://www.youtube.com/results"
                f"?search_query={urllib.parse.quote(query)}&sp={sp}"
            )
            info = self._extract(url, flat=True, use_auth=False)
        items = [normalize_feed_item(entry) for entry in info.get("entries") or []]
        if search_type != "video":
            items = [item for item in items if item["type"] == search_type]
        return items[:limit]

    def channel(self, target: str, *, limit: int = 20) -> dict[str, Any]:
        info = self._extract(self._channel_url(target), flat=True, use_auth=False)
        normalized = normalize_channel(info)
        root_items = [normalize_feed_item(entry) for entry in list(info.get("entries") or [])[:limit]]
        preview_limit = min(limit, 5)
        tab_previews: dict[str, list[dict[str, Any]]] = {}
        tab_status: dict[str, dict[str, Any]] = {}
        for tab_name, loader in {
            "videos": self.channel_videos,
            "playlists": self.channel_playlists,
        }.items():
            try:
                items = loader(target, limit=preview_limit)
                tab_previews[tab_name] = items
                tab_status[tab_name] = {
                    "available": True,
                    "sample_size": len(items),
                }
            except YoutubeCliError as exc:
                tab_previews[tab_name] = []
                tab_status[tab_name] = {
                    "available": False,
                    "error_code": exc.code,
                    "sample_size": 0,
                }
        normalized["recent_items"] = (
            [item for item in root_items if item["type"] == "video"][:limit]
            or tab_previews["videos"][:limit]
        )
        normalized["tab_previews"] = tab_previews
        normalized["tab_status"] = tab_status
        return normalized

    def channel_videos(self, target: str, *, limit: int = 20) -> list[dict[str, Any]]:
        return self._channel_tab(target, tab="videos", limit=limit)

    def channel_playlists(self, target: str, *, limit: int = 20) -> list[dict[str, Any]]:
        return self._channel_tab(target, tab="playlists", limit=limit)

    def playlist(self, target: str, *, limit: int = 20, use_auth: bool = False) -> dict[str, Any]:
        info = self._extract_with_auth_fallback(
            self._playlist_url(target),
            flat=True,
            use_auth=use_auth,
        )
        return normalize_playlist(info, limit=limit)

    def playlist_videos(
        self,
        target: str,
        *,
        limit: int | None = 20,
        use_auth: bool = False,
    ) -> list[dict[str, Any]]:
        info = self._extract_with_auth_fallback(self._playlist_url(target), flat=True, use_auth=use_auth)
        entries = list(info.get("entries") or [])
        if limit is not None:
            entries = entries[:limit]
        items = [normalize_feed_item(entry) for entry in entries]
        fallback_channel = {
            "id": info.get("channel_id"),
            "title": info.get("channel"),
            "handle": None,
        }
        for item in items:
            if not item["channel"].get("id"):
                item["channel"]["id"] = fallback_channel["id"]
            if not item["channel"].get("title"):
                item["channel"]["title"] = fallback_channel["title"]
            item["source_feed"] = "playlist_videos"
        return items

    def feed(self, name: str, *, limit: int = 20) -> list[dict[str, Any]]:
        target = FEED_URLS.get(name)
        if target is None:
            raise YoutubeCliError("unsupported_operation", f"未知 feed: {name}", source="youtube_cli")
        info = self._extract(target, flat=True, use_auth=True)
        items = [normalize_feed_item(entry) for entry in list(info.get("entries") or [])[:limit]]
        for item in items:
            item["source_feed"] = name
        return items

    def comments(
        self,
        target: str,
        *,
        limit: int = 20,
        sort: str = "top",
        use_auth: bool = False,
    ) -> list[dict[str, Any]]:
        info = self._extract_with_auth_fallback(
            target,
            use_auth=use_auth,
            getcomments=True,
            extractor_args={
                "youtube": {
                    "max_comments": [str(limit)],
                    "comment_sort": [sort],
                }
            },
        )
        return [normalize_comment(comment) for comment in list(info.get("comments") or [])[:limit]]

    def related(self, target: str, *, limit: int = 20) -> list[dict[str, Any]]:
        url = target if target.startswith("http") else f"https://www.youtube.com/watch?v={target}"
        html = self._fetch_html(url)
        data = self._extract_initial_data(html)
        results = (
            ((data.get("contents") or {}).get("twoColumnWatchNextResults") or {})
            .get("secondaryResults", {})
            .get("secondaryResults", {})
            .get("results", [])
        )
        items: list[dict[str, Any]] = []
        for result in results:
            model = result.get("lockupViewModel") or {}
            content_id = model.get("contentId")
            if not content_id:
                continue
            metadata = (
                ((model.get("metadata") or {}).get("lockupMetadataViewModel") or {})
                .get("metadata", {})
                .get("contentMetadataViewModel", {})
                .get("metadataRows", [])
            )
            title = (
                ((model.get("metadata") or {}).get("lockupMetadataViewModel") or {})
                .get("title", {})
                .get("content")
            )
            if not title:
                continue
            channel_title = None
            view_count_text = None
            published_text = None
            if metadata:
                first_row = metadata[0].get("metadataParts") or []
                if first_row:
                    channel_title = first_row[0].get("text", {}).get("content")
                if len(metadata) > 1:
                    second_row = metadata[1].get("metadataParts") or []
                    if second_row:
                        view_count_text = second_row[0].get("text", {}).get("content")
                    if len(second_row) > 1:
                        published_text = second_row[1].get("text", {}).get("content")
            duration_text = self._extract_duration_text(model)
            thumbnail_url = (
                ((model.get("contentImage") or {}).get("thumbnailViewModel") or {})
                .get("image", {})
                .get("sources", [{}])[0]
                .get("url")
            )
            items.append(
                {
                    "type": "video",
                    "id": content_id,
                    "title": title,
                    "url": f"https://www.youtube.com/watch?v={content_id}",
                    "channel": {
                        "id": None,
                        "title": channel_title,
                        "handle": None,
                    },
                    "thumbnail_url": thumbnail_url,
                    "duration_text": duration_text,
                    "view_count_text": view_count_text,
                    "published_text": published_text,
                }
            )
            if len(items) >= limit:
                break
        return items

    def save_to_watch_later(self, target: str, *, dry_run: bool = False) -> dict[str, Any]:
        client = YoutubeWriteClient(self.auth, mode=self.mode, retry=self.retry, no_check_certificate=self.no_check_certificate)
        return client.add_to_watch_later(target, dry_run=dry_run)

    def playlist_add(self, target: str, playlist: str, *, dry_run: bool = False) -> dict[str, Any]:
        client = YoutubeWriteClient(self.auth, mode=self.mode, retry=self.retry, no_check_certificate=self.no_check_certificate)
        return client.add_to_playlist(target, playlist, dry_run=dry_run)

    def playlist_create(
        self,
        title: str,
        *,
        description: str | None,
        privacy: str,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        client = YoutubeWriteClient(self.auth, mode=self.mode, retry=self.retry, no_check_certificate=self.no_check_certificate)
        return client.create_playlist(title, description=description, privacy=privacy, dry_run=dry_run)

    def playlist_delete(self, playlist: str, *, dry_run: bool = False) -> dict[str, Any]:
        client = YoutubeWriteClient(self.auth, mode=self.mode, retry=self.retry, no_check_certificate=self.no_check_certificate)
        return client.delete_playlist(playlist, dry_run=dry_run)

    def download(
        self,
        targets: list[str],
        *,
        output_dir: Path,
        format_selector: str,
        audio_only: bool = False,
        write_subtitles: bool = False,
        subtitle_languages: list[str] | None = None,
        subtitle_file_format: str = "srt",
        prefer_auto_subtitles: bool = False,
        use_auth: bool = False,
        rate_limit: str | None = None,
        quality: str | None = None,
        throttled_rate: str | None = None,
        http_chunk_size: str | None = None,
        concurrent_fragments: int = 4,
        fragment_retries: int = 10,
        external_downloader: str | None = None,
        external_downloader_args: list[str] | None = None,
        manifest_path: Path | None = None,
        resume_failed: bool = False,
    ) -> list[dict[str, Any]]:
        output_dir.mkdir(parents=True, exist_ok=True)
        manifest_file = manifest_path or output_dir / ".youtube-cli-manifest.json"
        manifest = self._load_download_manifest(manifest_file)
        manifest_entries = manifest.setdefault("entries", {})
        opts = self._base_opts(use_auth=use_auth)
        opts.update(
            {
                "quiet": False,
                "noprogress": True,
                "skip_download": False,
                "paths": {"home": str(output_dir)},
                "outtmpl": {
                    "default": "%(uploader|unknown)s/%(title).180B [%(id)s].%(ext)s",
                },
                "format": format_selector,
                "continuedl": True,
                "retries": 10,
                "fragment_retries": fragment_retries,
                "concurrent_fragment_downloads": concurrent_fragments,
                "retry_sleep_functions": {
                    "http": _parse_retry_sleep_expr("linear=1::2"),
                    "fragment": _parse_retry_sleep_expr("exp=1:20"),
                },
                "ignoreerrors": False,
            }
        )
        resolved_format_selector = self._resolve_download_format(
            format_selector=format_selector,
            quality=quality,
            audio_only=audio_only,
        )
        opts["format"] = resolved_format_selector
        effective_rate_limit = rate_limit or self.rate_limit.download_rate_limit
        effective_throttled_rate = throttled_rate or self.rate_limit.download_throttled_rate
        effective_http_chunk_size = http_chunk_size or self.rate_limit.download_http_chunk_size
        if effective_rate_limit:
            opts["ratelimit"] = effective_rate_limit
        if effective_throttled_rate:
            opts["throttledratelimit"] = effective_throttled_rate
        if effective_http_chunk_size:
            opts["http_chunk_size"] = effective_http_chunk_size
        if external_downloader:
            opts["external_downloader"] = {"default": external_downloader}
            if external_downloader_args:
                opts["external_downloader_args"] = {
                    external_downloader.lower(): external_downloader_args,
                }
        if audio_only:
            opts["format"] = resolved_format_selector
            opts["postprocessors"] = [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "0",
                }
            ]
        elif resolved_format_selector == "bv*+ba/b":
            opts["format"] = DEFAULT_VIDEO_FORMAT
            opts["format_sort"] = list(DEFAULT_VIDEO_FORMAT_SORT)
            opts["merge_output_format"] = "mp4"
        elif quality:
            opts["format_sort"] = list(DEFAULT_VIDEO_FORMAT_SORT)
            opts["merge_output_format"] = "mp4"
        tasks: list[dict[str, Any]] = []
        try:
            for index, target in enumerate(targets):
                self._maybe_sleep_between_tasks(index)
                task_id = f"dl_{len(tasks) + 1:03d}"
                task_key = self._task_key(target, audio_only=audio_only)
                existing = manifest_entries.get(task_key)
                if resume_failed and existing and existing.get("status") == "completed":
                    task = dict(existing)
                    task["task_id"] = task_id
                    task["skipped"] = True
                    task["resumed_from_manifest"] = True
                    tasks.append(task)
                    continue
                task = {
                    "task_id": task_id,
                    "target": {
                        "id": None,
                        "url": target,
                    },
                    "mode": "audio" if audio_only else "video",
                    "status": "running",
                    "output_path": None,
                    "requested_format": resolved_format_selector,
                    "actual_format": None,
                    "manifest_path": str(manifest_file),
                    "started_at": self._now_iso(),
                    "finished_at": None,
                    "skipped": False,
                    "resumed_from_manifest": bool(existing and resume_failed),
                    "subtitle_files": [],
                    "subtitle_error": None,
                }
                manifest_entries[task_key] = dict(task)
                self._save_download_manifest(manifest_file, manifest)
                try:
                    result = self._download_with_auth_fallback(
                        target,
                        opts=opts,
                        requested_format=resolved_format_selector,
                        audio_only=audio_only,
                        use_auth=use_auth,
                    )
                    task.update(result)
                    if write_subtitles and task.get("output_path"):
                        try:
                            task["subtitle_files"] = self._export_subtitle_files(
                                target=target,
                                output_path=Path(task["output_path"]),
                                subtitle_languages=subtitle_languages or [],
                                file_format=subtitle_file_format,
                                prefer_auto_subtitles=prefer_auto_subtitles,
                                use_auth=use_auth,
                            )
                        except YoutubeCliError as subtitle_exc:
                            task["subtitle_error"] = subtitle_exc.as_dict()
                    task["status"] = "completed"
                except YoutubeCliError as exc:
                    task["status"] = "failed"
                    task["error"] = exc.as_dict()
                task["finished_at"] = self._now_iso()
                manifest_entries[task_key] = dict(task)
                self._save_download_manifest(manifest_file, manifest)
                tasks.append(task)
        except Exception as exc:  # pragma: no cover - exercised via CLI tests/mocks
            if isinstance(exc, YoutubeCliError):
                raise
            raise map_provider_error(exc) from exc
        return tasks

    def _download_with_auth_fallback(
        self,
        target: str,
        *,
        opts: dict[str, Any],
        requested_format: str,
        audio_only: bool,
        use_auth: bool,
    ) -> dict[str, Any]:
        try:
            if use_auth:
                return self._call_silently(
                    self._download_one,
                    target,
                    opts=self._silent_auth_attempt_opts(opts),
                    requested_format=requested_format,
                    audio_only=audio_only,
                )
            return self._download_one(
                target,
                opts=opts,
                requested_format=requested_format,
                audio_only=audio_only,
            )
        except YoutubeCliError as exc:
            if not (use_auth and self._should_retry_without_auth(exc)):
                raise
            self._emit_auth_fallback_notice(stage="下载", reason=exc.message)
            try:
                result = self._download_one(
                    target,
                    opts=self._without_auth_opts(opts),
                    requested_format=requested_format,
                    audio_only=audio_only,
                )
                result["auth_fallback"] = {
                    "used": True,
                    "stage": "download",
                    "reason": self._summarize_auth_fallback_reason(exc.message),
                }
                return result
            except YoutubeCliError:
                raise exc

    def _should_retry_without_auth(self, exc: YoutubeCliError) -> bool:
        if exc.code == "provider_error" and "page needs to be reloaded" in exc.message.lower():
            return True
        if exc.code == "unsupported_operation":
            return True
        return False

    def _silent_auth_attempt_opts(self, opts: dict[str, Any]) -> dict[str, Any]:
        auth_opts = dict(opts)
        auth_opts["quiet"] = True
        auth_opts["no_warnings"] = True
        auth_opts["noprogress"] = True
        return auth_opts

    def _without_auth_opts(self, opts: dict[str, Any]) -> dict[str, Any]:
        fallback_opts = dict(opts)
        fallback_opts.pop("cookiefile", None)
        fallback_opts.pop("cookiesfrombrowser", None)
        return fallback_opts

    def _emit_auth_fallback_notice(self, *, stage: str, reason: str) -> None:
        summarized_reason = self._summarize_auth_fallback_reason(reason)
        notice_key = (stage, summarized_reason)
        if notice_key in self._auth_fallback_notice_keys:
            return
        self._auth_fallback_notice_keys.add(notice_key)
        print(
            (
                f"[youtube-cli] 认证链路在{stage}阶段遇到瞬时错误，"
                f"已自动回退到匿名链路继续。原因: {summarized_reason}"
            ),
            file=sys.stderr,
        )

    def _summarize_auth_fallback_reason(self, reason: str) -> str:
        if "page needs to be reloaded" in reason.lower():
            return "认证页面需要刷新"
        return reason

    def _call_silently(self, func, *args: Any, **kwargs: Any) -> Any:
        with contextlib.redirect_stdout(io.StringIO()):
            with contextlib.redirect_stderr(io.StringIO()):
                return func(*args, **kwargs)

    def _download_one(
        self,
        target: str,
        *,
        opts: dict[str, Any],
        requested_format: str,
        audio_only: bool,
    ) -> dict[str, Any]:
        candidate_formats = [requested_format]
        if audio_only and requested_format in {"bestaudio/best", "audio-default"}:
            candidate_formats = DEFAULT_AUDIO_FALLBACKS
        elif not audio_only and requested_format == "bv*+ba/b":
            candidate_formats = DEFAULT_VIDEO_FALLBACKS
        last_error: Exception | None = None
        for candidate_format in candidate_formats:
            candidate_opts = dict(opts)
            candidate_opts["format"] = candidate_format
            try:
                with yt_dlp.YoutubeDL(candidate_opts) as ydl:
                    info = ydl.extract_info(target, download=True)
                    if not isinstance(info, dict):
                        raise YoutubeCliError("provider_error", "下载返回了无法识别的数据结构。", source="yt_dlp")
                    output_path = ydl.prepare_filename(info)
                    if audio_only:
                        output_path = str(Path(output_path).with_suffix(".mp3"))
                    return {
                        "target": {
                            "id": info.get("id"),
                            "url": info.get("webpage_url") or target,
                        },
                        "mode": "audio" if audio_only else "video",
                        "status": "completed",
                        "output_path": output_path,
                        "requested_format": requested_format,
                        "actual_format": info.get("format_id") or candidate_format,
                        "error": None,
                    }
            except Exception as exc:  # pragma: no cover - exercised via live validation
                mapped = exc if isinstance(exc, YoutubeCliError) else map_provider_error(exc)
                last_error = mapped
                if (
                    mapped.code in {"unsupported_operation", "download_failed", "provider_error"}
                    and candidate_format != candidate_formats[-1]
                ):
                    continue
                raise mapped
        if isinstance(last_error, YoutubeCliError):
            raise last_error
        raise YoutubeCliError("download_failed", "下载失败。", source="yt_dlp")

    def _resolve_download_format(
        self,
        *,
        format_selector: str,
        quality: str | None,
        audio_only: bool,
    ) -> str:
        if audio_only or not quality or quality == "best":
            return format_selector
        height = QUALITY_HEIGHTS.get(quality)
        if height is None:
            raise YoutubeCliError(
                "unsupported_operation",
                f"不支持的清晰度选项: {quality}",
                hint=f"可选值: {', '.join(['best', *QUALITY_HEIGHTS])}",
                source="youtube_cli",
            )
        return (
            f"bv*[height<={height}]+ba"
            f"/b[height<={height}]"
            f"/b[ext=mp4][height<={height}]"
            "/22/18"
        )

    def _export_subtitle_files(
        self,
        *,
        target: str,
        output_path: Path,
        subtitle_languages: list[str],
        file_format: str,
        prefer_auto_subtitles: bool,
        use_auth: bool,
    ) -> list[dict[str, Any]]:
        requested_languages = subtitle_languages or ["en"]
        if len(requested_languages) > 2:
            raise YoutubeCliError(
                "unsupported_operation",
                "当前最多同时导出两种字幕语言。",
                hint="单语传一个 `--sub-lang`；双语传两个 `--sub-lang`。",
                source="youtube_cli",
            )
        base_output = output_path.with_suffix("")
        exports: list[dict[str, Any]] = []
        resolved: dict[str, dict[str, Any]] = {}
        missing: list[str] = []
        last_error: YoutubeCliError | None = None

        for language in requested_languages:
            try:
                resolved[language] = self.subtitle_with_fallback(
                    target,
                    language=language,
                    prefer_auto=prefer_auto_subtitles,
                    use_auth=use_auth,
                )
            except YoutubeCliError as exc:
                if exc.code != "subtitle_unavailable":
                    raise
                missing.append(language)
                last_error = exc

        if missing:
            source_track = None
            for language in requested_languages:
                if language in resolved:
                    source_track = resolved[language]
                    break
            if source_track is None:
                try:
                    source_track = self.subtitle_with_fallback(
                        target,
                        language=None,
                        prefer_auto=prefer_auto_subtitles,
                        use_auth=use_auth,
                    )
                except YoutubeCliError as exc:
                    if exc.code == "subtitle_unavailable":
                        return []
                    raise
            translator = build_translator()
            batch_size_raw = os.getenv("YOUTUBE_CLI_TRANSLATION_BATCH_SIZE", "20")
            try:
                batch_size = int(batch_size_raw)
            except ValueError:
                batch_size = 20
            for language in missing:

                translated_segments = translate_segments(
                    translator,
                    source_track["segments"],
                    source_lang=source_track["language"],
                    target_lang=language,
                    batch_size=batch_size,
                )
                resolved[language] = {
                    "video_id": source_track.get("video_id"),
                    "language": language,
                    "kind": "translated",
                    "format": file_format,
                    "segments": translated_segments,
                    "source_language": source_track.get("language"),
                    "provider": getattr(translator, "name", "unknown"),
                }

        for language in requested_languages:
            track = resolved.get(language)
            if not track:
                continue
            subtitle_path = base_output.with_suffix(f".{track['language']}.{file_format}")
            write_subtitle_file(subtitle_path, track["segments"], fmt=file_format)
            exports.append(
                {
                    "path": str(subtitle_path),
                    "language": track["language"],
                    "kind": track.get("kind"),
                    "mode": "single",
                    "format": file_format,
                    "translated": track.get("kind") == "translated",
                    "source_language": track.get("source_language"),
                    "provider": track.get("provider"),
                }
            )
        return exports

    def _parse_subtitle_content(self, content: str, *, ext: str | None) -> list[dict[str, Any]]:
        if ext == "json3":
            return parse_json3(content)
        if ext == "vtt":
            return parse_vtt(content)
        return []

    def _fetch_html(self, url: str) -> str:
        opts = self._base_opts(use_auth=False)
        opts["quiet"] = True
        headers = {"User-Agent": "Mozilla/5.0"}
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                request = yt_dlp.networking.common.Request(url, headers=headers)
                with ydl.urlopen(request) as response:
                    return response.read().decode("utf-8", errors="replace")
        except Exception as exc:  # pragma: no cover - exercised via live validation
            raise map_provider_error(exc) from exc

    def _extract_initial_data(self, html: str) -> dict[str, Any]:
        for pattern in YT_INITIAL_DATA_PATTERNS:
            match = pattern.search(html)
            if match:
                return json.loads(match.group(1))
        raise YoutubeCliError(
            "provider_error",
            "未能从 YouTube 页面中提取 ytInitialData。",
            source="related_provider",
        )

    def _extract_duration_text(self, model: dict[str, Any]) -> str | None:
        overlays = (
            ((model.get("contentImage") or {}).get("thumbnailViewModel") or {})
            .get("overlays", [])
        )
        for overlay in overlays:
            badges = (
                (overlay.get("thumbnailBottomOverlayViewModel") or {})
                .get("badges", [])
            )
            for badge in badges:
                text = (
                    (badge.get("thumbnailBadgeViewModel") or {})
                    .get("text")
                )
                if text:
                    return text
        return None

    def _auth_capabilities(self) -> dict[str, dict[str, Any]]:
        if not self.auth:
            raise YoutubeCliError(
                "auth_required",
                "当前没有可用的登录配置。",
                hint="先运行 `youtube login --browser chrome`。",
                source="yt_dlp",
            )
        results: dict[str, dict[str, Any]] = {}
        for name, target in FEED_URLS.items():
            try:
                info = self._extract(target, flat=True, use_auth=True)
                entries = list(info.get("entries") or [])[:3]
                results[name] = {
                    "accessible": True,
                    "sample_size": len(entries),
                    "sample_title": entries[0].get("title") if entries else None,
                }
            except YoutubeCliError as exc:
                results[name] = {
                    "accessible": False,
                    "error_code": exc.code,
                    "sample_size": 0,
                    "sample_title": None,
                }
        return results

    def _homepage_auth_state(self) -> dict[str, Any]:
        try:
            opts = self._base_opts(use_auth=True)
            opts["quiet"] = True
            with yt_dlp.YoutubeDL(opts) as ydl:
                request = yt_dlp.networking.common.Request(
                    "https://www.youtube.com/",
                    headers={"User-Agent": "Mozilla/5.0"},
                )
                with ydl.urlopen(request) as response:
                    html = response.read().decode("utf-8", errors="replace")
            data = self._extract_initial_data(html)
            topbar = ((data.get("topbar") or {}).get("desktopTopbarRenderer") or {})
            buttons = topbar.get("topbarButtons") or []
            button_kinds = [next(iter(button.keys())) for button in buttons if button]
            sign_in_visible = any(
                "Sign in" in json.dumps(button, ensure_ascii=False)
                for button in buttons
            )
            return {
                "reachable": True,
                "topbar_button_kinds": button_kinds,
                "sign_in_visible": sign_in_visible,
            }
        except Exception as exc:  # pragma: no cover - live path
            mapped = exc if isinstance(exc, YoutubeCliError) else map_provider_error(exc)
            return {
                "reachable": False,
                "error_code": mapped.code,
            }

    def _channel_url(self, target: str) -> str:
        if target.startswith("http"):
            return target
        if target.startswith("@"):
            return f"https://www.youtube.com/{target}"
        if target.startswith("UC"):
            return f"https://www.youtube.com/channel/{target}"
        return f"https://www.youtube.com/{target}"

    def _playlist_url(self, target: str) -> str:
        if target.startswith("http"):
            return target
        return f"https://www.youtube.com/playlist?list={target}"

    def _channel_tab(self, target: str, *, tab: str, limit: int) -> list[dict[str, Any]]:
        url = f"{self._channel_url(target).rstrip('/')}/{tab}"
        info = self._extract(url, flat=True, use_auth=False)
        items = [normalize_feed_item(entry) for entry in list(info.get("entries") or [])[:limit]]
        fallback_channel = {
            "id": info.get("channel_id") or info.get("id"),
            "title": info.get("channel") or info.get("uploader"),
            "handle": info.get("uploader_id"),
        }
        for item in items:
            if not item["channel"].get("id"):
                item["channel"]["id"] = fallback_channel["id"]
            if not item["channel"].get("title"):
                item["channel"]["title"] = fallback_channel["title"]
            if not item["channel"].get("handle"):
                item["channel"]["handle"] = fallback_channel["handle"]
            item["source_feed"] = f"channel_{tab}"
        return items

    def _task_key(self, target: str, *, audio_only: bool) -> str:
        mode = "audio" if audio_only else "video"
        return f"{mode}:{target}"

    def _load_download_manifest(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {
                "schema_version": 1,
                "entries": {},
            }
        return json.loads(path.read_text(encoding="utf-8"))

    def _save_download_manifest(self, path: Path, manifest: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
