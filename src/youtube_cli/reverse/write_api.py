from __future__ import annotations

import hashlib
import http.cookiejar
import json
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

import yt_dlp.cookies

from ..config import AuthConfig
from ..errors import YoutubeCliError

YTCFG_RE = re.compile(r"ytcfg\.set\s*\(\s*({.+?})\s*\)\s*;", re.DOTALL)
YT_INITIAL_DATA_PATTERNS = (
    re.compile(r"var ytInitialData = (\{.*?\});", re.DOTALL),
    re.compile(r"ytInitialData\s*=\s*(\{.*?\});", re.DOTALL),
)
VIDEO_ID_RE = re.compile(r"^[0-9A-Za-z_-]{11}$")


@dataclass
class PlaylistEditResult:
    action: str
    target_video_id: str
    playlist_id: str
    playlist_url: str
    dry_run: bool
    response: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "target_video_id": self.target_video_id,
            "playlist_id": self.playlist_id,
            "playlist_url": self.playlist_url,
            "dry_run": self.dry_run,
            "response": self.response,
        }


@dataclass
class PlaylistCreateResult:
    title: str
    description: str | None
    privacy: str
    dry_run: bool
    playlist_id: str | None = None
    playlist_url: str | None = None
    response: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "description": self.description,
            "privacy": self.privacy,
            "dry_run": self.dry_run,
            "playlist_id": self.playlist_id,
            "playlist_url": self.playlist_url,
            "response": self.response,
        }


@dataclass
class PlaylistDeleteResult:
    playlist_id: str
    playlist_url: str
    dry_run: bool
    response: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "playlist_id": self.playlist_id,
            "playlist_url": self.playlist_url,
            "dry_run": self.dry_run,
            "response": self.response,
        }


