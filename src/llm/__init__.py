"""LLM連携（例文生成・単語オートフィル）

Gemini → ローカルLLM（Ollama） → ローカル生成 の3段フォールバック。
UIには依存しない。
"""
from .client import LLMClient, WordInfo

__all__ = ["LLMClient", "WordInfo"]
