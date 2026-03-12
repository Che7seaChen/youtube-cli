from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from youtube_cli.subtitles import merge_bilingual_segments, parse_json3, render_subtitle_segments, write_subtitle_file


class SubtitleParsingTests(unittest.TestCase):
    def test_parse_json3_extracts_timeline_segments(self) -> None:
        payload = """
        {
          "events": [
            {"tStartMs": 0, "dDurationMs": 1200, "segs": [{"utf8": "Hello"}]},
            {"tStartMs": 1500, "dDurationMs": 900, "segs": [{"utf8": " world"}]},
            {"tStartMs": 2500, "segs": [{"utf8": "\\n"}]}
          ]
        }
        """
        segments = parse_json3(payload)
        self.assertEqual(len(segments), 2)
        self.assertEqual(segments[0]["text"], "Hello")
        self.assertEqual(segments[0]["start_seconds"], 0)
        self.assertEqual(segments[0]["end_seconds"], 1.2)
        self.assertEqual(segments[1]["text"], "world")

    def test_merge_bilingual_segments_keeps_primary_timeline(self) -> None:
        primary = [
            {"start_seconds": 0.0, "end_seconds": 1.0, "text": "Hello"},
            {"start_seconds": 1.5, "end_seconds": 2.5, "text": "World"},
        ]
        secondary = [
            {"start_seconds": 0.05, "end_seconds": 0.95, "text": "你好"},
            {"start_seconds": 1.55, "end_seconds": 2.45, "text": "世界"},
        ]
        merged = merge_bilingual_segments(primary, secondary)
        self.assertEqual(merged[0]["start_seconds"], 0.0)
        self.assertEqual(merged[0]["text"], "Hello\n你好")
        self.assertEqual(merged[1]["text"], "World\n世界")

    def test_render_srt_and_write_file(self) -> None:
        segments = [{"start_seconds": 0.0, "end_seconds": 1.2, "text": "Hello\n你好"}]
        rendered = render_subtitle_segments(segments, fmt="srt")
        self.assertIn("00:00:00,000 --> 00:00:01,200", rendered)
        self.assertIn("Hello\n你好", rendered)
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "sample.srt"
            write_subtitle_file(path, segments, fmt="srt")
            self.assertTrue(path.exists())
            self.assertIn("Hello", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
