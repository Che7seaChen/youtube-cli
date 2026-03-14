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
- 🤖 **Agent-friendly safety** — write actions require explicit `--yes` or `--dry-run`

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
# Login & account
youtube status --check
youtube login --browser chrome --check
youtube login --cookies ./cookies.txt --check
youtube whoami
youtube --yaml whoami

# Video metadata
youtube video "https://www.youtube.com/watch?v=VIDEO_ID"
youtube video "https://www.youtube.com/watch?v=VIDEO_ID" --use-auth
youtube comments "https://www.youtube.com/watch?v=VIDEO_ID" --limit 20
youtube comments "https://www.youtube.com/watch?v=VIDEO_ID" --limit 20 --sort new
youtube comments "https://www.youtube.com/watch?v=VIDEO_ID" --limit 20 --use-auth
youtube related "https://www.youtube.com/watch?v=VIDEO_ID" --limit 20
youtube formats "https://www.youtube.com/watch?v=VIDEO_ID"
youtube formats "https://www.youtube.com/watch?v=VIDEO_ID" --use-auth

# Subtitles
youtube subtitles "https://www.youtube.com/watch?v=VIDEO_ID" --language en
youtube subtitles "https://www.youtube.com/watch?v=VIDEO_ID" --language zh-CN --auto
youtube subtitles "https://www.youtube.com/watch?v=VIDEO_ID" --language en --use-auth

# Subtitle Translation (AI)
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

# Search & browse
youtube search "openai" --type video --limit 5
youtube search "openai" --type channel --limit 5
youtube search "openai" --type playlist --limit 5
youtube channel @OpenAI --limit 5
youtube channel-videos @OpenAI --limit 10
youtube channel-playlists @OpenAI --limit 10
youtube playlist PLAYLIST_ID --limit 10
youtube playlist-videos PLAYLIST_ID --limit 10

# Authenticated feeds
youtube subscriptions --limit 20
youtube favorites --limit 20
youtube watch-later --limit 20
youtube history --limit 20
youtube recommendations --limit 20
youtube notifications --limit 20

# Video downloads
youtube download "https://www.youtube.com/watch?v=VIDEO_ID" --quality 1080p
youtube download "https://www.youtube.com/watch?v=VIDEO_ID" --format "bv*+ba/b"
youtube download "https://www.youtube.com/watch?v=VIDEO_ID" --write-subs --sub-lang en --sub-lang zh-CN
youtube download "https://www.youtube.com/watch?v=VIDEO_ID" --write-subs --prefer-auto-subs
youtube download "https://www.youtube.com/watch?v=VIDEO_ID" --use-auth
youtube download --batch-file targets.txt --quality 720p
youtube download --batch-file targets.txt --resume-failed
youtube download "https://www.youtube.com/watch?v=VIDEO_ID" --downloader aria2c --downloader-args "-x 8 -k 1M"

# Audio downloads
youtube audio "https://www.youtube.com/watch?v=VIDEO_ID"
youtube audio "https://www.youtube.com/watch?v=VIDEO_ID" --write-subs --sub-lang en
youtube audio --batch-file targets.txt
youtube audio --batch-file targets.txt --resume-failed

# Playlist workflows
youtube playlist-download PLAYLIST_ID --quality 360p
youtube playlist-download PLAYLIST_ID --limit 5 --write-subs --sub-lang en --sub-lang zh-CN
youtube playlist-download PLAYLIST_ID --use-auth
youtube playlist-add "https://www.youtube.com/watch?v=VIDEO_ID" PLAYLIST_ID --yes
youtube playlist-create "My Playlist" --privacy private --yes
youtube playlist-create "My Playlist" --privacy unlisted --dry-run
youtube playlist-delete PLAYLIST_ID --yes

# Watch later
youtube save-to-watch-later "https://www.youtube.com/watch?v=VIDEO_ID" --yes
youtube save-to-watch-later "https://www.youtube.com/watch?v=VIDEO_ID" --dry-run

