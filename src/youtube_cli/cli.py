from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
import webbrowser
from pathlib import Path
from typing import Any

import click

from .config import AppConfig, AuthConfig, auth_summary, config_path, env_flag, load_config, save_config
from .errors import YoutubeCliError
from .output import OutputFormat, emit, emit_error, resolve_output_format
from .providers import YtDlpProvider


class AppContext:
    def __init__(self, output_format: OutputFormat, config: AppConfig, *, no_check_certificate: bool = False) -> None:
        self.output_format = output_format
        self.config = config
        self.no_check_certificate = no_check_certificate

    @property
    def provider(self) -> YtDlpProvider:
        return YtDlpProvider(
            self.config.auth,
            no_check_certificate=self.no_check_certificate,
        )


pass_context = click.make_pass_decorator(AppContext)


def _batch_targets(targets: tuple[str, ...], batch_file: str | None) -> list[str]:
    collected = list(targets)
    if batch_file:
        lines = Path(batch_file).read_text(encoding="utf-8").splitlines()
        collected.extend(line.strip() for line in lines if line.strip() and not line.strip().startswith("#"))
    if not collected:
        raise click.ClickException("至少提供一个 URL/ID，或通过 `--batch-file` 传入批量任务。")
    return collected


def _run(ctx: AppContext, command: str, fn: Any) -> None:
    try:
        data = fn()
    except YoutubeCliError as exc:
        emit_error(exc, command=command, output_format=ctx.output_format)
        return
    emit(data, command=command, output_format=ctx.output_format)


def _run_silently(cmd: list[str]) -> bool:
    try:
        subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except Exception:
        return False


def _open_incognito(browser: str, url: str) -> bool:
    name = (browser or "").lower()
    if sys.platform == "darwin":
        mac_apps = {
            "chrome": ("Google Chrome", ["--incognito"]),
            "google-chrome": ("Google Chrome", ["--incognito"]),
            "edge": ("Microsoft Edge", ["--inprivate"]),
            "msedge": ("Microsoft Edge", ["--inprivate"]),
            "brave": ("Brave Browser", ["--incognito"]),
            "firefox": ("Firefox", ["-private-window"]),
        }
        app = mac_apps.get(name)
        if app:
            app_name, args = app
            return _run_silently(["open", "-a", app_name, "--args", *args, url])
        return False

    if sys.platform.startswith("win"):
        win_targets = {
            "chrome": ["chrome", "--incognito", url],
            "google-chrome": ["chrome", "--incognito", url],
            "edge": ["msedge", "--inprivate", url],
            "msedge": ["msedge", "--inprivate", url],
            "brave": ["brave", "--incognito", url],
            "firefox": ["firefox", "-private-window", url],
        }
        cmd = win_targets.get(name)
        if cmd:
            return _run_silently(["cmd", "/c", "start", "", *cmd])
        return False

    linux_bins = {
        "chrome": ["google-chrome", "chrome", "chromium", "chromium-browser"],
        "google-chrome": ["google-chrome", "chrome"],
        "chromium": ["chromium", "chromium-browser"],
        "edge": ["microsoft-edge", "msedge"],
        "msedge": ["microsoft-edge", "msedge"],
        "brave": ["brave-browser", "brave"],
        "firefox": ["firefox"],
    }
    incognito_args = {
        "chrome": ["--incognito"],
        "google-chrome": ["--incognito"],
        "chromium": ["--incognito"],
        "edge": ["--inprivate"],
        "msedge": ["--inprivate"],
        "brave": ["--incognito"],
        "firefox": ["-private-window"],
    }
    candidates = linux_bins.get(name)
    if not candidates:
        candidates = (
            linux_bins.get("chrome", [])
            + linux_bins.get("edge", [])
            + linux_bins.get("brave", [])
            + linux_bins.get("firefox", [])
        )
    for binary in candidates:
        path = shutil.which(binary)
        if not path:
            continue
        args = incognito_args.get(name) or incognito_args.get(
            "firefox" if "firefox" in binary else "chrome",
            ["--incognito"],
        )
        if _run_silently([path, *args, url]):
            return True
    return False


