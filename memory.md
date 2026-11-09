# Orange - Project Decisions

This file is the source of truth for big decisions. Update it when a decision changes.

## Roadmap

| Version | What it is |
|---------|------------|
| v1.0 | Voice assistant on the Windows laptop (current) |
| v1.1 | Orange character on screen with expressions |
| v1.2 | Character moves around the screen |
| v1.3 | Phone app |
| v2.0 | Physical desk robot (Raspberry Pi 5, orange body) |
| v3.0 | Walking robot |

## Platform

- v1.0 runs on Windows (webcam, mic, speakers); later it moves to a Raspberry Pi 5.
- Code must stay portable to Linux and modular (each part swappable).
- `.gitattributes` forces LF line endings so files match on Windows and the Pi.

## AI providers (free by default)

- I'm a student and can't pay for APIs, so defaults must be free.
- **Chat:** free Gemini API (`GEMINI_API_KEY`).
- **Camera questions:** local Ollama vision model, so photos never leave the laptop.
- Providers are switchable in `config.yaml`: `gemini`, `groq`, `ollama`, `claude`.
- Keys in `.env`: `GEMINI_API_KEY`, `GROQ_API_KEY`, `ANTHROPIC_API_KEY` (only the one you use).
- Implemented with **LiteLLM in Phase 5** (ask before installing).
- **Phase 5 TODO:** check which Gemini Flash models are on the free tier for a NEW project.
  `gemini-2.5-flash` may only be available to older users.
- **Phase 5 TODO:** `main.py` still only checks `ANTHROPIC_API_KEY`, and `requirements.txt`
  still lists `anthropic`. Update both.

## Voice

- Text-to-speech: pyttsx3 now; Piper later (swap by changing `speak.engine` in config).
- Wake word: openWakeWord built-in `hey_jarvis` for now; custom "hey orange" later.

## Privacy rules (always)

- API keys only in `.env`, never in code, logs or git.
- Photos and audio stay in memory only, never saved to disk.
- Print a status line whenever the mic records or the camera is on.

## Planned later features (not built yet)

- Users can set Orange's name, tone and personality.
- Users can see and delete Orange's memory.
