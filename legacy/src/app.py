"""メインアプリケーション - Rumpsメニューバーアプリ"""
import threading
import rumps
from typing import Optional
from PyObjCTools.AppHelper import callAfter, callLater
from Foundation import NSNotificationCenter
from AppKit import (
    NSBackingStoreBuffered,
    NSButton,
    NSColor,
    NSFloatingWindowLevel,
    NSFont,
    NSMakeRect,
    NSPanel,
    NSScreen,
    NSTextField,
    NSWindowDidResignKeyNotification,
    NSWindowStyleMaskClosable,
    NSWindowStyleMaskTitled,
    NSWindowStyleMaskUtilityWindow,
)

from .config import QUIZ_INTERVAL_SECONDS, APP_ICON, AUTO_START_QUIZ
from .sheets_client import SheetsClient
from .ollama_client import OllamaClient


class VocabLibApp(rumps.App):
    """英単語暗記メニューバーアプリ"""
    
    def __init__(self):
        super(VocabLibApp, self).__init__(
            name="VocabLib",
            icon=None,  # アイコンファイルのパスを指定可能
            title=APP_ICON,
            quit_button="終了"
        )
        
        # クライアントの初期化
        self.sheets_client = SheetsClient()
        self.ollama_client = OllamaClient()
        
        # 状態管理
        self.quiz_running = False
        self.current_quiz: Optional[dict] = None
        self.stats = {
            'correct': 0,
            'incorrect': 0,
            'total': 0
        }
        
        # 統計メニュー項目への参照を保持
        self.stats_menu_item = rumps.MenuItem(self._get_stats_text(), callback=None)
        
        # メニュー項目の作成
        self.auto_quiz_menu_item = rumps.MenuItem(
            "自動クイズ: オフ",
            callback=self.toggle_auto_quiz,
        )
        self.menu = [
            rumps.MenuItem("今すぐクイズ", callback=self.show_quiz_now),
            rumps.separator,
            self.auto_quiz_menu_item,
            rumps.MenuItem("単語を再読み込み", callback=self.reload_words),
            rumps.separator,
            self.stats_menu_item,
            rumps.separator,
        ]
        
        # タイマー
        self.timer = None
        self.quiz_panel = None
        self.choice_buttons: list = []
        self._pending_record = None
        self._resign_observer = None

        if AUTO_START_QUIZ:
            self._start_auto_quiz(show_immediately=False, notify=False)
        
    def _get_stats_text(self) -> str:
        """統計テキストを取得"""
        total = self.stats['total']
        correct = self.stats['correct']
        if total == 0:
            return "統計: まだクイズに回答していません"
        accuracy = (correct / total) * 100
        return f"統計: {correct}/{total} 正解 ({accuracy:.1f}%)"
    
    def update_stats_menu(self):
        """統計メニューを更新"""
        self.stats_menu_item.title = self._get_stats_text()
    
    @rumps.clicked("今すぐクイズ")
    def show_quiz_now(self, _):
        """今すぐクイズを表示"""
        self._show_quiz()
    
    @rumps.clicked("単語を再読み込み")
    def reload_words(self, _):
        """単語を再読み込み"""
        rumps.notification(
            title="VocabLib",
            subtitle="単語を読み込み中...",
            message="しばらくお待ちください"
        )
        
        if self.sheets_client.fetch_words():
            count = len(self.sheets_client.words_cache)
            rumps.notification(
                title="VocabLib",
                subtitle="読み込み完了",
                message=f"{count}個の単語を読み込みました"
            )
        else:
            rumps.alert(
                title="エラー",
                message="単語の読み込みに失敗しました。\n設定を確認してください。"
            )
    
    def _update_quiz_timer(self, sender):
        """出題までの残り秒数をメニューに表示"""
        if not self.quiz_running:
            return
        self.remaining_seconds -= 1
        if self.remaining_seconds <= 0:
            self.auto_quiz_menu_item.title = "自動クイズ: 出題中"
            self.timer.stop()
            self._show_quiz()
        else:
            self.auto_quiz_menu_item.title = f"自動クイズ: {self.remaining_seconds}秒後に出題"

    def _start_auto_quiz(self, show_immediately: bool = True, notify: bool = True):
        """自動クイズを開始"""
        if self.quiz_running:
            return

        if not self.sheets_client.words_cache:
            if not self.sheets_client.fetch_words():
                rumps.alert(
                    title="エラー",
                    message="単語の読み込みに失敗しました。\n.envファイルとcredentials.jsonを確認してください。",
                )
                return

        self.quiz_running = True
        self.remaining_seconds = QUIZ_INTERVAL_SECONDS
        self.auto_quiz_menu_item.title = f"自動クイズ: {self.remaining_seconds}秒後に出題"
        self.timer = rumps.Timer(self._update_quiz_timer, 1)
        self.timer.start()

        if notify:
            rumps.notification(
                title="VocabLib",
                subtitle="自動クイズを開始しました",
                message=f"{QUIZ_INTERVAL_SECONDS // 60}分ごとに問題が表示されます",
            )

        if show_immediately:
            self._show_quiz()

    def _stop_auto_quiz(self, notify: bool = True):
        """自動クイズを停止"""
        if not self.quiz_running:
            return

        self.quiz_running = False
        if self.timer:
            self.timer.stop()
            self.timer = None
        self.auto_quiz_menu_item.title = "自動クイズ: オフ"

        if notify:
            rumps.notification(
                title="VocabLib",
                subtitle="自動クイズを停止しました",
                message="",
            )

    def toggle_auto_quiz(self, sender):
        """自動クイズのオン/オフを切り替え"""
        if self.quiz_running:
            self._stop_auto_quiz()
        else:
            self._start_auto_quiz(show_immediately=True, notify=True)
    
    def _show_quiz(self, _=None):
        """クイズを表示

        単語取得〜LLMによる選択肢生成は数秒かかるため、UIをブロックしないよう
        バックグラウンドスレッドで実行し、完成後に callAfter でメインスレッドに
        パネル表示を委譲する。
        """
        def _prepare():
            # 忘却曲線に基づいて単語を取得
            word_data = self.sheets_client.get_next_word()
            if not word_data:
                callAfter(self._alert_no_word)
                return

            correct_word, correct_meaning = word_data

            # 他の単語の意味を誤答候補として取得
            other_words = self.sheets_client.get_random_words(4, exclude=correct_word)
            other_meanings = [meaning for _, meaning in other_words]

            # まず LLM で誤答選択肢を生成。失敗/未起動時はローカル生成にフォールバック
            quiz = self.ollama_client.generate_quiz_with_ollama(
                correct_word, correct_meaning, other_meanings
            )
            if not quiz:
                quiz = self.ollama_client.generate_quiz(
                    correct_word, correct_meaning, other_words
                )
            if not quiz:
                return

            # correct_word / correct_meaning を quiz に明示保持（question 文面に依存しない）
            quiz['correct_word'] = correct_word
            quiz['correct_meaning'] = correct_meaning

            callAfter(self._present_quiz, quiz)

        threading.Thread(target=_prepare, daemon=True).start()

    def _alert_no_word(self):
        """単語取得失敗をメインスレッドで通知"""
        rumps.alert(title="エラー", message="単語が取得できませんでした")

    def _present_quiz(self, quiz: dict):
        """メインスレッドでクイズパネルを表示する"""
        self.current_quiz = quiz
        self._show_quiz_window(quiz)
    
    def _show_quiz_window(self, quiz: dict):
        """クイズウィンドウを表示"""
        self._show_quiz_panel(quiz)

    def _show_quiz_panel(self, quiz: dict):
        """右下にクイズパネルを表示"""
        question = quiz["question"]
        choices = quiz["choices"]

        self._cleanup_panel()

        width = 340
        height = 200
        screen = NSScreen.mainScreen().visibleFrame()
        x = screen.origin.x + screen.size.width - width - 16
        y = screen.origin.y + 16

        style = (
            NSWindowStyleMaskTitled
            | NSWindowStyleMaskClosable
            | NSWindowStyleMaskUtilityWindow
        )
        panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            ((x, y), (width, height)),
            style,
            NSBackingStoreBuffered,
            False,
        )
        panel.setTitle_("VocabLib")
        panel.setLevel_(NSFloatingWindowLevel)
        panel.setHidesOnDeactivate_(False)
        panel.setReleasedWhenClosed_(False)
        panel.setFloatingPanel_(True)

        content = panel.contentView()

        title_label = self._make_label(
            f"📚 {question}",
            NSMakeRect(12, height - 36, width - 24, 22),
            bold=True,
            size=13,
        )
        content.addSubview_(title_label)

        subtitle_label = self._make_label(
            "意味を選んでください:",
            NSMakeRect(12, height - 56, width - 24, 16),
            bold=False,
            size=11,
        )
        content.addSubview_(subtitle_label)

        button_top = height - 80
        button_height = 24
        self.choice_buttons = []
        for i, choice in enumerate(choices):
            button = NSButton.alloc().initWithFrame_(
                NSMakeRect(12, button_top - i * 28, width - 24, button_height)
            )
            button.setTitle_(f"{i + 1}. {choice}")
            button.setTarget_(self)
            button.setAction_("handle_quiz_choice:")
            button.setTag_(i)
            content.addSubview_(button)
            self.choice_buttons.append(button)

        self.example_label = None
        self.current_quiz = quiz
        self.quiz_panel = panel
        panel.makeKeyAndOrderFront_(None)

    def _make_label(self, text: str, frame, bold: bool, size: int, multiline: bool = False):
        """パネル用ラベルを作成

        multiline=True で複数行（改行を含むテキスト）を表示できるようにする。
        NSTextField はデフォルトで単一行モードのため、明示的に解除しないと
        改行以降（例文の和訳など）が切り捨てられる。
        """
        label = NSTextField.alloc().initWithFrame_(frame)
        label.setStringValue_(text)
        label.setBezeled_(False)
        label.setDrawsBackground_(False)
        label.setEditable_(False)
        label.setSelectable_(False)
        if multiline:
            label.setUsesSingleLineMode_(False)
            label.cell().setWraps_(True)
            label.setMaximumNumberOfLines_(0)
        if bold:
            label.setFont_(NSFont.boldSystemFontOfSize_(size))
        else:
            label.setFont_(NSFont.systemFontOfSize_(size))
        return label

    def handle_quiz_choice_(self, sender):
        """クイズの選択肢ボタンを処理"""
        if not self.current_quiz:
            return

        selected_index = sender.tag()
        quiz = self.current_quiz
        correct_index = quiz["correct_index"]

        if selected_index == -1:
            self._close_panel_and_save()
            return

        # ○×表示（色付き）
        is_correct = selected_index == correct_index
        for idx, btn in enumerate(self.choice_buttons):
            btn.setEnabled_(False)
            if idx == correct_index:
                btn.setTitle_(f"✅ {idx + 1}. {quiz['choices'][idx]}")
                btn.setContentTintColor_(NSColor.systemGreenColor())
            elif idx == selected_index:
                btn.setTitle_(f"❌ {idx + 1}. {quiz['choices'][idx]}")
                btn.setContentTintColor_(NSColor.systemRedColor())
            else:
                btn.setTitle_(f"  {idx + 1}. {quiz['choices'][idx]}")

        # 不正解時: パネルを下に拡張して例文を表示
        if not is_correct:
            self._expand_panel_with_example(quiz['correct_word'], quiz['correct_meaning'])

        self._check_answer(is_correct, quiz)
    
    def _expand_panel_with_example(self, word: str, meaning: str):
        """不正解時: パネルを上方向に80px拡張し、例文と閉じるボタンを追加"""
        panel = self.quiz_panel
        if not panel:
            return

        frame = panel.frame()
        expand = 80
        content = panel.contentView()
        width = int(frame.size.width)

        # 既存の全サブビューを拡張分だけ上にシフト（上方向に伸びるため）
        for subview in content.subviews():
            sf = subview.frame()
            subview.setFrame_(NSMakeRect(sf.origin.x, sf.origin.y + expand, sf.size.width, sf.size.height))

        # パネルを上方向に拡張（下端の位置は変えない）
        new_frame = NSMakeRect(
            frame.origin.x,
            frame.origin.y,
            frame.size.width,
            frame.size.height + expand,
        )
        panel.setFrame_display_animate_(new_frame, True, True)

        # 例文ラベルを拡張した下部エリアに追加
        self.example_label = self._make_label(
            "",
            NSMakeRect(16, 30, width - 32, 44),
            bold=False,
            size=13,
            multiline=True,
        )
        content.addSubview_(self.example_label)

        # 閉じるボタンを追加
        close_button = NSButton.alloc().initWithFrame_(
            NSMakeRect(width - 96, 8, 80, 24)
        )
        close_button.setTitle_("閉じる")
        close_button.setTarget_(self)
        close_button.setAction_("handle_quiz_choice:")
        close_button.setTag_(-1)
        content.addSubview_(close_button)

        # 例文を取得・表示
        def _format_example(text: str) -> str:
            """「英語 — 和訳」を2行に分割"""
            if " — " in text:
                en, ja = text.split(" — ", 1)
                return f"💡 {en}\n   {ja}"
            return f"💡 {text}"

        cached = self.sheets_client.get_example_sentence(word, meaning)
        if cached:
            self.example_label.setStringValue_(_format_example(cached))
        else:
            self.example_label.setStringValue_("💡 例文を生成中...")

            def _generate():
                sentence = self.ollama_client.generate_example_sentence(word, meaning)
                if not sentence:
                    sentence = OllamaClient.fallback_example_sentence(word, meaning)

                def _update_ui():
                    if self.quiz_panel and self.example_label:
                        self.example_label.setStringValue_(_format_example(sentence))
                    def _save():
                        self.sheets_client.save_example_sentence(word, meaning, sentence)
                    threading.Thread(target=_save, daemon=True).start()

                from PyObjCTools.AppHelper import callAfter
                callAfter(_update_ui)

            threading.Thread(target=_generate, daemon=True).start()

    def _cleanup_panel(self):
        """パネルと通知オブザーバーをクリーンアップ"""
        if self._resign_observer:
            NSNotificationCenter.defaultCenter().removeObserver_(self._resign_observer)
            self._resign_observer = None
        if self.quiz_panel:
            self.quiz_panel.close()
            self.quiz_panel = None

    def _close_panel_and_save(self):
        """パネルを閉じて学習記録をバックグラウンド保存する"""
        pending = self._pending_record
        self._pending_record = None

        self._cleanup_panel()
        self._restart_auto_quiz_timer()

        if pending:
            def save():
                self.sheets_client.record_answer(
                    pending['word'], pending['meaning'], pending['is_correct']
                )
            threading.Thread(target=save, daemon=True).start()

    def _on_panel_resign_key_(self, notification):
        """パネルがキーウィンドウでなくなった（フォーカスが外れた）時に呼ばれる"""
        if notification.object() == self.quiz_panel:
            self._close_panel_and_save()

    def _restart_auto_quiz_timer(self):
        """自動クイズタイマーを再開"""
        if self.quiz_running:
            self.remaining_seconds = QUIZ_INTERVAL_SECONDS
            self.auto_quiz_menu_item.title = f"自動クイズ: {self.remaining_seconds}秒後に出題"
            if self.timer:
                self.timer.start()

    def _check_answer(self, is_correct: bool, quiz: dict):
        """回答をチェック"""
        self.stats['total'] += 1

        if is_correct:
            self.stats['correct'] += 1
        else:
            self.stats['incorrect'] += 1

        # 学習記録をパネル閉じた後に保存するため一時保持
        self._pending_record = {
            'word': quiz['correct_word'],
            'meaning': quiz['correct_meaning'],
            'is_correct': is_correct,
        }

        if is_correct:
            # 正解: 1秒後に自動クローズ
            callLater(1.0, self._close_panel_and_save)
        else:
            # 不正解: フォーカスが外れたらクローズ
            self._resign_observer = NSNotificationCenter.defaultCenter()\
                .addObserverForName_object_queue_usingBlock_(
                    NSWindowDidResignKeyNotification,
                    self.quiz_panel,
                    None,
                    self._on_panel_resign_key_,
                )

        self.update_stats_menu()


def main():
    """メイン関数"""
    app = VocabLibApp()
    app.run()


if __name__ == "__main__":
    main()
