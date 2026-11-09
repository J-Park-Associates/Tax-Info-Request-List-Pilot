"""Tests for tracker/api.py: the review queue, a person's actions on it, and the words a card says.

What needs review and how it is triaged, a person's action judged against the record (decision 112), recovery as the
person's own (decision 110), a status in a preparer's words (decision 200), an unnamed issuer's card (decision 201)
and a file name on the page that is a live link.

Split from ``tests/test_api.py`` by SPEC-architecture-p5 P5.14 (E-3), by the banners the old file kept its
sections under, each test moved byte for byte with its section, so that each family runs as its own process
(Jason, 2026-09-29) and an affected-tests run reaches only the family a change touched. The map owns this file
as ``tracker/api.py``'s test by its name (decision P350). What more than one family reads is
``tests/api_driver.py``'s, because a test file may not import another (``tests/test_suite_shape.py``).
"""

import json
import re
from pathlib import Path

import pytest

import tracker.api as api
from tests import api_driver
from tests.api_driver import (
    HOUSEHOLD,
    SAMPLE_PEOPLE,
    _issuer_return,
    _parked_read_pdf_state,
    _parked_row,
    _walk_strings,
    a_moved_row,
    payload_of_state,
    run,
    sample_engagement,
    scan,
    two_households,
    waiting_document,
    where,
)
from tests.node_harness import APP_SCRIPTS, RENDERER_SCRIPTS, js_block, js_function, renderer_text, stripped_js
from tests.samples import text_pdf
from tracker import firm_view, ledger, manifest, reasons, request_edit, screen_words, store, view
from tracker.index import FILED, NEEDS_REVIEW, read_index
from tracker.layout import inbox_of
from tracker.manifest import COL_MANUAL_OVERRIDE, COL_OVERRIDE_REASON, Status
from tracker.records import ledger_key
from tracker.scaffold import PREPARED_DIR_NAME, REVIEW_DIR_NAME
from tracker.templates import BASE_YEAR

#: A fixture of ``tests/api_driver.py``, named here so every claim below can ask for it.
demo_root = api_driver.demo_root


# ------------------------------------------------------------ needs review ----


def test_assign_files_a_parked_document_and_rescans(capsys, demo_root, tmp_path):
    engagement = sample_engagement(capsys, demo_root, tmp_path,
                                   "Mortgage Notes.docx", "Form 1098 Mortgage Interest.pdf")
    code, payload = scan(capsys, engagement)
    assert code == 0
    parked = [e for e in payload["state"]["index"] if e["decision"] == NEEDS_REVIEW]
    assert [e["original_name"] for e in parked] == ["Mortgage Notes.docx"]

    code, payload = run(capsys, "assign", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"original": parked[0]["pbc_location"], "identifier": "D01",
                               "keyword": "mortgage notes", "seq": parked[0]["seq"]})
    assert code == 0, payload
    assigned = payload["assigned"]
    assert assigned["identifier"] == "D01" and assigned["moved_review_copy"] is True
    assert assigned["keyword"] == "mortgage notes" and assigned["scan_note"] == ""
    # What the page says it did, worded as the page typed it before R5.5;
    # no spelling was taught, so that one is empty and is not said.
    assert assigned["said"] == {
        "filed": f"Mortgage Notes.docx filed as {assigned['filed_as']}",
        "keyword_added": '"mortgage notes" added to D01 so the next one files itself',
        "spelling_added": ""}
    assert not [e for e in payload["state"]["index"] if e["decision"] == NEEDS_REVIEW]
    d01 = next(i for i in payload["state"]["items"] if i["identifier"] == "D01")
    assert "mortgage notes" in d01["any_keywords"]
    # The re-scan saw it straight away. D01 accepts pdf/xlsx and this is a
    # .docx, but a person looked at it and filed it: their decision stands,
    # the row is Received, and the note says the rules were not applied.
    from tracker.scanner import ACCEPTED_NOTE

    assert d01["status"] == Status.RECEIVED
    assert ACCEPTED_NOTE.format(n=1) in d01["validation_notes"]


def test_the_assign_sentences_are_the_apis_and_the_page_types_none_of_them():
    """R5.5 (D-9): the three sentences ``fileRow`` said are the API's
    constants, worded byte for byte as the page typed them, and no script
    the page loads holds any of their words in its code."""
    assert screen_words.ASSIGNED_FILED == "{name} filed as {filed_as}"
    assert screen_words.ASSIGNED_KEYWORD_ADDED == '"{keyword}" added to {identifier} so the next one files itself'
    assert screen_words.ASSIGNED_SPELLING_ADDED == '"{spelling}" added so the next page that prints it confirms itself'
    text = "\n".join(stripped_js(name) for name in RENDERER_SCRIPTS)
    for sentence in (screen_words.ASSIGNED_FILED, screen_words.ASSIGNED_KEYWORD_ADDED, screen_words.ASSIGNED_SPELLING_ADDED):
        for words in re.split(r"\{\w+\}", sentence):
            if len(words.split()) >= 2:
                assert words.strip(' "') not in text, words
    app = renderer_text(APP_SCRIPTS)
    assert "a.said.filed" in app and "a.said.keyword_added" in app
    assert "a.said.spelling_added" in app


def teach(folder, identifier: str, keyword: str) -> None:
    """A keyword recorded against a request, as a person's filing records it."""
    from tracker.index import ensure
    from tracker.locking import engagement_lock

    with engagement_lock(folder):
        ensure(folder)
        store.record(store.connect(), folder, ledger.new(ledger.KEYWORD_LEARNED, **{
            ledger.IDENTIFIER_KEY: identifier, ledger.KEYWORD_KEY: keyword,
        }))


def test_unlearn_records_one_event_re_scans_and_the_state_no_longer_lists_the_keyword(
        capsys, demo_root):
    """Decision 113: one event, and the request read again in the same breath.

    The re-scan is what makes the difference visible now rather than on
    Saturday: the engagement has never been scanned when the unlearn
    arrives, and the state that comes back carries a status for every row,
    which only a pass writes.
    """
    spec = {"household": HOUSEHOLD, "return_name": "Smith", "items": [{"identifier": "A01", "document": "W-2"},
                                       {"identifier": "C01", "document": "Form 1098"}]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    folder = where(demo_root, "Smith")
    teach(folder, "A01", "lender")
    state = api.state(folder)
    assert state["learned"] == {"A01": ["lender"]}
    assert not any(item["status"] for item in state["items"])      # nothing has scanned it

    code, payload = run(capsys, "unlearn", api.ENGAGEMENT_FLAG, str(folder),
                        stdin={"identifier": "A01", "keyword": "lender"})

    assert code == 0, payload
    assert payload["unlearned"] == {"identifier": "A01", "keyword": "lender", "scan_note": ""}
    assert payload["state"]["learned"] == {}
    a01 = next(i for i in payload["state"]["items"] if i["identifier"] == "A01")
    assert "lender" not in a01["any_keywords"]
    assert a01["status"] == Status.MISSING                         # the re-scan, in the same call
    names = [e[ledger.EVENT_KEY] for e in ledger.read_events(folder)]
    assert names.count(ledger.KEYWORD_UNLEARNED) == 1


def test_unlearn_refuses_a_blank_or_unknown_pair_by_name(capsys, demo_root):
    """A refusal is the usual error sentence, and nothing is recorded."""
    from tracker.manifest import UNLEARN_REFUSED

    spec = {"household": HOUSEHOLD, "return_name": "Smith", "items": [{"identifier": "A01", "document": "W-2"}]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    folder = where(demo_root, "Smith")
    teach(folder, "A01", "lender")
    head = ledger.head(folder)

    for sent in ({"identifier": "", "keyword": "lender"},
                 {"identifier": "A01", "keyword": "  "},
                 {}):
        code, payload = run(capsys, "unlearn", api.ENGAGEMENT_FLAG, str(folder), stdin=sent)
        assert code == 1 and "Pick the request and the keyword" in payload["error"]

    code, payload = run(capsys, "unlearn", api.ENGAGEMENT_FLAG, str(folder),
                        stdin={"identifier": "A01", "keyword": "escrow"})
    assert code == 1
    assert payload["error"] == UNLEARN_REFUSED.format(identifier="A01", keyword="escrow")
    assert ledger.head(folder) == head
    assert api.state(folder)["learned"] == {"A01": ["lender"]}


def test_the_renderer_types_no_unlearn_word(capsys, demo_root):
    """The button beside a taught keyword and the sentence after it are the
    API's words, like every other word the editor shows."""
    js = renderer_text(APP_SCRIPTS)

    between = screen_words.UNLEARNED_NOTE.split("}")[1].split("{")[0].strip()      # "unlearned from"
    tail = screen_words.UNLEARNED_NOTE.split("{identifier}")[1].strip()            # the rest of it

    assert screen_words.UNLEARN_LABEL not in js
    assert between not in js and tail not in js
    assert "vocab.editor.unlearn_label" in js and "vocab.editor.unlearned_note" in js


def test_rule_two_names_the_inbox_and_the_years_folder_and_is_quoted_everywhere(
        capsys, demo_root, tmp_path):
    """Decision 102, the owner's wording of 2026-09-19, re-rendered for the
    layout of decision 125: the rule used to name the index workbook, and
    then the two folders `Shared` and `PBC`, and none of the three exists
    any more. It says the inbox the client drops into and the client's own
    folder for the year, filled from the one place each is named, and it
    still names no file."""
    from tracker import api
    from tracker.layout import INBOX_DIR_NAME
    from tracker.records import THE_RECORD

    (rule,) = [r for r in api.standing_rules() if r["headline"].startswith("Originals")]

    assert rule["detail"] == (
        f"Files are moved byte for byte under their own names out of {INBOX_DIR_NAME} "
        f"into the client's folder for the year; all work happens on copies, and "
        f"every move is recorded in {THE_RECORD}."
    )
    assert ".xlsx" not in rule["detail"]
    assert "Shared" not in rule["detail"] and "PBC" not in rule["detail"]
    # And nothing in the rendered rule is a placeholder nobody filled.
    assert "{" not in rule["detail"] and "}" not in rule["detail"]


def test_the_state_the_app_reads_carries_no_deferred_index(capsys, demo_root, tmp_path):
    """There is nothing left for Excel to hold the index rows out of, so
    there is no word for it - in the reply, in the pass's own report, or in
    the vocabulary the renderer derives from."""
    from tracker import api
    from tracker.run_log import EngagementRun

    spec = {"household": HOUSEHOLD, "return_name": "Smith 2025", "form": "1040", "client": "John Smith",
            "items": [t for t in api.FORM_TEMPLATES["1040"] if t["core"]]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    state = api.state(where(demo_root, "Smith 2025"))

    assert "index_deferred" not in state
    assert "index" not in state["paths"] and "manifest" not in state["paths"]
    assert not hasattr(EngagementRun(engagement=None), "index_deferred")
    assert "index_deferred" not in json.dumps(api.vocab())


def test_dismiss_records_that_nothing_asks_for_a_parked_document(capsys, demo_root, tmp_path):
    # The app's other half of Needs Review: a file no request asks for stops
    # being a thing to do without anything being deleted, and the word for it
    # comes from the vocabulary the renderer reads, not from the renderer.
    from tracker.filer import DISMISSED_BY_PERSON
    from tracker.index import NOT_REQUESTED

    engagement = sample_engagement(capsys, demo_root, tmp_path, "Mortgage Notes.docx")
    code, payload = scan(capsys, engagement)
    assert code == 0, payload
    [parked] = [e for e in payload["state"]["index"] if e["decision"] == NEEDS_REVIEW]

    code, payload = run(capsys, "dismiss", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"original": parked["pbc_location"], "note": "an IRS notice",
                               "seq": parked["seq"]})
    assert code == 0, payload
    dismissed = payload["dismissed"]
    assert dismissed["decision"] == NOT_REQUESTED
    assert dismissed["reason"].startswith(DISMISSED_BY_PERSON)
    assert "an IRS notice" in dismissed["reason"]
    # The row is rewritten in place and the working copy is still parked.
    assert not [e for e in payload["state"]["index"] if e["decision"] == NEEDS_REVIEW]
    [row] = [e for e in payload["state"]["index"] if e["decision"] == NOT_REQUESTED]
    assert (engagement / row["prepared_location"]).is_file()
    assert api.vocab()["decisions"]["dismissed"] == NOT_REQUESTED


def test_unfile_sends_a_filed_document_back_for_review_and_the_status_with_it(capsys, demo_root, tmp_path):
    # The correction people used to make by dragging in Explorer, which the
    # index never learned: the row and the request both follow the file.
    from tracker.filer import UNFILED_BY_PERSON

    engagement = sample_engagement(capsys, demo_root, tmp_path, "Form 1098 Mortgage Interest.pdf")
    code, payload = scan(capsys, engagement)
    assert code == 0, payload
    [filed] = [e for e in payload["state"]["index"] if e["decision"] == FILED]
    request = next(i for i in payload["state"]["items"] if i["identifier"] == filed["identifier"])
    assert request["status"] == Status.RECEIVED

    code, payload = run(capsys, "unfile", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"original": filed["pbc_location"], "note": "wrong request",
                               "seq": filed["seq"]})
    assert code == 0, payload
    unfiled = payload["unfiled"]
    assert unfiled["decision"] == NEEDS_REVIEW
    assert unfiled["reason"].startswith(UNFILED_BY_PERSON) and "wrong request" in unfiled["reason"]
    assert unfiled["moved_working_copy"] is True
    assert unfiled["left_filed"] == "" and unfiled["scan_note"] == ""
    # The working copy is parked under the client's own name...
    parked = engagement / unfiled["prepared_location"]
    assert parked.is_file() and parked.name == filed["original_name"]
    assert not (engagement / filed["prepared_location"]).exists()
    # ...and the request it was answering is not Received any more.
    request = next(i for i in payload["state"]["items"] if i["identifier"] == filed["identifier"])
    assert request["status"] != Status.RECEIVED
    assert payload["state"]["summary"]["received"] == 0


def test_mark_missing_takes_one_request_off_a_consolidated_statement(capsys, demo_root):
    """d146. The app's button: the filed statement's row names the requests
    it answers, and marking one missing again leaves the statement filed,
    re-scans, and hands back the state with that request outstanding."""
    from tests.builders import _consolidated_return

    engagement = _consolidated_return(demo_root)
    code, payload = scan(capsys, engagement)
    assert code == 0, payload
    [filed] = [e for e in payload["state"]["index"] if e["decision"] == FILED]
    assert filed["identifier"] == "E01" and filed["answered"] == ["A02", "A04"]

    code, payload = run(capsys, "mark-missing", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"original": filed["pbc_location"], "identifier": "A02",
                               "seq": filed["seq"]})
    assert code == 0, payload
    assert payload["marked_missing"]["identifier"] == "A02"
    [filed] = [e for e in payload["state"]["index"] if e["decision"] == FILED]
    assert filed["answered"] == ["A04"]
    a02 = next(i for i in payload["state"]["items"] if i["identifier"] == "A02")
    assert a02["status"] == Status.MISSING

    code, payload = run(capsys, "mark-missing", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"original": filed["pbc_location"], "identifier": "A02",
                               "seq": filed["seq"]})
    assert code == 1 and "does not answer A02" in payload["error"]


