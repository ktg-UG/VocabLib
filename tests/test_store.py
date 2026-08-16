"""SQLiteデータアクセス層のテスト"""
import sqlite3

import pytest

from src.db.store import DuplicateWordError, Store


@pytest.fixture
def store(tmp_path):
    """テストごとに使い捨てのDBを作る（tmp_pathはpytestが用意する一時ディレクトリ）"""
    s = Store(tmp_path / "test.db")
    yield s
    s.close()


# ── 単語の追加 ────────────────────────────────────────────────────────────

def test_単語を追加して取得できる(store):
    word_id = store.add_word("postpone", "延期する", part_of_speech="動詞")
    word = store.get_word(word_id)

    assert word is not None
    assert word.english == "postpone"
    assert word.japanese == "延期する"
    assert word.part_of_speech == "動詞"


def test_単語追加時に学習記録も同時に作られる(store):
    """v1は初回回答まで学習記録の行が無く、例文保存が失敗するバグの原因だった"""
    word_id = store.add_word("postpone", "延期する")

    # 学習記録が無ければ record_answer は ValueError を投げる実装なので、
    # 例外なく通ること自体が「行が存在する」ことの確認になる
    store.record_answer(word_id, is_correct=True)
    assert store.get_stats_overall()["total"] == 1


def test_同じ単語を重複登録できない(store):
    store.add_word("postpone", "延期する")
    with pytest.raises(DuplicateWordError):
        store.add_word("postpone", "延期する")


def test_同じ英単語でも和訳が違えば登録できる(store):
    store.add_word("run", "走る")
    store.add_word("run", "経営する")
    assert store.count_words() == 2


def test_空文字は登録できない(store):
    with pytest.raises(ValueError):
        store.add_word("", "延期する")


def test_論理削除した単語は一覧に出ない(store):
    word_id = store.add_word("postpone", "延期する")
    store.soft_delete_word(word_id)

    assert store.count_words() == 0
    assert store.get_word(word_id) is None


def test_例文を保存できる(store):
    word_id = store.add_word("postpone", "延期する")
    store.set_example_sentence(word_id, "He postponed the meeting. — 彼は会議を延期した。")

    assert "postponed" in store.get_word(word_id).example_sentence


# ── タグ ──────────────────────────────────────────────────────────────────

def test_タグを付けて登録できる(store):
    word_id = store.add_word("incorporation", "法人設立", "名詞", tag="TOEIC")
    assert store.get_word(word_id).tag == "TOEIC"


def test_タグを省略するとタグなしになる(store):
    word_id = store.add_word("postpone", "延期する")
    assert store.get_word(word_id).tag == ""


def test_登録時にタグが正規化される(store):
    """UIから `#TOEIC` の形のまま渡ってきても保存前に整える"""
    word_id = store.add_word("postpone", "延期する", tag=" #TOEIC ")
    assert store.get_word(word_id).tag == "TOEIC"


def test_タグを後から付けられる(store):
    word_id = store.add_word("postpone", "延期する")
    store.set_word_tag(word_id, "TOEIC")

    assert store.get_word(word_id).tag == "TOEIC"


def test_タグを変えると未同期として拾われる(store):
    """updated_at を進め忘れると、Supabaseに反映されないローカル変更ができる"""
    word_id = store.add_word("postpone", "延期する")
    store.mark_words_synced([word_id])
    assert store.get_unsynced_words() == []

    store.set_word_tag(word_id, "TOEIC")

    assert [w["id"] for w in store.get_unsynced_words()] == [word_id]


def test_使われているタグを語数の多い順に返す(store):
    store.add_word("postpone", "延期する", tag="TOEIC")
    store.add_word("abandon", "見捨てる", tag="TOEIC")
    store.add_word("acquire", "獲得する", tag="ビジネス")

    assert store.list_tags() == [
        {"tag": "TOEIC", "count": 2},
        {"tag": "ビジネス", "count": 1},
    ]


def test_タグなしの単語は一覧に含めない(store):
    store.add_word("postpone", "延期する")
    store.add_word("abandon", "見捨てる", tag="TOEIC")

    assert store.list_tags() == [{"tag": "TOEIC", "count": 1}]


