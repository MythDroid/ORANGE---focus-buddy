"""Speech-to-text: turns recorded audio into text using faster-whisper (runs locally)."""
import os

# Hide a harmless Windows warning about the model download cache (symlinks).
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

from faster_whisper import WhisperModel  # noqa: E402 (must come after the line above)

_model = None     # Loaded once by init(), then reused for every sentence
_prompt = None    # "Context" text that nudges Whisper toward the right spellings
_hotwords = None  # Names Whisper should strongly expect


def init(stt_cfg, names=()):
    """Load the Whisper model once at startup (slow: a few seconds).

    names: e.g. ["Mythrayee", "Orange"]. They go first in the prompt, then
    the hint words from config.yaml. Another user just changes user.name.
    """
    global _model, _prompt, _hotwords
    _model = WhisperModel(stt_cfg["model_size"], device=stt_cfg["device"],
                          compute_type=stt_cfg["compute_type"])

    # Result looks like: "Mythrayee. Orange. GATE DA. eigenvalues, eigenvectors, ..."
    parts = [f"{n}." for n in names if n] + [stt_cfg.get("hint", "")]
    _prompt = " ".join(parts).strip() or None
    _hotwords = " ".join(n for n in names if n) if stt_cfg.get("use_hotwords") else None


def transcribe(audio):
    """audio: 16 kHz mono float32 numpy array (what listen.record returns). Returns text."""
    if _model is None:
        raise RuntimeError("Call stt.init(...) before transcribe().")
    # Whisper splits speech into segments. It returns a generator, so the
    # real work happens while we loop over it below.
    segments, _info = _model.transcribe(audio, language="en", beam_size=5,
                                        initial_prompt=_prompt, hotwords=_hotwords)
    return " ".join(seg.text.strip() for seg in segments).strip()
