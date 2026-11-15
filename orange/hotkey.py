"""A keyboard shortcut that works from any app: Ctrl+Space = "Orange, listen".

Windows lets a program reserve ONE key combination for itself (RegisterHotKey).
While Orange runs, Ctrl+Space belongs to her and other apps don't see it. She does
NOT watch the rest of your keyboard: Windows only tells her about this one combination.

Windows only. On other systems start() does nothing.
"""
import ctypes
import sys
import threading

_CTRL, _NO_REPEAT, _SPACE = 0x0002, 0x4000, 0x20   # Windows' numbers for Ctrl, "don't repeat while held", Space
_WM_HOTKEY = 0x0312                                # The message Windows sends when the shortcut is pressed


def start(on_press):
    """Call on_press() every time Ctrl+Space is pressed. Returns at once (uses its own thread)."""
    if sys.platform != "win32":
        return

    def listen():
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        # The shortcut must be registered in the same thread that waits for it.
        if not user32.RegisterHotKey(None, 1, _CTRL | _NO_REPEAT, _SPACE):
            print("Ctrl+Space is already taken by another program, so the shortcut is off. "
                  "Double-click Orange instead.")
            return
        print("Shortcut ready: Ctrl+Space makes Orange listen.")
        message = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:   # Sleeps until a message comes
            if message.message == _WM_HOTKEY:
                try:
                    on_press()
                except Exception as err:
                    print(f"Shortcut error: {err!r}")

    threading.Thread(target=listen, daemon=True).start()
