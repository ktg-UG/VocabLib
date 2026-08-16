"""メニューバーアプリ本体

タイマーで出題タイミングを管理し、`build_quiz` で作った問題を `QuizPanel` に渡す。
統計はここに保持せず、必要になるたび Store から読む。
（v1はメモリ上のdictで持っていたため、再起動すると統計が消えていた）
"""
from __future__ import annotations

import threading
import traceback
from datetime import datetime
from functools import partial

import rumps
from PyObjCTools.AppHelper import callAfter

from .. import config
from ..db.store import Store
from ..llm import LLMClient
from ..llm.parsing import fallback_example_sentence
from ..quiz import Quiz, build_quiz
from ..sync import SupabaseClient, SyncEngine, SyncResult, is_configured
from . import dialogs
from .panel import QuizPanel


class VocabLibApp(rumps.App):
    def __init__(self, store: Store, llm: LLMClient | None = None):
        super().__init__(name="VocabLib", title=config.APP_TITLE, quit_button="終了")
        self.store = store
        self.llm = llm if llm is not None else LLMClient()

        self.quiz_running = False
        self.remaining_seconds = config.QUIZ_INTERVAL_SECONDS
        self.panel: QuizPanel | None = None
        self.add_panel = None

        # コールバックは MenuItem に直接渡す。
        # v1は @rumps.clicked デコレータと併用していて同じメソッドが二重登録されていた。
        self.auto_item = rumps.MenuItem("自動出題: オフ", callback=self.toggle_auto_quiz)
        self.stats_item = rumps.MenuItem("統計: 読み込み中", callback=None)
        self.sync_item = rumps.MenuItem("同期: 未設定", callback=None)

        self.menu = [
            rumps.MenuItem("今すぐ出題", callback=self.quiz_now),
            rumps.separator,
            self.auto_item,
            rumps.separator,
            rumps.MenuItem("単語を追加...", callback=self.add_word),
            # 単語一覧はWeb側へ移すまでの繋ぎ（役割分担はSPEC 1.4を参照）
            rumps.MenuItem("単語一覧...", callback=self.list_words),
            rumps.separator,
            rumps.MenuItem("統計...", callback=self.show_stats),
            self.stats_item,
            rumps.separator,
            rumps.MenuItem("今すぐ同期", callback=self.sync_now),
            self.sync_item,
            rumps.separator,
        ]

        self.timer = rumps.Timer(self._tick, 1)
        self._refresh_stats_item()

        # 同期は設定が揃っているときだけ有効にする。
        # 未設定でもアプリはローカル完結で普通に動く（Gemini未設定時と同じ考え方）。
        self.sync_engine = self._build_sync_engine()
        self.sync_timer = None
        if self.sync_engine is not None:
            self.sync_item.title = "同期: 未実行"
            self.sync_timer = rumps.Timer(
                self._sync_tick, config.SYNC_INTERVAL_MINUTES * 60
            )
            self.sync_timer.start()
            self._sync_async()   # 起動直後に1回

        if config.AUTO_START_QUIZ:
            self._start_auto_quiz(notify=False)

    # ── メニュー操作 ──────────────────────────────────────────────────────

    def quiz_now(self, _) -> None:
        self._show_quiz()

    def add_word(self, _) -> None:
        if self.add_panel is not None:
            return   # 既に追加フォームを開いている
        self.add_panel = dialogs.prompt_add_word(
            self.store, self.llm, on_close=self._on_add_panel_closed
        )

    def _on_add_panel_closed(self) -> None:
        self.add_panel = None
        self._refresh_stats_item()

    def list_words(self, _) -> None:
        dialogs.show_words(self.store)

    def show_stats(self, _) -> None:
        dialogs.show_stats(self.store)

    def toggle_auto_quiz(self, _) -> None:
        if self.quiz_running:
            self._stop_auto_quiz()
        else:
            self._start_auto_quiz(notify=True)

    # ── タイマー ─────────────────────────────────────────────────────────

    def _start_auto_quiz(self, notify: bool = True) -> None:
        if self.quiz_running:
            return
        self.quiz_running = True
        self.remaining_seconds = config.QUIZ_INTERVAL_SECONDS
        self._update_auto_item()
        self.timer.start()
        if notify:
            dialogs.notify(
                "自動出題を開始しました",
                f"{config.QUIZ_INTERVAL_MINUTES}分ごとに出題します",
            )

    def _stop_auto_quiz(self, notify: bool = True) -> None:
        if not self.quiz_running:
            return
        self.quiz_running = False
        self.timer.stop()
        self.auto_item.title = "自動出題: オフ"
        if notify:
            dialogs.notify("自動出題を停止しました")

    def _tick(self, _) -> None:
        if not self.quiz_running:
            return
        self.remaining_seconds -= 1
        if self.remaining_seconds > 0:
            self._update_auto_item()
            return

        self.timer.stop()
        self.auto_item.title = "自動出題: 出題中"
        self._show_quiz()

    def _restart_timer(self) -> None:
        """出題後にタイマーを再開する。

        v1は出題処理が途中で失敗すると再開されず、自動出題が黙って止まっていた。
        v2では出題の成否にかかわらず必ずここを通す。
        """
        if not self.quiz_running:
            return
        self.remaining_seconds = config.QUIZ_INTERVAL_SECONDS
        self._update_auto_item()
        self.timer.start()

    def _update_auto_item(self) -> None:
        minutes, seconds = divmod(max(self.remaining_seconds, 0), 60)
        self.auto_item.title = f"自動出題: {minutes}分{seconds:02d}秒後"

    # ── 出題 ─────────────────────────────────────────────────────────────

    def _show_quiz(self) -> None:
        if self.panel is not None:
            return   # 既に出題中なら二重に出さない

        if self.add_panel is not None:
            # 単語追加フォームの上にクイズを重ねない。入力の邪魔になるうえ、
            # フォーカスの奪い合いで操作不能になりうる
            self._restart_timer()
            return

        try:
            quiz = build_quiz(self.store, choice_count=config.CHOICE_COUNT)
        except Exception as e:
            self._report_error("出題する単語の取得に失敗しました", e)
            self._restart_timer()
            return

        if quiz is None:
            dialogs.notify("単語がありません", "「単語を追加...」から登録してください")
            self._restart_timer()
            return

        try:
            panel = QuizPanel(
                quiz,
                on_answer=partial(self._on_answer, quiz),
                on_close=self._on_panel_closed,
            )
            panel.show()
            self.panel = panel
        except Exception as e:
            self.panel = None
            self._report_error("クイズの表示に失敗しました", e)
            self._restart_timer()

    def _on_answer(self, quiz: Quiz, is_correct: bool) -> None:
        try:
            self.store.record_answer(quiz.word.id, is_correct)
        except Exception as e:
            self._report_error("回答の記録に失敗しました", e)
        self._refresh_stats_item()

        # 不正解かつ例文が未キャッシュのときだけLLMを呼ぶ。
        # 出題のたびに呼ぶことはしない（レイテンシと無料枠の無駄なので）。
        if not is_correct and not quiz.word.example_sentence:
            self._generate_example_async(quiz)

    def _generate_example_async(self, quiz: Quiz) -> None:
        """例文をワーカースレッドで生成し、完了したらパネルに反映する。

        LLMは数秒かかるため、メインスレッドで呼ぶとメニューバー全体が固まる。
        UI更新は必ず callAfter でメインスレッドに戻す。
        """
        word = quiz.word
        panel = self.panel   # 生成中に別のクイズへ移っても、古いパネルを更新して無害に終わる

        def worker() -> None:
            try:
                sentence = self.llm.generate_example_sentence(word.english, word.japanese)
            except Exception:
                # LLM層は例外を投げない設計だが、保険として最終手段に落とす
                traceback.print_exc()
                sentence = fallback_example_sentence(word.english, word.japanese)

            try:
                self.store.set_example_sentence(word.id, sentence)
            except Exception:
                traceback.print_exc()

            if panel is not None:
                callAfter(panel.set_example, sentence)

        threading.Thread(target=worker, daemon=True).start()

    def _on_panel_closed(self) -> None:
        self.panel = None
        self._restart_timer()

    # ── 統計表示 ─────────────────────────────────────────────────────────

    def _refresh_stats_item(self) -> None:
        try:
            overall = self.store.get_stats_overall()
            streak = self.store.get_streak()
            due = self.store.get_due_counts()
        except Exception:
            self.stats_item.title = "統計: 取得できません"
            return

        if overall["total"] == 0:
            self.stats_item.title = "統計: まだ回答がありません"
            return

        self.stats_item.title = (
            f"{overall['correct']}/{overall['total']}正解"
            f"（{overall['accuracy']:.1f}%） 連続{streak}日"
            f" 復習待ち{due['overdue']}"
        )

    # ── 同期 ─────────────────────────────────────────────────────────────

    def sync_now(self, _) -> None:
        if self.sync_engine is None:
            rumps.alert(
                title="同期は未設定です",
                message="`.env` に SUPABASE_URL と SUPABASE_SERVICE_ROLE_KEY を"
                        "設定してからアプリを再起動してください。",
            )
            return
        self.sync_item.title = "同期: 実行中..."
        self._sync_async()

    def _sync_tick(self, _) -> None:
        self._sync_async()

    def _build_sync_engine(self) -> SyncEngine | None:
        if not is_configured():
            return None
        try:
            return SyncEngine(self.store, SupabaseClient())
        except Exception:
            # 設定はあるがクライアントを作れない（URLが不正など）。
            # 同期を諦めるだけで、アプリ自体は動かし続ける
            traceback.print_exc()
            return None

    def _sync_async(self) -> None:
        """同期をワーカースレッドで実行する。UIはこれを待たない"""
        engine = self.sync_engine
        if engine is None:
            return

        def worker() -> None:
            try:
                result = engine.sync()
            except Exception as e:
                # SyncEngine は例外を投げない設計だが、保険
                traceback.print_exc()
                result = SyncResult(error=str(e))
            callAfter(self._apply_sync_result, result)

        threading.Thread(target=worker, daemon=True).start()

    def _apply_sync_result(self, result: SyncResult) -> None:
        if result.skipped:
            return

        now = datetime.now().strftime("%H:%M")
        if result.error:
            # 同期の失敗でモーダルは出さない。ユーザーが頼んだ操作ではないため
            self.sync_item.title = f"同期: {now} 失敗"
        else:
            self.sync_item.title = (
                f"同期: {now} 完了（送信{result.pushed} 受信{result.pulled}）"
            )
            if result.pulled:
                self._refresh_stats_item()

    # ── エラー通知 ────────────────────────────────────────────────────────

    def _report_error(self, summary: str, error: Exception) -> None:
        """エラーを隠さずユーザーに見せ、詳細は標準エラーに出す"""
        traceback.print_exc()
        rumps.alert(title="VocabLib エラー", message=f"{summary}\n\n{type(error).__name__}: {error}")
