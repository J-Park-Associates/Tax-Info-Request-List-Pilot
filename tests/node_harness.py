"""Running the renderer's own JavaScript under node, and reading its text.

The window is sandboxed and there is no browser in the gate, so a claim about
what a page does is made by lifting the functions that do it out of the
renderer's scripts, as written, and running them in node against fakes of what
the page provides (a small DOM, the app's ``call``, the engine's replies).
``test_shell`` grew the runners (``run_shell``, ``run_pages``,
``run_pages_dom`` and their kin) and ``test_single_source`` imported one from it;
they live here so the borrowing names a
module that is not a test file (SPEC-architecture E-4, R2.1). Moved with their
words from ``tests/test_shell.py``; each runner keeps the fakes and the
function lists it always had.

``read(name)`` is the renderer's file as text, the one reader every test of the
renderer used to write out for itself (``test_pilot``, ``test_pilot_ui``).
"""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import tracker.api as api

REPO = Path(__file__).resolve().parent.parent
RENDERER = REPO / "app" / "renderer"


def read(name: str) -> str:
    return (RENDERER / name).read_text(encoding="utf-8")


#: Every script ``index.html`` loads, by file name, the vendored libraries left out:
#: the renderer's own code, in the order the page loads it.
RENDERER_SCRIPTS = tuple(src for src in re.findall(r'<script src="([^"]+)"', read("index.html"))
                         if not src.startswith("vendor/"))

# The lists of scripts a claim covers are this one or named parts of it
# (SPEC-architecture R3.2, D-5): a script added to index.html is read by every
# claim about the renderer as a whole and by every claim about the app's own
# scripts without anyone adding it, and test_renderer_seams holds each part
# inside the whole.

#: The pilot's own scripts (P10): its wording, the terms screen and badge, and
#: the tour, each built at run time inside its own namespace. test_pilot holds
#: them to the pilot's rules.
PILOT_SCRIPTS = ("pilot-content.js", "pilot.js", "tour.js")
#: The app's own scripts: every one the page loads but the pilot's.
APP_SCRIPTS = tuple(name for name in RENDERER_SCRIPTS if name not in PILOT_SCRIPTS)
#: The scripts SPEC-shell added beside app.js (P67), the ones its claims about
#: the new files name.
SHELL_SCRIPTS = ("shell.js", "tooltip.js", "pages.js", "sheet.js")


def renderer_text(scripts: tuple[str, ...] = RENDERER_SCRIPTS) -> str:
    """The renderer's scripts as one text, every one the page loads unless
    ``scripts`` names a part: what a claim about the renderer as a whole reads,
    so code that moves from one script to another is read where it lands."""
    return "\n".join(read(name) for name in scripts)


def stripped_js(name: str) -> str:
    """The file without its comments (no string in these files holds //)."""
    text = read(name)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"(?m)^\s*//.*$|(?<=[;{}),])\s*//.*$", "", text)


NODE = shutil.which("node")


#: What a probe that holds the engine's pages lifts besides what it draws (P278): the window's ask, its merge of a reply and its adoption of one.
ENGINE_FUNCTIONS = ("shellFirmAsk", "shellFirmMerge", "shellFirmShaped", "pagesAdopt", "pagesListOf", "pagesStoredOrder", "pagesSaveOrder")


#: A page of a firm list is cut by the engine (P278), so a probe that draws one asks the real
#: ``tracker.firm_pages`` through the interpreter running these tests: it is handed the made-up
#: firm's whole reply, the names its walk saw, the vocabulary's words and the window's own ask
#: (``shellFirmAsk``), and answers the page.
ENGINE_SNIPPET = """
import json, sys
from tracker import firm_pages
spec = json.load(sys.stdin)
ask = firm_pages.ask_of(spec["ask"], spec["words"]["client_types"])
reply = firm_pages.page(spec["whole"], spec["names"], spec["words"], ask)
reply["view"] = "made-up-view"
sys.stdout.write(json.dumps(reply))
"""


ENGINE_ENV = {**os.environ, "FIRM_PY": sys.executable, "FIRM_REPO": str(Path(__file__).resolve().parent.parent), "FIRM_SNIPPET": ENGINE_SNIPPET}


def js_function(name: str, file: str | None = None) -> str:
    """One function of the renderer's own scripts exactly as written: from
    ``function name(`` (or ``async function name(``) to the first ``"\\n}\\n"``,
    that line included.

    With ``file`` (``"app.js"``) the function is cut from that script. Without
    one, every script ``index.html`` loads is searched (:data:`RENDERER_SCRIPTS`,
    never ``vendor/``). Either way it must be defined exactly once: a name two
    scripts define (``show``, ``fill`` and ``render`` are) needs the script said,
    so a test never claims about the one it did not mean.

    This is the one lifter. It replaced seven (``test_shell``'s, two of
    ``test_single_source``'s, two of ``test_row_columns``', and inline cuts in
    ``test_api``); the claims about a function's text are the same, only the
    way of cutting it is one (SPEC-architecture R2.3). The callers that used to
    ask for a body without its header, or for the text to the matching brace,
    read this text, which holds the header and ends at the line of the closing
    brace.
    """
    found = []
    for script in (file,) if file else RENDERER_SCRIPTS:
        text = read(script)
        for match in re.finditer(rf"(?m)^[ \t]*((?:async )?function {re.escape(name)}\()", text):
            found.append((text, match.start(1)))
    assert len(found) == 1, f"{name} is defined {len(found)} times in {file or 'the renderer scripts'}"
    text, start = found[0]
    return text[start:text.index("\n}\n", start) + 3]


def store_functions() -> str:
    """app.js's storeRead and storeWrite, which the lists and the shell keep
    their choices on this PC through."""
    return js_function("storeRead", "app.js") + "\n" + js_function("storeWrite", "app.js")


def run_shell(functions: list[str], setup: str, probe: str, tmp_path: Path, source: str = "shell.js"):
    """Lift the named functions out of shell.js (or ``source``) as they are,
    put fakes for what app.js provides around them, and return what the
    probe prints."""
    if NODE is None:
        pytest.skip("node is not on PATH (CI installs it)")
    lifted = "\n".join(js_function(name, source if f"function {name}(" in read(source) else "shell.js") for name in functions)
    if "PAGES_COLLATOR" in lifted:
        lifted = lift_line("const PAGES_COLLATOR = ", "pages.js") + lifted   # a module-level const the lifted sorts compare through
    script = tmp_path / "probe.js"
    script.write_text(f"{setup}\n{lifted}\nPromise.resolve((() => {{ {probe} }})()).then((out) => process.stdout.write(JSON.stringify(out)));\n",
                      encoding="utf-8", newline="\n")
    done = subprocess.run([NODE, str(script)], capture_output=True, text=True, encoding="utf-8", timeout=60, check=False)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def run_pages(functions: list[str], setup: str, probe: str, tmp_path: Path):
    """The same, lifting the named functions out of pages.js."""
    return run_shell(functions, setup, probe, tmp_path, "pages.js")


