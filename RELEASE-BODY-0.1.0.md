# youtube-cli 0.1.0

`youtube-cli` is a YouTube CLI for browsing videos, channels, playlists, authenticated feeds, and download workflows.

`youtube-cli` 是一个面向真实使用场景的 YouTube CLI，用来查看内容、读取登录态列表、批量下载视频/音频/字幕，以及完成高价值但边界清晰的账号操作。

## Highlights / 版本重点

- Added `playlist-download` for one-command playlist downloads
- Added `playlist-create` and `playlist-delete` to complete playlist workflows
- Download flow now supports quality selection, batch files, manifest resume, bilingual subtitles, and optional `aria2c`
- Subtitle export is decoupled from main downloads: subtitle failure does not fail the main video / audio task
- Repeated `save-to-watch-later` / `playlist-add` operations now return a clear already-exists status instead of exposing a raw HTTP 409
- Authenticated subtitle and download flows follow `yt-dlp` behavior and support `--use-auth` when needed

- 新增 `playlist-download`，可以直接下载整个 playlist
- 新增 `playlist-create` 和 `playlist-delete`，playlist 工作流正式闭环
- 下载链路支持清晰度选择、批量文件、manifest 恢复、双语字幕和可选 `aria2c`
- 字幕导出与主下载解耦，字幕失败不会把视频 / 音频主任务标成失败
- `save-to-watch-later` / `playlist-add` 在重复添加时不再暴露原始 HTTP 409，而是返回清晰的已存在状态
- 认证态字幕与下载链路遵循 `yt-dlp` 的成熟行为，需要时可显式加 `--use-auth`

## What You Can Do / 当前可用能力

- inspect videos, comments, related videos, and formats
- search videos, channels, and playlists
- browse channel pages, channel videos, and channel playlists
- read subscriptions, favorites, watch later, history, recommendations, and notifications
- download video and audio
- export manual subtitles, auto subtitles, and bilingual subtitle files
- run batch downloads with `--batch-file`
- resume unfinished downloads with `--resume-failed`
- download an entire playlist with `playlist-download`
- save a video to watch later
- add a video to a playlist
- create and delete playlists
- use normalized `--yaml` and `--json` output for scripts and agents

- 查看视频、评论、相关推荐和格式信息
- 搜索视频、频道和 playlist
- 浏览频道主页、频道视频和频道 playlist
- 读取订阅、收藏、稍后再看、历史、推荐、通知
- 下载视频和音频
- 导出人工字幕、自动字幕和双语字幕文件
- 通过 `--batch-file` 执行批量下载
- 通过 `--resume-failed` 恢复未完成任务
- 用 `playlist-download` 下载整个 playlist
- 把视频加入稍后再看
- 把视频加入指定 playlist
- 创建和删除 playlist
- 用标准化 `--yaml` / `--json` 输出对接脚本和 agent

## Representative Commands / 代表性命令

```bash
youtube login --browser chrome --check
youtube status --check
youtube search "openai" --type channel --limit 5
youtube video "https://www.youtube.com/watch?v=VIDEO_ID"
youtube subtitles "https://www.youtube.com/watch?v=VIDEO_ID" --language en
youtube download "https://www.youtube.com/watch?v=VIDEO_ID" --quality 360p
youtube download "https://www.youtube.com/watch?v=VIDEO_ID" --write-subs --sub-lang en --sub-lang zh-CN
youtube audio "https://www.youtube.com/watch?v=VIDEO_ID"
youtube playlist-download PLAYLIST_ID --quality 360p
youtube save-to-watch-later "https://www.youtube.com/watch?v=VIDEO_ID" --yes
youtube playlist-create "My Playlist" --privacy private --yes
youtube playlist-add "https://www.youtube.com/watch?v=VIDEO_ID" PLAYLIST_ID --yes
youtube playlist-delete PLAYLIST_ID --yes
```

## Requirements / 依赖

- Python 3.11+
- `ffmpeg`
- `yt-dlp >= 2026.3.3`
- optional / 可选: `aria2c`

## Notes / 使用说明

- public metadata and downloads usually work without login
- authenticated feeds and write actions require browser cookies
- write actions always require explicit `--yes` or `--dry-run`
- subtitles are saved as separate files
- subtitle export failure does not fail the main video / audio download

- 公开内容的读取和下载通常不需要登录
- 登录态 feeds 和写操作需要浏览器 Cookie
- 所有写操作都要求显式 `--yes` 或 `--dry-run`
- 字幕以独立文件保存
- 字幕导出失败不会让主视频 / 音频下载失败

## TLS Certificate Workaround / TLS 证书问题绕行

If your machine has a broken local certificate chain, you can run:

如果当前机器的本地证书链异常，可以这样执行：

```bash
youtube --no-check-certificate status --check
youtube --no-check-certificate playlist-create "Test Playlist" --privacy private --yes
```

Or set this once for the current shell session:

或者给当前 shell 会话设置一次环境变量：

```bash
export YOUTUBE_CLI_NO_CHECK_CERTIFICATE=1
```

## Thanks / 致谢

- [yt-dlp](https://github.com/yt-dlp/yt-dlp)
- [bilibili-cli](https://github.com/jackwener/bilibili-cli)
- [Click](https://click.palletsprojects.com/)
- [Rich](https://github.com/Textualize/rich)
- [FFmpeg](https://ffmpeg.org/)
