"""Study mode: Orange's "what do I do now" logic. No window code and no AI in here.

The Buddy class is a small brain made of plain rules:
    reply = buddy.handle("study DL for 45 minutes")   # you said or typed something
    update = buddy.tick()                              # called about twice a second

handle() returns the words Orange answers with.
tick() returns what Orange should look like RIGHT NOW: its mood, the timer text,
and anything it wants to say by itself ("5 minutes left!", a reminder, "time's up").

Because this file never touches the window, it can be tested without one, and the
same Buddy will work when the voice is plugged in later.
"""
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from orange import commands

MAX_SESSION_SECONDS = 10 * 3600      # Nobody studies 10 hours without a break
SLEEPY_AFTER = timedelta(minutes=10)  # Nothing happening for this long = Orange dozes off
WARN_BEFORE_END = 5 * 60             # "5 minutes left!"


@dataclass
class Update:
    mood: str
    timer: str | None                 # Text under Orange, e.g. "DL 32:10". None = no timer
    says: list = field(default_factory=list)


def nice_duration(seconds):
    """2700 -> "45 minutes", 4800 -> "1 hour 20 minutes"."""
    minutes = max(1, round(seconds / 60)) if seconds >= 60 else 0
    if minutes == 0:
        return f"{int(seconds)} seconds"
    hours, minutes = divmod(minutes, 60)
    parts = []
    if hours:
        parts.append(f"{hours} hour" + ("s" if hours != 1 else ""))
    if minutes:
        parts.append(f"{minutes} minute" + ("s" if minutes != 1 else ""))
    return " ".join(parts)


def short_duration(seconds):
    """6000 -> "1 h 40 m", 2700 -> "45 m". For the summary, where space is tight."""
    minutes = int(round(seconds / 60))
    if minutes < 1:
        return "under 1 m"
    hours, minutes = divmod(minutes, 60)
    return f"{hours} h {minutes} m" if hours and minutes else f"{hours} h" if hours else f"{minutes} m"


