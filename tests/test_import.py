"""単語一括インポートのテスト

偽のLLMClientを注入するため、ネットワークに触らない。
"""
import pytest

from src.db.store import Store
from src.llm import WordInfo
from src.tools.import_words import (
    Entry,
    ImportResult,
    format_summary,
    import_words,
    parse_entries,
)


class FakeLLM:
    """英単語 → WordInfo の対応表を持つ偽クライアント"""

    def __init__(self, table=None):
        self.table = table or {}
        self.calls: list[str] = []

    def lookup_word(self, english):
        self.calls.append(english)
        return self.table.get(english)


@pytest.fixture
def store(tmp_path):
    s = Store(tmp_path / "test.db")
    yield s
    s.close()


def _import(store, llm, words, **kwargs):
    """文字列でもEntryでも渡せるようにして、テスト側の記述を短く保つ"""
    entries = [w if isinstance(w, Entry) else Entry(w) for w in words]
    kwargs.setdefault("delay", 0)
    kwargs.setdefault("log", lambda _: None)
    return import_words(store, llm, entries, **kwargs)


# ── 行のパース ────────────────────────────────────────────────────────────

def _english(text):
    return [entry.english for entry in parse_entries(text)]


def test_1行1単語として読める():
    assert _english("yield\nresidue\ninterim") == ["yield", "residue", "interim"]


def test_前後の空白を除去する():
    """実データの末尾にスペースが入っていた"""
    assert _english("recession \n  yield") == ["recession", "yield"]


def test_空行とコメント行を無視する():
    assert _english("yield\n\n# メモ\n\nresidue") == ["yield", "residue"]


def test_熟語もそのまま1件として扱う():
    assert _english("be indicative of") == ["be indicative of"]


def test_ファイル内の重複を除く():
    assert _english("yield\nYield\nyield") == ["yield"]


def test_単語だけの行はLLM補完が必要と判定される():
    assert parse_entries("yield")[0].needs_lookup is True


# ── 和訳・品詞の直接指定 ──────────────────────────────────────────────────

def test_カンマ区切りで和訳と品詞を指定できる():
    entry = parse_entries("incorporation, 法人設立, 名詞")[0]

    assert entry == Entry("incorporation", "法人設立", "名詞")
    assert entry.needs_lookup is False


def test_品詞は省略できる():
    assert parse_entries("yield, 産出する")[0] == Entry("yield", "産出する", None)


def test_選択肢に無い品詞は弾く():
    """表記ゆれが入ると同じ品詞から誤答を選ぶ処理が効かなくなる"""
    with pytest.raises(ValueError, match="2行目"):
        parse_entries("yield, 産出する, 動詞\nresidue, 残留物, 他動詞")


def test_和訳が空なら単語行として扱う():
    assert parse_entries("yield,")[0].needs_lookup is True


# ── インポート ────────────────────────────────────────────────────────────

def test_和訳と品詞を補完して登録される(store):
    llm = FakeLLM({"postpone": WordInfo(japanese="延期する", part_of_speech="動詞")})

    result = _import(store, llm, ["postpone"])

    assert result.added == ["postpone"]
    word = store.list_words()[0]
    assert word.english == "postpone"
    assert word.japanese == "延期する"
    assert word.part_of_speech == "動詞"


def test_登録済みの単語はLLMを呼ばずにskipされる(store):
    """再実行しても二重登録されず、無駄なAPI呼び出しもしない"""
    store.add_word("postpone", "延期する")
    llm = FakeLLM({"postpone": WordInfo(japanese="別の和訳")})

    result = _import(store, llm, ["postpone"])

    assert result.skipped == ["postpone"]
    assert result.added == []
    assert llm.calls == []


def test_大文字小文字が違っても登録済みと判定する(store):
    store.add_word("postpone", "延期する")
    llm = FakeLLM({"Postpone": WordInfo(japanese="延期する")})

    assert _import(store, llm, ["Postpone"]).skipped == ["Postpone"]


def test_和訳を取得できなければ登録しない(store):
    """和訳が無い単語は出題も選択肢にも使えないので、DBに入れる価値がない"""
    llm = FakeLLM({})

    result = _import(store, llm, ["untranslatable"])

    assert result.failed == ["untranslatable"]
    assert store.count_words() == 0


def test_一部が失敗しても残りは登録される(store):
    llm = FakeLLM({
        "postpone": WordInfo(japanese="延期する"),
        "acquire": WordInfo(japanese="獲得する"),
    })

    result = _import(store, llm, ["postpone", "unknown", "acquire"])

    assert result.added == ["postpone", "acquire"]
    assert result.failed == ["unknown"]
    assert store.count_words() == 2


def test_dry_runでは登録されない(store):
    llm = FakeLLM({"postpone": WordInfo(japanese="延期する")})

    result = _import(store, llm, ["postpone"], dry_run=True)

    assert result.added == ["postpone"]
    assert store.count_words() == 0


def test_品詞が取得できなくても登録できる(store):
    llm = FakeLLM({"postpone": WordInfo(japanese="延期する", part_of_speech=None)})

    _import(store, llm, ["postpone"])

    assert store.list_words()[0].part_of_speech is None


def test_同じファイル内の重複は1回しか登録されない(store):
    llm = FakeLLM({"postpone": WordInfo(japanese="延期する")})

    _import(store, llm, parse_entries("postpone\npostpone"))

    assert store.count_words() == 1


# ── 集計表示 ──────────────────────────────────────────────────────────────

def test_失敗した単語が一覧で報告される():
    result = ImportResult(added=["a"], skipped=["b"], failed=["c", "d"])

    summary = format_summary(result, dry_run=False)

    assert "登録   1語" in summary
    assert "- c" in summary
    assert "- d" in summary


def test_失敗が無ければ一覧は出ない():
    summary = format_summary(ImportResult(added=["a"]), dry_run=False)

    assert "失敗した単語" not in summary


# ── 直接指定の登録 ────────────────────────────────────────────────────────

def test_和訳を指定した行はLLMを呼ばずに登録される(store):
    llm = FakeLLM({})

    result = _import(store, llm, [Entry("incorporation", "法人設立", "名詞")])

    assert result.added == ["incorporation"]
    assert llm.calls == []
    word = store.list_words()[0]
    assert word.japanese == "法人設立"
    assert word.part_of_speech == "名詞"


def test_指定行とLLM補完行を混ぜられる(store):
    llm = FakeLLM({"postpone": WordInfo(japanese="延期する", part_of_speech="動詞")})

    result = _import(store, llm, [Entry("barely", "かろうじて", "副詞"), "postpone"])

    assert result.added == ["barely", "postpone"]
    assert llm.calls == ["postpone"]
