// Pilot edition: the badge in the side panel's foot and the one-time terms
// screen (pilot SPEC section 5; SPEC-shell section 12). The Tour button is
// gone: Help > Take the tour starts the tour, and Help > Terms shows the
// terms again, read only, with one Close.
//
// Why it is built this way: the pilot adds to the page and changes nothing
// the app already does (P7, P10). So this file calls no app.js function,
// joins none of its dialogs, and builds every element from text - the
// wording itself lives in pilot-content.js, the one file Jason edits (P8).
//
// The terms are the safe direction by design, and acceptance is kept where
// a restart finds it (P46). The durable record is the tracker's own, in its
// data folder, through the one channel the page already has (the API's
// pilot-record command); the window's local storage is only its cache. The
// pilot 0.1 Windows check showed why: a restart made while the last window
// was still closing could not open that storage, read nothing, and showed
// the terms again. So a cache that says nothing is never the answer on its
// own - the durable record is asked, and only when it cannot say either do
// the terms stay. While they are open nothing else can be reached: no
// Escape, no click outside, and Tab stays in the card.

// Acceptance and "tour seen", kept in the durable record and cached in the
// window's storage. With PilotDom below, all tour.js uses from this file.
const PilotRecord = (() => {
  const TERMS_KEY = "pilot.terms.accepted";
  const TOUR_KEY = "pilot.tour.seen";
  // The API command, which the shell allows only once the page's first
  // call has told it which commands exist (vocab.commands).
  const COMMAND = "pilot-record";
  const READY_WAIT_MS = 120000;
  const READY_LOOK_MS = 200;

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
      // Not cached: the durable record still holds it.
    }
  }

  // Whether the shell will run the command yet: app.js's first call has
  // answered and the API lists it. False when that never comes.
  function ready() {
    return new Promise((resolve) => {
      const began = Date.now();
      (function look() {
        if (typeof vocab === "object" && vocab && Array.isArray(vocab.commands)) {
          resolve(vocab.commands.indexOf(COMMAND) !== -1);
        } else if (Date.now() - began > READY_WAIT_MS) {
          resolve(false);
        } else {
          window.setTimeout(look, READY_LOOK_MS);
        }
      })();
    });
  }

  // The durable record: {terms, terms_signed_by, terms_accepted_at,
  // tour_seen}, or null when it cannot be had.
  // One call at a time: two writes sent together would each read, change and
  // write the file, and one would lose the other's field (P46 review, 1).
  let queue = Promise.resolve(null);
  function ask(payload) {
    const next = queue.then(() => askNow(payload));
    queue = next.catch(() => null);
    return next;
  }
  function askNow(payload) {
    return ready()
      .then((ok) => (ok ? window.tracker.call([COMMAND], payload) : null))
      .then((reply) => {
        if (reply && !reply.error) return reply;
        if (reply) window.tracker.logError(`pilot record: ${reply.error}`);
        return null;
      }, () => null);
  }

  return {
    termsCached: (version) => readStored(TERMS_KEY) === version,
    tourCached: () => readStored(TOUR_KEY) === "1",
    read: () => ask({}).then((record) => {
      if (record && record.tour_seen) writeStored(TOUR_KEY, "1");
      return record;
    }),
    // signedBy is the name typed to sign (P188); left out, the acceptance is
    // kept with no name - never one the tester did not type.
    acceptTerms: (version, signedBy) => {
      writeStored(TERMS_KEY, version);
      return ask(signedBy === undefined ? { terms: version } : { terms: version, signed_by: signedBy });
    },
    cacheTerms: (version) => writeStored(TERMS_KEY, version),
    tourSeen: () => {
      writeStored(TOUR_KEY, "1");
      return ask({ tour_seen: true });
    },
  };
})();

// The one element builder of the pilot layer, here and in tour.js: a tag,
// its classes, and its text with the contact email filled in. Text only, so
// nothing the content file holds is ever read as markup.
const PilotDom = (() => {
  function fill(text) {
    return String(text).split("{email}").join(PILOT.contact.email);
  }

  function make(tag, className, text) {
    const el = document.createElement(tag);
    if (className) {
      for (const name of className.split(" ")) el.classList.add(name);
    }
    if (text !== undefined) el.textContent = fill(text);
    return el;
  }

  return { make };
})();

