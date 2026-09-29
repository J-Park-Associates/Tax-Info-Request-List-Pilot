"""The guided tour's steps and what its script may do (pilot SPEC sections 6, 8, 11).

The tour's wording is data in ``pilot-content.js``; these tests pin that every
step is complete, every element it points at exists on the page, and that the
script only points - it never presses, dispatches or calls the tracker.
"""

import re
from pathlib import Path

from tests.test_pilot import content, read

REPO = Path(__file__).resolve().parent.parent


def tour() -> dict:
    return content()["tour"]


def test_every_tour_anchor_is_an_element_the_page_has():
    html = read("index.html")
    for step in tour()["steps"]:
        for anchor in step["anchors"]:
            assert f'id="{anchor}"' in html, (step["id"], anchor)


def test_every_step_has_its_three_callouts():
    for step in tour()["steps"]:
        assert step["title"].strip(), step["id"]
        for key in ("does", "strength", "limit"):
            value = step[key]
            lines = [value] if isinstance(value, str) else value
            assert lines and all(isinstance(x, str) and x.strip() for x in lines), (step["id"], key)


def test_every_step_sits_on_the_strip():
    stages, steps = tour()["stages"], tour()["steps"]
    assert len(stages) == 6
    positions = []
    for i, step in enumerate(steps):
        if step["stage"] == "":
            assert i in (0, len(steps) - 1), step["id"]
        else:
            assert step["stage"] in stages, step["id"]
            positions.append(stages.index(step["stage"]))
    assert positions == sorted(positions)


def test_a_step_that_points_says_what_to_expect_when_it_cannot():
    for step in tour()["steps"]:
        if step["anchors"]:
            assert step["fallback"].strip(), step["id"]
        else:
            assert step["fallback"] == "", step["id"]


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

    tokens = {t for s in strings(content()) for t in re.findall(r"\{[^}]*\}", s)}
    assert tokens <= {"{email}"}, tokens


def test_the_spot_follows_its_anchors_corner():
    js = (REPO / "app" / "renderer" / "tour.js").read_text(encoding="utf-8")
    assert "borderTopLeftRadius" in js and '"--pilot-spot-radius"' in js
    css = (REPO / "app" / "renderer" / "pilot-style.css").read_text(encoding="utf-8")
    assert "var(--pilot-spot-radius" in css