# Structured output
youtube --json video "https://www.youtube.com/watch?v=VIDEO_ID"
youtube --yaml search "openai" --type channel --limit 3
youtube --yaml playlist-download PLAYLIST_ID --limit 2 --quality 1080p
```

## Authentication

`youtube-cli` uses a practical auth strategy:

1. **Saved config** — `youtube login` stores browser or `cookies.txt` settings locally
2. **Browser cookies** — Chrome, Firefox, and compatible browsers can be used as the auth source
3. **Command-level auth** — use `--use-auth` only when private, restricted, or authenticated resources require it

Most public metadata and downloads work without login.

Authentication is needed for:

- private or restricted playlists
- subscriptions, favorites, watch later, history, recommendations, notifications
- write actions such as `save-to-watch-later`, `playlist-add`, `playlist-create`, and `playlist-delete`

Recommended flow:

```bash
youtube login --browser chrome --check
youtube status --check
youtube playlist-download PLAYLIST_ID --use-auth
```

Export cookies to a file (no browser extension required):

```bash
youtube login --export-cookies ~/Downloads/youtube-cookies.txt --check
youtube status --check
```

This will open YouTube in your browser and wait for you to finish login. It will try to open an incognito/private window by default and fall back to a normal window if needed. Use `--no-incognito` to disable.

### VPS / Headless Auth (cookies.txt)

If your environment cannot access browser cookies (VPS, CI, openclaw, etc.), use a cookies file:

1. On a machine with a logged-in browser, export a Netscape `cookies.txt`.
   - Prefer a fresh incognito session to reduce cookie rotation.
2. Upload it to the VPS and lock permissions:

```bash
scp cookies.txt vps:/home/USER/youtube-cookies.txt
chmod 600 /home/USER/youtube-cookies.txt
```

3. Point the CLI to the cookies file and verify:

```bash
youtube login --cookies /home/USER/youtube-cookies.txt --check
youtube status --check
```

Use `--use-auth` when a read command requires login. All write actions require a valid auth state.
If the VPS has no GUI login, export cookies on another machine first (see above), then upload the file.

## Structured Output

All `--json` and `--yaml` responses use the normalized envelope defined in [SCHEMA.md](./SCHEMA.md):

```yaml
ok: true
schema_version: 1
source: yt_dlp
command: video
generated_at: "2026-03-13T12:00:00+08:00"
data: {}
error: null
```

This keeps command output stable for both people and automation.

Examples:

- `youtube --yaml video ...`
- `youtube --json search ...`
- `youtube --yaml playlist-download ...`
- `youtube --json playlist-create ... --dry-run`

Write results also use the same envelope, so scripts can reliably check `ok`, `data`, and `error`.

## Use as AI Agent Skill

`youtube-cli` works well as an AI-agent-facing CLI because the command surface is explicit and structured:

- use `--yaml` or `--json` when the agent needs machine-readable output
- use narrower queries such as `--limit` to keep payloads small
- use `playlist-download` instead of manually chaining `playlist-videos` into batch downloads
- use `--dry-run` before write actions when the agent should preview the effect first

Agent output recommendation:

- prefer `--yaml` for machine-readable output when strict JSON is not required
- use `--json` for downstream systems that require exact JSON parsing
- keep read commands narrow with `--limit`
- treat write commands as two-step actions: `--dry-run` first, `--yes` second
- this repository also includes a workspace-ready [`SKILL.md`](./SKILL.md) for agent-oriented use

Recommended patterns:

```bash
youtube --yaml search "openai" --type channel --limit 3
youtube --yaml playlist-videos PLAYLIST_ID --limit 5
youtube --json download --batch-file targets.txt --quality 1080p
youtube playlist-create "Agent Review Queue" --dry-run
```

Release notes and version history:

- [`CHANGELOG.md`](./CHANGELOG.md)
- [`releases/`](./releases)

## FAQ

- In headless or no-browser environments, do not use `--browser`. Use `--cookies` instead.

## Troubleshooting

- `auth_required` — run `youtube login --browser chrome --check`, then retry with `--use-auth` if needed
- `auth_required` (headless) — export cookies on a machine with a browser and use `youtube login --cookies <path> --check`
- `auth_required` (export) — headless environments cannot open a login page; export cookies elsewhere and retry
- `tls_error` — check your local certificate chain; if you are in a restricted network environment, retry with `--no-check-certificate`
- `network_error` — verify network, DNS, proxy, or YouTube reachability
- `rate_limited` — reduce request frequency and retry later; for some cases, using `--use-auth` helps
- `download_failed` — inspect formats with `youtube formats <url>`, retry with `--use-auth`, or try `aria2c`
- `not_found` — verify the video, playlist, or channel URL / ID

For download workflows:

- subtitles are saved as separate files
- subtitle export failure does not mark the main video / audio download as failed
- `--resume-failed` reuses the local manifest and skips finished targets

TLS workaround examples:

```bash
youtube --no-check-certificate status --check
youtube --no-check-certificate playlist-create "Test Playlist" --privacy private --yes
```

Or set it once for the current shell session:

```bash
export YOUTUBE_CLI_NO_CHECK_CERTIFICATE=1
```

## Acknowledgements

- [@yt-dlp/yt-dlp](https://github.com/yt-dlp/yt-dlp) — the primary upstream foundation for YouTube extraction, download behavior, subtitles, cookies, and client compatibility handling
- [@jackwener/bilibili-cli](https://github.com/jackwener/bilibili-cli) — a strong reference for CLI product framing, command surface design, structured output, and README organization
- [@pallets/click](https://github.com/pallets/click) — the command-line framework used to keep the command tree explicit, composable, and maintainable
- [@Textualize/rich](https://github.com/Textualize/rich) — terminal rendering support for cleaner human-readable output and clearer operator feedback
- [@FFmpeg/FFmpeg](https://github.com/FFmpeg/FFmpeg) — media muxing, post-processing, and format conversion support across download workflows

---

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
- 🤖 **适合 Agent** — 写操作必须显式 `--yes` 或 `--dry-run`，更适合自动化调用

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
# 登录与账号
youtube status --check
youtube login --browser chrome --check
youtube login --cookies ./cookies.txt --check
youtube whoami
youtube --yaml whoami

# 视频信息
youtube video "https://www.youtube.com/watch?v=VIDEO_ID"
youtube video "https://www.youtube.com/watch?v=VIDEO_ID" --use-auth
youtube comments "https://www.youtube.com/watch?v=VIDEO_ID" --limit 20
youtube comments "https://www.youtube.com/watch?v=VIDEO_ID" --limit 20 --sort new
youtube comments "https://www.youtube.com/watch?v=VIDEO_ID" --limit 20 --use-auth
youtube related "https://www.youtube.com/watch?v=VIDEO_ID" --limit 20
youtube formats "https://www.youtube.com/watch?v=VIDEO_ID"
youtube formats "https://www.youtube.com/watch?v=VIDEO_ID" --use-auth

# 字幕
youtube subtitles "https://www.youtube.com/watch?v=VIDEO_ID" --language en
youtube subtitles "https://www.youtube.com/watch?v=VIDEO_ID" --language zh-CN --auto
youtube subtitles "https://www.youtube.com/watch?v=VIDEO_ID" --language en --use-auth

# 字幕翻译（AI）
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

# 搜索与浏览
youtube search "openai" --type video --limit 5
youtube search "openai" --type channel --limit 5
youtube search "openai" --type playlist --limit 5
youtube channel @OpenAI --limit 5
youtube channel-videos @OpenAI --limit 10
youtube channel-playlists @OpenAI --limit 10
youtube playlist PLAYLIST_ID --limit 10
youtube playlist-videos PLAYLIST_ID --limit 10

# 登录态列表
youtube subscriptions --limit 20
youtube favorites --limit 20
youtube watch-later --limit 20
youtube history --limit 20
youtube recommendations --limit 20
youtube notifications --limit 20

# 视频下载
youtube download "https://www.youtube.com/watch?v=VIDEO_ID" --quality 1080p
youtube download "https://www.youtube.com/watch?v=VIDEO_ID" --format "bv*+ba/b"
youtube download "https://www.youtube.com/watch?v=VIDEO_ID" --write-subs --sub-lang en --sub-lang zh-CN
youtube download "https://www.youtube.com/watch?v=VIDEO_ID" --write-subs --prefer-auto-subs
youtube download "https://www.youtube.com/watch?v=VIDEO_ID" --use-auth
youtube download --batch-file targets.txt --quality 720p
youtube download --batch-file targets.txt --resume-failed
youtube download "https://www.youtube.com/watch?v=VIDEO_ID" --downloader aria2c --downloader-args "-x 8 -k 1M"

# 音频下载
youtube audio "https://www.youtube.com/watch?v=VIDEO_ID"
youtube audio "https://www.youtube.com/watch?v=VIDEO_ID" --write-subs --sub-lang en
youtube audio --batch-file targets.txt
youtube audio --batch-file targets.txt --resume-failed

# Playlist 工作流
youtube playlist-download PLAYLIST_ID --quality 360p
youtube playlist-download PLAYLIST_ID --limit 5 --write-subs --sub-lang en --sub-lang zh-CN
youtube playlist-download PLAYLIST_ID --use-auth
youtube playlist-add "https://www.youtube.com/watch?v=VIDEO_ID" PLAYLIST_ID --yes
youtube playlist-create "My Playlist" --privacy private --yes
youtube playlist-create "My Playlist" --privacy unlisted --dry-run
youtube playlist-delete PLAYLIST_ID --yes

# 稍后再看
youtube save-to-watch-later "https://www.youtube.com/watch?v=VIDEO_ID" --yes
youtube save-to-watch-later "https://www.youtube.com/watch?v=VIDEO_ID" --dry-run

# 结构化输出
youtube --json video "https://www.youtube.com/watch?v=VIDEO_ID"
youtube --yaml search "openai" --type channel --limit 3
youtube --yaml playlist-download PLAYLIST_ID --limit 2 --quality 1080p
```

