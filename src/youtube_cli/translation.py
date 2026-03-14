from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Iterable

from .errors import YoutubeCliError


class Translator:
    name = "base"

    def translate(
        self,
        texts: list[str],
        *,
        source_lang: str,
        target_lang: str,
    ) -> list[str]:
        raise NotImplementedError


class OpenAITranslator(Translator):
    name = "openai"

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: float,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds

    def translate(
        self,
        texts: list[str],
        *,
        source_lang: str,
        target_lang: str,
    ) -> list[str]:
        if not texts:
            return []
        if source_lang == target_lang:
            return list(texts)
        payload = {
            "model": self.model,
            "temperature": 0,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a translation engine. "
                        "Translate the input from {source} to {target}. "
                        "Return a JSON array of strings with the same length as input. "
                        "Preserve line breaks inside each item. "
                        "Return JSON only."
                    ).format(source=source_lang, target=target_lang),
                },
                {
                    "role": "user",
                    "content": json.dumps(texts, ensure_ascii=False),
                },
            ],
        }
        data = _post_json(
            f"{self.base_url}/chat/completions",
            payload,
            api_key=self.api_key,
            timeout_seconds=self.timeout_seconds,
        )
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise YoutubeCliError(
                "translation_failed",
                "翻译服务返回了无法解析的响应。",
                hint="检查模型与接口是否兼容，并确认 API 返回符合 OpenAI chat 完成格式。",
                source="translation",
            ) from exc
        translated = _parse_json_list(content)
        if len(translated) != len(texts):
            raise YoutubeCliError(
                "translation_failed",
                "翻译结果数量与输入不一致。",
                hint="请稍后重试或调整翻译批次大小。",
                source="translation",
            )
        return [str(item) for item in translated]


class MockTranslator(Translator):
    name = "mock"

    def __init__(self, prefix: str = "[translated] ") -> None:
        self.prefix = prefix

    def translate(
        self,
        texts: list[str],
        *,
        source_lang: str,
        target_lang: str,
    ) -> list[str]:
        return [f"{self.prefix}{text}" if text else "" for text in texts]


def build_translator() -> Translator:
    provider = os.getenv("YOUTUBE_CLI_TRANSLATION_PROVIDER")
    if not provider:
        if os.getenv("YOUTUBE_CLI_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY"):
            provider = "openai"
        else:
            raise YoutubeCliError(
                "translation_unavailable",
                "未配置字幕翻译服务。",
                hint=(
                    "设置 `YOUTUBE_CLI_TRANSLATION_PROVIDER=openai` 并提供 "
                    "`YOUTUBE_CLI_OPENAI_API_KEY` (或 `OPENAI_API_KEY`)。"
                ),
                source="translation",
            )
    provider = provider.lower()
    if provider == "openai":
        api_key = os.getenv("YOUTUBE_CLI_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise YoutubeCliError(
                "translation_unavailable",
                "未检测到 OpenAI API Key。",
                hint=(
                    "设置 `YOUTUBE_CLI_OPENAI_API_KEY` (或 `OPENAI_API_KEY`) 后再重试。"
                ),
                source="translation",
            )
        base_url = os.getenv("YOUTUBE_CLI_OPENAI_BASE_URL", "https://api.openai.com/v1")
        model = os.getenv("YOUTUBE_CLI_OPENAI_MODEL")
        if not model:
            raise YoutubeCliError(
                "translation_unavailable",
                "未指定翻译模型。",
                hint="设置 `YOUTUBE_CLI_OPENAI_MODEL` 指定可用模型名称。",
                source="translation",
            )
        timeout = float(os.getenv("YOUTUBE_CLI_OPENAI_TIMEOUT", "30"))
        return OpenAITranslator(
            api_key=api_key,
            base_url=base_url,
            model=model,
            timeout_seconds=timeout,
        )
    if provider == "mock":
        prefix = os.getenv("YOUTUBE_CLI_TRANSLATION_MOCK_PREFIX", "[translated] ")
        return MockTranslator(prefix=prefix)
    raise YoutubeCliError(
        "translation_unavailable",
        f"未知的翻译服务提供方: {provider}",
        hint="可选值: openai, mock",
        source="translation",
    )


def translate_segments(
    translator: Translator,
    segments: list[dict[str, Any]],
    *,
    source_lang: str,
    target_lang: str,
    batch_size: int = 20,
) -> list[dict[str, Any]]:
    texts = [str(segment.get("text") or "") for segment in segments]
    translated = [""] * len(texts)
    indexed_texts = [(index, text) for index, text in enumerate(texts) if text.strip()]
    if not indexed_texts:
        return [dict(segment) for segment in segments]
    if batch_size <= 0:
        batch_size = 20
    for start in range(0, len(indexed_texts), batch_size):
        batch = indexed_texts[start : start + batch_size]
        batch_texts = [text for _, text in batch]
        batch_translated = translator.translate(
            batch_texts,
            source_lang=source_lang,
            target_lang=target_lang,
        )
        if len(batch_translated) != len(batch_texts):
            raise YoutubeCliError(
                "translation_failed",
                "翻译结果数量与输入不一致。",
                hint="请稍后重试或调整翻译批次大小。",
                source="translation",
            )
        for (index, _), translated_text in zip(batch, batch_translated):
            translated[index] = str(translated_text)
    result: list[dict[str, Any]] = []
    for segment, text in zip(segments, translated):
        updated = dict(segment)
        updated["text"] = text
        result.append(updated)
    return result


def _parse_json_list(value: str) -> list[Any]:
    value = value.strip()
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return parsed
    except json.JSONDecodeError:
        pass
    start = value.find("[")
    end = value.rfind("]")
    if start != -1 and end != -1 and end > start:
        try:
            parsed = json.loads(value[start : end + 1])
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError as exc:
            raise YoutubeCliError(
                "translation_failed",
                "翻译服务返回了无法解析的 JSON。",
                hint="请确认翻译服务输出 JSON 数组。",
                source="translation",
            ) from exc
    raise YoutubeCliError(
        "translation_failed",
        "翻译服务返回了无法解析的 JSON。",
        hint="请确认翻译服务输出 JSON 数组。",
        source="translation",
    )


def _post_json(
    url: str,
    payload: dict[str, Any],
    *,
    api_key: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        raise YoutubeCliError(
            "translation_failed",
            "翻译服务请求失败。",
            hint=body.strip() or str(exc),
            source="translation",
        ) from exc
    except urllib.error.URLError as exc:
        raise YoutubeCliError(
            "translation_failed",
            "无法连接翻译服务。",
            hint=str(exc),
            source="translation",
        ) from exc
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise YoutubeCliError(
            "translation_failed",
            "翻译服务返回了无法解析的响应。",
            hint=raw[:2000],
            source="translation",
        ) from exc