def test_削除した単語はタグ一覧に数えない(store):
    word_id = store.add_word("postpone", "延期する", tag="TOEIC")
    store.soft_delete_word(word_id)

    assert store.list_tags() == []


# ── マイグレーション ──────────────────────────────────────────────────────

def test_tag列の無い既存DBでも開ける(tmp_path):
    """schema.sql の CREATE TABLE IF NOT EXISTS は既存テーブルに効かないため、
    列の追加は _migrate() が担う。ここが無いと既存ユーザーだけ壊れる"""
    db = tmp_path / "old.db"

    # tag 列を持たない、Phase 7 以前のスキーマを手で作る
    conn = sqlite3.connect(db)
    conn.executescript(
        """CREATE TABLE words (
               id TEXT PRIMARY KEY, english TEXT NOT NULL, japanese TEXT NOT NULL,
               part_of_speech TEXT, example_sentence TEXT,
               created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
               deleted INTEGER NOT NULL DEFAULT 0, synced_at TEXT);
           INSERT INTO words (id, english, japanese, created_at, updated_at)
           VALUES ('w1', 'postpone', '延期する', '2026-01-01', '2026-01-01');"""
    )
    conn.commit()
    conn.close()

    s = Store(db)
    try:
        word = s.get_word("w1")
        assert word is not None
        assert word.tag == ""          # 既存行は「タグなし」になる
        s.set_word_tag("w1", "TOEIC")  # 書き込みもできる
        assert s.get_word("w1").tag == "TOEIC"
    finally:
        s.close()


def test_マイグレーションは何度実行しても安全(tmp_path):
    """起動のたびに走るのでべき等でなければならない"""
    db = tmp_path / "test.db"
    for _ in range(3):
        s = Store(db)
        s.close()

    s = Store(db)
    try:
        word_id = s.add_word("postpone", "延期する", tag="TOEIC")
        assert s.get_word(word_id).tag == "TOEIC"
    finally:
        s.close()


# ── 出題する単語の選択 ────────────────────────────────────────────────────

def test_単語が無ければNoneを返す(store):
    assert store.get_next_word() is None


def test_未学習の単語が出題される(store):
    store.add_word("postpone", "延期する")
    assert store.get_next_word().english == "postpone"


def test_期限切れの単語が未学習より優先される(store):
    """不正解にすると5分後が期限になるが、テスト時点では未来なので
    「期限切れ」ではなく「未学習の単語」が選ばれるべき"""
    answered = store.add_word("postpone", "延期する")
    store.record_answer(answered, is_correct=True)   # 1日後に設定される
    store.add_word("abandon", "見捨てる")             # 未学習

    assert store.get_next_word().english == "abandon"


def test_全て学習済みなら次回復習が最も近い単語が選ばれる(store):
    a = store.add_word("postpone", "延期する")
    b = store.add_word("abandon", "見捨てる")
    store.record_answer(a, is_correct=True)   # 1日後
    store.record_answer(b, is_correct=False)  # 5分後 ← こちらが近い

    assert store.get_next_word().english == "abandon"


def test_タグを指定するとその単語だけ出題される(store):
    store.add_word("postpone", "延期する", tag="TOEIC")
    store.add_word("apple", "りんご", tag="日常")

    assert store.get_next_word(tag="TOEIC").english == "postpone"


def test_タグ指定は完全一致(store):
    """1語1タグなので部分一致を考えなくてよい。TOEIC が TOEIC-Part5 を拾わない"""
    store.add_word("postpone", "延期する", tag="TOEIC-Part5")

    assert store.get_next_word(tag="TOEIC") is None


def test_該当するタグの単語が無ければNone(store):
    """勝手に絞り込みを解除して別の単語を出さない
    （設定が効いていないように見えるため）"""
    store.add_word("postpone", "延期する", tag="TOEIC")

    assert store.get_next_word(tag="ビジネス") is None


def test_タグを指定しなければ全単語から選ぶ(store):
    store.add_word("postpone", "延期する", tag="TOEIC")

    assert store.get_next_word() is not None


def test_誤答候補は同じ品詞を優先する(store):
    target = store.add_word("postpone", "延期する", part_of_speech="動詞")
    store.add_word("acquire", "獲得する", part_of_speech="動詞")
    store.add_word("assert", "主張する", part_of_speech="動詞")
    store.add_word("apple", "りんご", part_of_speech="名詞")

    meanings = store.get_distractor_meanings(target, limit=2, part_of_speech="動詞")

    assert set(meanings) <= {"獲得する", "主張する"}
    assert len(meanings) == 2


