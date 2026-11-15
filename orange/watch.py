"""The distraction watch: Orange notices when the window in front doesn't match your task.

Only while a study session is running (not on a break, not paused), she looks at the
TITLE of the window in front, for example "Funny cats - YouTube - Google Chrome".
She never looks at what is inside the window, and titles are not saved anywhere
(only the ones you tell her are fine, so she can remember that).

What she does, in gentle steps:
    1. side-eye                      as soon as she thinks you drifted
    2. a nudge in the bubble         if you stay there
    3. hides (minimises) the window  if you still stay. NEVER closes it: nothing is lost,
                                     one click on the taskbar brings it back. As she does it,
                                     she grows to fill the whole screen for a few seconds.
    4. if you open it again          she says so at once and hides it sooner each time

If she is wrong, say or type "this is for study". She brings the window back and
never flags that page again.

Who decides "distracted"?
    - she only judges the programs in watch.only_judge (browsers, chat and video apps).
      Calculator, Snipping Tool, Settings, your editor... are never judged at all
    - in a browser, an empty new tab, a search, a login page and AI assistants are always okay
    - pages you allowed are always okay
    - otherwise the local brain judges the title against your task
    - with the brain off, a short built-in list of well-known time-sinks is used
"""
import ctypes
import os
import re
import sys
import time

IS_WINDOWS = sys.platform == "win32"
_BROWSERS = ("chrome.exe", "msedge.exe", "firefox.exe", "brave.exe", "opera.exe")
_TIME_SINKS = re.compile(r"instagram|netflix|facebook|twitter|reddit|prime video|hotstar|amazon|"
                         r"flipkart|myntra|shorts|snapchat|pinterest|steam|9gag|tiktok", re.I)

# Browser pages that are never a distraction, whatever the task: an empty new tab, a search,
# a login or Wi-Fi sign-in page, browser settings, and AI assistants (you use them for doubts).
_NEUTRAL_PAGES = re.compile(
    r"^(?:new tab|new incognito tab|new inprivate tab|new private tab|about:blank|untitled|blank page|"
    r"start|home|google|bing|duckduckgo|search)$"
    r"|google search$|\bsearch results?\b|- bing$|- search$"
    r"|\b(?:log ?in|sign ?in|sign ?up|wi-?fi|hotspot|captive|network|authenticat\w*|verify|otp)\b"
    r"|\b(?:settings|downloads|history|extensions|bookmarks)$"
    r"|chatgpt|claude|gemini|copilot|perplexity|notebooklm|deepseek", re.I)

# On these sites, "the brain isn't sure" is treated as a distraction (a study video usually has a
# title that is clearly about the subject; a vague title on a video site usually isn't study).
_VIDEO_SITES = re.compile(r"youtube|netflix|hotstar|prime video|crunchyroll|jiocinema|twitch|"
                          r"disney|zee5|sonyliv|mx player", re.I)

# ---------- talking to Windows (the only Windows-specific part) ----------

if IS_WINDOWS:
    from ctypes import wintypes
    _user32, _kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
    # Tell Python what each Windows function takes and gives back (needed on 64-bit Windows).
    _user32.GetForegroundWindow.restype = wintypes.HWND
    _user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    _user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    _user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    _user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
    _user32.IsWindow.argtypes = [wintypes.HWND]
    _user32.IsIconic.argtypes = [wintypes.HWND]      # "iconic" is Windows' word for minimised
    _kernel32.OpenProcess.restype = wintypes.HANDLE
    _kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    _kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                                     ctypes.POINTER(wintypes.DWORD)]
    _kernel32.CloseHandle.argtypes = [wintypes.HANDLE]


def front_window():
    """The window you are using right now: {"id", "title", "app", "mine"}, or None."""
    if not IS_WINDOWS:
        return None
    hwnd = _user32.GetForegroundWindow()
    if not hwnd:
        return None
    length = _user32.GetWindowTextLengthW(hwnd)
    text = ctypes.create_unicode_buffer(length + 1)
    _user32.GetWindowTextW(hwnd, text, length + 1)
    pid = wintypes.DWORD()
    _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return {"id": hwnd, "title": text.value.strip(), "app": _app_name(pid.value),
            "mine": pid.value == os.getpid(),       # mine = one of Orange's own windows
            "minimised": bool(_user32.IsIconic(hwnd))}


