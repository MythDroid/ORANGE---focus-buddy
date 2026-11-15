"""Listens for the wake word ("Hey Jarvis" for now) using openWakeWord. Runs 100% locally.

How it works: every 80 ms we give openWakeWord the newest chunk of mic audio.
It returns a score from 0 to 1 = "how sure am I that the wake word was just said".
When the score passes the threshold in config.yaml, we stop and return.
"""
from pathlib import Path

import numpy as np
import sounddevice as sd
from openwakeword.model import Model
from openwakeword.utils import download_models

from orange import privacy

ROOT = Path(__file__).parent.parent  # Project folder (custom model paths are relative to it)

_model = None
_wake_cfg = None
_audio_cfg = None


def init(wake_cfg, audio_cfg):
    """Load the wake word model once at startup."""
    global _model, _wake_cfg, _audio_cfg
    _wake_cfg, _audio_cfg = wake_cfg, audio_cfg
    name = wake_cfg["model"]

    if name.endswith((".onnx", ".tflite")):
        model_ref = str(ROOT / name)  # Your own trained model file
    else:
        # Built-in model: download it the first time (a few MB, saved inside the venv).
        download_models([name])
        model_ref = name

    _model = Model(wakeword_models=[model_ref],
                   inference_framework=wake_cfg["inference_framework"])


def wait_for_wake_word(wake_now=None):
    """Block until the wake word is heard, then return.

    wake_now: an optional threading.Event. If something sets it (for example a click on
    Orange), we also return, as if the wake word had been said.
    """
    if _model is None:
        raise RuntimeError("Call wake.init(...) first.")

    # Clear the model's memory of old audio. Without this it still "remembers"
    # the last wake word and could fire again instantly.
    _model.reset()
    n = _wake_cfg["chunk_samples"]
    threshold = _wake_cfg["threshold"]

    privacy.wake_on()
    try:
        # "with" closes the mic stream as soon as we leave this block, so the mic
        # is free before listen.py opens its own stream.
        with sd.InputStream(samplerate=_audio_cfg["sample_rate"], channels=1, dtype="int16",
                            blocksize=n, device=_audio_cfg["input_device"]) as stream:
            while True:
                chunk, _ = stream.read(n)
                if wake_now is not None and wake_now.is_set():
                    print("Woken by a click")
                    return
                # openWakeWord wants a flat array of 16-bit integers.
                scores = _model.predict(np.ascontiguousarray(chunk[:, 0]))
                score = max(scores.values())  # We load one model, so one score

                if _wake_cfg["show_scores"] and score > 0.05:
                    print(f"   wake score: {score:.2f}")
                if score >= threshold:
                    print(f"Wake word heard (score {score:.2f})")
                    return
    finally:
        privacy.mic_off()
