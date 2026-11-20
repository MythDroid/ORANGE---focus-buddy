"""Turns a sentence into a command, using simple pattern rules (no AI needed).

    parse("study DL for 45 minutes")
      -> {"kind": "study", "task": "DL", "seconds": 2700}

It does not matter whether the sentence was typed or spoken: speech-to-text gives
us a sentence, and it comes here the same way.

Kinds: subject_add, subject_switch, subject_archive, subject_list, allow, teach, untaught, taught_list, study, break, away, resume, stop, bye, thanks, how_are_you, remind, remember, recall, forget_notes,
       time_left, today (also "summary"), call_me, greet, unknown
("pause" comes back as kind away, what pause)
"""
import re
from datetime import datetime, timedelta

# --- number words -> digits, so "forty five minutes" works like "45 minutes" ---
_UNITS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
          "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
          "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19}
_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70,
         "eighty": 80, "ninety": 90}
_NUMBER_WORDS = re.compile(
    r"\b(?:(%s)(?:[\s-](%s))?|(%s))\b" % ("|".join(_TENS), "|".join(list(_UNITS)[:9]), "|".join(_UNITS)),
    re.I)


def _words_to_digits(text):
    text = re.sub(r"\bhalf an hour\b", "30 minutes", text, flags=re.I)
    text = re.sub(r"\ban hour and a half\b", "90 minutes", text, flags=re.I)
    text = re.sub(r"\ban? (hour|minute)\b", r"1 \1", text, flags=re.I)
    text = re.sub(r"\b(?:a )?couple of\b", "2", text, flags=re.I)

    def swap(m):
        if m.group(1):
            return str(_TENS[m.group(1).lower()] + (_UNITS[m.group(2).lower()] if m.group(2) else 0))
        return str(_UNITS[m.group(3).lower()])
    return _NUMBER_WORDS.sub(swap, text)


# --- durations: "45 minutes", "1 hour 20 min", "1.5 hours", "90s" ---
_PIECE = r"\d+(?:\.\d+)?\s*(?:hours?|hrs?|h|minutes?|mins?|m|seconds?|secs?|s)\b"
_DURATION = re.compile(r"(?:%s(?:\s*(?:and|,)\s*|\s+)?)+" % _PIECE, re.I)
_PIECE_PARTS = re.compile(r"(\d+(?:\.\d+)?)\s*([a-z]+)", re.I)


def find_duration(text):
    """Returns (seconds, start, end) for the first duration in the text, or None."""
    m = _DURATION.search(text)
    if not m:
        return None
    seconds = 0.0
    for number, unit in _PIECE_PARTS.findall(m.group(0)):
        unit = unit.lower()
        seconds += float(number) * (3600 if unit[0] == "h" else 60 if unit[0] == "m" else 1)
    return int(seconds), m.start(), m.end()


# --- clock times: "at 6:30 pm", "at 7" ---
_CLOCK = re.compile(r"\bat\s+(\d{1,2})(?:[:.](\d{2}))?\s*(a\.?m\.?|p\.?m\.?)?(?![\d:])", re.I)


def find_clock_time(text, now):
    """Returns (datetime, start, end) for "at 6:30 pm", or None. Always a time in the future."""
    m = _CLOCK.search(text)
    if not m:
        return None
    hour, minute = int(m.group(1)), int(m.group(2) or 0)
    if hour > 23 or minute > 59:
        return None
    half = (m.group(3) or "").replace(".", "").lower()
    if half:                                   # "am" or "pm" was said
        hours = [hour % 12 + (12 if half == "pm" else 0)]
    elif hour > 12 or hour == 0:               # 24-hour style, e.g. "at 18:30"
        hours = [hour]
    else:                                      # "at 7": morning or evening? whichever comes first
        hours = [hour % 12, hour % 12 + 12]
    options = []
    for h in hours:
        when = now.replace(hour=h, minute=minute, second=0, microsecond=0)
        options.append(when if when > now else when + timedelta(days=1))
    return min(options), m.start(), m.end()


# Things you leave your desk for.
_AWAY = (r"dinner|lunch|breakfast|brunch|snacks?|food|eat|tea|coffee|water|shower|bath|washroom|"
         r"restroom|bathroom|toilet|loo|walk|nap|class|college|shop|shopping|pray|pooja|gym|workout")

# Words people say around the task that are not the task itself.
_FILLER = re.compile(
    r"^(?:please|okay|ok|so|i am|i'm|i'll|i will|i have to|i need to|i want to|let's|let me|"
    r"going to|gonna|be|start|begin|set|a|the|timer|session|study session|studying|study|"
    r"focusing on|focus on|focus|working on|work on|work|doing|do|log(?:ged)? in|for|on|to|now)\b[\s,]*",
    re.I)