def test_unfile_refuses_what_is_not_filed(capsys, demo_root, tmp_path):
    engagement = sample_engagement(capsys, demo_root, tmp_path, "nothing")
    code, payload = run(capsys, "unfile", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"original": "ghost.pdf", "seq": 1})
    assert code == 1
    assert "nothing in the index is called 'ghost.pdf'" in payload["error"]
    code, payload = run(capsys, "unfile", api.ENGAGEMENT_FLAG, str(engagement), stdin={})
    assert code == 1 and payload["error"]


def test_dismiss_refuses_a_file_the_index_does_not_know(capsys, demo_root, tmp_path):
    engagement = sample_engagement(capsys, demo_root, tmp_path, "nothing")
    code, payload = run(capsys, "dismiss", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"original": "ghost.pdf", "seq": 1})
    assert code == 1
    assert "nothing in the index is called 'ghost.pdf'" in payload["error"]
    code, payload = run(capsys, "dismiss", api.ENGAGEMENT_FLAG, str(engagement), stdin={})
    assert code == 1 and payload["error"]


@pytest.mark.parametrize("command, refusal, spec", [
    ("dismiss", "Pick the file no request asks for", {}),
    ("unfile", "Pick the document to send back for review", {}),
    ("restore", "Pick the working copy to put back", {}),
    ("mark-missing", "Pick the statement and the request to mark missing", {"identifier": "A01"}),
    ("assign", "Pick the file and the request it belongs to", {"identifier": "A01"}),
])
def test_a_null_original_is_the_same_refusal_as_a_blank_one(capsys, demo_root, tmp_path,
                                                            command, refusal, spec):
    """A JSON ``null`` is no file. It was once turned into the text ``None``,
    which passed the "Pick the file" refusal and went on to look for a
    document of that name."""
    engagement = sample_engagement(capsys, demo_root, tmp_path, "nothing")
    for given in (None, "", "   "):
        code, payload = run(capsys, command, api.ENGAGEMENT_FLAG, str(engagement),
                            stdin={**spec, "original": given, "seq": 1})
        assert code == 1 and payload["error"] == refusal, (given, payload)


def test_a_null_text_field_reads_as_missing_and_other_values_as_their_text():
    assert api._text({"original": None}, "original") == ""
    assert api._text({}, "original") == ""
    assert api._text({"original": "  a.pdf "}, "original") == "a.pdf"
    assert api._text({"original": 7}, "original") == "7"


# ------------------------------------------------- the review queue, triaged ----


def triage_engagement(capsys, demo_root, extra=()):
    """One engagement whose drop folder holds a document two requests want.

    Two rows, each with a plain required keyword, and one document that
    says A02's in its title and A01's far down the page: the router files
    neither (it matches more than one request) and the row is parked
    carrying both keywords, where they were said, through the filer's own
    writers. Nothing here types an evidence string.

    ``extra`` adds rows the document says nothing about, for the claim that
    needs a request off the shortlist to file to.
    """

    spec = {"household": HOUSEHOLD, "return_name": "Reed Property 2025", "client": "Ada Reed", "items": [
        {"identifier": "A01", "document": "Mortgage Interest Statement", "period": "TY2025",
         "required_keywords": "mortgage interest", "min_size_kb": 0, "date_pattern": "*"},
        {"identifier": "A02", "document": "Rental Property Statements", "period": "TY2025",
         "required_keywords": "rental income", "min_size_kb": 0, "date_pattern": "*"},
        *extra,
    ]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    engagement = where(demo_root, "Reed Property 2025")
    text_pdf(inbox_of(engagement) / "packet.pdf", "\n".join([
        "Rental income summary for the year 2025",
        "Lakeside Property Management",
        *[f"Unit {n:03d} rent collected and expenses paid during the year" for n in range(60)],
        "The mortgage interest paid on the property is shown below.",
    ]))
    return engagement


def test_the_state_triages_each_parked_file_best_first_with_the_reason_behind_each(
    capsys, demo_root,
):
    from tracker.review import IDENTITY_UNKNOWN

    engagement = triage_engagement(capsys, demo_root)
    code, payload = scan(capsys, engagement)
    assert code == 0, payload
    state = payload["state"]

    [triaged] = state["review"]
    [parked] = [e for e in state["index"] if e["decision"] == NEEDS_REVIEW]
    assert triaged["pbc_location"] == parked["pbc_location"], "the queue joins to the index row"
    # Best first, and best is not the manifest's order: A02 said its
    # keyword in the title, A01 said its own far down the same page.
    assert [s["identifier"] for s in triaged["shortlist"]] == ["A02", "A01"]
    assert [s["rank"] for s in triaged["shortlist"]] == sorted(
        s["rank"] for s in triaged["shortlist"]
    )
    assert all(s["rank"][0] == IDENTITY_UNKNOWN for s in triaged["shortlist"])
    # The sentence behind each, whole, as review.py wrote it: the row's own
    # word and where the document said it.
    first, second = triaged["shortlist"]
    assert first["reason"].startswith("A02") and "'rental income' in the title" in first["reason"]
    assert second["reason"].startswith("A01") and "'mortgage interest'" in second["reason"]


def test_a_parked_file_the_evidence_says_nothing_about_is_offered_nothing(
    capsys, demo_root, tmp_path,
):
    # A bitmap: no request accepts a .bmp, so the record names no candidate
    # and the queue says so rather than nominating the nearest row. A .jpg
    # was the file here until decision 127 made a photo a document; the
    # claim is about a file type nobody takes, and this is one.
    engagement = sample_engagement(capsys, demo_root, tmp_path, "vacation photo.bmp")
    code, payload = scan(capsys, engagement)
    assert code == 0, payload

    [triaged] = payload["state"]["review"]
    assert triaged["original_name"] == "vacation photo.bmp"
    assert triaged["shortlist"] == [], "no evidence, no suggestion — the person reads it"


def test_the_review_card_has_three_buckets_and_opens_only_a_documents_copy(capsys, demo_root, tmp_path):
    """Decision 190's three buckets, decided here from the row's code and
    its type on disk: each parked row and its triage carry ``bucket`` and
    its true ``extension``; a document's row carries the key its review
    copy is named under in ``paths`` - the only paths the shell opens - and
    a program's carries none, nor, since Open follows 184, a container's,
    nor a document the tracker never read (no request takes a .bmp)."""

    engagement = sample_engagement(capsys, demo_root, tmp_path, "vacation photo.bmp")
    text_pdf(inbox_of(engagement) / "a letter.pdf", "\n".join(
        f"Line {n:03d} of a fabricated letter that answers no request on the list" for n in range(400)))
    (inbox_of(engagement) / "W-2 2025.pdf.exe").write_bytes(b"MZ")
    (inbox_of(engagement) / "scans.zip").write_bytes(b"PK\x03\x04 not really a zip")
    code, payload = scan(capsys, engagement)
    assert code == 0, payload
    state = payload["state"]

    rows = {e["original_name"]: e for e in state["index"] if e["decision"] == NEEDS_REVIEW}
    assert {name: (e["bucket"], e["extension"]) for name, e in rows.items()} == {
        "a letter.pdf": (firm_view.BUCKET_DOCUMENT, "pdf"),
        "vacation photo.bmp": (firm_view.BUCKET_DOCUMENT, "bmp"),
        "scans.zip": (firm_view.BUCKET_CONTAINER, "zip"),
        "W-2 2025.pdf.exe": (firm_view.BUCKET_NOT_A_DOCUMENT, "exe"),
    }
    assert rows["W-2 2025.pdf.exe"]["open_key"] == "" and rows["scans.zip"]["open_key"] == ""
    assert rows["vacation photo.bmp"]["code"] == reasons.NO_REQUEST_ACCEPTS_CODE
    assert rows["vacation photo.bmp"]["open_key"] == "", "never read, so never opened here"
    assert rows["a letter.pdf"]["code"] in reasons.READ_AND_PARKED_CODES, rows["a letter.pdf"]["code"]
    opened = Path(state["paths"][rows["a letter.pdf"]["open_key"]])
    assert opened.is_file() and opened.parent.name == REVIEW_DIR_NAME
    assert {t["original_name"]: t["bucket"] for t in state["review"]} == {
        name: e["bucket"] for name, e in rows.items()}


@pytest.mark.parametrize("name, code", [
    *(("statement.pdf", code) for code in sorted(reasons.NO_OPEN_CODES - firm_view._CONTAINER_CODES)),
    *(("mail.eml", code) for code in sorted(firm_view._CONTAINER_CODES)),
    ("scans.zip", reasons.AMBIGUOUS_CODE),
])
def test_a_refused_file_has_no_open_on_the_designated_machine(name, code):
    """Open follows 184 (decision 190): a file whose reading the tracker
    refused or never made, and any email or zip, is opened, if at all, on a
    machine with no Drive sign-in and no client folder - so the API names no
    copy for it to open here, whatever its copy on disk, and the card
    offers none."""
    row = _parked_row(name, code)
    payload = api._review_payload(row)
    assert payload["open_key"] == "", (name, code, payload)
    if name != "statement.pdf":
        assert payload["bucket"] == firm_view.BUCKET_CONTAINER, payload


@pytest.mark.parametrize("code", ["", "a-code-nobody-has-placed"])
def test_a_code_nobody_has_placed_gets_no_open(code):
    """Open is an allow-list, so it fails closed: a row with no code, or with
    a code no one has put in either set, offers no Open (decision 190)."""
    payload = api._review_payload(_parked_row("statement.pdf", code))
    assert payload["bucket"] == firm_view.BUCKET_DOCUMENT and payload["open_key"] == "", payload


@pytest.mark.parametrize("code", sorted(reasons.READ_AND_PARKED_CODES))
def test_a_read_and_parked_document_opens_its_marked_copy(code):
    """The other half of the rule: a document the tracker read and parked
    for a filing reason carries the key of its review copy - the firm's
    copy, marked for Protected View - and nothing else opens it."""
    row = _parked_row("statement.pdf", code)
    payload = api._review_payload(row)
    assert payload["bucket"] == firm_view.BUCKET_DOCUMENT
    assert payload["open_key"] == f"review_copy {ledger_key(row)}", payload


def test_every_parked_row_ships_a_unique_handle_and_a_program_from_a_zip_is_answered_by_it(
    capsys, demo_root, tmp_path,
):
    """The review's M3: a program taken from a zip has no location, so the
    row, its triage and every review command travel by ``handle`` - the
    record's key, unique where ``""`` named every such row and the API
    refused it. Setting the first aside by its handle sets aside that row
    and no other; the card also shows a hidden program's type clean (M1)."""
    import io
    import zipfile

    from tracker.index import NOT_REQUESTED

    engagement = sample_engagement(capsys, demo_root, tmp_path, "vacation photo.bmp")
    packed = io.BytesIO()
    with zipfile.ZipFile(packed, "w") as archive:
        archive.writestr("invoice.js", b"WScript.Echo(1)")
        archive.writestr("payroll.exe", b"MZ")
    (inbox_of(engagement) / "docs.zip").write_bytes(packed.getvalue())
    (inbox_of(engagement) / "Pay.scr\ufeff").write_bytes(b"MZ another program")
    code, payload = scan(capsys, engagement)
    assert code == 0, payload
    state = payload["state"]

    parked = {e["original_name"]: e for e in state["index"] if e["decision"] == NEEDS_REVIEW}
    handles = [e["handle"] for e in parked.values()]
    assert "" not in handles and len(set(handles)) == len(handles)
    assert {t["handle"] for t in state["review"]} == set(handles)
    assert parked["Pay.scr"]["bucket"] == firm_view.BUCKET_NOT_A_DOCUMENT
    assert parked["Pay.scr"]["extension"] == "scr" and parked["Pay.scr"]["open_key"] == ""

    first = parked["invoice.js"]
    assert first["pbc_location"] == ""
    code, payload = run(capsys, "dismiss", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"original": first["handle"], "note": "", "seq": first["seq"]})
    assert code == 0, payload
    after = {e["original_name"]: e["decision"] for e in payload["state"]["index"]
             if e["original_name"] in ("invoice.js", "payroll.exe")}
    assert after == {"invoice.js": NOT_REQUESTED, "payroll.exe": NEEDS_REVIEW}


