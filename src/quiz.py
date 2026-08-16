"""出題データの組み立て

「次にどの単語を、どの選択肢で出すか」を決める層。

このモジュールは **UIに一切依存しない**（rumps も AppKit も import しない）。
そのおかげで出題ロジックを pytest で検証できる。
v1は出題ロジックがメニューバーアプリの中に埋まっており、確認するには
アプリを起動するしかなかった。
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from .db.store import Store, Word


@dataclass(frozen=True)
class Quiz:
    """4択クイズ1問ぶんのデータ"""

    word: Word
    choices: list[str]   # シャッフル済みの和訳
    correct_index: int   # choices の中の正解位置

    @property
    def correct_meaning(self) -> str:
        return self.choices[self.correct_index]


def build_quiz(
    store: Store, choice_count: int = 4, tag: str | None = None
) -> Quiz | None:
    """次に出題する単語を選び、選択肢を組み立てる。

    Args:
        store: データアクセス層
        choice_count: 選択肢の数（正解を含む）
        tag: 指定するとそのタグの単語だけを出題する

    Returns:
        Quiz。出題できる単語が1つも無ければ None
    """
    word = store.get_next_word(tag=tag)
    if word is None:
        return None

    # 同じ品詞の単語から誤答を選ぶ。品詞が混ざると消去法で正解できてしまい、
    # SM-2が「覚えた」と誤判定する。
    # 一方 tag では絞らない。絞ると選択肢の在庫が枯れて同じ4語が並び、
    # 綴りではなく位置で覚えてしまうため
    distractors = store.get_distractor_meanings(
        word.id,
        limit=choice_count - 1,
        part_of_speech=word.part_of_speech,
    )

    # 別の単語に正解と同じ和訳が登録されている場合、選択肢に正解が2つ並んでしまう。
    # （例: 「run=走る」と「dash=走る」）ここで取り除く。
    distractors = [d for d in distractors if d != word.japanese]

    choices = [word.japanese, *distractors]
    random.shuffle(choices)

    # 登録単語が少ないと choice_count に満たないが、2択でも出題は成立するので
    # エラーにはしない。
    return Quiz(
        word=word,
        choices=choices,
        correct_index=choices.index(word.japanese),
    )
