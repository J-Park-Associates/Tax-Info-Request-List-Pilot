"""Tests for tracker/containers.py, and the pass that opens what it reads -
an email or a zip is opened, and each attachment filed (decision 143).

The claims: a container a client drops is moved whole and kept untouched
like any original, and recorded ``Opened``; each attachment is taken out
into the household-year's hidden folder in the private tree - never the
client's - and sorted as a document of its own, its row naming the
container; nothing inside is ever run; a locked, damaged, empty or
oversized container parks with the sentence that says which; a name inside
cannot leave its folder; an attachment never files into another household;
a dry run writes nothing; and a pass killed half way ends, on the next
pass, with each attachment once.

The fixtures are built here from nothing - the ``.msg`` by the suite's own
compound-file writer (``tests.samples.cfb_bytes``), the ``.eml`` by the
standard library, the zip by ``zipfile`` - so no client's mail enters the
repository.
"""

from __future__ import annotations

import io
import tempfile
import zipfile
from email.message import EmailMessage
from pathlib import Path

import pytest

from tests.conftest import TEST_CLIENT, make_engagement, named_page, sort, sort_all
from tests.samples import msg_bytes
from tests.test_filer import (
    BUSINESS,
    DAY1,
    DAY2,
    FATHER,
    ITEMS,
    LLC_PEOPLE,
    feeding,
    original_at,
)
from tests.test_scanner import text_pdf
from tracker import containers, filer, ledger, reasons, store
from tracker.containers import (
    LIMIT_COUNT,
    LIMIT_DEPTH,
    LIMIT_RATIO,
    LIMIT_TOTAL,
    MAX_ATTACHMENTS,
    SKIP_BODY,
    SKIP_INLINE,
    NotOpened,
    open_container,
    safe_name,
)
from tracker.filer import (
    DUPLICATE,
    DUPLICATE_OF_OPENED,
    FILED,
    NEEDS_REVIEW,
    OPENED,
    FilingError,
    read_index,
    received_for,
    refresh_household_readme,
)
from tracker.layout import (
    INBOX_DIR_NAME,
    MAX_PATH_LENGTH,
    OPENED_DIR_NAME,
    README_NAME,
    client_household_dir,
    inbox_of,
    locate,
    location_of,
    opened_dir_of,
    originals_of,
    private_household_dir,
    root_of,
)
from tracker.records import Feed

W2 = "Form W-2 Wage and Tax Statement 2025"
FORM_1098 = "Form 1098 Mortgage Interest Statement 2025"


@pytest.fixture
def engagement(tmp_path):
    return make_engagement(tmp_path, ITEMS)


# ------------------------------------------------------------- the fixtures ----


def pdf(text: str, who: str = TEST_CLIENT) -> bytes:
    """A real PDF's bytes whose page says ``text`` and names ``who``."""
    with tempfile.TemporaryDirectory() as scratch:
        return text_pdf(Path(scratch) / "page.pdf", named_page(text, who) if who else text).read_bytes()


def eml(attachments, *, inline=(), body: str = "Here are my documents.") -> bytes:
    """An email as Outlook or Gmail saves one: a text body, the attachments
    (each carrying a Content-ID, as real ones do) and any inline pictures."""
    message = EmailMessage()
    message["Subject"] = "documents"
    message["From"] = "client@example.com"
    message["To"] = "firm@example.com"
    message.set_content(body)
    for n, (name, data) in enumerate(attachments):
        maintype, subtype = ("application", "pdf") if name.endswith(".pdf") else ("application", "octet-stream")
        message.add_attachment(data, maintype=maintype, subtype=subtype, filename=name,
                               cid=f"<part{n}@example.com>")
    for name, data in inline:
        message.add_attachment(data, maintype="image", subtype="png", filename=name,
                               disposition="inline", cid=f"<{name}@example.com>")
    return message.as_bytes()


def a_zip(members, *, method=zipfile.ZIP_DEFLATED) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", method) as archive:
        for name, data in members:
            archive.writestr(name, data)
    return buffer.getvalue()


def container_of(kind: str, attachments) -> bytes:
    if kind == "eml":
        return eml(attachments)
    if kind == "zip":
        return a_zip(attachments)
    return msg_bytes([{"name": name, "data": data} for name, data in attachments])


def drop_bytes(engagement, name: str, data: bytes) -> Path:
    path = inbox_of(engagement) / name
    path.write_bytes(data)
    return path


def opened_events(engagement) -> list[dict]:
    return [e for e in ledger.read_events(engagement) if e[ledger.EVENT_KEY] == ledger.OPENED]


def files_under(folder: Path) -> list[str]:
    return sorted(p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file())


# ----------------------------------------------------------- claims 1 and 2 ----


def test_an_email_with_two_pdfs_is_opened_and_each_is_filed_where_it_belongs(engagement):
    drop_bytes(engagement, "Fwd documents.eml", eml([("w2.pdf", pdf(W2)), ("1098.pdf", pdf(FORM_1098))]))

    done = sort(engagement, today=DAY1)

    rows = read_index(engagement)
    [box] = [row for row in rows if row.decision == OPENED]
    assert box.pbc_location == original_at(engagement, "Fwd documents.eml")
    assert box.identifier == "" and box.prepared_location == "" and box.container == ""
    assert box.reason.startswith("opened: 2 documents")
    assert done.opened == [box]
    filed = {row.identifier: row for row in rows if row.decision == FILED}
    assert set(filed) == {"A01", "C01"}
    for row in filed.values():
        assert row.container == box.pbc_location
        assert locate(engagement, row.pbc_location).parent.parent == opened_dir_of(engagement)
        assert (engagement / row.prepared_location).is_file()
    assert filed["A01"].original_name == "w2.pdf" and filed["C01"].original_name == "1098.pdf"
    # The client's README lists both under their requests.
    labels = {item.identifier: item.label for item in ITEMS}
    received = received_for([engagement])
    assert sorted(line.identifier for line in received.lines) == ["A01", "C01"]
    readme = refresh_household_readme(private_household_dir(root_of(engagement), "Test Household"))
    text = readme.read_text(encoding="utf-8") if readme else (
        inbox_of(engagement) / README_NAME).read_text(encoding="utf-8")
    assert labels["A01"] in text and labels["C01"] in text


