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