def test_同じ品詞が足りなければ他の品詞で補充する(store):
    target = store.add_word("postpone", "延期する", part_of_speech="動詞")
    store.add_word("acquire", "獲得する", part_of_speech="動詞")
    store.add_word("apple", "りんご", part_of_speech="名詞")
    store.add_word("residue", "残り", part_of_speech="名詞")

    meanings = store.get_distractor_meanings(target, limit=3, part_of_speech="動詞")

    assert len(meanings) == 3
    assert "獲得する" in meanings


def test_補充された誤答が重複しない(store):
    target = store.add_word("postpone", "延期する", part_of_speech="動詞")
    store.add_word("acquire", "獲得する", part_of_speech="動詞")
    store.add_word("apple", "りんご", part_of_speech="名詞")

    meanings = store.get_distractor_meanings(target, limit=3, part_of_speech="動詞")

    assert len(meanings) == len(set(meanings))


def test_品詞を指定しなければ従来どおり全体から選ぶ(store):
    target = store.add_word("postpone", "延期する", part_of_speech="動詞")
    store.add_word("apple", "りんご", part_of_speech="名詞")

    assert store.get_distractor_meanings(target, limit=3) == ["りんご"]


def test_誤答候補に正解の単語は含まれない(store):
    target = store.add_word("postpone", "延期する")
    store.add_word("abandon", "見捨てる")
    store.add_word("acquire", "獲得する")

    meanings = store.get_distractor_meanings(target, limit=3)
    assert "延期する" not in meanings
    assert len(meanings) == 2


# ── 回答の記録と統計 ──────────────────────────────────────────────────────

def test_回答を記録すると統計に反映される(store):
    word_id = store.add_word("postpone", "延期する")
    store.record_answer(word_id, is_correct=True)
    store.record_answer(word_id, is_correct=False)
    store.record_answer(word_id, is_correct=True)

    stats = store.get_stats_overall()
    assert stats["total"] == 3
    assert stats["correct"] == 2
    assert stats["incorrect"] == 1
    assert stats["accuracy"] == pytest.approx(66.67, abs=0.01)


def test_統計はDBを開き直しても消えない(tmp_path):
    """v1はメモリ上のdictだったため再起動で統計が消えていた"""
    db = tmp_path / "test.db"

    s1 = Store(db)
    word_id = s1.add_word("postpone", "延期する")
    s1.record_answer(word_id, is_correct=True)
    s1.close()

    s2 = Store(db)
    assert s2.get_stats_overall()["total"] == 1
    s2.close()


def test_存在しない単語には回答を記録できない(store):
    with pytest.raises(ValueError):
        store.record_answer("ghost-id", is_correct=True)


def test_苦手単語は誤答が多い順に並ぶ(store):
    weak = store.add_word("postpone", "延期する")
    ok = store.add_word("abandon", "見捨てる")

    for _ in range(3):
        store.record_answer(weak, is_correct=False)
    store.record_answer(ok, is_correct=False)
    store.record_answer(ok, is_correct=True)

    result = store.get_weak_words()
    assert result[0]["english"] == "postpone"
    assert result[0]["incorrect"] == 3
    assert result[0]["error_rate"] == 100.0


def test_全問正解の単語は苦手単語に出ない(store):
    word_id = store.add_word("postpone", "延期する")
    store.record_answer(word_id, is_correct=True)

    assert store.get_weak_words() == []


def test_連続学習日数は初日なら1(store):
    word_id = store.add_word("postpone", "延期する")
    store.record_answer(word_id, is_correct=True)

    assert store.get_streak() == 1


def test_回答がなければ連続学習日数は0(store):
    assert store.get_streak() == 0


def test_復習予定数を取得できる(store):
    a = store.add_word("postpone", "延期する")
    store.add_word("abandon", "見捨てる")     # 未学習
    store.record_answer(a, is_correct=True)   # 1日後 → 今週内

    counts = store.get_due_counts()
    assert counts["unlearned"] == 1
    assert counts["within_week"] == 1
    assert counts["overdue"] == 0
