"""
Pull a model into Ollama.

Run after the Ollama container is up. Defaults to llama3.1:8b if no
model name is provided. This script belongs to the scripts layer and
is not imported by application code.

Usage:
    uv run python scripts/pull_model.py
    uv run python scripts/pull_model.py qwen2.5:32b
"""

import os
import sys

# Ensure src/ is importable when running from the project root.
sys.path.insert(0, ".")

import httpx

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
MODEL = sys.argv[1] if len(sys.argv) > 1 else "llama3.1:8b"


def main() -> None:
    """Pull a model from the Ollama registry."""
    print(f"Pulling {MODEL} from {OLLAMA_HOST}...")
    print("This may take several minutes for large models.\n")

    try:
        with httpx.Client(timeout=600.0) as client:
            response = client.post(
                f"{OLLAMA_HOST}/api/pull",
                json={"name": MODEL},
            )
            response.raise_for_status()
        print(f"Successfully pulled {MODEL}")
    except httpx.HTTPError as exc:
        print(f"Failed to pull {MODEL}: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
