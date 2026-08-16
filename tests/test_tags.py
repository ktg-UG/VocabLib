"""タグの正規化と入力書式のパースのテスト

純粋関数だけなのでDBにもUIにも触らない。
"""
from src.tags import normalize_tag, parse_word_input


# ── normalize_tag ─────────────────────────────────────────────────────────

def test_前後の空白を除去する():
    assert normalize_tag("  TOEIC  ") == "TOEIC"


def test_先頭のシャープを取る():
    """入力欄で #TOEIC と書く記法に合わせる"""
    assert normalize_tag("#TOEIC") == "TOEIC"


def test_シャープと空白が混ざっていても取れる():
    assert normalize_tag(" # TOEIC ") == "TOEIC"


def test_内側の空白は保つ():
    """TOEIC Part5 のようなタグ名を1つのタグとして許す"""
    assert normalize_tag("TOEIC Part5") == "TOEIC Part5"


def test_大文字小文字は変換しない():
    """表示にそのまま使うため。toeic と TOEIC は別タグになる"""
    assert normalize_tag("toeic") == "toeic"


def test_カンマを除去する():
    """一括インポートの区切り文字と衝突するため"""
    assert normalize_tag("TOEIC,ビジネス") == "TOEICビジネス"


def test_空文字とNoneはタグなし():
    assert normalize_tag("") == ""
    assert normalize_tag(None) == ""
    assert normalize_tag("   ") == ""
    assert normalize_tag("#") == ""


# ── parse_word_input ──────────────────────────────────────────────────────

def test_シャープ以降がタグになる():
    assert parse_word_input("incorporation #TOEIC") == ("incorporation", "TOEIC")


def test_シャープが無ければタグなし():
    assert parse_word_input("incorporation") == ("incorporation", "")


def test_空白を含むフレーズでも切れる():
    """空白ではなく # を境目にするので、熟語がタグ側に混ざらない"""
    assert parse_word_input("extend an invitation to #TOEIC") == (
        "extend an invitation to",
        "TOEIC",
    )


def test_シャープの後の空白は無視する():
    assert parse_word_input("yield # TOEIC") == ("yield", "TOEIC")


def test_シャープだけならタグなし():
    assert parse_word_input("yield #") == ("yield", "")


def test_最初のシャープで1回だけ切る():
    """英単語側が意図せずタグに食われないことを確かめる"""
    english, tag = parse_word_input("yield #a#b")
    assert english == "yield"
    assert tag == "a#b"


def test_空入力():
    assert parse_word_input("") == ("", "")
