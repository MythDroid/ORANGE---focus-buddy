"""The pet window: transparent, no frame, always on top, with orange.html inside.

Built with PyQt6. Its QWebEngineView is a small built-in Chromium browser, so the
exact same orange.html you previewed in Chrome is what gets drawn here.

What this file does:
  - opens a small see-through window in the bottom-right corner
  - DRAG Orange to move her (she dangles; shake her, fling her or push her into a screen edge
    and she reacts; the spot is remembered for next time)
  - HOVER the mouse next to her without clicking and she leans away, suspicious
  - CLICK Orange to poke her (tummy, face, antennas, head, feet each react differently)
  - DOUBLE-CLICK Orange to talk to her (or, if her ears are off, to type in a small text box)
  - Orange answers in a speech bubble
  - right-click menu: quick sessions, moods, quit
  - tells Orange where the mouse is, so the eyes follow it across the whole screen

Three small windows live here: PetWindow (Orange), Bubble (what Orange says) and
AskBox (where you type). The bubble and the box are plain Qt widgets that only
appear when needed, so they never block your clicks the rest of the time.

Nothing here uses the internet. The page is loaded from the file on your disk.
"""
import ctypes
import json
import random
import signal
import sys
import threading
import time
from pathlib import Path

from PyQt6.QtCore import QEvent, QObject, Qt, QTimer, QUrl, pyqtSignal
from PyQt6.QtGui import QCursor
from PyQt6.QtWebEngineWidgets import QWebEngineView  # Must be imported before QApplication is made
from PyQt6.QtWidgets import QApplication, QLabel, QLineEdit, QMenu, QVBoxLayout, QWidget

# Keep this list the same as MOODS in orange.js.
MOODS = ["idle", "happy", "listening", "focused", "sleepy", "confused", "amazed",
         "celebrating", "sideeye"]

HTML = Path(__file__).parent / "orange.html"
# Where the window position is remembered. It lives in your home folder
# (C:\Users\<you>\.orange\window.json), so it never ends up in git.
STATE_FILE = Path.home() / ".orange" / "window.json"

WIDTH, HEIGHT = 180, 194   # Window size in pixels (same shape as the drawing: 200 x 216).
                           # run(width=...) changes it; the number comes from config.yaml (pet.width)
MARGIN = 24                # Gap from the screen edge at the default spot
LOOK_EVERY_MS = 100        # How often we check the mouse position (10 times a second is plenty)
DRAG_AFTER_PX = 6          # Move the mouse this far with the button down = a drag, not a click

# What she says when you poke her. One line is picked at random.
POKE_LINES = {
    "tummy": ["Hehe, that tickles!", "Eep! My tummy!", "Squish!"],
    "face": ["Ow, my screen!", "Not the face!", "You smudged my screen!"],
    "antenna": ["Boing!", "Wheee!", "Hey, that's my antenna!"],
    "feet": ["My toes!", "Hop hop!"],
    "head": ["Mmm, that's nice.", "Hehe, thank you!", "More pats please."],
    "huff": ["Hmph! Stop poking me!", "That's enough poking!"],
}
CARRY_LINES = ["Put me down!", "Whoa whoa whoa!", "Hey! I can walk, you know!", "Eeek!"]
SHAKE_LINES = ["S-s-stop sh-shaking me!", "Bzzt! My s-screen!"]
WARY_LINES = ["...what are you doing?", "I see you.", "Hmm?"]

ANNOYED_AFTER = 5          # This many pokes within 6 seconds and she gets huffy
HUFF_SECONDS = 4


def left_button_down():
    """Is the left mouse button held right now? (While Windows drags a window, only Windows knows.)"""
    if sys.platform == "win32":
        return bool(ctypes.windll.user32.GetAsyncKeyState(0x01) & 0x8000)   # 0x01 = left mouse button
    return bool(QApplication.mouseButtons() & Qt.MouseButton.LeftButton)


def body_spot(x, y):
    """Which part of Orange is at this point? x, y are in the drawing's own units (200 wide, 216 tall)."""
    if y > 168:
        return "feet"
    if y < 82 and x < 62:
        return "antenna-l"
    if y < 82 and x > 138:
        return "antenna-r"
    if 58 <= x <= 142 and 53 <= y <= 123:
        return "face"
    if y < 53 and 60 < x < 140:
        return "head"
    if 48 <= x <= 152 and 123 < y <= 168:
        return "tummy"
    return None                # empty space around her