def test_dismissing_a_file_takes_it_out_of_the_review_queue(capsys, demo_root, tmp_path):
    from tracker.index import NOT_REQUESTED

    engagement = sample_engagement(capsys, demo_root, tmp_path, "vacation photo.bmp")
    code, payload = scan(capsys, engagement)
    [parked] = payload["state"]["index"]
    assert [t["pbc_location"] for t in payload["state"]["review"]] == [parked["pbc_location"]]

    code, payload = run(capsys, "dismiss", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"original": parked["pbc_location"], "note": "a holiday snap",
                               "seq": parked["seq"]})
    assert code == 0, payload

    # The row is still in the index, said out loud; it is not work any more.
    [row] = [e for e in payload["state"]["index"] if e["decision"] == NOT_REQUESTED]
    assert row["pbc_location"] == parked["pbc_location"]
    assert payload["state"]["review"] == [], "a row nobody asks for is not triaged"


def test_a_resend_after_a_dismissal_is_triaged_and_its_row_carries_the_set_aside_sentence(
    capsys, demo_root, tmp_path,
):
    """Decision 111: the client sent it again, so it is somebody's work again.

    The sentence is the filer's and it rides the row, so the card reads it
    out of ``state["index"]`` the way it reads every other reason: nothing
    in tracker/review.py or in the vocabulary knows this decision happened.
    """
    from tracker.filer import RESENT_AFTER_SET_ASIDE
    from tracker.index import NOT_REQUESTED

    engagement = sample_engagement(capsys, demo_root, tmp_path, "vacation photo.bmp")
    code, payload = scan(capsys, engagement)
    assert code == 0, payload
    [parked] = payload["state"]["index"]
    # The row's own sequence number, read back out of the state the card was
    # drawn from, the way the app sends it: a review command that does not
    # carry it is refused (decision 112), and on a base without it this is
    # None and ignored.
    code, payload = run(capsys, "dismiss", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"original": parked["pbc_location"], "note": "a holiday snap",
                               "seq": parked.get("seq")})
    assert code == 0, payload
    [set_aside] = payload["state"]["index"]

    # The client sends the same photo again.
    original = engagement / set_aside["pbc_location"]
    (inbox_of(engagement) / original.name).write_bytes(original.read_bytes())
    code, payload = scan(capsys, engagement)
    assert code == 0, payload

    rows = payload["state"]["index"]
    assert [e["decision"] for e in rows] == [NOT_REQUESTED, NEEDS_REVIEW]
    again = rows[1]
    assert again["reason"].startswith(
        RESENT_AFTER_SET_ASIDE.format(earlier=set_aside["reason"])
    )
    # It is work again: the queue has it, joined to that row, with its own
    # copy under its own name.
    [triaged] = payload["state"]["review"]
    assert triaged["pbc_location"] == again["pbc_location"]
    assert triaged["original_name"] == again["original_name"]
    assert again["prepared_location"] != set_aside["prepared_location"]
    assert (engagement / again["prepared_location"]).is_file()
    assert (engagement / set_aside["prepared_location"]).is_file()


def test_assigning_a_shortlisted_request_files_it_and_the_queue_drops_it(capsys, demo_root):
    engagement = triage_engagement(capsys, demo_root)
    code, payload = scan(capsys, engagement)
    [triaged] = payload["state"]["review"]
    best = triaged["shortlist"][0]["identifier"]

    code, payload = run(capsys, "assign", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"original": triaged["pbc_location"], "identifier": best,
                               "seq": triaged["seq"]})
    assert code == 0, payload

    assert payload["assigned"]["identifier"] == best
    assert payload["state"]["review"] == [], "filed is not parked"
    [filed] = [e for e in payload["state"]["index"] if e["decision"] == FILED]
    assert filed["identifier"] == best


def test_the_vocabulary_carries_every_word_the_review_card_shows(capsys, demo_root):
    from tracker.records import WHERE_FOOTER
    from tracker.review import IDENTIFIER_SEPARATOR, MAX_SUGGESTIONS, PLACE_WORDS
    from tracker.screen_words import FOOTER_PLACE_WORDS, NOTHING_SUGGESTED_WORDS, SET_ASIDE_NOTE_WORDS

    vocab = run(capsys, "list")[1]["vocab"]
    # The app says the short words; the status report and the console keep
    # tracker.review's sentences, which they still read (P84).
    places = {**PLACE_WORDS, WHERE_FOOTER: FOOTER_PLACE_WORDS}

    # The card's own buttons and headings...
    labels = vocab["review_labels"]
    assert labels["file"] == screen_words.FILE_LABEL and labels["dismiss"] == screen_words.DISMISS_LABEL
    assert labels["file_anyway"] == screen_words.FILE_ANYWAY_LABEL
    assert labels["suggested"] == screen_words.SUGGESTED_HEADING
    assert labels["other_requests"] == screen_words.OTHER_REQUESTS_HEADING
    # ...its second rendering's three answers and the toggle's two words
    # (decision 114), which head their suggestion with the word above.
    assert labels["accept"] == screen_words.ACCEPT_LABEL and labels["skip"] == screen_words.SKIP_LABEL
    assert labels["open_in_list"] == screen_words.OPEN_IN_LIST_LABEL
    assert labels["card_mode"] == screen_words.CARD_MODE_LABEL
    assert labels["list_mode"] == screen_words.LIST_MODE_LABEL
    assert labels["card_position"] == screen_words.CARD_POSITION
    # ...and every word tracker.review owns, from tracker.review or, where
    # the app says it shorter, from the API.
    assert vocab["triage"] == {
        "nothing_suggested": NOTHING_SUGGESTED_WORDS,
        "identifier_separator": IDENTIFIER_SEPARATOR,
        "places": places,
        "max_suggestions": MAX_SUGGESTIONS,
        "set_aside_note": SET_ASIDE_NOTE_WORDS,
    }
    # Nothing the card shows is typed in the renderer: every one of these
    # reaches the screen through vocab, never as a literal of its own. Read
    # over every script the page loads (R3.3).
    renderer = renderer_text()
    for word in (*labels.values(), NOTHING_SUGGESTED_WORDS, SET_ASIDE_NOTE_WORDS, *places.values()):
        assert f'"{word}"' not in renderer and f"'{word}'" not in renderer, word


