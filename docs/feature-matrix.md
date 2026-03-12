# bilibili-cli 到 youtube-cli 功能对照矩阵

本文件的作用不是列功能清单，而是决定第一版做什么、怎么做、哪里该保守、哪里值得逆向。

## 判断标准

- `P0`：第一版必须交付
- `P1`：第一版建议交付
- `P2`：有价值，但可后置
- `R`：当 `yt-dlp` 路线不够时，考虑逆向

实现路径标记：

- `YTDLP`：优先由 `yt-dlp` 支撑
- `WRAP`：CLI 包装与标准化即可
- `REV`：需要逆向或私有接口实验
- `HOLD`：暂缓

## 功能矩阵

| bilibili-cli 能力 | YouTube 等价能力 | 优先级 | 实现路径 | 说明 |
| --- | --- | --- | --- | --- |
| `status` | `youtube status` | P0 | WRAP | 检查保存凭证、浏览器 Cookie、当前可用性 |
| `login` | `youtube login` | P0 | WRAP | 先支持浏览器 Cookie 导入与校验；必要时再研究 OAuth |
| `whoami` | `youtube whoami` | P0 | YTDLP + WRAP | 当前稳定返回登录态能力画像、首页登录态信号、cookie 来源 |
| `video` | `youtube video VIDEO_ID_OR_URL` | P0 | YTDLP | 元数据、章节、标签、统计信息 |
| `video --subtitle` | `youtube video ... --subtitle` | P0 | YTDLP | 优先字幕；支持自动字幕 |
| `video --subtitle-timeline` | `youtube video ... --subtitle-timeline` | P0 | YTDLP | 统一成 transcript schema |
| `video --comments` | `youtube comments VIDEO_ID_OR_URL` | P1 | YTDLP | 已验证 `yt-dlp` 可在受控上限下稳定提取评论 |
| `video --related` | `youtube related VIDEO_ID_OR_URL` | P1 | REV | 已实现为轻量 watch page provider，本质上仍属于隔离的页面解析路径 |
| `video --ai` | `youtube video ... --ai` | P2 | HOLD | CLI 本体先不内置 AI，总结交给上游 agent |
| `audio` | `youtube audio VIDEO_ID_OR_URL` | P0 | YTDLP + WRAP | 音频提取、转码、可选切片 |
| `user` | `youtube channel CHANNEL_ID_OR_HANDLE` | P0 | YTDLP | 频道信息 |
| `user-videos` | `youtube channel-videos ...` | P1 | YTDLP | 已可直接走频道 `/videos` tab |
| `user-playlists` | `youtube channel-playlists ...` | P1 | YTDLP | 已可直接走频道 `/playlists` tab |
| `favorite-list-videos` | `youtube playlist-videos ...` | P1 | YTDLP | 已可直接浏览播放列表中的视频项 |
| 批量下载收藏夹/播放列表 | `youtube playlist-download PLAYLIST` | P1 | YTDLP + WRAP | 已实现。内部先解析 playlist 视频 URL，再复用现有批量下载链路 |
| `following` | `youtube subscriptions` | P0 | YTDLP | 用登录态 feed `:ytsubs` 或订阅列表路径 |
| `search --type user` | `youtube search KEYWORD --type channel` | P0 | YTDLP | 搜索频道 |
| `search --type video` | `youtube search KEYWORD --type video` | P0 | YTDLP | 搜索视频 |
| `hot` | `youtube hot` | HOLD | HOLD | 当前公共 trending 路由语义不稳定，暂不开放，避免把命令定义做脏 |
| `rank` | `youtube hot --sort ...` | P2 | HOLD | YouTube 没有和 B 站完全等价的公开榜单 |
| `feed` | `youtube recommendations` | P1 | YTDLP | 对应 `:ytrec` |
| `favorites` | `youtube favorites` | P1 | YTDLP | 当前映射到 YouTube liked videos（`:ytfav`），这是最稳定的“我的收藏”近似能力 |
| `watch-later` | `youtube watch-later` | P0 | YTDLP | 对应 `:ytwatchlater` |
| `save-to-watch-later` | `youtube save-to-watch-later VIDEO --yes` | P1 | REV | 已实现，逆向层隔离在 `reverse/`，默认需显式确认 |
| `history` | `youtube history` | P0 | YTDLP | 对应 `:ythistory` |
| `my-dynamics` | `youtube notifications` 或我的社区内容 | P2 | YTDLP 或 REV | YouTube 没有完全等价能力 |
| `dynamic-post` | 社区发帖 | P2 | REV | 不进第一版主线 |
| `dynamic-delete` | 删除社区贴文 | P2 | REV | 不进第一版主线 |
| `playlist-add` | `youtube playlist-add VIDEO PLAYLIST --yes` | P1 | REV | 已实现，通用播放列表写入口；当前默认单次操作、显式确认 |
| 创建收藏夹 | `youtube playlist-create TITLE --yes` | P1 | REV | 已实现，当前支持 `private / unlisted / public` |
| 删除收藏夹 | `youtube playlist-delete PLAYLIST --yes` | P1 | REV | 已实现；`playlist-remove` 仍暂缓，因为标准站 playlist 删除单条视频通常需要额外的 `setVideoId` |
| `like` | `youtube like` | P2 | REV | 写操作，高风险 |
| `coin` | 无等价 | HOLD | HOLD | 直接删除，不模拟 |
| `triple` | `like + subscribe + bell` 组合 | HOLD | HOLD | 不做概念硬映射 |
| `unfollow` | `youtube unsubscribe` | P2 | REV | 写操作，高风险 |

## 第一版必须完成的范围

### 账户与认证

- `status`
- `login`
- `whoami`

### 内容读取

- `video`
- `subtitles`
- `formats`
- `channel`
- `playlist`
- `search`

### 下载主线

- `download`
- `audio`
- 批量 manifest
- 断点续传
- 限速
- 失败重试

### 登录态读取

- `favorites`
- `subscriptions`
- `watch-later`
- `history`
- `recommendations`
- `notifications`

## 逆向切入条件

只有在同时满足下面三个条件时，才切入逆向：

1. `yt-dlp` 明确无法实现
2. 该能力对产品价值高
3. 能把风险隔离在单独 provider 内，不污染主干

优先逆向顺序：

1. `comments`
2. `related`
3. 写操作与更深的账户身份信息
4. 写操作

## 结论

`youtube-cli` 第一阶段不应被“全面逆向”绑架。最可靠的路径是：

1. 用 `yt-dlp` 拿下搜索、详情、字幕、下载、登录态 feed
2. 用产品层做稳定 schema、稳定命令面、稳定错误处理
3. 只在高价值缺口上做逆向补洞