#: A small DOM, enough for h(), icon() and the pages' own builders: elements
#: with a class list, a dataset, attributes, children and a search by class
#: or role. Its point is to run pages.js's functions as written.
FAKE_DOM = r"""
class Node {}
class Text extends Node { constructor(data) { super(); this.data = data; } }
class Element extends Node {
  constructor(tag) { super(); this.tag = tag; this.className = ""; this.dataset = {}; this.attrs = {}; this.kids = []; this.open = false; this.handlers = {};
    this.style = { props: {}, setProperty(key, value) { this.props[key] = value; }, removeProperty(key) { delete this.props[key]; } }; }
  get classList() {
    const self = this;
    return { add(one) { if (!self.className.split(" ").includes(one)) self.className = `${self.className} ${one}`.trim(); },
             remove(one) { self.className = self.className.split(" ").filter((name) => name !== one).join(" "); },
             toggle(one, on) { if (on) this.add(one); else this.remove(one); return Boolean(on); },
             contains(one) { return self.className.split(" ").includes(one); } };
  }
  setAttribute(key, value) { this.attrs[key] = String(value); }
  removeAttribute(key) { delete this.attrs[key]; }
  getAttribute(key) { return this.attrs[key]; }
  get id() { return this.attrs.id; }
  getBoundingClientRect() { return { left: 10, bottom: 20, top: 0, right: 30 }; }
  append(...nodes) { for (const one of nodes) this.kids.push(one instanceof Node ? one : new Text(String(one))); }
  replaceChildren(...nodes) { this.kids = []; this.append(...nodes); }
  insertBefore(node, before) { const at = before ? this.kids.indexOf(before) : -1; if (at === -1) this.kids.push(node); else this.kids.splice(at, 0, node); return node; }
  removeChild(node) { this.kids.splice(this.kids.indexOf(node), 1); return node; }
  focus() {}
  querySelectorAll(selector) {
    if (selector.startsWith("[role=")) return this.find((one) => `[role="${one.attrs.role}"]` === selector);
    const names = selector.split(".").filter(Boolean);
    return this.find((one) => names.every((name) => one.className.split(" ").includes(name)));
  }
  addEventListener(type, fn) { (this.handlers[type] = this.handlers[type] || []).push(fn); }
  get childNodes() { return this.kids; }
  find(test, out = []) { for (const one of this.kids) if (one instanceof Element) { if (test(one)) out.push(one); one.find(test, out); } return out; }
  querySelector(selector) { return this.byClass(selector.slice(1))[0] || null; }
  byClass(name) { return this.find((one) => one.className.split(" ").includes(name)); }
  get textContent() { return this.kids.map((one) => (one instanceof Text ? one.data : one.textContent)).join(""); }
}
const document = { activeElement: null, createDocumentFragment: () => new Element("fragment"), createElement: (tag) => new Element(tag), createElementNS: (_ns, tag) => new Element(tag) };
const page = (nodes) => { const box = new Element("div"); box.append(...nodes.filter(Boolean)); return box; };
"""


PAGE_WORDS = r"""
const fill = (p, v) => p.replace(/\{(\w+)\}/g, (_, k) => v[k] ?? "");
const isSetAside = (o) => o === "Not Applicable";
const overrideLabel = (o, year) => `Not applicable ${year}`;
let locked = false;
let lastState = null;
const tips = []; const cutTips = [];
const setTipIfCut = (node, words) => { tips.push([node.className, words]); cutTips.push(node.className); };
const setTip = (node, words) => tips.push([node.className, words]);
const opened = []; const went = [];
const openPath = (path, how) => opened.push([path, how]);
const shellGo = (route) => went.push(route);
const popups = [];
const shellPopup = (name, token, x, y, enable) => popups.push([name, token, x, y, enable]);
const unanswered = (id) => failures.push(`unanswered ${id}`);
let shellReturn = (path) => ({ return_name: "1040 - John & Jane Smith", household: "h1", year: 2025 });
const PAGES_LINK_WORDS = { file: "show_in_explorer", household: "navigate_client", return: "navigate_return" };
const PAGES_GROUPS = ["needs_you", "waiting", "received", "set_aside"];
const PAGES_TONES = { needs: "is-attention", waiting: "is-waiting", done: "is-done", plain: "is-plain" };
let pagesUid = 0; const pagesTokens = new Map(); let pagesSetAsideOpen = false; let pagesBroken = []; let pagesDrawn = "";
let pagesFocus = null; let pagesLastLevel = ""; let pagesClientsAll = false;
const notices = []; const failures = [];
let syncNotices = (prefix, wanted) => notices.push([prefix, wanted.map((one) => [one.key, one.failure.sentence, one.detail || ""])]);
const failed = (err) => failures.push(String(err.message));
let shellHousehold = () => null; let households = [];
const vocab = {
  shell: { page_error: "The app hit an error" }, notices: { about: "{label}: {sentence}" },
  client_type_forms: { individuals: ["1040"], businesses: ["1120", "1120S", "1065"], trusts: ["1041"], nonprofits: ["990"] },
  layout: { return_name_pattern: "{form} - {client}" },
  decisions: { needs_review: "Needs Review", dismissed: "Not Requested", filed: "Filed", file_moved: "File Moved" },
  labels: { Missing: { label: "Outstanding" }, Received: { label: "Received" }, Partial: { label: "Partly in" }, Rejected: { label: "Could not use" }, NotAsked: { label: "Not asked" } },
  overrides: { not_applicable: "Not Applicable" },
  review_labels: { bucket_order: ["document", "container", "not_a_document"], dismiss: "Not requested",
                   buckets: { document: "Documents", container: "Emails and zips", not_a_document: "Not documents" } },
  reasons: { unmatched: { short: "Could not tell" }, "opened-not-across": { short: "Email or zip" } },
  reason_tips: { "opened-not-across": "Came in email or zip" },
  screen: {
    groups: { needs_you: "Needs you", waiting: "Waiting on client", received: "Received", set_aside: "Set aside" },
    steps: { check: "Check", open: "Open", draft: "Draft reminder", edit: "Edit" },
    notices: { paused: "Two Years Open; Sorting Paused" },
    empty: { received: "Nothing received yet" }, moved: "Moved by hand", due: "Due {date}", since: "Since {date}", partly: "{n} of {total}",
    show_in_explorer: "Show in File Explorer", navigate_client: "Navigate to Household", navigate_return: "Navigate to Return",
    counts: { need: "{n} need you", waiting: "{n} waiting", complete: "Complete", files: "{n} files", one_file: "1 file", one_return: "1 return", returns: "{n} returns" },
    sections: { overview: "Overview", needs_review: "Needs Review", reminders: "Reminders", clients: "Households" },
    columns: { tax_year: "Tax Year", taxpayer: "Taxpayer", form_type: "Form Type", taxpayer_tip: "{action} ({household})",
               status: "Status", date: "Date", file: "File", suggestion: "Suggestion", reason: "Reason",
               received: "Received", stage: "Stage", drafted: "Drafted", returns: "Returns", client_name: "Household Name", sort_by: "Sort by {column}",
               width: "{column} Width {n}" },
    linked: { tip: "Linked Households", feeds: "Also Feeds", fed_by: "Fed By", related: "Related" },
    tabs: { need: "Need You ({n})", waiting: "Waiting ({n})" }, documents: { one: "1 Document", many: "{n} Documents" },
    paging: { showing: "Showing {from}-{to} of {total} {noun}", previous: "Previous", next: "Next",
              nouns: { overview: "Returns", needs_review: "Files", reminders: "Drafts", clients: "Households" } },
    icons: { more_actions: "More Actions", remove_filter: "Remove Filter" }, filters: { work: "Work Waiting", all: "All" }, work: "Work Waiting",
    shared: "Shared", not_shared: "Not Shared",
    household_card: { contact: "Contact", shared_with: "Shared With", inbox_link: "Inbox Link", link_saved: "Saved", no_link: "Not Saved" },
    client_types: { individuals: "Individuals", businesses: "Businesses", trusts: "Trusts & Estates", nonprofits: "Nonprofits" },
  },
};
"""


#: The column headers' constants (SPEC-lists), lifted from pages.js as written:
#: the probes run the pages' own tables, not a copy of them.
PAGES_CONSTS = ("const PAGES_COLUMNS = {", "const PAGES_CELLS = ", "const PAGES_WIDTHS = ", "const PAGES_USUAL = ", "const PAGES_WIDTH_STEP = ",
                "const PAGES_WIDTHS_KEY = ", "const PAGES_ORDER_KEY = ", "let pagesOrder = ", "let pagesWidths = ",
                # The raised lists (pilot SPEC-lists 10-17): pages, tabs, reason cards, types, the panel.
                "const PAGES_REASON_ICONS = {", "const PAGES_SECTIONS = ", "let pagesPageAt = ", "let pagesEntered = ",
                "let pagesTab = ", "let pagesReasonPick = ", "let pagesClientType = ", "let pagesPanel = ", "let pagesYearless = ",
                # Long lists draw only the rows in view (P279).
                "const PAGES_VIRTUAL_FROM = ", "const PAGES_VIRTUAL_OVER_LEAST = ", "let pagesVirtualWired = ",
                # The one collator every name sort compares through (P264 N1).
                "const PAGES_COLLATOR = ")