@pytest.mark.parametrize("kind", ["msg", "zip"])
def test_the_same_for_a_msg_and_a_zip(engagement, kind):
    box_bytes = container_of(kind, [("w2.pdf", pdf(W2)), ("1098.pdf", pdf(FORM_1098))])
    drop_bytes(engagement, f"forwarded.{kind}", box_bytes)

    sort(engagement, today=DAY1)

    rows = read_index(engagement)
    [box] = [row for row in rows if row.decision == OPENED]
    assert box.pbc_location == original_at(engagement, f"forwarded.{kind}")
    assert sorted((row.identifier, row.container) for row in rows if row.decision == FILED) == [
        ("A01", box.pbc_location), ("C01", box.pbc_location)]
    # The container itself rests in the client's folder for the year, untouched.
    assert (originals_of(engagement) / f"forwarded.{kind}").read_bytes() == box_bytes


def test_a_zip_in_a_subfolder_of_the_drop_is_flattened_and_only_its_own_row_names_the_subfolder(engagement):
    """Decision 147, ruling 6: a container in a subfolder is moved like any
    drop - into the year's folder under its own name - and then opened.
    The container is what came out of the subfolder, so its row says so;
    what came out of the container did not, and its rows do not."""
    nested = inbox_of(engagement) / "From the bank"
    nested.mkdir()
    (nested / "docs.zip").write_bytes(a_zip([("w2.pdf", pdf(W2)), ("1098.pdf", pdf(FORM_1098))]))

    sort(engagement, today=DAY1)

    rows = read_index(engagement)
    [box] = [row for row in rows if row.decision == OPENED]
    assert box.pbc_location == original_at(engagement, "docs.zip")
    # Its own column since decision 190, never a clause of the Reason.
    assert box.subfolder == "From the bank" and "From the bank" not in box.reason
    filed = [row for row in rows if row.decision == FILED]
    assert len(filed) == 2
    assert all(row.subfolder == "" for row in filed)
    assert not nested.exists()


# ------------------------------------------------------------------ claim 3 ----


def test_an_attachment_already_sent_loose_is_a_duplicate(engagement):
    w2 = pdf(W2)
    drop_bytes(engagement, "w2.pdf", w2)
    sort(engagement, today=DAY1)
    drop_bytes(engagement, "mail.eml", eml([("W2 again.pdf", w2), ("1098.pdf", pdf(FORM_1098))]))

    sort(engagement, today=DAY2)

    rows = read_index(engagement)
    [again] = [row for row in rows if row.original_name == "W2 again.pdf"]
    assert again.decision == DUPLICATE and again.container == original_at(engagement, "mail.eml")
    assert [row.identifier for row in rows if row.decision == FILED] == ["A01", "C01"]


def test_a_re_sent_identical_email_is_not_opened_again(engagement):
    mail = eml([("w2.pdf", pdf(W2)), ("1098.pdf", pdf(FORM_1098))])
    drop_bytes(engagement, "mail.eml", mail)
    sort(engagement, today=DAY1)
    taken = files_under(opened_dir_of(engagement))
    drop_bytes(engagement, "mail.eml", mail)

    sort(engagement, today=DAY2)

    rows = read_index(engagement)
    [again] = [row for row in rows if row.pbc_location == original_at(engagement, "mail (2).eml")]
    assert again.decision == DUPLICATE
    assert again.reason == DUPLICATE_OF_OPENED.format(name="mail.eml")
    assert files_under(opened_dir_of(engagement)) == taken
    assert len([row for row in rows if row.container]) == 2


# ------------------------------------------------------------------ claim 4 ----


class Killed(BaseException):
    """The process dying: nothing after it runs, not even the record."""


def test_a_pass_killed_after_writing_attachments_opens_again_and_reuses_them(engagement, monkeypatch):
    mail = eml([("w2.pdf", pdf(W2)), ("1098.pdf", pdf(FORM_1098)), ("notes.pdf", pdf("some notes"))])
    drop_bytes(engagement, "mail.eml", mail)
    real = filer._decide_attachment
    calls = []

    def dies_on_the_second(*args, **kwargs):
        calls.append(1)
        if len(calls) == 2:
            raise Killed
        return real(*args, **kwargs)

    # A kill records nothing at the end: the batch record never runs. Only
    # the intent the first attachment's filing wrote before its copy is in
    # the journal.
    monkeypatch.setattr(filer, "_decide_attachment", dies_on_the_second)
    monkeypatch.setattr(filer, "_record", lambda *a, **k: None)
    with pytest.raises(Killed):
        sort(engagement, today=DAY1)
    monkeypatch.undo()
    assert read_index(engagement) == []
    written = files_under(opened_dir_of(engagement))
    assert len(written) == 3

    sort(engagement, today=DAY2)

    rows = read_index(engagement)
    assert files_under(opened_dir_of(engagement)) == written       # reused, not written twice
    attachment_rows = [row for row in rows if row.container]
    assert sorted(row.original_name for row in attachment_rows) == ["1098.pdf", "notes.pdf", "w2.pdf"]
    assert len({row.pbc_location for row in attachment_rows}) == 3
    assert [row.decision for row in rows].count(OPENED) == 1
    # The first attachment's row was finished from its intent, dated the
    # day it was decided (decision 119).
    [w2] = [row for row in attachment_rows if row.original_name == "w2.pdf"]
    assert w2.decision == FILED and w2.received == DAY1.isoformat()
    assert store.open_intents(store.connect(), engagement) == []


