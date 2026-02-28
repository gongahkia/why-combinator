from __future__ import annotations

import json
import os
import random
import time
import urllib.error
import urllib.request
from dataclasses import dataclass


class CodexClientError(Exception):
    pass


class CodexTemporaryError(CodexClientError):
    pass


class CodexRateLimitError(CodexTemporaryError):
    pass


class CodexPermanentError(CodexClientError):
    pass


@dataclass(frozen=True)
class CodexRequest:
    prompt: str
    temperature: float = 0.2
    max_output_tokens: int = 512


@dataclass(frozen=True)
class CodexResponse:
    text: str
    model: str
    raw: dict[str, object]


class CodexClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        max_retries: int = 3,
        backoff_base_seconds: float = 0.5,
    ) -> None:
        self._api_key = api_key or os.getenv("MODEL_API_KEY", "")
        self._base_url = base_url or os.getenv("CODEX_API_URL", "https://api.openai.com/v1/responses")
        self._model = model or os.getenv("CODEX_MODEL", "gpt-5")
        self._max_retries = max_retries
        self._backoff_base_seconds = backoff_base_seconds

    def call(self, request: CodexRequest) -> CodexResponse:
        if not self._api_key:
            raise CodexPermanentError("MODEL_API_KEY is required for Codex client calls")

        body = json.dumps(
            {
                "model": self._model,
                "input": request.prompt,
                "temperature": request.temperature,
                "max_output_tokens": request.max_output_tokens,
            }
        ).encode("utf-8")
        http_request = urllib.request.Request(
            self._base_url,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self._api_key}",
            },
        )

        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                with urllib.request.urlopen(http_request, timeout=30) as response:  # noqa: S310
                    payload = json.loads(response.read().decode("utf-8"))
                text = _extract_output_text(payload)
                return CodexResponse(text=text, model=self._model, raw=payload)
            except urllib.error.HTTPError as exc:
                if exc.code == 429:
                    last_error = CodexRateLimitError(f"rate limited: {exc}")
                elif 500 <= exc.code < 600:
                    last_error = CodexTemporaryError(f"upstream temporary error: {exc}")
                else:
                    raise CodexPermanentError(f"permanent HTTP error: {exc}") from exc
            except (urllib.error.URLError, TimeoutError) as exc:
                last_error = CodexTemporaryError(f"temporary transport error: {exc}")

            if attempt >= self._max_retries:
                break
            delay = self._backoff_base_seconds * (2**attempt) + random.uniform(0, 0.2)
            time.sleep(delay)

        assert last_error is not None
        raise last_error


def _extract_output_text(payload: dict[str, object]) -> str:
    output = payload.get("output")
    if isinstance(output, list):
        text_chunks: list[str] = []
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for block in content:
                if isinstance(block, dict) and block.get("type") == "output_text":
                    text_value = block.get("text")
                    if isinstance(text_value, str):
                        text_chunks.append(text_value)
        if text_chunks:
            return "\n".join(text_chunks)
    if isinstance(payload.get("output_text"), str):
        return str(payload["output_text"])
    return ""