#: The column headers' own functions (SPEC-lists), which every firm page and
#: pagesDraw now reach.
COLUMN_FUNCTIONS = ("pagesListOf", "pagesOrderBy",
                    "pagesColumnHeads", "pagesGrip", "pagesColumnKey", "pagesStoredWidths", "pagesWidthOf", "pagesSetWidth",
                    "pagesSaveWidths", "pagesApplyWidths", "pagesResetWidths", "pagesReviewSpec",
                    # The order kept on this PC (P199).
                    "pagesStoredOrder", "pagesSaveOrder",
                    # The raised lists (pilot SPEC-lists 10-17).
                    "pagesDetailCell", "pagesReasonTip", "pagesStatusCell", "pagesLinkMark", "pagesLinkMarkIn", "pagesShowPanel", "pagesPanelOpen",
                    "pagesClosePanel", "pagesOpenRowLinks", "pagesFootOf", "pagesFoot", "pagesTurn", "pagesPick", "pagesRedraw", "pagesPickButton", "pagesTabs",
                    "pagesFileCount", "pagesReasonCards", "pagesReviewGroup", "pagesSwitch", "pagesTypeFilter", "pagesReopenPanel",
                    # One field per column (pilot SPEC-firm-columns; P194, P195).
                    "pagesTaxpayer", "pagesFormCell", "pagesReturnHeading", "pagesReturnCells",
                    # The engine pages the lists (P278): the replies held, the choices forgotten on leaving, the page adopted.
                    "pagesReply", "pagesHeldPage", "pagesEnter", "pagesAdopt", "shellFirmAsk", "shellFirmMerge", "shellFirmShaped")


#: A row made apart from its registration, and the long list's own functions (P279): a list of more than
#: PAGES_VIRTUAL_FROM rows registers every row and makes only the nodes in view.
LONG_LIST_FUNCTIONS = ("pagesRegister", "pagesRowNode", "pagesIsChild", "pagesWindow", "pagesOver", "pagesListTop", "pagesVirtualList", "pagesVirtualMake",
                       "pagesVirtualNode", "pagesVirtualPlace", "pagesVirtualSize", "pagesVirtualMeasure", "pagesVirtualPlaceAll", "pagesVirtualWire",
                       "pagesVirtualReveal", "pagesActivateAt", "pagesKeyLong", "pagesVirtualNodeSaid", "pagesVirtualMeasureSaid")


def pages_consts() -> str:
    text = read("pages.js")
    out = []
    for head in PAGES_CONSTS:
        start = text.index(head)
        line_end = text.index("\n", start)
        end = text.index("\n};\n", start) + 3 if text[start:line_end].rstrip().endswith("{") else line_end
        out.append(text[start:end])
    return "\n".join(out)


RETURN_STATE = r"""
const item = (id, group, extra = {}) => ({ identifier: id, document: `Doc ${id}`, short_name: `Doc ${id}`, group, status_key: "Missing", manual_override: "",
  period: "", year: 2025, file_count: 0, expected_count: 1, received_date: null, ...extra });
const parked = (handle, extra = {}) => ({ handle, original_name: `${handle}.pdf`, decision: "Needs Review", group: "needs_you", code: "unmatched", received: "2026-03-03", bucket: "document", ...extra });
const movedRow = (handle, extra = {}) => ({ handle, original_name: `${handle}.pdf`, decision: "File Moved", group: "needs_you", code: "file-moved", received: "2026-03-02", ...extra });
const setAsideRow = (handle, extra = {}) => ({ handle, original_name: `${handle}.pdf`, decision: "Not Requested", group: "set_aside", code: "not-requested", received: "2026-03-01", ...extra });
const stateOf = (items, index = [], moved = []) => ({ paths: { engagement: "r1" }, engagement: { due: "2026-04-15" }, items, index, review: [], moved });
"""


def run_pages_dom(probe: str, tmp_path: Path, setup: str = "", functions=None):
    if NODE is None:
        pytest.skip("node is not on PATH (CI installs it)")
    wanted = functions or [
        "pagesReturn", "pagesReturnName", "pagesTitle", "pagesCaption", "pagesDue", "pagesSince", "pagesDay", "pagesReturnGroups", "pagesItemName",
        "pagesItemStatus", "pagesItemDetail", "pagesByName", "pagesReason", "pagesBlocks", "pagesRow", "pagesStepWords",
        "pagesReturnPlan", "pagesGroup", "pagesGroupStep", "pagesList", "pagesWorkRows", "pagesCounts", "pagesTally",
        "pagesHouseholdNotices", "pagesRoute", "pagesFiles", "h", "icon", "screenWords", "pagesSafe", "pagesEach", "pagesLabel",
        "pagesSafeName", "pagesTitleFor", "pagesReportBroken", "pagesRouteKey", "pagesDraw", "pagesBuild", "pagesYear", "pagesReturnSpecs",
        "pagesClientSpecs", "pagesRemember", "pagesRestore", "pagesFirmReturn", "pagesActivate", "pagesOverview", "pagesNeedsReview",
        "pagesReminders", "pagesClients", "pagesHousehold", "folderName", "pagesLinkWords",
        "pagesPathOf", "pagesFileLink", "pagesRunLink", "pagesLinkNode", "pagesCell", "pagesHeadLink", "pagesRunRowLink", "pagesWhere",
        "pagesNameCell", "pagesSteps", "pagesDrafts", "pagesRunRow", "pagesRunStep", "pagesPopup", "pagesEnableFor", "pagesRowRoute", "pagesKey", "pagesTitle",
        *COLUMN_FUNCTIONS, *LONG_LIST_FUNCTIONS,
    ]
    wanted = [*wanted, *[name for name in ENGINE_FUNCTIONS if name not in wanted]]
    shell = read("shell.js")
    consts = lift_line("const EL_ATTRIBUTES = new Set([", "app.js") + js_function("el", "app.js") + "\n" + shell[shell.index("const SVG_NS = "):shell.index("\n", shell.index("const SVG_NS = "))]
    lifted = consts + "\n" + pages_consts() + "\n" + store_functions() + "\n" + "\n".join(js_function(name, "pages.js" if f"function {name}(" in read("pages.js") else "shell.js") for name in wanted)
    script = tmp_path / "pages_probe.js"
    script.write_text(f"{FAKE_DOM}\n{PAGE_WORDS}\n{RETURN_STATE}\n{setup}\n{lifted}\nprocess.stdout.write(JSON.stringify((() => {{ {probe} }})()));\n",
                      encoding="utf-8", newline="\n")
    done = subprocess.run([NODE, str(script)], capture_output=True, text=True, encoding="utf-8", timeout=120, check=False, env=ENGINE_ENV)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


#: The scenarios of the harness's stub that draw notices, and the pages' own functions that draw them.
NOTICE_FUNCTIONS = ["renderMachineNotices", "renderAfterInstall", "renderShortOfRoom", "showLock", "lockStarted", "noticeOf"]


