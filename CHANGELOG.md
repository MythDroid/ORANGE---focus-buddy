# Orange - Change log

Every change made to this project, newest first. One entry per work session.
"NEW" = a file that did not exist before. "EDITED" = an existing file was changed.

## 15 Nov 2026 (evening) - Watch fix: she was hiding Calculator, Snipping Tool and new tabs

The watch judged EVERY window except a short list of work programs, so tools the brain did not
recognise as "study" were hidden. It is now the other way round.

- EDITED `orange/watch.py` - she only judges the programs in `watch.only_judge` (browsers and a
  few chat / video apps). Everything else is never touched. Inside a browser, these are always
  fine: an empty new tab, a search page, login / Wi-Fi sign-in pages, browser settings, and AI
  assistants (ChatGPT, Claude, Gemini, Copilot, Perplexity...).
- EDITED `config.yaml` (`watch:` block) - new `only_judge` list; `always_fine` is now empty.

## 15 Nov 2026 (later) - Getting ready for GitHub

- EDITED `README.md` - rewritten for the new Orange (it still described the old voice
  assistant): what she does, pictures, privacy, how she works, how to run her, status.
- EDITED `memory.md` - rewritten to match today's decisions (on-screen pet, PyQt6, SQLite,
  Ollama, "Hey Orange"). The old robot roadmap is removed.
- EDITED `.gitignore` - PNG files were all ignored; pictures in `docs/images/` are now allowed.
- NEW `docs/images/moods.png`, `pokes.png`, `carried.png` - still frames of Orange, drawn by her
  own code, for the README.

## 15 Nov 2026 (later) - BUG FIX: the distraction watch was not running at all

When the Ctrl+Space shortcut was added to `pet.py`, the lines that START the distraction watch
were deleted by mistake. From then on Orange never looked at any window, whatever the settings.
(This is why she ignored the Shin-chan video.)

- EDITED `pet.py` - the watch is started again. It also prints a line if it is switched off.

## 15 Nov 2026 (later) - Watch is much faster: hide after about 4 to 5 seconds

- EDITED `config.yaml` (`watch:` block) - `check_seconds` 2 -> 1, `settle_seconds` 6 -> 2,
  `hide_after_seconds` 45 -> 0, `repeat_hide_after_seconds` 15 -> 0. So: 2 seconds in front,
  about 3 seconds for the brain to judge (instant for a title she has judged before), then hide.
- EDITED `orange/watch.py` - the "weren't we doing ...?" nudge is skipped when the hide comes
  first, so she doesn't say two things at once.

## 15 Nov 2026 (later) - Watch: cartoons, and saying when it is on or off

- EDITED `orange/brain.py` - the window judge now names cartoons, anime, TV shows, web series,
  vlogs and comedy as distractions, with three new examples, and counts a video as on-task
  only if its title is clearly about the subject.
- EDITED `orange/watch.py` - on video sites, "not sure" now counts as a distraction. The
  terminal prints "Watch: ON for ..." / "Watch: OFF ..." whenever the watch switches.

## 15 Nov 2026 (later) - Smaller Orange, and she fills the screen when she hides a window

- EDITED `orange/face/window.py` - default size is now 180 x 194 pixels (was 220 x 238), and
  `run(width=...)` sets it. New `loom(seconds)`: the window grows to the whole screen, she pops
  up big with hands on hips, then shrinks back to her spot. While big she can't be poked or
  dragged, and the full-screen moment is not saved as her position. The bubble moves to the top
  of the screen when there is no room above or below her.
- EDITED `orange/face/__init__.py` - offers `face.loom()`.
- EDITED `orange/face/orange.css` - the "loom" and "shrink" looks.
- EDITED `orange/watch.py` - calls `face.loom()` each time she hides a window.
- EDITED `pet.py` - passes `pet.width` from config.yaml to the window.
- EDITED `config.yaml` - new `pet:` block with `width: 180`; new line `grow_seconds: 5` in `watch:`.

Status: the big look is checked in a browser. Growing the real window to full screen and back
on Windows is NOT yet tested.

## 15 Nov 2026 (later) - Carrying, shaking, dropping, squashing and hovering

- EDITED `orange/face/window.py` - while you drag her she is "carried" (25 checks a second on
  how she is moved). 5 quick left-right turns = shaken (screen glitches, dazed afterwards).
  Half a second above 1500 pixels a second = dizzy afterwards. Body pushed past a screen edge =
  squashed against that side, and she pops back onto the screen when you let go. Letting go =
  a squish and bounce. Mouse resting within about 115 pixels for 1.2 seconds = she leans away.
