# Changelog

All notable changes to this project will be documented in this file.

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