def run_notices(probe: str, tmp_path: Path, vocab_notices: str = "{}"):
    """Run the harness's own stub (pilot/harness/stub.js, with the API's long
    sentences in it) in a vm, get the replies it gives, and hand them to the
    functions of app.js, shell.js and pages.js that draw notices, as written.
    Every notice they draw, and every line they send to the error log, is
    recorded."""
    if NODE is None:
        pytest.skip("node is not on PATH (CI installs it)")
    lifted = "\n".join([js_function(name, "app.js") for name in NOTICE_FUNCTIONS] + [js_function("shortNotice", "shell.js"),
                                                                                       js_function("pagesHouseholdNotices", "pages.js")])
    harness = (REPO / "pilot" / "harness" / "stub.js").read_text(encoding="utf-8")
    mirror = json.dumps(api._vocab())
    script = tmp_path / "notices_probe.js"
    script.write_text(f"""
const vm = require("vm");
const fill = (p, v) => p.replace(/\\{{(\\w+)\\}}/g, (_, k) => v[k] ?? "");
const stubSource = {json.dumps(harness)};
const mirror = JSON.parse({json.dumps(mirror)});
async function replies(scenario) {{
  const window = {{ __VOCAB__: mirror }};
  vm.runInContext(stubSource, vm.createContext({{ window, location: {{ search: `?scenario=${{scenario}}` }}, URLSearchParams, setTimeout, console, Date, Intl }}));
  const list = await window.tracker.call(["list"]);
  const state = await window.tracker.call(["state", "--engagement", list.engagements[0].path]);
  return {{ list, state }};
}}
let vocab = null; let active = ""; let locked = false; let lockStale = false;
const drawn = []; const logged = [];
window = {{ tracker: {{ logError: (text) => logged.push(text) }} }};
const keyedNotice = (key, failure) => {{ drawn.push([key, failure.sentence]); return true; }};
const clearNotice = () => {{}};
let syncNotices = (prefix, wanted) => {{ for (const one of wanted) {{ drawn.push([`${{prefix}}:${{one.key.slice(0, 8)}}`, one.failure.sentence]); if (one.detail) logged.push(one.detail); }} }};
const stopLockWatch = () => {{}}; const setLocked = () => {{}}; const watchLock = () => {{}};
const acceptFolderName = () => {{}};
{lifted}
(async () => {{
  const out = await (async () => {{ {probe} }})();
  process.stdout.write(JSON.stringify(out));
}})();
""", encoding="utf-8", newline="\n")
    done = subprocess.run([NODE, str(script)], capture_output=True, text=True, encoding="utf-8", timeout=60, check=False)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


#: One firm reply for the four lists: five returns (one unreadable), three
#: waiting files in two returns, three drafts (one held).
#: The engine for a probe (P278): the made-up firm's WHOLE reply is `shellFirmData`; `settle(list)` asks the real
#: ``tracker.firm_pages`` for the page the window wants (`shellFirmAsk`) and holds it as the window does
#: (`shellFirmMerge`), so a probe draws and asks what the engine answers, never a copy of its rules.
ENGINE_BRIDGE = r"""
  let shellFirmData = null; let shellFirmAsOf = "";
  let shellFirmNow = { status: "ok", data: null };   // what the window holds: the pages the engine cut (P278)
  const shellFirm = () => (shellFirmAsOf ? { ...shellFirmNow, asOf: shellFirmAsOf } : shellFirmNow);
  globalThis.shellRoute = globalThis.shellRoute || { level: "overview" };   // a probe that holds its own (let) keeps it
  const { execFileSync } = require("child_process");
  const enginePages = new Map();
  const engineAnswers = (ask) => {
    const words = { need: vocab.screen.counts.need, waiting: vocab.screen.counts.waiting, complete: vocab.screen.counts.complete,
      paused: vocab.screen.notices.paused, held: vocab.screen.held, client_types: vocab.client_type_forms,
      stages: Object.fromEntries(((vocab.reminder || {}).stages || []).map((one) => [one.number, one.short])),
      reasons: Object.fromEntries(Object.entries(vocab.reasons).map(([code, one]) => [code, typeof one === "object" ? one.short : one])) };
    const walk = { returns: Object.fromEntries(shellFirmData.returns.map((one) => [one.path, (shellReturn(one.path) || { return_name: one.path.split(/[\\/]/).pop() }).return_name])),
      households: households.map((one) => ({ name: one.name, path: one.path, links: one.links || [], forms: (one.returns || []).map((r) => r.form) })) };
    const input = JSON.stringify({ whole: shellFirmData, names: walk, words, ask });
    if (!enginePages.has(input)) {
      enginePages.set(input, JSON.parse(execFileSync(process.env.FIRM_PY, ["-c", process.env.FIRM_SNIPPET], { input, cwd: process.env.FIRM_REPO, encoding: "utf8" })));
    }
    return JSON.parse(JSON.stringify(enginePages.get(input)));
  };
  // What shellTurnFirm does, at once: the page wanted of the list is asked of the engine and held.
  const settle = (...lists) => {
    for (const list of lists) {
      const reply = engineAnswers(shellFirmAsk(list));
      shellFirmNow = { status: "ok", data: shellFirmMerge(shellFirmNow.data, reply) };
      pagesAdopt(reply);
    }
  };
  const heldRows = (list) => shellFirmNow.data.replies[list].page.rows;
"""


FIRM_LISTS = ENGINE_BRIDGE + r"""
  const openNewHousehold = () => {};
  let shellRoute = { level: "overview" };
  const box = new Element("div"); const $ = (id) => box;
  Object.assign(vocab.screen, {
    figures: { need: "Need a Person", waiting: "Waiting on Taxpayers", complete: "Complete" }, work: "Work Waiting",
    filters: { work: "Work Waiting", all: "All" }, held: "Held",
    empty: { overview: "Nothing Is Waiting", next_sort: "Next Sort {time}", needs_review: "Nothing Needs Review", reminders: "No Drafts Ready",
             clients: "No Households Yet", work: "No Work Waiting", returns: "No Returns Yet", received: "Nothing Received Yet" },
  });
  vocab.reminder = { stages: [{ number: 1, short: "Heads Up" }, { number: 2, short: "Checking In" }, { number: 3, short: "Final Notice" }] };
  vocab.reasons = { unmatched: { short: "Could Not Tell" }, "opened-not-across": { short: "Came in Email or Zip" } };
  shellReturn = (path) => ({ return_name: path.split("/").pop(), household: "", year: 2025 });
  households = ["Alpha", "Bravo", "Charlie", "Delta", "Echo"].map((name) => ({ name, path: `c/${name}` }));
  const zero = { needs_you: 0, waiting: 0, received: 0, set_aside: 0 };
  const line = (name, household, extra) => ({ path: `r/${name}`, household, year: 2025, form: name.split(" - ")[0], counts: { ...zero }, oldest: null, due: null, problem: "",
                                              draft: { ready: false, stage: 0, held: 0, drafted: null }, ...extra });
  shellFirmData = { paths: {}, totals: { need: 3, waiting: 2, complete: 0 }, next_sort: null, returns: [
    line("1040 - Alpha", "Alpha", { counts: { ...zero, needs_you: 3 }, oldest: "2026-03-05", draft: { ready: true, stage: 1, held: 0, drafted: "2026-03-01" } }),
    line("1065 - Bravo", "Bravo", { counts: { ...zero, needs_you: 12 }, oldest: "2026-03-01", draft: { ready: true, stage: 2, held: 1, drafted: "2026-03-02" } }),
    line("1040 - Charlie", "Charlie", { year: 2024, counts: { ...zero, waiting: 2 }, due: "2026-04-15", draft: { ready: true, stage: 3, held: 0, drafted: "2026-02-20" } }),
    line("1040 - Delta", "Delta", { counts: { ...zero, waiting: 5 } }),
    line("1041 - Echo", "Echo", { problem: "Could Not Be Read" }),
  ], files: [
    { return: "r/1040 - Alpha", year: 2025, name: "b.pdf", handle: "h1", code: "unmatched", received: "2026-03-05", suggestion: "W-2", open_key: "" },
    { return: "r/1040 - Alpha", year: 2025, name: "a.pdf", handle: "h2", code: "opened-not-across", received: "2026-03-07", suggestion: "", open_key: "" },
    { return: "r/1065 - Bravo", year: 2025, name: "z.pdf", handle: "h3", code: "unmatched", received: "2026-03-01", suggestion: "K-1", open_key: "" },
  ] };
  const turned = [];
  const shellTurnFirm = (list, then) => { turned.push(list); settle(list); pagesDraw(shellRoute, box); if (then) then(); };
  // A person arrives on a firm list: its first page is asked and drawn.
  const draw = (level) => { shellRoute = { level }; pagesEnter(shellRoute); settle(pagesListOf(shellRoute)); pagesDraw(shellRoute, box); return box; };
  const names = (page) => page.byClass("row").map((row) => row.byClass("row-name")[0].textContent);
  const sorts = (page) => page.find((one) => one.attrs.role === "columnheader").map((one) => one.attrs["aria-sort"] || "");
"""


