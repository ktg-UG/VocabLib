"""3段フォールバックのテスト

偽のProviderを注入するため、ネットワークにもOllamaにも触らない。
"""
import time
from types import SimpleNamespace

from src.llm import client as client_module
from src.llm.client import LLMClient, WordInfo
from src.llm.gemini import GeminiProvider, _is_transient

GOOD_EXAMPLE = "He postponed the meeting. — 彼は会議を延期した。"
GOOD_JSON = '{"japanese": "延期する", "part_of_speech": "動詞"}'


class FakeProvider:
    """呼び出し回数を数えられる偽Provider"""

    def __init__(self, name, responses, available=True):
        self.name = name
        self._responses = list(responses)
        self._available = available
        self.calls = 0

    def is_available(self):
        return self._available

    def complete(self, prompt, timeout=None):
        self.calls += 1
        return self._responses.pop(0) if self._responses else None


# ── フォールバックの順序 ──────────────────────────────────────────────────

def test_1段目が成功したら2段目を呼ばない():
    first = FakeProvider("first", [GOOD_EXAMPLE])
    second = FakeProvider("second", [GOOD_EXAMPLE])

    result = LLMClient([first, second]).generate_example_sentence("postpone", "延期する")

    assert result == GOOD_EXAMPLE
    assert first.calls == 1
    assert second.calls == 0


def test_1段目が応答しなければ2段目に落ちる():
    first = FakeProvider("first", [None])
    second = FakeProvider("second", [GOOD_EXAMPLE])

    result = LLMClient([first, second]).generate_example_sentence("postpone", "延期する")

    assert result == GOOD_EXAMPLE
    assert second.calls == 1


def test_1段目の出力が不正な形式なら2段目に落ちる():
    """v1に無かった挙動。v1は同じLLMに再試行するだけで別手段に切り替わらなかった"""
    first = FakeProvider("first", ["区切りの無いただの文章です"])
    second = FakeProvider("second", [GOOD_EXAMPLE])

    result = LLMClient([first, second]).generate_example_sentence("postpone", "延期する")

    assert result == GOOD_EXAMPLE
    assert first.calls == 1
    assert second.calls == 1


def test_1段目の例文が対象単語を含まなければ2段目に落ちる():
    first = FakeProvider("first", ["The cat sleeps well. — 猫はよく眠る。"])
    second = FakeProvider("second", [GOOD_EXAMPLE])

    result = LLMClient([first, second]).generate_example_sentence("postpone", "延期する")

    assert result == GOOD_EXAMPLE


def test_利用不可のProviderは呼ばれない():
    """APIキー未設定のGeminiを飛ばすため"""
    unavailable = FakeProvider("gemini", [GOOD_EXAMPLE], available=False)
    fallback = FakeProvider("ollama", [GOOD_EXAMPLE])

    LLMClient([unavailable, fallback]).generate_example_sentence("postpone", "延期する")

    assert unavailable.calls == 0
    assert fallback.calls == 1


# ── 最終フォールバック ────────────────────────────────────────────────────

def test_全段失敗しても例文は必ず返る():
    """オフラインでもアプリが止まらないことの担保"""
    client = LLMClient([FakeProvider("a", [None]), FakeProvider("b", [None])])

    result = client.generate_example_sentence("postpone", "延期する")

    assert result == '"postpone" means "延期する"'


def test_Providerが1つも無くても例文は返る():
    assert LLMClient([]).generate_example_sentence("run", "走る") == '"run" means "走る"'


# ── オートフィル ──────────────────────────────────────────────────────────

def test_和訳と品詞を取得できる():
    client = LLMClient([FakeProvider("a", [GOOD_JSON])])

    assert client.lookup_word("postpone") == WordInfo(japanese="延期する", part_of_speech="動詞")


def test_品詞が無くても和訳だけ取得できる():
    client = LLMClient([FakeProvider("a", ['{"japanese": "延期する"}'])])

    info = client.lookup_word("postpone")
    assert info.japanese == "延期する"
    assert info.part_of_speech is None


def test_壊れたJSONなら次の段に落ちる():
    first = FakeProvider("first", ["JSONではない返事"])
    second = FakeProvider("second", [GOOD_JSON])

    assert LLMClient([first, second]).lookup_word("postpone").japanese == "延期する"
    assert second.calls == 1


