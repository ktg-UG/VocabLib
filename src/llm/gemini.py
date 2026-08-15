"""1段目: Google Gemini

APIキーが未設定なら `is_available()` が False を返し、この段は丸ごと飛ばされる。
（オフライン前提のアプリなので、キーが無いことは異常ではない）
"""
from __future__ import annotations

import logging

from .. import config

_LOGGER = logging.getLogger(__name__)

# Gemini APIが受け付けるデッドラインの下限。
# これ未満を送ると 400 INVALID_ARGUMENT で即座に弾かれ、
# 「速く諦めるつもりが1段目を丸ごと失う」という結果になる。
MIN_TIMEOUT_SECONDS = 10.0


class GeminiProvider:
    name = "gemini"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float | None = None,
    ):
        self._api_key = config.GEMINI_API_KEY if api_key is None else api_key
        self._model = model or config.GEMINI_MODEL
        self._default_timeout = (
            config.LLM_TIMEOUT_SECONDS if timeout is None else timeout
        )
        # タイムアウトごとにクライアントを使い回す（google-genai はクライアント単位で設定するため）
        self._clients: dict[float, object] = {}

    def is_available(self) -> bool:
        return bool(self._api_key)

    def complete(self, prompt: str, timeout: float | None = None) -> str | None:
        if not self.is_available():
            return None

        requested = self._default_timeout if timeout is None else timeout
        seconds = max(requested, MIN_TIMEOUT_SECONDS)
        try:
            client = self._client_for(seconds)
            response = client.models.generate_content(
                model=self._model,
                contents=prompt,
                config=_generation_config(),
            )
        except Exception as e:
            _LOGGER.warning("Gemini 呼び出し失敗: %s", e)
            return None

        text = getattr(response, "text", None)
        return text.strip() if text else None

    def _client_for(self, seconds: float):
        key = round(seconds, 3)
        if key not in self._clients:
            self._clients[key] = _build_client(self._api_key, seconds)
        return self._clients[key]


def _generation_config():
    """自動関数呼び出し（AFC）を無効にした生成設定を返す。

    このアプリはツールを一切渡さないため、AFCは不要なうえ
    呼び出しのたびにSDKが警告を出す。設定に失敗したら None を返し、
    既定設定のまま実行する（警告が出るだけで動作はする）。
    """
    try:
        from google.genai import types

        return types.GenerateContentConfig(
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )
    except Exception as e:
        _LOGGER.debug("Geminiの生成設定をスキップ: %s", e)
        return None


def _build_client(api_key: str, seconds: float):
    """google-genai のクライアントを作る。

    タイムアウト指定はSDKのバージョンで書き方が変わりうるため、
    設定に失敗してもクライアント自体は作れるようにしておく
    （タイムアウトが効かないことより、LLMが丸ごと使えないことの方が困る）。
    """
    from google import genai

    try:
        from google.genai import types

        return genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=int(seconds * 1000)),
        )
    except Exception as e:
        _LOGGER.debug("Geminiのタイムアウト設定をスキップ: %s", e)
        return genai.Client(api_key=api_key)
