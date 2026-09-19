"""Tests for tools/learned_keywords.py - what one person taught one engagement, seen by the firm.

A keyword typed into the app's filing action lands in one manifest and
nowhere else, so the report is the only place the firm can see that five
clients had to teach the router the same word. Two things have to hold or it
is worse than nothing: a keyword the catalog already carries must not be
reported (a list of things already done is a list nobody reads twice), and an
engagement the walk could not read must be named rather than dropped (a
silent skip reads as "nothing was taught here").

The reports are built on scratch clients roots under ``tmp_path``, the way
``tests/test_registry.py`` builds one: an engagement is a folder with a
manifest in it, and the manifests are the shipped catalog written through
``create_template()``, so the comparison under test is the real one.
"""

import sys
from pathlib import Path

from tracker.manifest import (
    EngagementInfo,
    RequestItem,
    add_any_keyword,
    create_template,
)
from tracker.registry import SKIP_ROLLED_FORWARD
from tracker.scaffold import MANIFEST_FILENAME
from tracker.templates import template_items

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import learned_keywords  # noqa: E402
from learned_keywords import FLAG_INACTIVE, collect, main, render  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
#: A keyword the 1040 catalog's W-2 row already carries, on its required side.
CARRIED = "wage and tax statement"
#: A title phrase the corpus's Form 1098-T prints, which tests/test_irs_forms.py
#: files under L01 in the 1040 catalog - so it misfiles that form anywhere else.
SAID_BY_A_FORM = "qualified tuition and related expenses"
#: A keyword no corpus form and no catalog says.
SAID_BY_NOTHING = "willow lane payroll recap"


def engagement(root: Path, *parts: str, items=None, info: EngagementInfo | None = None) -> Path:
    """One engagement folder with a manifest in it, as the registry finds them."""
    folder = root.joinpath(*parts)
    folder.mkdir(parents=True)
    create_template(folder / MANIFEST_FILENAME, template_items("1040") if items is None else items, info)
    return folder


def taught(folder: Path, identifier: str, keyword: str) -> None:
    """A person filing a parked document and typing a keyword, which is the only way one is learned."""
    add_any_keyword(folder / MANIFEST_FILENAME, identifier, keyword)


def line_for(text: str, keyword: str) -> str:
    return next(line for line in text.splitlines() if line.startswith(f"- `{keyword}`"))


# ------------------------------------------------------------- the grouping ----


def test_two_engagements_that_taught_the_same_keyword_report_it_once_with_the_count(tmp_path):
    """The point of the report: repetition across clients is what makes a catalog commit."""
    root = tmp_path / "Clients"
    for name in ("Smith 2025", "Jones 2025"):
        taught(engagement(root, name), "A01", SAID_BY_NOTHING)

    report = collect(root)
    (row,) = report.rows
    assert row.identifier == "A01" and row.catalogs == ("1040",)
    assert list(row.keywords) == [SAID_BY_NOTHING]
    assert len(row.keywords[SAID_BY_NOTHING]) == 2
    assert line_for(render(report), SAID_BY_NOTHING).endswith("2 engagement(s)")


def test_a_keyword_the_catalog_already_carries_on_that_row_is_not_learned(tmp_path):
    """A person may retype what the catalog has; the report is the list of what it lacks."""
    root = tmp_path / "Clients"
    folder = engagement(root, "Smith 2025")
    taught(folder, "A01", CARRIED)              # already a required keyword of that row
    taught(folder, "A01", SAID_BY_NOTHING)

    report = collect(root)
    (row,) = report.rows
    assert list(row.keywords) == [SAID_BY_NOTHING]
    assert CARRIED not in render(report)


def test_a_keyword_on_a_row_no_catalog_knows_is_a_custom_row(tmp_path):
    """There is nothing to compare a hand-added request against, so all of its keywords are candidates."""
    root = tmp_path / "Clients"
    engagement(root, "Marina 2025",
               items=[RequestItem(identifier="Z01", document="Boat Slip Lease", any_keywords=("slip lease",))])

    report = collect(root)
    assert report.rows == []
    (row,) = report.custom
    assert row.catalogs == () and list(row.keywords) == ["slip lease"]
    text = render(report)
    assert "## Custom rows" in text and "Z01 - Boat Slip Lease" in text


def test_a_row_is_compared_against_every_catalog_that_holds_it(tmp_path):
    """The Engagement sheet does not say which form type the engagement is, so
    the comparison is against all of them - and the report says which matched,
    because a keyword ruled out by a catalog the engagement is not is a keyword
    the reader has to be able to second-guess."""
    root = tmp_path / "Clients"
    engagement(root, "Willow Inc 2025", items=template_items("1120"))
    shared = [row for row in collect(root).rows + collect(root).custom]
    assert shared == []                                    # the shipped 1120 rows are all known

    folder = engagement(root, "Willow Inc 2026", items=template_items("1120"))
    taught(folder, "A02", SAID_BY_NOTHING)                 # the trial-balance row, which several catalogs share
    (row,) = collect(root).rows
    assert len(row.catalogs) > 1 and "1120" in row.catalogs


# ------------------------------------------------------- engagements, named ----


def test_the_default_output_counts_engagements_and_the_flag_names_them(tmp_path, capsys):
    """An engagement folder is a client's name, so the default report holds none."""
    root = tmp_path / "Clients"
    taught(engagement(root, "Willowbrook Family Trust 2025"), "A01", SAID_BY_NOTHING)

    assert main([str(root)]) == 0
    counted = capsys.readouterr().out
    assert "Willowbrook Family Trust 2025" not in counted
    assert line_for(counted, SAID_BY_NOTHING).endswith("1 engagement(s)")

    assert main([str(root), "--engagements"]) == 0
    assert "  - Willowbrook Family Trust 2025" in capsys.readouterr().out


