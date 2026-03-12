from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

from .errors import YoutubeCliError


@dataclass
class AuthConfig:
    browser: str | None = None
    profile: str | None = None
    container: str | None = None
    cookies_file: str | None = None


@dataclass
class AppConfig:
    auth: AuthConfig | None = None
    download_dir: str | None = None


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
    return AppConfig(auth=auth, download_dir=raw.get("download_dir"))


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


def env_flag(name: str) -> bool:
    value = os.environ.get(name, "")
    return value.strip().lower() in {"1", "true", "yes", "on"}
