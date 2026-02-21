"""Ollama連携モジュール"""
import json
import random
import re
from typing import List, Tuple, Optional
import requests
import time
import logging
import concurrent.futures

from .config import OLLAMA_HOST, OLLAMA_MODEL


_LOGGER = logging.getLogger(__name__)


class OllamaClient:
    """Ollamaクライアント"""

    def __init__(self):
        self.host = OLLAMA_HOST
        self.model = OLLAMA_MODEL

    def generate_quiz(
        self,
        correct_word: str,
        correct_meaning: str,
        other_words: List[Tuple[str, str]]
    ) -> Optional[dict]:
        """
        4択クイズを生成
        
        Args:
            correct_word: 正解の英単語
            correct_meaning: 正解の日本語意味
            other_words: 他の選択肢用の単語リスト [(英単語, 日本語), ...]
            
        Returns:
            {
                'question': 英単語,
                'choices': [選択肢1, 選択肢2, 選択肢3, 選択肢4],
                'correct_index': 正解のインデックス (0-3),
                'correct_answer': 正解の意味
            }
        """
        # シンプルな4択問題を生成（Ollamaを使わずに）
        # より高度な問題を作りたい場合はOllamaを使用
        
        # 選択肢を作成（重複を抽出するためにセットを使用）
        choices = [correct_meaning]
        used_meanings = {correct_meaning}
        
        # 他の選択肢を追加（最大3つ、重複は除外）
        for word, meaning in other_words:
            if meaning not in used_meanings and len(choices) < 4:
                choices.append(meaning)
                used_meanings.add(meaning)
        
        # 4択に満たない場合は汎用的なダミーを追加
        dummy_count = 1
        while len(choices) < 4:
            choices.append(f"その他の意味 {dummy_count}")
            dummy_count += 1
        
        # シャッフルして正解のインデックスを記録
        correct_index = random.randint(0, 3)
        random.shuffle(choices)
        
        # 正解を正しい位置に配置
        choices[correct_index] = correct_meaning
        
        return {
            'question': correct_word,
            'choices': choices,
            'correct_index': correct_index,
            'correct_answer': correct_meaning
        }
    
    def generate_quiz_with_ollama(
        self,
        correct_word: str,
        correct_meaning: str,
        other_meanings: List[str]
    ) -> Optional[dict]:
        """
        Ollamaを使って問題文や選択肢を生成（高度な使用例）
        
        注: これは将来的な拡張用。現在はシンプルな方法を使用
        """
        prompt = f"""英単語「{correct_word}」の4択問題を作成してください。
正解（日本語訳）: {correct_meaning}
指示:
- 他の選択肢は必ず正解と同じ品詞（名詞/動詞/形容詞など）にしてください。
- 可能な限りTOEICで出やすい語（頻出語）を選んでください。
- 選択肢の例を必ず2〜3個含め、自然な日本語の短い語句で示してください。
例:
- 単語: "convention" 正解: "会議"（名詞） → 他の選択肢例: "会話", "単語"（どちらも名詞でTOEIC頻出）

他の選択肢候補: {', '.join(other_meanings)}

以下のJSON形式で回答してください（追加で`correct_answer`フィールドを返してください）:
{
    "question": "英単語",
    "choices": ["選択肢1", "選択肢2", "選択肢3", "選択肢4"],
    "correct_index": 正解のインデックス(0-3),
    "correct_answer": 正解の日本語訳
}
注意: 出力は必ず有効なJSONのみとし、コードブロックや余計な説明文を含めないでください。
"""

        try:
            response = requests.post(
                f"{self.host}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False
                },
                timeout=30,
            )

            if response.status_code != 200:
                _LOGGER.warning("Ollama generate status: %s %s", response.status_code, response.text)
                return None

            # Ollamaのレスポンス形式は変動するため、いくつかのパターンに対応
            try:
                result = response.json()
            except Exception:
                # JSONでなければ生テキストを解析して返す
                text = response.text.strip()
                try:
                    return json.loads(text)
                except Exception:
                    return {'question': correct_word, 'choices': [correct_meaning] + other_meanings[:3], 'correct_index': 0, 'correct_answer': correct_meaning}

            # 通常はresultに'output'や'response'が含まれる
            # 試行的にtext要素を探す
            if isinstance(result, dict):
                # Ollama server の新しい形式
                # output -> list -> content -> list -> text
                out = None
                try:
                    for o in result.get('output', []) or []:
                        for c in o.get('content', []) or []:
                            if c.get('type') == 'output_text' and c.get('text'):
                                out = c.get('text')
                                break
                        if out:
                            break
                except Exception:
                    out = None

                if not out:
                    out = result.get('response') or result.get('text')

                if out:
                    # remove markdown code fences if present
                    out_clean = re.sub(r"^```[a-zA-Z0-9]*\n", "", out)
                    out_clean = re.sub(r"\n```$", "", out_clean)
                    # try to extract the first JSON object in the text
                    m = re.search(r"(\{(?:.|\n)*\})", out_clean)
                    json_text = m.group(1) if m else out_clean
                    try:
                        parsed = json.loads(json_text)
                        # normalize different response shapes into our internal format
                        if isinstance(parsed, dict):
                            # case: explicit choices list
                            if 'choices' in parsed and isinstance(parsed['choices'], list):
                                choices = parsed['choices'][:4]
                            else:
                                # case: choice1..choice4 keys
                                choices = []
                                for i in range(1, 5):
                                    c = parsed.get(f'choice{i}')
                                    if c:
                                        choices.append(c)
                                # fallback: try numbered keys as strings
                                if not choices:
                                    for i in range(1, 5):
                                        c = parsed.get(str(i))
                                        if c:
                                            choices.append(c)

                            # ensure length 4
                            while len(choices) < 4:
                                choices.append(f"その他の意味_auto_{len(choices)+1}")

                            # determine correct_index
                            correct_index = parsed.get('correct_index')
                            correct_answer = parsed.get('correct_answer') or parsed.get('answer')
                            if correct_index is None and correct_answer:
                                try:
                                    correct_index = choices.index(correct_answer)
                                except ValueError:
                                    correct_index = 0
                            if correct_index is None:
                                correct_index = 0

                            question_text = parsed.get('question') or correct_word
                            return {
                                'question': question_text,
                                'choices': choices,
                                'correct_index': int(correct_index),
                                'correct_answer': correct_answer or choices[int(correct_index)]
                            }
                    except Exception:
                        # 期待するJSONが返らない場合は、生テキストから最低限の構造を返す
                        return {'question': correct_word, 'choices': [correct_meaning] + other_meanings[:3], 'correct_index': 0, 'correct_answer': correct_meaning}

        except Exception as e:
            _LOGGER.exception("Ollama APIエラー: %s", e)

        return None
    
    def check_connection(self) -> bool:
        """Ollamaサーバーへの接続を確認"""
        try:
            # いくつかのエンドポイントを試す
            for ep in ("/api/tags", "/api/models", "/api/info"):
                try:
                    response = requests.get(f"{self.host}{ep}", timeout=5)
                    if response.status_code == 200:
                        return True
                except Exception:
                    continue
            return False
        except Exception as e:
            _LOGGER.exception("Ollama接続エラー: %s", e)
            return False

    def batch_generate_quizzes(self, items: List[dict], max_workers: int = 4, retries: int = 2) -> List[Optional[dict]]:
        """複数の生成タスクを並列で実行して結果を返す

        items: List of dicts with keys: correct_word, correct_meaning, other_meanings
        """
        results = [None] * len(items)

        def _work(index, item):
            attempt = 0
            while attempt <= retries:
                try:
                    return self.generate_quiz_with_ollama(
                        item.get('correct_word'),
                        item.get('correct_meaning'),
                        item.get('other_meanings', []),
                    )
                except Exception:
                    attempt += 1
                    time.sleep(0.5 * attempt)
            return None

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as exc:
            futures = {exc.submit(_work, idx, itm): idx for idx, itm in enumerate(items)}
            for fut in concurrent.futures.as_completed(futures):
                idx = futures[fut]
                try:
                    results[idx] = fut.result()
                except Exception:
                    results[idx] = None

        return results
