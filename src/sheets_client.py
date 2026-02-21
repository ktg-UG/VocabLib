"""Google Sheets連携モジュール"""
import os
import random
from typing import List, Tuple, Optional
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .config import (
    GOOGLE_SHEET_ID,
    GOOGLE_CREDENTIALS_PATH,
    GOOGLE_TOKEN_PATH,
    GOOGLE_SHEET_RANGE
)

# Google Sheets APIのスコープ
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']


class SheetsClient:
    """Google Sheetsクライアント"""
    
    def __init__(self):
        self.service = None
        self.words_cache: List[Tuple[str, str]] = []
        
    def authenticate(self) -> bool:
        """Google Sheetsに認証"""
        creds = None
        
        # トークンファイルが存在する場合は読み込み
        if os.path.exists(GOOGLE_TOKEN_PATH):
            creds = Credentials.from_authorized_user_file(GOOGLE_TOKEN_PATH, SCOPES)
        
        # 認証情報が無効または存在しない場合
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(GOOGLE_CREDENTIALS_PATH):
                    print(f"エラー: credentials.jsonが見つかりません: {GOOGLE_CREDENTIALS_PATH}")
                    return False
                    
                flow = InstalledAppFlow.from_client_secrets_file(
                    GOOGLE_CREDENTIALS_PATH, SCOPES)
                creds = flow.run_local_server(port=0)
            
            # トークンを保存
            with open(GOOGLE_TOKEN_PATH, 'w') as token:
                token.write(creds.to_json())
        
        try:
            self.service = build('sheets', 'v4', credentials=creds)
            return True
        except Exception as e:
            print(f"エラー: Google Sheets APIの初期化に失敗しました: {e}")
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
                print("エラー: スプレッドシートにデータがありません")
                return False
            
            # データをキャッシュ（英単語, 日本語意味）
            self.words_cache = []
            for row in values:
                if len(row) >= 2:
                    english = row[0].strip()
                    japanese = row[1].strip()
                    if english and japanese:
                        self.words_cache.append((english, japanese))
            
            print(f"✓ {len(self.words_cache)}個の単語を読み込みました")
            return len(self.words_cache) > 0
            
        except HttpError as e:
            print(f"エラー: スプレッドシートの読み込みに失敗しました: {e}")
            return False
        except Exception as e:
            print(f"エラー: {e}")
            return False
    
    def get_random_word(self) -> Optional[Tuple[str, str]]:
        """ランダムに単語を1つ取得"""
        if not self.words_cache:
            if not self.fetch_words():
                return None
        
        if self.words_cache:
            return random.choice(self.words_cache)
        return None
    
    def get_random_words(self, count: int = 4) -> List[Tuple[str, str]]:
        """ランダムに複数の単語を取得（重複なし）"""
        if not self.words_cache:
            if not self.fetch_words():
                return []
        
        if len(self.words_cache) < count:
            return self.words_cache.copy()
        
        return random.sample(self.words_cache, count)
