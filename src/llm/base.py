"""LLM Provider の共通インターフェース

各LLMの違いを `complete()` 1本に押し込める。こうしておくと、
Providerを1つ増やすのに他のコードを触らずに済む。

規約:
    - 例外を上位に投げない。失敗は `None` を返して表現する。
      （LLMの失敗は「異常」ではなく「次の段に落ちる」という想定内の分岐なので）
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMProvider(Protocol):
    name: str

    def is_available(self) -> bool:
        """この段を試す価値があるか（APIキー未設定など、明らかに無理なら False）"""
        ...

    def complete(self, prompt: str, timeout: float | None = None) -> str | None:
        """プロンプトを投げて生テキストを得る。失敗したら None"""
        ...