def clock(seconds):
    """125 -> "2:05", 3725 -> "1:02:05"."""
    seconds = max(0, int(seconds))
    h, rest = divmod(seconds, 3600)
    m, s = divmod(rest, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


class Buddy:
    def __init__(self, store, default_name="friend", brain=None):
        self.store = store
        self.brain = brain            # orange.brain, or None = rules only
        self.on_allow = None          # Set by pet.py: what to do when you say "this is for study"
        self.default_name = default_name
        self.session = None           # dict while a study session runs, else None
        self.break_until = None       # datetime while on a timed break
        self.paused_at = None         # datetime while you are away ("going for dinner"), no end time
        self.flash = None             # (mood, until): a short reaction, e.g. celebrating for 8 s
        self.last_active = datetime.now()
        self._lock = threading.RLock()   # handle() and tick() are called from different threads

    @property
    def name(self):
        return self.store.get_setting("call_me", self.default_name)

    # ---------- starting up ----------

    def start(self, now=None):
        """Call once at startup. Picks up a session that was running when Orange was closed."""
        now = now or datetime.now()
        with self._lock:
            self.last_active = now
            row = self.store.active_session()
            if row is None:
                return f"Hi {self.name}! Click me and tell me what we're studying."
            paused = self.store.get_setting("paused_at", "")
            if row["ends_at"] <= now and not paused:
                self.store.finish_session(row["id"], "done", row["ends_at"], row["planned_seconds"])
                return f"Hi {self.name}! Your {row['task']} session finished while I was away."
            self.session = {"id": row["id"], "task": row["task"], "planned": row["planned_seconds"],
                            "ends_at": row["ends_at"], "warned": False}
            if paused:                # You were away when Orange was closed: stay paused
                self.paused_at = datetime.fromisoformat(paused)
                return f"Hi {self.name}! {row['task']} is paused. Say \"I'm back\" when you're ready."
            left = (row["ends_at"] - now).total_seconds()
            return f"I'm back! {nice_duration(left)} of {row['task']} left. Let's go!"

    # ---------- you said / typed something ----------

    def handle(self, text, now=None):
        fixed_now = now               # Only tests pass a time; normally we read the clock
        now = now or datetime.now()
        with self._lock:
            self.last_active = now
            # 1. Is it a sentence you taught me?
            taught = self.store.find_phrase(commands.normalise(text))
            if taught and taught["kind"] == "reply":
                self._react("happy", 3, now)
                return taught["value"]
            if taught:                       # "means": swap in the sentence it stands for
                text = taught["value"]
            # 2. Do the built-in rules know it?
            cmd = commands.parse(text, now)
            if cmd["kind"] != "unknown" or self.brain is None or not self.brain.enabled():
                return getattr(self, "_do_" + cmd["kind"])(cmd, now)
            self._react("listening", 40, now)    # "thinking" face while the brain works
            name, studying = self.name, self.session["task"] if self.session else None

        # 3. Ask the brain. This can take a few seconds, so the lock is NOT held here:
        #    the timer keeps ticking while Orange thinks.
        idea = self.brain.understand(text, name, studying)

        with self._lock:
            now = fixed_now or datetime.now()
            self.flash = None
            if idea and not commands.mentions_a_time(text):
                idea["minutes"] = 0          # The brain made up a time you never said: ignore it
            cmd = self._from_brain(idea, now)
            return getattr(self, "_do_" + cmd["kind"])(cmd, now)

    def _from_brain(self, idea, now):
        """Turn the brain's answer into one of Orange's normal commands."""
        if not idea:
            return {"kind": "unknown"}
        action, minutes = idea["action"], idea["minutes"]
        if action == "study":
            task = idea["task"] or "study"
            if minutes <= 0:
                return {"kind": "say", "mood": "listening",
                        "text": f"How long shall we do {task}? Say: {task} for 45 minutes"}
            return {"kind": "study", "task": task, "seconds": int(minutes * 60)}
        if action == "break":
            return {"kind": "break", "seconds": int(minutes * 60) if minutes > 0 else 300}
        if action == "away":
            return {"kind": "away", "what": idea["text"].lower()}
        if action == "back":
            return {"kind": "resume"}
        if action == "remind":
            when = now + timedelta(minutes=minutes) if minutes > 0 else None
            return {"kind": "remind", "text": idea["text"], "when": when}
        if action == "remember" and idea["text"]:
            return {"kind": "remember", "text": idea["text"]}
        # Small models sometimes put the chat line in "text" instead of "reply". Accept both.
        if action == "chat" and (idea["reply"] or idea["text"]):
            return {"kind": "say", "mood": "happy", "text": idea["reply"] or idea["text"]}
        if action in ("stop", "time_left", "today", "greet", "bye", "thanks"):
            return {"kind": action}
        return {"kind": "unknown"}

    def _do_say(self, cmd, now):
        self._react(cmd["mood"], 4, now)
        return cmd["text"]

    # ---------- you teaching Orange ----------

    def _do_teach(self, cmd, now):
        trigger, value = cmd["trigger"], cmd["value"]
        if not trigger or not value:
            return "Tell me both parts: when I say ___, I mean ___"
        if cmd["how"] == "means" and commands.parse(value, now)["kind"] in ("unknown", "teach"):
            self._react("confused", 5, now)
            return (f"I can't learn that, because I don't understand \"{value}\" either.\n"
                    "The second part must be something I already know.")
        self.store.teach_phrase(trigger, cmd["how"], value)
        self._react("amazed", 3, now)
        return f"Learned it! When you say \"{trigger}\", I'll know."

    def _do_taught_list(self, cmd, now):
        phrases = self.store.all_phrases()
        if not phrases:
            return "You haven't taught me any phrases yet.\nTry: when I say food time, I mean I'm going for dinner"
        arrow = {"means": "means", "reply": "I say"}
        return "You taught me:\n" + "\n".join(f"- {p['trigger']} ({arrow[p['kind']]}: {p['value']})" for p in phrases)

    def _do_untaught(self, cmd, now):
        if self.store.forget_phrase(cmd["trigger"]):
            return f"Okay, I've forgotten \"{cmd['trigger']}\"."
        return f"I don't know the phrase \"{cmd['trigger']}\"."

    def focus_task(self):
        """What you should be doing right now, or None (no session / break / paused). For the watch."""
        with self._lock:
            if self.session and not self.break_until and not self.paused_at:
                return self.session["task"]
            return None

    def note_distraction(self):
        with self._lock:
            if self.session:
                self.store.add_distraction(self.session["id"])

    def _do_allow(self, cmd, now):
        if self.on_allow is None:
            return "I'm not watching your windows right now, so you're all good."
        self._react("happy", 3, now)
        return self.on_allow()

    def show(self, mood, seconds=30):
        """Other parts (the voice) can ask for a face for a while. show(None) cancels it."""
        with self._lock:
            self.last_active = datetime.now()
            self.flash = (mood, self.last_active + timedelta(seconds=seconds)) if mood else None

    def _react(self, mood, seconds, now):
        self.flash = (mood, now + timedelta(seconds=seconds))

    # ---------- subjects ----------

    def current_subject(self):
        name = self.store.get_setting("current_subject", "")
        row = self.store.find_subject(name) if name else None
        return row["name"] if row and not row["archived"] else None

    def _use_subject(self, name, now):
        """Find this subject (any capitals) or create it, bring it back if archived, make it current.
        Returns (the name as saved, a short note for the reply)."""
        row = self.store.find_subject(name)
        note = ""
        if row is None:
            self.store.add_subject(name, now)
            row, note = self.store.find_subject(name), f"New subject: {name}. "
        elif row["archived"]:
            self.store.set_archived(row["name"], False)
            note = f"Brought {row['name']} back from the archive. "
        self.store.set_setting("current_subject", row["name"])
        return row["name"], note

    def _do_subject_add(self, cmd, now):
        return self.subject_action("add", cmd["name"], now)

    def _do_subject_switch(self, cmd, now):
        return self.subject_action("switch", cmd["name"], now)

    def _do_subject_archive(self, cmd, now):
        return self.subject_action("archive", cmd["name"], now)

    def _do_subject_list(self, cmd, now):
        names, current = self.store.list_subjects(), self.current_subject()
        if not names:
            return "No subjects yet. Say: add subject Machine Learning"
        return "Your subjects:\n" + "\n".join(("  \u2713 " if n == current else "  \u2022 ") + n for n in names)

    def subjects_menu(self):
        """For the right-click menu: what to list. Safe to call from the window."""
        with self._lock:
            active, archived = self.store.list_subjects(), self.store.list_subjects(archived=True)
            return {"current": self.current_subject(), "active": active, "archived": archived,
                    "seconds": {n: self.store.total_seconds_for(n) for n in active + archived}}

    def subject_action(self, action, name, now=None):
        """add / switch / archive / unarchive / delete a subject. Returns Orange's reply."""
        now = now or datetime.now()
        name = (name or "").strip()
        if not name:
            return "Which subject? Say the name too."
        with self._lock:
            self.last_active = now
            row = self.store.find_subject(name)
            running = self.session and self.session["task"].lower() == name.lower()

            if action in ("add", "switch"):
                if action == "switch" and row is None:
                    self._react("confused", 4, now)
                    return f"I don't have a subject called {name}. Say: add subject {name}"
                if action == "add" and row is not None and not row["archived"]:
                    saved, note = self._use_subject(name, now)
                    return f"{saved} is already a subject. You're on it now."
                return self._switch_to(name, now)

            if row is None:
                return f"I don't have a subject called {name}."
            name = row["name"]
            if action in ("archive", "delete") and running:
                self._react("confused", 4, now)
                return f"{name}'s timer is running. Stop it or switch subjects first."
            if action == "archive":
                self.store.set_archived(name, True)
                if self.current_subject() is None:
                    self.store.set_setting("current_subject", "")
                return f"Archived {name}. Its history is kept; find it under Subjects \u2192 Archived."
            if action == "unarchive":
                self.store.set_archived(name, False)
                return f"{name} is back in your subjects."
            if action == "delete":
                self.store.delete_subject(name)
                if self.store.get_setting("current_subject", "").lower() == name.lower():
                    self.store.set_setting("current_subject", "")
                return f"Deleted {name} and its history."
            return "I don't know how to do that."

    def _switch_to(self, name, now):
        """Make this subject current. If a timer is running, its minutes so far are saved to the
        old subject and the rest of the timer carries on for the new one."""
        saved, note = self._use_subject(name, now)
        self._react("happy", 3, now)
        if not self.session or self.session["task"].lower() == saved.lower():
            return f"{note}You're on {saved} now. Say \"study for 45 minutes\" to start."
        if self.break_until:
            self._do_resume({}, now, quiet=True)
        was_paused = self.paused_at is not None
        left = self._remaining(now)
        old, done = self.session["task"], self._end_session("stopped", now)
        ends_at = now + timedelta(seconds=left)
        sid = self.store.start_session(saved, int(left), now, ends_at)
        self.session = {"id": sid, "task": saved, "planned": int(left), "ends_at": ends_at,
                        "warned": left <= WARN_BEFORE_END}
        if was_paused:
            self._set_pause(now)               # still paused, now on the new subject
        return (f"{note}Saved {nice_duration(done)} to {old}.\n"
                f"Now on {saved}, {nice_duration(left)} left.")

    # ---------- study sessions ----------

    def _do_study(self, cmd, now):
        seconds = cmd["seconds"]
        if seconds < 60 or seconds > MAX_SESSION_SECONDS:
            self._react("confused", 5, now)
            return "A session should be between 1 minute and 10 hours. Try: study DL for 45 minutes"
        note = ""
        if cmd["task"] == "study":                # no subject said: use the current one
            cmd["task"] = self.current_subject() or "study"
        else:                                     # a subject was said: find it or create it
            cmd["task"], note = self._use_subject(cmd["task"], now)
        swapped = ""
        if self.session:
            self._end_session("stopped", now)
            swapped = "Switching! "
        ends_at = now + timedelta(seconds=seconds)
        sid = self.store.start_session(cmd["task"], seconds, now, ends_at)
        self.session = {"id": sid, "task": cmd["task"], "planned": seconds, "ends_at": ends_at,
                        "warned": seconds <= 2 * WARN_BEFORE_END}   # short sessions get no warning
        self.break_until = None
        self._set_pause(None)
        self._react("happy", 3, now)
        what = "studying" if cmd["task"] == "study" else cmd["task"]
        return f"{note}{swapped}Okay {self.name}! {nice_duration(seconds)} of {what}. I'll study with you."

    def _do_break(self, cmd, now):
        seconds = max(60, min(cmd["seconds"], 3600))
        if not self.session:
            self.store.add_reminder("Break's over!", now + timedelta(seconds=seconds), now)
            return f"Enjoy your {nice_duration(seconds)} break. I'll call you."
        if self.break_until or self.paused_at:
            self._do_resume(cmd, now, quiet=True)
        self.break_until = now + timedelta(seconds=seconds)
        self.session["ends_at"] += timedelta(seconds=seconds)     # the break doesn't eat study time
        self.store.move_session_end(self.session["id"], self.session["ends_at"])
        self._react("happy", 3, now)
        return f"Break time! {nice_duration(seconds)}. Stretch and drink some water."

    def _do_away(self, cmd, now):
        """ "I'm gonna go have dinner" or "pause": pause the session with no end time, until "I'm back"."""
        what = cmd["what"]
        if what == "pause":                       # the Pause button, or saying "pause"
            if not self.session:
                self._react("confused", 3, now)
                return "There's no timer running to pause."
            if self.paused_at:
                return f"{self.session['task']} is already paused.\nRight-click me and pick Resume when you're ready."
            if self.break_until:
                self._do_resume(cmd, now, quiet=True)
            self._set_pause(now)
            self._react("happy", 3, now)
            return (f"Paused {self.session['task']} with {nice_duration(self._remaining(now))} left.\n"
                    "Right-click me and pick Resume when you're ready.")
        meals = ("dinner", "lunch", "breakfast", "brunch", "snack", "snacks", "food", "tea", "coffee")
        wish = f"Enjoy your {what}" if what in meals else "Enjoy" if what == "eat" else "Okay"
        self._react("happy", 3, now)
        if not self.session:
            return f"{wish}, {self.name}! I'll be right here."
        if self.break_until:
            self._do_resume(cmd, now, quiet=True)
        if not self.paused_at:
            self._set_pause(now)
        return (f"{wish}, {self.name}! I've paused {self.session['task']}.\n"
                "Say \"I'm back\" when you return.")

    def _set_pause(self, when):
        self.paused_at = when
        self.store.set_setting("paused_at", when.isoformat() if when else "")   # survives a restart

    def _do_resume(self, cmd, now, quiet=False):
        if self.session and self.paused_at:
            # Push the end time later by however long you were away.
            self.session["ends_at"] += now - self.paused_at
            self.store.move_session_end(self.session["id"], self.session["ends_at"])
            self._set_pause(None)
            self._react("happy", 3, now)
            return None if quiet else (f"Welcome back, {self.name}! "
                                       f"{nice_duration(self._remaining(now))} of {self.session['task']} left.")
        if not (self.session and self.break_until):
            self._react("happy", 3, now)
            return f"Welcome back, {self.name}!"
        unused = self.break_until - now                          # give back the unused break time
        if unused > timedelta(0):
            self.session["ends_at"] -= unused
            self.store.move_session_end(self.session["id"], self.session["ends_at"])
        self.break_until = None
        return None if quiet else f"Welcome back! On with {self.session['task']}."

    def _do_bye(self, cmd, now):
        note = ""
        if self.session and not self.paused_at:
            if self.break_until:
                self._do_resume(cmd, now, quiet=True)
            self._set_pause(now)
            note = f"\nI've paused {self.session['task']}."
        self._react("sleepy", 20, now)
        return f"Good night, {self.name}! Sleep well.{note}"

    def _do_thanks(self, cmd, now):
        self._react("happy", 3, now)
        return f"Anytime, {self.name}!"

    def _do_how_are_you(self, cmd, now):
        self._react("happy", 3, now)
        return "I'm good! Ready to study whenever you are."

    def _do_stop(self, cmd, now):
        if not self.session:
            return "There's no session running."
        task = self.session["task"]
        focused = self._end_session("stopped", now)
        return f"Okay, stopping. You did {nice_duration(focused)} of {task}."

    def _do_time_left(self, cmd, now):
        if not self.session:
            return "No session is running. Want to start one?"
        if self.paused_at:
            return f"Paused. {nice_duration(self._remaining(now))} of {self.session['task']} left."
        if self.break_until:
            return f"Break: {clock((self.break_until - now).total_seconds())} left."
        return f"{nice_duration(self._remaining(now))} left of {self.session['task']}."

    def _do_today(self, cmd, now):
        """Today's summary: total focus time, then each subject, then distractions tucked away."""
        subjects = {}                             # "dl" -> [name as you typed it, seconds]
        tucked = 0
        for row in self.store.sessions_on(now.date()):
            if self.session and row["id"] == self.session["id"]:
                seconds = self._focused(now)      # still running: count it up to now
            elif row["status"] == "active":
                continue
            else:
                seconds = row["focused_seconds"]
            tucked += row["distractions"]
            name = "Studying" if row["task"] == "study" else row["task"]
            entry = subjects.setdefault(name.lower(), [name, 0])
            entry[1] += seconds
        total = sum(seconds for _, seconds in subjects.values())
        if total < 60:
            return "Nothing logged today yet. Shall we start?"
        self._react("happy", 3, now)
        lines = [f"Today: {short_duration(total)} of focus"]
        for name, seconds in sorted(subjects.values(), key=lambda e: -e[1]):
            if seconds < 60:
                continue
            ever = self.store.total_seconds_for(name)
            if self.session and self.session["task"].lower() == name.lower():
                ever += self._focused(now)
            row = self.store.find_subject(name)
            label = row["name"] if row else name
            extra = f"  ({short_duration(ever)} in total)" if ever - seconds >= 60 else ""
            lines.append(f"  \u2022 {label}: {short_duration(seconds)}{extra}")
        if tucked:
            lines.append(f"Distractions tucked away: {tucked}")
        return "\n".join(lines)

    def _do_remind(self, cmd, now):
        if cmd["when"] is None:
            self._react("confused", 5, now)
            return "When should I remind you? Try: remind me in 10 minutes to drink water"
        text = cmd["text"] or "Time's up!"
        self.store.add_reminder(text, cmd["when"], now)
        gap = (cmd["when"] - now).total_seconds()
        when = f"in {nice_duration(gap)}" if gap < 3600 else "at " + cmd["when"].strftime("%I:%M %p").lstrip("0")
        return f"Got it. I'll remind you {when}: {text}"

    def _do_remember(self, cmd, now):
        self.store.add_note(cmd["text"], now)
        return "Okay, I'll remember that."

    def _do_recall(self, cmd, now):
        notes = self.store.recent_notes(5)
        if not notes:
            return "You haven't asked me to remember anything yet."
        return "You told me:\n" + "\n".join("- " + n["text"] for n in notes)

    def _do_forget_notes(self, cmd, now):
        self.store.delete_notes()
        return "Done. I've forgotten all the notes."

    def _do_call_me(self, cmd, now):
        self.store.set_setting("call_me", cmd["name"])
        self._react("happy", 3, now)
        return f"Okay, {cmd['name']}!"

    def _do_greet(self, cmd, now):
        self._react("happy", 3, now)
        return f"Hi {self.name}! What are we studying?"

    def _do_unknown(self, cmd, now):
        self._react("confused", 6, now)
        return ("Hmm, I didn't get that. I understand things like:\n- study DL for 45 minutes\n"
                "- I'm going for dinner / I'm back\n- remind me in 10 minutes to drink water\n"
                "Or teach me: when I say ___, I mean ___")

    # ---------- session helpers ----------

    def _remaining(self, now):
        """Study seconds still to go. While paused or on a break the clock stands still."""
        start_from = self.paused_at or self.break_until or now
        return max(0.0, (self.session["ends_at"] - start_from).total_seconds())

    def _focused(self, now):
        return max(0.0, self.session["planned"] - self._remaining(now))

    def _end_session(self, status, now):
        focused = self.session["planned"] if status == "done" else self._focused(now)
        self.store.finish_session(self.session["id"], status, now, focused)
        self.session = None
        self.break_until = None
        self._set_pause(None)
        return focused

    # ---------- called about twice a second ----------

    def tick(self, now=None):
        now = now or datetime.now()
        with self._lock:
            says = []

            if self.session and self.break_until and now >= self.break_until:
                self.break_until = None
                self._react("happy", 3, now)
                says.append(f"Break's over! Back to {self.session['task']}.")

            if self.session and not self.break_until and not self.paused_at:
                left = self._remaining(now)
                if left <= 0:
                    task, planned = self.session["task"], self.session["planned"]
                    self._end_session("done", now)
                    self._react("celebrating", 8, now)
                    total = self.store.focused_seconds_on(now.date())
                    line = f"Time's up, {self.name}! {nice_duration(planned)} of {task} done."
                    if total > planned:
                        line += f"\nThat's {nice_duration(total)} today."
                    says.append(line)
                elif left <= WARN_BEFORE_END and not self.session["warned"]:
                    self.session["warned"] = True
                    self._react("amazed", 4, now)
                    says.append("5 minutes left!")

            for r in self.store.due_reminders(now):
                self.store.finish_reminder(r["id"])
                self._react("amazed", 6, now)
                self.last_active = now
                says.append("Reminder: " + r["text"])

            return Update(self._mood(now), self._timer_text(now), says)

    def _mood(self, now):
        if self.flash:
            mood, until = self.flash
            if now < until:
                return mood
            self.flash = None
        if self.session:
            if self.paused_at:
                return "sleepy"          # dozing while it waits for you
            return "idle" if self.break_until else "focused"
        return "sleepy" if now - self.last_active > SLEEPY_AFTER else "idle"

    def _timer_text(self, now):
        if not self.session:
            return None
        if self.paused_at:
            return "paused"
        if self.break_until:
            return "break " + clock((self.break_until - now).total_seconds())
        task = self.session["task"]
        label = task if len(task) <= 9 else task[:8] + "…"
        return f"{label} {clock(self._remaining(now))}"
