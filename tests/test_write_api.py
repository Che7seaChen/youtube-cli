from __future__ import annotations

import http.cookiejar
import io
import ssl
import unittest
import urllib.error
from unittest.mock import Mock, patch

from youtube_cli.config import AuthConfig
from youtube_cli.errors import YoutubeCliError
from youtube_cli.reverse.write_api import YoutubeWriteClient


class YoutubeWriteClientTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = YoutubeWriteClient(AuthConfig(browser="chrome"))

    def test_resolve_video_id_from_watch_url(self) -> None:
        self.assertEqual(
            self.client._resolve_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
            "dQw4w9WgXcQ",
        )

    def test_resolve_playlist_id_from_playlist_url(self) -> None:
        self.assertEqual(
            self.client._resolve_playlist_id("https://www.youtube.com/playlist?list=PL123"),
            "PL123",
        )

    def test_add_to_playlist_dry_run_returns_summary(self) -> None:
        payload = self.client.add_to_playlist("dQw4w9WgXcQ", "PL123", dry_run=True)
        self.assertEqual(payload["playlist_id"], "PL123")
        self.assertEqual(payload["target_video_id"], "dQw4w9WgXcQ")
        self.assertTrue(payload["dry_run"])

    def test_create_playlist_dry_run_returns_summary(self) -> None:
        payload = self.client.create_playlist(
            "Language Acquisition",
            description="notes",
            privacy="unlisted",
            dry_run=True,
        )
        self.assertEqual(payload["title"], "Language Acquisition")
        self.assertEqual(payload["description"], "notes")
        self.assertEqual(payload["privacy"], "UNLISTED")
        self.assertTrue(payload["dry_run"])

    def test_delete_playlist_dry_run_returns_summary(self) -> None:
        payload = self.client.delete_playlist("PL123", dry_run=True)
        self.assertEqual(payload["playlist_id"], "PL123")
        self.assertTrue(payload["dry_run"])

    def test_sid_authorization_uses_available_cookie(self) -> None:
        jar = http.cookiejar.CookieJar()
        cookie = http.cookiejar.Cookie(
            version=0,
            name="SAPISID",
            value="testsid",
            port=None,
            port_specified=False,
            domain=".youtube.com",
            domain_specified=True,
            domain_initial_dot=True,
            path="/",
            path_specified=True,
            secure=True,
            expires=None,
            discard=True,
            comment=None,
            comment_url=None,
            rest={},
        )
        jar.set_cookie(cookie)
        header = self.client._get_sid_authorization_header(jar, origin="https://www.youtube.com")
        self.assertIsNotNone(header)
        self.assertIn("SAPISIDHASH", header)

    def test_describe_playlist_target_extracts_title_and_owner(self) -> None:
        html = """
        <script>
        var ytInitialData = {
          "header": {
            "pageHeaderRenderer": {
              "content": {
                "pageHeaderViewModel": {
                  "title": {
                    "dynamicTextViewModel": {
                      "text": {
                        "content": "Language Aquisition"
                      }
                    }
                  },
                  "metadata": {
                    "contentMetadataViewModel": {
                      "metadataRows": [
                        {
                          "metadataParts": [
                            {
                              "avatarStack": {
                                "avatarStackViewModel": {
                                  "text": {
                                    "content": "by Geworfenheit"
                                  }
                                }
                              }
                            }
                          ]
                        }
                      ]
                    }
                  }
                }
              }
            }
          }
        };
        </script>
        """
        opener = Mock()
        with patch.object(self.client, "_fetch_html", return_value=html):
            payload = self.client._describe_playlist_target("PL123", opener=opener)
        self.assertEqual(payload["title"], "Language Aquisition")
        self.assertEqual(payload["owner"], "Geworfenheit")

    def test_playlist_edit_http_403_includes_playlist_context(self) -> None:
        jar = http.cookiejar.CookieJar()
        opener = Mock()
        opener.open.side_effect = urllib.error.HTTPError(
            url="https://www.youtube.com/youtubei/v1/browse/edit_playlist",
            code=403,
            msg="Forbidden",
            hdrs=None,
            fp=io.BytesIO(
                b'{"error":{"code":403,"message":"Sorry, something went wrong.","status":"PERMISSION_DENIED"}}'
            ),
        )

        with patch.object(self.client, "_load_cookie_jar", return_value=jar):
            with patch.object(self.client, "_build_opener", return_value=opener):
                with patch.object(self.client, "_fetch_html", return_value="<html></html>"):
                    with patch.object(
                        self.client,
                        "_extract_ytcfg",
                        return_value={"INNERTUBE_API_KEY": "key", "INNERTUBE_CONTEXT": {"client": {}}},
                    ):
                        with patch.object(
                            self.client,
                            "_describe_playlist_target",
                            return_value={"title": "美剧精讲 + 巩固", "owner": "zaharaEnglish"},
                        ):
                            with self.assertRaises(YoutubeCliError) as ctx:
                                self.client.add_to_playlist(
                                    "dQw4w9WgXcQ",
                                    "PL35TJ0P4r10AoGD6l4YxsidmQByNL8Qxm",
                                    dry_run=False,
                                )

        self.assertEqual(ctx.exception.code, "permission_denied")
        self.assertIn("页面所有者: zaharaEnglish", ctx.exception.hint or "")
        self.assertIn("不是当前账号自建列表", ctx.exception.hint or "")

    def test_fetch_html_wraps_tls_failure(self) -> None:
        opener = Mock()
        opener.open.side_effect = urllib.error.URLError(
            ssl.SSLCertVerificationError("certificate verify failed")
        )

        with self.assertRaises(YoutubeCliError) as ctx:
            self.client._fetch_html("https://www.youtube.com/", opener=opener)

        self.assertEqual(ctx.exception.code, "tls_error")
        self.assertIn("--no-check-certificate", ctx.exception.hint or "")

    def test_fetch_html_wraps_network_failure(self) -> None:
        opener = Mock()
        opener.open.side_effect = urllib.error.URLError("temporary failure in name resolution")

        with self.assertRaises(YoutubeCliError) as ctx:
            self.client._fetch_html("https://www.youtube.com/", opener=opener)

        self.assertEqual(ctx.exception.code, "network_error")


if __name__ == "__main__":
    unittest.main()