def test_an_attachment_the_reader_could_not_start_on_waits_and_so_does_its_container(
        engagement, monkeypatch):
    """Decision 150 over 143, found by the restack onto 150. An attachment
    is read as a drop is - in 150's child - and one whose reader could not
    start is the machine's fault, so it gets no row. Nor does its
    container: a recorded container is known by its bytes and never opened
    again, which would leave the attachment unread for ever. Pass 1 files
    the W-2, records neither the 1098 nor the email, and says nothing is
    unaccounted; pass 2 reopens the email as a stray, reuses both files,
    skips the W-2 and files the 1098."""
    import tracker.content_check as content_check

    drop_bytes(engagement, "mail.eml", eml([("w2.pdf", pdf(W2)), ("1098.pdf", pdf(FORM_1098))]))
    real = filer.read_once

    def cannot_start_on_the_1098(path, questions):
        if path.name == "1098.pdf":
            return content_check.unjudged(content_check.could_not_start(0.0, "no more processes", path.name))
        return real(path, questions)

    monkeypatch.setattr(filer, "read_once", cannot_start_on_the_1098)
    content_check.readers_that_could_not_start()
    first = sort(engagement, today=DAY1)
    monkeypatch.undo()

    [w2] = read_index(engagement)
    assert w2.original_name == "w2.pdf" and w2.decision == FILED
    assert w2.container == original_at(engagement, "mail.eml")
    assert first.opened == [] and opened_events(engagement) == []
    assert first.attention == []                      # waiting, not unaccounted
    assert content_check.readers_that_could_not_start() == ["1098.pdf"]
    written = files_under(opened_dir_of(engagement))
    assert len(written) == 2

    second = sort(engagement, today=DAY2)

    rows = read_index(engagement)
    assert files_under(opened_dir_of(engagement)) == written       # reused, not written twice
    [box] = [row for row in rows if row.decision == OPENED]
    assert box.pbc_location == w2.container and second.opened == [box]
    assert sorted((row.original_name, row.identifier) for row in rows if row.container) == [
        ("1098.pdf", "C01"), ("w2.pdf", "A01")]
    assert [row for row in rows if row.original_name == "w2.pdf"] == [w2]
    assert second.attention == []


# ------------------------------------------------------------------ claim 5 ----


def test_nothing_is_ever_written_into_the_client_tree(engagement):
    drop_bytes(engagement, "mail.zip", a_zip([("w2.pdf", pdf(W2)), ("sub/1098.pdf", pdf(FORM_1098))]))

    sort(engagement, today=DAY1)

    client_side = client_household_dir(root_of(engagement), "Test Household")
    assert files_under(client_side) == sorted([f"{INBOX_DIR_NAME}/{README_NAME}", "2025/mail.zip"])
    assert len(files_under(opened_dir_of(engagement))) == 2
    assert opened_dir_of(engagement).name == OPENED_DIR_NAME
    assert opened_dir_of(engagement).parent == engagement.parent


# ------------------------------------------------------------------ claim 6 ----


def test_inline_images_and_bodies_are_skipped_and_named_in_the_opened_event(engagement):
    drop_bytes(engagement, "mail.eml", eml([("w2.pdf", pdf(W2))], inline=[("logo.png", b"\x89PNG" + b"0" * 200)]))
    drop_bytes(engagement, "mail.msg", msg_bytes([
        {"name": "1098.pdf", "data": pdf(FORM_1098)},
        {"name": "signature.jpg", "data": b"jpeg" * 100, "hidden": True},
        {"name": "banner.gif", "data": b"gif" * 100, "flags": 4},
        {"name": "link.pdf", "method": 2},
    ]))

    sort(engagement, today=DAY1)

    events = {e[ledger.KEY_KEY].rsplit("/", 1)[-1]: e for e in opened_events(engagement)}
    by_mail = {(one["name"], one["why"]) for one in events["mail.eml"][ledger.SKIPPED_KEY]}
    assert ("logo.png", SKIP_INLINE) in by_mail
    assert ("text/plain", SKIP_BODY) in by_mail
    assert [one["name"] for one in events["mail.eml"][ledger.ATTACHMENTS_KEY]] == ["w2.pdf"]
    by_msg = {(one["name"], one["why"]) for one in events["mail.msg"][ledger.SKIPPED_KEY]}
    assert by_msg == {("signature.jpg", SKIP_INLINE), ("banner.gif", SKIP_INLINE),
                      ("link.pdf", containers.SKIP_REFERENCE)}
    [taken] = events["mail.msg"][ledger.ATTACHMENTS_KEY]
    assert taken["name"] == "1098.pdf" and taken["size"] == len(pdf(FORM_1098)) and taken["digest"]
    # Nothing skipped was ever written out.
    assert sorted(Path(one).name for one in files_under(opened_dir_of(engagement))) == ["1098.pdf", "w2.pdf"]


# ------------------------------------------------------------------ claim 7 ----


def test_limits_depth():
    """An email holding a zip is opened through; a zip inside that zip is
    not, and parks as a container of its own with the limit named."""
    deepest = a_zip([("k1.pdf", b"%PDF k1")])
    middle = a_zip([("w2.pdf", b"%PDF w2"), ("deeper.zip", deepest)])
    opened = open_container(eml([("middle.zip", middle)]), "eml")
    assert [(one.name, bool(one.parks)) for one in opened.attachments] == [
        ("w2.pdf", False), ("deeper.zip", True)]
    assert LIMIT_DEPTH in opened.attachments[1].parks
    assert opened.attachments[1].code == reasons.CONTAINER_LIMIT.code
    # At the edge: depth 2 opens.
    assert [one.name for one in open_container(eml([("m.zip", deepest)]), "eml").attachments] == ["k1.pdf"]
    # An embedded message past the depth has no bytes to hand back: it
    # stops the whole container.
    too_deep = msg_bytes([{"method": 5, "name": "fwd", "attachments": [
        {"method": 5, "name": "fwd2", "attachments": [{"name": "x.pdf", "data": b"x"}]}]}])
    with pytest.raises(NotOpened, match=LIMIT_DEPTH):
        open_container(too_deep, "msg")


def test_limits_count():
    at_the_edge = a_zip([(f"{n}.pdf", b"%PDF") for n in range(MAX_ATTACHMENTS)])
    assert len(open_container(at_the_edge, "zip").attachments) == MAX_ATTACHMENTS
    past = a_zip([(f"{n}.pdf", b"%PDF") for n in range(MAX_ATTACHMENTS + 1)])
    with pytest.raises(NotOpened, match=LIMIT_COUNT):
        open_container(past, "zip")


def test_limits_total_bytes(monkeypatch):
    """Counted from the bytes actually produced: two stored members of 600
    bytes are 1200 produced, whatever the directory says."""
    two = a_zip([("a.pdf", b"a" * 600), ("b.pdf", b"b" * 600)], method=zipfile.ZIP_STORED)
    monkeypatch.setattr(containers, "MAX_TOTAL_BYTES", 1200)
    assert len(open_container(two, "zip").attachments) == 2
    monkeypatch.setattr(containers, "MAX_TOTAL_BYTES", 1199)
    with pytest.raises(NotOpened, match=LIMIT_TOTAL):
        open_container(two, "zip")


