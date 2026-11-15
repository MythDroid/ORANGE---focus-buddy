"""Shows Orange's window and walks through every mood, 5 seconds each.

Run from the ORANGE folder (with the venv active):   python demo_face.py
Right-click Orange -> Quit to close it (or press Ctrl+C in the terminal).
"""
import time

from orange import face


def show_all_moods():
    time.sleep(2)                      # Give the window a moment to appear
    for mood in face.MOODS:
        print(f"Mood: {mood}")
        face.set_mood(mood)
        time.sleep(5)
    face.set_mood("idle")
    print("Demo done. Orange stays on screen: drag it, or right-click for the menu.")


if __name__ == "__main__":
    face.run(background=show_all_moods)
