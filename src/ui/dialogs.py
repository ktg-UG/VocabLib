"""ダイアログ（単語登録・単語一覧・統計表示）"""
from __future__ import annotations

import threading
import traceback
from typing import Callable

import rumps
from PyObjCTools.AppHelper import callAfter

from ..db.store import DuplicateWordError, Store
from ..llm import LLMClient
from .add_word_panel import AddWordPanel

MAX_LISTED_WORDS = 40


def notify(subtitle: str, message: str = "") -> None:
    """通知を出す。

    `rumps.notification` は署名済みの .app にバンドルされていないと例外を投げる
    ことがあるため、失敗したら黙って諦める（通知は補助的な情報なので、
    出せないことでアプリを止める理由にはならない）。
    """
    try:
        rumps.notification(title="VocabLib", subtitle=subtitle, message=message)
    except Exception:
        pass


def prompt_add_word(
    store: Store,
    llm: LLMClient | None = None,
    on_close: Callable[[], None] | None = None,
) -> AddWordPanel | None:
    """単語を登録する。

    英単語だけ聞いたら、あとは確認フォーム1枚で完結する。
    和訳・品詞のオートフィルはワーカースレッドで走らせ、届いたら
    `callAfter` でフォームに流し込む。**待っている間もUIは固まらない。**

    Returns:
        開いた AddWordPanel。英単語の入力がキャンセルされたら None
    """
    english = _ask("追加する英単語を入力してください", title="単語を追加")
    if not english:
        if on_close is not None:
            on_close()
        return None

    def save(en: str, ja: str, pos: str | None) -> bool:
        """登録できたら True。False を返すとフォームは閉じずに残る"""
        try:
            store.add_word(en, ja, pos)
        except DuplicateWordError:
            rumps.alert(title="登録済み", message=f"「{en}（{ja}）」は既に登録されています。")
            return False
        except ValueError:
            rumps.alert(title="入力エラー", message="英単語と和訳はどちらも必須です。")
            return False
        notify("単語を追加しました", f"{en} — {ja}")
        return True

    panel = AddWordPanel(
        english,
        on_save=save,
        on_close=on_close if on_close is not None else (lambda: None),
    )
    panel.show()
    _autofill_async(panel, llm, english)
    return panel


def _autofill_async(panel: AddWordPanel, llm: LLMClient | None, english: str) -> None:
    """和訳・品詞をワーカースレッドで取得し、メインスレッドでフォームに反映する"""
    if llm is None:
        callAfter(panel.set_autofill, None)
        return

    def worker() -> None:
        try:
            info = llm.lookup_word(english)
        except Exception:
            traceback.print_exc()
            info = None
        callAfter(panel.set_autofill, info)

    threading.Thread(target=worker, daemon=True).start()


def _ask(message: str, title: str, default_text: str = "") -> str | None:
    """1行入力を求める。

    Returns:
        入力文字列（空文字もありうる）。キャンセルされたら None。
    """
    response = rumps.Window(
        message=message,
        title=title,
        default_text=default_text,
        ok="次へ",
        cancel="キャンセル",
        dimensions=(260, 24),
    ).run()

    if not response.clicked:
        return None
    return response.text.strip()


def show_words(store: Store) -> None:
    """登録済みの単語を一覧表示する"""
    words = store.list_words()
    if not words:
        rumps.alert(title="単語一覧", message="まだ単語が登録されていません。")
        return

    lines = [f"{w.english} — {w.japanese}" for w in words[:MAX_LISTED_WORDS]]
    if len(words) > MAX_LISTED_WORDS:
        lines.append(f"...ほか {len(words) - MAX_LISTED_WORDS} 語")

    rumps.alert(title=f"単語一覧（{len(words)}語）", message="\n".join(lines))


def show_stats(store: Store) -> None:
    """統計を表示する。数値はすべてDBから読む（メモリ上には持たない）"""
    overall = store.get_stats_overall()
    due = store.get_due_counts()
    weak = store.get_weak_words(limit=5)

    lines = [
        f"通算: {overall['total']}問中 {overall['correct']}問正解"
        f"（{overall['accuracy']:.1f}%）",
        f"連続学習: {store.get_streak()}日",
        f"登録単語: {store.count_words()}語",
        "",
        f"復習待ち: {due['overdue']}語（期限切れ）",
        f"今週の復習: {due['within_week']}語",
        f"未学習: {due['unlearned']}語",
    ]

    if weak:
        lines.append("")
        lines.append("苦手な単語:")
        for i, w in enumerate(weak, start=1):
            lines.append(
                f"  {i}. {w['english']}（{w['japanese']}）"
                f" 誤答{w['incorrect']}回 / {w['error_rate']:.0f}%"
            )

    rumps.alert(title="統計", message="\n".join(lines))
