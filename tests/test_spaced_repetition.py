"""SM-2アルゴリズムのテスト（純粋関数なのでDB不要）"""
from datetime import datetime, timezone

import pytest

from src.srs.spaced_repetition import (
    INITIAL_EASE_FACTOR,
    MAX_EASE_FACTOR,
    MIN_EASE_FACTOR,
    calculate_next_review,
)

NOW = datetime(2026, 8, 14, 0, 0, 0, tzinfo=timezone.utc)


def test_初回正解は1日後に復習():
    r = calculate_next_review(True, repetitions=0, ease_factor=2.5,
                              interval_days=0, now=NOW)
    assert r.interval_days == 1.0
    assert r.repetitions == 1
    assert (r.next_review - NOW).days == 1


def test_2回目の正解は6日後に復習():
    r = calculate_next_review(True, repetitions=1, ease_factor=2.5,
                              interval_days=1, now=NOW)
    assert r.interval_days == 6.0
    assert r.repetitions == 2


def test_3回目以降の正解は間隔がEF倍に伸びる():
    r = calculate_next_review(True, repetitions=2, ease_factor=2.5,
                              interval_days=6, now=NOW)
    assert r.interval_days == pytest.approx(15.0)  # 6 * 2.5


def test_不正解なら連続正解がリセットされ数分後に再出題される():
    r = calculate_next_review(False, repetitions=5, ease_factor=2.5,
                              interval_days=100, now=NOW)
    assert r.repetitions == 0
    assert r.interval_days < 1  # 5分 = 約0.0035日
    assert (r.next_review - NOW).total_seconds() == pytest.approx(5 * 60)


def test_不正解でEFが下がる():
    r = calculate_next_review(False, repetitions=0, ease_factor=2.5,
                              interval_days=0, now=NOW)
    assert r.ease_factor < 2.5


def test_正解でEFが回復する():
    """v1では正解時のEF増分が0で、一度下がると二度と回復しなかった。

    このテストがv1のバグに対する回帰テストになる。
    """
    lowered = calculate_next_review(False, repetitions=0,
                                    ease_factor=INITIAL_EASE_FACTOR,
                                    interval_days=0, now=NOW).ease_factor
    recovered = calculate_next_review(True, repetitions=0,
                                      ease_factor=lowered,
                                      interval_days=0, now=NOW).ease_factor
    assert recovered > lowered


def test_EFは下限を下回らない():
    ef = 1.3
    for _ in range(20):
        ef = calculate_next_review(False, repetitions=0, ease_factor=ef,
                                   interval_days=0, now=NOW).ease_factor
    assert ef == MIN_EASE_FACTOR


def test_EFは上限を超えない():
    """常に正解し続けても復習間隔が発散しないこと"""
    ef = INITIAL_EASE_FACTOR
    for i in range(50):
        ef = calculate_next_review(True, repetitions=i, ease_factor=ef,
                                   interval_days=1, now=NOW).ease_factor
    assert ef == MAX_EASE_FACTOR
