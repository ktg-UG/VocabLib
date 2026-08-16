"""単語追加フォーム

オートフィルの結果はたいてい正しいので、**修正しないなら「保存」を1回押すだけ**で
登録できるようにする。直したい項目だけ「修正」を押して編集する。

`QuizPanel` と同じ方針で、このクラスはUIだけを担当する。
DB書き込みと重複エラーの扱いは `on_save` の呼び出し先に任せる。
"""
from __future__ import annotations

from typing import Callable

from AppKit import (
    NSBackingStoreBuffered,
    NSButton,
    NSFont,
    NSMakeRect,
    NSPanel,
    NSPopUpButton,
    NSScreen,
    NSTextField,
    NSWindowStyleMaskClosable,
    NSWindowStyleMaskTitled,
    NSWindowStyleMaskUtilityWindow,
)
from Foundation import NSObject

from ..db.store import PARTS_OF_SPEECH
from ..llm import WordInfo

# プルダウンの選択肢。自由入力だと表記ゆれ（動詞 / 他動詞 / 【動】…）が起きて
# 将来の集計が効かなくなるため固定する。
# 品詞そのものの一覧は一括インポートとも共有する（db.store が正）。
POS_UNSET = "（未設定）"
POS_OPTIONS = [POS_UNSET, *PARTS_OF_SPEECH]

# ボタンの識別子（NSButton の tag）。単語に付ける「タグ」とは別物なので注意
TAG_EDIT_ENGLISH = 0
TAG_EDIT_JAPANESE = 1
TAG_SAVE = 2
TAG_CANCEL = 3
TAG_EDIT_WORD_TAG = 4

PANEL_WIDTH = 380
PANEL_HEIGHT = 220
LOADING_TEXT = "取得中..."
# タグ未設定のときの表示。空欄だと入力できる場所だと分からないため
TAG_UNSET_TEXT = "（なし）"


class _AddWordDelegate(NSObject):
    """ボタンの target 兼ウィンドウの delegate（素のPythonクラスは target になれない）"""

    def buttonClicked_(self, sender):
        self.owner._handle_click(sender.tag())

    def windowWillClose_(self, notification):
        self.owner._handle_window_will_close()


