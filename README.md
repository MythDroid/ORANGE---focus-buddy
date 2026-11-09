# Orange

A small voice-activated AI desk assistant. You say the wake word, ask a question,
and Orange answers out loud. It can also look through the webcam if you ask.

v1.0 runs on a Windows laptop. Later it moves to a Raspberry Pi 5.

## Setup (Windows)

1. **Install Python 3.11** (if `py -3.11 --version` fails):
   ```powershell
   winget install Python.Python.3.11
   ```
   Close and reopen the terminal afterwards.

2. **Create a virtual environment** (a private box of packages just for this project):
   ```powershell
   py -3.11 -m venv venv
   ```

3. **Activate it** (you'll see `(venv)` at the start of the prompt):
   ```powershell
   .\venv\Scripts\Activate.ps1
   ```
   If PowerShell says "running scripts is disabled", run this once, then try again:
   ```powershell
   Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
   ```

4. **Install the packages**:
   ```powershell
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```

5. **Add your API key**: copy `.env.example` to `.env` and paste your key in.
   ```powershell
   Copy-Item .env.example .env
   ```
   `.env` is in `.gitignore`, so it never gets committed.

6. **Run**:
   ```powershell
   python main.py
   ```
   You should see `Orange setup OK`.

## Wake word

Orange sleeps until it hears the wake word (default: **"Hey Jarvis"**). This runs fully
offline: a small model on your CPU scores each 80 ms of audio, and nothing is saved or sent.
Set `wake.show_scores: true` in `config.yaml` to see live scores and tune `wake.threshold`.

### Custom wake word (e.g. "Hey Orange")

openWakeWord models are trained on **synthetic speech**, so you don't record yourself thousands of times:

1. A text-to-speech engine generates thousands of clips of the phrase ("hey orange")
   in many different voices, speeds and accents.
2. The clips are mixed with background noise and room echo, so the model works in real rooms.
3. Lots of "negative" audio (normal talk, music, noise) teaches it what is NOT the wake word.
4. A small classifier is trained on top of openWakeWord's shared speech-feature model.
   The result is a single small `.onnx` file.

The openWakeWord GitHub repo has a training notebook for this
(https://github.com/dscripka/openWakeWord, see "Training New Models"). It runs on Google Colab's free GPU.

To use your model:
1. Put the file at `models/hey_orange.onnx`. Note that `models/` is in `.gitignore`.
2. In `config.yaml`, set `wake.model: "models/hey_orange.onnx"`.

## Project layout

```
main.py          entry point
config.yaml      all settings (no secrets)
.env             your API key (never committed)
goals.txt        your goals, used by study mode
orange/          one file per part: wake, listen, stt, vision, brain, speak, study_mode, privacy
tests/           tests
```

## Privacy

- The API key lives only in `.env`.
- Audio and photos stay in memory and are never saved to disk.
- Orange prints a status line whenever the mic is recording or the camera is on.