## 认证

`youtube-cli` 认证策略：

1. **本地已保存配置** — `youtube login` 会把浏览器或 `cookies.txt` 的设置保存到本地
2. **浏览器 Cookie** — 可以把 Chrome、Firefox 等浏览器作为认证来源
3. **命令级认证** — 只有在私有、受限或登录态资源确实需要时，才对命令显式加 `--use-auth`

大多数公开视频的读取和下载不需要登录。

下列场景需要认证：

- 私有或受限 playlist
- 订阅、收藏、稍后再看、历史、推荐、通知
- `save-to-watch-later`、`playlist-add`、`playlist-create`、`playlist-delete` 这类写入操作

推荐流程：

```bash
youtube login --browser chrome --check
youtube status --check
youtube playlist-download PLAYLIST_ID --use-auth
```

导出 cookies 文件（无需浏览器插件）：

```bash
youtube login --export-cookies ~/Downloads/youtube-cookies.txt --check
youtube status --check
```

命令会打开 YouTube 登录页并等待确认，默认尝试无痕/隐身窗口，失败则回退到普通窗口。可用 `--no-incognito` 关闭。

### VPS / 无头环境认证（cookies.txt）

当环境无法读取浏览器 Cookie（VPS、CI、openclaw 等）时，使用 cookies 文件：