def run_lists(probe: str, tmp_path: Path, extra: str = ""):
    return run_pages_dom(probe, tmp_path, setup=FIRM_LISTS + extra,
                         functions=[*re.findall(r"^function (\w+)\(", read("pages.js"), flags=re.M), "h", "icon", "screenWords", "folderName",
                                    "shellFirmAsk", "shellFirmMerge", "shellFirmShaped"])


def lift(*names: str) -> str:
    """The named functions as they are written, each from the renderer file
    that defines it: one of the app's own scripts (the pilot's define
    ``show``, ``fill`` and ``render`` of their own, inside their namespaces)."""
    out = []
    for name in names:
        source = next((one for one in APP_SCRIPTS if f"function {name}(" in read(one)), None)
        assert source, name
        out.append(js_function(name, source))
    return "\n".join(out)


def lift_line(head: str, source: str) -> str:
    """One top-level declaration that starts with ``head``, to its end (a
    one-line ``let``, or a ``new Set([`` list)."""
    text = read(source)
    start = text.index(head)
    end = text.index("]);\n", start) + 4 if head.endswith("[") else text.index("\n", start) + 1
    return text[start:end]


#: A DOM for the speed round's probes: any id is an element, made on first
#: ask, and every element keeps its parent, classes, attributes and children.
SPEED_DOM = r"""
class Node {}
class Text extends Node { constructor(data) { super(); this.data = data; this.parent = null; } get textContent() { return this.data; } }
class El extends Node {
  constructor(tag, id) { super(); this.tag = tag; this.id = id || ""; this.className = ""; this.dataset = {}; this.attrs = {}; this.kids = [];
    this.hidden = false; this.disabled = false; this.parent = null; this.handlers = {};
    this.style = { props: {}, setProperty(key, value) { this.props[key] = value; }, removeProperty(key) { delete this.props[key]; } }; }
  get classList() {
    const self = this;
    const now = () => self.className.split(" ").filter(Boolean);
    return { add(...names) { self.className = [...new Set([...now(), ...names])].join(" "); },
             remove(...names) { self.className = now().filter((one) => !names.includes(one)).join(" "); },
             toggle(name, on) { const want = on === undefined ? !now().includes(name) : Boolean(on); if (want) this.add(name); else this.remove(name); return want; },
             contains(name) { return now().includes(name); } };
  }
  setAttribute(key, value) { this.attrs[key] = String(value); }
  getAttribute(key) { return key in this.attrs ? this.attrs[key] : null; }
  removeAttribute(key) { delete this.attrs[key]; }
  adopt(one) { const node = one instanceof Node ? one : new Text(String(one)); if (node.parent) node.remove(); node.parent = this; return node; }
  append(...nodes) { for (const one of nodes) this.kids.push(this.adopt(one)); }
  prepend(...nodes) { this.kids.unshift(...nodes.map((one) => this.adopt(one))); }
  replaceChildren(...nodes) { for (const one of this.kids) one.parent = null; this.kids = []; this.append(...nodes); }
  remove() { if (this.parent) { this.parent.kids = this.parent.kids.filter((one) => one !== this); this.parent = null; } }
  get childNodes() { return this.kids; }
  get children() { return this.kids.filter((one) => one instanceof El); }
  focus() {}
  addEventListener(type, fn) { (this.handlers[type] = this.handlers[type] || []).push(fn); }
  get textContent() { return this.kids.map((one) => one.textContent).join(""); }
  set textContent(value) { this.replaceChildren(String(value)); }
  find(test, out = []) { for (const one of this.kids) if (one instanceof El) { if (test(one)) out.push(one); one.find(test, out); } return out; }
  byClass(name) { return this.find((one) => one.classList.contains(name)); }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
  querySelectorAll(selector) {
    const own = selector.replace(/^:scope > /, "");
    const pool = own === selector ? this.find(() => true) : this.children;
    if (own.startsWith(".")) return pool.filter((one) => one.classList.contains(own.slice(1)));
    if (own.startsWith("#")) return pool.filter((one) => one.id === own.slice(1));
    return pool.filter((one) => one.tag === own);
  }
}
const ELS = {};
const $ = (id) => ELS[id] || (ELS[id] = new El("div", id));
const document = { createElement: (tag) => new El(tag), createElementNS: (_ns, tag) => new El(tag), contains: () => true };
const window = { tracker: { logError() {} } };
"""


#: The reminder sheet's world: two returns' cards, a read that waits until the
#: probe lets it land, and a clipboard that records what was put on it.
REMINDER_SHEET = r"""
let vocab = {
  screen: { loading: "Loading", sheet: { reminder: "Draft Reminder" } },
  reminder: { stages: [], palette: { ink: "#000" }, hold_colour: "ink", stage_group: "Stage", edited_by_hand: "Edited", subject_prefix: "Subject: ",
              heading: "Letter", letter_ink: { body: "ink", muted: "ink", paper: "ink" }, never_drafted_line: "Never drafted", copied: "Copied", approve: "Approve" },
};
const card = (ret) => ({ held: [], unsorted: 0, stage: 1, editable: true, file: { edited: false }, subject: `For ${ret}`, letter: { greeting: `Dear ${ret}` },
                         html: `<p>${ret}</p>`, text: `Letter for ${ret}`, last: null, approved: null, lapsed: false, fingerprint: `fp-${ret}` });
let active = "A"; let lastState = { paths: { engagement: "A" }, reminder_card: { reminder: card("A") } };
let shellRoute = { level: "reminders" };
const FIRM_LEVELS = ["overview", "needs-review", "reminders", "clients"];
const reads = [];
const showReturn = (path) => new Promise((resolve) => reads.push({ path, land() {
  active = path; lastState = { paths: { engagement: path }, reminder_card: { reminder: card(path) } };
  drawReminderReply(lastState.reminder_card); resolve(true); } }));
let drafts = [{ ret: "B" }, { ret: "C" }];
const pagesDrafts = () => drafts; const pagesWhere = () => null; const pagesDay = (d) => d;
const openDialog = () => {}; const setTipIfCut = () => {}; const applyLock = () => {}; const closeSheet = () => {};
const failed = (err) => { throw err; }; const outcome = () => {};
const clipboard = []; const sent = [];
const navigator = { clipboard: { write: async (items) => { clipboard.push(items[0].parts["text/plain"].text); } } };
class ClipboardItem { constructor(parts) { this.parts = parts; } }
class Blob { constructor([text]) { this.text = text; } }
const call = async (args, payload) => { sent.push([args[0], payload]); return { reminder: card(active) }; };
const withEng = (name) => [name, "--engagement", active];
const loadReminder = async () => {};
let sheetNow = null; let sheetGeneration = 0;
const tick = () => new Promise((resolve) => setImmediate(resolve));
const actions = () => ({ card: reminderCard ? reminderCard.text : null, shown: !$("reminder-actions").hidden, busy: $("sheet").getAttribute("aria-busy"),
                         outline: $("reminder-wait").byClass("row-skeleton").length, word: $("reminder-wait").textContent });
"""


