from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from youtube_cli.cli import main


class FakeProvider:
    def __init__(self, auth=None, *, no_check_certificate=False) -> None:
        self.auth = auth
        self.no_check_certificate = no_check_certificate

    def status(self):
        return {"provider": "yt_dlp", "auth_configured": self.auth is not None}

    def validate_auth(self):
        return {"authenticated": True, "sample_size": 1}

    def whoami(self):
        return {
            "authenticated": True,
            "browser": "chrome",
            "capabilities": {
                "notifications": {"accessible": True, "sample_size": 1, "sample_title": "hello"}
            },
            "homepage": {"reachable": True, "sign_in_visible": False},
        }

    def video(self, target: str):
        return {"id": "abc123", "title": f"video:{target}"}

    def comments(self, target: str, *, limit: int = 20, sort: str = "top"):
        return [{"id": "c1", "text": "hello", "author": "tester", "limit": limit, "sort": sort}]

    def related(self, target: str, *, limit: int = 20):
        return [{"id": "r1", "title": "next video", "limit": limit}]

    def formats(self, target: str):
        return {"video_id": "abc123", "formats": [{"format_id": "18"}]}

    def subtitles(self, target: str, *, language=None, auto=False, use_auth=False):
        return {
            "video_id": "abc123",
            "language": language or "en",
            "kind": "auto" if auto else "manual",
            "use_auth": use_auth,
            "segments": [],
        }

    def search(self, query: str, *, limit: int = 10, search_type: str = "video"):
        return [{"id": "abc123", "title": query, "type": search_type, "limit": limit}]

    def channel(self, target: str, *, limit: int = 20):
        return {
            "id": "UC123",
            "title": target,
            "recent_items": [],
            "tab_previews": {"videos": [{"id": "v1"}], "playlists": [{"id": "p1"}]},
            "tab_status": {
                "videos": {"available": True, "sample_size": 1},
                "playlists": {"available": True, "sample_size": 1},
            },
            "limit": limit,
        }

    def channel_videos(self, target: str, *, limit: int = 20):
        return [{"id": "video1", "title": target, "type": "video", "limit": limit, "source_feed": "channel_videos"}]

    def channel_playlists(self, target: str, *, limit: int = 20):
        return [{"id": "playlist1", "title": target, "type": "playlist", "limit": limit, "source_feed": "channel_playlists"}]

    def playlist(self, target: str, *, limit: int = 20, use_auth: bool = False):
        return {"id": "PL123", "title": target, "items": [], "limit": limit}

    def playlist_videos(self, target: str, *, limit: int | None = 20, use_auth: bool = False):
        return [
            {
                "id": "pv1",
                "title": target,
                "type": "video",
                "limit": limit,
                "source_feed": "playlist_videos",
                "url": "https://youtu.be/pv1",
                "use_auth": use_auth,
            }
        ]

    def feed(self, name: str, *, limit: int = 20):
        return [{"id": "feed123", "type": "video", "limit": limit, "source_feed": name}]

    def save_to_watch_later(self, target: str, *, dry_run: bool = False):
        return {"action": "add_video", "playlist_id": "WL", "target_video_id": "abc123", "dry_run": dry_run}

    def playlist_add(self, target: str, playlist: str, *, dry_run: bool = False):
        return {"action": "add_video", "playlist_id": playlist, "target_video_id": "abc123", "dry_run": dry_run}

    def playlist_create(self, title: str, *, description: str | None, privacy: str, dry_run: bool = False):
        return {
            "title": title,
            "description": description,
            "privacy": privacy.upper(),
            "dry_run": dry_run,
            "playlist_id": "PLNEW",
        }

    def playlist_delete(self, playlist: str, *, dry_run: bool = False):
        return {"playlist_id": playlist, "dry_run": dry_run}

    def download(
        self,
        targets,
        *,
        output_dir,
        format_selector,
        quality=None,
        audio_only=False,
        write_subtitles=False,
        subtitle_languages=None,
        subtitle_file_format="srt",
        prefer_auto_subtitles=False,
        use_auth=False,
        rate_limit=None,
        throttled_rate=None,
        http_chunk_size=None,
        concurrent_fragments=4,
        fragment_retries=10,
        external_downloader=None,
        external_downloader_args=None,
        manifest_path=None,
        resume_failed=False,
    ):
        mode = "audio" if audio_only else "video"
        return [
            {
                "task_id": "dl_001",
                "target": {"id": "abc123", "url": targets[0]},
                "mode": mode,
                "status": "completed",
                "output_path": str(output_dir / f"{mode}.mp4"),
                "requested_format": format_selector,
                "actual_format": "18",
                "quality": quality,
                "write_subtitles": write_subtitles,
                "subtitle_languages": subtitle_languages or [],
                "subtitle_file_format": subtitle_file_format,
                "prefer_auto_subtitles": prefer_auto_subtitles,
                "use_auth": use_auth,
                "rate_limit": rate_limit,
                "throttled_rate": throttled_rate,
                "http_chunk_size": http_chunk_size,
                "concurrent_fragments": concurrent_fragments,
                "fragment_retries": fragment_retries,
                "external_downloader": external_downloader,
                "external_downloader_args": external_downloader_args or [],
                "manifest_path": str(manifest_path) if manifest_path else str(output_dir / ".youtube-cli-manifest.json"),
                "resume_failed": resume_failed,
            }
        ]


class CliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = CliRunner()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.env = {"YOUTUBE_CLI_CONFIG_DIR": self.temp_dir.name}

    def test_login_saves_config(self) -> None:
        with patch.dict(os.environ, self.env, clear=False):
            with patch("youtube_cli.cli.YtDlpProvider", FakeProvider):
                result = self.runner.invoke(main, ["--json", "login", "--browser", "chrome"])
        self.assertEqual(result.exit_code, 0, result.output)
        payload = json.loads(result.output)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["data"]["auth"]["browser"], "chrome")
        self.assertTrue((Path(self.temp_dir.name) / "config.json").exists())

    def test_video_command_returns_json(self) -> None:
        with patch.dict(os.environ, self.env, clear=False):
            with patch("youtube_cli.cli.YtDlpProvider", FakeProvider):
                result = self.runner.invoke(main, ["--json", "video", "https://youtu.be/example"])
        self.assertEqual(result.exit_code, 0, result.output)
        payload = json.loads(result.output)
        self.assertEqual(payload["command"], "video")
        self.assertEqual(payload["data"]["title"], "video:https://youtu.be/example")

    def test_comments_command(self) -> None:
        with patch.dict(os.environ, self.env, clear=False):
            with patch("youtube_cli.cli.YtDlpProvider", FakeProvider):
                result = self.runner.invoke(main, ["--json", "comments", "https://youtu.be/example", "--limit", "5", "--sort", "new"])
        self.assertEqual(result.exit_code, 0, result.output)
        payload = json.loads(result.output)
        self.assertEqual(payload["command"], "comments")
        self.assertEqual(payload["data"][0]["sort"], "new")

    def test_related_command(self) -> None:
        with patch.dict(os.environ, self.env, clear=False):
            with patch("youtube_cli.cli.YtDlpProvider", FakeProvider):
                result = self.runner.invoke(main, ["--json", "related", "https://youtu.be/example", "--limit", "4"])
        self.assertEqual(result.exit_code, 0, result.output)
        payload = json.loads(result.output)
        self.assertEqual(payload["command"], "related")
        self.assertEqual(payload["data"][0]["limit"], 4)

    def test_audio_batch_file(self) -> None:
        batch_file = Path(self.temp_dir.name) / "batch.txt"
        batch_file.write_text("https://youtu.be/one\n", encoding="utf-8")
        with patch.dict(os.environ, self.env, clear=False):
            with patch("youtube_cli.cli.YtDlpProvider", FakeProvider):
                result = self.runner.invoke(main, ["--json", "audio", "--batch-file", str(batch_file)])
        self.assertEqual(result.exit_code, 0, result.output)
        payload = json.loads(result.output)
        self.assertEqual(payload["command"], "audio")
        self.assertEqual(payload["data"][0]["mode"], "audio")

    def test_download_passes_advanced_downloader_options(self) -> None:
        with patch.dict(os.environ, self.env, clear=False):
            with patch("youtube_cli.cli.YtDlpProvider", FakeProvider):
                result = self.runner.invoke(
                    main,
                    [
                        "--json",
                        "download",
                        "https://youtu.be/example",
                        "--concurrent-fragments",
                        "6",
                        "--fragment-retries",
                        "12",
                        "--downloader",
                        "aria2c",
                        "--downloader-args",
                        "-x 8 -k 1M",
                    ],
                )
        self.assertEqual(result.exit_code, 0, result.output)
        payload = json.loads(result.output)
        self.assertEqual(payload["data"][0]["concurrent_fragments"], 6)
        self.assertEqual(payload["data"][0]["fragment_retries"], 12)
        self.assertEqual(payload["data"][0]["external_downloader"], "aria2c")
        self.assertEqual(payload["data"][0]["external_downloader_args"], ["-x", "8", "-k", "1M"])

    def test_download_supports_quality_and_subtitle_options(self) -> None:
        with patch.dict(os.environ, self.env, clear=False):
            with patch("youtube_cli.cli.YtDlpProvider", FakeProvider):
                result = self.runner.invoke(
                    main,
                    [
                        "--json",
                        "download",
                        "https://youtu.be/example",
                        "--quality",
                        "720p",
                        "--write-subs",
                        "--sub-lang",
                        "en",
                        "--sub-lang",
                        "zh-Hans",
                        "--subtitle-format",
                        "vtt",
                        "--prefer-auto-subs",
                        "--use-auth",
                        "--throttled-rate",
                        "100K",
                        "--http-chunk-size",
                        "10M",
                    ],
                )
        self.assertEqual(result.exit_code, 0, result.output)
        payload = json.loads(result.output)
        self.assertEqual(payload["data"][0]["quality"], "720p")
        self.assertEqual(payload["data"][0]["subtitle_languages"], ["en", "zh-Hans"])
        self.assertEqual(payload["data"][0]["subtitle_file_format"], "vtt")
        self.assertTrue(payload["data"][0]["prefer_auto_subtitles"])
        self.assertTrue(payload["data"][0]["use_auth"])
        self.assertEqual(payload["data"][0]["throttled_rate"], "100K")
        self.assertEqual(payload["data"][0]["http_chunk_size"], "10M")

    def test_subtitles_supports_use_auth(self) -> None:
        with patch.dict(os.environ, self.env, clear=False):
            with patch("youtube_cli.cli.YtDlpProvider", FakeProvider):
                result = self.runner.invoke(
                    main,
                    ["--json", "subtitles", "https://youtu.be/example", "--language", "zh-Hans", "--auto", "--use-auth"],
                )
        self.assertEqual(result.exit_code, 0, result.output)
        payload = json.loads(result.output)
        self.assertEqual(payload["data"]["language"], "zh-Hans")
        self.assertEqual(payload["data"]["kind"], "auto")
        self.assertTrue(payload["data"]["use_auth"])

    def test_download_rejects_quality_with_explicit_format(self) -> None:
        with patch.dict(os.environ, self.env, clear=False):
            with patch("youtube_cli.cli.YtDlpProvider", FakeProvider):
                result = self.runner.invoke(
                    main,
                    [
                        "--json",
                        "download",
                        "https://youtu.be/example",
                        "--quality",
                        "720p",
                        "--format",
                        "18",
                    ],
                )
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("只能二选一", result.output)

    def test_save_to_watch_later_requires_explicit_confirmation(self) -> None:
        with patch.dict(os.environ, self.env, clear=False):
            with patch("youtube_cli.cli.YtDlpProvider", FakeProvider):
                result = self.runner.invoke(main, ["--json", "save-to-watch-later", "https://youtu.be/example"])
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("写操作默认受保护", result.output)

    def test_save_to_watch_later_supports_dry_run(self) -> None:
        with patch.dict(os.environ, self.env, clear=False):
            with patch("youtube_cli.cli.YtDlpProvider", FakeProvider):
                result = self.runner.invoke(
                    main,
                    ["--json", "save-to-watch-later", "https://youtu.be/example", "--dry-run"],
                )
        self.assertEqual(result.exit_code, 0, result.output)
        payload = json.loads(result.output)
        self.assertTrue(payload["data"]["dry_run"])
        self.assertEqual(payload["data"]["playlist_id"], "WL")

    def test_playlist_add_supports_dry_run(self) -> None:
        with patch.dict(os.environ, self.env, clear=False):
            with patch("youtube_cli.cli.YtDlpProvider", FakeProvider):
                result = self.runner.invoke(
                    main,
                    ["--json", "playlist-add", "https://youtu.be/example", "PL123", "--dry-run"],
                )
        self.assertEqual(result.exit_code, 0, result.output)
        payload = json.loads(result.output)
        self.assertEqual(payload["data"]["playlist_id"], "PL123")

    def test_playlist_create_supports_dry_run(self) -> None:
        with patch.dict(os.environ, self.env, clear=False):
            with patch("youtube_cli.cli.YtDlpProvider", FakeProvider):
                result = self.runner.invoke(
                    main,
                    ["--json", "playlist-create", "My List", "--description", "hello", "--privacy", "unlisted", "--dry-run"],
                )
        self.assertEqual(result.exit_code, 0, result.output)
        payload = json.loads(result.output)
        self.assertEqual(payload["data"]["title"], "My List")
        self.assertEqual(payload["data"]["privacy"], "UNLISTED")
        self.assertTrue(payload["data"]["dry_run"])

    def test_playlist_delete_supports_dry_run(self) -> None:
        with patch.dict(os.environ, self.env, clear=False):
            with patch("youtube_cli.cli.YtDlpProvider", FakeProvider):
                result = self.runner.invoke(
                    main,
                    ["--json", "playlist-delete", "PL123", "--dry-run"],
                )
        self.assertEqual(result.exit_code, 0, result.output)
        payload = json.loads(result.output)
        self.assertEqual(payload["data"]["playlist_id"], "PL123")
        self.assertTrue(payload["data"]["dry_run"])

    def test_whoami_contains_capabilities(self) -> None:
        with patch.dict(os.environ, self.env, clear=False):
            with patch("youtube_cli.cli.YtDlpProvider", FakeProvider):
                result = self.runner.invoke(main, ["--json", "whoami"])
        self.assertEqual(result.exit_code, 0, result.output)
        payload = json.loads(result.output)
        self.assertTrue(payload["data"]["capabilities"]["notifications"]["accessible"])

    def test_search_supports_channel_type(self) -> None:
        with patch.dict(os.environ, self.env, clear=False):
            with patch("youtube_cli.cli.YtDlpProvider", FakeProvider):
                result = self.runner.invoke(main, ["--json", "search", "openai", "--type", "channel"])
        self.assertEqual(result.exit_code, 0, result.output)
        payload = json.loads(result.output)
        self.assertEqual(payload["data"][0]["type"], "channel")

    def test_channel_videos_command(self) -> None:
        with patch.dict(os.environ, self.env, clear=False):
            with patch("youtube_cli.cli.YtDlpProvider", FakeProvider):
                result = self.runner.invoke(main, ["--json", "channel-videos", "@openai", "--limit", "3"])
        self.assertEqual(result.exit_code, 0, result.output)
        payload = json.loads(result.output)
        self.assertEqual(payload["command"], "channel-videos")
        self.assertEqual(payload["data"][0]["type"], "video")

    def test_channel_playlists_command(self) -> None:
        with patch.dict(os.environ, self.env, clear=False):
            with patch("youtube_cli.cli.YtDlpProvider", FakeProvider):
                result = self.runner.invoke(main, ["--json", "channel-playlists", "@openai", "--limit", "2"])
        self.assertEqual(result.exit_code, 0, result.output)
        payload = json.loads(result.output)
        self.assertEqual(payload["command"], "channel-playlists")
        self.assertEqual(payload["data"][0]["type"], "playlist")

    def test_playlist_videos_command(self) -> None:
        with patch.dict(os.environ, self.env, clear=False):
            with patch("youtube_cli.cli.YtDlpProvider", FakeProvider):
                result = self.runner.invoke(main, ["--json", "playlist-videos", "PL123", "--limit", "2"])
        self.assertEqual(result.exit_code, 0, result.output)
        payload = json.loads(result.output)
        self.assertEqual(payload["command"], "playlist-videos")
        self.assertEqual(payload["data"][0]["source_feed"], "playlist_videos")

    def test_playlist_download_command(self) -> None:
        with patch.dict(os.environ, self.env, clear=False):
            with patch("youtube_cli.cli.YtDlpProvider", FakeProvider):
                result = self.runner.invoke(
                    main,
                    [
                        "--json",
                        "playlist-download",
                        "PL123",
                        "--quality",
                        "360p",
                        "--write-subs",
                        "--sub-lang",
                        "en",
                        "--use-auth",
                    ],
                )
        self.assertEqual(result.exit_code, 0, result.output)
        payload = json.loads(result.output)
        self.assertEqual(payload["command"], "playlist-download")
        self.assertEqual(payload["data"]["resolved_targets"], 1)
        self.assertEqual(payload["data"]["tasks"][0]["target"]["url"], "https://youtu.be/pv1")
        self.assertTrue(payload["data"]["tasks"][0]["use_auth"])

    def test_channel_command_includes_tab_summaries(self) -> None:
        with patch.dict(os.environ, self.env, clear=False):
            with patch("youtube_cli.cli.YtDlpProvider", FakeProvider):
                result = self.runner.invoke(main, ["--json", "channel", "@openai", "--limit", "2"])
        self.assertEqual(result.exit_code, 0, result.output)
        payload = json.loads(result.output)
        self.assertTrue(payload["data"]["tab_status"]["videos"]["available"])
        self.assertEqual(payload["data"]["tab_previews"]["playlists"][0]["id"], "p1")

    def test_status_supports_no_check_certificate_flag(self) -> None:
        with patch.dict(os.environ, self.env, clear=False):
            with patch("youtube_cli.cli.YtDlpProvider", FakeProvider):
                result = self.runner.invoke(main, ["--json", "--no-check-certificate", "status"])
        self.assertEqual(result.exit_code, 0, result.output)
        payload = json.loads(result.output)
        self.assertTrue(payload["ok"])

    def test_feed_includes_source_feed(self) -> None:
        with patch.dict(os.environ, self.env, clear=False):
            with patch("youtube_cli.cli.YtDlpProvider", FakeProvider):
                result = self.runner.invoke(main, ["--json", "notifications", "--limit", "1"])
        self.assertEqual(result.exit_code, 0, result.output)
        payload = json.loads(result.output)
        self.assertEqual(payload["data"][0]["source_feed"], "notifications")

    def test_favorites_command(self) -> None:
        with patch.dict(os.environ, self.env, clear=False):
            with patch("youtube_cli.cli.YtDlpProvider", FakeProvider):
                result = self.runner.invoke(main, ["--json", "favorites", "--limit", "1"])
        self.assertEqual(result.exit_code, 0, result.output)
        payload = json.loads(result.output)
        self.assertEqual(payload["command"], "favorites")
        self.assertEqual(payload["data"][0]["source_feed"], "favorites")

    def test_download_supports_resume_manifest_options(self) -> None:
        manifest_path = Path(self.temp_dir.name) / "dl-manifest.json"
        with patch.dict(os.environ, self.env, clear=False):
            with patch("youtube_cli.cli.YtDlpProvider", FakeProvider):
                result = self.runner.invoke(
                    main,
                    [
                        "--json",
                        "download",
                        "https://youtu.be/example",
                        "--manifest",
                        str(manifest_path),
                        "--resume-failed",
                    ],
                )
        self.assertEqual(result.exit_code, 0, result.output)
        payload = json.loads(result.output)
        self.assertEqual(payload["data"][0]["manifest_path"], str(manifest_path))
        self.assertTrue(payload["data"][0]["resume_failed"])


if __name__ == "__main__":
    unittest.main()