1. 在已登录的本机浏览器导出 Netscape `cookies.txt`。
   - 建议用新的无痕/隐身会话导出，降低 cookie 旋转风险。
2. 上传到 VPS 并限制权限：

```bash
scp cookies.txt vps:/home/USER/youtube-cookies.txt
chmod 600 /home/USER/youtube-cookies.txt
```

3. 让 CLI 读取 cookies 并验证：

```bash
youtube login --cookies /home/USER/youtube-cookies.txt --check
youtube status --check
```

读取类命令仅在需要时加 `--use-auth`；写操作必须有有效登录态。
如果 VPS 无法进行 GUI 登录，请先在其他机器导出 cookies 再上传。

## 结构化输出

所有 `--json` 和 `--yaml` 输出都遵循 [SCHEMA.md](./SCHEMA.md) 定义的统一 envelope：

```yaml
ok: true
schema_version: 1
source: yt_dlp
command: video
generated_at: "2026-03-13T12:00:00+08:00"
data: {}
error: null
```

好处在于：

- 默认输出尽量直接可读
- 脚本和 AI agent 可稳定读取 `ok / data / error`
- 不会直接把上游原始返回结构暴露到命令层

常见用法：

- `youtube --yaml video ...`
- `youtube --json search ...`
- `youtube --yaml playlist-download ...`
- `youtube --json playlist-create ... --dry-run`

写操作的结果也使用同一套 envelope，脚本可以统一判断 `ok`、`data` 和 `error`。

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
