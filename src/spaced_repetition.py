"""忘却曲線に基づくSpaced Repetition (SM-2アルゴリズム)

エビングハウスの忘却曲線に基づき、SuperMemo 2 (SM-2) アルゴリズムで
次回の復習日・難易度係数を計算する。
"""
import random
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from .config import INITIAL_EASE_FACTOR, INCORRECT_RETRY_MINUTES

_LOGGER = logging.getLogger(__name__)

# タイムゾーン（日本時間）
JST = timezone(timedelta(hours=9))


# ── SM-2 アルゴリズム ─────────────────────────────────────────────────────────

def calculate_next_review(
    is_correct: bool,
    repetitions: int,
    ease_factor: float,
    interval_days: float,
) -> Tuple[datetime, float, float, int]:
    """SM-2アルゴリズムで次回復習日を計算する。

    Args:
        is_correct: 正解したかどうか
        repetitions: 現在の連続正解回数
        ease_factor: 現在の難易度係数 (EF)
        interval_days: 現在の復習間隔（日数）

    Returns:
        (next_review, new_ease_factor, new_interval_days, new_repetitions)
    """
    now = datetime.now(JST)

    # quality: SM-2で使う回答品質スコア (0-5)
    quality = 4 if is_correct else 1

    if quality >= 3:  # 正解
        if repetitions == 0:
            interval_days = 1                          # 初回: 1日後
        elif repetitions == 1:
            interval_days = 6                          # 2回目: 6日後
        else:
            interval_days = interval_days * ease_factor  # 以降: 前回間隔 × EF
        repetitions += 1
    else:  # 不正解
        repetitions = 0
        interval_days = INCORRECT_RETRY_MINUTES / (60 * 24)  # 設定値を日数に変換

    # EF更新: EF' = EF + (0.1 - (5-q) * (0.08 + (5-q) * 0.02))
    ease_factor = max(
        1.3,
        ease_factor + 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02),
    )

    next_review = now + timedelta(days=interval_days)

    return next_review, ease_factor, interval_days, repetitions


# ── 出題単語の選択 ────────────────────────────────────────────────────────────

def select_word(
    learning_records: Dict[Tuple[str, str], dict],
    words: List[Tuple[str, str]],
) -> Optional[Tuple[str, str]]:
    """忘却曲線に基づいて次に出題する単語を選択する。

    優先順位:
        1. next_review ≤ 現在時刻 の単語（期限超過が最も古いものを優先）
        2. 未学習の単語（学習記録に未登録）からランダム選択
        3. 全単語が学習済みで期限前 → next_review が最も近い単語を選択

    Args:
        learning_records: {(word, meaning): record_dict} の辞書
        words: [(word, meaning), ...] 全単語リスト

    Returns:
        (word, meaning) または None
    """
    if not words:
        return None

    now = datetime.now(JST)

    # 優先度1: 期限切れの単語を収集
    overdue: List[Tuple[str, str, datetime]] = []
    # 優先度2: 未学習の単語を収集
    unlearned: List[Tuple[str, str]] = []
    # 優先度3: 期限前の学習済み単語
    upcoming: List[Tuple[str, str, datetime]] = []

    for word, meaning in words:
        key = (word, meaning)
        record = learning_records.get(key)

        if record is None:
            # 学習記録に未登録 → 未学習
            unlearned.append((word, meaning))
        else:
            next_review = record.get("next_review")
            if next_review is None:
                unlearned.append((word, meaning))
            elif next_review <= now:
                overdue.append((word, meaning, next_review))
            else:
                upcoming.append((word, meaning, next_review))

    # 優先度1: 期限超過が最も古いものを選択
    if overdue:
        overdue.sort(key=lambda x: x[2])  # next_review が古い順
        word, meaning, _ = overdue[0]
        _LOGGER.debug("期限切れ単語を出題: %s (%s)", word, meaning)
        return (word, meaning)

    # 優先度2: 未学習からランダム選択
    if unlearned:
        choice = random.choice(unlearned)
        _LOGGER.debug("未学習単語を出題: %s (%s)", choice[0], choice[1])
        return choice

    # 優先度3: next_review が最も近い単語
    if upcoming:
        upcoming.sort(key=lambda x: x[2])  # next_review が近い順
        word, meaning, _ = upcoming[0]
        _LOGGER.debug("次回復習が最も近い単語を出題: %s (%s)", word, meaning)
        return (word, meaning)

    return None
