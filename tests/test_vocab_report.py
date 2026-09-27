"""Tests for tools/vocab_report.py - the coverage report has to stay honest.

It is derived from the catalog and the suite, so a report that disagreed
with either would send the next review round after the wrong keywords.
The pure ``report()`` is exercised on small catalogs of our own; the
committed report is checked against its inputs by hash, as the map is.
"""

import json
import sys
from pathlib import Path

import pytest

from tracker.manifest import RequestItem
from tracker.settings import ENV_REAL_CORPUS, EXPECTATIONS_COLUMNS, EXPECTATIONS_FILENAME

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
            Document(REAL, "row 1", "Form W-2 Wage and Tax Statement 2025", {"1040": "A01"})]
    out = report(catalog, docs)
    hits = one(out)["rows"]["A01"]["keywords"][0]["reached_by"]
    assert hits == [{"kind": IRS, "name": "fw2.pdf", "expected": "A01"},
                    {"kind": REAL, "name": "row 1", "expected": "A01"}]
    assert out["counts"]["documents"] == {IRS: 1, CASE: 0, REAL: 1}
    text = render_markdown(out)
    assert "1 real documents" in text
    assert "- `w-2` (required) — fw2.pdf → **here**; row 1 → **here**" in text


def test_a_workbook_case_reads_the_same_to_the_report_as_to_the_suite(tmp_path):
    """The suite writes a workbook case to a real .xlsx and reads it back;
    the report renders the rows instead. If the two readings differed, a
    keyword a case reaches would be listed as unreached - or the other way
    about, which is worse."""
    from tests.samples import sheet_xlsx
    from tracker.content_check import extract_text

    rows = [["Willow Lane Inc."], ["Officer Compensation Detail - 2025"],
            ["Officer", "Title", "Compensation"], ["John Reyes", "President", 240000]]
    written = extract_text(sheet_xlsx(tmp_path / "officer comp.xlsx", rows))
    assert vocab_report.as_a_sheet(rows) == written


def test_the_workbook_cases_are_in_the_report_too():
    """Half of every catalog asks for a schedule a client keeps in Excel."""
    from tests.test_catalog import XLSX_CASES

    names = {doc.name for doc in vocab_report.case_documents()}
    assert {case[2] for case in XLSX_CASES} <= names


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


# ------------------------------------------- decision 185: the firm's own documents ----

#: A fabricated document name, distinctive so a test can show it is never printed.
FABRICATED_NAME = "Zephyrine Quillfeather W-2 2025.pdf"


def one_pdf_corpus(folder: Path, rows: list[str]) -> Path:
    """A corpus folder with one text PDF and an expectations file of ``rows``."""
    from tests.test_scanner import text_pdf

    folder.mkdir(parents=True, exist_ok=True)
    text_pdf(folder / FABRICATED_NAME, "Form W-2 Wage and Tax Statement 2025")
    (folder / EXPECTATIONS_FILENAME).write_text(
        "\n".join([",".join(EXPECTATIONS_COLUMNS), *rows, ""]), encoding="utf-8")
    return folder


def test_a_build_with_a_real_corpus_present_refuses_to_write_the_committed_report(tmp_path, monkeypatch, capsys):
    """A report read from the firm's own documents is never one `git add -A` from a commit."""
    corpus = one_pdf_corpus(tmp_path / "corpus", [f"{FABRICATED_NAME},1040,2025,A01"])
    monkeypatch.setenv(ENV_REAL_CORPUS, str(corpus))
    before = (vocab_report.REPORT_PATH.read_bytes(), vocab_report.MARKDOWN_PATH.read_bytes())
    assert vocab_report.main(["build"]) == 2
    assert ENV_REAL_CORPUS in capsys.readouterr().err
    assert (vocab_report.REPORT_PATH.read_bytes(), vocab_report.MARKDOWN_PATH.read_bytes()) == before


def test_a_local_reading_is_written_only_outside_the_repository(tmp_path, monkeypatch, capsys):
    """``--out`` inside the repository is refused; outside it, both files are written there."""
    monkeypatch.setenv(ENV_REAL_CORPUS, str(tmp_path / "corpus"))
    monkeypatch.setattr(vocab_report, "corpus_documents",
                        lambda: [Document(IRS, "fw2.pdf", "Form W-2 2025", {"1040": "A01"})])
    monkeypatch.setattr(vocab_report, "case_documents",
                        lambda: [Document(CASE, "case", "Form W-2 2025", {"1040": "A01"})])
    monkeypatch.setattr(vocab_report, "real_documents",
                        lambda: [Document(REAL, "row 1", "Form W-2 2025", {"1040": "A01"})])
    inside = vocab_report.ROOT / "x"
    assert vocab_report.main(["build", vocab_report.OUT_FLAG, str(inside)]) == 2
    assert "outside the repository" in capsys.readouterr().err
    assert not inside.exists()
    out = tmp_path / "reading"
    assert vocab_report.main(["build", vocab_report.OUT_FLAG, str(out)]) == 0
    assert (out / vocab_report.REPORT_PATH.name).is_file() and (out / vocab_report.MARKDOWN_PATH.name).is_file()
    assert vocab_report.real_documents_in(
        json.loads((out / vocab_report.REPORT_PATH.name).read_text(encoding="utf-8"))) == 1