def test_the_editor_saves_a_reason_and_the_vocabulary_carries_the_list_and_the_label(capsys, demo_root):
    """Decision 116: every word the editor and the table show about an
    override is the API's - the reasons, the word that opens the box, the
    label pattern, the set-aside sentence and the returning-client line -
    and the reason the editor saves travels in the one rules_changed event
    beside the override."""
    from tracker.manifest import (
        NOT_APPLICABLE_LABEL,
        OVERRIDE_REASON_OTHER,
        OVERRIDE_REASONS,
        Override,
    )
    from tracker.rollover import ORIGIN_NOT_APPLICABLE
    from tracker.screen_words import SET_ASIDE_NOTE_WORDS as SET_ASIDE_NOTE

    vocab = run(capsys, "list")[1]["vocab"]
    assert vocab["override_reasons"] == list(OVERRIDE_REASONS)
    assert vocab["override_reason_other"] == OVERRIDE_REASON_OTHER
    assert vocab["labels"][Override.NOT_APPLICABLE]["label"] == NOT_APPLICABLE_LABEL
    assert "not_applicable_label" not in vocab
    assert vocab["triage"]["set_aside_note"] == SET_ASIDE_NOTE
    assert vocab["origin_not_applicable"] == ORIGIN_NOT_APPLICABLE
    assert vocab["not_applicable_carried"] == screen_words.NOT_APPLICABLE_CARRIED
    assert [c["key"] for c in vocab["columns"]][-4:] == [
        "override_reason", "named", "asked", "short_title"]
    renderer = renderer_text()   # every script the page loads (R3.3)
    for word in (*OVERRIDE_REASONS, OVERRIDE_REASON_OTHER, *Override.ALL, NOT_APPLICABLE_LABEL,
                 SET_ASIDE_NOTE, screen_words.NOT_APPLICABLE_CARRIED, view.SET_ASIDE_SECTION, view.SET_ASIDE_GROUP):
        assert f'"{word}"' not in renderer and f"'{word}'" not in renderer, word
    for word in (*Override.ALL, OVERRIDE_REASON_OTHER, "Not Applicable in"):
        assert word not in renderer, word
    # Decision 142 (its review, R1): the words it adds reach the page only
    # through this vocabulary, and the renderer types none of them.
    from tracker.manifest import NOT_ASKED_LABEL
    from tracker.rollover import ORIGIN_NEW

    assert vocab["not_asked_label"] == NOT_ASKED_LABEL
    assert vocab["ask_the_client"] == screen_words.ASK_THE_CLIENT
    assert vocab["request_list"] == screen_words.REQUEST_LIST_WORDS == "request list"   # the dialog's heading (R5.5)
    assert vocab["not_asked_table_label"] == screen_words.NOT_ASKED_TABLE_LABEL
    assert vocab["roll_template_label"] == screen_words.ROLL_TEMPLATE_LABEL
    assert vocab["nothing_asked"] == screen_words.NOTHING_ASKED
    assert vocab["origin_new"] == ORIGIN_NEW
    assert vocab["new_not_asked_carried"] == screen_words.NEW_NOT_ASKED_CARRIED
    assert vocab["set_aside"] == {"heading": view.SET_ASIDE_SECTION, "group": view.SET_ASIDE_GROUP}
    assert "not_asked_heading" not in vocab["editor"]
    assert vocab["editor"]["yes_no_fields"] == ["named", "asked"]
    html = (Path(__file__).resolve().parent.parent / "app" / "renderer" / "index.html").read_text(
        encoding="utf-8")
    for word in (NOT_ASKED_LABEL, screen_words.ASK_THE_CLIENT, screen_words.ASK_THE_CLIENT_NOTE,
                 screen_words.NOT_ASKED_TABLE_LABEL, screen_words.ROLL_TEMPLATE_LABEL, screen_words.NOTHING_ASKED,
                 screen_words.NEW_NOT_ASKED_CARRIED.split("{n}")[1].split(" - ")[0].strip(),
                 view.SET_ASIDE_SECTION.split("{")[0].strip()):
        assert word not in renderer and word not in html, word

    spec = {"household": HOUSEHOLD, "return_name": "Smith", "items": [
        {"identifier": "A01", "document": "W-2", "required_keywords": "W-2"},
        {"identifier": "A02", "document": "1098", "required_keywords": "1098", "period": "TY2025"},
    ]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    engagement = where(demo_root, "Smith")
    rows = payload_of_state(capsys, engagement)["rules"]
    assert all(row["override_reason"] == "" for row in rows)

    # Accepted with no reason is refused, by row and column, and nothing is recorded.
    before = ledger.path_for(engagement).read_bytes()
    refused = [{**rows[0], "manual_override": Override.ACCEPTED}, rows[1]]
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"items": refused, "engagement": {}})
    assert code == 1 and payload["error"] == (
        f"Row 1: {COL_OVERRIDE_REASON} is required when {COL_MANUAL_OVERRIDE} is {Override.ACCEPTED}")
    assert ledger.path_for(engagement).read_bytes() == before

    # The word that opens the box is refused; the typed words are the reason.
    typed = [{**rows[0], "manual_override": Override.ACCEPTED, "override_reason": OVERRIDE_REASON_OTHER},
             rows[1]]
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"items": typed, "engagement": {}})
    assert code == 1 and "needs the reason typed" in payload["error"]
    edited = [{**rows[0], "manual_override": Override.ACCEPTED, "override_reason": "walked in on Tuesday"},
              {**rows[1], "manual_override": Override.NOT_APPLICABLE}]
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"items": edited, "engagement": {}})
    assert code == 0, payload
    assert payload["saved"]["changed"] == ["A01", "A02"]
    [event] = [e for e in ledger.read_events(engagement) if e[ledger.EVENT_KEY] == ledger.RULES_CHANGED][1:]
    by_id = {row["identifier"]: row for row in event[ledger.RULES_KEY]}
    assert by_id["A01"]["manual_override"] == Override.ACCEPTED
    assert by_id["A01"]["override_reason"] == "walked in on Tuesday"
    assert by_id["A02"]["manual_override"] == Override.NOT_APPLICABLE

    state = payload["state"]
    assert state["rules"][0]["override_reason"] == "walked in on Tuesday"
    assert state["summary"]["not_applicable"] == 1 and state["summary"]["total"] == 1
    # And the same list again records nothing.
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"items": state["rules"], "engagement": {}})
    assert code == 0 and payload["saved"]["recorded"] is False


def test_state_ships_each_rows_year_for_the_label(capsys, demo_root):
    """The renderer labels a set-aside row with the year the API gives the
    row, from its own Period, and reads nothing out of the Period's text."""
    from tracker.manifest import Override

    spec = {"household": HOUSEHOLD, "return_name": "Smith", "items": [
        {"identifier": "A01", "document": "W-2", "period": "TY2025", "manual_override": Override.NOT_APPLICABLE},
        {"identifier": "A02", "document": "Prior return", "period": "TY2024", "date_pattern": "*"},
        {"identifier": "A03", "document": "Whenever", "period": "quarterly"},
    ]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    state = payload_of_state(capsys, where(demo_root, "Smith"))
    years = {item["identifier"]: item["year"] for item in state["items"]}
    assert years == {"A01": 2025, "A02": 2024, "A03": None}
    [set_aside] = [item for item in state["items"] if item["manual_override"] == Override.NOT_APPLICABLE]
    assert set_aside["identifier"] == "A01" and set_aside["override_reason"] == ""


def test_assign_refuses_a_bad_request_with_a_sentence(capsys, demo_root, tmp_path):
    engagement = sample_engagement(capsys, demo_root, tmp_path, "nothing")
    code, payload = run(capsys, "assign", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"original": "ghost.pdf", "identifier": "A01", "seq": 1})
    assert code == 1
    assert "nothing in the index is called 'ghost.pdf'" in payload["error"]


# ----------- a person's action is judged against the record (d112) ----


def test_the_state_ships_each_rows_seq_on_the_index_and_on_the_review_list(
    capsys, demo_root, tmp_path,
):
    """The handle the card carries out. It rides beside the row and never in
    it: the index row itself is unchanged, and what is added is the record's
    own bookkeeping - the journal line that last wrote that row."""
    engagement = sample_engagement(capsys, demo_root, tmp_path,
                                   "Mortgage Notes.docx", "Form 1098 Mortgage Interest.pdf")
    code, payload = scan(capsys, engagement)
    assert code == 0, payload
    state = payload["state"]

    held = store.document_seqs(store.connect(), engagement)
    assert held, "the rows this pass wrote"
    assert {e["pbc_location"]: e["seq"] for e in state["index"]} == held
    assert {t["pbc_location"]: t["seq"] for t in state["review"]} == {
        e["pbc_location"]: held[e["pbc_location"]]
        for e in state["index"] if e["decision"] == NEEDS_REVIEW
    }


def test_a_review_command_with_no_seq_is_refused_and_a_stale_one_names_the_newer_decision(
    capsys, demo_root, tmp_path,
):
    """The app is drawn from ``state``, so it always has one; a spec without
    it is a caller with no view and is refused rather than acted on. And the
    card a person was called away from is refused with what the record now
    says, in the filer's own sentence."""
    from tracker.filer import STALE_ROW
    from tracker.index import NOT_REQUESTED

    engagement = sample_engagement(capsys, demo_root, tmp_path, "Mortgage Notes.docx")
    code, payload = scan(capsys, engagement)
    assert code == 0, payload
    [parked] = [e for e in payload["state"]["index"] if e["decision"] == NEEDS_REVIEW]

    code, payload = run(capsys, "assign", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"original": parked["pbc_location"], "identifier": "D01"})
    assert code == 1 and payload["error"] == screen_words.NO_SEQ

    # Somebody else sets the row aside while this card is open. It is still
    # parked, so the by-name refusal has nothing to say about it.
    code, after = run(capsys, "dismiss", api.ENGAGEMENT_FLAG, str(engagement),
                      stdin={"original": parked["pbc_location"], "note": "an IRS notice",
                             "seq": parked["seq"]})
    assert code == 0, after
    [now] = [e for e in after["state"]["index"] if e["decision"] == NOT_REQUESTED]

    code, payload = run(capsys, "assign", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"original": parked["pbc_location"], "identifier": "D01",
                               "seq": parked["seq"]})
    assert code == 1
    assert payload["error"] == STALE_ROW.format(
        name=now["original_name"], decision=now["decision"], reason=now["reason"])


def test_assign_records_the_override_against_the_shortlist_the_api_computed(capsys, demo_root):
    """Decision 84 lets a person file to any row on the engagement; the
    record now says when they filed against the evidence, and the shortlist
    it says they overruled is the one this command computed from the row the
    filer then acted on."""
    from tracker.filer import OVERRODE_SHORTLIST

    engagement = triage_engagement(capsys, demo_root, extra=[
        {"identifier": "A03", "document": "Prior Year Return", "period": "TY2025",
         "required_keywords": "prior year return", "min_size_kb": 0, "date_pattern": "*"},
    ])
    code, payload = scan(capsys, engagement)
    assert code == 0, payload
    [triaged] = payload["state"]["review"]
    suggested = [s["identifier"] for s in triaged["shortlist"]]
    assert suggested == ["A02", "A01"], "the document says nothing about A03"

    code, payload = run(capsys, "assign", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"original": triaged["pbc_location"], "identifier": "A03",
                               "seq": triaged["seq"]})
    assert code == 0, payload
    said = OVERRODE_SHORTLIST.format(listed=", ".join(suggested))
    assert payload["assigned"]["overrode_shortlist"] == said
    [row] = [e for e in payload["state"]["index"] if e["decision"] == FILED]
    assert said in row["reason"] and row["identifier"] == "A03"

    # The same document filed to the first of its suggestions instead:
    # nothing was overruled, so nothing is said.
    code, back = run(capsys, "unfile", api.ENGAGEMENT_FLAG, str(engagement),
                     stdin={"original": row["pbc_location"], "seq": row["seq"]})
    assert code == 0, back
    [again] = back["state"]["review"]
    code, payload = run(capsys, "assign", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"original": again["pbc_location"], "identifier": suggested[0],
                               "seq": again["seq"]})
    assert code == 0, payload
    assert payload["assigned"]["overrode_shortlist"] == ""

