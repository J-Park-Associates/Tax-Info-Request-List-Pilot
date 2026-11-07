"""Tests for tracker/verdicts.py — the verdict cache, all local files.

Since P337 (SPEC-architecture-p4 P4.11) the tests whose highest home is
tracker/verdicts.py are here, cut and pasted from tests/test_content_check.py
with their names, code and comments, in the order they stood: the cache
version that moved, and a cache refused for an engagement the store does not
hold. Every other cache test also asks content_check to check or read a
document, so it stays there. The last test is the one the move added: a
verdict row written before the move reads after it (R4.11.6).
"""

import pytest

from tests.content_check_helpers import an_engagement, item
from tracker import store
from tracker.content_check import ContentCache, rules_fingerprint
from tracker.keywords import ContentResult
from tracker.locking import engagement_lock
from tracker.records import Evidence
from tracker.verdicts import CACHE_VERSION


def test_the_cache_version_moved_so_a_verdict_read_sideways_is_read_again(tmp_path):
    """A verdict reached at version 9 may have been reached on nonsense: the
    page it was read from was never turned upright. The cache is
    disposable, so the version moves and the first pass after this
    decision re-reads those scans once. (Decision 141 moved it again, for
    the notice's first-page phrases, decision 169 once more: a new reader
    means new verdicts on every scan and photo, and decision 190 again: a
    verdict carries its cause's code, and P285 again: version 13 was read
    before the page was prepared and drawn at 300 dpi.)"""
    assert CACHE_VERSION == 14

    rule = item(required_keywords=("Chase",))
    engagement = an_engagement(tmp_path, rule)
    fingerprint = rules_fingerprint(rule)
    conn = store.connect()
    engagement_id = store._engagement_row(conn, engagement)["id"]
    for version, digest in ((9, "sideways"), (11, "read by tesseract")):
        conn.execute(
            f"INSERT INTO {store.VERDICTS_TABLE} (engagement_id, digest, fingerprint, version, verdict) "
            "VALUES (?, ?, ?, ?, ?)", (engagement_id, digest, fingerprint, version, '{"ok": true}'))

    assert ContentCache(engagement).get_by_digest("sideways", fingerprint) is None
    assert ContentCache(engagement).get_by_digest("read by tesseract", fingerprint) is None


def test_a_cache_for_an_engagement_the_store_does_not_hold_is_refused_by_name(tmp_path):
    folder = tmp_path / "Clients" / "Nobody 2025"
    folder.mkdir(parents=True)
    with pytest.raises(store.StoreError, match="does not hold this engagement") as raised:
        ContentCache(folder)
    assert folder.name in str(raised.value)


def test_a_verdict_row_written_before_verdicts_moved_reads_after_it(tmp_path):
    """No class name is kept (R4.11.6, P337). A verdict row is ``asdict`` of
    a ContentResult under CACHE_VERSION: the row below is what the cache
    wrote while it lived in tracker/content_check.py (``asdict`` at a67b7d5,
    pasted), and the moved cache reads it back as the verdict it was made
    from, its evidence and all."""
    kept = ContentResult(ok=True, evidence=(Evidence("required", "Chase", "title", 1),
                                            Evidence("date", "2025", "first_page", 1)))
    row = {"ok": True, "reason": "", "extractable": True, "transient": False,
           "evidence": ({"rule": "required", "term": "Chase", "where": "title", "page": 1},
                        {"rule": "date", "term": "2025", "where": "first_page", "page": 1}),
           "code": ""}
    rule = item(required_keywords=("Chase",))
    engagement = an_engagement(tmp_path, rule)
    fingerprint = rules_fingerprint(rule)
    with engagement_lock(engagement):
        store.remember_verdicts(store.connect(), engagement, version=CACHE_VERSION, memos={},
                                verdicts={"the digest": {fingerprint: row}},
                                forget_paths=set(), forget_digests=set())

    assert ContentCache(engagement).get_by_digest("the digest", fingerprint) == kept
