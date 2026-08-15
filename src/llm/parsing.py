"""LLM出力の抽出・検証

LLMは指示を無視して余計な装飾を付けてくる。
- 「例:」「1.」「- 」などのマーカー
- ```markdown コードフェンス
- JSONのみと指示しても添える説明文
- そして**対象単語を含まない例文**

ここはv1で実際にそれらに殴られて育った実装をほぼそのまま引き継いでいる。
純粋関数だけで構成し、ネットワークに触れないのでテストできる。
"""
from __future__ import annotations

import json
import re

# LLMが使う可能性のある区切り記号（em dash / en dash / ハイフン）
_DASH_PATTERN = re.compile(r"\s*[—–]\s*")
_LEADING_MARKER = re.compile(r"^\s*(例[:：]|[-*・]|\d+[.)])\s*")


def extract_example_line(out: str) -> str | None:
    """LLM出力から「英文 — 和訳」形式の行を1つ抽出し、区切りを ` — ` に正規化する。

    見つからなければ None（呼び出し側は次のProviderへ落とす）。
    """
    for raw in out.strip().splitlines():
        line = raw.strip()
        if not line or line.startswith("```"):
            continue
        line = _LEADING_MARKER.sub("", line).strip()
        if "—" in line or "–" in line:
            return _DASH_PATTERN.sub(" — ", line, count=1)
        if " - " in line:
            return line.replace(" - ", " — ", 1)
    return None


def sentence_uses_word(sentence: str, word: str) -> bool:
    """例文の英語部分が対象単語を含むか検証する（語尾変化を許容）。

    LLMは平気で対象単語と無関係な例文を返す。これを通さないと、
    覚える助けにならない例文がDBにキャッシュされてしまう。
    """
    english = re.split(r"—|–| - ", sentence, maxsplit=1)[0].lower()
    tokens = re.findall(r"[a-z]+", word.lower())
    # 意味を持つ語（4文字以上）を優先。無ければ全トークンで判定
    significant = [t for t in tokens if len(t) >= 4] or tokens
    for token in significant:
        # 語尾変化（-s / -ed / -ing 等）を許容するため末尾2文字を捨てて語幹とみなす
        stem = token[: max(4, len(token) - 2)]
        if stem in english:
            return True
    return False


def extract_json(out: str) -> dict | None:
    """出力からJSONオブジェクトを1つ抜き出してdictにする。

    コードフェンスや前後の説明文が付いていても取り出せる。
    """
    cleaned = re.sub(r"^```[a-zA-Z0-9]*\n", "", out.strip())
    cleaned = re.sub(r"\n```$", "", cleaned)

    match = re.search(r"(\{(?:.|\n)*\})", cleaned)
    candidate = match.group(1) if match else cleaned

    try:
        parsed = json.loads(candidate)
    except (json.JSONDecodeError, ValueError):
        return None
    return parsed if isinstance(parsed, dict) else None


def looks_japanese(text: str) -> bool:
    """かな・漢字を含むか（＝和訳として採用してよいか）。

    小さいモデルは「日本語で」と指示しても英語をそのまま返すことがある。
    ASCIIだけの出力は和訳ではないので弾く。

    かなを必須にはしない。「会議」「延期」のような漢字のみの和訳が
    正当に存在するため。
    """
    return any(
        "぀" <= ch <= "ヿ"   # ひらがな・カタカナ
        or "一" <= ch <= "鿿"  # 漢字
        for ch in text
    )


def fallback_example_sentence(word: str, meaning: str) -> str:
    """全てのLLMが失敗したときの最終手段。必ず成功する"""
    return f'"{word}" means "{meaning}"'