def test_the_state_carries_a_file_moved_row_in_the_index_and_in_no_list(capsys, demo_root, tmp_path):
    """Decision 109. A row whose working copy somebody dragged is in the
    index, where every column of it is readable, and in none of the lists
    the app draws: it is not waiting for review and it is not filed where
    the record says, and what to do about it is decision 110's card."""
    from tracker.index import FILE_MOVED

    engagement = sample_engagement(capsys, demo_root, tmp_path, "Form 1098 Mortgage Interest.pdf")
    code, payload = scan(capsys, engagement)
    assert code == 0, payload
    [filed] = [e for e in payload["state"]["index"] if e["decision"] == FILED]
    home = engagement / filed["prepared_location"]
    review_dir = engagement / PREPARED_DIR_NAME / REVIEW_DIR_NAME
    review_dir.mkdir(parents=True, exist_ok=True)
    home.rename(review_dir / home.name)                 # dragged by hand

    code, payload = scan(capsys, engagement)
    assert code == 0, payload
    state = payload["state"]
    [moved] = [e for e in state["index"] if e["decision"] == FILE_MOVED]
    assert moved["pbc_location"] == filed["pbc_location"]
    assert moved["prepared_location"] == filed["prepared_location"]   # home stays the column
    assert moved["pbc_location"] not in [t["pbc_location"] for t in state["review"]]
    assert not [e for e in state["index"]
                if e["decision"] == FILED and e["pbc_location"] == moved["pbc_location"]]
    assert api.vocab()["decisions"]["file_moved"] == FILE_MOVED
    # And the request it left is the firm's to sort out, not an ask.
    assert payload["run"]["warnings"]


# --------------- recovery is the person's: the moved card (d110) ----


WANDERED = {
    # In Prepared itself, renamed by a person under its request's name...
    "renamed under its request's name": (
        lambda eng, home: home.with_name(home.name.split(" - ")[0] + " - the 1098 (final).pdf"), True),
    # ...but not under a name no request's identifier begins.
    "renamed to a name no request begins": (
        lambda eng, home: home.with_name("the 1098 (final).pdf"), False),
    # A folder a person made inside Prepared is theirs (decision 168), even
    # one shaped like a request's...
    "a person's folder": (lambda eng, home: eng / PREPARED_DIR_NAME / "C01 - old" / home.name, False),
    # ...and the review folder belongs to no request.
    "the review folder": (
        lambda eng, home: eng / PREPARED_DIR_NAME / REVIEW_DIR_NAME / home.name, False),
}


@pytest.mark.parametrize("where", list(WANDERED))
def test_the_state_lists_moved_rows_with_home_now_seq_and_the_request_its_name_belongs_to(
    capsys, demo_root, tmp_path, where,
):
    """Decision 110's card is its own list, not a fourth column: the row's
    record version, the home the record put the copy at, where its bytes are
    now, and - only where the copy sits in Prepared itself under a name that
    belongs to a request (decision 168) - which request that is, because
    "keep it where it is" means nothing anywhere else."""
    from tracker.index import FILE_MOVED

    drag_to, in_a_request = WANDERED[where]
    engagement, filed, target, state = a_moved_row(capsys, demo_root, tmp_path, drag_to)

    [moved] = state["moved"]
    [row] = [e for e in state["index"] if e["decision"] == FILE_MOVED]
    assert moved["pbc_location"] == filed["pbc_location"]
    assert moved["original_name"] == filed["original_name"]
    assert moved["home"] == filed["prepared_location"]
    assert moved["now"] == target.relative_to(engagement).as_posix()
    assert moved["seq"] == row["seq"] and moved["seq"] != filed["seq"]
    assert moved["in_request"] == (filed["identifier"] if in_a_request else "")
    # And it is in none of the other lists: it is not waiting for review and
    # it is not filed where the record says.
    assert state["review"] == []
    assert not [e for e in state["index"] if e["decision"] == FILED]


def test_keep_it_here_is_offered_by_the_copys_name(capsys, demo_root, tmp_path):
    """Claim 7 (decision 168, ruling 6): a mislaid copy a person renamed
    within Prepared to ``A01 - ...`` - another request's name - is offered
    Keep it here for A01, and keeping it files it there as A01's canonical
    copy, beside the others; one inside a person's folder is offered no
    Keep it here."""
    engagement, filed, target, state = a_moved_row(
        capsys, demo_root, tmp_path, lambda eng, home: home.with_name("A01 - the 1098 I renamed.pdf"))
    [moved] = state["moved"]
    assert filed["identifier"] == "C01" and moved["in_request"] == "A01"

    code, payload = run(capsys, "assign", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"original": moved["pbc_location"], "identifier": moved["in_request"],
                               "seq": moved["seq"]})
    assert code == 0, payload
    [row] = [e for e in payload["state"]["index"] if e["decision"] == FILED]
    assert row["identifier"] == "A01"
    assert row["prepared_location"].startswith(f"{PREPARED_DIR_NAME}/A01 - ")
    assert "/" not in row["prepared_location"][len(PREPARED_DIR_NAME) + 1:]
    assert (engagement / row["prepared_location"]).is_file() and not target.exists()
    assert payload["state"]["moved"] == []
    # One inside a person's folder is offered none: WANDERED's "a person's
    # folder", above, is that half of the claim.


def test_restore_is_a_command_that_re_scans_and_the_moved_list_empties(
    capsys, demo_root, tmp_path,
):
    """The put-back is one command, and the request has its file back before
    the answer is printed: the filer re-scans inside it, so the status the
    app shows next is the one the copy earns."""
    from tracker.manifest import Status

    engagement, filed, target, state = a_moved_row(
        capsys, demo_root, tmp_path, WANDERED["the review folder"][0])
    [moved] = state["moved"]
    was_missing = {i["identifier"]: i["status"] for i in state["items"]}
    assert was_missing[filed["identifier"]] == Status.MISSING

    code, payload = run(capsys, "restore", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"original": moved["pbc_location"], "seq": moved["seq"]})

    assert code == 0, payload
    restored = payload["restored"]
    assert restored["moved_home"] and not restored["copied_from_original"]
    assert not restored["already_home"] and restored["parked_as"] == ""
    assert restored["decision"] == FILED and restored["scan_note"] == ""
    assert restored["prepared_location"] == filed["prepared_location"]
    assert not target.exists() and (engagement / filed["prepared_location"]).is_file()
    assert payload["state"]["moved"] == []
    now = {i["identifier"]: i["status"] for i in payload["state"]["items"]}
    assert now[filed["identifier"]] == Status.RECEIVED
    assert "restore" in api.vocab()["commands"]


def test_restore_refuses_without_a_seq_and_with_a_stale_one(capsys, demo_root, tmp_path):
    """Decision 112's rule over decision 110's command: the app is drawn from
    state and every row there carries its version, so a spec without one is a
    caller acting on no view, and an older one is a caller acting on a view
    the record has moved past."""
    from tracker.filer import STALE_ROW
    from tracker.index import FILE_MOVED

    engagement, filed, target, state = a_moved_row(
        capsys, demo_root, tmp_path, WANDERED["the review folder"][0])
    [moved] = state["moved"]

    code, payload = run(capsys, "restore", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"original": moved["pbc_location"]})
    assert code == 1 and payload["error"] == screen_words.NO_SEQ

    code, payload = run(capsys, "restore", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"original": moved["pbc_location"], "seq": filed["seq"]})
    assert code == 1
    assert payload["error"] == STALE_ROW.format(
        name=moved["original_name"], decision=FILE_MOVED,
        reason=[e for e in state["index"] if e["decision"] == FILE_MOVED][0]["reason"])
    assert target.is_file()                       # and nothing was touched


def test_the_renderer_types_none_of_the_moved_cards_words(capsys, demo_root):
    """Every word of decision 110's card is the API's - the three answers,
    the heading, the line under it and the word for a copy that is nowhere -
    and the page shows them without holding one of its own."""
    vocab = run(capsys, "list")[1]["vocab"]
    labels = vocab["review_labels"]
    assert labels["restore"] == screen_words.RESTORE_LABEL
    assert labels["keep"] == screen_words.KEEP_LABEL
    assert labels["send_to_review"] == screen_words.SEND_TO_REVIEW_LABEL
    assert labels["moved_heading"] == screen_words.MOVED_HEADING
    assert labels["moved_summary"] == screen_words.MOVED_SUMMARY
    assert labels["moved_nowhere"] == screen_words.MOVED_NOWHERE

    renderer = Path(__file__).resolve().parent.parent / "app" / "renderer"
    for rel in (*APP_SCRIPTS, "index.html"):
        text = (renderer / rel).read_text(encoding="utf-8")
        for word in (screen_words.RESTORE_LABEL, screen_words.KEEP_LABEL, screen_words.SEND_TO_REVIEW_LABEL,
                     screen_words.MOVED_HEADING, screen_words.MOVED_SUMMARY, screen_words.MOVED_NOWHERE):
            assert word not in text, (rel, word)


def test_the_moved_card_offers_mark_missing_on_a_row_whose_copy_and_original_are_both_gone(
    capsys, demo_root, tmp_path,
):
    """d157, ruling B6. A mislaid copy whose original is gone too has nothing
    to put back, keep or send to review, so the state says so (``gone``,
    with the row's own request) and the card offers the one answer left:
    **Mark ... missing**, the ``mark-missing`` command with the row's own
    identifier. Pressed, the row leaves the card, its request reads Missing
    and the next draft asks the client for it."""
    from tracker.layout import locate
    from tracker.reminder import draft_reminder

    engagement = sample_engagement(capsys, demo_root, tmp_path, "Form 1098 Mortgage Interest.pdf")
    code, payload = scan(capsys, engagement)
    assert code == 0, payload
    [filed] = [e for e in payload["state"]["index"] if e["decision"] == FILED]
    (engagement / filed["prepared_location"]).unlink()
    locate(engagement, filed["pbc_location"]).unlink()

    code, payload = scan(capsys, engagement)
    assert code == 0, payload
    [moved] = payload["state"]["moved"]
    assert moved["gone"] is True and moved["now"] is None
    assert moved["identifier"] == filed["identifier"]
    assert filed["identifier"] not in draft_reminder(engagement).asked

    code, payload = run(capsys, "mark-missing", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"original": moved["pbc_location"], "identifier": moved["identifier"],
                               "seq": moved["seq"]})

    assert code == 0, payload
    assert payload["marked_missing"]["identifier"] == filed["identifier"]
    assert payload["state"]["moved"] == []
    status = {i["identifier"]: i["status"] for i in payload["state"]["items"]}
    assert status[filed["identifier"]] == Status.MISSING
    assert filed["identifier"] in draft_reminder(engagement).asked

    # The card draws that answer, and only that answer, on such a row - with
    # the API's own label, wired to the same command as the filed list's.
    moved_row = js_function("movedRow")
    gone_branch = moved_row[moved_row.index("if (m.gone)"):moved_row.index("\n  }\n")]
    assert "vocab.review_labels.mark_missing" in gone_branch and "r-withdraw" in gone_branch
    assert "r-restore" not in gone_branch and "r-review" not in gone_branch and "r-keep" not in gone_branch
    assert "withdrawAnswer(" in js_block('$("sheet").addEventListener("click"')


# ------------------------------- statuses in a preparer's words (d200) ----


