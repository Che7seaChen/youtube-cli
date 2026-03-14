# 风控基线验证（最小版）

目标：验证当前“节流 + 抖动 + 写退避 + doctor”是否降低风控触发率，并建立可对比的基线。

## 建议流程（30-60 分钟）

1. 环境自检
- `youtube doctor`

2. 读链路（匿名 + 登录态）
- `youtube video "<video_url>"`
- `youtube comments "<video_url>" --limit 50`
- `youtube formats "<video_url>"`
- `youtube --mode safe video "<video_url>"`

3. 下载链路（单视频 + playlist）
- `youtube download "<video_url>" --quality 720p`
- `youtube playlist-download <playlist_id> --limit 10`

4. 写链路（登录态）
- `youtube playlist-create "risk-test" --privacy private --yes`
- `youtube playlist-add "<video_url>" <playlist_id> --yes`

## 记录模板（建议 5-10 次样本）

```
时间:
命令:
模式: safe / balanced / fast
是否登录态: 是/否
结果: 成功 / 失败
失败类型: 429 / 403 / bot_check / network / 其他
耗时:
备注:
```

## 判定标准

- 429/403/bot_check 出现频率明显下降（相对之前）
- 写操作失败后可退避重试成功
- `safe` 明显更稳但速度可接受

## 下一步

- 若 429/403 仍高：提高 `safe` 模式节流/抖动，或写操作单独收紧。
- 若只写操作触发：针对写接口单独加最小间隔。
- 若无明显问题：维持现状，避免过度工程。
