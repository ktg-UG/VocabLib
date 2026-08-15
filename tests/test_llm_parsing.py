"""LLM出力の抽出・検証のテスト（純粋関数なのでネットワーク不要）"""
from src.llm.parsing import (
    extract_example_line,
    extract_json,
    fallback_example_sentence,
    looks_japanese,
    sentence_uses_word,
)


# ── 例文の抽出 ────────────────────────────────────────────────────────────

def test_例文行を抽出できる():
    out = "He postponed the meeting. — 彼は会議を延期した。"
    assert extract_example_line(out) == "He postponed the meeting. — 彼は会議を延期した。"


def test_先頭の例マーカーを取り除く():
    out = "例: He postponed the meeting. — 彼は会議を延期した。"
    assert extract_example_line(out).startswith("He postponed")


def test_箇条書きや番号のマーカーも取り除く():
    assert extract_example_line("1. A — B").startswith("A")
    assert extract_example_line("- A — B").startswith("A")
    assert extract_example_line("・A — B").startswith("A")


def test_区切り記号を全角ダッシュに正規化する():
    """LLMは — / – / - を気分で使い分けるので、表示前に揃える"""
    assert extract_example_line("A – B") == "A — B"
    assert extract_example_line("A - B") == "A — B"


def test_コードフェンスの行を無視する():
    out = "```\nHe postponed it. — 彼は延期した。\n```"
    assert extract_example_line(out) == "He postponed it. — 彼は延期した。"


def test_説明文が混ざっていても例文行を拾う():
    out = "はい、例文を作成しました。\n\nHe postponed it. — 彼は延期した。"
    assert extract_example_line(out) == "He postponed it. — 彼は延期した。"


def test_区切りが無ければNoneを返す():
    """形式が不正なら採用せず次のProviderに落とすため"""
    assert extract_example_line("He postponed the meeting.") is None
    assert extract_example_line("") is None


# ── 例文が対象単語を含むかの検証 ──────────────────────────────────────────

def test_単語をそのまま含む例文を通す():
    assert sentence_uses_word("He will postpone it. — 彼は延期する。", "postpone")


def test_語尾変化した単語も通す():
    """LLMは活用形で出してくる。原形一致だけだと弾いてしまう"""
    assert sentence_uses_word("He postponed it. — 彼は延期した。", "postpone")
    assert sentence_uses_word("He is postponing it. — 彼は延期している。", "postpone")


def test_無関係な例文を弾く():
    """LLMは対象単語と無関係な例文を平気で返す。ここで止める"""
    assert not sentence_uses_word("The cat sleeps well. — 猫はよく眠る。", "postpone")


def test_和訳側に単語が出ていても英文側で判定する():
    assert not sentence_uses_word("The cat sleeps. — postpone は延期する。", "postpone")


def test_短い単語も判定できる():
    assert sentence_uses_word("I run every day. — 毎日走る。", "run")
    assert not sentence_uses_word("The cat sleeps. — 猫は眠る。", "run")


# ── JSONの抽出 ────────────────────────────────────────────────────────────

def test_素のJSONを読める():
    assert extract_json('{"japanese": "延期する"}') == {"japanese": "延期する"}


def test_コードフェンス付きのJSONを読める():
    out = '```json\n{"japanese": "延期する", "part_of_speech": "動詞"}\n```'
    assert extract_json(out)["part_of_speech"] == "動詞"


def test_説明文が前後についていても読める():
    out = 'はい、以下が結果です:\n{"japanese": "延期する"}\nご確認ください。'
    assert extract_json(out) == {"japanese": "延期する"}


def test_壊れたJSONはNoneを返す():
    assert extract_json("{japanese: 延期する") is None
    assert extract_json("これはJSONではありません") is None


def test_JSON配列はNoneを返す():
    """dictを期待しているので配列は受け付けない"""
    assert extract_json("[1, 2, 3]") is None


# ── 日本語判定 ────────────────────────────────────────────────────────────

def test_かなを含めば日本語とみなす():
    assert looks_japanese("延期する")
    assert looks_japanese("りんご")


def test_漢字のみでも日本語とみなす():
    """「会議」「延期」など漢字だけの和訳は正当なので弾いてはいけない"""
    assert looks_japanese("会議")


def test_英語のみは日本語とみなさない():
    """指示しても英語をそのまま返すモデルがあるため"""
    assert not looks_japanese("postpone")
    assert not looks_japanese("")


# ── 最終フォールバック ────────────────────────────────────────────────────

def test_最終フォールバックは必ず文字列を返す():
    assert fallback_example_sentence("postpone", "延期する") == '"postpone" means "延期する"'