class YoutubeWriteClient:
    def __init__(self, auth: AuthConfig | None, *, no_check_certificate: bool = False) -> None:
        self.auth = auth
        self.no_check_certificate = no_check_certificate

    def add_to_watch_later(self, target: str, *, dry_run: bool) -> dict[str, Any]:
        return self.add_to_playlist(target, "WL", dry_run=dry_run)

    def add_to_playlist(self, video_target: str, playlist_target: str, *, dry_run: bool) -> dict[str, Any]:
        self._require_auth()
        video_id = self._resolve_video_id(video_target)
        playlist_id = self._resolve_playlist_id(playlist_target)
        result = PlaylistEditResult(
            action="add_video",
            target_video_id=video_id,
            playlist_id=playlist_id,
            playlist_url=f"https://www.youtube.com/playlist?list={playlist_id}",
            dry_run=dry_run,
        )
        if dry_run:
            return result.as_dict()
        response = self._playlist_edit(
            referrer=f"https://www.youtube.com/watch?v={video_id}",
            playlist_id=playlist_id,
            actions=[{"action": "ACTION_ADD_VIDEO", "addedVideoId": video_id}],
        )
        result.response = self._summarize_response(response)
        return result.as_dict()

    def create_playlist(
        self,
        title: str,
        *,
        description: str | None,
        privacy: str,
        dry_run: bool,
    ) -> dict[str, Any]:
        self._require_auth()
        normalized_privacy = self._normalize_privacy(privacy)
        result = PlaylistCreateResult(
            title=title,
            description=description,
            privacy=normalized_privacy,
            dry_run=dry_run,
        )
        if dry_run:
            return result.as_dict()
        response = self._youtubei_call(
            referrer="https://www.youtube.com/",
            endpoint_path="playlist/create",
            body={
                "title": title,
                "description": description or "",
                "privacyStatus": normalized_privacy,
            },
        )
        playlist_id = response.get("playlistId")
        result.playlist_id = playlist_id
        result.playlist_url = f"https://www.youtube.com/playlist?list={playlist_id}" if playlist_id else None
        result.response = self._summarize_response(response)
        return result.as_dict()

    def delete_playlist(self, playlist_target: str, *, dry_run: bool) -> dict[str, Any]:
        self._require_auth()
        playlist_id = self._resolve_playlist_id(playlist_target)
        result = PlaylistDeleteResult(
            playlist_id=playlist_id,
            playlist_url=f"https://www.youtube.com/playlist?list={playlist_id}",
            dry_run=dry_run,
        )
        if dry_run:
            return result.as_dict()
        response = self._youtubei_call(
            referrer=f"https://www.youtube.com/playlist?list={playlist_id}",
            endpoint_path="playlist/delete",
            body={"playlistId": playlist_id},
        )
        result.response = self._summarize_response(response)
        return result.as_dict()

    def _youtubei_call(
        self,
        *,
        referrer: str,
        endpoint_path: str,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        cookie_jar = self._load_cookie_jar()
        opener = self._build_opener(cookie_jar)
        html = self._fetch_html(referrer, opener=opener)
        ytcfg = self._extract_ytcfg(html)
        api_key = ytcfg.get("INNERTUBE_API_KEY")
        context = ytcfg.get("INNERTUBE_CONTEXT")
        if not api_key or not isinstance(context, dict):
            raise YoutubeCliError(
                "provider_error",
                "未能从 YouTube 页面提取写接口所需的 ytcfg 信息。",
                hint="重试 `youtube login --browser chrome --check`，确认当前登录态可用。",
                source="youtube_write",
            )
        endpoint = f"https://www.youtube.com/youtubei/v1/{endpoint_path}?key={api_key}&prettyPrint=false"
        payload = json.dumps({"context": context, **body}).encode("utf-8")
        headers = self._generate_api_headers(cookie_jar, ytcfg=ytcfg, origin="https://www.youtube.com")
        headers.update(
            {
                "Content-Type": "application/json",
                "Referer": referrer,
            }
        )
        request = urllib.request.Request(endpoint, data=payload, headers=headers, method="POST")
        try:
            with opener.open(request) as response:
                raw = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            body_text = exc.read().decode("utf-8", errors="replace")
            raise YoutubeCliError(
                "permission_denied" if exc.code == 403 else "provider_error",
                f"YouTube 写接口请求失败: HTTP {exc.code}",
                hint=body_text[:200] or "检查登录态是否有效，以及目标播放列表是否可写。",
                source="youtube_write",
            ) from exc
        except Exception as exc:
            raise YoutubeCliError(
                "network_error",
                "调用 YouTube 写接口时遇到网络错误。",
                hint="检查网络连通性，或在可访问 YouTube 的环境中重试。",
                source="youtube_write",
            ) from exc
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise YoutubeCliError(
                "provider_error",
                "YouTube 写接口返回了无法解析的响应。",
                hint=raw[:200],
                source="youtube_write",
            ) from exc
        if data.get("error"):
            message = (
                data.get("error", {}).get("message")
                or data.get("error", {}).get("errors", [{}])[0].get("message")
            )
            raise YoutubeCliError(
                "provider_error",
                message or "YouTube 写接口返回错误。",
                source="youtube_write",
            )
        return data

    def _playlist_edit(
        self,
        *,
        referrer: str,
        playlist_id: str,
        actions: list[dict[str, Any]],
    ) -> dict[str, Any]:
        cookie_jar = self._load_cookie_jar()
        opener = self._build_opener(cookie_jar)
        html = self._fetch_html(referrer, opener=opener)
        ytcfg = self._extract_ytcfg(html)
        api_key = ytcfg.get("INNERTUBE_API_KEY")
        context = ytcfg.get("INNERTUBE_CONTEXT")
        if not api_key or not isinstance(context, dict):
            raise YoutubeCliError(
                "provider_error",
                "未能从 YouTube 页面提取写接口所需的 ytcfg 信息。",
                hint="重试 `youtube login --browser chrome --check`，确认当前登录态可用。",
                source="youtube_write",
            )
        endpoint = f"https://www.youtube.com/youtubei/v1/browse/edit_playlist?key={api_key}&prettyPrint=false"
        payload = json.dumps(
            {
                "context": context,
                "playlistId": playlist_id,
                "actions": actions,
            }
        ).encode("utf-8")
        headers = self._generate_api_headers(cookie_jar, ytcfg=ytcfg, origin="https://www.youtube.com")
        headers.update(
            {
                "Content-Type": "application/json",
                "Referer": referrer,
            }
        )
        request = urllib.request.Request(endpoint, data=payload, headers=headers, method="POST")
        try:
            with opener.open(request) as response:
                raw = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            if exc.code == 409 and self._is_add_video_conflict(actions):
                return {
                    "status": "STATUS_ALREADY_EXISTS",
                    "responseContext": {
                        "mainAppWebResponseContext": {
                            "loggedOut": False,
                        }
                    },
                    "error": self._summarize_http_error(body),
                }
            playlist_context = self._describe_playlist_target(playlist_id, opener=opener)
            hint_parts: list[str] = []
            if playlist_context.get("title"):
                hint_parts.append(f"目标 playlist: {playlist_context['title']}")
            if playlist_context.get("owner"):
                hint_parts.append(f"页面所有者: {playlist_context['owner']}")
            if exc.code == 403:
                hint_parts.append("如果这是你收藏的别人的 playlist，而不是当前账号自建列表，YouTube 会返回 403。请改传你自己的 playlist URL/ID。")
            if body:
                hint_parts.append(body[:200])
            raise YoutubeCliError(
                "permission_denied" if exc.code == 403 else "provider_error",
                f"YouTube 写接口请求失败: HTTP {exc.code}",
                hint=" ".join(hint_parts) or "检查登录态是否有效，以及目标播放列表是否可写。",
                source="youtube_write",
            ) from exc
        except Exception as exc:
            raise YoutubeCliError(
                "network_error",
                "调用 YouTube 写接口时遇到网络错误。",
                hint="检查网络连通性，或在可访问 YouTube 的环境中重试。",
                source="youtube_write",
            ) from exc
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise YoutubeCliError(
                "provider_error",
                "YouTube 写接口返回了无法解析的响应。",
                hint=raw[:200],
                source="youtube_write",
            ) from exc
        if data.get("error"):
            message = (
                data.get("error", {}).get("message")
                or data.get("error", {}).get("errors", [{}])[0].get("message")
            )
            raise YoutubeCliError(
                "provider_error",
                message or "YouTube 写接口返回错误。",
                source="youtube_write",
            )
        return data

    def _summarize_response(self, response: dict[str, Any]) -> dict[str, Any]:
        summary: dict[str, Any] = {
            "status": response.get("status"),
            "keys": sorted(response.keys()),
        }
        if response.get("status") == "STATUS_ALREADY_EXISTS":
            summary["already_exists"] = True
        logged_out = response.get("responseContext", {}).get("mainAppWebResponseContext", {}).get("loggedOut")
        if isinstance(logged_out, bool):
            summary["logged_out"] = logged_out
        if response.get("playlistId"):
            summary["playlist_id"] = response["playlistId"]
        return summary

    def _summarize_http_error(self, body_text: str) -> dict[str, Any] | None:
        if not body_text:
            return None
        try:
            data = json.loads(body_text)
        except json.JSONDecodeError:
            return {"raw": body_text[:200]}
        error = data.get("error")
        if not isinstance(error, dict):
            return {"raw": body_text[:200]}
        errors = error.get("errors")
        first_error = errors[0] if isinstance(errors, list) and errors and isinstance(errors[0], dict) else {}
        return {
            "code": error.get("code"),
            "message": error.get("message"),
            "reason": first_error.get("reason"),
            "domain": first_error.get("domain"),
        }

    def _is_add_video_conflict(self, actions: list[dict[str, Any]]) -> bool:
        return any(action.get("action") == "ACTION_ADD_VIDEO" for action in actions if isinstance(action, dict))

    def _generate_api_headers(
        self,
        cookie_jar: http.cookiejar.CookieJar,
        *,
        ytcfg: dict[str, Any],
        origin: str,
    ) -> dict[str, str]:
        context = ytcfg.get("INNERTUBE_CONTEXT") or {}
        client = context.get("client") or {}
        headers = {
            "X-YouTube-Client-Name": str(
                ytcfg.get("INNERTUBE_CONTEXT_CLIENT_NAME") or client.get("clientName") or "1"
            ),
            "X-YouTube-Client-Version": str(
                ytcfg.get("INNERTUBE_CLIENT_VERSION") or client.get("clientVersion") or ""
            ),
            "X-Goog-Visitor-Id": str(ytcfg.get("VISITOR_DATA") or client.get("visitorData") or ""),
            "Origin": origin,
            "User-Agent": str(client.get("userAgent") or self._default_user_agent()),
        }
        delegated_session_id = ytcfg.get("DELEGATED_SESSION_ID")
        session_index = ytcfg.get("SESSION_INDEX")
        user_session_id = ytcfg.get("USER_SESSION_ID")
        if delegated_session_id:
            headers["X-Goog-PageId"] = str(delegated_session_id)
        if delegated_session_id or session_index is not None:
            headers["X-Goog-AuthUser"] = str(session_index if session_index is not None else 0)
        auth = self._get_sid_authorization_header(cookie_jar, origin=origin, user_session_id=user_session_id)
        if auth:
            headers["Authorization"] = auth
            headers["X-Origin"] = origin
        if ytcfg.get("LOGGED_IN"):
            headers["X-Youtube-Bootstrap-Logged-In"] = "true"
        return {key: value for key, value in headers.items() if value}

    def _get_sid_authorization_header(
        self,
        cookie_jar: http.cookiejar.CookieJar,
        *,
        origin: str,
        user_session_id: str | None = None,
    ) -> str | None:
        additional_parts = {"u": str(user_session_id)} if user_session_id else {}
        yt_sapisid = self._cookie_value(cookie_jar, "SAPISID") or self._cookie_value(cookie_jar, "__Secure-3PAPISID")
        yt_1psapisid = self._cookie_value(cookie_jar, "__Secure-1PAPISID")
        yt_3psapisid = self._cookie_value(cookie_jar, "__Secure-3PAPISID")
        authorizations: list[str] = []
        for scheme, sid in (
            ("SAPISIDHASH", yt_sapisid),
            ("SAPISID1PHASH", yt_1psapisid),
            ("SAPISID3PHASH", yt_3psapisid),
        ):
            if sid:
                authorizations.append(self._make_sid_authorization(scheme, sid, origin, additional_parts))
        return " ".join(authorizations) if authorizations else None

    @staticmethod
    def _make_sid_authorization(
        scheme: str,
        sid: str,
        origin: str,
        additional_parts: dict[str, str],
    ) -> str:
        timestamp = str(round(time.time()))
        hash_parts: list[str] = []
        if additional_parts:
            hash_parts.append(":".join(additional_parts.values()))
        hash_parts.extend([timestamp, sid, origin])
        digest = hashlib.sha1(" ".join(hash_parts).encode()).hexdigest()
        parts = [timestamp, digest]
        if additional_parts:
            parts.append("".join(additional_parts))
        return f"{scheme} {'_'.join(parts)}"

    def _extract_ytcfg(self, html: str) -> dict[str, Any]:
        match = YTCFG_RE.search(html)
        if not match:
            raise YoutubeCliError(
                "provider_error",
                "未能从页面中提取 ytcfg。",
                source="youtube_write",
            )
        return json.loads(match.group(1))

    def _extract_initial_data(self, html: str) -> dict[str, Any]:
        for pattern in YT_INITIAL_DATA_PATTERNS:
            match = pattern.search(html)
            if match:
                return json.loads(match.group(1))
        raise YoutubeCliError(
            "provider_error",
            "未能从页面中提取 ytInitialData。",
            source="youtube_write",
        )

    def _describe_playlist_target(
        self,
        playlist_id: str,
        *,
        opener: urllib.request.OpenerDirector,
    ) -> dict[str, str | None]:
        try:
            html = self._fetch_html(f"https://www.youtube.com/playlist?list={playlist_id}", opener=opener)
            data = self._extract_initial_data(html)
        except Exception:
            return {"title": None, "owner": None}
        header = (
            ((data.get("header") or {}).get("pageHeaderRenderer") or {})
            .get("content", {})
            .get("pageHeaderViewModel", {})
        )
        rows = (
            ((header.get("metadata") or {}).get("contentMetadataViewModel") or {})
            .get("metadataRows", [])
        )
        owner: str | None = None
        if rows:
            first_row = rows[0].get("metadataParts", [])
            for part in first_row:
                avatar_text = (
                    ((part.get("avatarStack") or {}).get("avatarStackViewModel") or {})
                    .get("text", {})
                )
                text = self._text_content(avatar_text)
                if text and text.startswith("by "):
                    owner = text.removeprefix("by ").strip()
                    break
        return {
            "title": self._text_content(((header.get("title") or {}).get("dynamicTextViewModel") or {}).get("text", {})),
            "owner": owner,
        }

    def _text_content(self, node: dict[str, Any]) -> str | None:
        if not isinstance(node, dict):
            return None
        content = node.get("content")
        if isinstance(content, str):
            return content
        if "simpleText" in node:
            return node["simpleText"]
        runs = node.get("runs")
        if isinstance(runs, list):
            text = "".join((run.get("text") or "") for run in runs if isinstance(run, dict))
            return text or None
        return None

    def _fetch_html(self, url: str, *, opener: urllib.request.OpenerDirector) -> str:
        request = urllib.request.Request(
            url,
            headers={"User-Agent": self._default_user_agent()},
        )
        try:
            with opener.open(request) as response:
                return response.read().decode("utf-8", errors="replace")
        except urllib.error.URLError as exc:
            reason = exc.reason
            if isinstance(reason, ssl.SSLCertVerificationError):
                raise YoutubeCliError(
                    "tls_error",
                    "访问 YouTube 写接口前置页面时遇到 TLS 证书校验失败。",
                    hint="在当前环境下重试时可显式加 `--no-check-certificate`，例如 `youtube --no-check-certificate playlist-create ... --yes`。",
                    source="youtube_write",
                ) from exc
            raise YoutubeCliError(
                "network_error",
                "访问 YouTube 写接口前置页面时遇到网络错误。",
                hint="检查网络连通性、DNS 或代理设置，然后重试。",
                source="youtube_write",
            ) from exc

    def _load_cookie_jar(self) -> http.cookiejar.CookieJar:
        self._require_auth()
        browser_spec = None
        if self.auth and self.auth.browser:
            browser_spec = self._cookies_from_browser()
        try:
            return yt_dlp.cookies.load_cookies(
                self.auth.cookies_file if self.auth else None,
                browser_spec,
                None,
            )
        except Exception as exc:
            raise YoutubeCliError(
                "auth_required",
                "无法读取浏览器 Cookie，当前登录态不可用于写操作。",
                hint="重新执行 `youtube login --browser chrome --check`，并确保浏览器仍保持登录。",
                source="youtube_write",
            ) from exc

    def _build_opener(self, cookie_jar: http.cookiejar.CookieJar) -> urllib.request.OpenerDirector:
        ssl_context = None
        if self.no_check_certificate:
            ssl_context = ssl._create_unverified_context()
        return urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(cookie_jar),
            urllib.request.HTTPSHandler(context=ssl_context),
        )

    def _resolve_video_id(self, target: str) -> str:
        target = target.strip()
        if VIDEO_ID_RE.fullmatch(target):
            return target
        parsed = urllib.parse.urlparse(target)
        if parsed.netloc in {"www.youtube.com", "youtube.com", "m.youtube.com"}:
            query = urllib.parse.parse_qs(parsed.query)
            if "v" in query:
                return query["v"][0]
        if parsed.netloc == "youtu.be":
            return parsed.path.strip("/").split("/")[-1]
        raise YoutubeCliError(
            "unsupported_operation",
            "当前写操作需要明确的视频 URL 或 11 位 video id。",
            source="youtube_write",
        )

    def _resolve_playlist_id(self, target: str) -> str:
        target = target.strip()
        parsed = urllib.parse.urlparse(target)
        if parsed.netloc in {"www.youtube.com", "youtube.com", "m.youtube.com"}:
            query = urllib.parse.parse_qs(parsed.query)
            if "list" in query:
                return query["list"][0]
        return target

    def _normalize_privacy(self, privacy: str) -> str:
        normalized = privacy.strip().upper()
        if normalized not in {"PUBLIC", "PRIVATE", "UNLISTED"}:
            raise YoutubeCliError(
                "unsupported_operation",
                f"不支持的 playlist 可见性: {privacy}",
                hint="可选值: private, unlisted, public",
                source="youtube_write",
            )
        return normalized

    def _cookie_value(self, cookie_jar: http.cookiejar.CookieJar, name: str) -> str | None:
        for cookie in cookie_jar:
            if cookie.name == name and "youtube.com" in cookie.domain:
                return cookie.value
        return None

    def _cookies_from_browser(self) -> tuple[str, ...] | None:
        if not self.auth or not self.auth.browser:
            return None
        if self.auth.container is not None:
            return (self.auth.browser, self.auth.profile, None, self.auth.container)
        if self.auth.profile is not None:
            return (self.auth.browser, self.auth.profile)
        return (self.auth.browser,)

    def _require_auth(self) -> None:
        if not self.auth:
            raise YoutubeCliError(
                "auth_required",
                "该命令需要有效的 YouTube 登录态。",
                hint="先运行 `youtube login --browser chrome --check`。",
                source="youtube_write",
            )

    @staticmethod
    def _default_user_agent() -> str:
        return (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/136.0.0.0 Safari/537.36"
        )
