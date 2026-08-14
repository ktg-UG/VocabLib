"""クイズ生成モジュール

現在はローカルでシャッフルして4択問題を生成する。
Ollamaを使った高度な問題生成に切り替えたい場合は、generate_quiz() を
generate_quiz_with_ollama() に差し替えること（要 ollama パッケージ）。
"""
import json
import random
import re
import logging
import requests
from typing import List, Optional, Tuple

from .config import OLLAMA_HOST, OLLAMA_MODEL

_LOGGER = logging.getLogger(__name__)


class OllamaClient:
    """クイズ生成クライアント（現在はローカル生成。Ollama対応は generate_quiz_with_ollama 参照）"""

    def __init__(self):
        self.host = OLLAMA_HOST
        self.model = OLLAMA_MODEL

    def generate_quiz(
        self,
        correct_word: str,
        correct_meaning: str,
        other_words: List[Tuple[str, str]]
    ) -> Optional[dict]:
        """4択クイズを生成（ローカル処理）

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
        # 不正解の選択肢を収集（重複を除外、正解は含めない）
        distractors: list = []
        used_meanings = {correct_meaning}

        for word, meaning in other_words:
            if meaning not in used_meanings and len(distractors) < 3:
                distractors.append(meaning)
                used_meanings.add(meaning)

        # 3択に満たない場合は汎用的なダミーを追加
        dummy_count = 1
        while len(distractors) < 3:
            distractors.append(f"その他の意味 {dummy_count}")
            dummy_count += 1

        # distractors のみシャッフルし、正解を後から指定位置に insert
        random.shuffle(distractors)
        correct_index = random.randint(0, len(distractors))
        choices = distractors[:]
        choices.insert(correct_index, correct_meaning)

        return {
            'question': correct_word,
            'choices': choices,
            'correct_index': correct_index,
            'correct_answer': correct_meaning
        }

    def generate_example_sentence(self, word: str, meaning: str) -> Optional[str]:
        """単語を必ず含む短い例文を Ollama で生成する。

        生成文に対象単語が含まれない場合（無関係な文が出た場合）は最大3回まで
        再生成し、それでも失敗すれば None を返す（呼び出し側でフォールバック）。

        Returns:
            "English sentence — 日本語訳" 形式の文字列。失敗時は None。
        """
        prompt = f"""英単語「{word}」（意味: {meaning}）を使った、短くて記憶に残る英語の例文を1つ作ってください。

【必須ルール】
- 例文には必ず「{word}」を含めること（活用形・語形変化は可）
- 5〜8語程度の短い文にすること
- 具体的な情景が浮かぶ、覚えやすい内容にすること
- 和訳は必ず自然な**日本語**で書くこと（中国語は絶対に使わない）

出力は次の1行だけ。番号・説明・引用符は不要:
英語の例文 — 日本語訳

