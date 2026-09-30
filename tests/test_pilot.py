"""The pilot edition's badge, terms screen and wording (pilot SPEC sections 4, 5, 7, 9).

The wording lives in ``app/renderer/pilot-content.js`` between two marker
lines as plain JSON, so these tests read it with ``json.loads`` exactly as
the installer build reads it with node. The renderer files are read as text:
they run in a sandboxed window, so what can be pinned is what they may and
may not contain.
"""

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RENDERER = REPO / "app" / "renderer"
PILOT_JS = ("pilot-content.js", "pilot.js", "tour.js")


def read(name: str) -> str:
    return (RENDERER / name).read_text(encoding="utf-8")


def content() -> dict:
    text = read("pilot-content.js")
    begin, end = "// PILOT-CONTENT-BEGIN\n", "// PILOT-CONTENT-END"
    assert text.count(begin) == 1 and text.count(end) == 1
    return json.loads(text.split(begin)[1].split(end)[0])


def tour_lines(content_: dict):
    """One line per step (SPEC-shell 12): the strength, limit and fallback
    lines and the stage chips are gone."""
    for step in content_["tour"]["steps"]:
        assert set(step) == {"id", "anchors", "title", "does"}, step["id"]
        assert isinstance(step["does"], str), step["id"]
        yield step["does"]


def test_the_pilot_content_is_json_between_its_markers():
    data = content()
    assert set(data) == {"edition", "contact", "terms", "tour"}
    assert set(data["tour"]) == {"steps"}


def test_the_edition_version_is_a_plain_version_number():
    version = content()["edition"]["version"]
    assert re.fullmatch(r"\d+\.\d+(\.\d+)?", version), version
    assert content()["edition"]["label"]


def test_the_terms_have_every_field_and_a_positive_version():
    terms = content()["terms"]
    assert isinstance(terms["version"], int) and terms["version"] >= 1
    for key in ("title", "checkbox", "accept", "quit", "close"):
        assert isinstance(terms[key], str) and terms[key].strip(), key
    assert terms["sections"]


def test_every_terms_section_has_a_heading_and_bullets():
    for section in content()["terms"]["sections"]:
        assert section["heading"].strip()
        assert section["bullets"] and all(b.strip() for b in section["bullets"])


def test_the_contact_is_the_firms_admin_address():
    assert content()["contact"]["email"] == "admin@jparkassociates.com"


def test_every_line_of_copy_is_short():
    data = content()
    lines = [b for s in data["terms"]["sections"] for b in s["bullets"]]
    long = [line for line in lines if len(line.split()) > 30]
    assert not long, long


def test_every_tour_line_is_five_words_or_fewer():
    """P63: five words. The terms are the one exception, shown whole (P20)."""
    long = [line for line in tour_lines(content()) if len(line.split()) > 5]
    assert not long, long


def test_the_page_loads_the_pilot_after_the_app():
    html = read("index.html")
    assert html.index("pilot-style.css") > html.index('href="style.css"')
    order = [html.index(f'src="{name}"') for name in ("app.js", *PILOT_JS)]
    assert order == sorted(order)


def test_the_pilot_files_build_the_page_only_with_text():
    banned = ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write",
              "eval(", "new Function", "startsWith(")
    for name in PILOT_JS:
        text = read(name)
        assert not [b for b in banned if b in text], name


def test_the_pilot_never_types_the_product_name():
    product = json.loads((REPO / "app" / "package.json").read_text(encoding="utf-8"))["productName"]
    # The approved terms name the underlying product ("a test edition of Tax
    # Document Tracker"), which is not the pilot's product name once Build A
    # renames it to "... Pilot"; that one phrase is not a typing of it.
    approved = "A test edition of Tax Document Tracker, built by"
    for name in (*PILOT_JS, "pilot-style.css"):
        assert product not in read(name).replace(approved, ""), name


def test_the_terms_cannot_be_escaped():
    js = read("pilot.js")
    assert re.search(r'addEventListener\("keydown",\s*\w+,\s*true\)', js)
    assert '"Escape"' in js
    assert "DIALOGS" not in js.replace("app.js's DIALOGS", "")