def _clean_task(text):
    text = text.strip(" .,!?")
    while True:                                # Peel filler words off the front, one at a time
        shorter = _FILLER.sub("", text, count=1)
        if shorter == text:
            break
        text = shorter
    text = re.sub(r"[\s,]*\b(?:for|and|then)$", "", text, flags=re.I)   # "... DL for" -> "DL"
    return text.strip(" .,!?")


def normalise(text):
    """ "Hey Orange, Food time!!" -> "food time". Used to compare what you say with taught phrases."""
    text = re.sub(r"^(?:hey\s+)?orange[\s,!.]*", "", text.strip(), flags=re.I)
    return re.sub(r"\s+", " ", _unquote(text).lower().strip(" .,!?"))


def _unquote(text):
    return text.strip().strip("\"'\u201c\u201d\u2018\u2019").strip()


def parse(text, now=None):
    """Sentence -> command dict. Unknown sentences give {"kind": "unknown"}."""
    now = now or datetime.now()
    text = _words_to_digits(text.strip())
    text = re.sub(r"^(?:hey\s+)?orange[\s,!.]*", "", text, flags=re.I)   # drop "Hey Orange,"
    low = text.lower().strip(" .!?")

    # --- teaching Orange: 'when I say food time, I mean I'm going for dinner' ---
    m = re.match(r"(?:when|if) i say (.+?),? (?:i mean|it means|that means|means) (.+)", text, re.I)
    if m:
        return {"kind": "teach", "how": "means", "trigger": normalise(m.group(1)), "value": _unquote(m.group(2))}
    m = re.match(r"(?:when|if) i say (.+?),? (?:you )?(?:say|reply|answer|tell me) (.+)", text, re.I)
    if m:
        return {"kind": "teach", "how": "reply", "trigger": normalise(m.group(1)), "value": _unquote(m.group(2))}
    if re.search(r"\bwhat (?:did|have) i (?:teach|taught) you\b|\bshow (?:my )?phrases\b", low):
        return {"kind": "taught_list"}
    m = re.match(r"(?:forget|unlearn) (?:the )?phrase (.+)", text, re.I)
    if m:
        return {"kind": "untaught", "trigger": normalise(m.group(1))}

    # --- subjects (named buckets, e.g. "Machine Learning") ---
    m = re.match(r"(?:please\s+)?(?:add|new|create|make)(?: a)?(?: new)? subject(?: called| named)?\s+(.+)", text, re.I)
    if m:
        return {"kind": "subject_add", "name": _unquote(m.group(1)).strip(" .!?")}
    m = re.match(r"(?:please\s+)?(?:switch|change|move)(?: the)?(?: subject)? to\s+(.+)", text, re.I)
    if m:
        return {"kind": "subject_switch", "name": _unquote(m.group(1)).strip(" .!?")}
    m = re.match(r"(?:please\s+)?archive(?: the)?(?: subject)?\s+(.+)", text, re.I)
    if m:
        return {"kind": "subject_archive", "name": _unquote(m.group(1)).strip(" .!?")}
    if re.fullmatch(r"(?:what are |show |list )?(?:my |the )?subjects", low):
        return {"kind": "subject_list"}

    # --- "this is for study": Orange was wrong about a distraction ---
    if re.search(r"\b(?:this|that|it)(?: is|'s| was)? (?:for|part of|related to) (?:my |the |our )?"
                 r"(?:stud\w*|work|class|session|project|course|exam|task)\b"
                 r"|\bnot (?:a )?distract\w*|\bi need (?:this|that|it)\b|\bleave (?:it|that|this) alone\b", low):
        return {"kind": "allow"}

    if re.search(r"\bwhat (?:do|did) (?:you remember|i tell you)|\bshow (?:my )?notes\b", low):
        return {"kind": "recall"}
    if re.fullmatch(r"forget (?:everything|all|my notes|all (?:my )?notes)", low):
        return {"kind": "forget_notes"}

    m = re.match(r"(?:please\s+)?remind me\b\s*(.*)", text, re.I)
    if m:
        rest, when = m.group(1), None
        found = find_duration(rest)
        if found:
            seconds, a, b = found
            when = now + timedelta(seconds=seconds)
            a = re.search(r"(?:\b(?:in|after)\s+)?$", rest[:a], re.I).start()   # also cut "in"/"after"
            rest = rest[:a] + " " + rest[b:]
        else:
            found = find_clock_time(rest, now)
            if found:
                when, a, b = found
                rest = rest[:a] + " " + rest[b:]
        what = re.sub(r"^\s*(?:to|that|about)\b\s*", "", rest.strip(" .,!?"), flags=re.I).strip(" .,!?")
        return {"kind": "remind", "text": what, "when": when}

    m = re.match(r"(?:please\s+)?remember (?:that\s+)?(.+)", text, re.I)
    if m:
        return {"kind": "remember", "text": m.group(1).strip()}

    m = re.match(r"(?:please\s+)?call me (.+)", text, re.I)
    if m:
        return {"kind": "call_me", "name": m.group(1).strip(" .!?")}

    if re.search(r"\bhow (?:much|long) (?:did|have) i (?:stud\w+|focus\w*|work\w*)", low) \
            or re.search(r"\bsummary\b|\bhow (?:did|was) (?:my )?(?:day|today)\b", low):
        return {"kind": "today"}
    if re.fullmatch(r"(?:please )?(?:pause|hold)(?: it| the| my)?(?: session| timer| studying| study)?(?: please)?", low):
        return {"kind": "away", "what": "pause"}     # a pause with no time limit, until "resume"
    if re.search(r"\b(?:how (?:long|much time)|time left|time remaining)\b", low):
        return {"kind": "time_left"}
    if re.fullmatch(r"(?:i'm |i am )?(?:stop|end|finish|finished|done|cancel|quit)"
                    r"(?: it| the| my)?(?: session| studying| timer| study)?", low):
        return {"kind": "stop"}
    if re.fullmatch(r"(?:okay |ok )?(?:i'm |i am |im )?(?:resume|continue|back|back now|here|break over|end break|done eating)"
                    r"|(?:let's |lets )?(?:continue|resume|start again)", low):
        return {"kind": "resume"}

    # --- stepping away: "I'm gonna go have dinner", "brb", "going for a shower" ---
    if re.search(r"\bgood ?night\b|\b(?:go|going|gonna go|off) to (?:sleep|bed)\b|^(?:bye|goodbye|see you)\b", low):
        return {"kind": "bye"}
    m = (re.search(r"\b(?:go|going|gonna|gotta|have to|need to|off to|leaving|heading|time)\b.*?\b(%s)\b" % _AWAY, low)
         or re.match(r"(%s) time\b" % _AWAY, low))
    if m or re.search(r"\b(?:brb|be right back|(?:i'?ll|i will) be back|stepping (?:out|away)|going out)\b", low):
        found = find_duration(text)
        if found:                                   # "going for dinner for 30 minutes" = a timed break
            return {"kind": "break", "seconds": found[0]}
        return {"kind": "away", "what": m.group(1) if m else ""}

    if re.search(r"\b(?:thanks|thank you|thank u)\b", low):
        return {"kind": "thanks"}
    if re.search(r"\bhow are (?:you|u)\b|\bhow(?:'s| is) it going\b", low):
        return {"kind": "how_are_you"}

    if re.search(r"\b(?:done|finished|over) (?:with )?(?:my |the )?(?:eating|food|meal|call|%s)\b" % _AWAY, low):
        return {"kind": "resume"}                   # "I'm done with my food" = I'm back

    found = find_duration(text)
    lone = None if found else re.search(r"\b(\d{1,3})$", low)   # "focus 45" = 45 minutes

    if re.search(r"\bbreak\b", low):
        seconds = found[0] if found else int(lone.group(1)) * 60 if lone else 5 * 60
        return {"kind": "break", "seconds": seconds}

    if found or (lone and re.match(r"(?:study|focus|timer|work)\b", low)):
        if found:
            seconds, a, b = found
            task = _clean_task(text[:a] + " " + text[b:])
        else:
            seconds = int(lone.group(1)) * 60
            task = _clean_task(text[:lone.start() + (len(text) - len(text.lstrip()))])
        return {"kind": "study", "task": task or "study", "seconds": seconds}

    if re.match(r"(?:hi|hello|hey|hii+|good (?:morning|afternoon|evening))\b", low):
        return {"kind": "greet"}
    return {"kind": "unknown"}


def mentions_a_time(text):
    """True if the sentence really contains a length of time or a clock time ("45 minutes", "at 6").

    Used to double-check the brain, which sometimes invents a time nobody said.
    """
    text = _words_to_digits(text)
    return bool(find_duration(text) or _CLOCK.search(text) or re.search(r"\b\d+\b", text))
