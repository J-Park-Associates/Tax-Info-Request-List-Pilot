// Pilot edition: the guided tour over the real screen (pilot SPEC section 6).
//
// The tour only points (SPEC section 1). It highlights an element that is
// already on the page and says, in one line, what it does (SPEC-shell
// section 12: one line per step, five words or fewer). It never presses a
// button, runs a pass, opens a file or
// talks to the tracker - that it was seen is pilot.js's to keep (P46), and
// while it is open the layer under the card takes
// every click, so a tester reading a step cannot set something off by
// accident. The wording lives in pilot-content.js (P8); the buttons and the
// step count below are UI labels, not copy.
//
// Each step names the ids it can point at, in order. The shell's parts (the
// side panel, the path, the sort icon, the page) are always on the screen,
// so a step nearly always points; one that finds nothing is shown centred.
// The anchor is re-checked every half second, because a scheduled pass can
// change the page while the tester is reading.

const PilotTour = (() => {
  const { make } = PilotDom;   // pilot.js, loaded before this file
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

  function render() {
    const all = steps();
    const step = all[index];
    const last = index === all.length - 1;
    anchor = findAnchor(step);

    card.replaceChildren();
    card.appendChild(make("div", "pilot-tour-count", `Step ${index + 1} of ${all.length}`));
    const title = make("h2", "", step.title);
    title.id = "pilot-tour-title";
    card.appendChild(title);
    card.appendChild(make("p", "", step.does));

    const actions = make("div", "pilot-tour-actions");
    const back = button("Back", previous);
    if (index === 0) back.setAttribute("disabled", "");
    const next = button(last ? "Finish" : "Next", forward);
    next.classList.add("btn-primary");
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
    // The spot is its anchor's container: its corner is the anchor's plus the gap (P36).
    const corner = parseFloat(window.getComputedStyle(anchor).borderTopLeftRadius) || 0;
    spot.style.setProperty("--pilot-spot-radius", `${corner + PAD}px`);

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

  // An element may appear or vanish while the tour is open (a scheduled
  // pass finished); the step then points at it, or is shown centred.
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
      tipKey(e);   // tooltip.js: this capture stops the key before shellKey (P130)
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
    // Remembered where the terms are (P46): pilot.js's record, durable,
    // with the window's storage as its cache.
    if (!options || options.remember !== false) PilotRecord.tourSeen();
  }

  return { start, stop };
})();
