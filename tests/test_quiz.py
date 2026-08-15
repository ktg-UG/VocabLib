"""出題データ組み立てのテスト

UIに依存しない層なので、メニューバーアプリを起動せずに検証できる。
"""
import pytest

from src.db.store import Store
from src.quiz import build_quiz


@pytest.fixture
def store(tmp_path):
    s = Store(tmp_path / "test.db")
    yield s
    s.close()


def _add_words(store, count):
    meanings = ["延期する", "見捨てる", "獲得する", "主張する", "拡大する", "評価する"]
    words = ["postpone", "abandon", "acquire", "assert", "expand", "evaluate"]
    for i in range(count):
        store.add_word(words[i], meanings[i])


def test_単語が無ければNoneを返す(store):
    assert build_quiz(store) is None


def test_選択肢に正解の和訳が含まれる(store):
    _add_words(store, 4)
    quiz = build_quiz(store)

    assert quiz.choices[quiz.correct_index] == quiz.word.japanese
    assert quiz.correct_meaning == quiz.word.japanese


def test_選択肢に重複がない(store):
    _add_words(store, 4)
    quiz = build_quiz(store)

    assert len(quiz.choices) == len(set(quiz.choices))


def test_単語が4語あれば選択肢は4つ(store):
    _add_words(store, 4)
    assert len(build_quiz(store).choices) == 4


def test_単語が2語しかなくても出題できる(store):
    """登録直後は単語が少ない。4択に満たなくてもエラーにせず2択で出す"""
    _add_words(store, 2)
    quiz = build_quiz(store)

    assert len(quiz.choices) == 2
    assert quiz.choices[quiz.correct_index] == quiz.word.japanese


def test_単語が1語だけなら選択肢も1つ(store):
    _add_words(store, 1)
    quiz = build_quiz(store)

    assert quiz.choices == [quiz.word.japanese]
    assert quiz.correct_index == 0


def test_同じ和訳の別単語が誤答候補に混ざらない(store):
    """「走る」が2つ並ぶと正解が2つある問題になってしまう"""
    store.add_word("run", "走る")
    store.add_word("dash", "走る")
    store.add_word("abandon", "見捨てる")

    for _ in range(20):
        quiz = build_quiz(store)
        assert quiz.choices.count(quiz.word.japanese) == 1


def test_正解の位置が固定されない(store):
    """毎回同じ位置に正解があると、内容を読まずに答えられてしまう"""
    _add_words(store, 4)
    indexes = {build_quiz(store).correct_index for _ in range(30)}

    assert len(indexes) > 1


def test_選択肢数を指定できる(store):
    _add_words(store, 6)
    assert len(build_quiz(store, choice_count=3).choices) == 3
