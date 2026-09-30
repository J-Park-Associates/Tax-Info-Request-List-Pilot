// The custom tooltip (pilot SPEC-shell.md section 8.5, decisions P63, P65).
//
// Any element with a data-tip attribute gets one: after 300 ms of hover, or
// at once when the keyboard reaches it (any control but the search box). Esc
// and moving away hide it. There is one #tip element, role="tooltip", tied to
// its element with aria-describedby while it shows. Floating UI places it and
// keeps it inside the window; it is never wider than 320px (the stylesheet's).
//
// Why a tooltip of our own and no title attribute: a title shows after a
// second or more, cannot be styled for dark, is not shown on keyboard focus
// and is read twice by some screen readers. The words are never typed here:
// a tip is the API's vocabulary or a person's own name, set by setTip() from
// the code that draws the element. A tip that is a name which may fit on the
// screen is set with setTipIfCut() and shows only when the name is cut.

const TIP_DELAY_MS = 300;
const TIP_GAP = 4;
const TIP_MARGIN = 8;

let tipFor = null;      // the element whose tip shows, or null
let tipTimer = null;

function tipNode() {
  return document.getElementById("tip");
}

// The element's tip, or "" when it has none or its name is not cut.
function tipWords(node) {
  const words = node.dataset.tip || "";
  if (!words) return "";
  if (node.dataset.tipCut !== undefined && node.scrollWidth <= node.clientWidth) return "";
  return words;
}

// Set (or clear, with "") an element's tooltip. The replacement for every
// title attribute of the old screen.
function setTip(node, words) {
  if (words) node.dataset.tip = words;
  else delete node.dataset.tip;
  delete node.dataset.tipCut;
  if (tipFor === node) {
    if (words) showTip(node);
    else hideTip();
  }
}

// A name that is the tooltip only when it is cut on the screen.
function setTipIfCut(node, words) {
  setTip(node, words);
  if (words) node.dataset.tipCut = "";
}

// Placement is Floating UI's (vendor/floating-ui, loaded before this file):
// below the element, 4 off it, flipped above when there is no room and
// shifted to stay 8 inside the window, and hidden once its element is
// scrolled out of view (hide). Timing, focus, Esc and the words stay
// ours. computePosition answers later, so a hide that came first wins.
function placeTip(node, tip) {
  tip.style.setProperty("left", "0");
  tip.style.setProperty("top", "0");
  FloatingUIDOM.computePosition(node, tip, {
    strategy: "fixed",
    placement: "bottom",
    middleware: [
      FloatingUIDOM.offset(TIP_GAP),
      FloatingUIDOM.flip({ padding: TIP_MARGIN }),
      FloatingUIDOM.shift({ padding: TIP_MARGIN }),
      FloatingUIDOM.hide(),
    ],
  }).then(({ x, y, middlewareData }) => {
    if (tipFor !== node) return;
    if (middlewareData.hide && middlewareData.hide.referenceHidden) {
      hideTip();
      return;
    }
    tip.style.setProperty("left", `${x}px`);
    tip.style.setProperty("top", `${y}px`);
  });
}

function showTip(node) {
  const words = tipWords(node);
  const tip = tipNode();
  if (!words || !tip) {
    hideTip();
    return;
  }
  if (tipFor && tipFor !== node) tipFor.removeAttribute("aria-describedby");
  tipFor = node;
  tip.textContent = words;
  tip.hidden = false;
  node.setAttribute("aria-describedby", "tip");
  placeTip(node, tip);
}

function hideTip() {
  clearTimeout(tipTimer);
  tipTimer = null;
  const tip = tipNode();
  if (tip) tip.hidden = true;
  if (tipFor) tipFor.removeAttribute("aria-describedby");
  tipFor = null;
}

// Escape hides a showing tip, wherever the keyboard is (SPEC-shell 8.5,
// P130). shellKey hands it every key first - app.js keeps the document's one
// keydown listener (SPEC-shell 4.3) - and it never consumes one, so the same
// Escape still clears the search box, closes the side sheet or asks a dialog
// to close. Consuming it would make every dialog need two Escapes, because
// the keyboard puts a tip on each control it reaches.
function tipKey(e) {
  if (e.key === "Escape" && tipFor !== null) hideTip();
}

function tipTarget(event) {
  return event.target instanceof Element ? event.target.closest("[data-tip]") : null;
}

document.addEventListener("mouseover", (e) => {
  const node = tipTarget(e);
  if (!node || node === tipFor) return;
  hideTip();
  tipTimer = setTimeout(() => showTip(node), TIP_DELAY_MS);
});
document.addEventListener("mouseout", (e) => {
  const node = tipTarget(e);
  if (!node || node.contains(e.relatedTarget)) return;
  hideTip();
});
// The keyboard: at once, for a focus the keyboard made, on every control but
// the search box (its tip would cover the list its typing opens; hover still
// shows it).
document.addEventListener("focusin", (e) => {
  const node = tipTarget(e);
  if (node && node.matches(":focus-visible") && !node.matches("#find")) {
    hideTip();
    showTip(node);
  }
});
document.addEventListener("focusout", hideTip);
document.addEventListener("pointerdown", hideTip, true);
// Scrolling or resizing while a tip shows moves it with its element.
function replaceTip() {
  if (tipFor && tipFor.isConnected) placeTip(tipFor, tipNode());
  else hideTip();
}
document.addEventListener("scroll", replaceTip, true);
window.addEventListener("resize", replaceTip);
window.addEventListener("blur", hideTip);