def test_和訳が英語のまま返ってきたら次の段に落ちる():
    first = FakeProvider("first", ['{"japanese": "to postpone"}'])
    second = FakeProvider("second", [GOOD_JSON])

    assert LLMClient([first, second]).lookup_word("postpone").japanese == "延期する"


def test_全段失敗したらオートフィルはNoneを返す():
    """空欄で手入力してもらう。登録フローは止めない"""
    client = LLMClient([FakeProvider("a", [None]), FakeProvider("b", [None])])

    assert client.lookup_word("postpone") is None


def test_オートフィルは待ち時間の上限を超えたら次の段に進まない(monkeypatch):
    """オートフィルはUIを止めるので、段数ぶん待ち時間が積み上がってはいけない"""
    monkeypatch.setattr(client_module.config, "AUTOFILL_TIMEOUT_SECONDS", 0.05)

    class Slow:
        name = "slow"

        def is_available(self):
            return True

        def complete(self, prompt, timeout=None):
            time.sleep(0.1)
            return None

    second = FakeProvider("second", [GOOD_JSON])

    assert LLMClient([Slow(), second]).lookup_word("postpone") is None
    assert second.calls == 0


def test_可用性判定で例外が出てもクラッシュしない():
    class Broken:
        name = "broken"

        def is_available(self):
            raise RuntimeError("設定が壊れている")

        def complete(self, prompt, timeout=None):
            return GOOD_EXAMPLE

    healthy = FakeProvider("healthy", [GOOD_EXAMPLE])

    result = LLMClient([Broken(), healthy]).generate_example_sentence("postpone", "延期する")

    assert result == GOOD_EXAMPLE


# ── Gemini の一時エラーへのリトライ ────────────────────────────────────────

class _FlakyClient:
    """指定回数だけ例外を投げ、その後は成功する偽のgoogle-genaiクライアント"""

    def __init__(self, failures, error):
        self.failures = failures
        self.error = error
        self.calls = 0
        self.models = self

    def generate_content(self, **kwargs):
        self.calls += 1
        if self.calls <= self.failures:
            raise self.error
        return SimpleNamespace(text="  こんにちは  ")


def _provider_with(monkeypatch, fake):
    """GeminiProvider にクライアントを差し込む（ネットワークに触らない）"""
    provider = GeminiProvider(api_key="dummy", timeout=10.0)
    monkeypatch.setattr(provider, "_client_for", lambda seconds: fake)
    monkeypatch.setattr("src.llm.gemini.time.sleep", lambda _: None)
    return provider


def test_混雑503は再試行して成功する(monkeypatch):
    """503は待たずに即返り、次の呼び出しは通ることが多い。
    1回で2段目に落とすと「課金しているのにGeminiが機能しない」状態になる"""
    fake = _FlakyClient(1, RuntimeError("503 UNAVAILABLE. high demand"))

    result = _provider_with(monkeypatch, fake).complete("prompt")

    assert result == "こんにちは"
    assert fake.calls == 2


def test_再試行しても駄目なら諦めて次の段へ渡す(monkeypatch):
    """粘りすぎると「LLMが遅い」問題に化けるので、リトライは1回だけ"""
    fake = _FlakyClient(99, RuntimeError("503 UNAVAILABLE"))

    result = _provider_with(monkeypatch, fake).complete("prompt")

    assert result is None
    assert fake.calls == 2


def test_一時的でないエラーは再試行しない(monkeypatch):
    """400（デッドラインが短すぎる等）は投げ直しても同じ結果にしかならない"""
    fake = _FlakyClient(99, RuntimeError("400 INVALID_ARGUMENT"))

    result = _provider_with(monkeypatch, fake).complete("prompt")

    assert result is None
    assert fake.calls == 1


def test_一時エラーの判定はメッセージで行う():
    """google-genai の例外型はバージョンで変わるため型では判定しない"""
    assert _is_transient(RuntimeError("503 UNAVAILABLE"))
    assert _is_transient(RuntimeError("429 RESOURCE_EXHAUSTED"))
    assert _is_transient(RuntimeError("500 INTERNAL"))
    assert not _is_transient(RuntimeError("400 INVALID_ARGUMENT"))
    assert not _is_transient(RuntimeError("404 NOT_FOUND"))