- EDITED `orange/face/orange.css` - section 3c: carried, glitch, dazed, dizzy, land,
  squash-left/right/top/bottom, wary-left/right.
- EDITED `orange/face/orange.html` - a sixth eye drawing: the dizzy spiral.
- EDITED `orange/face/orange.js` - `Orange.react(name, 0)` keeps a reaction on; new `Orange.calm()`.

Status: the looks are checked in a browser. The carrying itself (does Windows keep reporting
her position while it drags the window, and does letting go register) is NOT yet tested.

## 15 Nov 2026 (later) - Pokes, double-click to talk, Ctrl+Space, and "Hey Orange"

"Hey Jarvis" is dropped. Orange no longer loads the wake-word model at all.

### New files
- NEW `orange/hotkey.py` - reserves Ctrl+Space with Windows; pressing it makes Orange listen.

### Edited files
- EDITED `orange/voice.py` - rewritten. No more `wake.py` / "Hey Jarvis". "Hey Orange" now works
  through the speech-to-text you already have: when she hears speech she checks only the first
  2.5 seconds for her name and throws everything else away. You can say the whole thing in one
  breath ("Hey Orange, study DL for 45 minutes").
- EDITED `orange/face/window.py` - single click = poke (tummy, face, antennas, head, feet),
  5 pokes in 6 seconds = she gets huffy for 4 seconds, rubbing the mouse over her head = a pat,
  double-click = talk. New `start_talking()` for the shortcut.
- EDITED `orange/face/__init__.py` - offers `face.start_talking()`.
- EDITED `orange/face/orange.html` - two little hearts (for head pats); preview hint text.
- EDITED `orange/face/orange.css` - the poke reactions (section 3b).
- EDITED `orange/face/orange.js` - `Orange.react(name, ms)`; pokes also work in the browser preview.
- EDITED `pet.py` - starts the shortcut; passes `on_talk` instead of `on_click`.
- EDITED `config.yaml` - `voice:` block is now `enabled`, `hey_orange`, `shortcut`
  (`wake_word` removed). The old `wake:` block is kept but marked as unused.

### Left in place on purpose (not deleted)
- `orange/wake.py`, `main.py` and the `wake:` block in `config.yaml` are the old "Hey Jarvis"
  voice loop. Orange (`pet.py`) no longer uses them. They are still in the folder because
  deleting files needs your say-so.

### Status
- Poke reactions: checked in a browser, they play.
- Double-click, Ctrl+Space, head pats and "Hey Orange" on Windows: NOT yet tested.

## 15 Nov 2026 (later) - Watch fix: she gave up after hiding a window once

The watch worked on Windows (spotted the reels, minimised the window). But after one hide she
only gave a side-eye forever, and fast scrolling (a new title every few seconds) could stall her.

- EDITED `orange/watch.py` - rounds: if you reopen a window she hid (or open another
  distraction), she says so at once and hides it again after 15 seconds, sooner than round 1.
  The step-up now keeps running while the title changes from reel to reel.
- EDITED `config.yaml` - one new line, `repeat_hide_after_seconds: 15`, in the `watch:` block.

## 15 Nov 2026 (later) - The distraction watch

### New files
- NEW `orange/watch.py` - during a study session, reads the TITLE of the window in front
  (never its contents), asks the brain whether it fits the task, then: side-eye -> nudge ->
  minimise the window. It never closes anything. Windows only.

### Edited files
- EDITED `orange/brain.py` - new `judge(task, title)`: on_task / distracted / unsure.
- EDITED `orange/store.py` - new table `allowed_titles` (pages you said are for study) and
  `add_distraction()`, which counts drifts per session.
- EDITED `orange/commands.py` - understands "this is for study", "not a distraction",
  "I need this", "leave it alone".
- EDITED `orange/study_mode.py` - `focus_task()`, `note_distraction()` and the reply to
  "this is for study".
- EDITED `pet.py` - starts the watch when `watch.enabled` is true.
- EDITED `config.yaml` - new `watch:` block (on/off, hide on/off, timings, always-fine programs).

### Status
- The step-up logic: tested with pretend windows, working.
- Reading real window titles and minimising on Windows: NOT yet tested.

## 15 Nov 2026 (later) - Brain fixes after the fair test (8 of 12 right, about 3 s each)

- EDITED `orange/study_mode.py` - safety net: if your sentence contains no time at all, any
  minutes the brain made up are ignored ("till lunch" had become 60 minutes).
- EDITED `orange/commands.py` - new rule: "I'm done with my food / call / shower" means "I'm
  back". New helper `mentions_a_time()` for the safety net above.
