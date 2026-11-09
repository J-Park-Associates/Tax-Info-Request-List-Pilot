"""The guided tour's steps and what its script may do (pilot SPEC sections 6, 8, 11).

The tour's wording is data in ``pilot-content.js``; these tests pin that every
step is complete, every element it points at exists on the page, and that the
script only points - it never presses, dispatches or calls the tracker.
"""

import json
import re
import subprocess
import tempfile
from pathlib import Path

import pytest

from tests.node_harness import NODE, content, read

REPO = Path(__file__).resolve().parent.parent


def tour() -> dict:
    return content()["tour"]


def test_every_tour_anchor_is_an_element_the_page_has():
    html = read("index.html")
    for step in tour()["steps"]:
        for anchor in step["anchors"]:
            assert f'id="{anchor}"' in html, (step["id"], anchor)


def test_every_tour_anchor_is_where_the_shell_put_it():
    """SPEC-shell 12: the anchors move to the shell's ids."""
    anchors = {step["id"]: step["anchors"] for step in tour()["steps"]}
    assert anchors == {
        "welcome": [],
        "clients-folder": ["page"],
        "new-household": ["side-sections"],
        "drop-files": ["crumbs"],
        "scan": ["sort"],
        "originals": ["page"],
        "working-copies": ["page"],
        "needs-review": ["side-sections"],
        "status": ["side-sections"],
        "reminder": ["side-sections"],
        "wrap-up": [],
    }


def test_every_step_has_a_title_and_one_line():
    for step in tour()["steps"]:
        assert step["title"].strip(), step["id"]
        assert isinstance(step["does"], str) and step["does"].strip(), step["id"]


def test_every_tour_title_and_line_is_in_title_case_but_the_inbox_folders_own_name():
    """Ruling 10: every drawn phrase is Title Case. The one step that names the
    inbox folder keeps the folder's own name (record data, untouched)."""
    from tests.wording import title_case

    steps = tour()["steps"]
    assert [s["title"] for s in steps if s["id"] == "needs-review"] == ["Needs Review"]
    for step in steps:
        for said in (step["title"], step["does"]):
            if said == "Drop files here":
                continue
            assert said == title_case(said), said


def test_the_tour_has_no_stage_strip_and_no_callouts_left():
    """The strength, limit and fallback lines and the stage chips are gone
    (P63, SPEC-shell 12), from the content and from the script: the tour
    holds its steps and the count line's words (SPEC-architecture-p6 R6.4.1)."""
    assert set(tour()) == {"count", "steps"}
    js = read("tour.js")
    for gone in ("stagesStrip", "callout(", "fallback", "PILOT.tour.stages", "step.strength", "step.limit"):
        assert gone not in js, gone
    css = read("pilot-style.css")
    for gone in (".pilot-tour-stage", ".pilot-tour-compare", ".pilot-tour-fallback", ".pilot-tour-ok", ".pilot-tour-warn"):
        assert gone not in css, gone


def test_step_ids_are_unique_and_the_tour_opens_and_closes_centred():
    steps = tour()["steps"]
    ids = [s["id"] for s in steps]
    assert len(ids) == len(set(ids))
    assert all(re.fullmatch(r"[a-z0-9-]+", i) for i in ids)
    assert steps[0]["anchors"] == [] and steps[-1]["anchors"] == []


def test_the_tour_only_points():
    js = read("tour.js")
    assert not [b for b in ("window.tracker", ".click(", "dispatchEvent") if b in js]


def test_the_tour_text_carries_no_placeholder_but_the_email():
    def strings(node):
        if isinstance(node, str):
            yield node
        elif isinstance(node, list):
            for item in node:
                yield from strings(item)
        elif isinstance(node, dict):
            for item in node.values():
                yield from strings(item)

    # Two other sentences are filled, each checked on its own: the terms'
    # "signed" line, which pilot.js puts the signed name and the day into
    # (P188), and the tour's count line, which tour.js puts the step's number
    # and the number of steps into (SPEC-architecture-p6 R6.4.1).
    text = content()
    signed = text["terms"].pop("signed")
    assert set(re.findall(r"\{[^}]*\}", signed)) == {"{name}", "{date}"}, signed
    count = text["tour"].pop("count")
    assert set(re.findall(r"\{[^}]*\}", count)) == {"{n}", "{total}"}, count
    tokens = {t for s in strings(text) for t in re.findall(r"\{[^}]*\}", s)}
    assert tokens <= {"{email}"}, tokens


def test_the_count_line_says_what_it_said_before_its_words_moved():
    """R6.4.1: the count's words are the pilot's, in pilot-content.js, and
    tour.js fills them, so the card says exactly what it said while tour.js
    typed them (``Step ${index + 1} of ${all.length}``). The one line that
    makes the count is lifted from tour.js and run under node against the
    content file as it is: the second of nine steps, and the first of the
    tour's own."""
    if NODE is None:
        pytest.skip("node is not on PATH (CI installs it)")
    lines = [line for line in read("tour.js").splitlines() if '"pilot-tour-count"' in line]
    assert len(lines) == 1, lines
    probe = f"""
const PILOT = require({json.dumps(str(REPO / "app" / "renderer" / "pilot-content.js"))});
const shown = [];
const card = {{ appendChild: (text) => shown.push(text) }};
const make = (tag, className, text) => text;
for (const [index, all] of [[1, new Array(9)], [0, PILOT.tour.steps]]) {{
{lines[0]}
}}
process.stdout.write(JSON.stringify(shown));
"""
    with tempfile.TemporaryDirectory() as folder:
        script = Path(folder) / "count.js"
        script.write_text(probe, encoding="utf-8", newline="\n")
        done = subprocess.run([NODE, str(script)], capture_output=True, text=True, encoding="utf-8", timeout=60,
                              check=False)
    assert done.returncode == 0, done.stderr
    assert json.loads(done.stdout) == ["Step 2 of 9", f"Step 1 of {len(tour()['steps'])}"]


def test_the_spot_follows_its_anchors_corner():
    js = (REPO / "app" / "renderer" / "tour.js").read_text(encoding="utf-8")
    assert "borderTopLeftRadius" in js and '"--pilot-spot-radius"' in js
    css = (REPO / "app" / "renderer" / "pilot-style.css").read_text(encoding="utf-8")
    assert "var(--pilot-spot-radius" in css
