from __future__ import annotations

import unittest
from unittest.mock import patch

from youtube_cli.providers.yt_dlp_provider import YtDlpProvider


class ProviderChannelTabTests(unittest.TestCase):
    def setUp(self) -> None:
        self.provider = YtDlpProvider()

    def test_channel_videos_uses_videos_tab_and_marks_source(self) -> None:
        with patch.object(
            self.provider,
            "_extract",
            return_value={
                "channel": "OpenAI",
                "channel_id": "UC123",
                "uploader_id": "@openai",
                "entries": [
                    {
                        "id": "abc123",
                        "title": "hello",
                        "webpage_url": "https://www.youtube.com/watch?v=abc123",
                        "channel": "OpenAI",
                    }
                ]
            },
        ) as mock_extract:
            items = self.provider.channel_videos("@openai", limit=1)
        mock_extract.assert_called_once_with("https://www.youtube.com/@openai/videos", flat=True, use_auth=False)
        self.assertEqual(items[0]["source_feed"], "channel_videos")
        self.assertEqual(items[0]["type"], "video")
        self.assertEqual(items[0]["channel"]["title"], "OpenAI")
        self.assertEqual(items[0]["channel"]["id"], "UC123")
        self.assertEqual(items[0]["channel"]["handle"], "@openai")

    def test_channel_playlists_uses_playlists_tab_and_marks_source(self) -> None:
        with patch.object(
            self.provider,
            "_extract",
            return_value={
                "channel": "OpenAI",
                "channel_id": "UC123",
                "uploader_id": "@openai",
                "entries": [
                    {
                        "id": "PL123",
                        "title": "playlist",
                        "webpage_url": "https://www.youtube.com/playlist?list=PL123",
                        "channel": "OpenAI",
                    }
                ]
            },
        ) as mock_extract:
            items = self.provider.channel_playlists("UC123", limit=1)
        mock_extract.assert_called_once_with("https://www.youtube.com/channel/UC123/playlists", flat=True, use_auth=False)
        self.assertEqual(items[0]["source_feed"], "channel_playlists")
        self.assertEqual(items[0]["type"], "playlist")
        self.assertEqual(items[0]["channel"]["title"], "OpenAI")

    def test_playlist_videos_marks_playlist_source_and_backfills_channel(self) -> None:
        with patch.object(
            self.provider,
            "_extract",
            return_value={
                "channel": "OpenAI",
                "channel_id": "UC123",
                "entries": [
                    {
                        "id": "abc123",
                        "title": "hello",
                        "webpage_url": "https://www.youtube.com/watch?v=abc123",
                    }
                ],
            },
        ) as mock_extract:
            items = self.provider.playlist_videos("PL123", limit=1)
        mock_extract.assert_called_once_with("https://www.youtube.com/playlist?list=PL123", flat=True, use_auth=False)
        self.assertEqual(items[0]["source_feed"], "playlist_videos")
        self.assertEqual(items[0]["channel"]["title"], "OpenAI")
        self.assertEqual(items[0]["channel"]["id"], "UC123")

    def test_channel_includes_tab_previews_and_status(self) -> None:
        with patch.object(
            self.provider,
            "_extract",
            return_value={
                "channel": "OpenAI",
                "channel_id": "UC123",
                "uploader_id": "@openai",
                "webpage_url": "https://www.youtube.com/@openai",
                "entries": [{"id": "root1", "title": "OpenAI - Videos", "webpage_url": "https://www.youtube.com/@openai/videos"}],
            },
        ):
            with patch.object(self.provider, "channel_videos", return_value=[{"id": "v1"}]) as mock_videos:
                with patch.object(self.provider, "channel_playlists", return_value=[{"id": "p1"}]) as mock_playlists:
                    data = self.provider.channel("@openai", limit=7)
        mock_videos.assert_called_once_with("@openai", limit=5)
        mock_playlists.assert_called_once_with("@openai", limit=5)
        self.assertEqual(data["tab_previews"]["videos"][0]["id"], "v1")
        self.assertTrue(data["tab_status"]["playlists"]["available"])
        self.assertEqual(data["recent_items"][0]["id"], "v1")


if __name__ == "__main__":
    unittest.main()
