"""Tests for tools/vocab_report.py - the coverage report has to stay honest.

It is derived from the catalog and the suite, so a report that disagreed
with either would send the next review round after the wrong keywords.
The pure ``report()`` is exercised on small catalogs of our own; the
committed report is checked against its inputs by hash, as the map is.
"""

import json
import sys
from pathlib import Path

from tracker.manifest import RequestItem

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import vocab_report  # noqa: E402
from vocab_report import CASE, IRS, REAL, Document, render_markdown, report  # noqa: E402


def row(identifier, document, *, required=(), any_keywords=()):
    return RequestItem(identifier=identifier, document=document,
                       required_keywords=tuple(required), any_keywords=tuple(any_keywords))


def one(catalog, form="1040"):
    return catalog["catalogs"][form]


# ------------------------------------------------------------- report() ----


def test_a_keyword_a_filing_document_says_is_reached_here_and_an_unsaid_one_is_unreached():
    catalog = {"1040": [row("A01", "W-2", required=["w-2", "wage and tax statement", "employee's social security number"])]}
    w2 = Document(CASE, "W-2.pdf", "Form W-2 Wage and Tax Statement 2025\n1 Wages", {"1040": "A01"}, 62)
    out = one(report(catalog, [w2]))
    said = {k["keyword"]: k["reached_by"] for k in out["rows"]["A01"]["keywords"]}
    assert said["w-2"] == [{"kind": CASE, "name": "W-2.pdf", "decision": 62, "expected": "A01"}]
    assert said["employee's social security number"] == []
    assert out["unreached"] == [["A01", "employee's social security number"]]
    assert out["reached_only_elsewhere"] == [] and out["rows_without_a_filing_document"] == []


def test_a_keyword_said_only_by_documents_that_park_or_file_elsewhere_is_named_apart():
    catalog = {"1040": [row("C01", "1098", required=["1098", "mortgage interest"]),
                        row("L01", "1098-T", any_keywords=["qualified tuition"])]}
    tuition = Document(IRS, "f1098t.pdf", "Form 1098-T Tuition Statement 2025\nqualified tuition\nmortgage interest paid", {"1040": "L01"})
    out = one(report(catalog, [tuition]))
    assert out["reached_only_elsewhere"] == [["C01", "mortgage interest"]]
    assert out["unreached"] == [["C01", "1098"]]              # 1098-T is not 1098: the reader's rule, not a substring
    assert out["rows_without_a_filing_document"] == ["C01"]


def test_a_keyword_said_only_by_documents_the_suite_never_routes_here_is_reached_without_expectation():
    catalog = {"1120": [row("A02", "Trial Balance", any_keywords=["trial balance"])]}
    elsewhere = Document(CASE, "trial balance.pdf", "Trial Balance As of December 31, 2025", {"1120S": "A02"}, 62)
    out = one(report(catalog, [elsewhere]), "1120")
    assert out["reached_without_expectation"] == [["A02", "trial balance"]]
    assert out["reached_only_elsewhere"] == []
    hit, = out["rows"]["A02"]["keywords"][0]["reached_by"]
    assert "expected" not in hit


def test_a_form_number_quoted_in_a_sentence_does_not_reach_its_keyword():
    catalog = {"1040": [row("C01", "1098", required=["1098"])]}
    organizer = Document(CASE, "organizer.pdf", "2025 Tax Organizer\nMortgage interest: attach Form 1098", {"1040": None}, 66)
    out = one(report(catalog, [organizer]))
    assert out["unreached"] == [["C01", "1098"]]


def test_hits_are_ordered_corpus_first_then_by_decision_and_name():
    catalog = {"1040": [row("A01", "W-2", required=["w-2"])]}
    docs = [
        Document(CASE, "b.pdf", "Form W-2 2025", {"1040": "A01"}, 66),
        Document(CASE, "a.pdf", "Form W-2 2025", {"1040": "A01"}, 66),
        Document(CASE, "z.pdf", "Form W-2 2025", {"1040": "A01"}, 62),
        Document(IRS, "fw2.pdf", "Form W-2 2025", {"1040": "A01"}),
    ]
    hits = one(report(catalog, docs))["rows"]["A01"]["keywords"][0]["reached_by"]
    assert [h["name"] for h in hits] == ["z.pdf", "a.pdf", "b.pdf", "fw2.pdf"]


