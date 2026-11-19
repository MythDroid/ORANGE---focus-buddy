"""Orange's small brain: a language model that runs ON YOUR LAPTOP through Ollama.

What it is for: understanding sentences the rules in commands.py don't know.
    "I'm starving, gonna grab a bite"  ->  {"action": "away", "text": "food"}

What it is NOT for: answering study questions. It only picks one of Orange's own
actions, or writes one short friendly line. It cannot do anything else, because
the answer must fit the fixed form in _FORM below.

How it talks to the model: Ollama runs a tiny web server on your own laptop
(http://localhost:11434). We send it the sentence and get JSON text back.
"localhost" means "this computer", so nothing leaves your laptop.

If Ollama is closed or slow, every function here returns None and Orange simply
carries on with her rules, exactly as before.
"""
import json
import time
import urllib.error
import urllib.request

ACTIONS = ["study", "break", "away", "back", "stop", "remind", "remember",
           "time_left", "today", "greet", "bye", "thanks", "chat", "none"]

# The model MUST answer in this shape (Ollama enforces it), so we never get free text.
_FORM = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ACTIONS},
        "task": {"type": "string"},
        "minutes": {"type": "number"},
        "text": {"type": "string"},
    },
    "required": ["action", "task", "minutes", "text"],
}

_RULES = """You are the language part of Orange, a small cute study-buddy pet that lives on the user's screen.
Read what the user said and choose exactly ONE action. Answer only with JSON.

Actions:
- study: the user wants to start working on something. task = what, minutes = how long (0 if no time was said).
- break: the user wants a short timed break. minutes = how long (0 if not said).
- away: the user is leaving the desk for a while (food, shower, phone call, errand, class). text = what for, one word.
- back: the user has returned, or says they finished eating / their call / their shower.
- stop: the user wants to end the current session.
- remind: the user wants a reminder. text = what to remind, minutes = how many minutes from now (0 if not said).
- remember: the user wants a fact saved ("remember...", "don't forget...", "note that..."). text = the whole fact.
- time_left: the user asks how much time is left.
- today: the user asks how much they studied today.
- greet: hello. bye: good night or leaving for the day. thanks: thank you.
- chat: friendly small talk or feelings (tired, bored, happy, sad). text = ONE short kind sentence from Orange, at most 15 words, simple English.
- none: you cannot tell what the user wants.

Rules:
- Unused fields: task "", text "", minutes 0.
- Convert hours to minutes (1.5 hours = 90).
- You are NOT a tutor. If the user asks a study or general-knowledge question, use chat and say you can't explain it but you will study beside them.
- Never invent a time the user did not say.

Examples:
"lemme grind some DSA for an hour" -> {"action":"study","task":"DSA","minutes":60,"text":""}
"i want to revise probability" -> {"action":"study","task":"probability","minutes":0,"text":""}
"i'm starving, gonna grab a bite" -> {"action":"away","task":"","minutes":0,"text":"food"}
"mom is calling me" -> {"action":"away","task":"","minutes":0,"text":"call"}
"alright i'm done with my food" -> {"action":"back","task":"","minutes":0,"text":""}
"don't forget my record is due on friday" -> {"action":"remember","task":"","minutes":0,"text":"my record is due on Friday"}
"let's do some physics till dinner" -> {"action":"study","task":"physics","minutes":0,"text":""}
"ok i'm here again" -> {"action":"back","task":"","minutes":0,"text":""}
"enough for today" -> {"action":"stop","task":"","minutes":0,"text":""}
"ping me in 20 min to check the oven" -> {"action":"remind","task":"","minutes":20,"text":"check the oven"}
"i'm so tired today" -> {"action":"chat","task":"","minutes":0,"text":"Aww. Let's do a small bit together, then rest."}
"what is an eigenvalue" -> {"action":"chat","task":"","minutes":0,"text":"I can't explain that, but I'll sit and study it with you!"}
"""

_cfg = None
_think_switch = True     # Becomes False if this model has no "thinking" mode to turn off


def init(brain_cfg):
    """Call once at startup with the `brain.understand` section of config.yaml."""
    global _cfg
    _cfg = dict(brain_cfg or {})


def enabled():
    return bool(_cfg and _cfg.get("enabled"))


def _post(body):
    """Send one request to Ollama and return its answer as a dict."""
    request = urllib.request.Request(
        _cfg.get("url", "http://localhost:11434").rstrip("/") + "/api/chat",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=_cfg.get("timeout_seconds", 25)) as answer:
        return json.loads(answer.read().decode("utf-8"))


def _timing(answer):
    """Where did the time go? Ollama reports it in nanoseconds (1 second = 1,000,000,000)."""
    load, read, write = (answer.get(k, 0) / 1e9 for k in ("load_duration", "prompt_eval_duration", "eval_duration"))
    print(f"   brain timing: loading {load:.1f}s, reading the instructions {read:.1f}s "
          f"({answer.get('prompt_eval_count', 0)} pieces), writing the answer {write:.1f}s "
          f"({answer.get('eval_count', 0)} pieces)")


