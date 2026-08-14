from src.ollama_client import OllamaClient

if __name__ == "__main__":
    client = OllamaClient()
    # テストデータ: convention（名詞）
    correct_word = "convention"
    correct_meaning = "会議"
    other_meanings = ["会話", "単語", "規則"]  # すべて名詞でTOEIC頻出
    result = client.generate_quiz_with_ollama(correct_word, correct_meaning, other_meanings)
    print("Ollama response:", result)
