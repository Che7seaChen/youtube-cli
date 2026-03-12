# youtube-cli Schema Draft

本文件定义 CLI 的稳定输出协议。目标是让命令层输出对用户和 AI agent 都稳定，不受底层 provider 波动影响。

## 总原则

- 默认人类可读输出
- `--yaml` 与 `--json` 输出标准化 envelope
- schema 稳定优先于 provider 完整字段
- provider 原始响应只作为调试信息存在，不进入默认 schema

## Envelope

所有结构化输出统一为：

```yaml
ok: true
schema_version: 1
source: yt_dlp
command: video
generated_at: "2026-03-11T00:00:00+08:00"
data: {}
error: null
```

失败时：

```yaml
ok: false
schema_version: 1
source: yt_dlp
command: video
generated_at: "2026-03-11T00:00:00+08:00"
data: null
error:
  code: auth_required
  message: Login is required for this command
  hint: Run `youtube login` or provide browser cookies
```

## 通用字段

- `schema_version`: 当前固定为 `1`
- `source`: `yt_dlp`、`reverse`、`cache`
- `command`: 当前命令名
- `generated_at`: ISO 8601 时间

## 核心实体

### Video

```yaml
id: "dQw4w9WgXcQ"
url: "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
title: "Example"
description: "..."
channel:
  id: "UC..."
  title: "Channel Name"
  handle: "@channel"
duration_seconds: 213
published_at: "2024-01-01T12:00:00Z"
view_count: 123456
like_count: 7890
comment_count: 456
tags:
  - "music"
is_live: false
availability: "public"
thumbnails:
  - url: "https://..."
chapters:
  - title: "Intro"
    start_seconds: 0
    end_seconds: 30
subtitles_available:
  manual: true
  auto: true
```

### Channel

```yaml
id: "UC..."
title: "Channel Name"
handle: "@channel"
url: "https://www.youtube.com/@channel"
description: "..."
subscriber_count: 100000
video_count: 200
is_verified: true
avatar_url: "https://..."
recent_items:
  - type: "video"
    id: "dQw4w9WgXcQ"
    title: "Latest video"
tab_previews:
  videos:
    - type: "video"
      id: "dQw4w9WgXcQ"
      title: "Latest video"
  playlists:
    - type: "playlist"
      id: "PL..."
      title: "Featured playlist"
tab_status:
  videos:
    available: true
    sample_size: 3
  playlists:
    available: true
    sample_size: 3
```

### Playlist

```yaml
id: "PL..."
title: "Playlist"
url: "https://www.youtube.com/playlist?list=PL..."
channel:
  id: "UC..."
  title: "Channel Name"
item_count: 30
items:
  - id: "dQw4w9WgXcQ"
    title: "Example"
    duration_seconds: 213
```

### Transcript

```yaml
video_id: "dQw4w9WgXcQ"
language: "en"
kind: "manual"
format: "vtt"
segments:
  - start_seconds: 0.0
    end_seconds: 2.5
    text: "Hello world"
```

### Format

```yaml
video_id: "dQw4w9WgXcQ"
formats:
  - format_id: "137"
    ext: "mp4"
    resolution: "1080p"
    vcodec: "avc1"
    acodec: "none"
    fps: 30
    filesize: 123456789
```

### FeedItem

```yaml
type: "video"
id: "dQw4w9WgXcQ"
title: "Example"
url: "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
channel:
  id: "UC..."
  title: "Channel Name"
  handle: "@channel"
published_at: "2024-01-01T12:00:00Z"
thumbnail_url: "https://i.ytimg.com/vi/.../hqdefault.jpg"
view_count: 123456
source_feed: "notifications"
```

### WhoAmI

```yaml
provider: "yt_dlp"
auth_configured: true
auth_mode: "browser"
browser: "chrome"
profile: null
container: null
cookies_file: null
no_check_certificate: false
authenticated: true
capabilities:
  subscriptions:
    accessible: true
    sample_size: 3
    sample_title: "Example video"
  notifications:
    accessible: true
    sample_size: 3
    sample_title: "Breaking News"
homepage:
  reachable: true
  topbar_button_kinds:
    - "buttonRenderer"
    - "notificationTopbarButtonRenderer"
  sign_in_visible: false
```

### Comment

```yaml
id: "Ugz..."
text: "can confirm: he never gave us up"
author: "@YouTube"
author_id: "UCBR8-60-B28hp2BmDPdntcQ"
author_url: "https://www.youtube.com/@YouTube"
like_count: 195000
is_pinned: true
is_favorited: true
parent: "root"
timestamp: 1746921600
```

### DownloadTask

```yaml
task_id: "dl_001"
target:
  id: "dQw4w9WgXcQ"
  url: "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
mode: "video"
status: "completed"
output_path: "/abs/path/file.mp4"
requested_format: "bestvideo+bestaudio"
actual_format: "137+140"
subtitle_files:
  - path: "/abs/path/file.en.srt"
    language: "en"
    kind: "manual"
    mode: "single"
    format: "srt"
subtitle_error: null
started_at: "2026-03-11T00:00:00+08:00"
finished_at: "2026-03-11T00:01:00+08:00"
manifest_path: "/abs/path/manifest.json"
skipped: false
resumed_from_manifest: false
error: null
```

### PlaylistEditResult

```yaml
action: "add_video"
target_video_id: "dQw4w9WgXcQ"
playlist_id: "WL"
playlist_url: "https://www.youtube.com/playlist?list=WL"
dry_run: false
response:
  status: "STATUS_SUCCEEDED"
  keys:
    - "status"
    - "playlistEditResults"
```

### PlaylistCreateResult

```yaml
title: "My Playlist"
description: "temporary validation"
privacy: "PRIVATE"
dry_run: false
playlist_id: "PL..."
playlist_url: "https://www.youtube.com/playlist?list=PL..."
response:
  status: null
  logged_out: false
  playlist_id: "PL..."
  keys:
    - "playlistId"
    - "responseContext"
```

### PlaylistDeleteResult

```yaml
playlist_id: "PL..."
playlist_url: "https://www.youtube.com/playlist?list=PL..."
dry_run: false
response:
  status: null
  logged_out: false
  keys:
    - "command"
    - "responseContext"
```

## 错误码草案

- `auth_required`
- `auth_invalid`
- `not_found`
- `rate_limited`
- `geo_blocked`
- `download_failed`
- `tls_error`
- `subtitle_unavailable`
- `unsupported_operation`
- `provider_error`
- `network_error`

## 设计备注

- `video` 命令可以通过参数扩展输出字幕、评论、相关推荐，但顶层实体保持 `Video`
- `download` 命令输出 `DownloadTask` 或 `DownloadTask[]`
  - `subtitle_files` 与 `subtitle_error` 只描述附加字幕导出结果，不影响视频/音频主任务的成功判定
- `save-to-watch-later` 与 `playlist-add` 输出 `PlaylistEditResult`
- `playlist-create` 输出 `PlaylistCreateResult`
- `playlist-delete` 输出 `PlaylistDeleteResult`
- `subtitles` 命令输出 `Transcript`
- `comments` 命令输出 `Comment[]`
- `search`、`favorites`、`subscriptions`、`watch-later`、`history`、`recommendations`、`notifications` 输出 `FeedItem[]`
- `whoami` 命令输出 `WhoAmI`
- `playlist-videos` 命令输出 `FeedItem[]`