def test_the_vocabulary_carries_the_one_label_table(capsys, demo_root):
    from tracker.manifest import STATUS_LABELS

    vocab = run(capsys, "list")[1]["vocab"]
    assert vocab["labels"] == {word: {"key": api._slug(word), "label": shown.label,
                                      "sentence": shown.sentence}
                               for word, shown in STATUS_LABELS.items()}
    assert vocab["statuses"] == [{"value": status, "key": api._slug(status)} for status in Status.ALL]


def test_the_vocabulary_carries_the_three_sides(capsys, demo_root):
    from tracker import reminder

    vocab = run(capsys, "list")[1]["vocab"]
    assert vocab["reminder"]["sides"] == [
        {"key": "client", "label": "Client", "sentence": reminder.SIDE_CLIENT.sentence},
        {"key": "us", "label": "Us", "sentence": reminder.SIDE_US.sentence},
        {"key": "decide", "label": "Decide", "sentence": reminder.SIDE_DECIDE.sentence},
    ]


def _sided_engagement(capsys, demo_root):
    """A return with a Client row, an Us row, a Decide row and rows with no
    side: one in, one set aside, one nobody asked for."""
    from tests.builders import seed_statuses
    from tracker import reasons
    from tracker.manifest import Override, StatusUpdate

    spec = {"household": HOUSEHOLD, "return_name": "Sided", "items": [
        {"identifier": "A01", "document": "W-2 Wage Statements"},
        {"identifier": "B01", "document": "Receipts"},
        {"identifier": "C01", "document": "Form 1098 Mortgage Interest Statement"},
        {"identifier": "D01", "document": "Bank Statements"},
        {"identifier": "D02", "document": "Charitable Donations",
         "manual_override": Override.NOT_APPLICABLE, "period": "TY2025"},
        {"identifier": "D03", "document": "Tuition Statement", "asked": "no"},
    ]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    folder = where(demo_root, "Sided")
    seed_statuses(folder, {
        "A01": StatusUpdate(status=Status.MISSING),
        "B01": StatusUpdate(status=Status.FAILED, file_count=1,
                            validation_notes="scan.pdf: " + reasons.NO_TEXT_LAYER.format(),
                            note_codes=reasons.NO_TEXT_LAYER.code),
        "C01": StatusUpdate(status=Status.FAILED, file_count=1,
                            validation_notes="1099.pdf: " + reasons.WRONG_DOCUMENT.format(listed="'1098'"),
                            note_codes=reasons.WRONG_DOCUMENT.code),
        "D01": StatusUpdate(status=Status.RECEIVED, file_count=1),
    })
    return folder


def test_every_outstanding_row_in_the_state_carries_its_side_and_sentence(capsys, demo_root):
    from tracker import reminder
    from tracker.index import read_index
    from tracker.manifest import load_manifest

    folder = _sided_engagement(capsys, demo_root)
    items = {one["identifier"]: one for one in payload_of_state(capsys, folder)["items"]}
    placed = reminder.sides(*reminder.triage(load_manifest(folder), read_index(folder)))
    assert set(placed) == {"A01", "B01", "C01"}
    for identifier, one in items.items():
        side, sentence = placed.get(identifier, (None, ""))
        assert one["side"] == (side.key if side else None), identifier
        assert one["side_sentence"] == sentence, identifier
    assert {i: items[i]["side"] for i in ("A01", "B01", "C01")} == {
        "A01": "client", "B01": "us", "C01": "decide"}
    assert items["B01"]["status_key"] == Status.FAILED
    # The key is all the renderer reads; its label comes from vocab.labels.
    assert all("status_label" not in one for one in items.values())


def test_the_state_builder_triages_once(capsys, demo_root, monkeypatch):
    """The reminder card's held rows and every row's side come from one
    triage of the return's rows. The household card triages each return
    for its own panel (decision 125) and is not this return's state, so
    the calls are counted by who made them."""
    import inspect

    from tracker import reminder

    folder = _sided_engagement(capsys, demo_root)
    callers = []
    real = reminder.triage

    def counted(*args, **kwargs):
        callers.append(inspect.stack()[1].function)
        return real(*args, **kwargs)

    monkeypatch.setattr(reminder, "triage", counted)
    state = payload_of_state(capsys, folder)
    assert callers.count("state") == 1 and "_reminder_payload" not in callers
    assert [row["identifier"] for row in state["reminder"]["held"]] == ["C01"]


def test_the_words_188_and_204_added_are_still_in_the_vocabulary(capsys, demo_root):
    vocab = run(capsys, "list")[1]["vocab"]
    assert vocab["review_labels"]["file_where_it_waits"] == screen_words.FILE_WHERE_IT_WAITS_LABEL
    assert vocab["review_labels"]["handed_over"] == screen_words.HANDED_OVER_LINE
    assert vocab["household"]["accept_folder_name"] == screen_words.ACCEPT_FOLDER_NAME_LABEL
    assert vocab["household"]["accept_folder_name_help"] == screen_words.ACCEPT_FOLDER_NAME_HELP
    father, _ = two_households(capsys, demo_root)
    assert "waits_for" in waiting_document(capsys, father)


# ------------------------------- decision 201: an unnamed issuer's card ----


def _add_issuer(capsys, engagement, row, issuer="Dunmore Capital", **given):
    """The card's one button, as the app presses it: the row, its version,
    the list's version the card was drawn from and the typed name."""
    from tracker.manifest import list_head

    spec = {"original": row["pbc_location"], "seq": row["seq"], "head": list_head(engagement),
            "issuer": issuer, **given}
    return run(capsys, "add-issuer-and-file", api.ENGAGEMENT_FLAG, str(engagement), stdin=spec)


def _nothing_moved(engagement, before):
    """The list, the index and the journal exactly as ``before`` held them."""
    from tracker.manifest import recorded_rules

    assert recorded_rules(engagement) == before["rules"]
    assert read_index(engagement) == before["index"]
    assert len(ledger.read_events(engagement)) == before["events"]


def _as_it_stands(engagement):
    from tracker.manifest import recorded_rules

    return {"rules": recorded_rules(engagement), "index": read_index(engagement),
            "events": len(ledger.read_events(engagement))}


def test_a_card_parked_for_an_unnamed_issuer_offers_the_next_free_issuer_row(capsys, demo_root):
    from tracker import reasons

    engagement, row = _issuer_return(capsys, demo_root)
    assert row["code"] == reasons.ISSUER_NOT_NAMED.code
    [card] = api.state(engagement)["review"]
    assert card["issuer"] == {"identifier": "F03"}


def test_a_card_parked_for_any_other_reason_offers_no_issuer_box(capsys, demo_root):

    engagement, _ = _issuer_return(capsys, demo_root)

    text_pdf(inbox_of(engagement) / "notice.pdf", ["an agency notice nothing asks for"], style="padded")
    scan(capsys, engagement)
    cards = {card["original_name"]: card for card in api.state(engagement)["review"]}
    assert cards["notice.pdf"]["issuer"] is None
    assert cards["k-1 dunmore.pdf"]["issuer"] == {"identifier": "F03"}


def test_the_state_marks_which_rows_came_from_the_catalog(capsys, demo_root):
    """A custom row is one no catalog row of the return's form has
    (decision 201): the editor draws its Document with the plain boxes."""
    engagement, _ = _issuer_return(capsys, demo_root)
    marked = {item["identifier"]: item["catalog_row"] for item in api.state(engagement)["items"]}
    assert marked == {"F01": True, "F02": False}
    assert all("catalog_row" not in rule for rule in api.state(engagement)["rules"])


def test_adding_the_issuer_and_filing_is_one_command_writing_two_events_in_one_transaction(
        capsys, demo_root, monkeypatch):
    engagement, row = _issuer_return(capsys, demo_root)
    count = len(ledger.read_events(engagement))
    calls = []
    real = store.record

    def counting(conn, folder, *events):
        calls.append(tuple(e[ledger.EVENT_KEY] for e in events))
        return real(conn, folder, *events)

    monkeypatch.setattr(store, "record", counting)
    code, payload = _add_issuer(capsys, engagement, row)
    assert code == 0, payload
    assert calls[:2] == [(ledger.MOVING,), (ledger.ASSIGNED_BY_PERSON, ledger.RULES_CHANGED)]
    written = [e[ledger.EVENT_KEY] for e in ledger.read_events(engagement)[count:count + 3]]
    assert written == [ledger.MOVING, ledger.ASSIGNED_BY_PERSON, ledger.RULES_CHANGED]
    monkeypatch.undo()
    # The store's rules and index agree with the journal, rebuilt from it.
    from tracker.manifest import recorded_rules

    rules, index = recorded_rules(engagement), read_index(engagement)
    store.rebuild_engagement(store.connect(), demo_root, engagement)
    assert recorded_rules(engagement) == rules and read_index(engagement) == index
    [filed] = [e for e in index if e.original_name == "k-1 dunmore.pdf"]
    assert filed.decision == FILED and filed.identifier == "F03"


def test_a_locked_rescan_after_adding_the_issuer_is_said_by_its_class_never_its_text(
        capsys, demo_root, monkeypatch):
    """The restack review's N2: when the re-scan after the filing meets the
    lock, the reply says so in the vocabulary's sentence, by the error's
    class alone - never the exception's own text (principle 7)."""
    engagement, row = _issuer_return(capsys, demo_root)

    def locked(folder):
        raise api.ScanLockedError("held at C:/private/fabricated by host-x")

    monkeypatch.setattr(api, "scan_engagement", locked)
    code, payload = _add_issuer(capsys, engagement, row)
    assert code == 0, payload
    note = payload["added_and_filed"]["assigned"]["scan_note"]
    assert note == screen_words.ISSUER_NOT_RESCANNED
    assert "private" not in note
    assert api.vocab()["review_labels"]["issuer_not_rescanned"] == screen_words.ISSUER_NOT_RESCANNED


def test_the_reply_names_the_row_added_and_the_document_filed(capsys, demo_root):
    engagement, row = _issuer_return(capsys, demo_root)
    code, payload = _add_issuer(capsys, engagement, row, issuer="Dunmore Capital, L.P.")
    assert code == 0, payload
    done = payload["added_and_filed"]
    assert done["added"] == {"identifier": "F03", "document": "Schedule K-1 - Dunmore Capital LP"}
    assert done["assigned"]["identifier"] == "F03" and done["assigned"]["original_name"] == "k-1 dunmore.pdf"
    assert done["said"] == screen_words.ISSUER_ADDED_AND_FILED.format(
        identifier="F03", document="Schedule K-1 - Dunmore Capital LP", name="k-1 dunmore.pdf")
    assert "F03" in {rule["identifier"] for rule in payload["state"]["rules"]}


def test_the_new_issuer_row_asks_for_the_returns_year_not_the_catalogs(capsys, demo_root):
    later = BASE_YEAR + 1
    engagement, row = _issuer_return(capsys, demo_root, year=later)
    code, payload = _add_issuer(capsys, engagement, row)
    assert code == 0, payload
    [added] = [rule for rule in payload["state"]["rules"] if rule["identifier"] == "F03"]
    assert added["period"] == f"TY{later}"


def test_the_added_row_reads_back_in_the_editor_as_issuer_row_builds_it(capsys, demo_root):
    from tracker.records import rule_to_json
    from tracker.templates import issuer_item

    engagement, row = _issuer_return(capsys, demo_root)
    code, payload = _add_issuer(capsys, engagement, row)
    assert code == 0, payload
    rules = payload["state"]["rules"]
    [added] = [rule for rule in rules if rule["identifier"] == "F03"]
    built = rule_to_json(issuer_item("F03", "Dunmore Capital", BASE_YEAR))
    for column in ("document", "period", "required_keywords", "any_keywords", "named",
                   "short_title", "expected_count"):
        assert added[column] == built[column], column
    code, saved = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                      stdin={"items": rules, "engagement": {}})
    assert code == 0, saved
    assert saved["saved"]["recorded"] is False