# Same flags for all three windows: no title bar, floats on top, no taskbar button.
_FLOATING = (Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
             | Qt.WindowType.Tool)
_LOOK = ("background: #FFF9EE; color: #5A3A22; border: 2px solid #E3741F; border-radius: 14px;"
         " font-family: 'Segoe UI', sans-serif; font-size: 13px;")


class _Bridge(QObject):
    """A safe doorway between threads.

    Qt windows may only be touched from the main thread. A "signal" is Qt's way
    to pass a message: any thread can emit it, and Qt delivers it on the main
    thread. So set_mood(), say() and set_timer() just emit a signal.
    """
    mood = pyqtSignal(str)
    say = pyqtSignal(str, float)
    timer = pyqtSignal(str)
    quit = pyqtSignal()
    talk = pyqtSignal()
    loom = pyqtSignal(float)


_bridge = None         # Made by run(). None means the window isn't open yet
_wanted_mood = "idle"  # The latest mood asked for (also used if asked before the window opens)
_on_text = None        # Function that receives what you typed; must return Orange's reply (or None)
_on_talk = None        # Optional function called on a double-click. Returns True if she started listening


class Bubble(QWidget):
    """Orange's speech bubble. Shows text for a few seconds, then hides. Click it to hide it now.

    Why a see-through box with a label inside: a floating window is a rectangle. To get
    round corners, the window itself is invisible and only the label inside is painted.
    """

    def __init__(self):
        super().__init__()
        # DoesNotAcceptFocus + ShowWithoutActivating: the bubble never steals the keyboard
        # from the app you are typing in.
        self.setWindowFlags(_FLOATING | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.label = QLabel(self)
        self.label.setWordWrap(True)
        self.label.setStyleSheet(f"QLabel {{ {_LOOK} padding: 8px 12px; }}")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSizeConstraint(QVBoxLayout.SizeConstraint.SetFixedSize)   # window hugs the label
        layout.addWidget(self.label)
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)

    def show_text(self, text, seconds, pet):
        # Width: as wide as the longest line needs, but never wider than 270 px (then it wraps).
        letters = self.label.fontMetrics()
        longest = max(letters.horizontalAdvance(line) for line in text.split("\n"))
        self.label.setFixedWidth(min(270, longest + 34))
        self.label.setText(text)
        self.adjustSize()
        self.place_above(pet)
        self.show()
        self._hide_timer.start(int(seconds * 1000))

    def place_above(self, pet):
        _place_above(self, pet)

    def mousePressEvent(self, event):
        self.hide()


class _AskEdit(QLineEdit):
    """The text field inside AskBox. Tells the box when you press Esc or click away."""

    cancelled = pyqtSignal()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.cancelled.emit()
        else:
            super().keyPressEvent(event)

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self.cancelled.emit()        # You clicked somewhere else


class AskBox(QWidget):
    """The little box where you type to Orange. Enter = send, Esc or clicking away = cancel."""

    sent = pyqtSignal(str)
    closed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowFlags(_FLOATING)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.edit = _AskEdit(self)
        self.edit.setStyleSheet(f"QLineEdit {{ {_LOOK} padding: 7px 12px; }}")
        self.edit.setPlaceholderText("Tell Orange... e.g. study DL for 45 minutes")
        self.edit.setFixedWidth(300)
        self.edit.returnPressed.connect(self._send)
        self.edit.cancelled.connect(self.hide)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSizeConstraint(QVBoxLayout.SizeConstraint.SetFixedSize)
        layout.addWidget(self.edit)

    def open(self, pet):
        self.edit.clear()
        self.adjustSize()
        _place_above(self, pet)
        self.show()
        self.activateWindow()    # Bring the keyboard here
        self.edit.setFocus()

    def _send(self):
        text = self.edit.text().strip()
        self.hide()
        if text:
            self.sent.emit(text)

    def hideEvent(self, event):
        super().hideEvent(event)
        self.closed.emit()