REMINDER_FUNCTIONS = ("el", "h", "show", "fill", "screenWords", "shellSkeleton", "shellWaiting", "stageOf", "stageInk", "marked", "holdLine", "reminderStatus", "lines",
                      "letterNodes", "drawReminderReply", "drawReminderLine", "drawReminder", "forgetReminderCard", "reminderWaitOver",
                      "reminderCardReady", "copyReminder", "approveReminder", "sheetSet", "sheetMore", "sheetFrame", "openReminder",
                      "sheetDraftsAfter", "sheetNextDraft", "sheetShow", "sheetDrawCheck", "sheetAfter")


def run_speed(setup: str, functions, probe: str, tmp_path: Path, consts: str = ""):
    """Run a probe against the named functions, lifted as written, in SPEED_DOM."""
    if NODE is None:
        pytest.skip("node is not on PATH (CI installs it)")
    script = tmp_path / "speed_probe.js"
    script.write_text(f"{SPEED_DOM}\n{setup}\n{consts}\n{lift(*functions)}\n"
                      f"(async () => {{ {probe} }})().then((out) => process.stdout.write(JSON.stringify(out)));\n",
                      encoding="utf-8", newline="\n")
    done = subprocess.run([NODE, str(script)], capture_output=True, text=True, encoding="utf-8", timeout=60, check=False)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def run_reminder_sheet(probe: str, tmp_path: Path):
    consts = "let reminderCard = null; let reminderCardFor = null;\n" + lift_line("const EL_ATTRIBUTES = new Set([", "app.js")
    return run_speed(REMINDER_SHEET, REMINDER_FUNCTIONS, probe, tmp_path, consts)


#: The early Overview (P221): window.tracker.call answers when the probe says.
EARLY_FIRM = r"""
const sentEarly = [];
window.tracker.call = (args, payload) => new Promise((resolve) => sentEarly.push({ args, payload, resolve }));
"""



#: shell.js's load of the firm's counts, lifted whole, with a `firm` that
#: answers only when the probe says so.
FIRM_LOAD = r"""
let vocab = { commands: ["list", "firm"], screen: { loading: "Loading", updating: "Updating", reading_households: "Reading {n} of {total} Households",
                                                    updating_as_of: "Updating, as of {time}", notices: { firm_failed: "Counts Not Available" } } };
const fill = (p, v) => p.replace(/\{(\w+)\}/g, (_, k) => v[k] ?? "");
let shellRoute = { level: "return" }; let shellPageBusy = false; let shellRootSet = false; let shellPaths = {}; let shellLastPass = null;
let shellFirmNow = { status: "idle", data: null }; let shellFirmAsked = false; let shellFirmEarly = null; let shellClock = 0;
let shellFirmLast = null; let shellFirmAsOf = "";
let shellFirmSentAt = 0; let shellWroteAt = 0; const shellFirmHeld = new Map(); let shellFirmCount = null; let shellFirmSlow = false;
let shellFirmTimer = null; const SHELL_FIRM_SLOW_MS = 2000;
let shellLastPassStopped = false;   // the last-pass asking (P256, P277) is not this probe's
const FIRM_LEVELS = ["overview", "needs-review", "reminders", "clients"];
const asked = []; const notices = []; const drawn = [];
// As call() does: a reply with an error throws its envelope.
const call = (args, payload) => new Promise((resolve, reject) => asked.push({ args, payload, resolve: (reply) => (reply.error ? reject(new TrackerError(reply)) : resolve(reply)) }));
// What the engine answers for the Overview (P278, SPEC-ui-menu-speed 4.3): one page, the totals and each return's counts; heldOf(n) is the answer the window holds from it.
const firmOf = (n) => ({ view: "v1", totals: {}, next_sort: null, paths: {}, return_counts: [{ path: "r1", counts: { needs_you: n } }],
  page: { list: "overview", at: 0, pages: 1, from: 1, to: 1, total: 1, order: null, filter: { tab: "all" }, counts: { all: 1, need: 1, waiting: 0 }, many_years: false, rows: [] } });
const heldOf = (n) => shellFirmMerge(null, firmOf(n));
let shellTurns = 0; let shellTurnGen = 0; let shellTurnThen = null;
let pagesPageAt = {}; let pagesTab = "all"; let pagesReasonPick = ""; let pagesClientsAll = false; let pagesClientType = "";
const pagesStoredOrder = () => ({}); const pagesEnter = () => {};
// A reply of the engine for one page of a list, as the probes land it (the page's own words are not read by them).
const pageOf = (list, at = 0, view = "v1", more = {}) => ({ ...firmOf(1), view,
  page: { list, at, pages: 3, from: at * 50 + 1, to: at * 50 + 50, total: 150, order: null,
          filter: { overview: { tab: "all" }, needs_review: { reason: "" }, reminders: {}, clients: { all: false, type: "" } }[list], counts: {}, many_years: false, rows: [], ...more } });
let failedAs = null;   // a probe that records the failures the page says, with their Retry, in place of throwing them
const stateOf = (n) => ({ paths: { engagement: "r1" }, counts: { needs_you: n } });
const pagesTally = (state) => state.counts; const sheetStateArrived = () => {};
let shellChanged = () => {};
const noticedAs = [];   // each notice said directly, with its kind and its Retry
const notice = (failure, opts = {}) => { notices.push(failure.sentence); noticedAs.push({ sentence: failure.sentence, kind: failure.kind, retry: opts.retry }); };
const failureSentence = () => "";
const failed = (err, retry) => { if (failedAs) { failedAs.push({ sentence: err.message, kind: err.failure.kind, retry }); return; } throw err; };
const warningNotices = (list) => notices.push(...list);
class TrackerError extends Error { constructor(result) { super(result.error); this.result = result; this.failure = result.failure || { sentence: result.error, kind: "failed" }; } }
const tick = async () => { for (let i = 0; i < 5; i += 1) await new Promise((resolve) => setImmediate(resolve)); };
const firms = () => asked.filter((one) => one.args[0] === "firm").length;
const land = async (i, reply) => { asked[i].resolve(reply); await tick(); };
"""


FIRM_LOAD_FUNCTIONS = ("el", "h", "screenWords", "shellAdopt", "shellAskFirmNow", "shellDropEarlyFirm", "shellAskFirmLast", "shellLastOf", "shellShowLast",
                       "takeReply", "shellAdoptEarly", "shellAskFirm", "shellFirmSent", "shellFirmAsk", "shellFirmList", "shellFirmMerge", "shellFirmShaped",
                       "shellFirmHolds", "shellFirmBrought", "shellFirmFollow", "shellTurnDone", "shellTurnFirm", "pagesListOf", "pagesAdopt",
                       "shellFirmDone", "shellFirmTookLong", "shellWriteLanded", "shellFirmProgress", "shellReading", "shellReadingNodes",
                       "shellSetReading", "shellDrawReading", "shellLoadFirm", "shellFollowsCounts", "shellFirmUpdating", "shellUpdating",
                       "shellMarkUpdating", "shellStateArrived", "shellPageReadsState", "shellCountsDiffer")


def run_firm_load(probe: str, tmp_path: Path, setup: str = "", functions=()):
    """FIRM_LOAD, with the page's draw faked unless ``functions`` lifts it."""
    if "drawPage" not in functions:
        setup += '\nconst shellDraw = () => drawn.push(shellRoute.level); const drawPage = () => drawn.push("page");\n'
    consts = lift_line("const EL_ATTRIBUTES = new Set([", "app.js")
    return run_speed(FIRM_LOAD + setup, (*FIRM_LOAD_FUNCTIONS, *functions), probe, tmp_path, consts)


