from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from youtube_cli.errors import YoutubeCliError
from youtube_cli.providers.yt_dlp_provider import YtDlpProvider


class DownloadManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.output_dir = Path(self.temp_dir.name) / "downloads"
        self.manifest_path = self.output_dir / ".youtube-cli-manifest.json"
        self.provider = YtDlpProvider()

    def test_resume_failed_skips_completed_items(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "entries": {
                        "video:https://youtu.be/completed": {
                            "task_id": "dl_001",
                            "target": {"id": "done", "url": "https://youtu.be/completed"},
                            "mode": "video",
                            "status": "completed",
                            "output_path": "/tmp/done.mp4",
                            "requested_format": "bv*+ba/b",
                            "actual_format": "18",
                            "manifest_path": str(self.manifest_path),
                            "started_at": "2026-03-12T18:00:00+08:00",
                            "finished_at": "2026-03-12T18:01:00+08:00",
                            "skipped": False,
                            "resumed_from_manifest": False,
                            "error": None,
                        }
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        with patch.object(self.provider, "_download_one") as mock_download:
            tasks = self.provider.download(
                ["https://youtu.be/completed"],
                output_dir=self.output_dir,
                format_selector="bv*+ba/b",
                manifest_path=self.manifest_path,
                resume_failed=True,
            )
        mock_download.assert_not_called()
        self.assertEqual(tasks[0]["status"], "completed")
        self.assertTrue(tasks[0]["skipped"])
        self.assertTrue(tasks[0]["resumed_from_manifest"])

    def test_batch_download_collects_failures_and_continues(self) -> None:
        def fake_download_one(target: str, *, opts, requested_format: str, audio_only: bool):
            if target.endswith("fail"):
                raise YoutubeCliError("download_failed", "boom", source="yt_dlp")
            return {
                "target": {"id": "ok", "url": target},
                "mode": "video",
                "status": "completed",
                "output_path": "/tmp/ok.mp4",
                "requested_format": requested_format,
                "actual_format": "18",
                "error": None,
            }

        with patch.object(self.provider, "_download_one", side_effect=fake_download_one):
            tasks = self.provider.download(
                ["https://youtu.be/fail", "https://youtu.be/ok"],
                output_dir=self.output_dir,
                format_selector="bv*+ba/b",
                manifest_path=self.manifest_path,
            )
        self.assertEqual(tasks[0]["status"], "failed")
        self.assertEqual(tasks[0]["error"]["code"], "download_failed")
        self.assertEqual(tasks[1]["status"], "completed")
        manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["entries"]["video:https://youtu.be/fail"]["status"], "failed")
        self.assertEqual(manifest["entries"]["video:https://youtu.be/ok"]["status"], "completed")

    def test_video_default_falls_back_to_progressive_mp4_after_provider_error(self) -> None:
        attempts: list[str] = []

        class FakeYoutubeDL:
            def __init__(self, params):
                self.params = params

            def __enter__(self):
                attempts.append(self.params["format"])
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def extract_info(self, target, download=True):
                if self.params["format"] != "18":
                    raise Exception("HTTP Error 403: Forbidden")
                return {
                    "id": "abc123",
                    "webpage_url": target,
                    "format_id": "18",
                    "uploader": "tester",
                    "title": "sample",
                    "ext": "mp4",
                }

            def prepare_filename(self, info):
                return str(self_output_dir / "tester" / "sample [abc123].mp4")

        self_output_dir = self.output_dir
        with patch("youtube_cli.providers.yt_dlp_provider.yt_dlp.YoutubeDL", FakeYoutubeDL):
            tasks = self.provider.download(
                ["https://youtu.be/example"],
                output_dir=self.output_dir,
                format_selector="bv*+ba/b",
                manifest_path=self.manifest_path,
            )
        self.assertEqual(tasks[0]["status"], "completed")
        self.assertEqual(tasks[0]["actual_format"], "18")
        self.assertEqual(attempts[:2], ["bv*+ba/b", "22/18"])
        self.assertEqual(attempts[-1], "18")

    def test_video_default_accepts_hls_result_when_yt_dlp_resolves_it(self) -> None:
        attempts: list[str] = []

        class FakeYoutubeDL:
            def __init__(self, params):
                self.params = params

            def __enter__(self):
                attempts.append(self.params["format"])
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def extract_info(self, target, download=True):
                return {
                    "id": "abc123",
                    "webpage_url": target,
                    "format_id": "95",
                    "uploader": "tester",
                    "title": "sample",
                    "ext": "mp4",
                }

            def prepare_filename(self, info):
                return str(self_output_dir / "tester" / "sample [abc123].mp4")

        self_output_dir = self.output_dir
        with patch("youtube_cli.providers.yt_dlp_provider.yt_dlp.YoutubeDL", FakeYoutubeDL):
            tasks = self.provider.download(
                ["https://youtu.be/example"],
                output_dir=self.output_dir,
                format_selector="bv*+ba/b",
                use_auth=True,
                manifest_path=self.manifest_path,
            )
        self.assertEqual(tasks[0]["status"], "completed")
        self.assertEqual(tasks[0]["actual_format"], "95")
        self.assertEqual(attempts, ["bv*+ba/b"])

    def test_use_auth_retries_download_without_auth_on_reload_error(self) -> None:
        attempts: list[dict[str, object]] = []

        class FakeYoutubeDL:
            def __init__(self, params):
                self.params = params

            def __enter__(self):
                attempts.append(self.params)
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def extract_info(self, target, download=True):
                if self.params.get("cookiesfrombrowser"):
                    raise Exception("ERROR: [youtube] abc123: The page needs to be reloaded.")
                return {
                    "id": "abc123",
                    "webpage_url": target,
                    "format_id": "18",
                    "uploader": "tester",
                    "title": "sample",
                    "ext": "mp4",
                }

            def prepare_filename(self, info):
                return str(self_output_dir / "tester" / "sample [abc123].mp4")

        self.provider.auth = type("Auth", (), {"cookies_file": None, "browser": "chrome", "profile": None, "container": None})()
        self_output_dir = self.output_dir
        with patch("youtube_cli.providers.yt_dlp_provider.yt_dlp.YoutubeDL", FakeYoutubeDL):
            tasks = self.provider.download(
                ["https://youtu.be/example"],
                output_dir=self.output_dir,
                format_selector="18",
                use_auth=True,
                manifest_path=self.manifest_path,
            )
        self.assertEqual(tasks[0]["status"], "completed")
        self.assertEqual(tasks[0]["actual_format"], "18")
        self.assertIsNotNone(attempts[0].get("cookiesfrombrowser"))
        self.assertTrue(attempts[0]["quiet"])
        self.assertIsNone(attempts[1].get("cookiesfrombrowser"))
        self.assertTrue(tasks[0]["auth_fallback"]["used"])

    def test_download_sets_fragment_and_external_downloader_options(self) -> None:
        captured_params: list[dict[str, object]] = []

        class FakeYoutubeDL:
            def __init__(self, params):
                self.params = params

            def __enter__(self):
                captured_params.append(self.params)
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def extract_info(self, target, download=True):
                return {
                    "id": "abc123",
                    "webpage_url": target,
                    "format_id": "18",
                    "uploader": "tester",
                    "title": "sample",
                    "ext": "mp4",
                }

            def prepare_filename(self, info):
                return str(self_output_dir / "tester" / "sample [abc123].mp4")

        self_output_dir = self.output_dir
        with patch("youtube_cli.providers.yt_dlp_provider.yt_dlp.YoutubeDL", FakeYoutubeDL):
            self.provider.download(
                ["https://youtu.be/example"],
                output_dir=self.output_dir,
                format_selector="18",
                concurrent_fragments=6,
                fragment_retries=12,
                external_downloader="aria2c",
                external_downloader_args=["-x", "8"],
                manifest_path=self.manifest_path,
            )
        self.assertEqual(captured_params[0]["concurrent_fragment_downloads"], 6)
        self.assertEqual(captured_params[0]["fragment_retries"], 12)
        self.assertEqual(captured_params[0]["external_downloader"], {"default": "aria2c"})
        self.assertEqual(captured_params[0]["external_downloader_args"], {"aria2c": ["-x", "8"]})

    def test_quality_selector_maps_to_height_bound(self) -> None:
        selector = self.provider._resolve_download_format(
            format_selector="bv*+ba/b",
            quality="720p",
            audio_only=False,
        )
        self.assertIn("height<=720", selector)
        self.assertNotIn("protocol!=m3u8_native", selector)
        self.assertTrue(selector.endswith("/22/18"))

    def test_write_subtitles_exports_single_files(self) -> None:
        def fake_download_one(target: str, *, opts, requested_format: str, audio_only: bool):
            return {
                "target": {"id": "ok", "url": target},
                "mode": "video",
                "status": "completed",
                "output_path": str(self.output_dir / "clip.mp4"),
                "requested_format": requested_format,
                "actual_format": "18",
                "error": None,
            }

        subtitles = {
            "en": {
                "video_id": "ok",
                "language": "en",
                "kind": "manual",
                "segments": [{"start_seconds": 0.0, "end_seconds": 1.0, "text": "Hello"}],
            },
            "zh-Hans": {
                "video_id": "ok",
                "language": "zh-Hans",
                "kind": "auto",
                "segments": [{"start_seconds": 0.0, "end_seconds": 1.0, "text": "你好"}],
            },
        }

        def fake_subtitle_with_fallback(target: str, *, language=None, prefer_auto=False, use_auth=False):
            self.assertTrue(use_auth)
            return subtitles[language]

        with patch.object(self.provider, "_download_one", side_effect=fake_download_one):
            with patch.object(self.provider, "subtitle_with_fallback", side_effect=fake_subtitle_with_fallback):
                tasks = self.provider.download(
                    ["https://youtu.be/example"],
                    output_dir=self.output_dir,
                    format_selector="18",
                    write_subtitles=True,
                    subtitle_languages=["en", "zh-Hans"],
                    subtitle_file_format="srt",
                    use_auth=True,
                    manifest_path=self.manifest_path,
                )
        exported = tasks[0]["subtitle_files"]
        self.assertEqual(len(exported), 2)
        self.assertTrue((self.output_dir / "clip.en.srt").exists())
        self.assertTrue((self.output_dir / "clip.zh-Hans.srt").exists())
        self.assertIsNone(tasks[0]["subtitle_error"])

    def test_missing_subtitle_translates_with_provider(self) -> None:
        def fake_download_one(target: str, *, opts, requested_format: str, audio_only: bool):
            return {
                "target": {"id": "ok", "url": target},
                "mode": "video",
                "status": "completed",
                "output_path": str(self.output_dir / "clip.mp4"),
                "requested_format": requested_format,
                "actual_format": "18",
                "error": None,
            }

        subtitles = {
            "en": {
                "video_id": "ok",
                "language": "en",
                "kind": "manual",
                "segments": [
                    {"start_seconds": 0.0, "end_seconds": 1.0, "text": "Hello"},
                    {"start_seconds": 1.0, "end_seconds": 2.0, "text": "World"},
                ],
            },
        }

        def fake_subtitle_with_fallback(target: str, *, language=None, prefer_auto=False, use_auth=False):
            if language in (None, "en"):
                return subtitles["en"]
            raise YoutubeCliError(
                "subtitle_unavailable",
                f"语言 `{language}` 的字幕不存在。",
                hint="可用语言: en",
                source="yt_dlp",
            )

        with patch.object(self.provider, "_download_one", side_effect=fake_download_one):
            with patch.object(self.provider, "subtitle_with_fallback", side_effect=fake_subtitle_with_fallback):
                with patch.dict(
                    os.environ,
                    {
                        "YOUTUBE_CLI_TRANSLATION_PROVIDER": "mock",
                        "YOUTUBE_CLI_TRANSLATION_MOCK_PREFIX": "ZH:",
                    },
                    clear=False,
                ):
                    tasks = self.provider.download(
                        ["https://youtu.be/example"],
                        output_dir=self.output_dir,
                        format_selector="18",
                        write_subtitles=True,
                        subtitle_languages=["en", "zh-CN"],
                        subtitle_file_format="srt",
                        use_auth=True,
                        manifest_path=self.manifest_path,
                    )
        exported = tasks[0]["subtitle_files"]
        self.assertEqual(len(exported), 2)
        zh_sub = self.output_dir / "clip.zh-CN.srt"
        self.assertTrue(zh_sub.exists())
        self.assertIn("ZH:Hello", zh_sub.read_text(encoding="utf-8"))
        self.assertIsNone(tasks[0]["subtitle_error"])

    def test_missing_subtitles_is_ignored(self) -> None:
        def fake_download_one(target: str, *, opts, requested_format: str, audio_only: bool):
            return {
                "target": {"id": "ok", "url": target},
                "mode": "video",
                "status": "completed",
                "output_path": str(self.output_dir / "clip.mp4"),
                "requested_format": requested_format,
                "actual_format": "18",
                "error": None,
            }

        def fake_subtitle_with_fallback(*args, **kwargs):
            raise YoutubeCliError(
                "subtitle_unavailable",
                "当前视频没有可用字幕。",
                source="yt_dlp",
            )

        with patch.object(self.provider, "_download_one", side_effect=fake_download_one):
            with patch.object(self.provider, "subtitle_with_fallback", side_effect=fake_subtitle_with_fallback):
                tasks = self.provider.download(
                    ["https://youtu.be/example"],
                    output_dir=self.output_dir,
                    format_selector="18",
                    write_subtitles=True,
                    subtitle_languages=["en", "zh-CN"],
                    subtitle_file_format="srt",
                    use_auth=True,
                    manifest_path=self.manifest_path,
                )

        self.assertEqual(tasks[0]["status"], "completed")
        self.assertEqual(tasks[0]["subtitle_files"], [])
        self.assertIsNone(tasks[0]["subtitle_error"])

    def test_subtitle_export_failure_does_not_fail_video_download(self) -> None:
        def fake_download_one(target: str, *, opts, requested_format: str, audio_only: bool):
            return {
                "target": {"id": "ok", "url": target},
                "mode": "video",
                "status": "completed",
                "output_path": str(self.output_dir / "clip.mp4"),
                "requested_format": requested_format,
                "actual_format": "18",
                "error": None,
            }

        subtitle_error = YoutubeCliError(
            "subtitle_unavailable",
            "当前视频没有可用字幕。",
            source="yt_dlp",
        )

        with patch.object(self.provider, "_download_one", side_effect=fake_download_one):
            with patch.object(self.provider, "_export_subtitle_files", side_effect=subtitle_error):
                tasks = self.provider.download(
                    ["https://youtu.be/example"],
                    output_dir=self.output_dir,
                    format_selector="18",
                    write_subtitles=True,
                    subtitle_languages=["en", "zh-Hans"],
                    subtitle_file_format="srt",
                    use_auth=True,
                    manifest_path=self.manifest_path,
                )

        self.assertEqual(tasks[0]["status"], "completed")
        self.assertEqual(tasks[0]["actual_format"], "18")
        self.assertEqual(tasks[0]["subtitle_files"], [])
        self.assertEqual(tasks[0]["subtitle_error"]["code"], "subtitle_unavailable")

    def test_subtitles_use_auth_is_forwarded_to_extract_chain(self) -> None:
        provider = YtDlpProvider()
        info = {
            "id": "abc123",
            "subtitles": {"en": [{"ext": "json3", "url": "https://example.com/en.json3"}]},
            "automatic_captions": {},
        }

        with patch.object(provider, "_extract", return_value=info) as mock_extract:
            with patch.object(provider, "_extract_subtitle_track", return_value={"language": "en"}) as mock_track:
                result = provider.subtitles("https://youtu.be/example", language="en", use_auth=True)

        self.assertEqual(result, {"language": "en"})
        mock_extract.assert_called_once_with(
            "https://youtu.be/example",
            use_auth=True,
            quiet=True,
            no_warnings=True,
        )
        self.assertEqual(mock_track.call_args.kwargs["use_auth"], True)

    def test_subtitles_retry_without_auth_on_reload_error(self) -> None:
        provider = YtDlpProvider()
        auth_error = YoutubeCliError(
            "provider_error",
            "ERROR: [youtube] abc123: The page needs to be reloaded.",
            source="yt_dlp",
        )
        info = {
            "id": "abc123",
            "subtitles": {"en": [{"ext": "json3", "url": "https://example.com/en.json3"}]},
            "automatic_captions": {},
        }

        with patch.object(provider, "_extract", side_effect=[auth_error, info]) as mock_extract:
            with patch.object(provider, "_extract_subtitle_track", return_value={"language": "en"}) as mock_track:
                result = provider.subtitles("https://youtu.be/example", language="en", use_auth=True)

        self.assertEqual(result, {"language": "en"})
        self.assertEqual(mock_extract.call_args_list[0].kwargs["use_auth"], True)
        self.assertEqual(mock_extract.call_args_list[0].kwargs["quiet"], True)
        self.assertEqual(mock_extract.call_args_list[1].kwargs["use_auth"], False)
        self.assertEqual(mock_track.call_args.kwargs["use_auth"], True)


if __name__ == "__main__":
    unittest.main()