class AddWordPanel:
    def __init__(
        self,
        english: str,
        on_save: Callable[[str, str, str | None, str], bool],
        on_close: Callable[[], None],
        tag: str = "",
    ):
        """
        Args:
            on_save: (英単語, 和訳, 品詞, タグ) を受け取り、登録できたら True を返す。
                False ならフォームを開いたままにする（重複などを直せるように）。
            on_close: フォームが閉じたとき（保存・キャンセル・×のいずれでも）
            tag: 英単語欄に `#TOEIC` と書かれていた場合のタグ。無ければ空文字
        """
        self._english = english
        self._tag = tag
        self._on_save = on_save
        self._on_close = on_close

        self._panel = None
        self._delegate = None
        self._english_field = None
        self._japanese_field = None
        self._pos_popup = None
        self._tag_field = None
        self._closed = False

    # ── 表示 ─────────────────────────────────────────────────────────────

    def show(self) -> None:
        width, height = PANEL_WIDTH, PANEL_HEIGHT

        screen = NSScreen.mainScreen().visibleFrame()
        x = screen.origin.x + (screen.size.width - width) / 2
        y = screen.origin.y + (screen.size.height - height) / 2

        panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            ((x, y), (width, height)),
            NSWindowStyleMaskTitled
            | NSWindowStyleMaskClosable
            | NSWindowStyleMaskUtilityWindow,
            NSBackingStoreBuffered,
            False,
        )
        panel.setTitle_("単語を追加")
        panel.setReleasedWhenClosed_(False)

        delegate = _AddWordDelegate.alloc().init()
        delegate.owner = self
        panel.setDelegate_(delegate)

        self._panel = panel
        self._delegate = delegate

        content = panel.contentView()

        content.addSubview_(
            _label("追加する内容を確認してください", NSMakeRect(16, height - 40, width - 32, 22),
                   bold=True, size=13)
        )

        # 英単語
        content.addSubview_(_label("英単語", NSMakeRect(16, height - 74, 60, 20), size=12))
        self._english_field = _value_field(
            self._english, NSMakeRect(80, height - 76, 200, 22)
        )
        content.addSubview_(self._english_field)
        content.addSubview_(
            _button("修正", NSMakeRect(288, height - 78, 70, 26), TAG_EDIT_ENGLISH, delegate)
        )

        # 和訳（オートフィルが届くまでは「取得中...」）
        content.addSubview_(_label("和訳", NSMakeRect(16, height - 104, 60, 20), size=12))
        self._japanese_field = _value_field(
            LOADING_TEXT, NSMakeRect(80, height - 106, 200, 22)
        )
        content.addSubview_(self._japanese_field)
        content.addSubview_(
            _button("修正", NSMakeRect(288, height - 108, 70, 26), TAG_EDIT_JAPANESE, delegate)
        )

        # 品詞（プルダウン。オートフィルが届くまで無効）
        content.addSubview_(_label("品詞", NSMakeRect(16, height - 134, 60, 20), size=12))
        popup = NSPopUpButton.alloc().initWithFrame_pullsDown_(
            NSMakeRect(80, height - 138, 150, 26), False
        )
        popup.addItemsWithTitles_(POS_OPTIONS)
        popup.setEnabled_(False)
        content.addSubview_(popup)
        self._pos_popup = popup

        # タグ（`#` 記法で指定済みならその値。オートフィルの対象にはしない）
        content.addSubview_(_label("タグ", NSMakeRect(16, height - 164, 60, 20), size=12))
        self._tag_field = _value_field(
            self._tag or TAG_UNSET_TEXT, NSMakeRect(80, height - 166, 200, 22)
        )
        content.addSubview_(self._tag_field)
        content.addSubview_(
            _button("修正", NSMakeRect(288, height - 168, 70, 26),
                    TAG_EDIT_WORD_TAG, delegate)
        )

        content.addSubview_(
            _button("キャンセル", NSMakeRect(186, 14, 90, 28), TAG_CANCEL, delegate)
        )
        save_button = _button("保存", NSMakeRect(284, 14, 80, 28), TAG_SAVE, delegate)
        save_button.setKeyEquivalent_("\r")   # Enterで保存できる
        content.addSubview_(save_button)

        panel.makeKeyAndOrderFront_(None)

    # ── オートフィルの反映 ────────────────────────────────────────────────

    def set_autofill(self, info: WordInfo | None) -> None:
        """LLMの取得結果を流し込む。必ずメインスレッドから呼ぶこと。

        取得中にフォームが閉じられていることがあるため、閉じていれば何もしない。
        ユーザーが既に和訳を手入力していた場合は上書きしない。
        """
        if self._closed or self._japanese_field is None:
            return

        current = self._japanese_field.stringValue().strip()
        if current in ("", LOADING_TEXT):
            self._japanese_field.setStringValue_(info.japanese if info else "")

        if self._pos_popup is not None:
            self._pos_popup.setEnabled_(True)
            if info and info.part_of_speech in POS_OPTIONS:
                self._pos_popup.selectItemWithTitle_(info.part_of_speech)

        # 和訳が空（LLM失敗）なら、すぐ入力できるようにしておく
        if not self._japanese_field.stringValue().strip():
            _make_editable(self._japanese_field)
            if self._panel is not None:
                self._panel.makeFirstResponder_(self._japanese_field)

    # ── 操作 ─────────────────────────────────────────────────────────────

    def _handle_click(self, tag: int) -> None:
        if tag == TAG_EDIT_ENGLISH:
            self._enable_editing(self._english_field)
        elif tag == TAG_EDIT_JAPANESE:
            self._enable_editing(self._japanese_field)
        elif tag == TAG_EDIT_WORD_TAG:
            # 「（なし）」を消してから編集させる（そのまま打ち足させない）
            if self._tag_field is not None:
                if self._tag_field.stringValue().strip() == TAG_UNSET_TEXT:
                    self._tag_field.setStringValue_("")
            self._enable_editing(self._tag_field)
        elif tag == TAG_CANCEL:
            self.close()
        elif tag == TAG_SAVE:
            self._save()

    def _enable_editing(self, field) -> None:
        if field is None:
            return
        _make_editable(field)
        if self._panel is not None:
            self._panel.makeFirstResponder_(field)

    def _save(self) -> None:
        english = self._english_field.stringValue().strip()
        japanese = self._japanese_field.stringValue().strip()
        if japanese == LOADING_TEXT:
            japanese = ""

        pos = self._pos_popup.titleOfSelectedItem() if self._pos_popup else POS_UNSET
        part_of_speech = None if pos == POS_UNSET else pos

        tag = self._tag_field.stringValue().strip() if self._tag_field else ""
        if tag == TAG_UNSET_TEXT:
            tag = ""

        # 登録できたら閉じる。できなければ（重複など）開いたままにして直させる
        if self._on_save(english, japanese, part_of_speech, tag):
            self.close()

    # ── 終了 ─────────────────────────────────────────────────────────────

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True

        if self._panel is not None:
            # delegate を外してから閉じる（windowWillClose_ 経由の再入を防ぐ）
            self._panel.setDelegate_(None)
            self._panel.close()
            self._panel = None

        self._on_close()

    def _handle_window_will_close(self) -> None:
        """タイトルバーの×で閉じられたとき"""
        if self._closed:
            return
        self._closed = True
        self._panel = None
        self._on_close()


# ── ウィジェット生成のヘルパー ────────────────────────────────────────────

def _label(text: str, frame, bold: bool = False, size: int = 12):
    label = NSTextField.alloc().initWithFrame_(frame)
    label.setStringValue_(text)
    label.setBezeled_(False)
    label.setDrawsBackground_(False)
    label.setEditable_(False)
    label.setSelectable_(False)
    label.setFont_(
        NSFont.boldSystemFontOfSize_(size) if bold else NSFont.systemFontOfSize_(size)
    )
    return label


def _value_field(text: str, frame):
    """値の表示欄。

    表示用ラベルと入力欄を別ウィジェットにせず、`NSTextField` 1つの
    編集可否を切り替えて使う。実体が同じなので、保存時は常に
    `stringValue()` を読むだけで済み、分岐が要らない。
    """
    field = NSTextField.alloc().initWithFrame_(frame)
    field.setStringValue_(text)
    field.setEditable_(False)
    field.setBezeled_(False)
    field.setDrawsBackground_(False)
    field.setFont_(NSFont.systemFontOfSize_(13))
    return field


def _make_editable(field) -> None:
    field.setEditable_(True)
    field.setBezeled_(True)
    field.setDrawsBackground_(True)
    field.setSelectable_(True)


def _button(title: str, frame, tag: int, target):
    button = NSButton.alloc().initWithFrame_(frame)
    button.setTitle_(title)
    button.setTarget_(target)
    button.setAction_("buttonClicked:")
    button.setTag_(tag)
    return button
