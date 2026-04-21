"""Test Yandex Cloud AI API connectivity.

Usage:
  python test_api.py                  # default model
  python test_api.py deepseek         # deepseek-v32/latest
  python test_api.py gpt120           # gpt-oss-120b/latest
  python test_api.py gpt20            # gpt-oss-20b/latest
  python test_api.py qwen             # qwen3.5-35b-a3b-fp8/latest
  python test_api.py all              # test all models
"""
import os
import sys
from pathlib import Path

# Load .env from project root
env_path = Path(__file__).resolve().parents[1] / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip())

import openai

__test__ = False

FOLDER = "b1gste4lfr39is20f5r8"
API_KEY = os.environ["YANDEX_AI_API_KEY"]

MODELS = {
    "deepseek": "deepseek-v32/latest",
    "gpt120":   "gpt-oss-120b/latest",
    "gpt20":    "gpt-oss-20b/latest",
    "qwen":     "qwen3.5-35b-a3b-fp8/latest",
}
DEFAULT_MODEL = "qwen"

client = openai.OpenAI(
    api_key=API_KEY,
    base_url="https://ai.api.cloud.yandex.net/v1",
)


def test_model(alias: str) -> bool:
    model = MODELS[alias]
    print(f"\n[{alias}] {model}")
    response = client.chat.completions.create(
        model=f"gpt://{FOLDER}/{model}",
        temperature=0.3,
        messages=[{"role": "user", "content": "Say 'API OK' and nothing else."}],
        max_tokens=500,
    )
    msg = response.choices[0].message
    text = msg.content
    reasoning = getattr(msg, "reasoning_content", None)

    if text:
        print(f"  Response: {text.strip()}")
        print("  PASSED")
        return True
    elif reasoning:
        print(f"  Reasoning only (finish_reason={response.choices[0].finish_reason}): {reasoning[:80]}...")
        print("  FAILED: increase max_tokens")
        return False
    else:
        print("  FAILED: empty response")
        return False


def main() -> None:
    arg = sys.argv[1].lower() if len(sys.argv) > 1 else DEFAULT_MODEL

    if arg == "all":
        results = {alias: test_model(alias) for alias in MODELS}
        print("\n--- Summary ---")
        for alias, ok in results.items():
            print(f"  {alias:10} {'PASSED' if ok else 'FAILED'}")
    elif arg in MODELS:
        test_model(arg)
    else:
        print(f"Unknown model '{arg}'. Available: {', '.join(MODELS)} | all")
        sys.exit(1)


if __name__ == "__main__":
    main()