def test_a_stale_card_adds_no_row_and_files_nothing(capsys, demo_root):
    engagement, row = _issuer_return(capsys, demo_root)
    before = _as_it_stands(engagement)
    code, payload = _add_issuer(capsys, engagement, row, seq=row["seq"] + 1)
    assert code == 1 and "is not as you saw it" in payload["error"]
    _nothing_moved(engagement, before)


def test_a_list_changed_since_the_card_was_drawn_adds_no_row_and_files_nothing(capsys, demo_root):
    from tracker.actions import ISSUER_LIST_MOVED

    engagement, row = _issuer_return(capsys, demo_root)
    before = _as_it_stands(engagement)
    code, payload = _add_issuer(capsys, engagement, row, head="0" * 64)
    assert code == 1 and payload["error"] == ISSUER_LIST_MOVED
    _nothing_moved(engagement, before)


def test_a_card_no_longer_waiting_for_an_issuer_is_refused(capsys, demo_root):
    from tracker.actions import NOT_AN_ISSUER_CARD

    engagement, _ = _issuer_return(capsys, demo_root)
    text_pdf(inbox_of(engagement) / "notice.pdf", ["an agency notice nothing asks for"], style="padded")
    scan(capsys, engagement)
    [notice] = [e for e in api.state(engagement)["index"] if e["original_name"] == "notice.pdf"]
    before = _as_it_stands(engagement)
    code, payload = _add_issuer(capsys, engagement, notice)
    assert code == 1 and payload["error"] == NOT_AN_ISSUER_CARD.format(name="notice.pdf")
    _nothing_moved(engagement, before)


def test_an_issuer_name_inside_another_is_refused_and_nothing_is_filed(capsys, demo_root):
    engagement, row = _issuer_return(capsys, demo_root)
    before = _as_it_stands(engagement)
    code, payload = _add_issuer(capsys, engagement, row, issuer="Ashford")
    assert code == 1 and "Rows F03 and F02 both narrow F01, and F03's name is inside F02's" in payload["error"]
    _nothing_moved(engagement, before)


def test_an_issuer_name_already_listed_is_refused_and_nothing_is_filed(capsys, demo_root):
    from tracker.manifest import ISSUER_NAMED_TWICE

    engagement, row = _issuer_return(capsys, demo_root)
    before = _as_it_stands(engagement)
    code, payload = _add_issuer(capsys, engagement, row, issuer="Ashford Holdings")
    assert code == 1
    assert payload["error"] == ISSUER_NAMED_TWICE.format(inner="F02", outer="F03", broad="F01",
                                                         name="Ashford Holdings")
    _nothing_moved(engagement, before)


def test_a_blank_issuer_name_is_refused_before_anything_is_read(capsys, demo_root, monkeypatch):
    engagement, row = _issuer_return(capsys, demo_root)
    before = _as_it_stands(engagement)

    def unread(*_args, **_kwargs):
        raise AssertionError("read before the name was checked")

    for name in ("load_engagement_info", "load_manifest", "read_index", "assign_review_file"):
        monkeypatch.setattr(api, name, unread)
    for name in ("load_engagement_info", "load_manifest", "read_index"):
        monkeypatch.setattr(firm_view, name, unread)
    monkeypatch.setattr(request_edit, "load_manifest", unread)
    code, payload = _add_issuer(capsys, engagement, row, issuer=" , . ")
    assert code == 1 and payload["error"] == "an issuer row needs the name of the entity that issued the K-1"
    monkeypatch.undo()
    _nothing_moved(engagement, before)


def test_an_issuer_that_is_not_text_is_refused_rather_than_made_a_name(capsys, demo_root):
    engagement, row = _issuer_return(capsys, demo_root)
    before = _as_it_stands(engagement)
    for sent in (["Dunmore Capital"], {"name": "Dunmore Capital"}, 7):
        code, payload = _add_issuer(capsys, engagement, row, issuer=sent)
        assert code == 1 and payload["error"] == screen_words.ISSUER_NOT_TEXT, sent
    _nothing_moved(engagement, before)


def test_an_issuer_row_that_would_not_narrow_this_returns_k1_row_is_refused(capsys, demo_root):
    """A return whose K-1 row is its own - no Any Keyword in common with the
    catalog's - has issuer rows copied from that row, in the editor: the
    catalog's issuer row would not be read as one of them."""
    from tracker.actions import ISSUER_DOES_NOT_NARROW

    own = [{"identifier": "F01", "document": "K-1 statements", "period": f"TY{BASE_YEAR}",
            "extensions": "pdf", "any_keywords": "k-1 statement"},
           {"identifier": "F02", "document": "K-1 statement - Ashford", "period": f"TY{BASE_YEAR}",
            "extensions": "pdf", "required_keywords": "Ashford Holdings", "any_keywords": "k-1 statement"}]
    engagement, row = _issuer_return(capsys, demo_root, items=own)
    before = _as_it_stands(engagement)
    code, payload = _add_issuer(capsys, engagement, row)
    assert code == 1
    assert payload["error"] == ISSUER_DOES_NOT_NARROW.format(identifier="F03", listed="F01, F02")
    _nothing_moved(engagement, before)


def test_an_editor_opened_before_the_issuer_was_added_is_refused_on_save(capsys, demo_root):
    from tracker.manifest import LIST_MOVED

    engagement, row = _issuer_return(capsys, demo_root)
    opened = api.state(engagement)
    code, payload = _add_issuer(capsys, engagement, row)
    assert code == 0, payload
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"items": opened["rules"], "engagement": {}, "head": opened["list_head"]})
    assert code == 1 and payload["error"] == LIST_MOVED
    assert "F03" in {rule["identifier"] for rule in api.state(engagement)["rules"]}


def _hold_a_twin(engagement):
    """F03, a second issuer row named Ashford Holdings beside F02, recorded
    as a list written before decision 201 could hold it."""
    from dataclasses import replace

    from tracker.locking import engagement_lock
    from tracker.manifest import validated
    from tracker.records import rule_to_json
    from tracker.templates import issuer_row, item_from_spec

    [twin] = validated([item_from_spec(issuer_row("F03", "Ashford Holdings"))])
    with engagement_lock(engagement):
        store.record(store.connect(), engagement, ledger.new(ledger.RULES_CHANGED, **{
            ledger.RULES_KEY: [rule_to_json(replace(twin, row=3))], ledger.REMOVED_KEY: [],
            ledger.INFO_KEY: {},
        }))


TWIN_SAID = {"inner": "F02", "outer": "F03", "broad": "F01", "name": "Ashford Holdings"}


def test_a_list_already_holding_one_issuer_name_twice_still_renames(capsys, demo_root):
    """Decision 201, the review's S1: a rename changes an identifier and
    never a name, so a same-name pair already on the list is not the
    rename's to refuse."""
    from tracker.manifest import list_head

    engagement, _ = _issuer_return(capsys, demo_root)
    _hold_a_twin(engagement)
    code, payload = run(capsys, "rename", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"from": "F03", "to": "F09", "head": list_head(engagement)})
    assert code == 0, payload
    assert [rule["identifier"] for rule in payload["state"]["rules"]] == ["F01", "F02", "F09"]


def test_the_issuer_card_files_a_new_issuer_on_a_list_already_holding_one_name_twice(
        capsys, demo_root):
    """Decision 201, the review's S1: the card checks the list with the list
    as the record holds it, so a pair already on it does not refuse a
    different issuer's row."""
    engagement, row = _issuer_return(capsys, demo_root)
    _hold_a_twin(engagement)
    code, payload = _add_issuer(capsys, engagement, row)
    assert code == 0, payload
    assert payload["added_and_filed"]["added"]["identifier"] == "F04"


def test_a_roll_of_a_list_already_holding_one_issuer_name_twice_carries_it_and_says_so(
        capsys, demo_root):
    """Decision 201, the review's S1: the pair rolls as it was, and the
    roll's reply carries the sentence - not left to the first later save."""
    from tracker.manifest import ISSUER_NAMED_TWICE

    engagement, _ = _issuer_return(capsys, demo_root)
    _hold_a_twin(engagement)
    code, payload = run(capsys, "rollover", stdin={"prior": str(engagement), "year": BASE_YEAR + 1})
    assert code == 0, payload
    assert payload["rollover"]["warnings"] == [ISSUER_NAMED_TWICE.format(**TWIN_SAID)]
    assert {"F02", "F03"} <= {rule["identifier"] for rule in payload["state"]["rules"]}


def test_an_edit_of_a_list_already_holding_one_issuer_name_twice_saves_and_warns(capsys, demo_root):
    """The orchestrator's ruling on R7 (decision 201): two issuer rows of
    one name already on the list do not lock a save of anything else, and
    the reply names both rows; a save naming a third row the same is
    refused."""
    from tracker.manifest import ISSUER_NAMED_TWICE, list_head

    engagement, _ = _issuer_return(capsys, demo_root)
    _hold_a_twin(engagement)
    rules = api.state(engagement)["rules"]
    rules[0] = {**rules[0], "expected_count": 2}
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"items": rules, "engagement": {}})
    assert code == 0, payload
    assert payload["saved"]["changed"] == ["F01"]
    assert payload["warnings"][0] == ISSUER_NAMED_TWICE.format(**TWIN_SAID)
    third = {**rules[1], "identifier": "F04"}
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"items": [*rules, third], "engagement": {}, "head": list_head(engagement)})
    assert code == 1 and "and F04 both narrow F01 with the same name" in payload["error"]


def test_the_vocabulary_carries_every_word_201_shows():
    words = api.vocab()
    assert words["dialogs"] == {"unsaved": "Unsaved Changes",
                                "keep_editing": "Keep Editing", "discard": "Discard My Changes"}
    editor = words["editor"]
    assert editor["plain_columns"] == ["expected_count", "asked", "manual_override", "override_reason",
                                       "short_title"]
    assert editor["routing_columns"] == ["identifier", "document", "period", "allowed_extensions",
                                         "min_size_kb", "required_keywords", "any_keywords",
                                         "date_pattern", "named"]
    # The fold and its two labels went with S5's one Advanced switch; nothing reads them.
    assert "routing" not in editor and "routing_all" not in editor and editor["advanced"] == "Advanced"
    assert editor["not_this_return"] == screen_words.EDITOR_NOT_THIS_RETURN
    assert editor["routing_help"] == ("How the app recognises this document when it arrives. A save "
                                      "checks these the same way whether the fold is open or not.")
    labels = words["review_labels"]
    assert labels["keyword"] == "Keyword to Learn (Optional)"
    assert labels["keyword_help"] == ("A word this document contains that others like it will too. "
                                      "Taught to the request so the next one files itself; the editor "
                                      "shows it beside the row.")
    assert labels["issuer_label"] == "Issuer Name"
    assert screen_words.ISSUER_LABEL is manifest.COL_ISSUER
    assert labels["issuer_help"] == ("Adds {identifier}, a K-1 row for this issuer, to the request list "
                                     "and files this document under it. Type the distinctive words and "
                                     "leave off the suffix (L.P., LLC).")
    assert labels["issuer_add"] == "Add Issuer"
    settings = words["settings"]
    assert (settings["firm_label"], settings["firm_help"], settings["root_label"]) == (
        "Firm Name", "as it should sign the reminders", "Clients Folder")
    assert "add-issuer-and-file" in words["commands"]
    # None of them is typed in the renderer.
    here = Path(__file__).resolve().parents[1]
    js = renderer_text(APP_SCRIPTS)
    html = (here / "app" / "renderer" / "index.html").read_text(encoding="utf-8")
    for word in (*words["dialogs"].values(), labels["keyword"],
                 labels["issuer_label"], labels["issuer_add"], settings["firm_label"],
                 settings["firm_help"]):
        assert word not in js and word not in html, word
    assert settings["root_label"] not in html


