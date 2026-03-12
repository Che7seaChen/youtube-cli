# FORCodex

## 这是什么

这是 `youtube-cli` 项目的工程复盘文档起始版本。它不是交付物包装文案，而是给未来维护者看的“人话说明书”。

如果要在新线程里继续接手本项目，先读：

- `/Users/che7seachen/Projects/youtube-cli/HANDOFF-Codex-20260313.md`

## 项目目标

这个项目的目标很明确：

- 做一个真正可用的 YouTube CLI
- 第一版就把登录态和下载主线做扎实
- 使用方式尽量向 `bilibili-cli` 靠拢
- 底层优先复用成熟能力，不轻易陷入高维护逆向

通俗一点说，这个项目不该像一把只会开一次的锁匠工具，而应该像一把你愿意每天放在口袋里的瑞士军刀。

## 当前架构判断

现在最可靠的判断是双层：

- 上层是产品层，负责命令、输出、错误处理、用户体验
- 下层是 provider 层，先用 `yt-dlp`，缺口再用逆向 provider 补

这个选择的好处是，真正会变的是 YouTube 的抓取方式，不是我们对外承诺的 CLI 契约。把变化挡在 provider 里，命令面才可能长期稳定。

## 为什么不一开始就全面逆向

因为那样很容易把项目带进一个错误方向：

- 交付速度慢
- 维护成本高
- 每次接口变动都要修主干
- 用户拿不到第一版可用产品

逆向不是禁区，但必须是“补洞工具”，不能是默认路径。

## 第一阶段最重要的工程决策

1. 先定命令面，再写代码
2. 先定 schema，再接 provider
3. 下载是主线，不是边角料
4. 登录态能力第一版就进
5. 写操作默认保守

## 潜在坑

- YouTube 登录态能力并不都一样稳定，通知、推荐、历史这类 feed 可能比公开视频详情更脆
- 评论和相关推荐可能需要单独补 provider
- 批量下载如果不做任务恢复，会很快变成一次性脚本

## 当前状态

当前已经进入“可运行骨架”阶段。已经完成的关键工作：

- 明确最终目标是产品级 CLI，而不是 demo
- 明确第一版就纳入登录态和下载主线
- 明确以 `bilibili-cli` 为对照蓝本
- 明确默认技术路线是 `yt-dlp + 产品层 + 必要时逆向`
- 建立了 `click` CLI 骨架
- 建立了配置层、输出层、错误层、provider 层
- 打通了 `status / login / whoami / video / formats / subtitles / search / channel / playlist / subscriptions / watch-later / history / recommendations / notifications / download / audio`
- 补了最小自动化测试，并在当前环境跑通
- 做了第二阶段真实联调，不再只是本地假数据
- 根据实测新增了 `--no-check-certificate`
- 根据实测把公共读取/下载默认改成无认证路径，登录态只用于 feed 与账号相关命令
- 根据实测把音频默认格式收敛到更稳定的 `140`
- 根据实测把自动字幕改成 `json3` 优先解析
- 根据实测确认 `comments` 可先走 `yt-dlp`
- 根据实测确认 `related` 可以先用隔离的 watch page provider 实现，不必一开始做更重的逆向
- 根据实测把 `whoami` 从“伪账户信息”校准为“登录态能力画像”
- 根据实测为 feed 项统一补上 `source_feed`、缩略图和可用的观看量字段
- 根据实测给 `download` / `audio` 增加 manifest 恢复能力，已完成项可以被跳过，失败项会落盘等待重试
- 根据实测确认 `channel-videos` / `channel-playlists` 可以直接复用 `yt-dlp` 的频道 tab，不必走逆向
- 根据实测确认 `playlist-videos` 也可以直接复用 `yt-dlp` 的播放列表提取，不必额外造分页抽象
- 根据 `yt-dlp` 本地 extractor 确认并实装 `favorites`，当前映射到 liked videos（`:ytfav`），不去硬做“我创建的所有播放列表”
- 根据实测确认当前公共 `trending` 路由不稳定，因此把 `hot` 暂缓，而不是强行上线一个语义模糊的命令
- 根据实测把 `channel` 升级成聚合视图，直接返回基础信息、近期视频和 tab 预览
- 把所有逆向逻辑显式隔离到 `src/youtube_cli/reverse/`，不让下载/读取主线直接依赖逆向细节
- 下载主线新增 `--quality`、字幕文件导出、双语字幕合并、`--use-auth`、运行时依赖探测
- 下载默认策略现已回到 `yt-dlp` 的主路径：接受认证态下的 client 切换和 HLS 结果，不再额外屏蔽 `m3u8_native`
- 发布前把 `yt-dlp` 依赖下限提升到 `2026.3.3`，避免新安装环境落到上游已判定“超过 90 天”的旧版本
- 逆向实现并实测打通了 `save-to-watch-later`、`playlist-add`、`playlist-create`、`playlist-delete`
- 新增了 `playlist-download`，把“先列 playlist 视频再手工喂给批量下载”的两步工作流收成了一个 agent 友好的单命令
- 修掉了 `download --use-auth` 只覆盖视频、不覆盖字幕导出链路的问题；现在认证态会继续透传到字幕抓取
- 2026-03-13 的最终实网收口里，又补了一层针对 `The page needs to be reloaded.` 的匿名回退：认证下载或认证字幕提取遇到这个瞬时错误时，会自动改走无认证公共链路重试
- 同时把“字幕导出失败会拖垮整单”这个错误语义拆掉了：字幕现在是独立附加产物，失败只记到 `subtitle_error`，不再把视频下载标记成失败
- 给 `subtitles` 命令补了 `--use-auth`，并把 `429 / bot-check / 需要登录` 的提示改得更接近真实原因
- 重新查清了反复出现的 `playlist-add` 403：根因不是写接口整体失效，而是 `/feed/playlists` 里混有大量“收藏的别人的 playlist”，把这些 ID 当成自建列表写入时，YouTube 只会回一个很差的泛化 403
- 为此在 `reverse/write_api.py` 里补了 403 上下文提示：失败时会返回目标 playlist 标题和页面所有者，帮助快速判断是不是传错了列表
- 2026-03-13 的实网验证里，`save-to-watch-later --yes` 和自建私有 playlist `PLlaidnW7a-Ibn-TlB-mWufuUWUZuH0Mpe` 的 `playlist-add --yes` 都返回了 `STATUS_SUCCEEDED`

## 下一步

- 进入最终发布与验收阶段：确认 wheel、editable install、console script、README 安装路径都真实可用
- 如果未来继续扩写操作，必须继续放在 `reverse/` 下，并保留 `--yes` / `--dry-run` 这类保护
- 如果未来重做 `hot`，优先找稳定公开来源，再决定是否上隔离 provider