def _app_name(pid):
    """Process id -> program file name in lower case, e.g. "chrome.exe". "" if not allowed to ask."""
    handle = _kernel32.OpenProcess(0x1000, False, pid)   # 0x1000 = "may I ask only basic facts"
    if not handle:
        return ""
    try:
        path = ctypes.create_unicode_buffer(520)
        size = wintypes.DWORD(520)
        if _kernel32.QueryFullProcessImageNameW(handle, 0, path, ctypes.byref(size)):
            return os.path.basename(path.value).lower()
        return ""
    finally:
        _kernel32.CloseHandle(handle)


def hide_window(window_id):
    """Minimise (6). The window and everything in it stays open in the taskbar."""
    if IS_WINDOWS and _user32.IsWindow(window_id):
        _user32.ShowWindow(window_id, 6)


def bring_back_window(window_id):
    """Restore (9) a window that was minimised."""
    if IS_WINDOWS and _user32.IsWindow(window_id):
        _user32.ShowWindow(window_id, 9)


def tidy_title(title):
    """ "(3) Cats - YouTube - Google Chrome" -> "Cats - YouTube". Unread counts and browser names removed."""
    title = re.sub(r"^\(\d+\+?\)\s*", "", title)
    title = re.sub(r"\s+[-–—]\s+(?:Google Chrome|Microsoft​? Edge|Mozilla Firefox|Brave|Opera)$", "", title)
    return re.sub(r"\s+[-–—]\s+(?:Personal|Profile \d+|Work)$", "", title).strip()


# ---------- the watcher ----------

