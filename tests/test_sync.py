"""同期エンジンのテスト

偽の RemoteClient を注入するため、ネットワークに触らない。
衝突解決（LWW）は本番で試すのが難しい部類なので、ここで押さえておく。
"""
import pytest

from src.db.store import Store
from src.sync.engine import LAST_PULLED_AT, SyncEngine


class FakeRemote:
    """送られた行を溜め、返す行を仕込める偽リモート"""

    def __init__(self, tables=None, fail_on=None):
        self.pushed: dict[str, list[dict]] = {}
        self.tables: dict[str, list[dict]] = tables or {}
        self.fail_on = fail_on          # このテーブルへのupsertで例外を出す
        self.fetch_calls: list[tuple] = []

    def upsert(self, table, rows):
        if self.fail_on == table:
            raise RuntimeError("ネットワークエラー")
        self.pushed.setdefault(table, []).extend(rows)

    def fetch_since(self, table, column, since):
        self.fetch_calls.append((table, column, since))
        rows = self.tables.get(table, [])
        if since is None:
            return list(rows)
        return [r for r in rows if r[column] > since]


@pytest.fixture
def store(tmp_path):
    s = Store(tmp_path / "test.db")
    yield s
    s.close()


def _pushed_ids(remote, table, key="id"):
    return {r[key] for r in remote.pushed.get(table, [])}


# ── push ──────────────────────────────────────────────────────────────────

def test_未送信の単語が送信される(store):
    word_id = store.add_word("postpone", "延期する")
    remote = FakeRemote()

    result = SyncEngine(store, remote).sync()

    assert result.ok
    assert _pushed_ids(remote, "words") == {word_id}


def test_送信済みの単語は再送されない(store):
    store.add_word("postpone", "延期する")
    remote = FakeRemote()
    engine = SyncEngine(store, remote)

    engine.sync()
    remote.pushed.clear()
    engine.sync()

    assert remote.pushed.get("words", []) == []


def test_更新した単語は再送される(store):
    word_id = store.add_word("postpone", "延期する")
    remote = FakeRemote()
    engine = SyncEngine(store, remote)

    engine.sync()
    remote.pushed.clear()
    store.set_example_sentence(word_id, "He postponed it. — 彼は延期した。")
    engine.sync()

    assert _pushed_ids(remote, "words") == {word_id}


def test_未送信の回答ログだけが送信される(store):
    """answer_log の synced=0 がそのまま送信キューとして機能している"""
    word_id = store.add_word("postpone", "延期する")
    store.record_answer(word_id, is_correct=True)
    remote = FakeRemote()
    engine = SyncEngine(store, remote)

    engine.sync()
    assert len(remote.pushed["answer_log"]) == 1

    remote.pushed.clear()
    store.record_answer(word_id, is_correct=False)
    engine.sync()
    assert len(remote.pushed["answer_log"]) == 1   # 新しい1件だけ


def test_送信内容にローカル専用の列が含まれない(store):
    """synced_at / synced はSupabase側に存在しないので送ってはいけない"""
    store.add_word("postpone", "延期する")
    store.record_answer(store.list_words()[0].id, is_correct=True)
    remote = FakeRemote()

    SyncEngine(store, remote).sync()

    assert "synced_at" not in remote.pushed["words"][0]
    assert "synced" not in remote.pushed["answer_log"][0]


def test_真偽値として送られる(store):
    """Postgres側は boolean 型なので 0/1 ではなく True/False で送る"""
    word_id = store.add_word("postpone", "延期する")
    store.record_answer(word_id, is_correct=True)
    remote = FakeRemote()

    SyncEngine(store, remote).sync()

    assert remote.pushed["words"][0]["deleted"] is False
    assert remote.pushed["answer_log"][0]["is_correct"] is True


# ── pull と衝突解決（LWW） ────────────────────────────────────────────────

def test_リモートにしかない単語が取り込まれる(store):
    remote = FakeRemote({"words": [{
        "id": "remote-1", "english": "acquire", "japanese": "獲得する",
        "part_of_speech": "動詞", "example_sentence": None,
        "created_at": "2026-08-15T00:00:00+00:00",
        "updated_at": "2026-08-15T00:00:00+00:00",
        "deleted": False,
    }]})

    result = SyncEngine(store, remote).sync()

    assert result.pulled == 1
    assert store.get_word("remote-1").english == "acquire"


