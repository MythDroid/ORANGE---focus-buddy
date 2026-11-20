"""Orange, the study buddy. This is the program you run every day:

    python pet.py

It joins three parts:
  orange/face        the window (what you see)
  orange/study_mode  the Buddy (decides what Orange does: sessions, breaks, reminders)
  orange/store       the memory (SQLite file in data/orange.db)
  orange/brain       the small local brain (Ollama), for sentences the rules don't know
  orange/watch       the distraction watch (looks at the title of the window in front)
  orange/voice       the ears ("Hey Orange" + speech-to-text), so you can talk instead of type
  orange/hotkey      the Ctrl+Space shortcut

Say "Hey Orange", double-click her, or press Ctrl+Space to talk. Click to poke her.
Drag to move. Right-click for the menu, including "Type to Orange".
"""
import faulthandler
import sys
import threading
import time
from pathlib import Path

import yaml

from orange import brain, face, store
from orange.study_mode import Buddy

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
faulthandler.enable()   # If the window part ever crashes hard, print where, instead of closing silently
ROOT = Path(__file__).parent


def main():
    with open(ROOT / "config.yaml", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    store.init()
    brain.init(config.get("brain", {}).get("understand"))   # The small local brain (Ollama). Optional.
    buddy = Buddy(store, default_name=config["user"]["name"], brain=brain)

    def heartbeat():
        """Runs beside the window. Twice a second it asks the Buddy: what now?"""
        time.sleep(1.5)                       # Let the window appear first
        face.say(buddy.start())
        brain.warm_up()                       # Load the model now, so the first sentence is quick
        shown_mood, shown_timer = None, None
        while True:
            update = buddy.tick()
            if update.says:
                face.say("\n".join(update.says), seconds=12)
            # Only talk to the window when something actually changed (saves CPU).
            if update.mood != shown_mood:
                shown_mood = update.mood
                face.set_mood(update.mood)
            if update.timer != shown_timer:
                shown_timer = update.timer
                face.set_timer(update.timer)
            time.sleep(0.5)

    # Orange's ears (optional). The import is inside the "if" because the speech models are
    # big: with voice switched off in config.yaml, Orange starts faster and needs no microphone.
    on_talk = None
    if config.get("voice", {}).get("enabled", False):
        from orange import voice
        threading.Thread(target=voice.run, args=(config, buddy, face), daemon=True).start()
        on_talk = voice.talk_now

    # Ctrl+Space from any app = the same as double-clicking Orange.
    if config.get("voice", {}).get("shortcut", True):
        from orange import hotkey
        hotkey.start(face.start_talking)

    # The distraction watch (optional, Windows only): spots a distracting window and hides it.
    if config.get("watch", {}).get("enabled", False):
        from orange import watch
        if watch.IS_WINDOWS:
            watcher = watch.Watcher(config["watch"], buddy, brain, store, face)
            buddy.on_allow = watcher.allow_current
            threading.Thread(target=watcher.run, daemon=True).start()
        else:
            print("The distraction watch only works on Windows, so it is off.")
    else:
        print("The distraction watch is switched off in config.yaml (watch.enabled).")

    # on_text: what you type goes to buddy.handle(), and its answer goes into the bubble.
    face.run(background=heartbeat, on_text=buddy.handle, on_talk=on_talk,
             width=config.get("pet", {}).get("width"),
             subjects=buddy.subjects_menu, on_subject=buddy.subject_action)


if __name__ == "__main__":
    main()