#: The firm pages drawn while their counts are asked (P222): a clock the probe
#: moves on, two side counts, and a page the fake pagesDraw fills.
FIRM_PAGE = r"""
const timers = [];
const setTimeout = (fn, ms) => { timers.push({ fn, ms }); return timers.length; };
const clearTimeout = (id) => { if (id && timers[id - 1]) timers[id - 1].fn = null; };
const waiting = () => timers.filter((one) => one.fn).map((one) => one.ms);
const passTime = () => { for (const one of timers) if (one.fn) { const fn = one.fn; one.fn = null; fn(); } };
const pagesDraw = (route, page) => {
  const figure = new El("b"); figure.className = "figure-number"; figure.append("3");
  const row = new El("div"); row.className = "row"; row.append("a row");
  page.replaceChildren(figure, row);
  page.dataset.list = pagesListOf(route);
};
const routeTitle = () => "";
const pagesLeave = () => {};
let shellPageFailed = false;
const shellDraw = () => { drawn.push(shellRoute.level); drawCounts(); drawPage(); };
shellChanged = () => drawCounts();
const sides = [0, 1].map(() => { const side = new El("button"); side.dataset.section = "overview"; const count = new El("span"); count.className = "side-count"; side.append(count); return side; });
document.querySelectorAll = (selector) => (selector === ".side-section[data-section]" ? sides : []);
const shellCounts = () => ({ overview: 3 });
// index.html's one status for "Updating": every time its words are set is
// counted, since a status set again is read out again.
let saidSet = 0;
Object.defineProperty($("page-updating"), "textContent", {
  get() { return this.kids.map((one) => one.textContent).join(""); },
  set(value) { saidSet += 1; this.replaceChildren(String(value)); },
});
const looks = () => {
  const page = $("page");
  return { busy: page.getAttribute("aria-busy"), updating: page.classList.contains("is-updating"),
           said: $("page-updating").textContent, saidSet,
           rows: page.children.map((one) => one.className),
           inPage: page.byClass("page-updating").length,
           held: sides.map((one) => one.byClass("side-count")[0].classList.contains("is-held")),
           reading: page.byClass("firm-reading-words").map((one) => one.textContent),
           bars: page.find((one) => one.getAttribute("role") === "progressbar").map((one) =>
             [one.getAttribute("aria-valuenow"), one.getAttribute("aria-valuemax"), one.getAttribute("aria-labelledby")]),
           hidden: page.byClass("visually-hidden").map((one) => one.textContent) };
};
"""


FIRM_PAGE_FUNCTIONS = ("drawPage", "shellLoading", "shellSkeleton", "drawTitleOnly", "drawCounts")


def run_firm_page(probe: str, tmp_path: Path):
    return run_firm_load(probe, tmp_path, FIRM_PAGE, FIRM_PAGE_FUNCTIONS)


#: A Sort's end as app.js's passEnded meets it (P228): the shown return's
#: state and the list through call() (the probe lands each), the Overview
#: through window.tracker.call (EARLY_FIRM), and app.js's other names faked.
SORT_END = EARLY_FIRM + r"""
let scanning = null; let active = "r1"; let viewGeneration = 1; const kept = []; const rendered = [];
const scanDone = () => {};
const adoptList = (listed) => shellAdopt(listed);
const withEng = (command) => [command, "--engagement", active];
const renderFor = (view, state) => { if (view !== viewGeneration) return false; rendered.push(state.paths.engagement); shellStateArrived(state); return true; };
const showReturn = () => {};
const runScan = () => {};
const scanSummary = () => ({ cls: "ok", text: "" });
const sortReturnSaid = () => "";
const keepSortAnswer = (ran, asked, answer) => kept.push({ ran, asked, answer: answer.length });
const sent = () => [...asked.map((one) => one.args[0]), ...sentEarly.map((one) => one.args[0])];
const ofCommand = (name) => asked.find((one) => one.args[0] === name);
const landOf = async (name, reply) => { ofCommand(name).resolve(reply); await tick(); };
"""


def run_sort_end(probe: str, tmp_path: Path):
    return run_firm_load(probe, tmp_path, SORT_END, ("passEnded",))


#: The launch (P229): the probe lands `firm` (sentEarly[0]) and `firm-last`
#: (sentEarly[1]) when it says, before or after the list's words arrive.
#: ``lastOf`` is tracker.api's firm-last as it answers (handoff P229, "The
#: contract"): the firm reply's own fields at the top level, with
#: ``last: true`` and ``as_of``, the cache's "HH:MM"; ``refused`` is its
#: refusal. ``overviewSays`` is the Overview's own line (pagesAsOf), and
#: ``timeOf`` the app's words for a time (pagesTime).
LAST_COUNTS = EARLY_FIRM + FIRM_PAGE + r"""
const lastOf = (n, asOf = "09:14") => ({ ...firmOf(n), files: [], paths: {}, next_sort: null, warnings: [], last: true, as_of: asOf });
const refused = { last: null, warnings: [] };
const overviewSays = () => pagesAsOf();
const timeOf = (clock) => pagesTime(clock);
const words = vocab;
const launch = () => { vocab = null; shellRoute = { level: "overview" }; shellAskFirmNow(); shellAskFirmLast(); };
const listLands = () => { vocab = words; shellAdopt({ root: "/root" }); };
const early = (name) => sentEarly.find((one) => one.args[0] === name);
const counts = () => (shellFirmNow.data ? shellFirmNow.data.return_counts[0].counts.needs_you : null);
"""


def run_last_counts(probe: str, tmp_path: Path):
    return run_firm_load(probe, tmp_path, LAST_COUNTS, (*FIRM_PAGE_FUNCTIONS, "shellFirm", "pagesAsOf", "pagesTime"))


#: The page's scroller and a row's measured height, as a probe's fakes: `H` is what a drawn row measures (the
#: density's own, 40 or 32), `pageBox` is #page (800px of view), and `draw` puts a return of `items` in it, the way
#: pagesDraw does - the lists made, the page replaced, every long list measured and its rows placed. The list sits
#: 100px down the page's content, and its rect moves with the scroll as a real one does.
LONG_SETUP = r"""
const hideTip = () => {}; const showTipNow = () => {};
let H = 40;
Object.defineProperty(Element.prototype, "offsetHeight", { get() { return H; }, configurable: true });
const pageBox = new Element("div");
pageBox.scrollTop = 0; pageBox.clientHeight = 800; pageBox.getBoundingClientRect = () => ({ top: 0 });
const $ = (id) => (id === "page" ? pageBox : null);
const parkedFiles = (n, extra = () => ({})) => Array.from({ length: n }, (_, i) => parked(`f${String(i + 1).padStart(4, "0")}`, extra(i)));
const draw = (index, items = []) => {
  lastState = stateOf(items, index);
  pagesUid = 0; pagesTokens.clear(); pagesBroken = [];
  pageBox.replaceChildren(...pagesReturn({ level: "return", ret: "r1", year: 2025 }));
  pageBox.scrollTop = 0;
  for (const list of pageBox.querySelectorAll(".rows.is-virtual")) list.getBoundingClientRect = () => ({ top: 100 - pageBox.scrollTop });
  pagesVirtualMeasure(pageBox);
  return pageBox.querySelectorAll(".rows.is-virtual")[0];
};
const scrollTo = (top) => { pageBox.scrollTop = top; pagesVirtualPlaceAll(pageBox); };
"""


def run_long(probe: str, tmp_path: Path, setup: str = ""):
    return run_pages_dom(probe, tmp_path, setup=LONG_SETUP + setup)


def content() -> dict:
    text = read("pilot-content.js")
    begin, end = "// PILOT-CONTENT-BEGIN\n", "// PILOT-CONTENT-END"
    assert text.count(begin) == 1 and text.count(end) == 1
    return json.loads(text.split(begin)[1].split(end)[0])


