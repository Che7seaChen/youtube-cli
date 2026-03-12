from __future__ import annotations


class YoutubeCliError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        hint: str | None = None,
        source: str = "youtube_cli",
        exit_code: int = 1,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.hint = hint
        self.source = source
        self.exit_code = exit_code

    def as_dict(self) -> dict[str, str | None]:
        return {
            "code": self.code,
            "message": self.message,
            "hint": self.hint,
        }


def map_provider_error(exc: Exception) -> YoutubeCliError:
    message = str(exc)
    lowered = message.lower()
    if "login details are needed" in lowered or "cookies" in lowered:
        return YoutubeCliError(
            "auth_required",
            "该命令需要有效的 YouTube 登录态。",
            hint="先运行 `youtube login --browser chrome` 或提供 `--cookies`。",
            source="yt_dlp",
        )
    if "certificate_verify_failed" in lowered or "ssl" in lowered:
        return YoutubeCliError(
            "tls_error",
            "访问 YouTube 时遇到 TLS 证书校验失败。",
            hint="确认系统证书链是否正常；如处于受限网络环境，可显式加 `--no-check-certificate` 再试。",
            source="yt_dlp",
        )
    if "unable to download api page" in lowered or "failed to resolve" in lowered:
        return YoutubeCliError(
            "network_error",
            "无法连接 YouTube，可能是网络、DNS 或代理问题。",
            hint="检查网络连通性，或在可访问 YouTube 的环境中重试。",
            source="yt_dlp",
        )
    if "http error 429" in lowered or "too many requests" in lowered:
        return YoutubeCliError(
            "rate_limited",
            "YouTube 返回了请求限流。",
            hint="稍后重试；如果当前命令支持 `--use-auth`，也可以带登录态再试。",
            source="yt_dlp",
        )
    if "sign in to confirm you’re not a bot" in lowered or "sign in to confirm you're not a bot" in lowered:
        return YoutubeCliError(
            "auth_required",
            "YouTube 要求登录以确认当前请求不是机器人。",
            hint="先运行 `youtube login --browser chrome --check`，然后对该命令加 `--use-auth` 重试。",
            source="yt_dlp",
        )
    if "http error 403" in lowered or "forbidden" in lowered:
        return YoutubeCliError(
            "download_failed",
            "下载被 YouTube 拒绝，通常意味着当前流需要登录态、客户端切换，或该链路本身不稳定。",
            hint="先重试 `--use-auth`，必要时显式指定 `--format`，或改用 `--downloader aria2c`。",
            source="yt_dlp",
        )
    if "requested format is not available" in lowered:
        return YoutubeCliError(
            "unsupported_operation",
            "请求的格式不存在或当前视频不可用。",
            hint="先运行 `youtube formats <url>` 查看可用格式。",
            source="yt_dlp",
        )
    if "requested format not available" in lowered:
        return YoutubeCliError(
            "unsupported_operation",
            "请求的格式不存在或当前视频不可用。",
            hint="先运行 `youtube formats <url>` 查看可用格式。",
            source="yt_dlp",
        )
    if "downloaded file is empty" in lowered:
        return YoutubeCliError(
            "download_failed",
            "下载完成后文件为空，通常意味着所选流不可稳定获取。",
            hint="先重试 `--use-auth`，必要时显式指定 `--format`，或稍后再试。",
            source="yt_dlp",
        )
    if "video unavailable" in lowered or "not available" in lowered:
        return YoutubeCliError(
            "not_found",
            "目标视频或资源不可用。",
            hint="确认 URL/ID 是否正确，或该内容是否受地区/权限限制。",
            source="yt_dlp",
        )
    return YoutubeCliError(
        "provider_error",
        message or exc.__class__.__name__,
        source="yt_dlp",
    )
