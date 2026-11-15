/* Orange's little behaviours: changing mood, blinking, eyes following the mouse.
 *
 * The looks are all in orange.css. This file only flips small switches:
 *   - mood  -> sets  data-mood="..."  on the <svg>
 *   - blink -> adds the class "blink" for a moment
 *   - eyes  -> sets two CSS numbers, --look-x and --look-y
 *
 * Other code (Python, in the next phase) controls Orange through one object:
 *   Orange.setMood("happy")
 */
(function () {
  "use strict";

  const MOODS = ["idle", "happy", "listening", "focused", "sleepy", "confused", "amazed", "celebrating", "sideeye"];
  const svg = document.getElementById("orange");

  // "orange.html?window" = running as the real pet window (no buttons, see-through).
  const windowMode = location.search.includes("window");
  if (windowMode) document.documentElement.classList.add("window-mode");

  /* ---------- Mood ---------- */

  function setMood(mood) {
    if (!MOODS.includes(mood)) {
      console.warn(`Unknown mood "${mood}". Use one of: ${MOODS.join(", ")}`);
      return false;
    }
    svg.dataset.mood = mood;
    if (!tracksMouse()) lookAt(0, 0);   // reading or dozing: eyes stop following the mouse
    document.querySelectorAll("#mood-buttons button").forEach(
      (b) => b.classList.toggle("on", b.dataset.mood === mood));
    return true;
  }

  function getMood() { return svg.dataset.mood; }

  // While reading, dozing or giving you the side-eye, Orange doesn't follow the mouse.
  function tracksMouse() { return !["focused", "sleepy", "sideeye"].includes(getMood()); }

  /* ---------- Eyes follow the mouse ---------- */

  // x and y go from -1 to 1 (left/right, up/down). The eyes move only a few pixels.
  function lookAt(x, y) {
    const clamp = (n) => Math.max(-1, Math.min(1, n));
    svg.style.setProperty("--look-x", (clamp(x) * 3.5).toFixed(2) + "px");
    svg.style.setProperty("--look-y", (clamp(y) * 2.5).toFixed(2) + "px");
  }

  let mouseEvent = null;   // newest mouse position, handled at most once per screen frame
  window.addEventListener("mousemove", (e) => {
    if (mouseEvent === null) requestAnimationFrame(followMouse);
    mouseEvent = e;
  });

  function followMouse() {
    const e = mouseEvent;
    mouseEvent = null;
    if (!e || !tracksMouse()) return;
    const box = svg.getBoundingClientRect();
    const dx = e.clientX - (box.left + box.width / 2);
    const dy = e.clientY - (box.top + box.height * 0.43);   // 0.43 = roughly where the face is
    // Mouse 250 px away (or more) = eyes fully turned that way.
    lookAt(dx / 250, dy / 250);
  }

  /* ---------- Blinking ---------- */

  let blinkTimer = null;

  function scheduleBlink() {
    const wait = 3000 + Math.random() * 3000;   // every 3 to 6 seconds, never the same
    blinkTimer = setTimeout(() => {
      if (getMood() !== "sleepy") {             // eyes are already closed when sleepy
        blink();
        if (Math.random() < 0.2) setTimeout(blink, 260);   // sometimes a cute double blink
      }
      scheduleBlink();
    }, wait);
  }

  function blink() {
    svg.classList.add("blink");
    setTimeout(() => svg.classList.remove("blink"), 130);
  }

  /* ---------- Confetti (made once, animated by CSS only while celebrating) ---------- */

  function makeConfetti() {
    const layer = document.getElementById("confetti");
    const colours = ["#FF6B6B", "#FFD93D", "#6BCB77", "#4D96FF", "#FF8FA0", "#B983FF"];
    const pieces = 14;
    for (let i = 0; i < pieces; i++) {
      // Spread the pieces in a fan above Orange: from far left (-165 deg) to far right (-15 deg).
      const angle = (-165 + (150 * i) / (pieces - 1)) * Math.PI / 180;
      const dist = 52 + Math.random() * 26;
      const p = document.createElementNS("http://www.w3.org/2000/svg", "rect");
      p.setAttribute("class", "confetti");
      p.setAttribute("x", -3); p.setAttribute("y", -2);
      p.setAttribute("width", 6); p.setAttribute("height", 4); p.setAttribute("rx", 1);
      p.setAttribute("fill", colours[i % colours.length]);
      p.style.setProperty("--dx", (Math.cos(angle) * dist).toFixed(1) + "px");
      p.style.setProperty("--dy", (Math.sin(angle) * dist).toFixed(1) + "px");
      p.style.setProperty("--r", Math.round(120 + Math.random() * 300) + "deg");
      p.style.setProperty("--d", (Math.random() * 0.5).toFixed(2) + "s");
      layer.appendChild(p);
    }
  }

  /* ---------- Poke reactions ---------- */

  // react("tummy", 900): play a short reaction, then go back to the current mood.
  // react("carried", 0):  0 means "keep it until told otherwise" (used while you drag her).
  // calm():               stop any reaction now.
  let pokeTimer = null;
  function react(name, ms) {
    clearTimeout(pokeTimer);
    svg.removeAttribute("data-poke");
    void svg.getBoundingClientRect();        // Makes the browser notice the removal, so the same
    svg.dataset.poke = name;                 // reaction can play twice in a row
    if (ms !== 0) pokeTimer = setTimeout(calm, ms || 900);
  }
  function calm() {
    clearTimeout(pokeTimer);
    svg.removeAttribute("data-poke");
  }

  /* ---------- Timer label under Orange ---------- */

  // setTimer("DL 32:10") shows the label; setTimer(null) hides it.
  function setTimer(text) {
    const label = document.getElementById("timer");
    if (text) label.querySelector("text").textContent = text;
    label.classList.toggle("on", Boolean(text));
  }

  /* ---------- Save CPU when nobody can see Orange ---------- */

  document.addEventListener("visibilitychange", () => {
    svg.classList.toggle("paused", document.hidden);
    clearTimeout(blinkTimer);
    if (!document.hidden) scheduleBlink();
  });

  /* ---------- Preview page buttons (not used in the pet window) ---------- */

  function buildPreview() {
    const row = document.getElementById("mood-buttons");
    MOODS.forEach((mood, i) => {
      const b = document.createElement("button");
      b.textContent = `${i + 1}. ${mood}`;
      b.dataset.mood = mood;
      b.addEventListener("click", () => setMood(mood));
      row.appendChild(b);
    });
    window.addEventListener("keydown", (e) => {
      const n = Number(e.key);
      if (n >= 1 && n <= MOODS.length) setMood(MOODS[n - 1]);
    });

    const stage = document.getElementById("stage");
    document.querySelectorAll("[data-bg]").forEach((b) => b.addEventListener("click", () => {
      stage.classList.remove("dark", "desk");
      if (b.dataset.bg !== "cream") stage.classList.add(b.dataset.bg);
      document.querySelectorAll("[data-bg]").forEach((x) => x.classList.toggle("on", x === b));
    }));
    document.querySelectorAll("[data-size]").forEach((b) => b.addEventListener("click", () => {
      stage.classList.toggle("real", b.dataset.size === "real");
      document.querySelectorAll("[data-size]").forEach((x) => x.classList.toggle("on", x === b));
    }));
  }

  // Preview only: clicking her in the browser plays the reaction for that spot.
  function previewPokes() {
    svg.addEventListener("click", (e) => {
      const box = svg.getBoundingClientRect();
      const x = (e.clientX - box.left) / box.width * 200, y = (e.clientY - box.top) / box.height * 216;
      const spot = y > 168 ? "feet" : (y < 82 && x < 62) ? "antenna-l" : (y < 82 && x > 138) ? "antenna-r"
        : (x >= 58 && x <= 142 && y >= 53 && y <= 123) ? "face" : y < 53 ? "head"
        : (x >= 48 && x <= 152) ? "tummy" : null;
      if (spot) react(spot, spot === "head" ? 1700 : 1000);
    });
  }

  /* ---------- Start ---------- */

  makeConfetti();
  if (!windowMode) { buildPreview(); previewPokes(); }
  setMood("idle");
  scheduleBlink();

  // The "remote control" for other code.
  // (lookAt here is the polite version: it does nothing while Orange is reading or dozing.)
  window.Orange = {
    MOODS, setMood, getMood, blink, setTimer, react, calm,
    lookAt: (x, y) => { if (tracksMouse()) lookAt(x, y); },
  };
})();
