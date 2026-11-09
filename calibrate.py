"""Measures your room's background noise and suggests audio.silence_threshold.

Run it, stay QUIET for 3 seconds, then copy the suggested number into config.yaml.
"""
import sys
from pathlib import Path

import numpy as np
import sounddevice as sd
import yaml

from orange import privacy
from orange.listen import rms

sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # So the emoji print on any terminal
SECONDS = 3

cfg = yaml.safe_load(open(Path(__file__).parent / "config.yaml", encoding="utf-8"))["audio"]
rate = cfg["sample_rate"]
block = int(rate * cfg["block_ms"] / 1000)

print(f"Stay quiet for {SECONDS} seconds...")
privacy.mic_on()
try:
    audio = sd.rec(SECONDS * rate, samplerate=rate, channels=cfg["channels"],
                   dtype="float32", device=cfg["input_device"])
    sd.wait()  # Block until recording is done
finally:
    privacy.mic_off()

# Same chunk size as listen.py, so the numbers are comparable.
audio = audio[:, 0]
levels = [rms(audio[i:i + block]) for i in range(0, len(audio) - block + 1, block)]
typical = float(np.median(levels))
loudest = float(np.percentile(levels, 95))  # Ignores the very loudest 5% (a single click)

# Speech is usually several times louder than background noise. Setting the
# threshold ~3x above the noise means noise counts as silence but your voice doesn't.
suggested = round(max(loudest * 3, 0.003), 4)

print(f"Typical noise level : {typical:.4f}")
print(f"Loud noise level    : {loudest:.4f}")
print(f"Current threshold   : {cfg['silence_threshold']}")
print(f"Suggested threshold : {suggested}")
print("Put the suggested value in config.yaml -> audio -> silence_threshold.")
