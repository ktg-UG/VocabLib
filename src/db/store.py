"""SQLite データアクセス層

VocabLib のローカルDB（source of truth）への全アクセスをこのクラスに集約する。
アプリはネットワークを待たずにここを読み書きし、Supabaseへの同期は別レイヤーが
バックグラウンドで行う。

スレッド安全性:
    UIスレッドと同期ワーカーから同時に呼ばれるため、接続1本を Lock で保護する。
    WALモードなので読み取りは書き込みにブロックされない。
"""
from __future__ import annotations

import sqlite3
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..srs.spaced_repetition import INITIAL_EASE_FACTOR, calculate_next_review
from ..tags import normalize_tag

SCHEMA_PATH = Path(__file__).parent / "schema.sql"

# 「1日」の区切りをJSTで判定するためのSQLite用オフセット。
# 時刻はUTCで保存しているため、日別集計では +9時間して日付を取り出す。
JST_SHIFT = "+9 hours"


class DuplicateWordError(Exception):
    """同じ (英単語, 和訳) が既に登録されている"""


@dataclass(frozen=True)
class Word:
    id: str
    english: str
    japanese: str
    part_of_speech: str | None = None
    example_sentence: str | None = None
    tag: str = ""          # 1単語1タグ。空文字はタグなし


# 品詞の正式な選択肢。自由入力だと表記ゆれ（動詞 / 他動詞 / 【動】…）が起き、
# 4択の誤答を同じ品詞から選ぶ処理（get_distractor_meanings）が効かなくなるため、
# UI のプルダウンも一括インポートもこの1箇所を参照する。
PARTS_OF_SPEECH = (
    "名詞",
    "動詞",
    "形容詞",
    "副詞",
    "前置詞",
    "接続詞",
    "代名詞",
    "間投詞",
    "熟語",
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    """DBに保存するUTCのISO8601文字列へ変換する。

    ISO8601かつUTC固定なら、文字列のまま比較しても時系列順になる。
    """
    return dt.astimezone(timezone.utc).isoformat()


class Store:
    """SQLiteへの全アクセスを提供する"""

    def __init__(self, db_path: str | Path):
        db_path = Path(db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)

        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        # 外部キー制約はSQLiteでは既定でオフ。接続ごとに有効化する必要がある
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._init_schema()

    def _init_schema(self) -> None:
        sql = SCHEMA_PATH.read_text(encoding="utf-8")
        with self._lock:
            self._conn.executescript(sql)
            self._migrate()

    def _migrate(self) -> None:
        """スキーマ変更を既存DBに適用する。

        `schema.sql` は `CREATE TABLE IF NOT EXISTS` なので、**既にテーブルがあるDBには
        何の効果もない**。列を足しただけでは手元のDBに生えず、新規インストールでしか
        動かない変更になる。列の追加は必ずここに書く。

        起動のたびに走るので、何度実行しても安全であること（列があれば何もしない）。
        呼び出し元が `self._lock` を保持している前提。
        """
        columns = {row["name"] for row in self._conn.execute("PRAGMA table_info(words)")}
        if "tag" not in columns:
            self._conn.execute(
                "ALTER TABLE words ADD COLUMN tag TEXT NOT NULL DEFAULT ''"
            )

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # ── 単語の管理 ───────────────────────────────────────────────────────

    def add_word(
        self,
        english: str,
        japanese: str,
        part_of_speech: str | None = None,
        example_sentence: str | None = None,
        tag: str = "",
    ) -> str:
        """単語を追加し、word_id を返す。

        learning_records の行も同じトランザクションで必ず作成する。
        （v1は初回回答時まで行が無く、例文の保存に失敗するバグの原因になっていた）
        """
        english = english.strip()
        japanese = japanese.strip()
        if not english or not japanese:
            raise ValueError("englishとjapaneseは必須です")
        tag = normalize_tag(tag)

        word_id = str(uuid.uuid4())
        now = _iso(_now())

        with self._lock:
            try:
                with self._conn:  # トランザクション（例外時は自動ロールバック）
                    self._conn.execute(
                        """INSERT INTO words
                           (id, english, japanese, part_of_speech, tag,
                            example_sentence, created_at, updated_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (word_id, english, japanese, part_of_speech, tag,
                         example_sentence, now, now),
                    )
                    self._conn.execute(
                        """INSERT INTO learning_records (word_id, ease_factor, updated_at)
                           VALUES (?, ?, ?)""",
                        (word_id, INITIAL_EASE_FACTOR, now),
                    )
            except sqlite3.IntegrityError as e:
                raise DuplicateWordError(f"既に登録されています: {english} ({japanese})") from e

        return word_id

    def get_word(self, word_id: str) -> Word | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM words WHERE id = ? AND deleted = 0", (word_id,)
            ).fetchone()
        return _to_word(row) if row else None

    def list_words(self) -> list[Word]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM words WHERE deleted = 0 ORDER BY created_at"
            ).fetchall()
        return [_to_word(r) for r in rows]

    def count_words(self) -> int:
        with self._lock:
            return self._conn.execute(
                "SELECT COUNT(*) FROM words WHERE deleted = 0"
            ).fetchone()[0]

    def soft_delete_word(self, word_id: str) -> None:
        """論理削除する（同期先にも削除を伝えるため物理削除はしない）"""
        now = _iso(_now())
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE words SET deleted = 1, updated_at = ? WHERE id = ?",
                (now, word_id),
            )

    def set_word_tag(self, word_id: str, tag: str) -> None:
        """タグを付け替える。

        他の更新系と同じく `updated_at` を進める。これで
        `synced_at IS NULL OR updated_at > synced_at` に引っかかり、次の同期でpushされる。
        （SQLiteを直接UPDATEするとここを書き忘れ、Supabaseに反映されない
        ローカル変更ができてしまう）
        """
        now = _iso(_now())
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE words SET tag = ?, updated_at = ? WHERE id = ?",
                (normalize_tag(tag), now, word_id),
            )

    def list_tags(self) -> list[dict]:
        """使われているタグと語数を、多い順に返す。タグなしは含めない"""
        with self._lock:
            rows = self._conn.execute(
                """SELECT tag, COUNT(*) AS count FROM words
                   WHERE deleted = 0 AND tag != ''
                   GROUP BY tag ORDER BY count DESC, tag"""
            ).fetchall()
        return [{"tag": r["tag"], "count": r["count"]} for r in rows]

    def set_example_sentence(self, word_id: str, sentence: str) -> None:
        """AI生成した例文をキャッシュする"""
        now = _iso(_now())
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE words SET example_sentence = ?, updated_at = ? WHERE id = ?",
                (sentence, now, word_id),
            )

    # ── 出題する単語の選択 ────────────────────────────────────────────────

    def get_next_word(self, tag: str | None = None) -> Word | None:
        """忘却曲線に基づいて次に出題する単語を選ぶ。

        優先順位:
            1. 復習期限を過ぎた単語（最も長く放置しているものから）
            2. 未学習の単語（ランダム）
            3. 期限前だが最も近く出題予定の単語

        Args:
            tag: 指定するとそのタグの単語だけから選ぶ。該当が無ければ None を返す
                 （**勝手に絞り込みを解除しない**。別の単語を出すと設定が
                 効いていないように見えるため）
        """
        now = _iso(_now())
        base = """SELECT w.* FROM words w
                  JOIN learning_records lr ON lr.word_id = w.id
                  WHERE w.deleted = 0 """
        # 1単語1タグなので完全一致でよい（カンマ区切りの部分一致を考えなくて済む）
        tag_filter = "AND w.tag = ? " if tag else ""
        tag_params: tuple = (tag,) if tag else ()
        base += tag_filter

        queries = [
            # 1. 期限切れ: next_review が古い順
            (base + "AND lr.next_review IS NOT NULL AND lr.next_review <= ? "
                    "ORDER BY lr.next_review LIMIT 1", tag_params + (now,)),
            # 2. 未学習: ランダム
            (base + "AND lr.next_review IS NULL ORDER BY RANDOM() LIMIT 1", tag_params),
            # 3. 期限前: next_review が近い順
            (base + "AND lr.next_review > ? ORDER BY lr.next_review LIMIT 1",
             tag_params + (now,)),
        ]

        with self._lock:
            for sql, params in queries:
                row = self._conn.execute(sql, params).fetchone()
                if row:
                    return _to_word(row)
        return None

    def get_distractor_meanings(
        self,
        exclude_word_id: str,
        limit: int = 3,
        part_of_speech: str | None = None,
    ) -> list[str]:
        """4択の誤答候補として、他の単語の和訳を取得する。

        `part_of_speech` を指定すると同じ品詞の単語を優先して集める。
        品詞が混ざると「動詞の問題に名詞の選択肢」となり、意味を知らなくても
        消去法で正解できてしまうため。

        同じ品詞だけで足りなければ品詞を問わず補充する
        （選択肢が減って出題できないより、少し易しい方がマシ）。
        """
        with self._lock:
            meanings: list[str] = []

            if part_of_speech:
                rows = self._conn.execute(
                    """SELECT DISTINCT japanese FROM words
                       WHERE deleted = 0 AND id != ? AND part_of_speech = ?
                       ORDER BY RANDOM() LIMIT ?""",
                    (exclude_word_id, part_of_speech, limit),
                ).fetchall()
                meanings = [r["japanese"] for r in rows]

            if len(meanings) < limit:
                exclusion = ""
                params: list = [exclude_word_id]
                if meanings:
                    exclusion = f"AND japanese NOT IN ({','.join('?' * len(meanings))})"
                    params.extend(meanings)
                params.append(limit - len(meanings))

                rows = self._conn.execute(
                    f"""SELECT DISTINCT japanese FROM words
                        WHERE deleted = 0 AND id != ? {exclusion}
                        ORDER BY RANDOM() LIMIT ?""",
                    params,
                ).fetchall()
                meanings.extend(r["japanese"] for r in rows)

        return meanings

    # ── 回答の記録 ───────────────────────────────────────────────────────

    def record_answer(self, word_id: str, is_correct: bool, source: str = "mac") -> None:
        """回答を記録し、SM-2で次回復習日時を更新する。

        answer_log への追記と learning_records の更新を1トランザクションで行うため、
        「履歴はあるのに状態が古い」という不整合が起きない。
        """
        now_dt = _now()
        now = _iso(now_dt)

        with self._lock, self._conn:
            record = self._conn.execute(
                "SELECT * FROM learning_records WHERE word_id = ?", (word_id,)
            ).fetchone()
            if record is None:
                raise ValueError(f"単語が存在しません: {word_id}")

            result = calculate_next_review(
                is_correct=is_correct,
                repetitions=record["repetitions"],
                ease_factor=record["ease_factor"],
                interval_days=record["interval_days"],
                now=now_dt,
            )

            # ① 回答イベントを追記（synced=0 のまま = 送信待ち）
            self._conn.execute(
                """INSERT INTO answer_log (id, word_id, is_correct, answered_at, source)
                   VALUES (?, ?, ?, ?, ?)""",
                (str(uuid.uuid4()), word_id, int(is_correct), now, source),
            )

            # ② SM-2の状態を更新
            self._conn.execute(
                """UPDATE learning_records SET
                       last_reviewed = ?, next_review = ?, ease_factor = ?,
                       interval_days = ?, repetitions = ?,
                       total_correct = total_correct + ?,
                       total_seen = total_seen + 1,
                       updated_at = ?
                   WHERE word_id = ?""",
                (now, _iso(result.next_review), result.ease_factor,
                 result.interval_days, result.repetitions,
                 int(is_correct), now, word_id),
            )

    # ── 統計 ─────────────────────────────────────────────────────────────

    def get_stats_overall(self) -> dict:
        """通算の正解数・回答数・正答率（再起動しても消えない）"""
        with self._lock:
            row = self._conn.execute(
                """SELECT COUNT(*) AS total,
                          COALESCE(SUM(is_correct), 0) AS correct
                   FROM answer_log"""
            ).fetchone()
        total, correct = row["total"], row["correct"]
        return {
            "total": total,
            "correct": correct,
            "incorrect": total - correct,
            "accuracy": (correct / total * 100) if total else 0.0,
        }

    def get_stats_daily(self, days: int = 30) -> list[dict]:
        """日別（JST）の回答数と正答率。新しい日が末尾になる順で返す"""
        since = _iso(_now() - timedelta(days=days))
        with self._lock:
            rows = self._conn.execute(
                f"""SELECT date(answered_at, '{JST_SHIFT}') AS day,
                           COUNT(*) AS total,
                           COALESCE(SUM(is_correct), 0) AS correct
                    FROM answer_log
                    WHERE answered_at >= ?
                    GROUP BY day ORDER BY day""",
                (since,),
            ).fetchall()
        return [
            {
                "date": r["day"],
                "total": r["total"],
                "correct": r["correct"],
                "accuracy": (r["correct"] / r["total"] * 100) if r["total"] else 0.0,
            }
            for r in rows
        ]

    def get_streak(self) -> int:
        """連続学習日数（JST基準）。今日まだ未回答でも、昨日まで続いていれば継続扱い"""
        with self._lock:
            rows = self._conn.execute(
                f"""SELECT DISTINCT date(answered_at, '{JST_SHIFT}') AS day
                    FROM answer_log ORDER BY day DESC"""
            ).fetchall()
        if not rows:
            return 0

        studied = [datetime.strptime(r["day"], "%Y-%m-%d").date() for r in rows]
        today = (_now() + timedelta(hours=9)).date()

        # 直近の学習日が今日でも昨日でもなければ、連続は途切れている
        if (today - studied[0]).days > 1:
            return 0

        streak = 1
        for prev, cur in zip(studied, studied[1:]):
            if (prev - cur).days == 1:
                streak += 1
            else:
                break
        return streak

    def get_weak_words(self, limit: int = 10) -> list[dict]:
        """苦手な単語（誤答が多い順）"""
        with self._lock:
            rows = self._conn.execute(
                """SELECT w.id, w.english, w.japanese,
                          COUNT(*) AS total,
                          COUNT(*) - COALESCE(SUM(a.is_correct), 0) AS incorrect
                   FROM answer_log a
                   JOIN words w ON w.id = a.word_id
                   WHERE w.deleted = 0
                   GROUP BY w.id
                   HAVING incorrect > 0
                   ORDER BY incorrect DESC, total DESC
                   LIMIT ?""",
                (limit,),
            ).fetchall()
        return [
            {
                "word_id": r["id"],
                "english": r["english"],
                "japanese": r["japanese"],
                "total": r["total"],
                "incorrect": r["incorrect"],
                "error_rate": r["incorrect"] / r["total"] * 100,
            }
            for r in rows
        ]

    def get_due_counts(self) -> dict:
        """復習予定数（期限切れ / 今日中 / 今週 / 未学習）"""
        now_dt = _now()
        now = _iso(now_dt)
        end_of_week = _iso(now_dt + timedelta(days=7))

        with self._lock:
            row = self._conn.execute(
                """SELECT
                     SUM(CASE WHEN lr.next_review IS NOT NULL
                               AND lr.next_review <= ? THEN 1 ELSE 0 END) AS overdue,
                     SUM(CASE WHEN lr.next_review IS NOT NULL
                               AND lr.next_review <= ? THEN 1 ELSE 0 END) AS within_week,
                     SUM(CASE WHEN lr.next_review IS NULL THEN 1 ELSE 0 END) AS unlearned
                   FROM learning_records lr
                   JOIN words w ON w.id = lr.word_id
                   WHERE w.deleted = 0""",
                (now, end_of_week),
            ).fetchone()

        return {
            "overdue": row["overdue"] or 0,
            "within_week": row["within_week"] or 0,
            "unlearned": row["unlearned"] or 0,
        }

    # ── 同期（Phase 4） ───────────────────────────────────────────────────
    #
    # synced_at / synced はローカル専用の列で、Supabaseには存在しない。
    # push対象の抽出はこの列だけで完結するため、別途アウトボックステーブルを
    # 持つ必要がない。

    def get_unsynced_words(self) -> list[dict]:
        """まだ送っていない（または送信後に更新された）単語"""
        with self._lock:
            rows = self._conn.execute(
                """SELECT id, english, japanese, part_of_speech, tag, example_sentence,
                          created_at, updated_at, deleted
                   FROM words
                   WHERE synced_at IS NULL OR updated_at > synced_at"""
            ).fetchall()
        return [{**dict(r), "deleted": bool(r["deleted"])} for r in rows]

    def get_unsynced_records(self) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                """SELECT word_id, last_reviewed, next_review, ease_factor,
                          interval_days, repetitions, total_correct, total_seen,
                          updated_at
                   FROM learning_records
                   WHERE synced_at IS NULL OR updated_at > synced_at"""
            ).fetchall()
        return [dict(r) for r in rows]

    def get_unsynced_answers(self) -> list[dict]:
        """未送信の回答ログ。`synced = 0` がそのまま送信キューになっている"""
        with self._lock:
            rows = self._conn.execute(
                """SELECT id, word_id, is_correct, answered_at, source
                   FROM answer_log WHERE synced = 0"""
            ).fetchall()
        return [{**dict(r), "is_correct": bool(r["is_correct"])} for r in rows]

    def mark_words_synced(self, word_ids: list[str]) -> None:
        self._mark_synced("words", "id", word_ids)

    def mark_records_synced(self, word_ids: list[str]) -> None:
        self._mark_synced("learning_records", "word_id", word_ids)

    def mark_answers_synced(self, answer_ids: list[str]) -> None:
        if not answer_ids:
            return
        placeholders = ",".join("?" * len(answer_ids))
        with self._lock, self._conn:
            self._conn.execute(
                f"UPDATE answer_log SET synced = 1 WHERE id IN ({placeholders})",
                answer_ids,
            )

    def _mark_synced(self, table: str, id_column: str, ids: list[str]) -> None:
        if not ids:
            return
        now = _iso(_now())
        placeholders = ",".join("?" * len(ids))
        with self._lock, self._conn:
            self._conn.execute(
                f"UPDATE {table} SET synced_at = ? WHERE {id_column} IN ({placeholders})",
                [now, *ids],
            )

    def apply_remote_word(self, row: dict) -> bool:
        """リモートの単語を取り込む（LWW）。採用したら True。

        比較と更新をSQL 1文で行うため、「読んでから書くまでの間に
        別スレッドが書き換える」競合が起きない。
        """
        now = _iso(_now())
        try:
            with self._lock, self._conn:
                cur = self._conn.execute(
                    """INSERT INTO words
                       (id, english, japanese, part_of_speech, tag, example_sentence,
                        created_at, updated_at, deleted, synced_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(id) DO UPDATE SET
                           english          = excluded.english,
                           japanese         = excluded.japanese,
                           part_of_speech   = excluded.part_of_speech,
                           tag              = excluded.tag,
                           example_sentence = excluded.example_sentence,
                           updated_at       = excluded.updated_at,
                           deleted          = excluded.deleted,
                           synced_at        = excluded.synced_at
                       WHERE excluded.updated_at > words.updated_at""",
                    (
                        row["id"], row["english"], row["japanese"],
                        row.get("part_of_speech"),
                        # 列を足す前に入った行には tag が無い
                        row.get("tag") or "",
                        row.get("example_sentence"),
                        row["created_at"], row["updated_at"],
                        int(bool(row.get("deleted"))), now,
                    ),
                )
        except sqlite3.IntegrityError:
            # 同じ (english, japanese) が別idで既に存在する等。取り込めないので飛ばす
            return False
        return cur.rowcount > 0

    def apply_remote_record(self, row: dict) -> bool:
        """リモートの学習記録を取り込む（LWW）。採用したら True"""
        now = _iso(_now())
        try:
            with self._lock, self._conn:
                cur = self._conn.execute(
                    """INSERT INTO learning_records
                       (word_id, last_reviewed, next_review, ease_factor,
                        interval_days, repetitions, total_correct, total_seen,
                        updated_at, synced_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(word_id) DO UPDATE SET
                           last_reviewed = excluded.last_reviewed,
                           next_review   = excluded.next_review,
                           ease_factor   = excluded.ease_factor,
                           interval_days = excluded.interval_days,
                           repetitions   = excluded.repetitions,
                           total_correct = excluded.total_correct,
                           total_seen    = excluded.total_seen,
                           updated_at    = excluded.updated_at,
                           synced_at     = excluded.synced_at
                       WHERE excluded.updated_at > learning_records.updated_at""",
                    (
                        row["word_id"], row.get("last_reviewed"), row.get("next_review"),
                        row.get("ease_factor", INITIAL_EASE_FACTOR),
                        row.get("interval_days", 0), row.get("repetitions", 0),
                        row.get("total_correct", 0), row.get("total_seen", 0),
                        row["updated_at"], now,
                    ),
                )
        except sqlite3.IntegrityError:
            # 対応する words の行がまだ無い（外部キー違反）。次回の同期で拾う
            return False
        return cur.rowcount > 0

    def apply_remote_answer(self, row: dict) -> bool:
        """リモートの回答ログを取り込む。新規に入ったら True。

        `answer_log` は追記のみ・不変なのでLWW判定が要らない。
        「知らないidなら入れる」だけで済む。

        `synced = 1` で入れるので、取り込んだ行を送り返すことはない。
        """
        try:
            with self._lock, self._conn:
                cur = self._conn.execute(
                    """INSERT OR IGNORE INTO answer_log
                       (id, word_id, is_correct, answered_at, source, synced)
                       VALUES (?, ?, ?, ?, ?, 1)""",
                    (
                        row["id"], row["word_id"], int(bool(row["is_correct"])),
                        row["answered_at"], row.get("source") or "mac",
                    ),
                )
        except sqlite3.IntegrityError:
            # 対応する words の行がまだ無い（外部キー違反）。次回の同期で拾う
            return False
        return cur.rowcount > 0

    def get_sync_value(self, key: str) -> str | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT value FROM sync_state WHERE key = ?", (key,)
            ).fetchone()
        return row["value"] if row else None

    def set_sync_value(self, key: str, value: str) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO sync_state (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )


def _to_word(row: sqlite3.Row) -> Word:
    return Word(
        id=row["id"],
        english=row["english"],
        japanese=row["japanese"],
        part_of_speech=row["part_of_speech"],
        example_sentence=row["example_sentence"],
        tag=row["tag"] or "",
    )