class Watcher:
    def __init__(self, cfg, buddy, brain, store, face, front=front_window,
                 hide=hide_window, bring_back=bring_back_window):
        self.cfg, self.buddy, self.brain, self.store, self.face = cfg, buddy, brain, store, face
        self._front, self._hide, self._bring_back = front, hide, bring_back
        self.always_fine = {a.lower() for a in cfg.get("always_fine", [])}
        # She only ever judges these programs (browsers and a few chat / entertainment apps).
        # Everything else - Calculator, Snipping Tool, Settings, the Wi-Fi panel... - is left alone.
        self.only_judge = {a.lower() for a in cfg.get("only_judge", _BROWSERS)}
        self.verdicts = {}        # (task, title) -> True (distracted) / False. Brain answers we remember
        self.seen = None          # (window id, title) currently in front
        self.seen_since = 0.0
        self.judged = False       # Has the window in front been judged yet?
        self.drift = None         # While distracted: which window, since when, which round, what she did
        self.watching = "?"       # The task being watched (None = off). "?" = not announced yet
        self.last_flagged = None  # The last window she complained about (for "this is for study")

    def run(self):
        """Loop forever. Start this in a thread."""
        print("Orange is watching for distractions during study sessions (window titles only).")
        while True:
            try:
                self.step(time.time())
            except Exception as err:          # One odd window must not stop the watch
                print(f"Watch hiccup: {err!r}")
            time.sleep(self.cfg.get("check_seconds", 1))

    def step(self, now):
        task = self.buddy.focus_task()
        if task != self.watching:             # Say in the terminal when the watch switches on or off
            self.watching = task
            print(f"Watch: ON for \"{task}\"" if task else
                  "Watch: OFF (no study session running, or on a break, or paused)")
        if task is None:                      # No session, or on a break, or paused: don't watch
            self._calm_down()
            self.seen = None
            return
        window = self._front()
        if window is None or window["mine"] or not window["title"] or window.get("minimised"):
            return                            # Orange's own windows, the bare desktop, a window just hidden

        # --- 1. Judge the window once it has stayed in front for a few seconds ---
        key = (window["id"], window["title"])
        if key != self.seen:                  # You switched window or page: start the settle clock
            self.seen, self.seen_since, self.judged = key, now, False
        if not self.judged and now - self.seen_since >= self.cfg.get("settle_seconds", 2):
            self.judged = True
            if self._is_distraction(task, window):
                self.last_flagged = dict(window)
                if self.drift is None:
                    self.buddy.note_distraction()
                    self._start_round(1, window, now)
                elif self.drift["hidden"]:    # A different distraction after she already hid one
                    self._start_round(self.drift["round"] + 1, window, now)
                else:
                    self.drift["id"] = window["id"]
            else:
                came_back = self.drift is not None and self.drift["nudged"]
                self._calm_down()
                if came_back:
                    self.buddy.show("happy", 3)
                    self.face.say(f"Yay, back to {task}!")
                return

        # --- 2. While you stay on the distracting window, step it up ---
        # (This runs even while the title keeps changing, e.g. scrolling from reel to reel.)
        drift = self.drift
        if drift is None or window["id"] != drift["id"]:
            return
        if drift["hidden"]:
            # She hid this window and you opened it again: start a stricter round.
            if now - drift["hidden_at"] >= 4:
                self._start_round(drift["round"] + 1, window, now)
            return
        waited = now - drift["since"]
        first = drift["round"] == 1
        hide_after = (self.cfg.get("hide_after_seconds", 0) if first
                      else self.cfg.get("repeat_hide_after_seconds", 0))
        hiding = self.cfg.get("hide_windows", True)
        nudge_after = self.cfg.get("nudge_after_seconds", 20)
        # The nudge only makes sense if it comes BEFORE the hide (or if hiding is switched off).
        if not drift["nudged"] and waited >= nudge_after and (not hiding or nudge_after < hide_after):
            drift["nudged"] = True
            self.face.say(f"Hmm... weren't we doing {task}?\n(If this is for study, tell me: this is for study)",
                          seconds=12)
        if hiding and waited >= hide_after:
            drift["hidden"], drift["hidden_at"] = True, now
            self._hide(drift["id"])
            grow = self.cfg.get("grow_seconds", 5)
            if grow and hasattr(self.face, "loom"):
                self.face.loom(grow)          # She fills the whole screen for a few seconds
            line = ("I tucked that window away. It's safe in the taskbar." if first
                    else "Nope! Tucked away again." if drift["round"] == 2
                    else f"That's {drift['round']} times now! Away it goes.")
            self.face.say(f"{line}\nBack to {task}!", seconds=12)

    def _start_round(self, number, window, now):
        """Round 1 is gentle (side-eye, nudge, hide). Later rounds speak up at once and hide sooner."""
        self.drift = {"id": window["id"], "since": now, "round": number,
                      "nudged": number > 1, "hidden": False, "hidden_at": 0.0}
        self.buddy.show("sideeye", 3600)
        if number > 1:
            task = self.buddy.focus_task() or "work"
            self.face.say(f"Hey, I saw that! We're doing {task}, remember?", seconds=10)

    def _calm_down(self):
        if self.drift is not None:
            self.drift = None
            self.buddy.show(None)

    def _is_distraction(self, task, window):
        app, title = window["app"], tidy_title(window["title"])
        if app not in self.only_judge or app in self.always_fine:
            return False                      # Not a program she judges (tools, system windows...)
        if _NEUTRAL_PAGES.search(title) or self.store.is_allowed_title(title):
            return False                      # New tab, search, login, AI assistant, or you allowed it
        if (task, title) not in self.verdicts:
            verdict = self.brain.judge(task, title, app) if self.brain and self.brain.enabled() else None
            if verdict is None:               # Brain off or unreachable: the short built-in list
                verdict = "distracted" if _TIME_SINKS.search(title) else "on_task"
            if verdict == "unsure" and _VIDEO_SITES.search(title):
                verdict = "distracted"        # see _VIDEO_SITES above
            print(f"Watch: \"{title}\" ({app}) during \"{task}\" -> {verdict}")
            self.verdicts[(task, title)] = verdict == "distracted"   # elsewhere "unsure" counts as fine
        return self.verdicts[(task, title)]

    def allow_current(self):
        """You said "this is for study". Returns Orange's reply."""
        flagged = self.last_flagged
        if flagged is None:
            return "Okay! I wasn't worried about anything right now."
        self.store.allow_title(tidy_title(flagged["title"]))
        if self.drift is not None and self.drift["hidden"]:
            self._bring_back(self.drift["id"])
        self._calm_down()
        self.last_flagged = None
        self.judged = False                   # Look again with fresh eyes
        return "Oh, sorry! I'll remember that one is for study."