// The terms card. gate() is the one-time screen, which cannot be escaped;
// show() is Help > Terms: the same card read only, its Accept and Quit
// become one Close, and Escape closes it.
const PilotTerms = (() => {
  const { make } = PilotDom;

  // The overlay, its card and the controls; the caller wires them.
  function build(readOnly) {
    const terms = PILOT.terms;
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

    const controls = { overlay };
    const actions = make("div", "pilot-terms-actions");
    if (readOnly) {
      // Who signed and when: built here, attached by show() above the
      // actions only once the record holds a name, never hidden and shown.
      Object.assign(controls, { signed: make("p", "pilot-terms-signed"), actions });
      const close = make("button", "btn btn-primary", terms.close);
      close.id = "pilot-terms-close";
      close.setAttribute("type", "button");
      actions.appendChild(close);
      controls.close = close;
    } else {
      const check = make("label", "pilot-terms-check");
      const agree = make("input");
      agree.id = "pilot-terms-agree";
      agree.setAttribute("type", "checkbox");
      check.appendChild(agree);
      check.appendChild(document.createTextNode(` ${terms.checkbox}`));
      card.appendChild(check);
      // The sign-off (P188): the name typed here is the signature.
      const field = make("label", "field pilot-terms-name");
      field.appendChild(make("span", "", terms.sign));
      const name = make("input");
      name.id = "pilot-terms-name";
      name.setAttribute("type", "text");
      name.setAttribute("maxlength", "200");
      name.setAttribute("autocomplete", "off");
      name.setAttribute("spellcheck", "false");
      field.appendChild(name);
      card.appendChild(field);
      const quit = make("button", "btn", terms.quit);
      quit.id = "pilot-terms-quit";
      quit.setAttribute("type", "button");
      const accept = make("button", "btn btn-primary", terms.accept);
      accept.id = "pilot-terms-accept";
      accept.setAttribute("type", "button");
      accept.setAttribute("disabled", "");
      actions.appendChild(quit);
      actions.appendChild(accept);
      Object.assign(controls, { agree, name, quit, accept });
    }
    card.appendChild(actions);
    overlay.appendChild(card);
    return controls;
  }

  // Captured before the app's own keyboard rule: Tab never leaves the card,
  // and Escape closes it only when it is read only.
  function holdKeys(stops, onEscape) {
    return function hold(e) {
      if (e.key === "Escape") {
        tipKey(e);   // tooltip.js: this capture stops the key before shellKey (P130)
        e.preventDefault();
        e.stopPropagation();
        if (onEscape) onEscape();
      } else if (e.key === "Tab") {
        const live = stops().filter((el) => !el.disabled);
        const at = live.indexOf(document.activeElement);
        const next = e.shiftKey
          ? (at <= 0 ? live.length - 1 : at - 1)
          : (at === -1 || at === live.length - 1 ? 0 : at + 1);
        e.preventDefault();
        e.stopPropagation();
        live[next].focus();
      }
    };
  }

  // A signature carries its full date: month name, day and year from the
  // stored ISO time. pagesDay (pages.js) drops the year, and no on-screen
  // format carries one, so this is the pilot's own.
  function signedDay(iso) {
    const parts = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso || ""));
    if (!parts) return "";
    return new Date(Number(parts[1]), Number(parts[2]) - 1, Number(parts[3])).toLocaleDateString([], { year: "numeric", month: "long", day: "numeric" });
  }

  // Help > Terms. The signature line shows only when the record holds a
  // name; an acceptance from before the sign-off shows none (P188 Q2).
  function show() {
    if (document.getElementById("pilot-terms") || document.getElementById("pilot-tour")) return;
    const { overlay, signed, actions, close } = build(true);
    PilotRecord.read().then((record) => {
      const name = record ? String(record.terms_signed_by || "") : "";
      const day = record ? signedDay(record.terms_accepted_at) : "";
      if (!name || !day || !overlay.isConnected) return;
      // The date goes in first, so nothing a person typed is read as a slot.
      signed.textContent = PILOT.terms.signed.split("{date}").join(day).split("{name}").join(name);
      actions.before(signed);
    });
    const hold = holdKeys(() => [close], dismiss);
    function dismiss() {
      document.removeEventListener("keydown", hold, true);
      overlay.remove();
    }
    close.addEventListener("click", dismiss);
    overlay.addEventListener("mousedown", (e) => {
      if (e.target === overlay) e.preventDefault();
    });
    document.addEventListener("keydown", hold, true);
    document.body.appendChild(overlay);
    close.focus();
  }

  // The one-time screen. Returns without a word when this version's
  // acceptance is already kept.
  function gate() {
    const terms = PILOT.terms;
    const version = String(terms.version);
    if (PilotRecord.termsCached(version)) {
      // The cache has it; the durable record is brought level in the
      // background (a tester of 0.1 accepted before it existed). That
      // acceptance was made on this PC, so it stands without a name (P188
      // Q2): none is sent, and none is ever made up.
      PilotRecord.read().then((record) => {
        if (record && record.terms !== version) PilotRecord.acceptTerms(version);
      });
      return;
    }

    const { overlay, agree, name, quit, accept } = build(false);
    const hold = holdKeys(() => [agree, name, quit, accept], null);
    // Sign and Accept waits for the box and a name; spaces are not a name.
    const signedBy = () => name.value.trim();
    const ready = () => agree.checked && signedBy() !== "";

    // Clicks outside the card land on the overlay and go nowhere.
    overlay.addEventListener("mousedown", (e) => {
      if (e.target === overlay) e.preventDefault();
    });
    agree.addEventListener("change", () => {
      accept.disabled = !ready();
    });
    name.addEventListener("input", () => {
      accept.disabled = !ready();
    });
    quit.addEventListener("click", () => window.close());
    function close() {
      document.removeEventListener("keydown", hold, true);
      if (overlay.contains(document.activeElement)) document.activeElement.blur();
      overlay.remove();
    }
    accept.addEventListener("click", () => {
      if (!ready()) return;
      PilotRecord.acceptTerms(version, signedBy());
      close();
      if (!PilotRecord.tourCached()) PilotTour.start();
    });

    document.addEventListener("keydown", hold, true);
    document.body.appendChild(overlay);
    agree.focus();

    // The cache said nothing, which is not an answer (P46): the durable
    // record is asked, and when it holds this version's acceptance the terms
    // go without a word - and the tour, seen or not, is not started. When it
    // cannot say, the terms stay: the safe direction.
    PilotRecord.read().then((record) => {
      if (!record || record.terms !== version || !overlay.isConnected) return;
      PilotRecord.cacheTerms(version);
      close();
    });
  }

  return { show, gate };
})();

(function pilotEdition() {
  // ── Badge: the side panel's foot, or floating when there is none ────────
  const badge = document.createElement("span");
  badge.classList.add("pilot-badge");
  badge.id = "pilot-badge";
  badge.textContent = `${PILOT.edition.label} ${PILOT.edition.version}`;
  const foot = document.getElementById("side-foot");
  if (foot) {
    foot.appendChild(badge);
  } else {
    // The badge must always show, even if the panel ever changes.
    badge.classList.add("pilot-badge-float");
    document.body.appendChild(badge);
  }

  PilotTerms.gate();
})();
