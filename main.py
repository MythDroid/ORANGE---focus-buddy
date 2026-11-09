"""Orange - entry point. Phase 1: just checks that setup works."""
import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

# Path(__file__).parent = the folder this file is in, so it works from any directory
# and on any OS (Windows or Raspberry Pi).
ROOT = Path(__file__).parent


def load_config():
    """Read config.yaml into a normal Python dict."""
    with open(ROOT / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main():
    config = load_config()
    load_dotenv(ROOT / ".env")  # Copies values from .env into environment variables

    # Only check IF the key exists. Never print the key itself (privacy rule).
    has_key = bool(os.getenv("ANTHROPIC_API_KEY"))
    print(f"Config loaded: assistant name = {config['assistant']['name']}")
    print(f"API key found in .env: {'yes' if has_key else 'no (fine for now)'}")
    print("Orange setup OK")


if __name__ == "__main__":
    main()
