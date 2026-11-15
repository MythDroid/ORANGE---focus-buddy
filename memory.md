# Orange - Project Decisions

This file is the source of truth for big decisions. Update it when a decision changes.
The day-by-day list of changes is in CHANGELOG.md.

## What Orange is (decided Nov 2026)

- An **on-screen study-buddy pet**. Not a physical robot (the earlier desk-robot roadmap is dropped).
- A **companion, not a tutor**. She studies with me; she does not answer study questions.
- Character: **"Soft Bot"**, a squishy orange robot with a dark screen face. Not a fruit.
- She stays the same: no growing, no levels, nothing to buy.
- For me only for now. One laptop, one user.

## How she is built

- **Face:** drawn in SVG + CSS (no image files) inside a transparent, frameless, always-on-top
  PyQt6 window. PyQt6 was chosen over pywebview because transparent, clickable windows are well
  proven there on Windows.
- **Logic first, window second:** `study_mode.py` (the Buddy), `commands.py` and `store.py`
  have no window code, so they can be tested alone.
- **Memory:** SQLite, one file, `data/orange.db`. No Docker, no server. `store.py` is the only
  file that touches the database, so a cloud database could replace it later.
- **Understanding sentences, in this order:** phrases I taught her -> built-in rules -> the
  local brain. The brain can only choose one of her own actions.
- **Brain:** Ollama on the laptop, model `qwen3.5:2b` (fits a 4 GB graphics card, about 3 s per
  answer). No cloud API, no key.
- **Voice in:** faster-whisper `base.en` on CPU. "Hey Orange" is done with speech-to-text on the
  first 2.5 seconds of anything she hears (no separate wake-word model). "Hey Jarvis" is dropped.
- **Ways to talk:** "Hey Orange", double-click, Ctrl+Space. A single click is a poke.
- **Replies:** speech bubble. Speaking out loud is not built yet.
- **Distraction watch:** only during a session; reads the front window's TITLE only; hides
  (minimises) the window and never closes it; "this is for study" teaches her.

## Privacy rules (always)

- Nothing leaves the laptop. No cloud model, no telemetry.
- Audio and photos stay in memory only, never saved to disk.
- Window titles are not saved, except pages I mark as "for study".
- `data/` and `.env` are in `.gitignore`.
- Print a status line whenever the mic is on.

## Platform

- Windows 10/11, Python 3.11. The watch and the shortcut are Windows-only.
- `.gitattributes` forces LF line endings.

## Old parts still in the folder (not used by `pet.py`)

- `main.py`, `orange/wake.py`, the `wake:` block in `config.yaml`: the first voice-only loop
  with the "Hey Jarvis" wake word.
- `orange/vision.py`: empty placeholder for a camera feature that is on hold.
- `orange/speak.py`: text-to-speech, kept for when she talks out loud.

## Planned later

- Activity buddy (she does what I do: paints, types, stretches).
- Teach mode (I explain a topic; she asks me to teach it again later).
- Idle life (bored fidgets, sleeping cap at night), charging instead of food.
- A desktop shortcut to start her without a terminal.
