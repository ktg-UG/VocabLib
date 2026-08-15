"""2段目: ローカルLLM（Ollama）

オフラインでも例文が出せるようにするための段。
Ollamaが起動していなければ `complete()` が None を返し、次の段に落ちる。
"""
from __future__ import annotations

import logging

import requests

from .. import config

_LOGGER = logging.getLogger(__name__)


class OllamaProvider:
    name = "ollama"

    def __init__(
        self,
        host: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
    ):
        self._host = (host or config.OLLAMA_HOST).rstrip("/")
        self._model = model or config.OLLAMA_MODEL
        self._default_timeout = (
            config.LLM_TIMEOUT_SECONDS if timeout is None else timeout
        )

    def is_available(self) -> bool:
        # 事前のヘルスチェックはしない。生存確認のHTTPを毎回1往復増やすより、
        # 本番のリクエストが失敗したら次の段に落ちる方が速い。
        return True

    def complete(self, prompt: str, timeout: float | None = None) -> str | None:
        seconds = self._default_timeout if timeout is None else timeout
        try:
            response = requests.post(
                f"{self._host}/api/generate",
                json={"model": self._model, "prompt": prompt, "stream": False},
                timeout=seconds,
            )
        except Exception as e:
            _LOGGER.warning("Ollama 呼び出し失敗: %s", e)
            return None

        if response.status_code != 200:
            _LOGGER.warning("Ollama status: %s", response.status_code)
            return None

        try:
            payload = response.json()
        except ValueError:
            return None

        text = payload.get("response") or payload.get("text")
        return text.strip() if text else None
