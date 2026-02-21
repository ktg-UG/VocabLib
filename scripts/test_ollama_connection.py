#!/usr/bin/env python3
"""簡単な Ollama 接続テストスクリプト

Usage:
  python scripts/test_ollama_connection.py
"""
import json
import sys
import requests

HOST = "http://localhost:11434"

def check_info():
    for ep in ("/api/info", "/api/models", "/api/tags"):
        try:
            r = requests.get(HOST + ep, timeout=3)
            print(ep, r.status_code)
            if r.status_code == 200:
                try:
                    print(json.dumps(r.json(), indent=2, ensure_ascii=False))
                except Exception:
                    print(r.text[:400])
                return True
        except Exception as e:
            print(f"{ep} error: {e}")
    return False

def generate_sample():
    payload = {
        "model": "qwen2.5:1.5b",
        "prompt": "英単語: apple\n4択問題をJSONで出してください",
        "stream": False,
    }
    try:
        r = requests.post(HOST + "/api/generate", json=payload, timeout=10)
        print("POST /api/generate ->", r.status_code)
        try:
            print(json.dumps(r.json(), indent=2, ensure_ascii=False))
        except Exception:
            print(r.text[:1000])
    except Exception as e:
        print("generate error:", e)

def main():
    ok = check_info()
    if not ok:
        print("Ollama server not reachable on localhost:11434")
        sys.exit(2)
    print("Ollama seems reachable — trying a sample generate...")
    generate_sample()

if __name__ == '__main__':
    main()
