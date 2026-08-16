"""単語の一括インポート

1行1単語のテキストファイルを読み、和訳と品詞をLLMに補完させて登録する。

    uv run python -m src.tools.import_words tmp.txt
    uv run python -m src.tools.import_words tmp.txt --dry-run

和訳・品詞を自分で指定したい行は、カンマ区切りで書けばLLMを呼ばずに登録する。

    yield                       ← LLMが和訳・品詞を補完する
    incorporation, 法人設立, 名詞   ← 書いたとおりに登録する（LLMを呼ばない）
"""
from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from .. import config
from ..db.store import PARTS_OF_SPEECH, DuplicateWordError, Store
from ..llm import LLMClient

# Geminiの無料枠には毎分のリクエスト上限がある。一気に投げると429で
# ローカルLLMに落ちてしまい、品質が下がるので間隔を空ける。
DEFAULT_DELAY_SECONDS = 1.0


@dataclass(frozen=True)
class Entry:
    """インポートする1件。和訳が未指定ならLLMに補完させる"""

    english: str
    japanese: str | None = None
    part_of_speech: str | None = None

    @property
    def needs_lookup(self) -> bool:
        return self.japanese is None


@dataclass
class ImportResult:
    added: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)   # 既に登録済み
    failed: list[str] = field(default_factory=list)    # LLMが和訳を返さなかった

    @property
    def total(self) -> int:
        return len(self.added) + len(self.skipped) + len(self.failed)


def parse_entries(text: str) -> list[Entry]:
    """テキストからインポート対象を作る。

    - 前後の空白を除去する（実データに末尾スペースがあった）
    - 空行と `#` で始まる行は無視する
    - ファイル内の重複も除く（大文字小文字は区別しない）
    - `英単語, 和訳, 品詞` の形式なら、その値をそのまま使う（品詞は省略可）

    英単語側にカンマを含むフレーズは扱えないが、実データに存在しないので許容する。

    Raises:
        ValueError: 品詞がプルダウンの選択肢に無い（表記ゆれを防ぐため弾く）
    """
    entries: list[Entry] = []
    seen: set[str] = set()

    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue

        entry = _parse_line(line, lineno)
        key = entry.english.lower()
        if key in seen:
            continue
        seen.add(key)
        entries.append(entry)

    return entries


def _parse_line(line: str, lineno: int) -> Entry:
    fields = [part.strip() for part in line.split(",")]
    english = fields[0]
    japanese = fields[1] if len(fields) >= 2 and fields[1] else None
    pos = fields[2] if len(fields) >= 3 and fields[2] else None

    if japanese is None:
        # 和訳が無ければ品詞だけ指定しても意味がないので、単語行として扱う
        return Entry(english=english)

    if pos is not None and pos not in PARTS_OF_SPEECH:
        raise ValueError(
            f"{lineno}行目: 品詞「{pos}」は選択肢にありません"
            f"（{' / '.join(PARTS_OF_SPEECH)}）"
        )
    return Entry(english=english, japanese=japanese, part_of_speech=pos)


def import_words(
    store: Store,
    llm: LLMClient,
    entries: list[Entry],
    *,
    dry_run: bool = False,
    delay: float = DEFAULT_DELAY_SECONDS,
    log: Callable[[str], None] = print,
) -> ImportResult:
    """単語を順に登録する。

    和訳が取得できなかった単語は**登録しない**。和訳の無い単語は出題できず、
    4択の選択肢としても使えないため、DBに入れる価値がない。
    最後に一覧で報告し、手で登録してもらう。
    """
    result = ImportResult()
    existing = {word.english.lower() for word in store.list_words()}

    for index, entry in enumerate(entries, start=1):
        english = entry.english
        prefix = f"[{index}/{len(entries)}] {english}"

        if english.lower() in existing:
            log(f"{prefix} … skip（登録済み）")
            result.skipped.append(english)
            continue

        if entry.needs_lookup:
            info = llm.lookup_word(english)
            if info is None:
                log(f"{prefix} … 失敗（和訳を取得できませんでした）")
                result.failed.append(english)
                continue
            japanese, part_of_speech = info.japanese, info.part_of_speech
        else:
            japanese, part_of_speech = entry.japanese, entry.part_of_speech

        pos_label = f" / {part_of_speech}" if part_of_speech else ""
        if dry_run:
            log(f"{prefix} … {japanese}{pos_label}（dry-run）")
        else:
            try:
                store.add_word(english, japanese, part_of_speech)
            except DuplicateWordError:
                # 同じ (英単語, 和訳) が既にある。上の existing では拾えない経路
                log(f"{prefix} … skip（登録済み）")
                result.skipped.append(english)
                continue
            log(f"{prefix} … {japanese}{pos_label}")

        existing.add(english.lower())
        result.added.append(english)

        # LLMを呼んでいない行で待つ理由は無い（レート制限のための待機なので）
        if delay and entry.needs_lookup and index < len(entries):
            time.sleep(delay)

    return result


def format_summary(result: ImportResult, dry_run: bool) -> str:
    lines = [
        "",
        f"  {'登録予定' if dry_run else '登録'}   {len(result.added)}語",
        f"  skip     {len(result.skipped)}語",
        f"  失敗     {len(result.failed)}語",
    ]
    if result.failed:
        lines.append("")
        lines.append("失敗した単語（メニューバーの「単語を追加...」から手で登録してください）:")
        lines.extend(f"  - {word}" for word in result.failed)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="単語を一括インポートする")
    parser.add_argument("path", type=Path, help="1行1単語のテキストファイル")
    parser.add_argument(
        "--dry-run", action="store_true", help="登録せず、取得結果だけ表示する"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_DELAY_SECONDS,
        help=f"LLMを呼ぶ行ごとの待ち時間（秒）。既定 {DEFAULT_DELAY_SECONDS}",
    )
    args = parser.parse_args(argv)

    if not args.path.exists():
        print(f"ファイルが見つかりません: {args.path}", file=sys.stderr)
        return 1

    try:
        entries = parse_entries(args.path.read_text(encoding="utf-8"))
    except ValueError as error:
        print(f"{args.path}: {error}", file=sys.stderr)
        return 1

    if not entries:
        print("登録できる単語がありません", file=sys.stderr)
        return 1

    lookups = sum(1 for entry in entries if entry.needs_lookup)
    print(f"インポート: {args.path}（{len(entries)}語 / うちLLM補完 {lookups}語）\n")

    store = Store(config.DB_PATH)
    try:
        result = import_words(
            store,
            LLMClient(),
            entries,
            dry_run=args.dry_run,
            delay=args.delay,
        )
    finally:
        store.close()

    print(format_summary(result, args.dry_run))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