def _open_login_page(browser: str, *, incognito: bool) -> bool:
    url = "https://www.youtube.com/"
    if incognito and _open_incognito(browser, url):
        return True
    return webbrowser.open(url)


def _is_headless() -> bool:
    if sys.platform == "darwin":
        return False
    if sys.platform.startswith("win"):
        return False
    return not (
        (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
        and shutil.which("xdg-open")
    )


def _require_write_confirmation(yes: bool, dry_run: bool) -> None:
    if yes and dry_run:
        raise click.ClickException("`--yes` 和 `--dry-run` 不能同时使用。")
    if not yes and not dry_run:
        raise click.ClickException("写操作默认受保护。请显式传 `--yes` 执行，或传 `--dry-run` 只做预演。")


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.option("--json", "as_json", is_flag=True, help="输出 JSON envelope。")
@click.option("--yaml", "as_yaml", is_flag=True, help="输出 YAML envelope。")
@click.option(
    "--no-check-certificate",
    is_flag=True,
    help="跳过 TLS 证书校验。仅在受限网络或本机证书链异常时使用。",
)
def main(as_json: bool, as_yaml: bool, no_check_certificate: bool) -> None:
    output_format = resolve_output_format(as_json, as_yaml)
    context = AppContext(
        output_format,
        load_config(),
        no_check_certificate=no_check_certificate or env_flag("YOUTUBE_CLI_NO_CHECK_CERTIFICATE"),
    )
    click.get_current_context().obj = context


@main.command()
@click.option("--check", is_flag=True, help="尝试访问订阅 feed，验证当前登录态是否可用。")
@pass_context
def status(ctx: AppContext, check: bool) -> None:
    def action() -> dict[str, Any]:
        data = {
            "config_path": str(config_path()),
            "auth": auth_summary(ctx.config.auth),
            "provider": ctx.provider.status(),
        }
        if check:
            data["validation"] = ctx.provider.validate_auth()
        return data

    _run(ctx, "status", action)


@main.command()
@click.option("--browser", default="chrome", show_default=True, help="从浏览器读取 Cookie。")
@click.option("--profile", default=None, help="浏览器 profile 名称或路径。")
@click.option("--container", default=None, help="Firefox container 名称。")
@click.option("--cookies", "cookies_file", default=None, type=click.Path(exists=True), help="直接指定 cookies.txt 文件。")
@click.option(
    "--export-cookies",
    "export_cookies",
    default=None,
    type=click.Path(),
    help="从浏览器导出 Netscape cookies.txt 到指定路径（完成登录后按提示继续）。",
)
@click.option(
    "--open-login/--no-open-login",
    default=True,
    show_default=True,
    help="导出 cookies 前是否自动打开 YouTube 登录页。",
)
@click.option(
    "--incognito/--no-incognito",
    default=True,
    show_default=True,
    help="打开登录页时优先使用无痕/隐身窗口（失败则回退到普通窗口）。",
)
@click.option("--yes", is_flag=True, help="跳过导出 cookies 的确认提示。")
@click.option("--check", is_flag=True, help="保存后立即验证登录态。")
@pass_context
def login(
    ctx: AppContext,
    browser: str,
    profile: str | None,
    container: str | None,
    cookies_file: str | None,
    export_cookies: str | None,
    open_login: bool,
    incognito: bool,
    yes: bool,
    check: bool,
) -> None:
    def action() -> dict[str, Any]:
        if export_cookies and cookies_file:
            raise click.ClickException("`--export-cookies` 不能与 `--cookies` 同时使用。")
        export_path = Path(export_cookies).expanduser() if export_cookies else None
        if export_path:
            if not yes:
                confirm = click.confirm(
                    f"将从浏览器导出 cookies 并写入: {export_path}\n继续吗？",
                    default=False,
                )
                if not confirm:
                    return {
                        "saved": False,
                        "exported": False,
                        "cancelled": True,
                    }
            if open_login:
                if _is_headless():
                    click.echo("检测到当前环境可能为无头模式，无法自动打开登录页。")
                    click.echo("请在可登录浏览器的机器导出 cookies，再上传并使用 `youtube login --cookies <path> --check`。")
                    raise YoutubeCliError(
                        "auth_required",
                        "无头环境无法自动引导浏览器登录。",
                        hint="改用 `youtube login --cookies <path> --check`。",
                        source="youtube_cli",
                    )
                opened = _open_login_page(browser, incognito=incognito)
                if not opened:
                    click.echo("无法自动打开浏览器，请手动访问 https://www.youtube.com/ 并登录。")
            click.echo("请完成登录后按 Enter 继续导出 cookies（建议使用无痕/隐身窗口）。")
            click.pause()
            export_auth = AuthConfig(
                browser=browser,
                profile=profile,
                container=container,
                cookies_file=None,
            )
            exporter = ctx.provider.__class__(
                export_auth,
                no_check_certificate=ctx.no_check_certificate,
            )
            export_info = exporter.export_cookies(export_path)
            auth = AuthConfig(
                browser=None,
                profile=None,
                container=None,
                cookies_file=str(export_path),
            )
        else:
            export_info = None
            auth = AuthConfig(
                browser=None if cookies_file else browser,
                profile=profile,
                container=container,
                cookies_file=cookies_file,
            )
        ctx.config.auth = auth
        path = save_config(ctx.config)
        data: dict[str, Any] = {
            "saved": True,
            "config_path": str(path),
            "auth": auth_summary(auth),
            "no_check_certificate": ctx.no_check_certificate,
        }
        if export_info:
            data["cookies_export"] = export_info
        if check:
            data["validation"] = ctx.provider.__class__(
                auth,
                no_check_certificate=ctx.no_check_certificate,
            ).validate_auth()
        return data

    _run(ctx, "login", action)


@main.command()
@pass_context
def whoami(ctx: AppContext) -> None:
    _run(ctx, "whoami", ctx.provider.whoami)


@main.command()
@click.argument("target")
@click.option(
    "--use-auth",
    is_flag=True,
    help="读取视频详情时显式携带浏览器登录态。仅在匿名链路触发限流或受限时使用。",
)
@pass_context
def video(ctx: AppContext, target: str, use_auth: bool) -> None:
    _run(ctx, "video", lambda: ctx.provider.video(target, use_auth=use_auth))


@main.command()
@click.argument("target")
@click.option("--limit", default=20, show_default=True, type=int)
@pass_context
def related(ctx: AppContext, target: str, limit: int) -> None:
    _run(ctx, "related", lambda: ctx.provider.related(target, limit=limit))


@main.command()
@click.argument("target")
@click.option("--limit", default=20, show_default=True, type=int)
@click.option(
    "--sort",
    default="top",
    show_default=True,
    type=click.Choice(["top", "new"]),
    help="评论排序方式。",
)
@click.option(
    "--use-auth",
    is_flag=True,
    help="读取评论时显式携带浏览器登录态。仅在匿名链路触发限流或受限时使用。",
)
@pass_context
def comments(ctx: AppContext, target: str, limit: int, sort: str, use_auth: bool) -> None:
    _run(
        ctx,
        "comments",
        lambda: ctx.provider.comments(target, limit=limit, sort=sort, use_auth=use_auth),
    )


@main.command()
@click.argument("target")
@click.option(
    "--use-auth",
    is_flag=True,
    help="读取格式信息时显式携带浏览器登录态。仅在匿名链路触发限流或受限时使用。",
)
@pass_context
def formats(ctx: AppContext, target: str, use_auth: bool) -> None:
    _run(ctx, "formats", lambda: ctx.provider.formats(target, use_auth=use_auth))


@main.command()
@click.argument("target")
@click.option("--language", default=None, help="字幕语言，如 `en`、`zh-Hans`。")
@click.option("--auto", is_flag=True, help="优先读取自动字幕。")
@click.option("--use-auth", is_flag=True, help="读取字幕时显式携带浏览器登录态。仅在匿名字幕链路触发限流或受限时使用。")
@pass_context
def subtitles(ctx: AppContext, target: str, language: str | None, auto: bool, use_auth: bool) -> None:
    _run(ctx, "subtitles", lambda: ctx.provider.subtitles(target, language=language, auto=auto, use_auth=use_auth))


@main.command()
@click.argument("query")
@click.option("--limit", default=10, show_default=True, type=int)
@click.option(
    "--type",
    "search_type",
    default="video",
    type=click.Choice(["video", "channel", "playlist"]),
    show_default=True,
)
@pass_context
def search(ctx: AppContext, query: str, limit: int, search_type: str) -> None:
    _run(ctx, "search", lambda: ctx.provider.search(query, limit=limit, search_type=search_type))


@main.command()
@click.argument("target")
@click.option("--limit", default=20, show_default=True, type=int)
@pass_context
def channel(ctx: AppContext, target: str, limit: int) -> None:
    _run(ctx, "channel", lambda: ctx.provider.channel(target, limit=limit))


@main.command()
@click.argument("target")
@click.option("--limit", default=20, show_default=True, type=int)
@pass_context
def channel_videos(ctx: AppContext, target: str, limit: int) -> None:
    _run(ctx, "channel-videos", lambda: ctx.provider.channel_videos(target, limit=limit))


@main.command()
@click.argument("target")
@click.option("--limit", default=20, show_default=True, type=int)
@pass_context
def channel_playlists(ctx: AppContext, target: str, limit: int) -> None:
    _run(ctx, "channel-playlists", lambda: ctx.provider.channel_playlists(target, limit=limit))


@main.command()
@click.argument("target")
@click.option("--limit", default=20, show_default=True, type=int)
@pass_context
def playlist(ctx: AppContext, target: str, limit: int) -> None:
    _run(ctx, "playlist", lambda: ctx.provider.playlist(target, limit=limit))


@main.command()
@click.argument("target")
@click.option("--limit", default=20, show_default=True, type=int)
@pass_context
def playlist_videos(ctx: AppContext, target: str, limit: int) -> None:
    _run(ctx, "playlist-videos", lambda: ctx.provider.playlist_videos(target, limit=limit))


@main.command("subscriptions")
@click.option("--limit", default=20, show_default=True, type=int)
@pass_context
def subscriptions_cmd(ctx: AppContext, limit: int) -> None:
    _run(ctx, "subscriptions", lambda: ctx.provider.feed("subscriptions", limit=limit))


@main.command()
@click.option("--limit", default=20, show_default=True, type=int)
@pass_context
def favorites(ctx: AppContext, limit: int) -> None:
    _run(ctx, "favorites", lambda: ctx.provider.feed("favorites", limit=limit))


@main.command("watch-later")
@click.option("--limit", default=20, show_default=True, type=int)
@pass_context
def watch_later_cmd(ctx: AppContext, limit: int) -> None:
    _run(ctx, "watch-later", lambda: ctx.provider.feed("watch_later", limit=limit))


@main.command()
@click.option("--limit", default=20, show_default=True, type=int)
@pass_context
def history(ctx: AppContext, limit: int) -> None:
    _run(ctx, "history", lambda: ctx.provider.feed("history", limit=limit))


@main.command()
@click.option("--limit", default=20, show_default=True, type=int)
@pass_context
def recommendations(ctx: AppContext, limit: int) -> None:
    _run(ctx, "recommendations", lambda: ctx.provider.feed("recommendations", limit=limit))


@main.command()
@click.option("--limit", default=20, show_default=True, type=int)
@pass_context
def notifications(ctx: AppContext, limit: int) -> None:
    _run(ctx, "notifications", lambda: ctx.provider.feed("notifications", limit=limit))


@main.command()
@click.argument("target")
@click.option("--yes", is_flag=True, help="确认执行写操作。")
@click.option("--dry-run", is_flag=True, help="只返回即将执行的动作，不真正修改账号。")
@pass_context
def save_to_watch_later(ctx: AppContext, target: str, yes: bool, dry_run: bool) -> None:
    _require_write_confirmation(yes, dry_run)
    _run(ctx, "save-to-watch-later", lambda: ctx.provider.save_to_watch_later(target, dry_run=dry_run))


@main.command("playlist-add")
@click.argument("target")
@click.argument("playlist")
@click.option("--yes", is_flag=True, help="确认执行写操作。")
@click.option("--dry-run", is_flag=True, help="只返回即将执行的动作，不真正修改账号。")
@pass_context
def playlist_add(ctx: AppContext, target: str, playlist: str, yes: bool, dry_run: bool) -> None:
    _require_write_confirmation(yes, dry_run)
    _run(ctx, "playlist-add", lambda: ctx.provider.playlist_add(target, playlist, dry_run=dry_run))


@main.command("playlist-create")
@click.argument("title")
@click.option("--description", default=None, help="playlist 描述。")
@click.option(
    "--privacy",
    default="private",
    show_default=True,
    type=click.Choice(["private", "unlisted", "public"]),
    help="playlist 可见性。",
)
@click.option("--yes", is_flag=True, help="确认执行写操作。")
@click.option("--dry-run", is_flag=True, help="只返回即将执行的动作，不真正修改账号。")
@pass_context
def playlist_create(
    ctx: AppContext,
    title: str,
    description: str | None,
    privacy: str,
    yes: bool,
    dry_run: bool,
) -> None:
    _require_write_confirmation(yes, dry_run)
    _run(
        ctx,
        "playlist-create",
        lambda: ctx.provider.playlist_create(
            title,
            description=description,
            privacy=privacy,
            dry_run=dry_run,
        ),
    )


@main.command("playlist-delete")
@click.argument("playlist")
@click.option("--yes", is_flag=True, help="确认执行写操作。")
@click.option("--dry-run", is_flag=True, help="只返回即将执行的动作，不真正修改账号。")
@pass_context
def playlist_delete(ctx: AppContext, playlist: str, yes: bool, dry_run: bool) -> None:
    _require_write_confirmation(yes, dry_run)
    _run(ctx, "playlist-delete", lambda: ctx.provider.playlist_delete(playlist, dry_run=dry_run))


@main.command("playlist-download")
@click.argument("playlist")
@click.option("--limit", default=None, type=int, help="最多下载多少条；默认下载当前 playlist 中解析到的全部视频。")
@click.option("--output-dir", default="downloads", show_default=True, type=click.Path(path_type=Path))
@click.option(
    "--format",
    "format_selector",
    default="bv*+ba/b",
    show_default=True,
    help="yt-dlp 格式选择器。默认遵循 yt-dlp 的视频选择逻辑，并接受认证态 client/HLS 路径。",
)
@click.option(
    "--quality",
    type=click.Choice(["best", "2160p", "1440p", "1080p", "720p", "480p", "360p"]),
    default=None,
    help="按清晰度直接选择下载，适合不想手写格式选择器时使用。",
)
@click.option("--write-subs", is_flag=True, help="同时下载字幕。")
@click.option("--sub-lang", "subtitle_languages", multiple=True, help="字幕语言，可重复指定。")
@click.option(
    "--subtitle-format",
    type=click.Choice(["srt", "vtt"]),
    default="srt",
    show_default=True,
    help="字幕文件格式。",
)
@click.option("--prefer-auto-subs", is_flag=True, help="优先使用自动字幕；默认优先人工字幕，失败后再退回自动字幕。")
@click.option("--use-auth", is_flag=True, help="下载时显式携带浏览器登录态。对自建私有 playlist 很有用。")
@click.option("--rate-limit", default=None, help="限速，如 `5M`。")
@click.option("--throttled-rate", default=None, help="低于该速率时视为被限速，可触发 yt-dlp 重新提取下载链路，例如 `100K`。")
@click.option("--http-chunk-size", default=None, help="HTTP 分块大小，例如 `10M`。仅在被服务端限速时尝试。")
@click.option(
    "--concurrent-fragments",
    default=4,
    show_default=True,
    type=int,
    help="DASH/HLS 分片并发数。适度提高可改善速度，但会增加请求并发。",
)
@click.option(
    "--fragment-retries",
    default=10,
    show_default=True,
    type=int,
    help="分片下载重试次数。",
)
@click.option(
    "--downloader",
    "external_downloader",
    default=None,
    help="可选外部下载器，如 `aria2c`。未安装时不要启用。",
)
@click.option(
    "--downloader-args",
    default=None,
    help="透传给外部下载器的参数字符串，例如 `-x 8 -k 1M`。",
)
@click.option(
    "--manifest",
    "manifest_path",
    default=None,
    type=click.Path(path_type=Path),
    help="下载任务 manifest 路径。默认写入 `output_dir/.youtube-cli-manifest.json`。",
)
@click.option("--resume-failed", is_flag=True, help="从 manifest 恢复任务，跳过已完成目标。")
@pass_context
def playlist_download(
    ctx: AppContext,
    playlist: str,
    limit: int | None,
    output_dir: Path,
    format_selector: str,
    quality: str | None,
    write_subs: bool,
    subtitle_languages: tuple[str, ...],
    subtitle_format: str,
    prefer_auto_subs: bool,
    use_auth: bool,
    rate_limit: str | None,
    throttled_rate: str | None,
    http_chunk_size: str | None,
    concurrent_fragments: int,
    fragment_retries: int,
    external_downloader: str | None,
    downloader_args: str | None,
    manifest_path: Path | None,
    resume_failed: bool,
) -> None:
    parameter_source = click.get_current_context().get_parameter_source("format_selector")
    if quality and parameter_source != click.core.ParameterSource.DEFAULT:
        raise click.ClickException("`--quality` 和 `--format` 只能二选一。")

    def action() -> dict[str, Any]:
        items = ctx.provider.playlist_videos(playlist, limit=limit, use_auth=use_auth)
        targets = [item["url"] for item in items if item.get("url")]
        if not targets:
            raise YoutubeCliError(
                "not_found",
                "当前 playlist 没有可下载的视频项。",
                hint="检查 playlist URL/ID 是否正确，或对私有 playlist 加 `--use-auth`。",
                source="youtube_cli",
            )
        tasks = ctx.provider.download(
            targets,
            output_dir=output_dir,
            format_selector=format_selector,
            quality=quality,
            write_subtitles=write_subs,
            subtitle_languages=list(subtitle_languages),
            subtitle_file_format=subtitle_format,
            prefer_auto_subtitles=prefer_auto_subs,
            use_auth=use_auth,
            rate_limit=rate_limit,
            throttled_rate=throttled_rate,
            http_chunk_size=http_chunk_size,
            concurrent_fragments=concurrent_fragments,
            fragment_retries=fragment_retries,
            external_downloader=external_downloader,
            external_downloader_args=shlex.split(downloader_args) if downloader_args else None,
            manifest_path=manifest_path,
            resume_failed=resume_failed,
        )
        return {
            "playlist": playlist,
            "resolved_targets": len(targets),
            "tasks": tasks,
        }

    _run(ctx, "playlist-download", action)


@main.command()
@click.argument("targets", nargs=-1)
@click.option("--batch-file", type=click.Path(exists=True), help="批量任务文件，每行一个 URL/ID。")
@click.option("--output-dir", default="downloads", show_default=True, type=click.Path(path_type=Path))
@click.option(
    "--format",
    "format_selector",
    default="bv*+ba/b",
    show_default=True,
    help="yt-dlp 格式选择器。默认遵循 yt-dlp 的视频选择逻辑，并接受认证态 client/HLS 路径。",
)
@click.option(
    "--quality",
    type=click.Choice(["best", "2160p", "1440p", "1080p", "720p", "480p", "360p"]),
    default=None,
    help="按清晰度直接选择下载，适合不想手写格式选择器时使用。",
)
@click.option("--write-subs", is_flag=True, help="同时下载字幕。")
@click.option("--sub-lang", "subtitle_languages", multiple=True, help="字幕语言，可重复指定。")
@click.option(
    "--subtitle-format",
    type=click.Choice(["srt", "vtt"]),
    default="srt",
    show_default=True,
    help="字幕文件格式。",
)
@click.option("--prefer-auto-subs", is_flag=True, help="优先使用自动字幕；默认优先人工字幕，失败后再退回自动字幕。")
@click.option("--use-auth", is_flag=True, help="下载时显式携带浏览器登录态。仅在公共链路触发 bot check 或受限内容时使用。")
@click.option("--rate-limit", default=None, help="限速，如 `5M`。")
@click.option("--throttled-rate", default=None, help="低于该速率时视为被限速，可触发 yt-dlp 重新提取下载链路，例如 `100K`。")
@click.option("--http-chunk-size", default=None, help="HTTP 分块大小，例如 `10M`。仅在被服务端限速时尝试。")
@click.option(
    "--concurrent-fragments",
    default=4,
    show_default=True,
    type=int,
    help="DASH/HLS 分片并发数。适度提高可改善速度，但会增加请求并发。",
)
@click.option(
    "--fragment-retries",
    default=10,
    show_default=True,
    type=int,
    help="分片下载重试次数。",
)
@click.option(
    "--downloader",
    "external_downloader",
    default=None,
    help="可选外部下载器，如 `aria2c`。未安装时不要启用。",
)
@click.option(
    "--downloader-args",
    default=None,
    help="透传给外部下载器的参数字符串，例如 `-x 8 -k 1M`。",
)
@click.option(
    "--manifest",
    "manifest_path",
    default=None,
    type=click.Path(path_type=Path),
    help="下载任务 manifest 路径。默认写入 `output_dir/.youtube-cli-manifest.json`。",
)
@click.option("--resume-failed", is_flag=True, help="从 manifest 恢复任务，跳过已完成目标。")
@pass_context
def download(
    ctx: AppContext,
    targets: tuple[str, ...],
    batch_file: str | None,
    output_dir: Path,
    format_selector: str,
    quality: str | None,
    write_subs: bool,
    subtitle_languages: tuple[str, ...],
    subtitle_format: str,
    prefer_auto_subs: bool,
    use_auth: bool,
    rate_limit: str | None,
    throttled_rate: str | None,
    http_chunk_size: str | None,
    concurrent_fragments: int,
    fragment_retries: int,
    external_downloader: str | None,
    downloader_args: str | None,
    manifest_path: Path | None,
    resume_failed: bool,
) -> None:
    parameter_source = click.get_current_context().get_parameter_source("format_selector")
    if quality and parameter_source != click.core.ParameterSource.DEFAULT:
        raise click.ClickException("`--quality` 和 `--format` 只能二选一。")
    resolved_targets = _batch_targets(targets, batch_file)
    _run(
        ctx,
        "download",
        lambda: ctx.provider.download(
            resolved_targets,
            output_dir=output_dir,
            format_selector=format_selector,
            quality=quality,
            write_subtitles=write_subs,
            subtitle_languages=list(subtitle_languages),
            subtitle_file_format=subtitle_format,
            prefer_auto_subtitles=prefer_auto_subs,
            use_auth=use_auth,
            rate_limit=rate_limit,
            throttled_rate=throttled_rate,
            http_chunk_size=http_chunk_size,
            concurrent_fragments=concurrent_fragments,
            fragment_retries=fragment_retries,
            external_downloader=external_downloader,
            external_downloader_args=shlex.split(downloader_args) if downloader_args else None,
            manifest_path=manifest_path,
            resume_failed=resume_failed,
        ),
    )


@main.command()
@click.argument("targets", nargs=-1)
@click.option("--batch-file", type=click.Path(exists=True), help="批量任务文件，每行一个 URL/ID。")
@click.option("--output-dir", default="downloads", show_default=True, type=click.Path(path_type=Path))
@click.option(
    "--format",
    "format_selector",
    default="140",
    show_default=True,
    help="音频格式选择器。默认使用更稳定的 YouTube m4a itag 140，可手动覆盖。",
)
@click.option("--write-subs", is_flag=True, help="同时下载字幕。")
@click.option("--sub-lang", "subtitle_languages", multiple=True, help="字幕语言，可重复指定。")
@click.option(
    "--subtitle-format",
    type=click.Choice(["srt", "vtt"]),
    default="srt",
    show_default=True,
    help="字幕文件格式。",
)
@click.option("--prefer-auto-subs", is_flag=True, help="优先使用自动字幕；默认优先人工字幕，失败后再退回自动字幕。")
@click.option("--use-auth", is_flag=True, help="下载时显式携带浏览器登录态。仅在公共链路触发 bot check 或受限内容时使用。")
@click.option("--rate-limit", default=None, help="限速，如 `5M`。")
@click.option("--throttled-rate", default=None, help="低于该速率时视为被限速，可触发 yt-dlp 重新提取下载链路，例如 `100K`。")
@click.option("--http-chunk-size", default=None, help="HTTP 分块大小，例如 `10M`。仅在被服务端限速时尝试。")
@click.option(
    "--concurrent-fragments",
    default=4,
    show_default=True,
    type=int,
    help="DASH/HLS 分片并发数。适度提高可改善速度，但会增加请求并发。",
)
@click.option(
    "--fragment-retries",
    default=10,
    show_default=True,
    type=int,
    help="分片下载重试次数。",
)
@click.option(
    "--downloader",
    "external_downloader",
    default=None,
    help="可选外部下载器，如 `aria2c`。未安装时不要启用。",
)
@click.option(
    "--downloader-args",
    default=None,
    help="透传给外部下载器的参数字符串，例如 `-x 8 -k 1M`。",
)
@click.option(
    "--manifest",
    "manifest_path",
    default=None,
    type=click.Path(path_type=Path),
    help="下载任务 manifest 路径。默认写入 `output_dir/.youtube-cli-manifest.json`。",
)
@click.option("--resume-failed", is_flag=True, help="从 manifest 恢复任务，跳过已完成目标。")
@pass_context
def audio(
    ctx: AppContext,
    targets: tuple[str, ...],
    batch_file: str | None,
    output_dir: Path,
    format_selector: str,
    write_subs: bool,
    subtitle_languages: tuple[str, ...],
    subtitle_format: str,
    prefer_auto_subs: bool,
    use_auth: bool,
    rate_limit: str | None,
    throttled_rate: str | None,
    http_chunk_size: str | None,
    concurrent_fragments: int,
    fragment_retries: int,
    external_downloader: str | None,
    downloader_args: str | None,
    manifest_path: Path | None,
    resume_failed: bool,
) -> None:
    resolved_targets = _batch_targets(targets, batch_file)
    _run(
        ctx,
        "audio",
        lambda: ctx.provider.download(
            resolved_targets,
            output_dir=output_dir,
            format_selector=format_selector,
            audio_only=True,
            write_subtitles=write_subs,
            subtitle_languages=list(subtitle_languages),
            subtitle_file_format=subtitle_format,
            prefer_auto_subtitles=prefer_auto_subs,
            use_auth=use_auth,
            rate_limit=rate_limit,
            throttled_rate=throttled_rate,
            http_chunk_size=http_chunk_size,
            concurrent_fragments=concurrent_fragments,
            fragment_retries=fragment_retries,
            external_downloader=external_downloader,
            external_downloader_args=shlex.split(downloader_args) if downloader_args else None,
            manifest_path=manifest_path,
            resume_failed=resume_failed,
        ),
    )
