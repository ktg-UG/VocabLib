"""忘却曲線に基づく復習スケジューリング（SM-2アルゴリズム）

エビングハウスの忘却曲線に基づき、SuperMemo 2 (SM-2) で次回の復習日時と
難易度係数 (ease factor) を計算する。

このモジュールは純粋関数のみで構成し、DBやUIに一切依存させない。
（テストしやすく、`answer_log` から状態を再計算できるようにするため）
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import NamedTuple

# ── パラメータ ────────────────────────────────────────────────────────────
INITIAL_EASE_FACTOR = 2.5   # 新規単語の初期EF（SM-2の標準値）
MIN_EASE_FACTOR = 1.3       # EFの下限（SM-2の標準値。これ未満は間隔が縮みすぎる）
MAX_EASE_FACTOR = 3.0       # EFの上限（v2で追加。理由は下記 quality の項を参照）
INCORRECT_RETRY_MINUTES = 5  # 不正解時に再出題するまでの分数

# 4択クイズは自己申告の手応え(0-5)を取れないため、正誤の2値をqualityに割り当てる。
#
# v1は正解=4を使っていたが、SM-2のEF更新式に q=4 を入れると増分が
#   0.1 - (5-4) * (0.08 + (5-4) * 0.02) = 0.1 - 0.10 = 0
# となり、**正解ではEFが一切上がらず、不正解でのみ下がる一方通行**になっていた。
# その結果、一度間違えた単語はEFが下がったまま永久に回復しない。
#
# v2は正解=5とし、正解でEFが +0.1 回復するようにした。ただし常に満点扱いのため
# EFが青天井に伸びて復習間隔が発散しないよう MAX_EASE_FACTOR で頭打ちにする。
QUALITY_CORRECT = 5
QUALITY_INCORRECT = 2


class ReviewResult(NamedTuple):
    """SM-2の計算結果"""
    next_review: datetime
    ease_factor: float
    interval_days: float
    repetitions: int


def calculate_next_review(
    is_correct: bool,
    repetitions: int,
    ease_factor: float,
    interval_days: float,
    now: datetime | None = None,
) -> ReviewResult:
    """次回の復習日時とSM-2パラメータを計算する。

    Args:
        is_correct: 今回正解したか
        repetitions: これまでの連続正解回数
        ease_factor: 現在のEF（覚えやすさ係数）
        interval_days: 現在の復習間隔（日数）
        now: 基準時刻。省略時は現在時刻（テストから固定時刻を渡せるようにしている）

    Returns:
        ReviewResult(next_review, ease_factor, interval_days, repetitions)
    """
    if now is None:
        now = datetime.now(timezone.utc)

    quality = QUALITY_CORRECT if is_correct else QUALITY_INCORRECT

    if is_correct:
        # 正解: 間隔を伸ばす（1日 → 6日 → 前回 × EF）
        if repetitions == 0:
            interval_days = 1.0
        elif repetitions == 1:
            interval_days = 6.0
        else:
            interval_days = interval_days * ease_factor
        repetitions += 1
    else:
        # 不正解: 連続正解をリセットし、数分後に再出題する
        repetitions = 0
        interval_days = INCORRECT_RETRY_MINUTES / (60 * 24)

    # EF更新式: EF' = EF + (0.1 - (5-q) * (0.08 + (5-q) * 0.02))
    delta = 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)
    ease_factor = min(MAX_EASE_FACTOR, max(MIN_EASE_FACTOR, ease_factor + delta))

    next_review = now + timedelta(days=interval_days)

    return ReviewResult(
        next_review=next_review,
        ease_factor=ease_factor,
        interval_days=interval_days,
        repetitions=repetitions,
    )
