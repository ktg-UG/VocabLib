"""タグの正規化と入力書式のパース

タグは UI・DB層・一括インポートの3箇所から触るため、純粋関数だけをここに集める。
`ui/` に置くと `rumps` / `AppKit` を巻き込んでテストできず、`db/store.py` に置くと
入力書式の話がデータアクセス層に混ざるため、`config.py` と同じ最下層に置く。

1単語につきタグは1つ。空文字が「タグなし」を表す（`None` は使わない。
「タグなし」の表現が2通りあると、検索条件を毎回2つ書くことになるため）。
"""
from __future__ import annotations

# 入力欄でタグを書き始める記号。`incorporation #TOEIC` のように使う
TAG_PREFIX = "#"


def normalize_tag(text: str | None) -> str:
    """タグを保存できる形に整える。空文字は「タグなし」。

    - 前後の空白を除去する
    - 先頭の `#` を取る（`#TOEIC` と書く入力記法に合わせる）
    - 内側の空白は保つ（`TOEIC Part5` を1つのタグとして許す）
    - 大文字小文字は変換しない（表示にそのまま使うため）
    - カンマを除去する（一括インポートの区切り文字と衝突するため）

    大文字小文字を潰さない代わりに同一視もしない。`toeic` と `TOEIC` は別タグになる。
    メニューから既存のタグを選べるので、手で打ち直す機会自体が少ない。
    """
    if not text:
        return ""

    tag = text.strip().lstrip(TAG_PREFIX).replace(",", "").strip()
    return tag


def parse_word_input(text: str) -> tuple[str, str]:
    """英単語の入力を (英単語, タグ) に分ける。

    >>> parse_word_input("incorporation #TOEIC")
    ('incorporation', 'TOEIC')
    >>> parse_word_input("extend an invitation to")
    ('extend an invitation to', '')

    英単語側に空白を含むフレーズがあるため、空白ではなく **最初の `#`** で1回だけ分割する。
    `#` が無ければタグは空文字。`#` だけでタグ名が無い場合もタグなしとして扱う。
    """
    if not text:
        return "", ""

    english, separator, rest = text.partition(TAG_PREFIX)
    if not separator:
        return english.strip(), ""

    return english.strip(), normalize_tag(rest)
