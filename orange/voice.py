"""Orange's ears: lets you TALK to Orange instead of typing.

Three ways to start talking:
    1. Say "Hey Orange" (you can say everything in one breath:
       "Hey Orange, study DL for 45 minutes").
    2. Double-click Orange.
    3. Press Ctrl+Space (works from any app).

How "Hey Orange" works (no special wake-word model needed):
    The mic waits for a sound louder than the room. When you speak, the sentence is
    recorded in memory and only its first 2.5 seconds are turned into text. If that
    text does not start with "hey Orange", the recording is thrown away at once.
    Nothing is saved, nothing is printed, nothing leaves the laptop.
    Cost: the mic is on while Orange runs, and she does a little work each time she
    hears speech. Switch it off with voice.hey_orange: false in config.yaml.

Reuses listen.py (recording) and stt.py (Whisper speech-to-text) from the earlier
phases. This runs in its own thread, so the window never freezes while she listens.
"""
import re
import threading

import numpy as np
import sounddevice as sd

from orange import listen, privacy, stt

_talk_now = threading.Event()    # Set by a double-click or Ctrl+Space: "listen right now"
_running = False

# "hey orange", "hi orange", "okay orange", or just "orange", at the very start.
# Whisper sometimes writes it as "orang", "oranges" or "aurange", so those count too.
_CALL = re.compile(r"^\W*(?:(?:hey|hi|hay|a|ok|okay|hello)\W+)?(?:orange|oranges|orang|aurange|or?ange)\b[\s,.!?]*",
                   re.I)


def talk_now():
    """Call this on a double-click or the shortcut. Returns False if her ears are not on."""
    if _running:
        _talk_now.set()
    return _running


def heard_my_name(text):
    """ "Hey Orange, study DL" -> "study DL".  "Hey Orange" -> "".  Something else -> None."""
    match = _CALL.match(text)
    return text[match.end():].strip() if match else None


def _wait_for_speech(audio_cfg):
    """Wait (as long as it takes) for someone to speak, and record that one sentence.

    Returns the recording, or None if a double-click / shortcut arrived instead.
    Same loudness idea as listen.py: loud chunk = speech, long quiet = sentence over.
    """
    rate = audio_cfg["sample_rate"]
    block = int(rate * audio_cfg["block_ms"] / 1000)
    block_sec = block / rate
    recent, chunks, quiet, started = [], [], 0.0, False
    keep_before = max(1, int(audio_cfg["pre_roll_seconds"] / block_sec))
    with sd.InputStream(samplerate=rate, channels=audio_cfg["channels"], dtype="float32",
                        blocksize=block, device=audio_cfg["input_device"]) as stream:
        while not _talk_now.is_set():
            chunk, _ = stream.read(block)
            chunk = chunk[:, 0].copy()
            loud = listen.rms(chunk) > audio_cfg["silence_threshold"]
            if not started:
                recent = (recent + [chunk])[-keep_before:]     # keep a moment from just before speech
                if loud:
                    started, chunks = True, list(recent)
                continue
            chunks.append(chunk)
            quiet = 0.0 if loud else quiet + block_sec
            if quiet >= audio_cfg["silence_seconds"] or len(chunks) * block_sec >= audio_cfg["max_record_seconds"]:
                return np.concatenate(chunks)
    return None


def run(config, buddy, face):
    """The listening loop. Blocks forever, so start it in a thread."""
    global _running
    hey_orange = config.get("voice", {}).get("hey_orange", True)
    audio_cfg, rate = config["audio"], config["audio"]["sample_rate"]
    try:
        print(f"Loading speech model '{config['stt']['model_size']}'...")
        stt.init(config["stt"], names=[config["user"]["name"], config["assistant"]["name"]])
        _running = True
        ways = "Say \"Hey Orange\", double-click me, or press Ctrl+Space" if hey_orange \
            else "Double-click me or press Ctrl+Space"
        print(f"Orange can hear now. {ways} to talk.")
        if hey_orange:
            print("🟠 Mic on: waiting for \"Hey Orange\" (audio not saved or sent)")

        while True:
            text = None
            # 1. Wait until you want to talk.
            if hey_orange:
                audio = _wait_for_speech(audio_cfg)
                if audio is not None:
                    # Cheap check first: only the first 2.5 seconds, just to look for her name.
                    if heard_my_name(stt.transcribe(audio[:int(2.5 * rate)])) is None:
                        continue                         # Not for her: forget it and keep waiting
                    text = heard_my_name(stt.transcribe(audio)) or ""
            else:
                _talk_now.wait()
            _talk_now.clear()

            # 2. If she has no sentence yet (double-click, shortcut, or only "Hey Orange"): listen now.
            if not text:
                buddy.show("listening", 30)
                face.say("I'm listening...", seconds=6)
                audio = listen.record(audio_cfg)
                if audio is None or len(audio) < 0.4 * rate:
                    buddy.show(None)
                    face.say("I didn't hear anything. Double-click me and try again.")
                    continue
                text = stt.transcribe(audio)
                text = heard_my_name(text) or text       # drop a leading "Hey Orange" if you said it anyway
                if not text:
                    buddy.show(None)
                    face.say("I couldn't make out the words. Try once more?")
                    continue
            print(f"You said: {text}")

            # 3. Do it, and show what was heard so you can spot a mishearing.
            buddy.show(None)
            face.say(f"I heard: \"{text}\"", seconds=30)     # stays until the answer replaces it
            reply = buddy.handle(text)
            face.say(f"I heard: \"{text}\"\n\n{reply}")
            _talk_now.clear()
    except Exception as err:      # No microphone, model missing, ...: Orange keeps working without ears
        _running = False
        print(f"Voice stopped: {err!r}")
        face.say("My ears aren't working. You can still type to me (right-click).\nSee the terminal for why.")
    finally:
        privacy.mic_off()