def test_an_engagement_the_run_would_not_chase_is_still_read_and_is_flagged(tmp_path):
    """Last year's list and a retired client taught the router too, and the
    catalog they taught is this year's catalog."""
    root = tmp_path / "Clients"
    prior = engagement(root, "Smith", "Smith - 2025")
    engagement(root, "Smith", "Smith - 2026", info=EngagementInfo(rolled_from=str(prior.resolve())))
    dormant = engagement(root, "Old Co 2025", info=EngagementInfo(active=False))
    for folder in (prior, dormant):
        taught(folder, "A01", SAID_BY_NOTHING)

    report = collect(root)
    assert report.read == 3 and report.rolled_forward == 1 and report.inactive == 1
    named = render(report, engagements=True)
    assert f"Old Co 2025 ({FLAG_INACTIVE})" in named
    assert f"Smith - 2025 ({SKIP_ROLLED_FORWARD.format(successor='Smith - 2026')})" in named


def test_an_engagement_whose_manifest_cannot_be_read_is_a_problem_line_not_a_silence(tmp_path):
    """A skipped engagement reads as one that taught the router nothing, which is the opposite claim."""
    root = tmp_path / "Clients"
    taught(engagement(root, "Fine 2025"), "A01", SAID_BY_NOTHING)
    broken = root / "Broken 2025"
    broken.mkdir()
    (broken / MANIFEST_FILENAME).write_bytes(b"not a workbook")

    report = collect(root)
    assert report.engagements == 2 and report.read == 1
    (folder, problem), = report.problems
    assert folder == str(broken) and "Could not open" in problem
    text = render(report)
    assert "## Problems" in text and str(broken) in text and "1 problem(s)" in text


# ------------------------------------------------------------- writing none ----


def _tree() -> dict[str, tuple[int, int]]:
    """Every file under the repository, by size and mtime, the caches excluded."""
    skip = {".git", "node_modules", "__pycache__", ".claude", ".pytest_cache", ".ruff_cache"}
    found = {}

    def walk(folder: Path) -> None:
        for child in folder.iterdir():
            if child.name in skip:
                continue
            if child.is_dir():
                walk(child)
            else:
                stat = child.stat()
                found[str(child)] = (stat.st_size, stat.st_mtime_ns)

    walk(REPO)
    return found


def test_the_report_writes_nothing_under_the_repository_and_refuses_an_out_path_inside_it(tmp_path, capsys):
    """The report names client folders when asked to; a file under the tree is one `git add -A` from a commit."""
    root = tmp_path / "Clients"
    taught(engagement(root, "Smith 2025"), "A01", SAID_BY_NOTHING)

    before = _tree()
    assert main([str(root), "--engagements"]) == 0
    capsys.readouterr()
    assert _tree() == before

    inside = REPO / "docs" / "learned.md"
    assert main([str(root), "--out", str(inside)]) == 2
    assert "refusing to write inside the repository" in capsys.readouterr().err
    assert not inside.exists()
    assert _tree() == before

    outside = tmp_path / "learned.md"
    assert main([str(root), "--out", str(outside)]) == 0
    assert SAID_BY_NOTHING in outside.read_text(encoding="utf-8")
    assert _tree() == before


# -------------------------------------------------------------------- lint ----


def test_lint_marks_a_keyword_that_would_misfile_a_corpus_form_and_leaves_the_rest_alone(tmp_path, capsys):
    """A keyword is promoted into the catalog or it is not, and the blank forms
    in tests/irs/ already say where each of them belongs: one that would move a form
    the suite places is not a candidate, whatever it did for one client."""
    root = tmp_path / "Clients"
    folder = engagement(root, "Smith 2025")
    taught(folder, "A01", SAID_BY_A_FORM)       # the 1098-T's own title phrase, on the W-2 row
    taught(folder, "A01", SAID_BY_NOTHING)

    assert main([str(root), "--lint"]) == 0
    out = capsys.readouterr().out
    assert "would misfile: f1098t.pdf files as L01" in line_for(out, SAID_BY_A_FORM)
    assert "would misfile" not in line_for(out, SAID_BY_NOTHING)


def test_a_report_that_was_not_linted_says_so(tmp_path):
    """The lists differ in what they are worth, and a reader must not mistake one for the other."""
    root = tmp_path / "Clients"
    taught(engagement(root, "Smith 2025"), "A01", SAID_BY_NOTHING)
    report = collect(root)
    assert report.linted is False
    assert "has been run against the IRS forms" in render(report)


# --------------------------------------------------------------------- CLI ----


def test_a_root_neither_given_nor_configured_is_named_not_guessed(tmp_path, monkeypatch, capsys):
    """Walking the working folder because nothing was set is how a report reads an empty practice."""
    from tracker.settings import ENV_SETTINGS_DIR, settings_path

    monkeypatch.setenv(ENV_SETTINGS_DIR, str(tmp_path))
    assert main([]) == 2
    assert str(settings_path()) in capsys.readouterr().err


def test_a_root_that_is_not_a_folder_is_the_registrys_own_refusal(tmp_path, capsys):
    assert main([str(tmp_path / "nowhere")]) == 2
    assert "clients root is not a folder" in capsys.readouterr().err


def test_the_out_path_is_resolved_against_the_working_folder(tmp_path, monkeypatch):
    """A relative path is refused or accepted on where it lands, not on how it is spelt."""
    monkeypatch.chdir(tmp_path)
    assert learned_keywords.out_path("learned.md") == (tmp_path / "learned.md").resolve()
