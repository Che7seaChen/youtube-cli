# youtube-cli

[![CI](https://github.com/Che7seaChen/youtube-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/Che7seaChen/youtube-cli/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3-blue)
![License](https://img.shields.io/badge/license-Apache%202.0-blue)

A CLI for YouTube — browse videos, channels, playlists, account feeds, and download content from the terminal.

[English](#features) | [中文](#功能特性)

## Features

- 🎬 **Video** — inspect video details, comments, related videos, and available download formats
- 📝 **Subtitles** — fetch manual or auto subtitles, export `srt` / `vtt`, and auto-translate missing languages during downloads (per-language files only)
- 🔍 **Search** — search videos, channels, and playlists by keyword
- 👤 **Channel** — view channel profile, recent videos, and channel playlists
- 📂 **Playlist** — inspect playlist metadata, list playlist videos, and download a whole playlist with one command
- 📰 **Authenticated feeds** — read subscriptions, favorites, watch later, history, recommendations, and notifications
- ⬇️ **Downloads** — download video or audio with quality selection, format selector, batch file input, manifest resume, and optional external downloader support
- 🔐 **Auth-aware workflows** — use browser cookies for private playlists, restricted content, or authenticated feeds
- ✍️ **Account actions** — save to watch later, add a video to a playlist, create playlists, and delete playlists
- 📊 **Structured output** — every command supports normalized `--yaml` or `--json` envelope output

## Installation

Requirements:

- Python 3.11+
- `ffmpeg`
- `yt-dlp >= 2026.3.3`

Optional:

- `aria2c` for faster downloads in some cases

macOS example:

```bash
brew install ffmpeg
# Optional
brew install aria2
```

Install from PyPI:

```bash
uv tool install youtube-cli
# Or
pipx install youtube-cli
```

Install from source:

```bash
git clone git@github.com:Che7seaChen/youtube-cli.git
cd youtube-cli
python -m pip install -e .
youtube --help
```

Upgrade:

```bash
uv tool upgrade youtube-cli
# Or
pipx upgrade youtube-cli
```

> Tip: Keep `yt-dlp` current. YouTube extraction behavior changes frequently, and outdated versions are more likely to fail on formats, subtitles, or authenticated flows.

## Usage

```bash
# Login
youtube login --browser chrome --check

# Inspect a video
youtube video "https://www.youtube.com/watch?v=VIDEO_ID"

# Download with subtitles (auto-translate missing languages if configured)
youtube download "https://www.youtube.com/watch?v=VIDEO_ID" \
  --write-subs --sub-lang en --sub-lang zh-CN

# JSON output
youtube --json video "https://www.youtube.com/watch?v=VIDEO_ID"
```

## Subtitle Translation (AI)

When the requested subtitle language is missing, youtube-cli can translate from an available track and keep timestamps aligned.

Required environment variables:

```bash
export YOUTUBE_CLI_TRANSLATION_PROVIDER=openai
export YOUTUBE_CLI_OPENAI_API_KEY="..."
export YOUTUBE_CLI_OPENAI_MODEL="..."
```

Notes:
- Per-language subtitle files only (no bilingual merge).
- Subtitle text is sent to the translation service.

## Authentication

Auth sources:
- Saved config (`youtube login`)
- Browser cookies
- Cookies file (`youtube login --cookies`)

Auth is required for private/restricted content, account feeds, and write actions.

```bash
youtube login --browser chrome --check
youtube status --check
# Headless/VPS
youtube login --cookies /path/to/cookies.txt --check
```

## 功能特性

- 🎬 **视频** — 查看视频详情、评论、相关推荐，以及当前可下载的格式列表
- 📝 **字幕** — 获取人工字幕或自动字幕，支持导出 `srt` / `vtt`，缺失语言可在下载时自动翻译（仅生成单语文件）
- 🔍 **搜索** — 按关键词搜索视频、频道和 playlist
- 👤 **频道** — 查看频道资料、最新视频和频道下的 playlist
- 📂 **Playlist** — 查看 playlist 信息、列出 playlist 视频，并用单个命令下载整个 playlist
- 📰 **登录态列表** — 读取订阅、收藏、稍后再看、历史、推荐、通知
- ⬇️ **下载** — 下载视频或音频，支持清晰度选择、格式选择器、批量任务、manifest 恢复、外部下载器
- 🔐 **认证工作流** — 使用浏览器 Cookie 访问私有 playlist、受限内容和登录态列表
- ✍️ **账号操作** — 加入稍后再看、把视频加入 playlist、创建 playlist、删除 playlist
- 📊 **结构化输出** — 所有命令都支持标准化 `--yaml` 或 `--json` envelope

## 安装

必需依赖：

- Python 3.11+
- `ffmpeg`
- `yt-dlp >= 2026.3.3`

可选依赖：

- `aria2c`，可在部分场景提升下载速度

macOS 可先安装系统依赖：

```bash
brew install ffmpeg
# 可选
brew install aria2
```

如已经发布至 PyPI，推荐使用隔离安装：

```bash
uv tool install youtube-cli
# 或
pipx install youtube-cli
```

从源码安装：

```bash
git clone git@github.com:Che7seaChen/youtube-cli.git
cd youtube-cli
python -m pip install -e .
youtube --help
```

升级：

```bash
uv tool upgrade youtube-cli
# 或
pipx upgrade youtube-cli
```

> 提示：YouTube 的提取和下载链路变化较快，`yt-dlp` 版本过旧时更容易在格式、字幕或认证链路上失败。

## 用法

```bash
# 登录
youtube login --browser chrome --check

# 查看视频
youtube video "https://www.youtube.com/watch?v=VIDEO_ID"

# 下载并输出字幕（缺失语言会按配置翻译）
youtube download "https://www.youtube.com/watch?v=VIDEO_ID" \
  --write-subs --sub-lang en --sub-lang zh-CN

# JSON 输出
youtube --json video "https://www.youtube.com/watch?v=VIDEO_ID"
```

## 字幕翻译（AI）

当所需字幕语言缺失时，youtube-cli 会基于可用字幕进行翻译并保持时间轴对齐。

必需环境变量：

```bash
export YOUTUBE_CLI_TRANSLATION_PROVIDER=openai
export YOUTUBE_CLI_OPENAI_API_KEY="..."
export YOUTUBE_CLI_OPENAI_MODEL="..."
```

说明：
- 每种语言单独保存字幕文件（不合并双语）。
- 字幕文本会发送到翻译服务。

## 认证

认证来源：
- 本地配置（`youtube login`）
- 浏览器 Cookie
- cookies 文件（`youtube login --cookies`）

私有/受限内容、登录态列表、写操作需要认证。

```bash
youtube login --browser chrome --check
youtube status --check
# 无头环境
youtube login --cookies /path/to/cookies.txt --check
```

## 结构化输出

所有 `--json` / `--yaml` 输出遵循 [SCHEMA.md](./SCHEMA.md) 的统一 envelope。

## FAQ

- 无浏览器环境不要用 `--browser`，改用 `--cookies`。

## 故障排查

- `auth_required` — 先运行 `youtube login --browser chrome --check`，必要时对命令加 `--use-auth`
- `tls_error` — 如处于受限网络环境，可改用 `--no-check-certificate`
- `translation_unavailable` — 未配置翻译服务；设置翻译相关环境变量
- `unsupported_operation`（格式不存在）— 如伴随 JS challenge 提示，配置 `YOUTUBE_CLI_JS_RUNTIMES=node` 与 `YOUTUBE_CLI_REMOTE_COMPONENTS=ejs:github`

## 致谢

- [@yt-dlp/yt-dlp](https://github.com/yt-dlp/yt-dlp) — YouTube 读取、下载、字幕、Cookie 与 client 兼容行为，都建立在其长期验证过的能力之上
- [@jackwener/bilibili-cli](https://github.com/jackwener/bilibili-cli) — 在命令面设计、产品化收口、结构化输出和 README 组织方式上，提供了非常直接且实用的参考
- [@pallets/click](https://github.com/pallets/click) — 用于构建清晰、可组合、可维护的 CLI 命令体系
- [@Textualize/rich](https://github.com/Textualize/rich) — 用于提供更清晰的人类可读终端输出和操作反馈
- [@FFmpeg/FFmpeg](https://github.com/FFmpeg/FFmpeg) — 用于下载链路中的音视频封装、后处理与格式转换