# ------------------------------------ every file name on the page is a live link (S8a) ----


def test_a_filed_documents_working_copy_has_a_key_the_shell_can_open_and_the_row_carries_no_path(
        capsys, demo_root, tmp_path):
    """A filed row names each working copy by a key in ``open_keys`` (one per
    request a page was filed under, in ``filed_names`` order); the path is
    only in ``paths``, which is the map the shell opens from (P63)."""
    engagement = sample_engagement(capsys, demo_root, tmp_path, "Form 1098 Mortgage Interest.pdf")
    code, payload = scan(capsys, engagement)
    assert code == 0, payload
    state = payload["state"]
    [filed] = [e for e in state["index"] if e["decision"] == FILED]

    assert len(filed["open_keys"]) == len(filed["filed_names"]) == 1
    [key] = filed["open_keys"]
    copy = Path(state["paths"][key])
    assert copy == engagement / filed["prepared_location"] and copy.is_file()
    assert copy.name == filed["filed_as"], "the name that is drawn is the name of the file that opens"
    assert screen_words.PATH_KINDS[key.split(" ", 1)[0]] == "reveal", "a filed copy is shown, never opened (F1)"
    # The reply puts no absolute path on a row the page draws; a key is a word and a row's handle.
    for field in ("open_keys", "filed_names", "filed_as"):
        assert not [s for s in _walk_strings(filed[field]) if str(engagement) in s or s.startswith("/")], field
    # A row that is not filed carries no filed-copy key.
    assert all(e["open_keys"] == [] for e in state["index"] if e["decision"] != FILED)


def test_a_page_filed_under_two_requests_has_its_open_keys_in_filed_names_order(
        capsys, demo_root, tmp_path):
    """Decision 94: the n-th key shows the n-th name's copy."""
    from tests.samples import scanned_1098_lines, scanned_w2_lines

    engagement = sample_engagement(capsys, demo_root, tmp_path, "no such sample")   # an empty inbox
    text_pdf(inbox_of(engagement) / "scan0003.pdf",
             "\n".join(scanned_w2_lines(2025) + scanned_1098_lines(2025) + [SAMPLE_PEOPLE[0]["name"]]
                       + [f"Line {n:03d} of the statement's fine print" for n in range(400)]))
    code, payload = scan(capsys, engagement)
    assert code == 0, payload
    [filed] = [e for e in payload["state"]["index"] if e["decision"] == FILED]
    assert len(filed["filed_names"]) == 2 and len(filed["open_keys"]) == 2
    names = [Path(payload["state"]["paths"][k]).name for k in filed["open_keys"]]
    assert names == filed["filed_names"]
    assert names[0] != names[1]
    assert [key.rsplit(" ", 1)[1] for key in filed["open_keys"]] == ["0", "1"], "copy n is key n"
    assert all(Path(payload["state"]["paths"][k]).is_file() for k in filed["open_keys"])


def test_a_moved_by_hand_copy_has_a_key_to_where_it_is_now_and_no_path_on_the_row(
        capsys, demo_root, tmp_path):
    engagement, filed, target, state = a_moved_row(
        capsys, demo_root, tmp_path, lambda eng, home: home.with_name("A01 - the 1098 I renamed.pdf"))
    [moved] = state["moved"]

    assert Path(state["paths"][moved["open_key"]]) == target and target.is_file()
    assert screen_words.PATH_KINDS[moved["open_key"].split(" ", 1)[0]] == "reveal"
    assert not [s for s in _walk_strings(moved["open_key"]) if str(engagement) in s]
    # The moved row's index entry is not a filed one, so it offers no second key for the same file.
    [index_row] = [e for e in state["index"] if e["decision"] == "File Moved"]
    assert index_row["open_keys"] == []


def test_a_moved_copy_whose_bytes_are_nowhere_has_no_key(capsys, demo_root, tmp_path):
    engagement, _filed, target, state = a_moved_row(
        capsys, demo_root, tmp_path, lambda eng, home: home.with_name("A01 - the 1098 I renamed.pdf"))
    [before] = state["moved"]
    assert before["open_key"].startswith("moved_copy ") and before["now"]
    target.unlink()                                  # now the bytes are nowhere
    code, payload = scan(capsys, engagement)
    assert code == 0, payload
    [moved] = payload["state"]["moved"]
    assert moved["now"] is None
    assert moved["open_key"] == ""
    assert not [key for key in payload["state"]["paths"] if key.startswith("moved_copy")]


def test_a_set_aside_file_and_a_parked_document_are_shown_but_a_zip_or_email_is_plain_text(
        capsys, demo_root, tmp_path):
    """F2, and ruling 24: every file name is a link (SPEC 3.9) except a
    container. A row that must not open still carries a reveal-only
    ``shown_key``; a program has no copy and no key; an email or a zip has a
    working copy but no key at all, on ``state`` and on ``firm`` alike,
    because one more click on a revealed container would open it (decision
    190)."""
    engagement = sample_engagement(capsys, demo_root, tmp_path, "vacation photo.bmp")
    (inbox_of(engagement) / "letters.zip").write_bytes(b"PK\x03\x04 not really a zip")
    (inbox_of(engagement) / "setup.exe").write_bytes(b"MZ")
    code, payload = scan(capsys, engagement)
    assert code == 0, payload
    rows = {e["original_name"]: e for e in payload["state"]["index"]}
    [photo] = [e for e in rows.values() if e["original_name"] == "vacation photo.bmp"]
    code, payload = run(capsys, "dismiss", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"original": photo["pbc_location"], "note": "a holiday snap",
                               "seq": photo.get("seq")})
    assert code == 0, payload
    state = payload["state"]
    rows = {e["original_name"]: e for e in state["index"]}
    assert rows["vacation photo.bmp"]["decision"] == api.NOT_REQUESTED
    row = rows["vacation photo.bmp"]
    assert row["open_key"] == ""
    key = row["shown_key"]
    assert key.startswith("shown_copy ") and screen_words.PATH_KINDS["shown_copy"] == "reveal"
    assert Path(state["paths"][key]) == engagement / row["prepared_location"]
    assert Path(state["paths"][key]).is_file()
    assert not [s for s in _walk_strings(key) if str(engagement) in s]
    zipped = rows["letters.zip"]
    assert zipped["prepared_location"] and zipped["bucket"] == firm_view.BUCKET_CONTAINER
    assert zipped["open_key"] == "" and zipped["shown_key"] == "", "an email or a zip is plain text"
    assert rows["setup.exe"]["shown_key"] == "" and not rows["setup.exe"]["prepared_location"]
    assert not [k for k in state["paths"] if k.startswith("shown_copy") and "setup" in state["paths"][k]]
    assert not [p for p in state["paths"].values() if p.endswith("letters.zip") or "letters" in Path(p).name]
    # The firm's Needs Review file for the zip has no key and no path either.
    code, firm = run(capsys, "firm")
    assert code == 0, firm
    [file] = [f for f in firm["files"] if "letters" in f["name"]]
    assert file["open_key"] == ""
    assert not [p for p in firm["paths"].values() if "letters" in Path(p).name]
    # A filed row carries no shown key (its copies are open_keys).
    assert all("shown_key" not in e for e in state["index"] if e["decision"] == FILED)


def test_a_parked_pdfs_shown_key_is_its_open_key_so_no_path_is_named_twice(capsys, demo_root, tmp_path):
    """Review 2, F1: the shell's allow-list is keyed by path, so a copy named
    under both a ``review_copy`` and a ``shown_copy`` key would have the
    reveal-only kind overwrite the one that opens."""
    state, parked = _parked_read_pdf_state(capsys, demo_root, tmp_path)
    assert parked["shown_key"] == parked["open_key"]
    kinds_of = {}
    for key, path in state["paths"].items():
        kinds_of.setdefault(path, set()).add(screen_words.PATH_KINDS.get(key.split(" ", 1)[0]))
    assert all(len(kinds) == 1 for kinds in kinds_of.values()), kinds_of
    paths = list(state["paths"].values())
    assert len(paths) == len(set(paths)), "one key per path"


def test_a_real_state_paths_still_opens_a_parked_pdfs_review_copy_through_the_shell(
        capsys, demo_root, tmp_path):
    """Review 2, F1 end to end: the real reply's ``paths`` (in its own order)
    and the API's kinds through the real ``app/main.js`` - the card's plain
    Open opens the review copy, and reveal still shows it."""
    from tests.node_harness import run_menu

    state, parked = _parked_read_pdf_state(capsys, demo_root, tmp_path)
    review = state["paths"][parked["open_key"]]
    [zip_like] = [e for e in state["index"] if e["original_name"] == "Mortgage Notes.docx"]
    shown = state["paths"][zip_like["shown_key"]]
    scenario = {"pathKinds": screen_words.PATH_KINDS, "paths": state["paths"]}
    steps = [{"tracker": ["list"]}, {"open": [review]}, {"open": [review, "reveal"]},
             {"open": [shown]}, {"open": [shown, "reveal"]}]
    ran = run_menu(tmp_path, steps, **scenario)
    assert ran["opened"] == [review], "a plain open of the review copy opens it"
    assert ran["revealed"] == [review, shown]
    assert ran["answers"] == ["", "", "Not Opened; It Has Changed", ""]


def test_no_return_or_household_row_carries_an_open_key_and_their_words_navigate(
        capsys, demo_root, tmp_path, monkeypatch):
    """Household and return names navigate inside the app (S8a ruling), so
    neither their rows nor the list carry a key for opening a folder."""
    engagement = sample_engagement(capsys, demo_root, tmp_path, "Form 1098 Mortgage Interest.pdf")
    code, listed = run(capsys, "list")
    assert code == 0, listed
    assert listed["households"]
    for household in listed["households"]:
        assert "open_key" not in household
        assert all("open_key" not in one for one in household["returns"])
    assert all("open_key" not in one for one in listed["engagements"])
    assert not [key for key in listed["paths"] if " " in key]
    code, state = run(capsys, "state", api.ENGAGEMENT_FLAG, str(engagement))
    assert code == 0, state
    assert all("open_key" not in one for one in state["household"]["returns"])
    from tracker import settings

    monkeypatch.setattr(settings, "host_system", lambda: "posix")   # a Mac says Finder (R11)
    screen = api.vocab()["screen"]
    assert screen["navigate_client"] == "Navigate to Household"
    assert screen["navigate_return"] == "Navigate to Return"
    assert screen["show_in_explorer"] == "Show in File Explorer"


def test_the_short_reason_and_the_section_words_are_capitalised_as_jason_asked():
    assert reasons.SHORT_REASONS["unmatched"] == "Could Not Sort"
    assert screen_words.MENU["needs_review"] == "Needs Review"
    assert api.vocab()["screen"]["sections"]["needs_review"] == "Needs Review"
    assert api.vocab()["screen"]["empty"]["needs_review"] == "Nothing Needs Review"
