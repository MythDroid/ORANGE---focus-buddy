"""Checks Orange's local brain. Run:  python test_brain.py

It sends a few everyday sentences to the model and prints what the brain decided
and how long each one took. Ollama must be installed and the model pulled.
"""
import sys
from pathlib import Path

import yaml

from orange import brain

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
config = yaml.safe_load(open(Path(__file__).parent / "config.yaml", encoding="utf-8"))
brain.init(config["brain"]["understand"])

print("Loading the model (the first time can take a while)...")
brain.warm_up()

# These are NOT the example sentences written inside the brain's instructions,
# so this shows whether she really understands, not whether she can copy.
SENTENCES = [
    ("hold on, someone's at the door", "away"),
    ("gotta pee brb", "away (the rules catch 'brb', so this checks the brain agrees)"),
    ("let's do some machine learning till lunch", "study, 0 minutes (no time was said)"),
    ("two hours of GATE maths please", "study, 120 minutes"),
    ("alright I'm done with my food", "back"),
    ("nudge me after half an hour to call amma", "remind, 30 minutes"),
    ("don't forget my lab record is due on Friday", "remember"),
    ("I feel like I'm not good enough for this exam", "chat, with a kind reply"),
    ("can you explain backpropagation", "chat, saying she can't explain"),
    ("I can't do this anymore, closing up", "stop or bye"),
    ("how much longer do I have", "time_left"),
    ("asdf qwerty", "none"),
]
right_after = ""
for sentence, expected in SENTENCES:
    print(f"\nExpected: {expected}")
    if brain.understand(sentence, name="princess") is None:
        print("No answer. Is Ollama running? Try:  ollama list")
        break
