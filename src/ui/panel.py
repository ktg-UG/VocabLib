"""クイズパネル（画面右下に浮かぶ4択ウィンドウ）

v1では `app.py` の中にパネル生成・回答判定・例文表示が全部入っていた。
v2ではこのファイルに切り出し、メニューバー側とはコールバック2本
（`on_answer` / `on_close`）だけでつながる。
"""
from __future__ import annotations

from typing import Callable

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
from Foundation import NSNotificationCenter, NSObject
from PyObjCTools.AppHelper import callLater

from .. import config
from ..quiz import Quiz

CLOSE_BUTTON_TAG = -1
CORRECT_AUTO_CLOSE_SECONDS = 1.0
EXAMPLE_AREA_HEIGHT = 80


class _PanelDelegate(NSObject):
    """ボタンの target 兼ウィンドウの delegate

    NSButton の target と NSWindow の delegate は Objective-C のオブジェクトで
    ある必要があるため、素のPythonクラスである QuizPanel を直接は渡せない。
    このクラスが橋渡しをする。
    """

    def buttonClicked_(self, sender):
        self.owner._handle_click(sender.tag())

    def windowWillClose_(self, notification):
        # タイトルバーの×で閉じられた場合もここを通る。
        # これが無いと、×で閉じたときに on_close が呼ばれず出題タイマーが止まる。
        self.owner._handle_window_will_close()


