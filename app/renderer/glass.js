// The glass theme's script (pilot 0.2, SPEC-glass section 7.1, decisions P34, P44).
//
// Everything visible is CSS in glass.css; this file only does the three things
// CSS cannot: it puts the chosen quality level on <html>, builds the picker for
// it in the header, and marks when the page has scrolled so the toolbar can
// deepen.
//
// Why it is built this way: like the other pilot files it adds to the page and
// changes nothing the app already does (P7, P10) - it calls no app.js function,
// opens no channel, builds every element from text, and keeps its wording in
// pilot-content.js (P8). It has no timer and no loop of its own. If this file
// fails to run the CSS default still applies, and the only thing lost is the
// scrolled shadow.

(function glassTheme() {
  if (typeof PILOT === "undefined" || !PILOT.glass) return;

  const CONFIG = PILOT.glass;
  const STORAGE_KEY = "pilot.glass.level";
  const CLASS_PREFIX = "glass-";
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

  // ── The scrolled toolbar ───────────────────────────────────────────────

  const main = document.querySelector(".main");
  if (main) {
    let scrolled = false;
    main.addEventListener("scroll", () => {
      const now = main.scrollTop > 4;
      if (now === scrolled) return;
      scrolled = now;
      root.classList.toggle("glass-scrolled", now);
    }, { passive: true });
  }
})();
