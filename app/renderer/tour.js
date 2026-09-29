// Pilot edition: the guided tour over the real screen (pilot SPEC section 6).
//
// The tour only points (SPEC section 1). It highlights an element that is
// already on the page and says what it does, why it is safe and what its
// current limit is. It never presses a button, runs a pass, opens a file or
// talks to the tracker - that it was seen is pilot.js's to keep (P31), and
// while it is open the layer under the card takes
// every click, so a tester reading a step cannot set something off by
// accident. The wording lives in pilot-content.js (P8); the three headings
// below are UI labels, not copy.
//
// A step's element may not exist yet - the Needs Review card appears only
// once a pass sets something aside - so each step names the ids it can
// point at, in order, and a line to show instead when none is on screen.
// The anchor is re-checked every half second, because a scheduled pass can
// bring the card in while the tester is reading.

const PilotTour = (() => {
  const GAP = 12;
  const PAD = 6;
  const MARGIN = 8;

  let layer = null;
  let spot = null;
  let card = null;
  let index = 0;
  let anchor = null;
  let timer = null;

  function steps() {
    return PILOT.tour.steps;
  }

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

  function button(label, onClick) {
    const el = make("button", "btn", label);
    el.setAttribute("type", "button");
    el.addEventListener("click", onClick);
    return el;
  }

  function findAnchor(step) {
    for (const id of step.anchors) {
      const el = document.getElementById(id);
      if (el && el.getClientRects().length > 0) return el;
    }
    return null;
  }

  function callout(className, heading, value) {
    const section = make("section", className);
    section.appendChild(make("h3", "", heading));
    if (Array.isArray(value)) {
      const list = make("ul");
      for (const line of value) list.appendChild(make("li", "", line));
      section.appendChild(list);
    } else {
      section.appendChild(make("p", "", value));
    }
    return section;
  }

  function stagesStrip(step) {
    const names = PILOT.tour.stages;
    const current = names.indexOf(step.stage);
    const strip = make("ol", "pilot-tour-stages");
    names.forEach((name, i) => {
      const item = make("li", "pilot-tour-stage", name);
      if (current !== -1 && i === current) item.classList.add("is-current");
      if (current !== -1 && i < current) item.classList.add("is-done");
      strip.appendChild(item);
    });
    return strip;
  }

  function render() {
    const all = steps();
    const step = all[index];
    const last = index === all.length - 1;
    anchor = findAnchor(step);

    card.replaceChildren();
    card.classList.remove("is-wide");
    card.appendChild(stagesStrip(step));
    card.appendChild(make("div", "pilot-tour-count", `Step ${index + 1} of ${all.length}`));
    const title = make("h2", "", step.title);
    title.id = "pilot-tour-title";
    card.appendChild(title);
    card.appendChild(callout("pilot-tour-does", "What it does", step.does));

    const ok = callout("pilot-tour-ok", "Why it's safe", step.strength);
    const warn = callout("pilot-tour-warn", "Current limit", step.limit);
    if (Array.isArray(step.strength) && Array.isArray(step.limit)) {
      const compare = make("div", "pilot-tour-compare");
      compare.appendChild(ok);
      compare.appendChild(warn);
      card.appendChild(compare);
      card.classList.add("is-wide");
    } else {
      card.appendChild(ok);
      card.appendChild(warn);
    }
    if (!anchor && step.fallback) {
      card.appendChild(make("p", "pilot-tour-fallback", step.fallback));
    }

    const actions = make("div", "pilot-tour-actions");
    const back = button("Back", previous);
    if (index === 0) back.setAttribute("disabled", "");
    const next = button(last ? "Finish" : "Next", forward);
    actions.appendChild(back);
    actions.appendChild(next);
    actions.appendChild(button("Close", stop));
    card.appendChild(actions);

    if (anchor) anchor.scrollIntoView({ block: "center" });
    place();
    next.focus();
  }

  // Sizes the spot to the anchor and keeps the card inside the window:
  // below the spot, or above it when there is no room below.
  function place() {
    if (!layer) return;
    const width = window.innerWidth;
    const height = window.innerHeight;
    const box = card.getBoundingClientRect();
    if (!anchor) {
      layer.classList.add("is-centred");
      spot.classList.add("is-hidden");
      card.style.setProperty("left", `${Math.max(MARGIN, (width - box.width) / 2)}px`);
      card.style.setProperty("top", `${Math.max(MARGIN, (height - box.height) / 2)}px`);
      return;
    }
    layer.classList.remove("is-centred");
    spot.classList.remove("is-hidden");
    const r = anchor.getBoundingClientRect();
    const top = r.top - PAD;
    const bottom = r.bottom + PAD;
    spot.style.setProperty("left", `${r.left - PAD}px`);
    spot.style.setProperty("top", `${top}px`);
    spot.style.setProperty("width", `${r.width + 2 * PAD}px`);
    spot.style.setProperty("height", `${r.height + 2 * PAD}px`);

    let cardTop = bottom + GAP;
    if (cardTop + box.height > height - MARGIN && top - GAP - box.height >= MARGIN) {
      cardTop = top - GAP - box.height;
    }
    cardTop = Math.min(Math.max(MARGIN, cardTop), Math.max(MARGIN, height - box.height - MARGIN));
    let cardLeft = r.left;
    cardLeft = Math.min(Math.max(MARGIN, cardLeft), Math.max(MARGIN, width - box.width - MARGIN));
    card.style.setProperty("left", `${cardLeft}px`);
    card.style.setProperty("top", `${cardTop}px`);
  }

  // A card may appear or vanish while the tour is open (a scheduled pass
  // finished); the step then points at it, or says what to expect.
  function recheck() {
    if (!layer) return;
    const found = findAnchor(steps()[index]);
    if (found !== anchor) render();
    else place();
  }

  function go(to) {
    index = to;
    render();
  }

  function forward() {
    if (index === steps().length - 1) stop();
    else go(index + 1);
  }

  function previous() {
    if (index > 0) go(index - 1);
  }

  function onKey(e) {
    if (!layer || document.getElementById("pilot-terms")) return;
    if (e.key === "Escape") {
      e.preventDefault();
      e.stopPropagation();
      stop();
    } else if (e.key === "ArrowRight") {
      e.preventDefault();
      e.stopPropagation();
      forward();
    } else if (e.key === "ArrowLeft") {
      e.preventDefault();
      e.stopPropagation();
      previous();
    } else if (e.key === "Tab") {
      // Keep the keyboard on the card, as the layer keeps the mouse.
      const stops = Array.from(card.querySelectorAll("button")).filter((el) => !el.disabled);
      const at = stops.indexOf(document.activeElement);
      const next = e.shiftKey
        ? (at <= 0 ? stops.length - 1 : at - 1)
        : (at === -1 || at === stops.length - 1 ? 0 : at + 1);
      e.preventDefault();
      e.stopPropagation();
      stops[next].focus();
    }
  }

  function start() {
    if (document.getElementById("pilot-terms")) return;
    if (layer) stop({ remember: false });

    layer = make("div", "pilot-tour-layer");
    layer.id = "pilot-tour";
    spot = make("div", "pilot-tour-spot");
    card = make("div", "pilot-tour-card");
    card.setAttribute("role", "dialog");
    card.setAttribute("aria-live", "polite");
    card.setAttribute("aria-labelledby", "pilot-tour-title");
    layer.appendChild(spot);
    layer.appendChild(card);
    document.body.appendChild(layer);

    document.addEventListener("keydown", onKey, true);
    window.addEventListener("resize", place);
    window.addEventListener("scroll", place, true);
    timer = window.setInterval(recheck, 500);
    go(0);
  }

  function stop(options) {
    if (!layer) return;
    window.clearInterval(timer);
    timer = null;
    document.removeEventListener("keydown", onKey, true);
    window.removeEventListener("resize", place);
    window.removeEventListener("scroll", place, true);
    layer.remove();
    layer = null;
    spot = null;
    card = null;
    anchor = null;
    // Remembered where the terms are (P31): pilot.js's record, durable,
    // with the window's storage as its cache.
    if (!options || options.remember !== false) PilotRecord.tourSeen();
  }

  return { start, stop };
})();
