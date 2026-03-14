---
name: youtube-cli
description: Use this skill for account management, deep metadata, and comments.
  - 核心场景："看评论"、"管理订阅"、"稍后观看"、"账户状态"、"youtube status"、"youtube login"。
  - 注意：侧重于账户和社交数据。
---

# youtube-cli Skill

Use this repository's `youtube` CLI as the default interface for YouTube tasks in this workspace.

## When to use

Use this skill when the user asks to:

- search YouTube videos, channels, or playlists
- inspect video metadata, comments, related videos, or formats
- fetch subtitles or auto-translate missing subtitle languages
- browse channels, playlists, subscriptions, watch later, history, recommendations, or notifications
- download videos, audio, or whole playlists
- save to watch later or manage playlists

## Command rules

- Prefer `youtube --json` or `youtube --yaml` for machine-readable output.
- Keep responses narrow with `--limit`.
- For whole-playlist downloads, prefer `playlist-download` over manually chaining `playlist-videos`.
- For write actions, use `--dry-run` first when preview is useful, then use `--yes` only when the user clearly intends to modify the account.
- Use `--use-auth` only for private, restricted, or authenticated resources.

## Authentication

- Check auth state with `youtube status --check`.
- Set up auth with `youtube login --browser chrome --check` (local browser) or a cookies file.
- One-step export: `youtube login --export-cookies /path/to/cookies.txt --check` (opens YouTube, waits for login, then saves Netscape cookies).
- The export flow defaults to incognito/private windows; use `--no-incognito` to disable.
- Headless/VPS: export on a machine with a GUI, then `youtube login --cookies /path/to/cookies.txt --check`.
- Most public metadata and downloads do not require login.

## TLS workaround

Some local environments have a broken certificate chain. If a command fails with a TLS error, retry with:

```bash
youtube --no-check-certificate ...
```

Or set:

```bash
export YOUTUBE_CLI_NO_CHECK_CERTIFICATE=1
```

## Recommended patterns

```bash
youtube --yaml search "openai" --type channel --limit 3
youtube --json comments "https://www.youtube.com/watch?v=VIDEO_ID" --limit 20
youtube --yaml playlist-videos PLAYLIST_ID --limit 5
youtube --json download --batch-file targets.txt --quality 360p
youtube playlist-create "Agent Review Queue" --dry-run
```

## References

- Read [`README.md`](README.md) for end-user usage examples.
- Read [`SCHEMA.md`](SCHEMA.md) when you need the exact structured output envelope.