def _place_above(widget, pet):
    """Put a small window centred above Orange (or below, if there is no room above)."""
    box = pet.geometry()
    screen = pet.screen().availableGeometry()
    x = box.center().x() - widget.width() // 2
    x = max(screen.left() + 4, min(x, screen.right() - widget.width() - 4))   # stay on the screen
    y = box.top() - widget.height() - 2
    if y < screen.top():
        y = box.bottom() + 2
    if y + widget.height() > screen.bottom():        # No room above OR below (she fills the screen):
        y = screen.top() + 40                        # sit near the top of the screen instead
    widget.move(x, y)


class PetWindow(QWebEngineView):
    def __init__(self):
        super().__init__()
        self._loaded = False
        self._last_look = None
        self._press = None       # Where the left button went down (None = not pressed)
        self._timer_text = ""
        self._skip_release = False   # True right after a double-click (its 2nd release is not a poke)
        self._poke_times = []        # When the recent pokes happened (to notice too much poking)
        self._huff_until = 0.0
        self._stroke = {"x": None, "dir": 0, "turns": 0, "since": 0.0}   # mouse rubbing her head
        self._big = False            # True while she fills the whole screen (see loom)
        self._small_box = None       # Her normal place and size, to go back to afterwards
        self._carry = None           # While you drag her: speed, distance, shaking... (see _begin_carry)
        self._wary = False           # True while she leans away from a hovering mouse
        self._wary_rest = 0.0        # No new wary look before this time
        self._hover = None           # (x, y, since): where the mouse has been resting near her

        self.setWindowFlags(_FLOATING)
        # These three lines make the background see-through: the window itself,
        # the web page behind the drawing, and no default grey fill.
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet("background: transparent;")
        self.page().setBackgroundColor(Qt.GlobalColor.transparent)
        # Turn off the browser's own right-click menu (Back / Reload / ...). We show ours.
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)

        self.resize(WIDTH, HEIGHT)
        self._restore_position()

        self.bubble = Bubble()
        self.ask = AskBox()
        self.ask.sent.connect(self._on_typed)
        self.ask.closed.connect(lambda: self.apply_mood(_wanted_mood))   # stop "listening"

        # "?window" tells orange.js to hide the preview buttons and go see-through.
        url = QUrl.fromLocalFile(str(HTML))
        url.setQuery("window")
        self.loadFinished.connect(self._on_loaded)
        self.load(url)

        # Saving the position: wait until the window has stopped moving for half a
        # second, then save once (instead of saving 100 times during one drag).
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(500)
        self._save_timer.timeout.connect(self._save_position)

        # A single click waits a moment before it counts as a poke, in case it turns out to be
        # the first half of a double-click.
        self._poke_timer = QTimer(self)
        self._poke_timer.setSingleShot(True)
        self._poke_timer.setInterval(QApplication.doubleClickInterval())
        self._poke_timer.timeout.connect(self._poke)
        self._poke_at = None

        # While you carry her, this checks 25 times a second how she is being moved.
        self._carry_timer = QTimer(self)
        self._carry_timer.setInterval(40)
        self._carry_timer.timeout.connect(self._carry_tick)

        # Eyes follow the mouse anywhere on the screen.
        self._look_timer = QTimer(self)
        self._look_timer.setInterval(LOOK_EVERY_MS)
        self._look_timer.timeout.connect(self._look_at_mouse)

        # Mouse clicks land on a hidden child widget inside the web view, not on
        # this window. Listening at the application level catches them wherever they land.
        QApplication.instance().installEventFilter(self)

    # ----- talking to the page -----

    def _js(self, code):
        if self._loaded:
            self.page().runJavaScript(code)

    def _on_loaded(self, ok):
        if not ok:
            print(f"Orange's face could not load {HTML}")
            return
        self._loaded = True
        self.apply_mood(_wanted_mood)
        self.apply_timer(self._timer_text)
        self._look_timer.start()

    def apply_mood(self, mood):
        """Runs on the main thread (called through the bridge signal)."""
        if self.ask.isVisible():
            return               # Keep "listening" while you type; the real mood returns after
        # json.dumps turns happy into "happy" WITH quotes, which is safe to put inside JavaScript.
        self._js(f"Orange.setMood({json.dumps(mood)})")

    def apply_timer(self, text):
        self._timer_text = text
        self._js(f"Orange.setTimer({json.dumps(text or None)})")

    def show_bubble(self, text, seconds):
        if seconds <= 0:
            # Longer text stays longer: 4 seconds, plus a bit for every letter, at most 15.
            seconds = min(15.0, 4.0 + len(text) * 0.06)
        self.bubble.show_text(text, seconds, self)

    def _look_at_mouse(self):
        mouse = QCursor.pos()
        centre = self.geometry().center()
        self._notice_hover(mouse, centre)
        # -1..1 in each direction. 400 px away or more = looking fully that way.
        x = max(-1.0, min(1.0, (mouse.x() - centre.x()) / 400))
        y = max(-1.0, min(1.0, (mouse.y() - centre.y()) / 400))
        look = (round(x, 2), round(y, 2))
        if look != self._last_look:      # Mouse didn't move = do nothing (saves CPU)
            self._last_look = look
            self._js(f"Orange.lookAt({look[0]}, {look[1]})")

    # ----- typing to Orange -----

    def open_ask(self):
        self.bubble.hide()
        self._js('Orange.setMood("listening")')
        self.ask.open(self)

    def _on_typed(self, text):
        handle_text(text)

    # ----- click (poke), double-click (talk), drag (move) and the right-click menu -----

    def eventFilter(self, obj, event):
        kind = event.type()
        if kind not in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseMove, QEvent.Type.MouseButtonRelease,
                        QEvent.Type.MouseButtonDblClick, QEvent.Type.ContextMenu):
            return False                 # Not a mouse event: let it through untouched
        if not (obj is self or (obj.isWidgetType() and self.isAncestorOf(obj))):
            return False                 # A click somewhere else (the menu, the bubble, the text box)

        if kind == QEvent.Type.ContextMenu:
            return True                  # Swallow it; our menu opens on the right-button press
        if self._big:
            return True                  # While she fills the screen she can't be poked or dragged

        if kind == QEvent.Type.MouseButtonDblClick and event.button() == Qt.MouseButton.LeftButton:
            self._poke_timer.stop()      # It was a double-click, so the first click is not a poke
            self._press, self._skip_release = None, True
            self.start_talking()

        elif kind == QEvent.Type.MouseButtonPress:
            if event.button() == Qt.MouseButton.RightButton:
                self._show_menu(event.globalPosition().toPoint())
                return True
            if event.button() == Qt.MouseButton.LeftButton:
                self._press = event.globalPosition().toPoint()   # Click or drag? We'll see.

        elif kind == QEvent.Type.MouseMove:
            here = event.globalPosition().toPoint()
            if self._press is not None:
                if (here - self._press).manhattanLength() > DRAG_AFTER_PX:
                    # It's a drag. Hand it to the operating system: smooth, works on Windows and Linux.
                    self._press = None
                    self._begin_carry()
                    self.windowHandle().startSystemMove()
            elif event.buttons() == Qt.MouseButton.NoButton:
                self._notice_stroke(here)

        elif kind == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
            if self._skip_release:
                self._skip_release = False
            elif self._press is not None:    # Button went down and up without moving = a click
                self._poke_at, self._press = self._press, None
                self._poke_timer.start()
        return False

    def start_talking(self):
        """Double-click or Ctrl+Space. Talk if her ears are on, otherwise open the text box."""
        if not (_on_talk and _on_talk()):
            self.open_ask()

    def _spot_at(self, point):
        """Screen point -> which part of her body is there (or None)."""
        local = point - self.pos()
        return body_spot(local.x() / self.width() * 200, local.y() / self.height() * 216)

    def _poke(self):
        self._react_to(self._spot_at(self._poke_at))

    def _react_to(self, spot):
        now = time.time()
        if spot is None or now < self._huff_until:
            return                       # Empty space, or she is still huffy and ignoring you
        self._wary = False               # A poke replaces the wary look
        self._poke_times = [t for t in self._poke_times if now - t < 6] + [now]
        if len(self._poke_times) >= ANNOYED_AFTER:
            self._poke_times, self._huff_until = [], now + HUFF_SECONDS
            spot, ms = "huff", HUFF_SECONDS * 1000
        else:
            ms = 1700 if spot == "head" else 1000
        self._js(f"Orange.react({json.dumps(spot)}, {ms})")
        self.show_bubble(random.choice(POKE_LINES[spot.split("-")[0]]), 2.5)

    def _notice_stroke(self, here):
        """Rubbing the mouse left-right over her head (no button pressed) = a pat."""
        s, now = self._stroke, time.time()
        if self._spot_at(here) not in ("head", "face") or now - s["since"] > 1.5:
            s.update(x=here.x(), dir=0, turns=0, since=now)      # left her head, or too slow: start over
            return
        step = here.x() - s["x"]
        if abs(step) < 4:
            return                       # Too small a wiggle to count
        direction = 1 if step > 0 else -1
        if s["dir"] and direction != s["dir"]:
            s["turns"] += 1              # The mouse changed direction: one "rub"
        s.update(x=here.x(), dir=direction, since=now)
        if s["turns"] >= 3:
            s.update(dir=0, turns=0)
            self._poke_times = []        # Pats are nice; they don't count as poking
            if now >= self._huff_until:
                self._js('Orange.react("head", 1700)')
                self.show_bubble(random.choice(POKE_LINES["head"]), 2.5)

    # ----- being carried: dangling, shaking, squashing against edges, landing -----

    def _hold(self, look):
        """Keep a reaction on until we change it (see section 3c of orange.css)."""
        self._js(f"Orange.react({json.dumps(look)}, 0)")

    def _begin_carry(self):
        now = time.time()
        self._wary = False
        self._carry = {"start": now, "last": self.pos(), "last_t": now, "still": 0.0,
                       "dist": 0.0,      # total pixels she has been moved
                       "dir": 0, "flips": [],   # left/right direction changes (for shaking)
                       "fast": 0.0,      # seconds spent moving really fast (for dizziness)
                       "shaken": False, "look": "carried"}
        self._hold("carried")
        self.show_bubble(random.choice(CARRY_LINES), 2.5)
        self._carry_timer.start()

    def _carry_tick(self):
        c, now, pos = self._carry, time.time(), self.pos()
        if c is None:
            self._carry_timer.stop()
            return
        dt = max(now - c["last_t"], 0.001)
        dx, dy = pos.x() - c["last"].x(), pos.y() - c["last"].y()
        step = (dx * dx + dy * dy) ** 0.5
        c["dist"] += step
        c["still"] = 0.0 if step else c["still"] + dt
        if step / dt > 1500:                     # faster than 1500 pixels a second
            c["fast"] += dt
        if abs(dx) > 10:
            direction = 1 if dx > 0 else -1
            if c["dir"] and direction != c["dir"]:
                c["flips"] = [t for t in c["flips"] if now - t < 1.5] + [now]
            c["dir"] = direction
        if not c["shaken"] and len(c["flips"]) >= 5:     # 5 quick left-right turns = a shake
            c["shaken"] = True
            self.show_bubble(random.choice(SHAKE_LINES), 2.5)
        c["last"], c["last_t"] = pos, now

        side = self._edge_pushed()
        look = "squash-" + side if side else "glitch" if c["shaken"] else "carried"
        if look != c["look"]:
            c["look"] = look
            self._hold(look)

        # Let go? On Windows we can ask directly. Elsewhere: "hasn't moved for a moment".
        let_go = (not left_button_down()) if sys.platform == "win32" else c["still"] > 0.4
        if let_go and now - c["start"] > 0.15:
            self._end_carry()

    def _edge_pushed(self):
        """Which screen edge is her BODY pressed into? ("left", "right", "top", "bottom" or None)

        The window has empty space around her, so the window may poke out a little
        before her body actually touches the edge.
        """
        box, screen = self.geometry(), self.screen().availableGeometry()   # screen minus the taskbar
        if box.left() < screen.left() - 0.18 * WIDTH:
            return "left"
        if box.right() > screen.right() + 0.18 * WIDTH:
            return "right"
        if box.top() < screen.top() - 0.12 * HEIGHT:
            return "top"
        if box.bottom() > screen.bottom() + 0.08 * HEIGHT:
            return "bottom"
        return None

    def _end_carry(self):
        c, self._carry = self._carry, None
        self._carry_timer.stop()
        # If she was pushed past an edge, pop her back fully onto the screen.
        screen = self.screen().availableGeometry()
        x = max(screen.left(), min(self.x(), screen.right() - WIDTH))
        y = max(screen.top(), min(self.y(), screen.bottom() - HEIGHT))
        if (x, y) != (self.x(), self.y()):
            self.move(x, y)

        if c["shaken"]:
            self._js('Orange.react("dazed", 3500)')
            self.show_bubble("Bzzt... everything is wobbly...", 3)
        elif c["fast"] >= 0.5:
            self._js('Orange.react("dizzy", 3500)')
            self.show_bubble("Wheee... the room is spinning...", 3)
        else:
            self._js('Orange.react("land", 800)')
            if c["dist"] > 300:              # A long trip gets an "oof"
                self.show_bubble(random.choice(["Oof!", "Phew, solid ground.", "Boing!"]), 2)
            else:
                self.bubble.hide()

    # ----- looming: she grows to fill the screen for a few seconds, then shrinks back -----

    def loom(self, seconds):
        """Used when she hides a distracting window: for a moment she is impossible to ignore."""
        if self._big or self._carry is not None:
            return
        self._big, self._wary = True, False
        self._small_box = self.geometry()
        whole = self.screen().geometry()
        # One pixel short of the full screen on purpose: when a see-through window covers the
        # screen EXACTLY, Windows may switch to a "full-screen app" mode and paint it black.
        self.setGeometry(whole.x(), whole.y(), whole.width(), whole.height() - 1)
        self.raise_()
        self._js('Orange.react("loom", 0)')
        QTimer.singleShot(int(seconds * 1000), self._shrink)

    def _shrink(self):
        self._js('Orange.react("shrink", 0)')        # a quick shrinking animation first...
        QTimer.singleShot(280, self._back_to_small)

    def _back_to_small(self):
        self.setGeometry(self._small_box)            # ...then the window itself goes back
        self._big = False
        self._js("Orange.calm()")
        if self.bubble.isVisible():
            self.bubble.place_above(self)

    # ----- the mouse hovering close: she leans away and eyes it -----

    def _notice_hover(self, mouse, centre):
        now = time.time()
        busy = (self._big or self._carry is not None or self.ask.isVisible() or now < self._huff_until
                or _wanted_mood == "sleepy" or left_button_down())
        distance = ((mouse.x() - centre.x()) ** 2 + (mouse.y() - centre.y()) ** 2) ** 0.5
        if self._wary:
            if busy or distance > 150 * WIDTH / 220:       # The mouse went away (or something else is happening)
                self._wary, self._wary_rest = False, now + 4
                if self._carry is None:
                    self._js("Orange.calm()")
            return
        if busy or distance > 115 * WIDTH / 220 or now < self._wary_rest:
            self._hover = None
            return
        h = self._hover
        if h is None or abs(mouse.x() - h[0]) + abs(mouse.y() - h[1]) > 10:
            self._hover = (mouse.x(), mouse.y(), now)    # The mouse moved: restart the wait
        elif now - h[2] >= 1.2:                          # Resting close to her for 1.2 seconds
            self._wary, self._hover = True, None
            self._hold("wary-left" if mouse.x() < centre.x() else "wary-right")
            if random.random() < 0.4:
                self.show_bubble(random.choice(WARY_LINES), 2.5)

    def _show_menu(self, where):
        menu = QMenu(self)
        menu.addAction("Type to Orange...").triggered.connect(self.open_ask)
        menu.addSeparator()
        # These menu items simply "type" a sentence for you.
        for label, sentence in [("Study 25 minutes", "study for 25 minutes"),
                                ("Study 45 minutes", "study for 45 minutes"),
                                ("Study 1 hour", "study for 1 hour"),
                                ("Take a 5 minute break", "break 5"),
                                ("Stop session", "stop")]:
            menu.addAction(label).triggered.connect(lambda _c=False, s=sentence: handle_text(s))
        menu.addSeparator()
        moods = menu.addMenu("Mood (test)")
        for mood in MOODS:
            # "m=mood" freezes the current value; without it every item would use the last mood.
            moods.addAction(mood).triggered.connect(lambda _c=False, m=mood: set_mood(m))
        moods.addSeparator()
        moods.addAction("fill the screen (5 s)").triggered.connect(lambda _c=False: self.loom(5))
        menu.addSeparator()
        menu.addAction("Quit").triggered.connect(QApplication.instance().quit)
        menu.exec(where)

    # ----- remembering where Orange sits -----

    def moveEvent(self, event):
        super().moveEvent(event)
        self._save_timer.start()         # (Re)start the half-second countdown
        if self.bubble.isVisible():
            self.bubble.place_above(self)   # The bubble follows Orange

    def _save_position(self):
        if self._big:
            return                       # Don't remember the full-screen moment as her "spot"
        try:
            STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            STATE_FILE.write_text(json.dumps({"x": self.x(), "y": self.y()}), encoding="utf-8")
        except OSError as err:
            print(f"Could not save Orange's position: {err}")

    def _restore_position(self):
        screen = QApplication.primaryScreen().availableGeometry()   # Screen minus the taskbar
        x = screen.right() - WIDTH - MARGIN
        y = screen.bottom() - HEIGHT - MARGIN
        try:
            saved = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            sx, sy = int(saved["x"]), int(saved["y"])
            # Only use the saved spot if it is still on a screen (a monitor may have been unplugged).
            if any(s.availableGeometry().contains(sx + WIDTH // 2, sy + HEIGHT // 2)
                   for s in QApplication.screens()):
                x, y = sx, sy
        except (OSError, ValueError, KeyError, TypeError):
            pass                         # No saved spot yet (first run), or the file is broken
        self.move(x, y)


# ---------- the remote control (safe to call from any thread) ----------

def set_mood(mood):
    """Change Orange's expression."""
    global _wanted_mood
    if mood not in MOODS:
        raise ValueError(f"Unknown mood '{mood}'. Use one of: {MOODS}")
    _wanted_mood = mood
    if _bridge is not None:
        _bridge.mood.emit(mood)


def say(text, seconds=0):
    """Show text in Orange's speech bubble. seconds=0 means "pick a good time for this length"."""
    if text and _bridge is not None:
        _bridge.say.emit(str(text), float(seconds))


def set_timer(text):
    """Show a small label under Orange, e.g. "DL 32:10". None or "" hides it."""
    if _bridge is not None:
        _bridge.timer.emit(text or "")


def handle_text(text):
    """Something was typed (or picked from the menu). Pass it to the brain, show the reply.

    The work happens in a helper thread, because Orange may need a few seconds to think
    and the window must keep moving meanwhile.
    """
    if _on_text is None:
        say("Nobody is listening to typed text yet.")
        return

    def work():
        try:
            reply = _on_text(text)
        except Exception as err:         # A bug in the brain must not close Orange's window
            print(f"Error while handling '{text}': {err!r}")
            reply = "Oops, something went wrong. Look at the terminal."
        say(reply)

    threading.Thread(target=work, daemon=True).start()


def loom(seconds=5):
    """Grow to fill the whole screen for a few seconds, then shrink back."""
    if _bridge is not None:
        _bridge.loom.emit(float(seconds))


def start_talking():
    """Same as a double-click on Orange. Used by the Ctrl+Space shortcut."""
    if _bridge is not None:
        _bridge.talk.emit()


def quit():
    """Close Orange's window."""
    if _bridge is not None:
        _bridge.quit.emit()


def run(background=None, on_text=None, on_talk=None, width=None):
    """Open the window and keep it alive. Returns only when Orange is closed.

    background: an optional function to run in a second thread while the window is open
                (the timer loop now, the voice loop later).
    on_text:    an optional function(text) -> reply, called when you type to Orange.
    width:      her width in pixels (smaller number = smaller Orange).
    on_talk:    an optional function() -> True/False, called on a double-click. It should make
                Orange listen and return True. If it returns False (or is missing), the text box opens.
    """
    global _bridge, _on_text, _on_talk, WIDTH, HEIGHT
    _on_text, _on_talk = on_text, on_talk
    if width:                            # Her size. The height follows, to keep her shape.
        WIDTH = max(90, min(int(width), 600))
        HEIGHT = round(WIDTH * 216 / 200)
    # Let Ctrl+C in the terminal close Orange (Qt would otherwise ignore it).
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    # sys.argv = the words typed to start the program. Qt's built-in browser needs at least
    # the program name from it, or it refuses to start.
    app = QApplication(sys.argv or ["orange"])
    window = PetWindow()
    _bridge = _Bridge()
    _bridge.mood.connect(window.apply_mood)
    _bridge.say.connect(window.show_bubble)
    _bridge.timer.connect(window.apply_timer)
    _bridge.quit.connect(app.quit)
    _bridge.talk.connect(window.start_talking)
    _bridge.loom.connect(window.loom)
    window.show()

    if background is not None:
        # daemon=True: this helper thread stops by itself when the window closes.
        threading.Thread(target=background, daemon=True).start()

    app.exec()          # The window's main loop. Blocks here until Quit.
    _bridge = None