def _chat(messages, form=None):
    """Ask the model. Returns its text, or None if Ollama can't be reached."""
    global _think_switch
    body = {
        "model": _cfg.get("model", "qwen3.5:2b"),
        "messages": messages,
        "stream": False,                 # One complete answer, not word by word
        "keep_alive": "15m",             # Keep the model loaded for 15 quiet minutes (faster replies)
        "options": {
            "temperature": 0,            # 0 = no randomness: same sentence, same answer
            # How much text the model can hold at once. Smaller = less graphics-card memory,
            # so more of the model fits on the card and it answers faster.
            "num_ctx": int(_cfg.get("context", 2048)),
        },
    }
    if form:
        body["format"] = form
    if _think_switch:
        # Some models "think out loud" for a long time before answering.
        # Orange needs a quick answer, so we switch that off.
        body["think"] = False
    try:
        try:
            answer = _post(body)
        except urllib.error.HTTPError as err:
            if not (err.code == 400 and _think_switch):
                raise
            _think_switch = False        # This model has no thinking switch: ask without it
            body.pop("think", None)
            answer = _post(body)
        if _cfg.get("show_timing"):
            _timing(answer)
        return answer["message"]["content"]
    except Exception as err:             # Ollama closed, model missing, too slow, ...
        print(f"Brain not available ({err!r}). Orange is using her rules only.")
        return None


def understand(text, name="friend", studying=None):
    """Sentence -> {"action": ..., "task": ..., "minutes": ..., "text": ...}, or None."""
    if not enabled():
        return None
    now_doing = f"The user is in a study session on: {studying}." if studying else "No study session is running."
    started = time.time()
    raw = _chat([{"role": "system", "content": _RULES},
                 {"role": "user", "content": f"The user's name is {name}. {now_doing}\nThe user said: \"{text}\""}],
                form=_FORM)
    if raw is None:
        return None
    try:
        result = json.loads(raw)
    except ValueError:
        print(f"Brain gave something that is not JSON: {raw[:200]!r}")
        return None
    if not isinstance(result, dict) or result.get("action") not in ACTIONS:
        return None
    # Clean up the fields so the rest of Orange can trust them.
    try:
        minutes = float(result.get("minutes") or 0)
    except (TypeError, ValueError):
        minutes = 0.0
    clean = {"action": result["action"], "minutes": max(0.0, minutes)}
    for key in ("task", "text", "reply"):
        clean[key] = str(result.get(key) or "").strip()[:200]
    print(f"Brain ({time.time() - started:.1f}s): {text!r} -> {clean}")
    return clean


_JUDGE_FORM = {
    "type": "object",
    "properties": {"verdict": {"type": "string", "enum": ["on_task", "distracted", "unsure"]}},
    "required": ["verdict"],
}

_JUDGE_RULES = """A student is in a focus session. Decide if the browser page in front is a distraction. Answer only with JSON.
Be fair: most pages a student opens while studying are fine. Only call a page a distraction when it is clearly entertainment.
- distracted: clearly entertainment or time-wasting: shopping, social media feeds, cartoons, anime, TV shows, movies, web series, music videos, vlogs, comedy, memes, games, sports, gossip, or a video site's home feed.
- on_task: anything else that could be part of studying or working: class pages, notes, documents, PDFs, slides, email, college or course portals, coding sites, documentation, search results, AI chat assistants (whatever the chat is called), and videos clearly about a study subject. The page does NOT have to mention the task.
- unsure: you really cannot tell.
On video sites (YouTube and similar) a video is on_task only if its title is clearly about a study subject.
Examples:
task "machine learning", page "Backpropagation explained - YouTube", site "youtube.com" -> {"verdict":"on_task"}
task "machine learning", page "YouTube", site "youtube.com" -> {"verdict":"distracted"}
task "machine learning", page "Shinchan New Episode in Hindi - YouTube", site "youtube.com" -> {"verdict":"distracted"}
task "DSA", page "Doraemon full episode 12 - YouTube", site "unknown" -> {"verdict":"distracted"}
task "machine learning", page "Amazon.in : wireless earbuds", site "amazon.in" -> {"verdict":"distracted"}
task "DSA", page "Instagram", site "instagram.com" -> {"verdict":"distracted"}
task "machine learning", page "IPL live score", site "cricbuzz.com" -> {"verdict":"distracted"}
task "DL", page "Unit 1 - Google Classroom", site "classroom.google.com" -> {"verdict":"on_task"}
task "DL", page "Orange Software Pet Timer", site "chatgpt.com" -> {"verdict":"on_task"}
task "maths", page "Assignment 3 - Google Docs", site "unknown" -> {"verdict":"on_task"}
task "study", page "Inbox (3) - Gmail", site "mail.google.com" -> {"verdict":"on_task"}
task "DSA", page "Two Sum - LeetCode", site "leetcode.com" -> {"verdict":"on_task"}
task "drawing", page "Pinterest - character pose references", site "pinterest.com" -> {"verdict":"on_task"}
task "study", page "Unit 3 notes.pdf", site "unknown" -> {"verdict":"on_task"}
"""


def judge(task, title, app="", site=""):
    """Is this page a distraction? Returns "on_task", "distracted", "unsure", or None (no brain)."""
    if not enabled():
        return None
    raw = _chat([{"role": "system", "content": _JUDGE_RULES},
                 {"role": "user", "content": f'task "{task}", page "{title[:150]}", site "{site or "unknown"}"'}],
                form=_JUDGE_FORM)
    if raw is None:
        return None
    try:
        verdict = json.loads(raw).get("verdict")
    except (ValueError, AttributeError):
        return None
    return verdict if verdict in ("on_task", "distracted", "unsure") else None


def warm_up():
    """Load the model into memory now, so the first real sentence isn't slow."""
    if enabled():
        _chat([{"role": "user", "content": "hi"}])
