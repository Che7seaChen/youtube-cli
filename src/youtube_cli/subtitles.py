from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .errors import YoutubeCliError

TIMESTAMP_RE = re.compile(
    r"(?P<h>\d{2}):(?P<m>\d{2}):(?P<s>\d{2})\.(?P<ms>\d{3})"
)


def parse_vtt_timestamp(value: str) -> float:
    match = TIMESTAMP_RE.fullmatch(value.strip())
    if not match:
        raise YoutubeCliError("provider_error", f"无法解析字幕时间戳: {value}", source="yt_dlp")
    hours = int(match.group("h"))
    minutes = int(match.group("m"))
    seconds = int(match.group("s"))
    milliseconds = int(match.group("ms"))
    return hours * 3600 + minutes * 60 + seconds + milliseconds / 1000


def parse_vtt(content: str) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    blocks = re.split(r"\n\s*\n", content.strip())
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines or lines[0].startswith("WEBVTT"):
            continue
        if "-->" not in lines[0]:
            lines = lines[1:]
        if not lines or "-->" not in lines[0]:
            continue
        timing, *text_lines = lines
        start_str, end_str = [part.strip().split(" ")[0] for part in timing.split("-->")]
        segments.append(
            {
                "start_seconds": parse_vtt_timestamp(start_str),
                "end_seconds": parse_vtt_timestamp(end_str),
                "text": " ".join(text_lines).strip(),
            }
        )
    return segments


def parse_json3(content: str) -> list[dict[str, Any]]:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise YoutubeCliError("provider_error", "无法解析 json3 字幕内容。", source="yt_dlp") from exc

    segments: list[dict[str, Any]] = []
    for event in payload.get("events", []):
        segs = event.get("segs") or []
        if not segs:
            continue
        text = "".join(seg.get("utf8", "") for seg in segs).strip()
        if not text:
            continue
        start_ms = event.get("tStartMs")
        if start_ms is None:
            continue
        duration_ms = event.get("dDurationMs") or 0
        segments.append(
            {
                "start_seconds": start_ms / 1000,
                "end_seconds": (start_ms + duration_ms) / 1000,
                "text": text,
            }
        )
    return segments


def _normalize_text(value: str) -> str:
    return "\n".join(line.strip() for line in value.replace("\r\n", "\n").split("\n") if line.strip())


def format_srt_timestamp(seconds: float) -> str:
    total_ms = max(0, int(round(seconds * 1000)))
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"


def format_vtt_timestamp(seconds: float) -> str:
    total_ms = max(0, int(round(seconds * 1000)))
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{milliseconds:03d}"


def merge_bilingual_segments(
    primary_segments: list[dict[str, Any]],
    secondary_segments: list[dict[str, Any]],
    *,
    tolerance_seconds: float = 0.35,
) -> list[dict[str, Any]]:
    if not secondary_segments:
        return list(primary_segments)
    merged: list[dict[str, Any]] = []
    secondary_index = 0
    for primary in primary_segments:
        start = float(primary.get("start_seconds") or 0)
        end = float(primary.get("end_seconds") or start)
        text_parts = [_normalize_text(str(primary.get("text") or ""))]
        while secondary_index < len(secondary_segments):
            candidate_end = float(secondary_segments[secondary_index].get("end_seconds") or 0)
            if candidate_end + tolerance_seconds < start:
                secondary_index += 1
                continue
            break
        candidate_texts: list[str] = []
        scan_index = secondary_index
        while scan_index < len(secondary_segments):
            candidate = secondary_segments[scan_index]
            candidate_start = float(candidate.get("start_seconds") or 0)
            if candidate_start - tolerance_seconds > end:
                break
            overlaps = (
                candidate_start <= end + tolerance_seconds
                and float(candidate.get("end_seconds") or candidate_start) >= start - tolerance_seconds
            )
            if overlaps:
                normalized = _normalize_text(str(candidate.get("text") or ""))
                if normalized:
                    candidate_texts.append(normalized)
            scan_index += 1
        if candidate_texts:
            candidate_text = "\n".join(dict.fromkeys(candidate_texts))
            if candidate_text and candidate_text != text_parts[0]:
                text_parts.append(candidate_text)
        merged.append(
            {
                "start_seconds": start,
                "end_seconds": end,
                "text": "\n".join(part for part in text_parts if part).strip(),
            }
        )
    return merged


def render_subtitle_segments(segments: list[dict[str, Any]], *, fmt: str) -> str:
    fmt = fmt.lower()
    blocks: list[str] = []
    for index, segment in enumerate(segments, start=1):
        start = float(segment.get("start_seconds") or 0)
        end = float(segment.get("end_seconds") or start)
        text = _normalize_text(str(segment.get("text") or ""))
        if not text:
            continue
        if fmt == "srt":
            blocks.append(
                f"{index}\n{format_srt_timestamp(start)} --> {format_srt_timestamp(end)}\n{text}"
            )
        elif fmt == "vtt":
            blocks.append(
                f"{format_vtt_timestamp(start)} --> {format_vtt_timestamp(end)}\n{text}"
            )
        else:
            raise YoutubeCliError(
                "unsupported_operation",
                f"不支持的字幕文件格式: {fmt}",
                source="youtube_cli",
            )
    if fmt == "vtt":
        return "WEBVTT\n\n" + "\n\n".join(blocks) + ("\n" if blocks else "")
    return "\n\n".join(blocks) + ("\n" if blocks else "")


def write_subtitle_file(
    path: Path,
    segments: list[dict[str, Any]],
    *,
    fmt: str,
) -> Path:
    path.write_text(render_subtitle_segments(segments, fmt=fmt), encoding="utf-8")
    return path
