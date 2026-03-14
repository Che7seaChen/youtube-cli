from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .errors import YoutubeCliError

VALID_MODES = {"safe", "balanced", "fast"}


@dataclass
class AuthConfig:
    browser: str | None = None
    profile: str | None = None
    container: str | None = None
    cookies_file: str | None = None


@dataclass
class RateLimitConfig:
    sleep_interval: float | None = None
    max_sleep_interval: float | None = None
    sleep_interval_requests: int | None = None
    task_jitter_seconds: float | None = None
    download_rate_limit: str | None = None
    download_throttled_rate: str | None = None
    download_http_chunk_size: str | None = None
    download_concurrent_fragments: int | None = None
    download_fragment_retries: int | None = None


@dataclass
class RetryConfig:
    write_max_attempts: int = 2
    write_backoff_base: float = 1.0
    write_backoff_max: float = 4.0


@dataclass
class AppConfig:
    auth: AuthConfig | None = None
    download_dir: str | None = None
    mode: str = "balanced"
    rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)
    retry: RetryConfig = field(default_factory=RetryConfig)


def _config_dir() -> Path:
    override = os.environ.get("YOUTUBE_CLI_CONFIG_DIR")
    if override:
        return Path(override).expanduser()
    xdg_config = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config:
        return Path(xdg_config).expanduser() / "youtube-cli"
    return Path.home() / ".config" / "youtube-cli"


def config_path() -> Path:
    return _config_dir() / "config.json"


def load_config() -> AppConfig:
    path = config_path()
    if not path.exists():
        return AppConfig()
    raw = json.loads(path.read_text(encoding="utf-8"))
    auth_raw = raw.get("auth")
    auth = AuthConfig(**auth_raw) if auth_raw else None
    rate_raw = raw.get("rate_limit")
    retry_raw = raw.get("retry")
    mode = normalize_mode(raw.get("mode"))
    rate_limit = _parse_dataclass(RateLimitConfig, rate_raw)
    retry = _parse_dataclass(RetryConfig, retry_raw)
    return AppConfig(
        auth=auth,
        download_dir=raw.get("download_dir"),
        mode=mode,
        rate_limit=rate_limit,
        retry=retry,
    )


def save_config(config: AppConfig) -> Path:
    path = config_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(asdict(config), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError as exc:
        raise YoutubeCliError(
            "config_write_failed",
            f"无法写入配置文件: {path}",
            hint="设置 `YOUTUBE_CLI_CONFIG_DIR` 到可写目录，或切换到有权限的环境后重试。",
        ) from exc
    return path


def auth_summary(auth: AuthConfig | None) -> dict[str, object]:
    return {
        "configured": auth is not None,
        "browser": auth.browser if auth else None,
        "profile": auth.profile if auth else None,
        "container": auth.container if auth else None,
        "cookies_file": auth.cookies_file if auth else None,
    }


def normalize_mode(value: str | None) -> str:
    if not value:
        return "balanced"
    normalized = value.strip().lower()
    if normalized not in VALID_MODES:
        return "balanced"
    return normalized


def _parse_dataclass(cls: type, raw: object):
    if not isinstance(raw, dict):
        return cls()
    allowed = {name for name in getattr(cls, "__dataclass_fields__", {}).keys()}
    filtered = {key: value for key, value in raw.items() if key in allowed}
    try:
        return cls(**filtered)
    except TypeError:
        return cls()


def env_flag(name: str) -> bool:
    value = os.environ.get(name, "")
    return value.strip().lower() in {"1", "true", "yes", "on"}