- EDITED `orange/brain.py` - three more examples and clearer wording for "back" and "remember".
  Can print where its time goes (loading, reading instructions, writing the answer).
- EDITED `config.yaml` - one new line, `show_timing: true`, in the `brain.understand` block.

## 15 Nov 2026 - Orange gets a small local brain (Ollama)

Plan change: Orange is a companion, not a tutor. The brain only helps her understand everyday
sentences and say one short friendly line. It runs on the laptop through Ollama (model
`qwen3.5:2b`), so nothing typed leaves the laptop. Rules and taught phrases are still tried first.

### New files
- NEW `test_brain.py` - sends 9 everyday sentences to the brain and prints what it decided
  and how long each took.

### Edited files
- EDITED `orange/brain.py` - was a one-line placeholder comment. Now talks to Ollama, forces the
  answer into a fixed form (one of 14 actions), switches the model's long "thinking" off, and
  returns nothing if Ollama is closed, so Orange falls back to her rules.
- EDITED `orange/study_mode.py` - when the rules don't understand, the Buddy asks the brain
  (without freezing the timer) and turns its answer into a normal command.
- EDITED `orange/face/window.py` - typed text is now handled in a helper thread, so the window
  keeps moving while Orange thinks.
- EDITED `pet.py` - starts the brain and loads the model at startup.
- EDITED `config.yaml` - added the `brain.understand` block (enabled, model, url,
  timeout_seconds) at the top of the `brain:` section. The older lines below it are unchanged.

### After the first real brain test (9 of 9 actions right, about 3 seconds each)
- EDITED `orange/study_mode.py` - the model put its chat line in the wrong field ("text"
  instead of "reply"), so Orange would not have said it. She now accepts either.
- EDITED `test_brain.py` - replaced the sentences with 12 new ones that are not the examples
  inside the brain's instructions, for a fairer test.

### Speed tuning (the model was only 65% on the graphics card)
- EDITED `orange/brain.py` - asks Ollama for a smaller working space (`num_ctx` 2048 instead of
  4096) so more of the model fits on the 4 GB card. The brain's answer form now has one text
  field instead of two, so it writes less.
- EDITED `config.yaml` - one new line, `context: 2048`, in the `brain.understand` block.

### Status
- The Buddy's use of the brain: tested with a pretend brain, working.
- The real model on the laptop: NOT yet tested. Run `python test_brain.py`.

## 15 Nov 2026 (later) - Talking to Orange

### New files
- NEW `orange/voice.py` - the listening loop: wake word or click -> record -> speech-to-text ->
  show "I heard: ..." -> do it. Reuses wake.py, listen.py and stt.py. Audio is never saved.

### Edited files
- EDITED `orange/wake.py` - `wait_for_wake_word()` takes an optional `wake_now` signal, so a
  click on Orange can wake her as well as the wake word. Four new lines; nothing else changed,
  and `main.py` still works as before.
- EDITED `orange/study_mode.py` - new `Buddy.show(mood)` so the voice can ask for the
  listening face.
- EDITED `orange/face/window.py` - a click on Orange now means "talk" when her ears are on
  (otherwise the text box opens as before). The menu item is renamed "Type to Orange...".
- EDITED `pet.py` - starts the voice thread when `voice.enabled` is true.
- EDITED `config.yaml` - new `voice:` block (`enabled`, `wake_word`) above the `wake:` block.

### Status
- NOT yet tested with a real microphone. The click-to-talk and wake word paths are new.

## 14 Nov 2026 (later) - Study sessions, memory, typing and speech bubbles

### New files
- NEW `pet.py` - the program to run every day (`python pet.py`). Joins the window, the Buddy
  and the memory.
- NEW `orange/store.py` - Orange's memory: a SQLite database in `data/orange.db` (made on first
  run). Tables: `sessions`, `reminders`, `notes`, `settings`. The only file that touches the database.
- NEW `orange/commands.py` - turns a sentence into a command with pattern rules (no AI).
  Understands: study X for N minutes, break, resume, stop, remind me in/at ..., remember that ...,
  what do you remember, forget everything, time left, how long did I study today, call me X, hello.

### Edited files
- EDITED `orange/study_mode.py` - was a one-line placeholder comment. Now holds the `Buddy`:
  study sessions, breaks, "5 minutes left", celebrating at the end, reminders, notes,
  dozing off after 10 quiet minutes, and resuming a session if Orange was closed mid-way.
- EDITED `.gitignore` - added `data/` (with a comment) so your memory file never goes to git.
- EDITED `orange/face/window.py` - added the speech bubble, the text box (click Orange to type),
  click-versus-drag detection, quick study items in the right-click menu, `say()`,
  `set_timer()` and `on_text`. Window is now 220 x 238 (was 220 x 220) to fit the timer label.
