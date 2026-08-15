"""リモート（Supabase）へのアクセス

`SyncEngine` はこのファイルの `RemoteClient` が持つ2メソッドしか知らない。
そのおかげで、テストでは偽クライアントを差し込むだけで
ネットワーク無しに同期ロジック全体を検証できる。
"""
from __future__ import annotations

import logging
from typing import Protocol

from .. import config

_LOGGER = logging.getLogger(__name__)


class RemoteClient(Protocol):
    def upsert(self, table: str, rows: list[dict]) -> None:
        """行を投入する。同じidが既にあれば更新する（何度呼んでも同じ結果になる）"""
        ...

    def fetch_since(self, table: str, column: str, since: str | None) -> list[dict]:
        """`column` が `since` より新しい行を取得する。`since` が None なら全件"""
        ...


def is_configured() -> bool:
    """同期に必要な設定が揃っているか。揃っていなければ同期機能を丸ごと無効にする"""
    return bool(config.SUPABASE_URL and config.SUPABASE_SERVICE_ROLE_KEY)


class SupabaseClient:
    """Supabase公式クライアントの薄いラッパー

    `user_id` の付与とフィルタはこのクラスの中だけで完結させる。
    `SyncEngine` は `user_id` を知る必要がなく、Phase 4 で書いたテストを
    1つも変えずに済む。
    """

    def __init__(
        self,
        url: str | None = None,
        key: str | None = None,
        user_id: str | None = None,
    ):
        from supabase import create_client

        self._client = create_client(
            url or config.SUPABASE_URL,
            key or config.SUPABASE_SERVICE_ROLE_KEY,
        )
        self._user_id = config.SUPABASE_USER_ID if user_id is None else user_id

    def upsert(self, table: str, rows: list[dict]) -> None:
        if not rows:
            return
        if self._user_id:
            # Web側のRLSポリシーが user_id で判定するため、送信時に付ける
            rows = [{**row, "user_id": self._user_id} for row in rows]
        self._client.table(table).upsert(rows).execute()

    def fetch_since(self, table: str, column: str, since: str | None) -> list[dict]:
        query = self._client.table(table).select("*")
        if self._user_id:
            # service_role はRLSをバイパスするので、自分で絞らないと
            # 他人の行まで取ってきてしまう
            query = query.eq("user_id", self._user_id)
        if since:
            query = query.gt(column, since)
        return query.execute().data or []