#: The real main.js under node with Electron stood in for: the menu it sets and
#: the pop-ups it opens are recorded as plain data (a label, whether it is
#: enabled, its accelerator, its role), items are "clicked" by label, and the
#: tracker child process is a fake that answers ``list`` with a vocabulary. A
#: scenario is a list of steps; the harness prints what happened.
MENU_HARNESS = r"""
const Module = require("module");
const EventEmitter = require("events");
const realFs = require("fs");
const [mainJs, scenarioJson] = process.argv.slice(2);
const sc = JSON.parse(scenarioJson);
// Off Windows the fallback is Electron's userData; "win32" is %LOCALAPPDATA%.
Object.defineProperty(process, "platform", { value: sc.platform || "linux" });
// A Mac is refused below Apple silicon and macOS 14 (SPEC-mac R6), so a scenario
// that stands in for one says which chip and which Darwin release it has.
if (sc.arch) Object.defineProperty(process, "arch", { value: sc.arch });
if (sc.release) require("os").release = () => sc.release;
if (sc.localAppData !== undefined) process.env.LOCALAPPDATA = sc.localAppData;
process.resourcesPath = process.resourcesPath || "/resources";
const log = { menus: [], popups: [], sends: [], opened: [], revealed: [], answers: [], backgrounds: [], windowOptions: null,
              userModelIds: [], spawned: [] };
let openHandler = null;
let menuHandler = null;
let trackerHandler = null;
let updated = null;
const theme = { shouldUseDarkColors: !!sc.dark, shouldUseHighContrastColors: !!sc.contrast,
                themeSource: "", on(name, fn) { if (name === "updated") updated = fn; } };
const snapshot = (items) => items.map((i) => ({
  label: i.label, type: i.type, role: i.role, enabled: i.enabled, accelerator: i.accelerator, checked: i.checked,
  submenu: i.submenu ? snapshot(i.submenu) : undefined }));
let live = { bar: null, popup: null };
// What main.js has started and not yet seen finish: Electron's ready, a fake
// tracker child until it closes, a file check (fs.promises). The harness waits
// for this to reach nought, never for a fixed time: a busy PC (12 test files at
// once) once took longer than the 60 ms it used to wait for a file check (P200).
let pending = 0;
const track = (promise) => {
  pending += 1;
  const done = () => { pending -= 1; };
  promise.then(done, done);
  return promise;
};
// Every continuation of a settled promise runs before the next turn of the
// event loop, so a turn with nothing pending means main.js has done answering.
const settle = async () => {
  do { await new Promise((resolve) => setImmediate(resolve)); } while (pending > 0);
};
const win = {
  isDestroyed: () => false,
  getContentBounds: () => ({ width: 1400, height: 900 }),
  setBackgroundColor: (c) => log.backgrounds.push(c),
  loadFile() {}, on() {}, isMinimized: () => false, focus() {},
  webContents: { setWindowOpenHandler() {}, on() {}, session: { flushStorageData() {} },
                 send: (channel, message) => log.sends.push({ channel, message }) },
};
class BrowserWindow {
  constructor(options) { log.windowOptions = options; return win; }
  static getAllWindows() { return [win]; }
}
const electron = {
  app: { isPackaged: !!sc.packaged, requestSingleInstanceLock: () => true, quit() {}, on() {},
         setPath() {}, setAppUserModelId(id) { log.userModelIds.push(id); },
         getPath: (name) => { if (name === "appData") return "appdata";
                              if (!sc.userData) throw new Error("no such path"); return sc.userData; },
         whenReady: () => track(Promise.resolve()) },
  BrowserWindow,
  Menu: {
    buildFromTemplate: (template) => ({ template, popup(options) {
      live.popup = template;
      log.popups.push({ items: snapshot(template), options });
    } }),
    setApplicationMenu(menu) {
      live.bar = menu.template;
      log.menus.push(snapshot(menu.template));
    },
  },
  ipcMain: { handle(name, fn) {
               if (name === "tracker-cmd") trackerHandler = fn;
               if (name === "open-path") openHandler = fn;
             },
             on(name, fn) { if (name === "menu") menuHandler = fn; } },
  nativeTheme: theme,
  shell: { openPath: async (p) => { log.opened.push(p); return ""; },
           showItemInFolder: (p) => { log.revealed.push(p); } },
  dialog: {},
};
const listReply = () => ({ vocab: { commands: ["list", "after-install"], menu: sc.vocabMenu,
                                    path_kinds: sc.pathKinds,
                                    shell: { error_log: sc.errorLog } }, paths: sc.paths });
const fakeSpawn = (cmd, args) => {
  const proc = new EventEmitter();
  log.spawned.push(cmd);
  proc.stdout = new EventEmitter();
  proc.stdout.setEncoding = () => {};
  proc.stderr = new EventEmitter();
  if (args.includes("--resident")) {
    // The engine (P276) stays up and answers the frame it is handed: a line {id, argv, bytes},
    // then its reply and an end line. Never closed here, or the shell would log an engine's end.
    let framed = Buffer.alloc(0);
    proc.pid = 1;
    proc.kill = () => {};
    proc.stdin = { on() {}, end() {},
      write(chunk) {
        framed = Buffer.concat([framed, Buffer.from(chunk)]);
        for (;;) {
          const at = framed.indexOf(10);
          if (at < 0) return true;
          const head = JSON.parse(framed.slice(0, at).toString("utf8"));
          if (framed.length - at - 1 < head.bytes) return true;       // the payload's bytes are part of the frame
          framed = framed.slice(at + 1 + head.bytes);
          pending += 1;
          setImmediate(() => {
            if (head.argv.includes("list")) proc.stdout.emit("data", JSON.stringify(listReply()) + "\n");
            proc.stdout.emit("data", "\n" + JSON.stringify({ engine_end: head.id, code: 0, retiring: false }) + "\n");
            pending -= 1;
          });
        }
      } };
    return proc;
  }
  proc.stdin = { write() {}, end() {}, on() {} };
  proc.pid = 1;
  proc.kill = () => {};
  pending += 1;
  setImmediate(() => {
    if (args.includes("list")) proc.stdout.emit("data", JSON.stringify(listReply()) + "\n");
    proc.emit("close", 0);
    pending -= 1;
  });
  return proc;
};
const load = Module._load;
Module._load = function (request, ...rest) {
  if (request === "electron") return electron;
  if (request === "child_process") return { spawn: fakeSpawn };
  if (request === "fs") {
    const promises = Object.fromEntries(Object.entries(realFs.promises).map(([name, fn]) =>
      [name, typeof fn === "function" ? (...args) => track(fn.apply(realFs.promises, args)) : fn]));
    return { ...realFs, promises, existsSync: () => true,
      readFileSync(p, ...more) {
        const base = String(p).split(/[\\/]/).pop();
        if (base in (sc.css || {})) {
          if (sc.css[base] === null) throw Object.assign(new Error("no such file"), { code: "ENOENT" });
          return sc.css[base];
        }
        return realFs.readFileSync(p, ...more);
      } };
  }
  return load.call(this, request, ...rest);
};
const items = (list, label) => {
  for (const item of list) {
    if (item.label === label) return item;
    const inner = item.submenu && items(item.submenu, label);
    if (inner) return inner;
  }
  return null;
};
(async () => {
  require(mainJs);
  await settle();
  for (const step of sc.steps) {
    if (step.menu !== undefined) {
      menuHandler({ sender: step.stranger ? {} : win.webContents }, step.menu);
    } else if (step.tracker) {
      await trackerHandler({ sender: { isDestroyed: () => false, send() {} } }, step.tracker, undefined);
    } else if (step.open) {
      log.answers.push(await openHandler({}, ...step.open));
    } else if (step.clickBar) {
      const item = items(live.bar, step.clickBar);
      if (item && item.click) item.click();
    } else if (step.clickPopup) {
      const item = items(live.popup, step.clickPopup);
      if (item && item.click) item.click();
    } else if (step.theme) {
      Object.assign(theme, step.theme);
      updated();
    }
    await settle();
  }
  process.stdout.write(JSON.stringify(log));
})();
"""


def _node():
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not on PATH (CI installs it)")
    return node


def run_menu(tmp_path, steps, **scenario) -> dict:
    harness = tmp_path / "menu_harness.js"
    harness.write_text(MENU_HARNESS, encoding="utf-8", newline="\n")
    done = subprocess.run(
        [_node(), str(harness), str(REPO / "app" / "main.js"),
         json.dumps({"steps": steps, **scenario})],
        capture_output=True, text=True, encoding="utf-8", timeout=60, check=False)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)