def test_a_document_from_the_firms_own_corpus_is_reported_beside_the_forms_and_the_cases():
    """The thirteenth reading is briefed from the report, so it must see the real ones too."""
    catalog = {"1040": [row("A01", "W-2", required=["w-2"])]}
    docs = [Document(IRS, "fw2.pdf", "Form W-2 2025", {"1040": "A01"}),
            Document(REAL, "redacted w-2.pdf", "Form W-2 Wage and Tax Statement 2025", {"1040": "A01"})]
    out = report(catalog, docs)
    hits = one(out)["rows"]["A01"]["keywords"][0]["reached_by"]
    assert hits == [{"kind": IRS, "name": "fw2.pdf", "expected": "A01"},
                    {"kind": REAL, "name": "redacted w-2.pdf", "expected": "A01"}]
    assert out["counts"]["documents"] == {IRS: 1, CASE: 0, REAL: 1}
    text = render_markdown(out)
    assert "1 real documents" in text
    assert "- `w-2` (required) — fw2.pdf → **here**; redacted w-2.pdf → **here**" in text


def test_a_report_built_without_a_corpus_says_nothing_about_one():
    """The committed report is built on a machine with no corpus; CI has none either."""
    out = report({"1040": [row("A01", "W-2", required=["w-2"])]}, [])
    assert out["counts"]["documents"] == {IRS: 0, CASE: 0}
    assert "real" not in render_markdown(out).split("## ")[0]
    assert vocab_report.real_documents_in(out) == 0


def test_a_committed_report_naming_the_firms_own_documents_is_refused(tmp_path, monkeypatch, capsys):
    """Committing one would put client file names in the repository."""
    data = vocab_report.load_report()
    data["counts"]["documents"][REAL] = 2
    monkeypatch.setattr(vocab_report, "REPORT_PATH", tmp_path / "vocab-coverage.json")
    vocab_report.REPORT_PATH.write_text(json.dumps(data), encoding="utf-8")
    assert vocab_report.main(["check"]) == 1
    assert vocab_report.ENV_REAL_CORPUS in capsys.readouterr().out


def test_the_counts_add_up_across_catalogs():
    catalog = {"1040": [row("A01", "W-2", required=["w-2"])],
               "1041": [row("B01", "1099s", any_keywords=["1099-int", "1099-div"])]}
    out = report(catalog, [Document(IRS, "fw2.pdf", "Form W-2 2025", {"1040": "A01"})])
    assert out["counts"] == {
        "catalogs": 2, "rows": 2, "keywords": 3, "unreached": 2, "reached_only_elsewhere": 0,
        "reached_without_expectation": 0, "rows_without_a_filing_document": 1,
        "documents": {IRS: 1, CASE: 0},
    }


# ------------------------------------------------------------- markdown ----


def test_the_markdown_leads_with_the_generated_note_and_names_every_list():
    catalog = {"1040": [row("A01", "W-2", required=["w-2", "employee's social security number"])]}
    out = report(catalog, [Document(IRS, "fw2.pdf", "Form W-2 2025", {"1040": "A01"})])
    text = render_markdown(out)
    assert text.startswith("# Vocabulary coverage") and vocab_report.GENERATED_NOTE in text
    assert "## Unreached keywords" in text and "- **1040 A01** `employee's social security number`" in text
    assert "## Keywords reached only by documents that file elsewhere or park" in text
    assert "## Keywords reached only by documents the suite never routes against this catalog" in text
    assert "## Rows the suite never files a document into" in text
    assert "- `w-2` (required) — fw2.pdf → **here**" in text


# ------------------------------------------------------------ the check ----


def test_a_changed_input_is_reported_by_name():
    data = {"inputs": vocab_report.input_hashes()}
    assert vocab_report.stale_inputs(data) == []
    data["inputs"]["tracker/templates.py"] = "0" * 64
    assert vocab_report.stale_inputs(data) == ["tracker/templates.py"]


def test_the_corpus_forms_are_inputs_too():
    hashes = vocab_report.input_hashes()
    assert "tests/irs/fw2.pdf" in hashes and all(len(h) == 64 for h in hashes.values())


def test_the_committed_report_is_current(capsys):
    """Like the map: a stale report is worse than none, and the next round would trust it."""
    data = vocab_report.load_report()
    assert vocab_report.stale_inputs(data) == []
    assert vocab_report.MARKDOWN_PATH.read_text(encoding="utf-8") == render_markdown(data)
    assert vocab_report.main(["check"]) == 0
    assert "current" in capsys.readouterr().out


def test_show_prints_a_catalog_and_names_an_unknown_one(capsys):
    assert vocab_report.main(["show", "1040"]) == 0
    assert "[A01]" in capsys.readouterr().out
    assert vocab_report.main(["show", "nope"]) == 1