def test_limits_total_bytes_ignores_what_the_directory_declares(monkeypatch):
    """A zip bomb that lies in its directory: the member's declared size is
    tiny, and the counting read stops it at the limit all the same."""
    payload = b"\0" * 50_000
    data = bytearray(a_zip([("bomb.pdf", payload)]))
    # Rewrite the declared uncompressed size (local header and central
    # directory) to 10 bytes.
    local = data.find(b"PK\x03\x04")
    data[local + 22:local + 26] = (10).to_bytes(4, "little")
    central = data.find(b"PK\x01\x02")
    data[central + 24:central + 28] = (10).to_bytes(4, "little")
    monkeypatch.setattr(containers, "MAX_RATIO", 10**9)
    monkeypatch.setattr(containers, "MAX_TOTAL_BYTES", 20_000)
    with pytest.raises(NotOpened) as raised:
        open_container(bytes(data), "zip")
    assert LIMIT_TOTAL in raised.value.sentence or "could not be opened" in raised.value.sentence


def test_limits_ratio(monkeypatch):
    """A crafted zip bomb: a megabyte of zeros deflates to about a
    kilobyte, far past a hundred times its packed size."""
    bomb = a_zip([("bomb.pdf", b"\0" * 1_000_000)])
    with pytest.raises(NotOpened, match=LIMIT_RATIO):
        open_container(bomb, "zip")
    # At its edge: the member's own ratio passes, one below does not.
    info = zipfile.ZipFile(io.BytesIO(bomb)).infolist()[0]
    ratio = -(-info.file_size // info.compress_size)
    monkeypatch.setattr(containers, "MAX_RATIO", ratio)
    assert len(open_container(bomb, "zip").attachments) == 1
    monkeypatch.setattr(containers, "MAX_RATIO", ratio - 1)
    with pytest.raises(NotOpened, match=LIMIT_RATIO):
        open_container(bomb, "zip")


def test_limits_park_the_container_with_the_limit_in_the_sentence(engagement):
    drop_bytes(engagement, "bomb.zip", a_zip([("bomb.pdf", b"\0" * 1_000_000)]))

    done = sort(engagement, today=DAY1)

    [row] = read_index(engagement)
    assert row.decision == NEEDS_REVIEW and LIMIT_RATIO in row.reason
    assert row.code == reasons.CONTAINER_LIMIT.code
    assert done.opened == [] and not opened_dir_of(engagement).exists()


# ------------------------------------------------------------------ claim 8 ----


def locked_zip() -> bytes:
    """A zip whose member carries the encryption flag, in both of the
    headers that say it (``zipfile`` will not write the flag itself)."""
    data = bytearray(a_zip([("w2.pdf", b"%PDF " * 100)]))
    for signature, at in ((b"PK\x03\x04", 6), (b"PK\x01\x02", 8)):
        where = data.find(signature)
        data[where + at] |= 0x1
    return bytes(data)


@pytest.mark.parametrize("name, data, reason", [
    ("locked.zip", None, reasons.CONTAINER_LOCKED),
    ("broken.zip", b"PK\x03\x04 not really a zip at all" * 10, reasons.CONTAINER_DAMAGED),
    ("broken.msg", b"\xd0\xcf\x11\xe0 not a compound file" * 100, reasons.CONTAINER_DAMAGED),
    ("empty.eml", b"", reasons.CONTAINER_DAMAGED),
])
def test_an_encrypted_or_damaged_container_parks(engagement, name, data, reason):
    drop_bytes(engagement, name, locked_zip() if data is None else data)

    sort(engagement, today=DAY1)

    [row] = read_index(engagement)
    assert row.decision == NEEDS_REVIEW and row.code == reason.code
    assert row.prepared_location           # a review copy of the container, for a person
    assert not opened_dir_of(engagement).exists()


def test_an_unsupported_compression_is_said_as_password_protected(monkeypatch):
    data = bytearray(a_zip([("w2.pdf", b"%PDF " * 100)]))
    for signature, at in ((b"PK\x03\x04", 8), (b"PK\x01\x02", 10)):
        where = data.find(signature)
        data[where + at:where + at + 2] = (99).to_bytes(2, "little")      # AES
    with pytest.raises(NotOpened) as raised:
        open_container(bytes(data), "zip")
    assert raised.value.code == reasons.CONTAINER_LOCKED.code


def test_an_email_with_nothing_attached_parks(engagement):
    drop_bytes(engagement, "hello.msg", msg_bytes([]))
    drop_bytes(engagement, "hello.eml", eml([], inline=[("logo.png", b"\x89PNG" + b"0" * 64)]))

    sort(engagement, today=DAY1)

    rows = read_index(engagement)
    assert len(rows) == 2
    for row in rows:
        assert row.decision == NEEDS_REVIEW
        assert row.reason == "an email with nothing attached; read it here"
        assert row.code == reasons.CONTAINER_EMPTY.code and reasons.CONTAINER_EMPTY.firm_side


# ------------------------------------------------------------------ claim 9 ----


@pytest.mark.parametrize("raw, expected", [
    ("../../evil.pdf", "evil.pdf"),
    ("..\\..\\evil.pdf", "evil.pdf"),
    ("C:\\Windows\\evil.pdf", "evil.pdf"),
    ("C:evil.pdf", "C_evil.pdf"),
    ("\\\\server\\share\\evil.pdf", "evil.pdf"),
    ("/etc/passwd", "passwd"),
    ("CON.pdf", "attachment.pdf"),
    ("nul", "attachment"),
    ("..", "attachment"),
    ("", "attachment"),
    ("tab\there.pdf", "tab_here.pdf"),
    ("trailing dot. ", "trailing dot"),
])
def test_an_attachment_name_cannot_leave_its_folder(raw, expected):
    assert safe_name(raw, "attachment") == expected


def test_an_attachment_name_cannot_leave_its_folder_on_disk(engagement):
    long_name = "L" * 300 + ".pdf"
    drop_bytes(engagement, "names.zip", a_zip([
        ("../../../../outside.pdf", b"%PDF one" * 1000),
        ("C:\\Windows\\win.pdf", b"%PDF two" * 1000),
        ("\\\\server\\share\\unc.pdf", b"%PDF three" * 1000),
        ("CON.pdf", b"%PDF four" * 1000),
        (long_name, b"%PDF five" * 1000),
        ("same.pdf", b"%PDF six" * 1000),
        ("dir/same.pdf", b"%PDF seven" * 1000),
    ], method=zipfile.ZIP_STORED))

    sort(engagement, today=DAY1)

    root = root_of(engagement)
    folder = opened_dir_of(engagement) / "names"
    written = sorted(p for p in folder.rglob("*") if p.is_file())
    assert len(written) == 7
    for path in written:
        assert path.parent == folder
        assert len(str(path)) <= MAX_PATH_LENGTH
    names = {p.name for p in written}
    assert {"outside.pdf", "win.pdf", "unc.pdf", "same.pdf", "same (2).pdf"} <= names
    assert any(name.startswith("L") and name.endswith(".pdf") for name in names)
    assert not any(name.upper().startswith("CON") for name in names)
    # Nothing escaped: the only files outside the two trees' own folders
    # are the ones the test made.
    assert not (root / "outside.pdf").exists() and not (root.parent / "outside.pdf").exists()


# ----------------------------------------------------------------- claim 10 ----


@pytest.fixture
def fed(tmp_path):
    father = make_engagement(tmp_path, ITEMS, household="Park Family",
                             return_name="1040 - John Park", people=FATHER)
    llc = make_engagement(tmp_path, BUSINESS, household="Park & Lee LLC",
                          return_name="1120S - Park & Lee LLC", people=LLC_PEOPLE)
    feeding(tmp_path, [Feed("Park & Lee LLC", "1120S - Park & Lee LLC")])
    return father, llc


def test_an_attachment_never_files_into_another_household(fed):
    father, llc = fed
    drop_bytes(father, "mail.eml", eml([("tb.pdf", pdf("Trial balance as of December 31 2025",
                                                      who="Park & Lee LLC"))]))

    done = sort_all([father, llc], home=[father], today=DAY1)

    assert read_index(llc) == []
    [parked] = done[father].review
    assert parked.reason == reasons.OPENED_NOT_ACROSS.format()
    assert "B01" in parked.evidence                 # the return and request that wanted it
    assert not any(originals_of(llc).iterdir())
    # The hand-over refuses it in the same words.
    with pytest.raises(FilingError, match="not filed into another household"):
        filer.hand_over(father, parked.pbc_location, llc, "B01", today=DAY2)
    assert read_index(llc) == []


def test_an_attachment_identical_to_another_households_document_writes_nothing_there(fed):
    # The review's B1: the bytes-first road asked every return in the feed
    # list whether it held the bytes, and the one in the other household
    # wrote a Duplicate row naming this household's attachment and its
    # private _Opened path. An attachment never reaches another household's
    # record, by the bytes or by the requests.
    father, llc = fed
    page = pdf("Trial balance as of December 31 2025", who="Park & Lee LLC")
    drop_bytes(llc, "tb.pdf", page)
    sort_all([llc], home=[llc], today=DAY1)
    before = read_index(llc)
    assert [row.decision for row in before] == [FILED]

    drop_bytes(father, "mail.eml", eml([("tb from email.pdf", page)]))
    done = sort_all([father, llc], home=[father], today=DAY2)

    assert read_index(llc) == before
    [parked] = done[father].review
    assert parked.reason == reasons.OPENED_NOT_ACROSS.format()
    assert parked.original_name == "tb from email.pdf" and parked.container
    assert locate(father, parked.pbc_location).is_relative_to(opened_dir_of(father))
    assert not done[llc].duplicates


# ----------------------------------------------------------------- claim 11 ----


def test_a_dry_run_opens_nothing_on_disk(engagement):
    mail = drop_bytes(engagement, "mail.eml", eml([("w2.pdf", pdf(W2))]))
    before = files_under(root_of(engagement))

    done = sort(engagement, today=DAY1, dry_run=True)

    assert [row.decision for row in done.opened] == [OPENED]
    assert done.opened[0].reason.startswith("opened: 1 document")
    assert files_under(root_of(engagement)) == before
    assert mail.is_file() and not opened_dir_of(engagement).exists()
    assert read_index(engagement) == []


# ----------------------------------------------------------------- claim 12 ----


def test_an_unnamed_file_in_opened_is_reported_and_left_alone(engagement):
    drop_bytes(engagement, "mail.eml", eml([("w2.pdf", pdf(W2))]))
    sort(engagement, today=DAY1)
    stray = opened_dir_of(engagement) / "mail" / "dragged in.pdf"
    stray.write_bytes(b"%PDF somebody put this here")
    orphan = opened_dir_of(engagement) / "old mail" / "left.pdf"
    orphan.parent.mkdir()
    orphan.write_bytes(b"%PDF left from a container nobody recorded")

    done = sort(engagement, today=DAY2)

    said = {one.name: one.error for one in done.attention}
    assert "dragged in.pdf" in said and "no row names it" in said["dragged in.pdf"]
    assert "left.pdf" in said
    assert stray.read_bytes() == b"%PDF somebody put this here" and orphan.is_file()
    assert not any(row.original_name in ("dragged in.pdf", "left.pdf") for row in read_index(engagement))


def test_a_replaced_attachment_under_opened_is_reported(engagement):
    # The review's B2: a file replaced under its own name in the year's
    # folder is said every pass; one replaced under _Opened was said by
    # nothing until something tried to use its row.
    drop_bytes(engagement, "mail.eml", eml([("w2.pdf", pdf(W2))]))
    sort(engagement, today=DAY1)
    [one] = [row for row in read_index(engagement) if row.container]
    taken_out = locate(engagement, one.pbc_location)
    assert taken_out.is_relative_to(opened_dir_of(engagement))
    taken_out.write_bytes(b"%PDF a different document under the same name")

    done = sort(engagement, today=DAY2)

    said = [s.error for s in done.attention if s.name == taken_out.name]
    assert len(said) == 1 and "no longer holds the bytes recorded" in said[0]
    assert one.pbc_location in said[0]
    assert taken_out.read_bytes() == b"%PDF a different document under the same name"


def test_a_folder_whose_container_row_is_gone_is_reported(engagement):
    drop_bytes(engagement, "mail.eml", eml([("w2.pdf", pdf(W2))]))
    sort(engagement, today=DAY1)
    rows = read_index(engagement)
    [box] = [row for row in rows if row.decision == OPENED]
    [one] = [row for row in rows if row.container]
    from tracker.locking import engagement_lock

    # The sweep asked directly, of a record whose container row is gone:
    # nothing a person can do removes a container's row, so the state is
    # made by hand here.
    with engagement_lock(engagement):
        prepared = filer._prepare_return(engagement, DAY2.isoformat(), dry_run=False)
    prepared.entries[:] = [one]
    said = filer._unaccounted_in_opened(prepared, [prepared])
    assert [(s.name, "whose own row is gone" in s.error) for s in said] == [("mail", True)]
    assert box.pbc_location                              # it was there before


# ----------------------------------------------------------------- claim 13 ----


def test_the_store_rebuilds_with_container_and_opened(engagement, tmp_path):
    from tracker.filer import ensure
    from tracker.locking import engagement_lock
    from tracker.records import IndexEntry, entry_to_json

    # A row written before decision 143 carries no container at all: the
    # line is written in that older shape, through the one writer.
    old = IndexEntry(received="2026-06-01", original_name="old.pdf", size_kb=1.0, digest="0" * 64,
                     identifier="", prepared_location="", pbc_location=location_of(engagement, originals_of(engagement) / "old.pdf"),
                     decision=NEEDS_REVIEW, reason="waiting")
    row = entry_to_json(old)
    del row["container"]
    with engagement_lock(engagement):
        ensure(engagement)
        store.record(store.connect(), engagement, ledger.new(
            ledger.IMPORTED, **{ledger.KEY_KEY: old.pbc_location, ledger.ROW_KEY: row}))
    drop_bytes(engagement, "mail.zip", a_zip([("w2.pdf", pdf(W2))]))
    sort(engagement, today=DAY1)

    root = root_of(engagement)
    with tempfile.TemporaryDirectory() as scratch:
        conn = store.open(Path(scratch) / store.STORE_FILENAME)
        try:
            store.rebuild_engagement(conn, root, engagement)
            assert store.check(conn, root, engagement) == []
            held = {row["original_name"]: (row["decision"], row["container"])
                    for row in store.documents(conn, engagement)}
        finally:
            conn.close()
    # The store holds what the line said - nothing - and the reader reads
    # it as a document that came on its own.
    assert held["old.pdf"] == (NEEDS_REVIEW, None)
    assert [row.container for row in read_index(engagement) if row.original_name == "old.pdf"] == [""]
    assert held["mail.zip"] == (OPENED, "")
    assert held["w2.pdf"] == (FILED, original_at(engagement, "mail.zip"))
    assert ledger.OPENED in ledger.ROW_EVENTS


# -------------------------------------------------------- the parsers alone ----


def test_a_container_is_known_by_its_extension_alone():
    assert containers.is_container("Fwd.MSG") and containers.is_container("a.eml")
    assert containers.is_container("x.zip")
    assert not containers.is_container("book.xlsx") and not containers.is_container("letter.docx")


def test_a_content_id_alone_is_not_an_inline_signal():
    """Real attachments carry a Content-ID too (the corpus's did): only an
    ``inline`` disposition, or the .msg's hidden or rendered-in-place flag,
    skips a part."""
    opened = open_container(eml([("w2.pdf", b"%PDF w2")]), "eml")
    assert [one.name for one in opened.attachments] == ["w2.pdf"]


def test_a_nested_container_that_will_not_open_is_handed_back_to_park():
    opened = open_container(eml([("w2.pdf", b"%PDF w2"), ("locked.zip", locked_zip())]), "eml")
    assert [(one.name, one.code == reasons.CONTAINER_LOCKED.code) for one in opened.attachments] == [
        ("w2.pdf", False), ("locked.zip", True)]


def test_a_zip_member_is_never_extracted_to_disk(tmp_path, monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("extract was called")

    monkeypatch.setattr(zipfile.ZipFile, "extract", refuse)
    monkeypatch.setattr(zipfile.ZipFile, "extractall", refuse)
    assert len(open_container(a_zip([("a.pdf", b"%PDF")]), "zip").attachments) == 1


def test_the_command_line_lists_and_writes_nothing(tmp_path):
    import subprocess
    import sys

    box = tmp_path / "mail.zip"
    box.write_bytes(a_zip([("w2.pdf", b"%PDF" * 10)]))
    before = files_under(tmp_path)
    done = subprocess.run([sys.executable, "-m", "tracker.containers", str(box)],
                          capture_output=True, text=True, cwd=Path(__file__).resolve().parents[1])
    assert done.returncode == 0 and "w2.pdf" in done.stdout
    assert files_under(tmp_path) == before


def test_limits_parts_left_inside():
    """Every part left inside is named on the container's line, so their
    number is held too: the body and 199 inline pictures are 200, and open;
    one more stops the container."""
    from tracker.containers import LIMIT_SKIPPED, MAX_SKIPPED

    pictures = [(f"p{n}.png", b"\x89PNG" + b"0" * 16) for n in range(MAX_SKIPPED - 1)]
    opened = open_container(eml([("w2.pdf", b"%PDF w2")], inline=pictures), "eml")
    assert len(opened.skipped) == MAX_SKIPPED
    one_more = pictures + [("last.png", b"\x89PNG" + b"1" * 16)]
    with pytest.raises(NotOpened, match=LIMIT_SKIPPED):
        open_container(eml([("w2.pdf", b"%PDF w2")], inline=one_more), "eml")


def test_a_name_on_the_record_is_never_longer_than_a_file_name():
    from tracker.containers import NAME_MAX

    kept = safe_name("L" * 1000 + ".pdf", "attachment")
    assert len(kept) == NAME_MAX and kept.endswith(".pdf")


# ------------------------------------------ decision 154: opened in the child ----
#
# 150 read every document in a child process the pass can stop; 143's three
# parsers ran in the pass's own process. The opening is now one more job
# for that child. The stand-ins that block or crash are in
# tests/child_readers.py, because a patch made here never reaches the child.


@pytest.fixture
def opened_in_a_child(monkeypatch, tmp_path):
    """Containers opened - and documents read - in a child, as the pass
    does, with the opener's marks in a folder of the test's own."""
    import tracker.content_check as content_check
    from tests import child_readers

    marks = tmp_path / "marks"
    marks.mkdir()
    monkeypatch.setattr(content_check, "READ_IN_A_CHILD", True)
    monkeypatch.setenv(child_readers.MARKS_VARIABLE, str(marks))
    content_check.readers_that_could_not_start()          # nothing left from another test
    return monkeypatch


def test_a_container_parser_that_never_finishes_is_stopped_and_the_container_parks(
        engagement, opened_in_a_child):
    """A defect in olefile, email or zipfile that nobody has found yet would
    have held the whole pass: the parsers ran in its own process, outside
    150's stop. The opening now ends at the stop for a file, and the
    container parks with the stop's sentence - kept by its row, so the
    next pass does not open it again - with nothing written under the
    hidden folder of what was taken out, and no child left."""
    import time

    import tracker.content_check as content_check
    from tests import child_readers
    from tests.test_content_check import STOP_IN_TESTS, STOPPED, eventually, no_child_left, running

    opened_in_a_child.setattr(content_check, "READING_STOP_DOCUMENT_SECONDS", STOP_IN_TESTS)
    opened_in_a_child.setattr(containers, "_CHILD_OPENER",
                              child_readers.a_container_parser_that_never_finishes)
    drop_bytes(engagement, "mail.zip", a_zip([("w2.pdf", pdf(W2))]))

    started = time.monotonic()
    sort(engagement, today=DAY1)
    took = time.monotonic() - started

    mark = child_readers.opener_reached(Path("mail.zip"), "parser")
    assert mark.is_file()                                          # stopped inside the parser
    assert STOP_IN_TESTS <= took < STOP_IN_TESTS + 45
    [row] = read_index(engagement)
    assert row.decision == NEEDS_REVIEW and row.reason == STOPPED
    assert row.code == reasons.READING_STOPPED.code
    assert row.pbc_location == original_at(engagement, "mail.zip")
    assert not opened_dir_of(engagement).exists()
    assert no_child_left()
    assert eventually(lambda: not running(int(mark.read_text(encoding="utf-8"))))

    opened_in_a_child.setattr(content_check, "in_a_child",
                              lambda *a, **k: pytest.fail("a parked container was opened again"))
    sort(engagement, today=DAY2)
    assert read_index(engagement) == [row]


def test_a_container_parser_that_crashes_parks_the_container_not_the_pass(
        engagement, opened_in_a_child):
    """A crash in a parser used to end the pass's own process, and every
    document after the container went unsorted. The child ends instead:
    the container parks with the failed reading's sentence, and the pass
    goes on to the loose W-2 dropped beside it."""
    from tests import child_readers
    from tests.test_content_check import CRASHED, no_child_left

    opened_in_a_child.setattr(containers, "_CHILD_OPENER", child_readers.a_container_parser_that_crashes)
    drop_bytes(engagement, "a mail.eml", eml([("1098.pdf", pdf(FORM_1098))]))
    drop_bytes(engagement, "w2.pdf", pdf(W2))

    done = sort(engagement, today=DAY1)

    assert child_readers.opener_reached(Path("a mail.eml"), "parser").is_file()
    [parked] = done.review
    assert parked.original_name == "a mail.eml" and parked.reason == CRASHED
    assert parked.code == reasons.READING_CRASHED.code
    [filed] = done.filed
    assert filed.original_name == "w2.pdf" and filed.identifier == "A01"
    assert not opened_dir_of(engagement).exists()
    assert no_child_left()


def test_a_container_the_reader_could_not_start_on_is_reopened_next_pass(
        engagement, opened_in_a_child):
    """150's rule for a machine fault, applied to the opening: a child that
    never says "started" is the machine's doing, not the file's, so the
    container gets no row - a row would make its bytes known and it would
    never be opened - and nothing is written. It rests in the year's
    folder as a stray, the pass says it once, and the next pass, on a
    working machine, opens it and files what it holds."""
    from tests.test_content_check import _a_reader_only_the_pass_has, no_child_left
    from tracker import content_check
    from tracker.registry import discover_engagements
    from tracker.runner import REMINDERS_NEVER, run_registry

    mail = eml([("w2.pdf", pdf(W2)), ("1098.pdf", pdf(FORM_1098))])
    drop_bytes(engagement, "mail.eml", mail)
    root = root_of(engagement)

    with pytest.MonkeyPatch.context() as broken:           # the machine is broken
        broken.setattr(containers, "_CHILD_OPENER", _a_reader_only_the_pass_has(broken))
        first = run_registry(discover_engagements(root), today=DAY1, reminders=REMINDERS_NEVER)

    assert read_index(engagement) == []                    # not opened, not recorded
    assert (originals_of(engagement) / "mail.eml").read_bytes() == mail
    assert not opened_dir_of(engagement).exists()
    [warning] = first.warnings
    assert "could not start on this machine for 1 file(s)" in warning and "mail.eml" in warning
    assert [run.review for run in first.runs] == [0]
    assert content_check.readers_that_could_not_start() == []     # said by the pass, once
    assert no_child_left()

    second = run_registry(discover_engagements(root), today=DAY2, reminders=REMINDERS_NEVER)

    assert second.warnings == []
    rows = read_index(engagement)
    [box] = [row for row in rows if row.decision == OPENED]
    assert box.pbc_location == original_at(engagement, "mail.eml")
    assert sorted((row.original_name, row.identifier) for row in rows if row.container) == [
        ("1098.pdf", "C01"), ("w2.pdf", "A01")]
    assert no_child_left()


@pytest.mark.parametrize("name", [
    "mail.eml", "mail.msg", "mail.zip", "nested.zip", "locked.zip", "broken.msg",
])
def test_an_opened_container_gives_the_same_parts_as_in_process(tmp_path, opened_in_a_child, name):
    """On time, the child hands back exactly what the pass's own process
    opens: every attachment's name and bytes, in order, each part left
    inside and why - or, for one that will not open, the same sentence."""
    from tests.test_content_check import no_child_left
    from tracker import content_check

    two = [("w2.pdf", pdf(W2)), ("1098.pdf", pdf(FORM_1098))]
    data = {
        "mail.eml": lambda: eml(two, inline=[("logo.png", b"\x89PNG" + b"0" * 16)]),
        "mail.msg": lambda: container_of("msg", two),
        "mail.zip": lambda: a_zip([two[0], ("sub/1098.pdf", two[1][1]), ("sub/", b"")]),
        "nested.zip": lambda: a_zip([("mail.eml", eml(two[:1])), ("notes.pdf", b"%PDF notes")]),
        "locked.zip": locked_zip,
        "broken.msg": lambda: b"\xd0\xcf\x11\xe0 not a compound file" * 100,
    }[name]()
    path = tmp_path / name
    path.write_bytes(data)
    spawned = []
    real = content_check.in_a_child
    opened_in_a_child.setattr(content_check, "in_a_child",
                              lambda *a, **k: spawned.append(1) or real(*a, **k))
    try:
        expected = open_container(data, path.suffix)
    except NotOpened as exc:
        with pytest.raises(NotOpened) as raised:
            containers.open_bounded(path)
        assert raised.value.sentence == exc.sentence
    else:
        assert expected.attachments and containers.open_bounded(path) == expected
    assert spawned == [1]
    assert no_child_left()


def test_a_recorded_attachment_named_like_a_temp_survives_the_sweep(engagement):
    """Decision 155's review, FIX 2. What came out of an email or a zip rests
    under ``_Opened`` as an original rests in the year's folder, and its
    own name is the client's: one that happens to have the exact temp shape
    (``fsio.TEMP_NAME``), older than the pass and naming a process that is
    gone, is still never taken while a row names it - nor is its working
    copy, parked under the same name. The same file with no row naming it
    is a killed write's leftover, and is."""
    import os
    import time

    from tracker.filer import sweep_stranded_temps
    from tracker.fsio import TEMP_NAME
    from tracker.layout import household_of, opened_dir_of

    odd = f"statement.pdf.{os.getpid()}.0a1b2c3d.tmp"
    drop_bytes(engagement, "docs.zip", a_zip([(odd, pdf("Form 1098 Mortgage Interest Statement 2025"))]))
    sort(engagement, today=DAY1)
    [kept] = [locate(engagement, row.pbc_location) for row in read_index(engagement)
              if row.pbc_location.endswith(odd)]
    assert kept.is_file() and TEMP_NAME.fullmatch(kept.name)
    assert opened_dir_of(engagement) in kept.parents
    stranger = kept.parent / f"other.pdf.{os.getpid()}.1b2c3d4e.tmp"
    stranger.write_bytes(kept.read_bytes())

    taken = sweep_stranded_temps(household_of(engagement), [engagement], started=time.time() + 1)

    assert taken == [stranger] and not stranger.exists()
    assert kept.is_file()                       # a row names it: never taken
    # Its working copy, parked under the client's own name - the same shape -
    # is a row's too, and stays (the review's probe found the sweep taking it).
    [row] = [row for row in read_index(engagement) if row.pbc_location.endswith(odd)]
    assert row.filed_locations and all(locate(engagement, where).is_file()
                                       for where in row.filed_locations)


def test_a_zip_packed_with_bzip2_or_lzma_is_a_persons_to_open(engagement):
    """Decision 178: the standard library bounds a deflated read at the size
    asked for, but inflates a bzip2 or LZMA part a whole compressed chunk at
    a time - 905 bytes of bzip2 grew past two gigabytes in one read, before
    the ratio could count it. Only stored and deflated parts are unpacked;
    a zip holding any other is refused from its directory, before a byte of
    it is unpacked, and parks for a person with the limit it passed."""
    for method in (zipfile.ZIP_BZIP2, zipfile.ZIP_LZMA):
        packed = a_zip([("W-2.pdf", b"%PDF-1.4 " + b"\0" * 1000)], method=method)
        with pytest.raises(NotOpened) as refused:
            open_container(packed, "zip")
        assert refused.value.sentence == reasons.CONTAINER_LIMIT.format(
            error=containers.LIMIT_PACKING)
    assert len(open_container(a_zip([("W-2.pdf", b"x")], method=zipfile.ZIP_STORED),
                              "zip").attachments) == 1

    drop_bytes(engagement, "packed.zip",
               a_zip([("W-2.pdf", b"%PDF-1.4 " + b"\0" * 1000)], method=zipfile.ZIP_BZIP2))
    sort(engagement, today=DAY1)
    [row] = read_index(engagement)
    assert row.decision == NEEDS_REVIEW and containers.LIMIT_PACKING in row.reason
    assert row.code == reasons.CONTAINER_LIMIT.code and reasons.CONTAINER_LIMIT.firm_side


def test_an_attachment_name_keeps_no_invisible_formatting_character():
    """Decision 176: a right-to-left override shows ``invoice<RLO>fdp.exe``
    as ``invoiceexe.pdf`` in Explorer - a program dressed as a PDF in the
    firm's review folder - and a zero-width space makes two names that look
    alike two files. Every formatting character goes; the letters stay."""
    assert safe_name("invoice‮fdp.exe", "x") == "invoicefdp.exe"
    assert safe_name("W​-2⁠ 2025.pdf", "x") == "W-2 2025.pdf"
    assert safe_name("﻿Statement.pdf", "x") == "Statement.pdf"
    assert safe_name("Muñoz W-2.pdf", "x") == "Muñoz W-2.pdf"
    assert safe_name("‮​", "attachment 1") == "attachment 1"


def test_an_attachment_name_loses_what_the_layouts_invisible_set_names():
    """Decision 188: the invisible set is the layout's one set, so the
    default-ignorables outside the format category - a variation selector,
    a combining grapheme joiner, the Hangul filler - go from an attachment's
    name as a zero-width space does; a space and a letter stay."""
    from tracker.layout import is_invisible

    for hidden in ("️", "͏", "ㅤ", "​"):
        assert is_invisible(hidden)
        assert safe_name(f"W-2{hidden} 2025.pdf", "x") == "W-2 2025.pdf", hex(ord(hidden))
    assert safe_name("W-2 2025.pdf", "x") == "W-2 2025.pdf"
