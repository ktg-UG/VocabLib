"""3段フォールバックの司令塔

    1. Gemini Flash        （APIキーがあれば）
    2. Ollama / gemma2:2b  （ローカルで動いていれば）
    3. ローカル生成         （必ず成功する終端）

v1との違い: 「呼べたが出力が使い物にならない」場合も次の段に落ちる。
v1は同じOllamaに3回再試行するだけで、別手段に切り替わらなかった。
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Iterator, Sequence

from .. import config
from .base import LLMProvider
from .gemini import GeminiProvider
from .ollama import OllamaProvider
from .parsing import (
    extract_example_line,
    extract_json,
    fallback_example_sentence,
    looks_japanese,
    sentence_uses_word,
)

_LOGGER = logging.getLogger(__name__)

MAX_MEANING_LENGTH = 40
MAX_POS_LENGTH = 10


@dataclass(frozen=True)
class WordInfo:
    """オートフィルで取得した単語情報（あくまで下書き。ユーザーが編集できる）"""

    japanese: str
    part_of_speech: str | None = None


class LLMClient:
    def __init__(self, providers: Sequence[LLMProvider] | None = None):
        """
        Args:
            providers: 試す順に並べたProvider。省略時は Gemini → Ollama。
                テストではネットに触らない偽Providerを注入する。
        """
        self._providers = list(providers) if providers is not None else [
            GeminiProvider(),
            OllamaProvider(),
        ]

    # ── 例文生成（F-03） ──────────────────────────────────────────────────

    def generate_example_sentence(self, word: str, meaning: str) -> str:
        """単語を使った例文を返す。**必ず文字列を返す**（最終段があるため）"""
        prompt = _example_prompt(word, meaning)

        for provider in self._available_providers():
            raw = provider.complete(prompt, timeout=config.LLM_TIMEOUT_SECONDS)
            if not raw:
                continue

            sentence = extract_example_line(raw)
            if not sentence:
                _LOGGER.debug("%s: 例文の形式が不正のため次の段へ", provider.name)
                continue
            if not sentence_uses_word(sentence, word):
                # 対象単語を含まない例文は覚える助けにならないので採用しない
                _LOGGER.debug("%s: 例文が「%s」を含まないため次の段へ", provider.name, word)
                continue

            _LOGGER.info("例文を生成: provider=%s word=%s", provider.name, word)
            return sentence

        _LOGGER.info("例文を生成: provider=fallback word=%s（全てのLLMが失敗）", word)
        return fallback_example_sentence(word, meaning)

    # ── 単語オートフィル（F-09） ──────────────────────────────────────────

    def lookup_word(self, english: str) -> WordInfo | None:
        """和訳と品詞を引く。全段失敗したら None（空欄で手入力してもらう）

        オートフィルはモーダルダイアログの合間に走るためUIを止める。
        1段目が上限まで粘った時点で打ち切り、2段目に持ち越さない
        （待ち時間が段数ぶん積み上がるのを防ぐ）。
        """
        prompt = _lookup_prompt(english)
        budget = config.AUTOFILL_TIMEOUT_SECONDS
        started = time.monotonic()

        for provider in self._available_providers():
            if time.monotonic() - started >= budget:
                _LOGGER.info("オートフィル: 待ち時間の上限に達したため打ち切り word=%s", english)
                break

            raw = provider.complete(prompt, timeout=budget)
            if not raw:
                continue

            info = _parse_word_info(raw)
            if info is None:
                _LOGGER.debug("%s: 単語情報を解釈できないため次の段へ", provider.name)
                continue

            _LOGGER.info("オートフィル: provider=%s word=%s", provider.name, english)
            return info

        _LOGGER.info("オートフィル: 全てのLLMが失敗 word=%s", english)
        return None

    # ── 内部 ─────────────────────────────────────────────────────────────

    def _available_providers(self) -> Iterator[LLMProvider]:
        for provider in self._providers:
            try:
                if provider.is_available():
                    yield provider
            except Exception:
                _LOGGER.warning("%s の可用性判定に失敗したのでスキップ", provider.name)


def _parse_word_info(raw: str) -> WordInfo | None:
    parsed = extract_json(raw)
    if not parsed:
        return None

    japanese = str(parsed.get("japanese") or "").strip()
    if not japanese or len(japanese) > MAX_MEANING_LENGTH:
        return None
    if not looks_japanese(japanese):
        # 英語のまま返ってきた場合はオートフィルとして役に立たない
        return None

    part_of_speech = str(parsed.get("part_of_speech") or "").strip()
    if len(part_of_speech) > MAX_POS_LENGTH:
        part_of_speech = ""

    return WordInfo(japanese=japanese, part_of_speech=part_of_speech or None)


def _example_prompt(word: str, meaning: str) -> str:
    """v1で実際にLLMの誤りを潰しながら育てたプロンプトを踏襲している"""
    return f"""英単語「{word}」（意味: {meaning}）を使った、短くて記憶に残る英語の例文を1つ作ってください。

【必須ルール】
- 例文には必ず「{word}」を含めること（活用形・語形変化は可）
- 5〜8語程度の短い文にすること
- 具体的な情景が浮かぶ、覚えやすい内容にすること
- 和訳は必ず自然な**日本語**で書くこと（中国語は絶対に使わない）

出力は次の1行だけ。番号・説明・引用符は不要:
英語の例文 — 日本語訳

例: Cats abandon their owners daily. — 猫は毎日飼い主を見捨てる。
例: He postponed the meeting again. — 彼はまた会議を延期した。"""


def _lookup_prompt(english: str) -> str:
    return f"""英単語「{english}」の最も一般的な日本語訳と品詞を1つだけ答えてください。

【必須ルール】
- 意味は最も基本的・頻出のもの**1つだけ**（複数書かない）
- 動詞は「〜する」の形、名詞は名詞のまま書くこと
- 品詞は次のいずれか1語: 名詞 / 動詞 / 形容詞 / 副詞 / 前置詞 / 接続詞 / 代名詞 / 間投詞 / 熟語
- 和訳は必ず自然な**日本語**で書くこと（中国語・英語は絶対に使わない）

以下のJSON形式のみを出力してください。説明文・コードブロックは不要:
{{"japanese": "延期する", "part_of_speech": "動詞"}}"""
