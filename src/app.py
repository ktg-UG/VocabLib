"""メインアプリケーション - Rumpsメニューバーアプリ"""
import rumps
import threading
from typing import Optional
from AppKit import (
    NSAlert,
    NSAlertStyleInformational,
    NSAlertFirstButtonReturn,
    NSBackingStoreBuffered,
    NSButton,
    NSFloatingWindowLevel,
    NSFont,
    NSPanel,
    NSScreen,
    NSTextField,
    NSWindowStyleMaskClosable,
    NSWindowStyleMaskTitled,
    NSWindowStyleMaskUtilityWindow,
    NSMakeRect,
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
        self.auto_quiz_menu_item.title = "自動クイズ: オン"

        self.timer = rumps.Timer(self._show_quiz, QUIZ_INTERVAL_SECONDS)
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
        """クイズを表示"""
        # ランダムに単語を取得
        word_data = self.sheets_client.get_random_word()
        if not word_data:
            rumps.alert(
                title="エラー",
                message="単語が取得できませんでした"
            )
            return
        
        correct_word, correct_meaning = word_data
        
        # 他の選択肢を取得
        other_words = self.sheets_client.get_random_words(4)
        
        # クイズを生成
        quiz = self.ollama_client.generate_quiz(
            correct_word,
            correct_meaning,
            other_words
        )
        
        if not quiz:
            return
        
        self.current_quiz = quiz
        
        # クイズウィンドウを表示
        self._show_quiz_window(quiz)
    
    def _show_quiz_window(self, quiz: dict):
        """クイズウィンドウを表示"""
        self._show_quiz_panel(quiz)

    def _show_quiz_panel(self, quiz: dict):
        """右下にクイズパネルを表示"""
        question = quiz["question"]
        choices = quiz["choices"]
        correct_index = quiz["correct_index"]

        if self.quiz_panel:
            self.quiz_panel.close()
            self.quiz_panel = None

        width = 360
        height = 240
        screen = NSScreen.mainScreen().visibleFrame()
        x = screen.origin.x + screen.size.width - width - 20
        y = screen.origin.y + 20

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
            NSMakeRect(16, height - 44, width - 32, 24),
            bold=True,
            size=13,
        )
        content.addSubview_(title_label)

        subtitle_label = self._make_label(
            "意味を選んでください:",
            NSMakeRect(16, height - 68, width - 32, 18),
            bold=False,
            size=11,
        )
        content.addSubview_(subtitle_label)

        button_top = height - 104
        button_height = 24
        for i, choice in enumerate(choices):
            button = NSButton.alloc().initWithFrame_(
                NSMakeRect(16, button_top - i * 28, width - 32, button_height)
            )
            button.setTitle_(f"{i + 1}. {choice}")
            button.setTarget_(self)
            button.setAction_("handle_quiz_choice:")
            button.setTag_(i)
            content.addSubview_(button)

        skip_button = NSButton.alloc().initWithFrame_(NSMakeRect(16, 12, 80, 24))
        skip_button.setTitle_("スキップ")
        skip_button.setTarget_(self)
        skip_button.setAction_("handle_quiz_choice:")
        skip_button.setTag_(-1)
        content.addSubview_(skip_button)

        self.current_quiz = quiz
        self.quiz_panel = panel
        panel.makeKeyAndOrderFront_(None)

    def _make_label(self, text: str, frame, bold: bool, size: int):
        """パネル用ラベルを作成"""
        label = NSTextField.alloc().initWithFrame_(frame)
        label.setStringValue_(text)
        label.setBezeled_(False)
        label.setDrawsBackground_(False)
        label.setEditable_(False)
        label.setSelectable_(False)
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

        if self.quiz_panel:
            self.quiz_panel.close()
            self.quiz_panel = None

        if selected_index == -1:
            return

        self._check_answer(selected_index, correct_index, quiz)
    
    def _check_answer(self, user_choice: int, correct_index: int, quiz: dict):
        """回答をチェック"""
        self.stats['total'] += 1
        
        if user_choice == correct_index:
            # 正解
            self.stats['correct'] += 1
            rumps.alert(
                title="✅ 正解！",
                message=f"{quiz['question']}\n\n正解: {quiz['correct_answer']}"
            )
        else:
            # 不正解
            self.stats['incorrect'] += 1
            user_answer = quiz['choices'][user_choice]
            rumps.alert(
                title="❌ 不正解",
                message=(
                    f"{quiz['question']}\n\n"
                    f"あなたの回答: {user_answer}\n"
                    f"正解: {quiz['correct_answer']}"
                )
            )
        
        # 統計を更新
        self.update_stats_menu()


def main():
    """メイン関数"""
    app = VocabLibApp()
    app.run()


if __name__ == "__main__":
    main()