- EDITED `orange/face/__init__.py` - now also offers `face.say()` and `face.set_timer()`.
- EDITED `orange/face/orange.html` - drawing is 16 units taller; added the timer label under Orange.
- EDITED `orange/face/orange.css` - styles for the timer label; preview sizes adjusted.
- EDITED `orange/face/orange.js` - added `Orange.setTimer()`.
- EDITED `CHANGELOG.md` - this entry.

### Fix after the first run on Windows
- EDITED `orange/face/window.py` - Orange closed at once with "Argument list is empty". The window
  toolkit was started without the program's name. It now gets `sys.argv`.
- EDITED `pet.py` - added `faulthandler.enable()` so a hard crash prints where it happened.

### Fixes after Orange first ran on Windows (it works: transparent window, drag, typing)
- EDITED `orange/face/window.py` - the speech bubble had no background, so the text was
  unreadable on dark screens. The bubble and the text box are now a see-through window with a
  painted label inside, which gives a solid cream bubble with round corners.
- EDITED `orange/commands.py` - new sentences: stepping away ("I'm gonna go have dinner", "brb",
  "going for a shower", "lunch time"), "good night" / "bye", "thank you", "how are you", and more
  ways to say "I'm back".
- EDITED `orange/study_mode.py` - new "away" pause: the session stops counting with no end time
  until you say "I'm back" (it survives closing Orange). Orange dozes while it waits and the
  label shows "paused". Added replies for good night, thanks and how are you. Shorter, friendlier
  "I didn't get that" message.

### Teaching Orange new phrases yourself
- EDITED `orange/store.py` - new table `phrases` and four functions for it.
- EDITED `orange/commands.py` - understands "when I say X, I mean Y", "when I say X, say Y",
  "what did I teach you" and "forget the phrase X".
- EDITED `orange/study_mode.py` - checks your taught phrases first, then the built-in rules.

### Status
- Sessions, commands and memory: tested with a fake clock (no window), all working.
- Window, bubble and text box: written but NOT yet tested on Windows.

## 14 Nov 2026 - Orange gets a body (Soft Bot)

Direction change: Orange is now an on-screen study-buddy pet (no physical robot).
The character is "Soft Bot": a squishy orange robot with a dark screen face.

### New files
- NEW `orange/face/orange.html` - Orange's body, drawn in SVG shapes. Opens in a browser as a
  preview with mood buttons, or inside the pet window (`orange.html?window`).
- NEW `orange/face/orange.css` - colours, shapes and every animation.
- NEW `orange/face/orange.js` - mood switching, blinking, eyes following the mouse, confetti.
  Other code controls it with `Orange.setMood("happy")`.
- NEW `orange/face/window.py` - the transparent, frameless, always-on-top window (PyQt6).
  Drag to move (position saved in `C:\Users\<you>\.orange\window.json`), right-click menu
  (Mood list, Quit), eyes follow the mouse across the whole screen.
- NEW `orange/face/__init__.py` - the Python remote control: `face.set_mood()`, `face.run()`, `face.quit()`.
- NEW `demo_face.py` - opens the window and shows every mood for 5 seconds.
- NEW `CHANGELOG.md` - this file.

### Edited files
- EDITED `requirements.txt` - added 3 lines at the end: a comment, `PyQt6>=6.5` and
  `PyQt6-WebEngine>=6.5`. Nothing else in the file was touched.

### The 9 moods
idle, happy, listening, focused, sleepy, confused, amazed, celebrating, sideeye.

### Changes made during the evening (after the first version)
- Antennas made shorter.
- "amazed" eyes changed from round sparkly eyes to star eyes (the round ones looked scared).
- "sleepy" antennas now hang down instead of sticking out sideways.
- "celebrating" arms reach higher.
- "confused" rebuilt: staggers left and right, then plops down on its bottom, then "?" appears.
- "sideeye" mood added: turns away, half-closed eyes slide sideways, hands on hips, foot tapping.
- `orange.js`: `Orange.lookAt()` now does nothing while Orange is reading, dozing or side-eyeing.

### Not changed
`main.py`, `config.yaml`, `memory.md`, `README.md`, `.env.example`, `.gitignore`, `goals.txt`,
`calibrate.py` and all the voice files (`wake.py`, `listen.py`, `stt.py`, `speak.py`, `privacy.py`).

### Status
- Browser preview: checked, all moods draw with no errors.
- Pet window: written but NOT yet tested on Windows.
