# youtube-cli 0.1.1

`youtube-cli` 0.1.1 is a patch release focused on write-path stability and release polish.

`youtube-cli` 0.1.1 是一个补丁版本，重点收口写操作的幂等行为和发布文档。

## Fixes / 修复

- repeated `save-to-watch-later` and `playlist-add` requests no longer surface raw HTTP 409 errors
- duplicate add operations now return a clearer already-exists style status in the write response
- release docs and acknowledgements were cleaned up for public release

- `save-to-watch-later` 和 `playlist-add` 在重复添加时，不再暴露原始 HTTP 409
- 重复添加现在会返回更清晰的“已存在”状态，便于脚本和 agent 处理
- 发布文档和致谢名单已补齐并收口

## What Stays the Same / 保持不变

- search videos, channels, and playlists
- inspect video details, comments, related videos, and formats
- read subscriptions, favorites, watch later, history, recommendations, and notifications
- download video, audio, subtitles, and bilingual subtitle files
- batch downloads, playlist downloads, and resume via manifest
- create playlists, add videos to playlists, delete playlists

- 搜索视频、频道和 playlist
- 查看视频详情、评论、相关推荐和格式信息
- 读取订阅、收藏、稍后再看、历史、推荐、通知
- 下载视频、音频、字幕和双语字幕文件
- 批量下载、整 playlist 下载、manifest 恢复
- 创建 playlist、把视频加入 playlist、删除 playlist

## Representative Commands / 代表性命令

```bash
youtube login --browser chrome --check
youtube search "macbook neo" --type video --limit 10
youtube save-to-watch-later "https://www.youtube.com/watch?v=VIDEO_ID" --yes
youtube playlist-add "https://www.youtube.com/watch?v=VIDEO_ID" PLAYLIST_ID --yes
youtube playlist-download PLAYLIST_ID --quality 360p
youtube playlist-create "test" --privacy private --yes
```

## Requirements / 依赖

- Python 3.11+
- `ffmpeg`
- `yt-dlp >= 2026.3.3`
- optional / 可选: `aria2c`

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

- [@yt-dlp/yt-dlp](https://github.com/yt-dlp/yt-dlp) — the upstream foundation for YouTube extraction, downloads, subtitles, cookies, and client compatibility
- [@jackwener/bilibili-cli](https://github.com/jackwener/bilibili-cli) — a practical reference for command design, structured output, and public-facing CLI documentation
- [@pallets/click](https://github.com/pallets/click) — the command-line framework used to shape the CLI surface
- [@Textualize/rich](https://github.com/Textualize/rich) — terminal rendering support for readable operator output
- [@FFmpeg/FFmpeg](https://github.com/FFmpeg/FFmpeg) — media post-processing and format handling
