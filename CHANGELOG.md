# Changelog

## [0.2.1] - 2026-03-14

### Fixed

- Added auth-to-anon fallback for read operations when authenticated extraction fails (e.g., unsupported format), preventing `--use-auth` from breaking reads.

All notable changes to this project will be documented in this file.

## [0.2.0] - 2026-03-14

### Added

- Added risk-control modes (`--mode safe|balanced|fast`) and default request pacing for stability.
- Added `youtube doctor` for environment/auth diagnostics and recent error metrics.
- Added local metrics tracking for command success/failure (no URL logging).

### Changed

- Applied request sleep intervals to yt-dlp read flows and task-level jitter for batch downloads.
- Added retry/backoff for write APIs and explicit rate-limited handling on write calls.
- Status output now surfaces risk-control configuration.

## [0.1.3] - 2026-03-14

### Added

- Added AI translation fallback when requested subtitle languages are missing; subtitles remain aligned to the original timeline.
- Added `--use-auth` for `video`, `comments`, and `formats` to pass browser auth when bot checks are triggered.
- Added translation configuration via `YOUTUBE_CLI_TRANSLATION_PROVIDER` and related OpenAI-compatible environment variables.
- Added optional JS challenge configuration via `YOUTUBE_CLI_JS_RUNTIMES` and `YOUTUBE_CLI_REMOTE_COMPONENTS`.

### Changed

- Subtitles are now exported as per-language files only; bilingual SRT merge has been removed.
- If no subtitles exist, subtitle export is skipped when `--write-subs` is used (download still succeeds).

## [0.1.2] - 2026-03-14

### Added

- Added `youtube login --export-cookies` to export Netscape cookies.txt directly from a logged-in browser (中文：新增浏览器直接导出 cookies.txt 的登录流程).
- Defaulted login page launch to incognito/private windows with safe fallback to normal windows (中文：默认尝试无痕/隐身窗口打开登录页，失败自动回退普通窗口).
- Added headless detection to block auto-login flow and guide users to cookies export (中文：无头环境阻止自动打开登录页并引导改用 cookies 导出).
- Documented headless/VPS auth flow and export guidance in README and SKILL.md (中文：补充无头/VPS 登录态流程与导出说明).

## [0.1.1] - 2026-03-13

### Fixed

- Made repeated `save-to-watch-later` and `playlist-add` requests behave idempotently instead of surfacing raw HTTP 409 errors.
- Polished public release docs and acknowledgements for the first patch release.

## [0.1.0] - 2026-03-13

### Added

- Initial public release of `youtube-cli`.
- Search, channel, playlist, comments, related videos, formats, and authenticated feed commands.
- Video and audio downloads with subtitles, bilingual subtitle export, batch input, and manifest resume.
- Playlist workflows including `playlist-download`, `playlist-create`, `playlist-add`, and `playlist-delete`.
