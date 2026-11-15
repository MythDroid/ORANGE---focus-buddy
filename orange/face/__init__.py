"""Orange's face: the little see-through window with the Soft Bot in it.

How other code uses it (this is the whole "remote control"):

    from orange import face

    face.set_mood("happy")        # change the expression
    face.say("5 minutes left!")   # speech bubble
    face.set_timer("DL 32:10")    # small label under Orange (None hides it)
    face.start_talking()          # same as a double-click on her
    face.loom(5)                  # fill the whole screen for 5 seconds, then shrink back
    face.run(background=my_loop, on_text=my_answer_function)   # open the window

All of these are safe to call from any thread.

Why run() works this way: a window toolkit (Qt) must own the program's MAIN
thread, and run() does not return until Orange is closed. So anything else
(the timer loop, later the voice loop) is passed in as `background` and runs in
a second thread. That way the window never freezes while Orange listens or thinks.
"""
from orange.face.window import MOODS, loom, quit, run, say, set_mood, set_timer, start_talking

__all__ = ["MOODS", "run", "set_mood", "say", "set_timer", "start_talking", "loom", "quit"]
