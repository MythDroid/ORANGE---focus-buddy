"""Text-to-speech: says Orange's reply out loud.

Engine is picked by `speak.engine` in config.yaml:
  "pyttsx3" -> works now (offline, uses the voice built into Windows / Linux)
  "piper"   -> placeholder for later (nicer, more natural voice)
"""
import pyttsx3

# Default settings. init() replaces these with the values from config.yaml.
_settings = {"engine": "pyttsx3", "rate": 175, "volume": 1.0}


def init(speak_config):
    """Call once at startup with the `speak:` section of config.yaml."""
    _settings.update(speak_config)


def say(text):
    """Print the text, then speak it. Returns when speaking is finished."""
    print(f"Orange: {text}")

    engine_name = _settings["engine"]
    if engine_name not in _ENGINES:
        raise ValueError(f"Unknown speak.engine '{engine_name}'. Use one of: {list(_ENGINES)}")
    _ENGINES[engine_name](text)


def _say_pyttsx3(text):
    # WHY a new engine every time: on Windows, reusing one pyttsx3 engine often
    # freezes on the 2nd runAndWait() call. Creating a fresh engine for each
    # sentence and stopping it afterwards avoids that. Creating one is quick.
    engine = pyttsx3.init()
    engine.setProperty("rate", _settings["rate"])
    engine.setProperty("volume", _settings["volume"])
    engine.say(text)
    engine.runAndWait()  # Blocks until the sentence is fully spoken
    engine.stop()
    # pyttsx3 keeps a cached engine while it's still referenced. Deleting our
    # reference lets the next init() build a brand-new one.
    del engine


def _say_piper(text):
    # PLACEHOLDER: Piper support comes in a later phase.
    raise NotImplementedError("Piper isn't set up yet. Set speak.engine to 'pyttsx3' in config.yaml.")


# Maps the config value to the function that does the speaking.
# To add a new engine: write a _say_xxx(text) function and add it here.
_ENGINES = {
    "pyttsx3": _say_pyttsx3,
    "piper": _say_piper,
}