def test_a_real_document_is_named_by_its_row_never_its_file(tmp_path, monkeypatch):
    corpus = one_pdf_corpus(tmp_path / "corpus", [f"{FABRICATED_NAME},1040,2025,A01"])
    monkeypatch.setenv(ENV_REAL_CORPUS, str(corpus))
    [document] = vocab_report.real_documents()
    assert document.kind == REAL and document.name == "row 1"

    missing = "Absalom Fairweather 1099-INT.pdf"
    one_pdf_corpus(corpus, [f"{FABRICATED_NAME},1040,2025,A01", f"{missing},1040,2025,A02"])
    with pytest.raises(vocab_report.ReportError) as raised:
        vocab_report.real_documents()
    assert "entry 2" in str(raised.value) and missing not in str(raised.value)
    assert str(corpus) not in str(raised.value)

    one_pdf_corpus(corpus, [f"{FABRICATED_NAME},1040,2025,A01", f"{missing},1040,,A02"])
    with pytest.raises(vocab_report.ReportError) as raised:     # one sentence, never a traceback
        vocab_report.real_documents()
    # Said by its class (decision 208), never the reader's words.
    assert f"{EXPECTATIONS_FILENAME} could not be read (ValueError)" in str(raised.value)
    assert missing not in str(raised.value) and str(corpus) not in str(raised.value)


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


def test_the_vocab_report_hashes_what_git_commits(tmp_path):
    """The map's CRLF exposure was the report's too: it hashed working-copy bytes (decision 151)."""
    for rel in vocab_report.INPUT_PATHS:
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_bytes(b"line one\nline two\n")
    irs = tmp_path / "tests" / "irs"
    irs.mkdir(parents=True, exist_ok=True)
    (irs / "f.pdf").write_bytes(b"%PDF-1.7\r\n\x00\x01stream\r\n")
    lf = vocab_report.input_hashes(tmp_path)

    for rel in vocab_report.INPUT_PATHS:
        (tmp_path / rel).write_bytes(b"line one\r\nline two\r\n")
    assert vocab_report.input_hashes(tmp_path) == lf, "a CRLF working copy is the LF file Git commits"
    (irs / "f.pdf").write_bytes(b"%PDF-1.7\n\x00\x01stream\n")
    assert vocab_report.input_hashes(tmp_path)["tests/irs/f.pdf"] != lf["tests/irs/f.pdf"], (
        "a binary file is hashed as it is: its CR bytes count")


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


# ------------------------------------------------- a damaged document (208) ----

GARBAGE = b"these bytes are no document at all \x00\x01\x02"
HEADER = "file,catalog,year,expected\n"


def fabricated_corpus(folder, files, lines):
    """A corpus of fabricated bytes (never real data) and its expectations file."""
    folder.mkdir()
    for name, content in files.items():
        (folder / name).write_bytes(content)
    (folder / vocab_report.EXPECTATIONS_FILENAME).write_text(HEADER + "".join(lines), encoding="utf-8")
    return folder


def test_a_damaged_workbook_and_pdf_stop_the_build_by_their_entry_and_class(tmp_path, monkeypatch):
    """The router parks a damaged file; the report cannot count it as saying
    nothing, so it stops - once, naming every damaged document by its
    expectations entry and its error's class. A blank spacer line is not an
    entry, and the parser's own message never reaches the sentence."""
    import pytest

    folder = fabricated_corpus(
        tmp_path / "Private Corpus Folder",
        {"Client Secret W2.pdf": GARBAGE, "notes.csv": b"a,b\n1,2\n", "Client Secret K1.xlsx": GARBAGE},
        ["notes.csv,1040,2025,\n", ",,,\n", "Client Secret K1.xlsx,1040,2025,\n", "Client Secret W2.pdf,1040,2025,A01\n"],
    )
    monkeypatch.setenv(vocab_report.ENV_REAL_CORPUS, str(folder))
    with pytest.raises(vocab_report.ReportError) as raised:
        vocab_report.real_documents()
    said = str(raised.value)
    assert "expectations entry 2 (BadZipFile)" in said
    assert "expectations entry 3 (PdfminerException)" in said
    assert "holds 2 documents" in said
    for leak in ("Client Secret", "Private Corpus Folder", "Root", ".pdf", ".xlsx"):
        assert leak not in said