例: Cats abandon their owners daily. — 猫は毎日飼い主を見捨てる。
例: He postponed the meeting again. — 彼はまた会議を延期した。"""

        for attempt in range(3):
            try:
                response = requests.post(
                    f"{self.host}/api/generate",
                    json={"model": self.model, "prompt": prompt, "stream": False},
                    timeout=30,
                )

                if response.status_code != 200:
                    _LOGGER.warning("Ollama 例文生成 status: %s", response.status_code)
                    continue

                result = response.json()
                out = result.get('response') or result.get('text')
                if not out:
                    continue

                sentence = self._extract_example_line(out)
                if sentence and self._sentence_uses_word(sentence, word):
                    return sentence

                _LOGGER.debug(
                    "例文が単語「%s」を含まず再生成 (%d回目): %r",
                    word, attempt + 1, sentence,
                )

            except Exception as e:
                _LOGGER.warning("Ollama 例文生成エラー: %s", e)
                return None

        _LOGGER.warning("例文生成: 単語「%s」を含む文を生成できませんでした", word)
        return None

    @staticmethod
    def _extract_example_line(out: str) -> Optional[str]:
        """LLM出力から「英語 — 和訳」形式の行を1つ抽出し、区切りを正規化する。"""
        for raw in out.strip().splitlines():
            line = raw.strip()
            if not line or line.startswith('```'):
                continue
            # 先頭の「例:」「1.」「- 」等のマーカーを除去
            line = re.sub(r'^\s*(例[:：]|[-*・]|\d+[.)])\s*', '', line).strip()
            if '—' in line or '–' in line:
                # 表示用に区切りを " — " へ正規化
                return re.sub(r'\s*[—–]\s*', ' — ', line, count=1)
            if ' - ' in line:
                return line.replace(' - ', ' — ', 1)
        return None

    @staticmethod
    def _sentence_uses_word(sentence: str, word: str) -> bool:
        """例文の英語部分が対象単語を含むか検証する（活用形・語形変化を許容）。"""
        english = re.split(r'—|–| - ', sentence, maxsplit=1)[0].lower()
        tokens = re.findall(r'[a-z]+', word.lower())
        # 意味を持つ語（4文字以上）を優先。無ければ全トークンで判定
        significant = [t for t in tokens if len(t) >= 4] or tokens
        for tok in significant:
            stem = tok[:max(4, len(tok) - 2)]  # 語尾変化（-s/-ed/-ing 等）を許容
            if stem in english:
                return True
        return False

    @staticmethod
    def fallback_example_sentence(word: str, meaning: str) -> str:
        """Ollama 非稼働時のフォールバック例文"""
        return f'"{word}" means "{meaning}"'

    def generate_quiz_with_ollama(
        self,
        correct_word: str,
        correct_meaning: str,
        other_meanings: List[str]
    ) -> Optional[dict]:
        """Ollamaを使って不正解選択肢を生成する（将来の拡張用）

        使い方: generate_quiz() の代わりに呼び出す。
        Ollamaサーバーが起動していない場合は None を返す。
        """
        prompt = f"""英単語またはフレーズ「{correct_word}」の日本語訳を問う4択問題の「不正解の選択肢（distractor）」を3つ生成してください。

正解の日本語訳: 「{correct_meaning}」

【最重要ルール】
1. 不正解の選択肢は必ず正解と**同じ表現形式**にすること
   - 正解が1語の名詞（例:「会議」）→ 不正解も1語の名詞
   - 正解が動詞句（例:「〜を延期する」）→ 不正解も同じ動詞句の形
2. 不正解は各々が独立した1つの日本語表現であること
3. 正解と意味が紛らわしいが、明確に異なる語/句を選ぶこと
4. 【禁止】正解「{correct_meaning}」の同義語・言い換え・ほぼ同じ意味になる語は絶対に選ばないこと
   （例: 正解が「生み出す」なら「作り出す」「産出する」はNG。意味が明確に区別できる語のみ）
5. 選択肢はすべて自然な**日本語**で書くこと（中国語は絶対に使わない）

以下のJSON形式で不正解の選択肢のみ返してください:
{{"distractors": ["不正解1", "不正解2", "不正解3"]}}

注意: 有効なJSONのみ出力し、コードブロック・説明文を含めないでください。
"""

        try:
            response = requests.post(
                f"{self.host}/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False},
                timeout=30,
            )

            if response.status_code != 200:
                _LOGGER.warning("Ollama generate status: %s", response.status_code)
                return None

            result = response.json()
            out = result.get('response') or result.get('text')
            if not out:
                return None

            # マークダウンコードフェンスを除去し、JSON を抽出
            out_clean = re.sub(r"^```[a-zA-Z0-9]*\n", "", out)
            out_clean = re.sub(r"\n```$", "", out_clean)
            m = re.search(r"(\{(?:.|\n)*\})", out_clean)
            json_text = m.group(1) if m else out_clean

            parsed = json.loads(json_text)
            raw_distractors = parsed.get('distractors', [])

            # 不正な選択肢を除外・重複排除
            distractors = []
            seen = {correct_meaning}
            for d in raw_distractors:
                d_str = str(d).strip()
                if d_str and d_str not in seen and 'その他の意味' not in d_str:
                    seen.add(d_str)
                    distractors.append(d_str)

            distractors = distractors[:3]

            # 不足分を other_meanings から補充
            for om in other_meanings:
                if len(distractors) >= 3:
                    break
                if om != correct_meaning and om not in distractors:
                    distractors.append(om)

            random.shuffle(distractors)
            correct_index = random.randint(0, len(distractors))
            choices = distractors[:]
            choices.insert(correct_index, correct_meaning)

            return {
                'question': correct_word,
                'choices': choices,
                'correct_index': correct_index,
                'correct_answer': correct_meaning
            }

        except Exception as e:
            _LOGGER.exception("Ollama APIエラー: %s", e)
            return None
