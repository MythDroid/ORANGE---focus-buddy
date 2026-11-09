"""Records your voice from the mic until you stop talking. Audio stays in memory only.

How silence detection works:
  The mic gives us audio as numbers between -1 and 1. We look at it in small
  chunks (30 ms each) and measure each chunk's loudness with RMS
  ("root mean square": square every number, take the average, then the square
  root). Quiet room = small RMS, talking = bigger RMS.
  - Before you speak: we wait for a chunk louder than silence_threshold.
  - While you speak: every loud chunk resets a "quiet timer".
  - When the quiet timer reaches silence_seconds, you've finished, so we stop.
"""
from collections import deque

import numpy as np
import sounddevice as sd

from orange import privacy


def rms(chunk):
    """Loudness of one chunk of audio (0 = total silence)."""
    return float(np.sqrt(np.mean(np.square(chunk))))


def record(audio_cfg):
    """Record one sentence. Returns a 1-D float32 numpy array, or None if nothing was heard."""
    rate = audio_cfg["sample_rate"]
    block = int(rate * audio_cfg["block_ms"] / 1000)  # Samples per chunk
    block_sec = block / rate

    # Small rolling buffer of the most recent chunks before speech starts.
    # deque(maxlen=N) automatically drops the oldest chunk when full.
    pre_roll = deque(maxlen=max(1, int(audio_cfg["pre_roll_seconds"] / block_sec)))
    chunks = []          # The actual recording (only in memory)
    started = False      # Has the person started talking yet?
    quiet_time = 0.0     # How long it's been quiet since they last spoke
    elapsed = 0.0        # Seconds of audio read so far (counted from the audio, not a clock)

    privacy.mic_on()
    try:
        with sd.InputStream(samplerate=rate, channels=audio_cfg["channels"], dtype="float32",
                            blocksize=block, device=audio_cfg["input_device"]) as stream:
            while True:
                chunk, _ = stream.read(block)  # Waits until one chunk is ready
                chunk = chunk[:, 0].copy()     # Keep channel 0 -> flat 1-D array
                elapsed += block_sec
                loud = rms(chunk) > audio_cfg["silence_threshold"]

                if not started:
                    pre_roll.append(chunk)
                    if loud:
                        started = True
                        chunks.extend(pre_roll)  # Include the moment just before speech
                    elif elapsed > audio_cfg["no_speech_timeout"]:
                        print("Gave up, nothing heard.")
                        return None
                else:
                    chunks.append(chunk)
                    quiet_time = 0.0 if loud else quiet_time + block_sec
                    if quiet_time >= audio_cfg["silence_seconds"]:
                        break  # They stopped talking

                if elapsed >= audio_cfg["max_record_seconds"]:
                    print("Max recording time reached.")
                    break
    finally:
        privacy.mic_off()  # "finally" runs even if there's an error, so this always prints

    return np.concatenate(chunks)