def test_リモートの方が新しければ上書きされる(store):
    word_id = store.add_word("postpone", "延期する")
    remote = FakeRemote({"words": [{
        "id": word_id, "english": "postpone", "japanese": "先延ばしにする",
        "part_of_speech": None, "example_sentence": None,
        "created_at": "2026-08-15T00:00:00+00:00",
        "updated_at": "2099-01-01T00:00:00+00:00",   # 未来 = リモートが新しい
        "deleted": False,
    }]})

    SyncEngine(store, remote).sync()

    assert store.get_word(word_id).japanese == "先延ばしにする"


def test_ローカルの方が新しければ上書きされない(store):
    """衝突解決の肝。手元の変更が古いリモート値で消されてはいけない"""
    word_id = store.add_word("postpone", "延期する")
    remote = FakeRemote({"words": [{
        "id": word_id, "english": "postpone", "japanese": "古い和訳",
        "part_of_speech": None, "example_sentence": None,
        "created_at": "2000-01-01T00:00:00+00:00",
        "updated_at": "2000-01-01T00:00:00+00:00",   # 過去 = ローカルが新しい
        "deleted": False,
    }]})

    SyncEngine(store, remote).sync()

    assert store.get_word(word_id).japanese == "延期する"


def test_取り込んだ行を次の同期で送り返さない(store):
    """pull → 変更扱い → push → 相手もpull、の無限ピンポンを防ぐ"""
    remote = FakeRemote({"words": [{
        "id": "remote-1", "english": "acquire", "japanese": "獲得する",
        "part_of_speech": None, "example_sentence": None,
        "created_at": "2026-08-15T00:00:00+00:00",
        "updated_at": "2026-08-15T00:00:00+00:00",
        "deleted": False,
    }]})
    engine = SyncEngine(store, remote)

    engine.sync()
    remote.pushed.clear()
    engine.sync()

    assert remote.pushed.get("words", []) == []


def test_削除された単語が取り込まれる(store):
    """論理削除は墓標を同期先に伝えるための仕組み"""
    word_id = store.add_word("postpone", "延期する")
    remote = FakeRemote({"words": [{
        "id": word_id, "english": "postpone", "japanese": "延期する",
        "part_of_speech": None, "example_sentence": None,
        "created_at": "2026-08-15T00:00:00+00:00",
        "updated_at": "2099-01-01T00:00:00+00:00",
        "deleted": True,
    }]})

    SyncEngine(store, remote).sync()

    assert store.get_word(word_id) is None
    assert store.count_words() == 0


def test_時刻表記が違っても比較できる(store):
    """Postgresが `Z` 表記で返してもLWWが誤判定しないこと"""
    word_id = store.add_word("postpone", "延期する")
    remote = FakeRemote({"words": [{
        "id": word_id, "english": "postpone", "japanese": "新しい和訳",
        "part_of_speech": None, "example_sentence": None,
        "created_at": "2026-08-15T00:00:00Z",
        "updated_at": "2099-01-01T00:00:00Z",
        "deleted": False,
    }]})

    SyncEngine(store, remote).sync()

    assert store.get_word(word_id).japanese == "新しい和訳"


def test_2回目のpullは前回以降だけを取りに行く(store):
    remote = FakeRemote()
    engine = SyncEngine(store, remote)

    engine.sync()
    assert remote.fetch_calls[0][2] is None      # 初回は全件

    remote.fetch_calls.clear()
    engine.sync()
    assert remote.fetch_calls[0][2] is not None  # 2回目は差分のみ


def test_リモートの回答ログが取り込まれる(store):
    """ローカルDBを失ったときに統計を復元するための経路"""
    word_id = store.add_word("postpone", "延期する")
    remote = FakeRemote({"answer_log": [{
        "id": "answer-1", "word_id": word_id, "is_correct": True,
        "answered_at": "2026-08-15T00:00:00+00:00", "source": "mac",
    }]})

    SyncEngine(store, remote).sync()

    assert store.get_stats_overall()["total"] == 1


def test_同じ回答ログを二重に取り込まない(store):
    word_id = store.add_word("postpone", "延期する")
    remote = FakeRemote({"answer_log": [{
        "id": "answer-1", "word_id": word_id, "is_correct": True,
        "answered_at": "2026-08-15T00:00:00+00:00", "source": "mac",
    }]})
    engine = SyncEngine(store, remote)

    engine.sync()
    remote.tables["answer_log"][0]["answered_at"] = "2099-01-01T00:00:00+00:00"
    engine.sync()

    assert store.get_stats_overall()["total"] == 1


