"""SM-2 Spaced Repetition アルゴリズムのユニットテスト"""
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

# テスト用にconfig値を固定
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# config をモックしてからインポート
with patch.dict(os.environ, {
    'INITIAL_EASE_FACTOR': '2.5',
    'INCORRECT_RETRY_MINUTES': '5',
    'GOOGLE_SHEET_ID': 'test',
    'GOOGLE_CREDENTIALS_PATH': '/tmp/test_creds.json',
}):
    from src.spaced_repetition import calculate_next_review, select_word


JST = timezone(timedelta(hours=9))


class TestCalculateNextReview:
    """calculate_next_review のテスト"""

    def test_first_correct(self):
        """初回正解 → interval=1日, repetitions=1"""
        next_review, ef, interval, reps = calculate_next_review(
            is_correct=True, repetitions=0, ease_factor=2.5, interval_days=0,
        )
        assert interval == 1
        assert reps == 1
        assert ef >= 1.3  # EFは最低1.3

    def test_second_correct(self):
        """2回目正解 → interval=6日, repetitions=2"""
        _, _, interval, reps = calculate_next_review(
            is_correct=True, repetitions=1, ease_factor=2.5, interval_days=1,
        )
        assert interval == 6
        assert reps == 2

    def test_third_correct(self):
        """3回目正解 → interval=6*2.5=15日"""
        _, _, interval, reps = calculate_next_review(
            is_correct=True, repetitions=2, ease_factor=2.5, interval_days=6,
        )
        assert interval == pytest.approx(15.0)
        assert reps == 3

    def test_incorrect_resets_repetitions(self):
        """不正解 → repetitions=0, interval=INCORRECT_RETRY_MINUTES/1440"""
        _, _, interval, reps = calculate_next_review(
            is_correct=False, repetitions=3, ease_factor=2.5, interval_days=15,
        )
        assert reps == 0
        assert interval == pytest.approx(5 / (60 * 24))  # 5分を日数に変換

    def test_ease_factor_minimum(self):
        """EFは1.3未満にならない"""
        # 連続不正解でEFを下げる
        ef = 1.3
        for _ in range(10):
            _, ef, _, _ = calculate_next_review(
                is_correct=False, repetitions=0, ease_factor=ef, interval_days=0,
            )
        assert ef >= 1.3

    def test_ease_factor_increases_on_correct(self):
        """正解時にEFが上がる（quality=4）"""
        _, new_ef, _, _ = calculate_next_review(
            is_correct=True, repetitions=0, ease_factor=2.5, interval_days=0,
        )
        # quality=4: EF += 0.1 - (5-4)*(0.08 + (5-4)*0.02) = 0.1 - 0.1 = 0
        # So EF stays the same (2.5)
        assert new_ef == pytest.approx(2.5)

    def test_next_review_is_in_future(self):
        """next_review は現在時刻より後"""
        now = datetime.now(JST)
        next_review, _, _, _ = calculate_next_review(
            is_correct=True, repetitions=0, ease_factor=2.5, interval_days=0,
        )
        assert next_review > now


class TestSelectWord:
    """select_word のテスト"""

    def test_overdue_word_priority(self):
        """優先度1: 期限切れの単語を優先"""
        now = datetime.now(JST)
        words = [("apple", "りんご"), ("book", "本"), ("cat", "猫")]
        records = {
            ("apple", "りんご"): {"next_review": now - timedelta(days=1)},  # 期限切れ
            ("book", "本"): {"next_review": now + timedelta(days=1)},  # 期限内
        }
        result = select_word(records, words)
        assert result == ("apple", "りんご")

    def test_unlearned_word_priority(self):
        """優先度2: 未学習の単語を選択"""
        now = datetime.now(JST)
        words = [("apple", "りんご"), ("book", "本"), ("cat", "猫")]
        records = {
            ("apple", "りんご"): {"next_review": now + timedelta(days=1)},
            ("book", "本"): {"next_review": now + timedelta(days=2)},
        }
        # "cat" は学習記録に未登録 → 未学習
        result = select_word(records, words)
        assert result == ("cat", "猫")

    def test_nearest_upcoming_priority(self):
        """優先度3: 全て学習済みで期限前 → next_review最短"""
        now = datetime.now(JST)
        words = [("apple", "りんご"), ("book", "本")]
        records = {
            ("apple", "りんご"): {"next_review": now + timedelta(days=3)},
            ("book", "本"): {"next_review": now + timedelta(days=1)},
        }
        result = select_word(records, words)
        assert result == ("book", "本")

    def test_oldest_overdue_first(self):
        """期限切れが複数ある場合、最も古いものを選択"""
        now = datetime.now(JST)
        words = [("apple", "りんご"), ("book", "本")]
        records = {
            ("apple", "りんご"): {"next_review": now - timedelta(days=1)},
            ("book", "本"): {"next_review": now - timedelta(days=3)},  # より古い
        }
        result = select_word(records, words)
        assert result == ("book", "本")

    def test_empty_words_returns_none(self):
        """空の単語リスト → None"""
        result = select_word({}, [])
        assert result is None

    def test_all_unlearned(self):
        """全て未学習 → ランダムに1つ選択"""
        words = [("apple", "りんご"), ("book", "本")]
        result = select_word({}, words)
        assert result in words
