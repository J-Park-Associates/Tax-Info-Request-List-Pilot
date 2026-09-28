// Pilot edition: the header badge, the Tour button and the one-time terms
// screen (pilot SPEC section 5).
//
// Why it is built this way: the pilot adds to the page and changes nothing
// the app already does (P7, P10). So this file calls no app.js function,
// joins none of its dialogs, opens no channel to the tracker, and builds
// every element from text - the wording itself lives in pilot-content.js,
// the one file Jason edits (P8).
//
// The terms are the safe direction by design: acceptance lives in the
// window's local storage (P9), and anything that goes wrong reading it -
// storage missing, blocked or cleared - shows the terms again rather than
// letting a tester in who never saw them. While they are open nothing else
// can be reached: no Escape, no click outside, and Tab stays in the card.

(function pilotEdition() {
  const TERMS_KEY = "pilot.terms.accepted";
  const TOUR_KEY = "pilot.tour.seen";

  function fill(text) {
    return String(text).split("{email}").join(PILOT.contact.email);
  }

  function readStored(key) {
    try {
      return window.localStorage.getItem(key);
    } catch (err) {
      return null;
    }
  }

  function writeStored(key, value) {
    try {
      window.localStorage.setItem(key, value);
    } catch (err) {
      // Not remembered: the terms show again next launch, the safe direction.
    }
  }

  function make(tag, className, text) {
    const el = document.createElement(tag);
    if (className) {
      for (const name of className.split(" ")) el.classList.add(name);
    }
    if (text !== undefined) el.textContent = fill(text);
    return el;
  }

  // ── Badge ──────────────────────────────────────────────────────────────
  const badge = make("span", "pilot-badge", `${PILOT.edition.label} ${PILOT.edition.version}`);
  badge.id = "pilot-badge";
  const brand = document.querySelector(".brand");
  if (brand) {
    brand.appendChild(badge);
  } else {
    // The badge must always show, even if the header ever changes.
    badge.classList.add("pilot-badge-float");
    document.body.appendChild(badge);
  }

  // ── Tour button ────────────────────────────────────────────────────────
  const tourButton = make("button", "btn", "Tour");
  tourButton.id = "btn-tour";
  tourButton.setAttribute("type", "button");
  tourButton.addEventListener("click", () => PilotTour.start());
  const inbox = document.getElementById("btn-inbox");
  const toolbar = document.querySelector(".toolbar");
  if (inbox && inbox.parentNode) {
    inbox.parentNode.insertBefore(tourButton, inbox);
  } else if (toolbar) {
    toolbar.appendChild(tourButton);
  } else {
    badge.appendChild(tourButton);
  }

  // ── Terms ──────────────────────────────────────────────────────────────
  const terms = PILOT.terms;
  if (readStored(TERMS_KEY) === String(terms.version)) return;

  const overlay = make("div", "pilot-terms-overlay");
  overlay.id = "pilot-terms";
  overlay.setAttribute("role", "dialog");
  overlay.setAttribute("aria-modal", "true");
  overlay.setAttribute("aria-labelledby", "pilot-terms-title");

  const card = make("div", "pilot-terms-card");
  const title = make("h2", "", terms.title);
  title.id = "pilot-terms-title";
  card.appendChild(title);

  const body = make("div", "pilot-terms-body");
  for (const section of terms.sections) {
    const part = make("div", "pilot-terms-section");
    part.appendChild(make("h3", "", section.heading));
    const list = make("ul");
    for (const bullet of section.bullets) list.appendChild(make("li", "", bullet));
    part.appendChild(list);
    body.appendChild(part);
  }
  card.appendChild(body);

  const check = make("label", "pilot-terms-check");
  const agree = make("input");
  agree.id = "pilot-terms-agree";
  agree.setAttribute("type", "checkbox");
  check.appendChild(agree);
  check.appendChild(document.createTextNode(` ${terms.checkbox}`));
  card.appendChild(check);

  const actions = make("div", "pilot-terms-actions");
  const quit = make("button", "btn", terms.quit);
  quit.id = "pilot-terms-quit";
  quit.setAttribute("type", "button");
  const accept = make("button", "btn btn-primary", terms.accept);
  accept.id = "pilot-terms-accept";
  accept.setAttribute("type", "button");
  accept.setAttribute("disabled", "");
  actions.appendChild(quit);
  actions.appendChild(accept);
  card.appendChild(actions);
  overlay.appendChild(card);

  // Captured before the app's own keyboard rule, so the terms cannot be
  // closed with Escape and Tab never leaves the card.
  function holdKeys(e) {
    if (e.key === "Escape") {
      e.preventDefault();
      e.stopPropagation();
    } else if (e.key === "Tab") {
      const stops = [agree, quit, accept].filter((el) => !el.disabled);
      const at = stops.indexOf(document.activeElement);
      const next = e.shiftKey
        ? (at <= 0 ? stops.length - 1 : at - 1)
        : (at === -1 || at === stops.length - 1 ? 0 : at + 1);
      e.preventDefault();
      e.stopPropagation();
      stops[next].focus();
    }
  }

  // Clicks outside the card land on the overlay and go nowhere.
  overlay.addEventListener("mousedown", (e) => {
    if (e.target === overlay) e.preventDefault();
  });
  agree.addEventListener("change", () => {
    accept.disabled = !agree.checked;
  });
  quit.addEventListener("click", () => window.close());
  accept.addEventListener("click", () => {
    if (!agree.checked) return;
    writeStored(TERMS_KEY, String(terms.version));
    document.removeEventListener("keydown", holdKeys, true);
    overlay.remove();
    if (readStored(TOUR_KEY) !== "1") PilotTour.start();
  });

  document.addEventListener("keydown", holdKeys, true);
  document.body.appendChild(overlay);
  agree.focus();
})();
