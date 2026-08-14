"""Google Sheets連携モジュール"""
import logging
import os
import random
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .config import (
    GOOGLE_SHEET_ID,
    GOOGLE_CREDENTIALS_PATH,
    GOOGLE_TOKEN_PATH,
    GOOGLE_SHEET_RANGE,
    LEARNING_SHEET_NAME,
    INITIAL_EASE_FACTOR,
)

# Google Sheets APIのスコープ
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

_LOGGER = logging.getLogger(__name__)

# タイムゾーン（日本時間）
JST = timezone(timedelta(hours=9))

# 学習記録シートのヘッダー
LEARNING_HEADERS = [
    "word", "meaning", "last_reviewed", "next_review",
    "ease_factor", "interval_days", "repetitions", "total_correct",
    "example_sentence",
]


class SheetsClient:
    """Google Sheetsクライアント"""

    def __init__(self):
        self.service = None
        self.words_cache: List[Tuple[str, str]] = []
        self.learning_records: Dict[Tuple[str, str], dict] = {}

    def authenticate(self) -> bool:
        """Google Sheetsに認証"""
        creds = None

        # トークンファイルが存在する場合は読み込み
        if os.path.exists(GOOGLE_TOKEN_PATH):
            creds = Credentials.from_authorized_user_file(GOOGLE_TOKEN_PATH, SCOPES)

        # 認証情報が無効または存在しない場合
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as e:
                    _LOGGER.warning("トークンのリフレッシュに失敗しました: %s", e)
                    creds = None
            if not creds or not creds.valid:
                if not os.path.exists(GOOGLE_CREDENTIALS_PATH):
                    _LOGGER.error("credentials.jsonが見つかりません: %s", GOOGLE_CREDENTIALS_PATH)
                    return False

                flow = InstalledAppFlow.from_client_secrets_file(
                    GOOGLE_CREDENTIALS_PATH, SCOPES)
                creds = flow.run_local_server(port=0)

            # トークンを保存
            try:
                with open(GOOGLE_TOKEN_PATH, 'w') as token:
                    token.write(creds.to_json())
            except OSError as e:
                _LOGGER.warning("token.jsonの書き込みに失敗しました: %s", e)

        try:
            self.service = build('sheets', 'v4', credentials=creds)
            return True
        except Exception as e:
            _LOGGER.exception("Google Sheets APIの初期化に失敗しました: %s", e)
            return False

    def fetch_words(self) -> bool:
        """スプレッドシートから単語を取得"""
        if not self.service:
            if not self.authenticate():
                return False

        try:
            sheet = self.service.spreadsheets()
            result = sheet.values().get(
                spreadsheetId=GOOGLE_SHEET_ID,
                range=GOOGLE_SHEET_RANGE
            ).execute()

            values = result.get('values', [])

            if not values:
                _LOGGER.error("スプレッドシートにデータがありません")
                return False

            # データをキャッシュ（英単語, 日本語意味）
            self.words_cache = []
            for row in values:
                if len(row) >= 2:
                    english = row[0].strip()
                    japanese = row[1].strip()
                    if english and japanese:
                        self.words_cache.append((english, japanese))

            _LOGGER.info("✓ %d個の単語を読み込みました", len(self.words_cache))
            return len(self.words_cache) > 0

        except HttpError as e:
            _LOGGER.error("スプレッドシートの読み込みに失敗しました (HTTP %s): %s", e.status_code, e)
            return False
        except Exception as e:
            _LOGGER.exception("スプレッドシートの読み込み中にエラーが発生しました: %s", e)
            return False

    # ── 学習記録シートの管理 ───────────────────────────────────────────────

    def ensure_learning_sheet_exists(self) -> bool:
        """「学習記録」シートが存在しない場合にヘッダー行付きで自動作成"""
        if not self.service:
            if not self.authenticate():
                return False

        try:
            # 既存シート一覧を取得
            spreadsheet = self.service.spreadsheets().get(
                spreadsheetId=GOOGLE_SHEET_ID
            ).execute()

            sheet_titles = [
                s['properties']['title']
                for s in spreadsheet.get('sheets', [])
            ]

            if LEARNING_SHEET_NAME in sheet_titles:
                _LOGGER.debug("学習記録シートは既に存在します")
                return True

            # シートを新規作成
            body = {
                'requests': [{
                    'addSheet': {
                        'properties': {
                            'title': LEARNING_SHEET_NAME,
                        }
                    }
                }]
            }
            self.service.spreadsheets().batchUpdate(
                spreadsheetId=GOOGLE_SHEET_ID,
                body=body,
            ).execute()

            # ヘッダー行を書き込み
            self.service.spreadsheets().values().update(
                spreadsheetId=GOOGLE_SHEET_ID,
                range=f"{LEARNING_SHEET_NAME}!A1",
                valueInputOption='RAW',
                body={'values': [LEARNING_HEADERS]},
            ).execute()

            _LOGGER.info("✓ 学習記録シートを作成しました")
            return True

        except Exception as e:
            _LOGGER.exception("学習記録シートの作成に失敗しました: %s", e)
            return False

    def fetch_learning_records(self) -> bool:
        """「学習記録」シートから全単語の学習データを取得"""
        if not self.service:
            if not self.authenticate():
                return False

        if not self.ensure_learning_sheet_exists():
            return False

        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=GOOGLE_SHEET_ID,
                range=f"{LEARNING_SHEET_NAME}!A:I",
            ).execute()

            values = result.get('values', [])
            self.learning_records = {}

            # ヘッダー行をスキップ
            for row in values[1:]:
                if len(row) < 2:
                    continue

                word = row[0].strip()
                meaning = row[1].strip()
                if not word or not meaning:
                    continue

                key = (word, meaning)
                record = {
                    'last_reviewed': row[2] if len(row) > 2 else '',
                    'next_review': None,
                    'ease_factor': INITIAL_EASE_FACTOR,
                    'interval_days': 0,
                    'repetitions': 0,
                    'total_correct': 0,
                }

                # next_review をパース
                if len(row) > 3 and row[3]:
                    try:
                        record['next_review'] = datetime.fromisoformat(row[3])
                    except ValueError:
                        record['next_review'] = None

                # 数値フィールドをパース
                if len(row) > 4 and row[4]:
                    try:
                        record['ease_factor'] = float(row[4])
                    except ValueError:
                        pass
                if len(row) > 5 and row[5]:
                    try:
                        record['interval_days'] = float(row[5])
                    except ValueError:
                        pass
                if len(row) > 6 and row[6]:
                    try:
                        record['repetitions'] = int(row[6])
                    except ValueError:
                        pass
                if len(row) > 7 and row[7]:
                    try:
                        record['total_correct'] = int(row[7])
                    except ValueError:
                        pass

                record['example_sentence'] = row[8].strip() if len(row) > 8 and row[8] else ''

                self.learning_records[key] = record

            _LOGGER.info("✓ %d件の学習記録を読み込みました", len(self.learning_records))
            return True

        except Exception as e:
            _LOGGER.exception("学習記録の読み込みに失敗しました: %s", e)
            return False

    def record_answer(self, word: str, meaning: str, is_correct: bool) -> bool:
        """正誤結果を学習記録シートに書き込み"""
        from .spaced_repetition import calculate_next_review

        if not self.service:
            if not self.authenticate():
                return False

        key = (word, meaning)
        record = self.learning_records.get(key, {
            'ease_factor': INITIAL_EASE_FACTOR,
            'interval_days': 0,
            'repetitions': 0,
            'total_correct': 0,
        })

        # SM-2で次回復習日を計算
        next_review, new_ef, new_interval, new_reps = calculate_next_review(
            is_correct=is_correct,
            repetitions=record['repetitions'],
            ease_factor=record['ease_factor'],
            interval_days=record['interval_days'],
        )

        now_str = datetime.now(JST).isoformat()
        total_correct = record['total_correct'] + (1 if is_correct else 0)

        new_row = [
            word,
            meaning,
            now_str,
            next_review.isoformat(),
            str(round(new_ef, 4)),
            str(round(new_interval, 4)),
            str(new_reps),
            str(total_correct),
        ]

        try:
            # 既存行を検索して更新／新規行を追加
            row_number = self._find_record_row(word, meaning)

            if row_number is not None:
                # 既存行を更新
                range_str = f"{LEARNING_SHEET_NAME}!A{row_number}:H{row_number}"
                self.service.spreadsheets().values().update(
                    spreadsheetId=GOOGLE_SHEET_ID,
                    range=range_str,
                    valueInputOption='RAW',
                    body={'values': [new_row]},
                ).execute()
            else:
                # 新規行を追加
                self.service.spreadsheets().values().append(
                    spreadsheetId=GOOGLE_SHEET_ID,
                    range=f"{LEARNING_SHEET_NAME}!A:H",
                    valueInputOption='RAW',
                    insertDataOption='INSERT_ROWS',
                    body={'values': [new_row]},
                ).execute()

            # ローカルキャッシュも更新（既存の example_sentence は保持）
            self.learning_records[key] = {
                'last_reviewed': now_str,
                'next_review': next_review,
                'ease_factor': new_ef,
                'interval_days': new_interval,
                'repetitions': new_reps,
                'total_correct': total_correct,
                'example_sentence': record.get('example_sentence', ''),
            }

            _LOGGER.info(
                "✓ 学習記録を更新: %s (%s) - %s, 次回: %s",
                word, meaning,
                "正解" if is_correct else "不正解",
                next_review.strftime("%Y-%m-%d %H:%M"),
            )
            return True

        except Exception as e:
            _LOGGER.exception("学習記録の書き込みに失敗しました: %s", e)
            return False

    def _find_record_row(self, word: str, meaning: str) -> Optional[int]:
        """学習記録シートで word+meaning が一致する行番号を返す（1-indexed）"""
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=GOOGLE_SHEET_ID,
                range=f"{LEARNING_SHEET_NAME}!A:B",
            ).execute()

            values = result.get('values', [])
            for idx, row in enumerate(values):
                if idx == 0:  # ヘッダースキップ
                    continue
                if len(row) >= 2 and row[0].strip() == word and row[1].strip() == meaning:
                    return idx + 1  # 1-indexed

            return None

        except Exception as e:
            _LOGGER.warning("学習記録の検索に失敗しました: %s", e)
            return None

    # ── 例文の管理 ─────────────────────────────────────────────────────

    def get_example_sentence(self, word: str, meaning: str) -> str:
        """キャッシュから例文を取得。未生成なら空文字を返す"""
        key = (word, meaning)
        record = self.learning_records.get(key, {})
        return record.get('example_sentence', '')

    def save_example_sentence(self, word: str, meaning: str, sentence: str) -> bool:
        """例文を学習記録シート I列に保存（A:H列は変更しない）"""
        if not self.service:
            if not self.authenticate():
                return False

        key = (word, meaning)

        # ローカルキャッシュを更新
        if key in self.learning_records:
            self.learning_records[key]['example_sentence'] = sentence

        try:
            row_number = self._find_record_row(word, meaning)
            if row_number is None:
                _LOGGER.warning("例文保存: 学習記録が見つかりません: %s (%s)", word, meaning)
                return False

            self.service.spreadsheets().values().update(
                spreadsheetId=GOOGLE_SHEET_ID,
                range=f"{LEARNING_SHEET_NAME}!I{row_number}",
                valueInputOption='RAW',
                body={'values': [[sentence]]},
            ).execute()

            _LOGGER.info("✓ 例文を保存: %s (%s)", word, meaning)
            return True

        except Exception as e:
            _LOGGER.exception("例文の保存に失敗しました: %s", e)
            return False

    # ── 出題単語の選択 ────────────────────────────────────────────────────

    def get_next_word(self) -> Optional[Tuple[str, str]]:
        """忘却曲線に基づいて次に出題する単語を取得"""
        from .spaced_repetition import select_word

        if not self.words_cache:
            if not self.fetch_words():
                return None

        # 学習記録を取得（初回またはキャッシュが空の場合）
        if not self.learning_records:
            self.fetch_learning_records()

        return select_word(self.learning_records, self.words_cache)

    def get_random_word(self) -> Optional[Tuple[str, str]]:
        """ランダムに単語を1つ取得（後方互換用）"""
        if not self.words_cache:
            if not self.fetch_words():
                return None

        if self.words_cache:
            return random.choice(self.words_cache)
        return None

    def get_random_words(self, count: int = 4, exclude: Optional[str] = None) -> List[Tuple[str, str]]:
        """ランダムに複数の単語を取得（重複なし）

        Args:
            count: 取得する単語数
            exclude: この英単語を候補から除外する（正解単語の混入防止）
        """
        if not self.words_cache:
            if not self.fetch_words():
                return []

        pool = [w for w in self.words_cache if w[0] != exclude] if exclude else self.words_cache

        if len(pool) < count:
            return pool.copy()

        return random.sample(pool, count)