def test_build_says_the_damaged_rows_in_one_sentence_and_exits_2(tmp_path, monkeypatch, capsys):
    """No traceback: the CLI prints the sentence, writes no report, and exits 2."""
    folder = fabricated_corpus(tmp_path / "corpus", {"Client Secret.pdf": GARBAGE},
                               ["Client Secret.pdf,1040,2025,\n"])
    monkeypatch.setenv(vocab_report.ENV_REAL_CORPUS, str(folder))
    monkeypatch.setattr(vocab_report, "REPORT_PATH", tmp_path / "out" / "vocab-coverage.json")
    monkeypatch.setattr(vocab_report, "MARKDOWN_PATH", tmp_path / "out" / "vocab-coverage.md")
    # With a corpus set, a reading goes only to --out outside the repository (decision 185).
    reading = tmp_path / "reading"
    assert vocab_report.main(["build", vocab_report.OUT_FLAG, str(reading)]) == 2
    out, err = capsys.readouterr()
    assert "expectations entry 1 (PdfminerException)" in err
    assert "Client Secret" not in out + err
    assert not (tmp_path / "out").exists() and not any(reading.glob("vocab-coverage.*"))


def test_a_missing_document_is_named_by_its_entry_not_its_name(tmp_path, monkeypatch):
    import pytest

    folder = fabricated_corpus(tmp_path / "corpus", {"here.csv": b"a\n"},
                               ["Zed Secret.pdf,1040,2025,\n", "here.csv,1040,2025,\n", "Client Secret.pdf,1040,2025,\n"])
    monkeypatch.setenv(vocab_report.ENV_REAL_CORPUS, str(folder))
    with pytest.raises(vocab_report.ReportError) as raised:
        vocab_report.real_documents()
    assert str(raised.value) == "expectations entries 1, 3 name a file that is not in the corpus folder"
    assert "Client Secret" not in str(raised.value) and str(folder) not in str(raised.value)


def test_a_contradicting_expectation_is_named_by_its_entry_not_its_name(tmp_path, monkeypatch):
    import pytest

    folder = fabricated_corpus(tmp_path / "corpus", {"Client Secret.csv": b"w-2\n"},
                               ["Client Secret.csv,1040,2025,A01\n", "Client Secret.csv,1040,2025,A02\n"])
    monkeypatch.setenv(vocab_report.ENV_REAL_CORPUS, str(folder))
    with pytest.raises(vocab_report.ReportError) as raised:
        vocab_report.real_documents()
    assert str(raised.value).startswith("expectations entry 1 is expected at both A01 and A02")
    assert "Client Secret" not in str(raised.value)


def test_a_sound_corpus_still_reads_and_a_type_with_no_extractor_is_no_failure(tmp_path, monkeypatch):
    """A garbage photo or docx never had words to the report; it still has none, and is not an error."""
    folder = fabricated_corpus(
        tmp_path / "corpus",
        {"a.csv": b"Form W-2 Wage and Tax Statement 2025\n", "b.png": GARBAGE, "c.docx": GARBAGE},
        ["a.csv,1040,2025,A01\n", "b.png,1040,2025,\n", "c.docx,1040,2025,\n"],
    )
    monkeypatch.setenv(vocab_report.ENV_REAL_CORPUS, str(folder))
    documents = {doc.name: doc for doc in vocab_report.real_documents()}
    # Each labelled by its entry, never by its name (decision 185).
    assert set(documents) == {"row 1", "row 2", "row 3"}
    assert "W-2" in documents["row 1"].text
    assert documents["row 2"].text == documents["row 3"].text == ""


def test_the_report_reads_documents_the_routers_way_only():
    """One reading (decision 208): the bare extractor, which lets a parser's
    traceback through, is not the report's to call."""
    assert not hasattr(vocab_report, "extract_text")
    assert vocab_report.extract.__module__ == "tracker.content_check"


def test_a_malformed_expectations_file_is_said_by_its_class_not_its_text(tmp_path, monkeypatch, capsys):
    """read_expectations' own message names the corpus folder and a document;
    the report says only that the file could not be read, and what to check."""
    folder = fabricated_corpus(tmp_path / "Private Corpus Folder", {"Client Secret.pdf": GARBAGE},
                               ["Client Secret.pdf,1040,,\n"])
    monkeypatch.setenv(vocab_report.ENV_REAL_CORPUS, str(folder))
    assert vocab_report.main(["build", vocab_report.OUT_FLAG, str(tmp_path / "reading")]) == 2
    out, err = capsys.readouterr()
    assert "could not be read (ValueError)" in err
    for leak in ("Client Secret", "Private Corpus Folder", "Traceback"):
        assert leak not in out + err


def test_a_file_the_system_refuses_is_said_by_its_class(tmp_path, monkeypatch):
    """The size check sits before extract's own guard; a refusal there is a class, not a path."""
    import errno

    import pytest

    folder = fabricated_corpus(tmp_path / "corpus", {"Client Secret.pdf": GARBAGE}, ["Client Secret.pdf,1040,2025,\n"])
    monkeypatch.setenv(vocab_report.ENV_REAL_CORPUS, str(folder))

    def refused(path, **_kwargs):
        raise PermissionError(errno.EACCES, "Permission denied", str(path))

    monkeypatch.setattr(vocab_report, "extract", refused)
    with pytest.raises(vocab_report.ReportError) as raised:
        vocab_report.real_documents()
    assert "expectations entry 1 (PermissionError (EACCES))" in str(raised.value)
    assert "Client Secret" not in str(raised.value) and str(folder) not in str(raised.value)