def test_取り込んだ回答ログを送り返さない(store):
    word_id = store.add_word("postpone", "延期する")
    remote = FakeRemote({"answer_log": [{
        "id": "answer-1", "word_id": word_id, "is_correct": True,
        "answered_at": "2026-08-15T00:00:00+00:00", "source": "mac",
    }]})
    engine = SyncEngine(store, remote)

    engine.sync()
    remote.pushed.clear()
    engine.sync()

    assert remote.pushed.get("answer_log", []) == []


def test_ローカルDBを失っても復元できる(store, tmp_path):
    """このアプリの価値は学習データの蓄積なので、消えたら戻せる必要がある"""
    word_id = store.add_word("postpone", "延期する")
    store.record_answer(word_id, is_correct=True)
    store.record_answer(word_id, is_correct=False)

    remote = FakeRemote()
    SyncEngine(store, remote).sync()

    # 送信済みの内容をそのままリモートの中身として作り直す
    restored_remote = FakeRemote(dict(remote.pushed))
    restored = Store(tmp_path / "restored.db")
    try:
        SyncEngine(restored, restored_remote).sync()

        assert restored.count_words() == 1
        assert restored.get_word(word_id).japanese == "延期する"
        assert restored.get_stats_overall() == {
            "total": 2, "correct": 1, "incorrect": 1, "accuracy": 50.0,
        }
    finally:
        restored.close()


# ── 異常系 ────────────────────────────────────────────────────────────────

def test_通信に失敗しても例外を投げない(store):
    """同期の失敗でアプリが止まってはいけない"""
    store.add_word("postpone", "延期する")
    remote = FakeRemote(fail_on="words")

    result = SyncEngine(store, remote).sync()

    assert result.error is not None
    assert not result.ok


def test_送信に失敗した行は次回再送される(store):
    word_id = store.add_word("postpone", "延期する")
    failing = FakeRemote(fail_on="words")
    SyncEngine(store, failing).sync()

    healthy = FakeRemote()
    SyncEngine(store, healthy).sync()

    assert _pushed_ids(healthy, "words") == {word_id}


def test_pullに失敗したら前回時刻を進めない(store):
    class BrokenFetch(FakeRemote):
        def fetch_since(self, table, column, since):
            raise RuntimeError("取得失敗")

    result = SyncEngine(store, BrokenFetch()).sync()

    assert result.error is not None
    assert store.get_sync_value(LAST_PULLED_AT) is None


def test_同期は多重に実行されない(store):
    engine = SyncEngine(store, FakeRemote())
    engine._lock.acquire()   # 実行中の状態を作る
    try:
        result = engine.sync()
    finally:
        engine._lock.release()

    assert result.skipped
    assert not result.ok


# ── タグの同期 ────────────────────────────────────────────────────────────

def test_タグがpushされる(store):
    store.add_word("incorporation", "法人設立", "名詞", tag="TOEIC")
    remote = FakeRemote()

    SyncEngine(store, remote).sync()

    assert remote.pushed["words"][0]["tag"] == "TOEIC"


def test_タグがpullされる(store):
    remote = FakeRemote(tables={"words": [{
        "id": "w1", "english": "yield", "japanese": "産出する",
        "part_of_speech": "動詞", "tag": "TOEIC", "example_sentence": None,
        "created_at": "2026-08-16T00:00:00+00:00",
        "updated_at": "2026-08-16T00:00:00+00:00", "deleted": False,
    }]})

    SyncEngine(store, remote).sync()

    assert store.get_word("w1").tag == "TOEIC"


def test_リモート行にtagが無くても落ちない(store):
    """Supabaseに列を足す前に入った行が返ってくる場合"""
    remote = FakeRemote(tables={"words": [{
        "id": "w1", "english": "yield", "japanese": "産出する",
        "part_of_speech": "動詞", "example_sentence": None,
        "created_at": "2026-08-16T00:00:00+00:00",
        "updated_at": "2026-08-16T00:00:00+00:00", "deleted": False,
    }]})

    result = SyncEngine(store, remote).sync()

    assert result.ok
    assert store.get_word("w1").tag == ""