def test_the_pilot_style_targets_only_its_own_names():
    css = re.sub(r"/\*.*?\*/", "", read("pilot-style.css"), flags=re.S)
    css = re.sub(r"@media[^{]*\{", "", css)
    selectors = [s.strip() for block in re.findall(r"([^{}]+)\{", css) for s in block.split(",")]
    allowed = (".pilot-", "#pilot-")
    assert selectors and all(s.startswith(allowed) for s in selectors), selectors


def test_acceptance_is_asked_of_the_durable_record_before_the_terms_stay():
    """P46: the window's storage is only a cache. A launch whose cache says
    nothing - storage that could not be opened reads as nothing - asks the
    tracker's own record, through the one channel the page has, and the
    terms go when it holds this version's acceptance."""
    import tracker.api as api

    js = read("pilot.js")
    assert 'const COMMAND = "pilot-record";' in js and "pilot-record" in api.COMMANDS
    assert "window.tracker.call([COMMAND], payload)" in js
    # The shell allows it only once the page's first call named the commands.
    assert "vocab.commands.indexOf(COMMAND)" in js
    shown = js.index("document.body.appendChild(overlay);")
    asked = js.index("PilotRecord.read().then((record) => {", shown)
    assert "record.terms !== version" in js[asked:] and "close();" in js[asked:]
    # Accepting records it durably, not only in the cache.
    accepted = js[js.index('accept.addEventListener("click"'):]
    assert "PilotRecord.acceptTerms(version);" in accepted.split("});")[0]
    # Storage is touched in one place only.
    assert js.count("window.localStorage.") == 2


def test_the_tour_is_remembered_through_the_pilot_record():
    tour = read("tour.js")
    assert "PilotRecord.tourSeen();" in tour and "localStorage" not in tour
    assert "tourSeen: () => {" in read("pilot.js")


def test_the_shell_writes_the_pages_storage_as_the_window_closes():
    """P46: flushed at close, not left to the end of a shutdown a quick
    restart can overtake."""
    main = (REPO / "app" / "main.js").read_text(encoding="utf-8")
    assert 'win.on("close", () => win.webContents.session.flushStorageData());' in main
    assert "app.requestSingleInstanceLock()" in main


def test_windows_contrast_themes_are_honoured_without_touching_the_normal_look():
    """Microsoft's contrast-theme guidance: a forced-colors block keeps edges and focus."""
    for name in ("style.css", "pilot-style.css"):
        css = read(name)
        block = re.search(r"@media \(forced-colors: active\) \{(.*)\n\}\n?$", css, flags=re.S)
        assert block, f"the forced-colors block must be the last rule of {name}"
        inner = block.group(1)
        assert "CanvasText" in inner or "Highlight" in inner
        assert not re.search(r"#[0-9a-fA-F]{3,8}\b|rgba?\(", inner), "system colours only"
        assert "glass" not in css and "backdrop-filter" not in css


def test_the_badge_sits_in_the_side_panels_foot_and_there_is_no_tour_button():
    """SPEC-shell 12: the badge moves to #side-foot; Help > Take the tour
    starts the tour (the menu id `tour`), so the page has no Tour button."""
    js = read("pilot.js")
    assert 'document.getElementById("side-foot")' in js
    assert "btn-tour" not in js and "btn-tour" not in read("index.html")
    assert "PilotTour.start()" in read("shell.js") and "PilotTerms.show()" in read("shell.js")
    assert 'id="side-foot"' in read("index.html")


def test_help_terms_shows_the_same_card_read_only_with_one_close():
    js = read("pilot.js")
    shown = js[js.index("function show() {"):js.index("function gate() {")]
    code = re.sub(r"//[^\n]*", "", shown)
    assert "build(true)" in code and "close" in code
    assert not re.search(r"\b(?:agree|accept|quit)\b", code) and "window.close" not in code
    assert '"close": "Close"' in read("pilot-content.js")
