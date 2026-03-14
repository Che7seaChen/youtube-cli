from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import config_path

MAX_METRICS_ENTRIES = 200
DEFAULT_RECENT_ENTRIES = 10


def _metrics_path() -> Path:
    return config_path().parent / "metrics.json"


def _load_entries(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]


def _write_entries(path: Path, entries: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(entries, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def record_metric(
    *,
    command: str,
    ok: bool,
    error_code: str | None = None,
    mode: str | None = None,
    auth_configured: bool | None = None,
    duration_ms: int | None = None,
) -> None:
    entry = {
        "ts": datetime.now().astimezone().isoformat(timespec="seconds"),
        "command": command,
        "ok": ok,
        "error_code": error_code,
        "mode": mode,
        "auth_configured": auth_configured,
        "duration_ms": duration_ms,
    }
    try:
        path = _metrics_path()
        entries = _load_entries(path)
        entries.append(entry)
        if len(entries) > MAX_METRICS_ENTRIES:
            entries = entries[-MAX_METRICS_ENTRIES :]
        _write_entries(path, entries)
    except Exception:
        return


def summarize_metrics(recent_limit: int = DEFAULT_RECENT_ENTRIES) -> dict[str, Any]:
    path = _metrics_path()
    entries = _load_entries(path)
    total = len(entries)
    ok_count = sum(1 for item in entries if item.get("ok"))
    fail_count = total - ok_count
    by_error_code: dict[str, int] = {}
    for item in entries:
        code = item.get("error_code")
        if not code:
            continue
        by_error_code[code] = by_error_code.get(code, 0) + 1
    recent = entries[-recent_limit:] if recent_limit > 0 else []
    return {
        "enabled": True,
        "total": total,
        "ok": ok_count,
        "fail": fail_count,
        "by_error_code": by_error_code,
        "recent": recent,
    }
