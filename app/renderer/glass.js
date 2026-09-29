// The glass theme's script (pilot 0.2, SPEC-glass section 7.1, decisions P34, P44, P45).
//
// Everything visible is CSS in glass.css; this file only does the four things
// CSS cannot: it puts the chosen quality level on <html>, builds the picker for
// it in the header, moves two numbers so the pointer light can follow the
// pointer, and marks when the page has scrolled so the toolbar can deepen.
//
// Why it is built this way: like the other pilot files it adds to the page and
// changes nothing the app already does (P7, P10) - it calls no app.js function,
// opens no channel, builds every element from text, and keeps its wording in
// pilot-content.js (P8). It sets exactly two custom properties, --glass-x and
// --glass-y, and nothing else on any element (P44). It has no timer and no loop
// of its own: the pointer light is redrawn at most once per animation frame,
// only at the refraction level, only while the pointer is over a light glass
// surface, and it reads that surface's rectangle once and keeps it until the
// page scrolls or resizes, because reading it every frame would force a layout
// every frame (P45). If this file fails to run the CSS default still applies,
// and the only things lost are the pointer light and the scrolled shadow.

(function glassTheme() {
  if (typeof PILOT === "undefined" || !PILOT.glass) return;

  const CONFIG = PILOT.glass;
  const STORAGE_KEY = "pilot.glass.level";
  const CLASS_PREFIX = "glass-";
  const FULL_CLASS = "glass-full";
  // The light glass surfaces of SPEC-glass 6.1 (the header is dark glass and
  // takes no pointer light).
  const SURFACES = ".toolbar, #review-card, #reminder-card, #moved-card, .modal, .pilot-terms-card, .pilot-tour-card";
  const QUIET = "(prefers-reduced-transparency: reduce), (prefers-reduced-motion: reduce), (prefers-contrast: more), (forced-colors: active)";

  const root = document.documentElement;
  const keys = CONFIG.levels.map((level) => level.key);
  const quiet = window.matchMedia(QUIET);

  function make(tag, className, text) {
    const el = document.createElement(tag);
    if (className) {
      for (const name of className.split(" ")) el.classList.add(name);
    }
    if (text !== undefined) el.textContent = text;
    return el;
  }

  // ── The level ──────────────────────────────────────────────────────────

  function storedLevel() {
    try {
      const value = window.localStorage.getItem(STORAGE_KEY);
      if (keys.includes(value)) return value;
    } catch (err) {
      // Storage missing or blocked: the default applies.
    }
    return CONFIG.default;
  }

  function applyLevel(key) {
    for (const each of keys) root.classList.remove(CLASS_PREFIX + each);
    root.classList.add(CLASS_PREFIX + key);
  }

  let level = storedLevel();
  applyLevel(level);

  // The shell asks Windows 11 for its window material and says so in the
  // page's own address (P46); the CSS then lays a wash over it. Without the
  // word the class is absent and the page paints its opaque backdrop.
  if (new URLSearchParams(window.location.search).get("material") === "mica") {
    root.classList.add("glass-mica");
  }

  // ── The picker in the header ───────────────────────────────────────────

  const topbar = document.querySelector(".topbar");
  let select = null;
  let note = null;
  if (topbar) {
    const label = make("label", "glass-level");
    label.appendChild(make("span", "glass-level-label", CONFIG.label));
    select = make("select");
    select.id = "glass-level-select";
    for (const entry of CONFIG.levels) {
      const option = make("option", "", entry.name);
      option.value = entry.key;
      select.appendChild(option);
    }
    select.value = level;
    label.appendChild(select);
    note = make("span", "glass-level-note hidden", CONFIG.system_note);
    label.appendChild(note);
    topbar.appendChild(label);

    select.addEventListener("change", () => {
      level = select.value;
      applyLevel(level);
      try {
        window.localStorage.setItem(STORAGE_KEY, level);
      } catch (err) {
        // Not remembered: the level stays applied for this session.
      }
    });
  }

  // While Windows asks for less, the CSS makes the screen plain whatever the
  // picker says; the picker is greyed and says why, live.
  function syncQuiet() {
    if (select) select.disabled = quiet.matches;
    if (note) note.classList.toggle("hidden", !quiet.matches);
  }
  syncQuiet();
  quiet.addEventListener("change", syncQuiet);

  // ── The pointer light (refraction level only) ──────────────────────────

  let surface = null;
  let rect = null;
  let frame = 0;
  let pointerX = 0;
  let pointerY = 0;

  document.addEventListener("pointerover", (event) => {
    const next = event.target instanceof Element ? event.target.closest(SURFACES) : null;
    if (next !== surface) {
      surface = next;
      rect = null;
    }
  }, { passive: true });

  function paintLight() {
    frame = 0;
    if (!surface) return;
    if (!rect) rect = surface.getBoundingClientRect();
    surface.style.setProperty("--glass-x", (pointerX - rect.left) + "px");
    surface.style.setProperty("--glass-y", (pointerY - rect.top) + "px");
  }

  document.addEventListener("pointermove", (event) => {
    if (!surface || quiet.matches || !root.classList.contains(FULL_CLASS)) return;
    pointerX = event.clientX;
    pointerY = event.clientY;
    if (!frame) frame = window.requestAnimationFrame(paintLight);
  }, { passive: true });

  window.addEventListener("resize", () => {
    rect = null;
  }, { passive: true });

  // ── The scrolled toolbar ───────────────────────────────────────────────

  const main = document.querySelector(".main");
  if (main) {
    let scrolled = false;
    main.addEventListener("scroll", () => {
      rect = null;
      const now = main.scrollTop > 4;
      if (now === scrolled) return;
      scrolled = now;
      root.classList.toggle("glass-scrolled", now);
    }, { passive: true });
  }

  // ── Pause the drift while another program is in front ──────────────────

  window.addEventListener("blur", () => root.classList.add("glass-paused"));
  window.addEventListener("focus", () => root.classList.remove("glass-paused"));
})();