class QuizPanel:
    """4択クイズを表示するフローティングパネル"""

    def __init__(
        self,
        quiz: Quiz,
        on_answer: Callable[[bool], None],
        on_close: Callable[[], None],
    ):
        self.quiz = quiz
        self._on_answer = on_answer
        self._on_close = on_close

        self._panel = None
        self._delegate = None      # 参照を保持しないとGCされてクリックが効かなくなる
        self._buttons: list = []
        self._example_label = None
        self._resign_observer = None
        self._answered = False
        self._closed = False

    # ── 表示 ─────────────────────────────────────────────────────────────

    def show(self) -> None:
        width = config.PANEL_WIDTH
        height = config.PANEL_HEIGHT
        margin = config.PANEL_MARGIN

        screen = NSScreen.mainScreen().visibleFrame()
        x = screen.origin.x + screen.size.width - width - margin
        y = screen.origin.y + margin

        panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            ((x, y), (width, height)),
            NSWindowStyleMaskTitled
            | NSWindowStyleMaskClosable
            | NSWindowStyleMaskUtilityWindow,
            NSBackingStoreBuffered,
            False,
        )
        panel.setTitle_("VocabLib")
        panel.setLevel_(NSFloatingWindowLevel)   # 他アプリの前面に出す
        panel.setHidesOnDeactivate_(False)
        panel.setReleasedWhenClosed_(False)
        panel.setFloatingPanel_(True)

        delegate = _PanelDelegate.alloc().init()
        delegate.owner = self
        panel.setDelegate_(delegate)

        self._panel = panel
        self._delegate = delegate

        content = panel.contentView()
        content.addSubview_(
            self._make_label(
                f"📚 {self.quiz.word.english}",
                NSMakeRect(12, height - 36, width - 24, 22),
                bold=True,
                size=13,
            )
        )
        content.addSubview_(
            self._make_label(
                "意味を選んでください:",
                NSMakeRect(12, height - 56, width - 24, 16),
                bold=False,
                size=11,
            )
        )

        button_top = height - 80
        self._buttons = []
        for i, choice in enumerate(self.quiz.choices):
            button = NSButton.alloc().initWithFrame_(
                NSMakeRect(12, button_top - i * 28, width - 24, 24)
            )
            button.setTitle_(f"{i + 1}. {choice}")
            button.setTarget_(delegate)
            button.setAction_("buttonClicked:")
            button.setTag_(i)
            content.addSubview_(button)
            self._buttons.append(button)

        panel.makeKeyAndOrderFront_(None)

    def _make_label(self, text: str, frame, bold: bool, size: int, multiline: bool = False):
        """パネル用のラベルを作る。

        multiline=True にしないと改行以降（例文の和訳）が切り捨てられる。
        NSTextField は既定が単一行モードのため、明示的に解除する必要がある。
        （v1で踏んだ落とし穴。解決済みの実装をそのまま踏襲している）
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
        label.setFont_(
            NSFont.boldSystemFontOfSize_(size) if bold else NSFont.systemFontOfSize_(size)
        )
        return label

    # ── 回答 ─────────────────────────────────────────────────────────────

    def _handle_click(self, tag: int) -> None:
        if tag == CLOSE_BUTTON_TAG:
            self.close()
            return
        if self._answered:
            return
        self._answered = True

        correct_index = self.quiz.correct_index
        is_correct = tag == correct_index

        for i, button in enumerate(self._buttons):
            button.setEnabled_(False)
            choice = self.quiz.choices[i]
            if i == correct_index:
                button.setTitle_(f"✅ {i + 1}. {choice}")
                button.setContentTintColor_(NSColor.systemGreenColor())
            elif i == tag:
                button.setTitle_(f"❌ {i + 1}. {choice}")
                button.setContentTintColor_(NSColor.systemRedColor())
            else:
                button.setTitle_(f"　 {i + 1}. {choice}")

        # 回答はこの場で記録する。
        # v1はパネルを閉じるまで保存を遅延させており、閉じる前に落ちると記録が消えた。
        self._on_answer(is_correct)

        if is_correct:
            callLater(CORRECT_AUTO_CLOSE_SECONDS, self.close)
        else:
            self._expand_with_example()
            self._observe_resign_key()

    def _expand_with_example(self) -> None:
        """不正解時: パネルを上方向に伸ばして例文と閉じるボタンを出す"""
        panel = self._panel
        if panel is None:
            return

        frame = panel.frame()
        content = panel.contentView()
        width = int(frame.size.width)

        # 下端を固定したまま上に伸ばすので、既存のビューを拡張分だけ上へずらす
        for subview in content.subviews():
            sf = subview.frame()
            subview.setFrame_(
                NSMakeRect(
                    sf.origin.x,
                    sf.origin.y + EXAMPLE_AREA_HEIGHT,
                    sf.size.width,
                    sf.size.height,
                )
            )
        panel.setFrame_display_animate_(
            NSMakeRect(
                frame.origin.x,
                frame.origin.y,
                frame.size.width,
                frame.size.height + EXAMPLE_AREA_HEIGHT,
            ),
            True,
            True,
        )

        self._example_label = self._make_label(
            _format_example(self.quiz.word.example_sentence),
            NSMakeRect(16, 30, width - 32, 44),
            bold=False,
            size=13,
            multiline=True,
        )
        content.addSubview_(self._example_label)

        close_button = NSButton.alloc().initWithFrame_(NSMakeRect(width - 96, 8, 80, 24))
        close_button.setTitle_("閉じる")
        close_button.setTarget_(self._delegate)
        close_button.setAction_("buttonClicked:")
        close_button.setTag_(CLOSE_BUTTON_TAG)
        content.addSubview_(close_button)

    def set_example(self, sentence: str) -> None:
        """例文ラベルを差し替える（LLM生成の完了時に呼ばれる）。

        必ずメインスレッドから呼ぶこと。生成中にパネルが閉じられている
        ことがあるため、閉じていれば何もしない。
        """
        if self._closed or self._example_label is None:
            return
        self._example_label.setStringValue_(_format_example(sentence))

    def _observe_resign_key(self) -> None:
        """フォーカスが外れたら閉じる（作業に戻ったら勝手に消える）"""
        self._resign_observer = (
            NSNotificationCenter.defaultCenter()
            .addObserverForName_object_queue_usingBlock_(
                NSWindowDidResignKeyNotification, self._panel, None,
                lambda notification: self.close(),
            )
        )

    # ── 終了 ─────────────────────────────────────────────────────────────

    def close(self) -> None:
        """パネルを閉じる。何度呼んでも安全"""
        if self._closed:
            return
        self._closed = True
        self._remove_observer()

        if self._panel is not None:
            # delegate を外してから閉じる。
            # 外さないと windowWillClose_ 経由で close() が再入する。
            self._panel.setDelegate_(None)
            self._panel.close()
            self._panel = None

        self._on_close()

    def _handle_window_will_close(self) -> None:
        """タイトルバーの×で閉じられたとき"""
        if self._closed:
            return
        self._closed = True
        self._remove_observer()
        self._panel = None
        self._on_close()

    def _remove_observer(self) -> None:
        if self._resign_observer is not None:
            NSNotificationCenter.defaultCenter().removeObserver_(self._resign_observer)
            self._resign_observer = None


def _format_example(sentence: str | None) -> str:
    """「英文 — 和訳」を2行に整形する。

    未キャッシュの場合は生成中の表示を出す。生成が終わると
    `set_example()` でこの文字列が置き換わる。
    """
    if not sentence:
        return "💡 例文を生成中..."
    if " — " in sentence:
        english, japanese = sentence.split(" — ", 1)
        return f"💡 {english}\n   {japanese}"
    return f"💡 {sentence}"
