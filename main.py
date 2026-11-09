"""Orange - entry point. Says hello, then: press Enter -> record -> print what you said."""
import os
import sys
from pathlib import Path

import yaml
from dotenv import load_dotenv

from orange import listen, speak, stt

# Make sure emoji status lines (🔴 / ⚪) print on any Windows terminal.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

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

    speak.init(config["speak"])
    print(f"Loading speech model '{config['stt']['model_size']}' (first run downloads it)...")
    # Load Whisper ONCE here, not on every sentence. Names help it spell them right.
    stt.init(config["stt"], names=[config["user"]["name"], config["assistant"]["name"]])

    speak.say("Hi, I'm Orange!")

    # Phase 3: press Enter -> record -> print what you said
    while True:
        if input("\nPress Enter to talk (q + Enter to quit): ").strip().lower() == "q":
            break
        audio = listen.record(config["audio"])
        if audio is None:
            continue  # Nothing heard; listen.record already said so
        print("Transcribing...")
        text = stt.transcribe(audio)
        print(f"You said: {text or '(could not make out any words)'}")
        # 'audio' is replaced next loop and never written to disk.


if __name__ == "__main__":
    main()
