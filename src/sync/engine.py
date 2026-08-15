"""同期エンジン（push / pull / 衝突解決）

設計上の要点:

1. **pushが先、pullが後。**
   逆にすると、まだ送っていないローカルの変更が古いリモート値で上書きされる。

2. **衝突解決はLWW（Last-Write-Wins）。**
   `updated_at` が新しい方を採用する。判定は `Store.apply_remote_*` の中で
   SQL 1文（`WHERE excluded.updated_at > ...`）として行うので原子的。

3. **pullした行をpushし返さない。**
   リモートを採用したときは `updated_at` をリモート値のまま入れ、
   `synced_at = now` にする。これを怠ると無限ピンポンになる。

4. **例外を上位に投げない。** 失敗は `SyncResult.error` に入れて返す。
   同期はユーザーが頼んだ操作ではないので、失敗でUIを止めない。
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timezone

from ..db.store import Store
from .remote import RemoteClient

_LOGGER = logging.getLogger(__name__)

LAST_PULLED_AT = "last_pulled_at"

# Postgres由来の時刻表記をローカルの表記に揃えるための対象列。
# 文字列のまま大小比較するため、表記が揃っていないとLWWが誤判定する。
_TIMESTAMP_COLUMNS = (
    "created_at",
    "updated_at",
    "last_reviewed",
    "next_review",
    "answered_at",
)


@dataclass(frozen=True)
class SyncResult:
    pushed: int = 0
    pulled: int = 0
    error: str | None = None
    skipped: bool = False   # 既に同期中だったため何もしなかった

    @property
    def ok(self) -> bool:
        return self.error is None and not self.skipped


class SyncEngine:
    def __init__(self, store: Store, remote: RemoteClient):
        self._store = store
        self._remote = remote
        self._lock = threading.Lock()

    def sync(self) -> SyncResult:
        # 前回の同期が終わっていなければ何もしない（多重実行の防止）
        if not self._lock.acquire(blocking=False):
            _LOGGER.debug("同期が既に実行中のためskip")
            return SyncResult(skipped=True)
        try:
            return self._sync()
        finally:
            self._lock.release()

    def _sync(self) -> SyncResult:
        pushed = 0
        try:
            pushed += self._push_words()
            pushed += self._push_records()
            pushed += self._push_answers()
        except Exception as e:
            _LOGGER.warning("push失敗: %s", e)
            # マークしていないので、送れなかった分は次回そのまま再送される
            return SyncResult(pushed=pushed, error=str(e))

        pulled = 0
        try:
            # pull開始時刻を次回の起点にする。
            # 「pull中に書き込まれた行」を取りこぼさないため、終了時刻ではなく開始時刻を使う。
            started = _now_iso()
            pulled += self._pull_words()
            pulled += self._pull_records()
            pulled += self._pull_answers()
            self._store.set_sync_value(LAST_PULLED_AT, started)
        except Exception as e:
            _LOGGER.warning("pull失敗: %s", e)
            # last_pulled_at を進めないので、次回また同じ範囲を取り直す
            return SyncResult(pushed=pushed, pulled=pulled, error=str(e))

        _LOGGER.info("同期完了: 送信%d件 受信%d件", pushed, pulled)
        return SyncResult(pushed=pushed, pulled=pulled)

    # ── push ─────────────────────────────────────────────────────────────

    def _push_words(self) -> int:
        rows = self._store.get_unsynced_words()
        if not rows:
            return 0
        self._remote.upsert("words", rows)
        self._store.mark_words_synced([r["id"] for r in rows])
        return len(rows)

    def _push_records(self) -> int:
        rows = self._store.get_unsynced_records()
        if not rows:
            return 0
        self._remote.upsert("learning_records", rows)
        self._store.mark_records_synced([r["word_id"] for r in rows])
        return len(rows)

    def _push_answers(self) -> int:
        rows = self._store.get_unsynced_answers()
        if not rows:
            return 0
        self._remote.upsert("answer_log", rows)
        self._store.mark_answers_synced([r["id"] for r in rows])
        return len(rows)

    # ── pull ─────────────────────────────────────────────────────────────

    def _pull_words(self) -> int:
        since = self._store.get_sync_value(LAST_PULLED_AT)
        rows = self._remote.fetch_since("words", "updated_at", since)
        return sum(1 for row in rows if self._store.apply_remote_word(_normalize(row)))

    def _pull_records(self) -> int:
        """必ず `_pull_words()` の後に呼ぶこと。

        `learning_records.word_id` は `words(id)` を参照しているため、
        先に単語が入っていないと外部キー違反で取り込めない。
        """
        since = self._store.get_sync_value(LAST_PULLED_AT)
        rows = self._remote.fetch_since("learning_records", "updated_at", since)
        return sum(1 for row in rows if self._store.apply_remote_record(_normalize(row)))

    def _pull_answers(self) -> int:
        """回答ログを取り込む。

        Supabaseに書く相手がMacアプリだけである以上、通常運用では何も返らない。
        これが効くのは **ローカルDBを失ったときの復元**。
        `answer_log` は正答率・連続日数・日別推移すべての元データなので、
        これを取り込まないと単語と学習状態は戻るのに統計だけ空、という状態になる。

        追記のみ・不変のテーブルなので衝突しない。知らないidを入れるだけ。
        """
        since = self._store.get_sync_value(LAST_PULLED_AT)
        rows = self._remote.fetch_since("answer_log", "answered_at", since)
        return sum(1 for row in rows if self._store.apply_remote_answer(_normalize(row)))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize(row: dict) -> dict:
    """リモート行の時刻表記をローカルと同じ形に揃える。

    LWWは `updated_at` の**文字列比較**で判定する（ISO8601のUTCなら
    文字列のまま時系列順になるため）。Postgres側の表記が
    `...Z` や秒未満の桁数違いだと比較が壊れるので、ここで正規化する。
    """
    normalized = dict(row)
    for column in _TIMESTAMP_COLUMNS:
        value = normalized.get(column)
        if isinstance(value, str) and value:
            normalized[column] = _to_utc_iso(value)
    return normalized


def _to_utc_iso(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value   # 解釈できなければそのまま（比較で不利になるだけで壊れはしない）
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()
