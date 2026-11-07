"""What a judgment says, and the verdict cache that keeps its verdicts.

Two things live here, and they are one module because one keeps the
other.

- **The judgment's shapes** (decision 189). :class:`Extraction` is what
  one reading of a document says, or why it could not be read.
  :class:`RowQuestion`, :class:`NameQuestion` and :class:`Questions` are
  what the pass asks of a document, once, and :class:`Judgment`, with a
  :class:`RowJudgment` for each row asked about, is the answer;
  :func:`unjudged` is the judgment of a reading that has no words to
  judge. They are what crosses back from the reading's child over its
  pipe: the answers to the questions the pass asked, in the firm's own
  words - a row's keyword, a reason sentence, a form number the catalog
  knows, one of the firm's spellings - and never a word of the document.
  The reading and the judging stay in :mod:`tracker.content_check`
  (:func:`tracker.content_check.judge`,
  :func:`tracker.content_check.judgment_of`); this module only says what
  their answer looks like.
- **The verdict cache** (decisions 107, 109, 150, 155 and 189).
  :class:`ContentCache` keeps a judgment's verdicts by the file's
  content; a per-path memo of each file's digest, the one memo every hash
  of a file in the firm's tree goes through (decision 109), which also
  learns the digest a copy was proved against (decision 155); and, for the
  pass alone, the last few judgments the content check is about to ask for
  (decision 150, ``_HELD_READINGS``). A kept verdict's evidence is
  rebuilt by ``_evidence_from_json``.

Caching: :class:`ContentCache` stores only *verdicts* — pass/fail, reason
and evidence — keyed by the file's **content digest** and the row's rules
fingerprint, with a per-path memo of (size, mtime, digest) so an unchanged
file is not re-hashed. Keyed on content, not path, because the same bytes are read
twice in this system: once as a drop the router routes, once as the
working copy the scanner checks. A verdict the router reached is the
verdict the scanner finds. Extracted client text is deliberately never
persisted anywhere. Editing a row's rules changes the fingerprint and
triggers one re-extraction; unchanged files on unchanged rules are never
re-read, which keeps the scheduled cadence cheap.

**Where the cache lives** (decision 107): in the store on the designated
machine - two tables of :mod:`tracker.store`, the memos and the verdicts,
per engagement - and nowhere in the engagement folder. Until then it was a
JSON file beside the client's documents that every pass rewrote, in a
folder a cloud client syncs; the owner's rule is that nothing the machine
can derive lives in the synced folder, because a file rewritten every two
hours there is the synced-database failure one file over. It is **not
journalled**: a verdict is a derivation of the bytes in the folder and the
rules in the record, not a fact about the engagement, so a rebuild of the
store from the journals leaves the cache empty and the next pass reads
each document once - slower, never wrong. A save is one transaction of
the store's own, under the engagement lock every writer already holds,
and never ``store.record()``: there is no event. A cache built with no
engagement - the command line's, a test's - lives in memory and never
touches the store. The old file is never read; the after-install step
removes it (:data:`RETIRED_CACHE_FILENAME`).

**Nothing kept names a class.** A verdict row is ``asdict`` of a
:class:`tracker.keywords.ContentResult`, under :data:`CACHE_VERSION`; the
shapes cross the child's pipe pickled under their qualified names, which
both ends import from the same code, and nothing pickles one to disk. So
the move that brought them here changed no stored row and no message, and
:data:`CACHE_VERSION` did not move.

**Why the shapes and the cache are one module** (SPEC-architecture-p4
P4.11, P337; the architecture audit's A-5). The audit proposed a module
for the cache alone. But :class:`ContentCache` stores and hands back
:class:`Judgment` objects, and content_check annotates with
:class:`ContentCache`; the suite's import graph (``tests/import_graph.py``)
counts an ``if TYPE_CHECKING:`` import as a load edge, so with the cache
here and the shapes in content_check each module would name the other's
types - a cycle. With the shapes beside the cache that keeps them, the one
direction is content_check, then this module, then
:mod:`tracker.keywords`. Out of it, content_check is the reading and the
judgment.

**Why it sits at layer 2.** It reads the store's two verdict tables
(:func:`tracker.store.cached_verdicts`,
:func:`tracker.store.remember_verdicts`), the validators' hash, the request
row and the Evidence record (layer 1), the per-reply memo (layer 0) and,
in its own layer, :class:`tracker.keywords.ContentResult`, the rules'
verdict a row holds; ``store`` makes layer 2 the lowest layer that holds
it beside ``keywords``. It imports nothing of ``content_check`` or
``ocr``. It does not log: a shape has nothing to say to the run log, and
the cache's one write is the store's own transaction.

**Every reader asks this module.** content_check imports back by name what
its own code reads and offers none of it on; every other reader imports
each name from here. Of the code that came from content_check only the
memo reads ``sha256_of``, so a stand-in that counts the memo's hashes is
set on this module and no longer on content_check (the audit's A-4).
"""

from __future__ import annotations

import os
from collections import OrderedDict
from dataclasses import MISSING, asdict, dataclass, field, fields, replace
from pathlib import Path

from tracker import hold, store
from tracker.keywords import ContentResult
from tracker.manifest import RequestItem

# The Evidence record lives in tracker/records.py (decision 100): it is the
# shape of a verdict, not the reading of a document. This module imports it
# to rebuild a kept verdict's evidence, and offers it on to no one (P322).
from tracker.records import Evidence
from tracker.validators import sha256_of

#: The file the verdict cache was, in the engagement folder, until decision
#: 107 moved it into the store. Never read again: the one use left is the
#: after-install step (P234), which removes it from every folder that has one.
RETIRED_CACHE_FILENAME = "_content_cache.json"
#: The cache's layout, carried on every verdict row in the store; a row at
#: any other version is ignored on load and deleted on save (the cache is
#: disposable), so a matcher change invalidates without a store version.
#: Bump it whenever what a verdict means changes; docs/ROADMAP.md holds
#: what each bump (3 to 13) was for; 14 is the pilot's P285
#: (``pilot/DECISIONS.md``): the page is prepared and drawn at 300 dpi, so
#: every verdict on a scan or a photo was reached on other pixels.
CACHE_VERSION = 14


# ---------------------------------------------------------------- evidence ----


def _evidence_from_json(raw: object) -> tuple[Evidence, ...]:
    """The evidence of a cached verdict, rebuilt from what ``asdict`` wrote.

    Total, like everything that reads the cache: the cache is disposable,
    so anything unrecognised costs a re-extraction, never an exception in
    a scheduled run. A tuple as well as a list: ``asdict`` leaves the
    evidence a tuple of dicts until the store's JSON round trip makes it a
    list, and a verdict read back in the same pass it was kept must be the
    verdict that was kept (decision 107's claim that the kept verdict and
    the miss verdict are one).
    """
    if not isinstance(raw, (list, tuple)):
        return ()
    return tuple(
        Evidence(str(item.get("rule", "")), str(item.get("term", "")),
                 str(item.get("where", "")), int(item.get("page", 0) or 0))
        for item in raw if isinstance(item, dict)
    )


@dataclass(frozen=True, slots=True)
class Extraction:
    """What one document says, or why it could not be read.

    ``text`` is None when there is nothing usable and ``reason`` then says
    why in the words the scanner writes. ``needs_ocr`` marks a PDF whose
    text layer is empty when the caller asked not to OCR yet.
    """

    text: str | None
    from_ocr: bool = False       # the text came from OCR, not a text layer
    needs_ocr: bool = False      # a scan; OCR was not attempted (ocr=False)
    reason: str = ""             # why there is no usable text, if there is none
    extractable: bool = True     # False: no extractor, no OCR, or extraction failed
    #: Why the reading failed: the exception's class (decision 190), never
    #: its message, or the firm's own sentence for a child that ended.
    error: str = ""
    transient: bool = False      # the machine's doing (no OCR, OCR failed), not the file's
    #: How long this reading took, in seconds (decision 127). Recorded on
    #: every reading, failed ones included, and never acted on: a slow
    #: reading is said in the run's summary and finished, never cut short.
    #: It is the number the reader benchmark and the owner's speed ceiling
    #: are measured in.
    seconds: float = 0.0
    #: Only the first ``validators.TEXT_READ_CAP_MB`` of a text file was
    #: read (decision 137). Said beside any verdict reached on it.
    cut: bool = False
    #: Tier 2's open test of the same file, made where the reading was made
    #: (decision 150, :func:`validators.open_test`): ``""`` when it opens
    #: cleanly, the refusal otherwise, and None when it was not made - a
    #: reading of :func:`extract` alone, or one that never finished.
    opened: str | None = None
    #: The code of the Reason ``reason`` says (decision 190).
    code: str = ""


# --------------------------------------------------- the judgment's shapes ----


@dataclass(frozen=True, slots=True)
class RowQuestion:
    """What a judgment is asked of one request row: exactly the parts of the
    row :func:`evaluate_rules`, :func:`required_matched` and
    :func:`any_keyword_matched` read, and nothing else of the row - no
    identifier, no note, no status.

    It is its own key in :attr:`Judgment.rows`. Finer than
    :func:`rules_fingerprint`, which leaves out the Period and whether the
    Date Pattern was derived from it: two rows alike in their rules but not
    in those two would share a fingerprint and could be answered
    differently (the Period is the evidence's term; a derived pattern runs
    over the whole text, a typed one line by line). The verdict cache keeps
    the fingerprint as its key, as before.
    """

    required_keywords: tuple[str, ...] = ()
    any_keywords: tuple[str, ...] = ()
    date_pattern: str = ""
    date_pattern_derived: bool = False
    period: str = ""

    def as_item(self) -> RequestItem:
        """The row, as the rules read it, with nothing of the row's own."""
        return RequestItem(
            identifier="", document="", period=self.period,
            required_keywords=self.required_keywords, any_keywords=self.any_keywords,
            date_pattern=self.date_pattern, date_pattern_derived=self.date_pattern_derived,
        )


def row_question(item: RequestItem) -> RowQuestion:
    """The question a judgment is asked about ``item``, and the key its
    answer is found under."""
    return RowQuestion(
        required_keywords=tuple(item.required_keywords), any_keywords=tuple(item.any_keywords),
        date_pattern=item.date_pattern, date_pattern_derived=item.date_pattern_derived,
        period=item.period,
    )


@dataclass(frozen=True, slots=True)
class NameQuestion:
    """Whose document is this, asked for one return (decision 128): that
    return's spellings, and each other return the drop may feed as
    ``(label, spellings)``, in order. Its own key in
    :attr:`Judgment.names`; every string in it is the firm's."""

    own: tuple[str, ...] = ()
    others: tuple[tuple[str, tuple[str, ...]], ...] = ()


@dataclass(frozen=True, slots=True)
class Questions:
    """Everything the pass will ask of one document, asked once.

    ``ocr`` is whether a scan is read by OCR (:func:`extract`'s own
    switch); ``rows`` every row the caller may ask about - for the router,
    every row of every return the drop may feed; for the scanner, the row
    the working copy sits under; ``names`` one question per return the
    drop may feed. A question not asked has no answer: the pass asks a new
    judgment for it (the scanner) or fails loudly (the router).
    """

    ocr: bool = True
    rows: tuple[RowQuestion, ...] = ()
    names: tuple[NameQuestion, ...] = ()


@dataclass(frozen=True, slots=True)
class RowJudgment:
    """One row's answers, each the value the pass once computed itself.

    ``verdict`` is :func:`evaluate_rules` with the page's own forms
    (:func:`own_forms`) - the ordinary reading, and also decision 94's
    split: the split reads a two-family page with the forms it names as
    itself counted as its own, and that set *is* :func:`own_forms`'s
    answer, so the two readings are one (decision 107 made them so).
    ``required_matched`` and ``any_matched`` are the router's two leads.
    """

    verdict: ContentResult
    required_matched: bool = False
    any_matched: bool = False


@dataclass(frozen=True, slots=True)
class Judgment:
    """What one document said to the questions asked of it (decision 189).

    ``extraction`` is the reading with its words taken out: ``text`` is
    ``""`` where there were words and None where there were none, so every
    test the pass made of ``text is None`` still means what it meant, and
    everything else - the reason, ``transient``, ``needs_ocr``,
    ``from_ocr``, the seconds, ``cut``, the open test's verdict - is as the
    reader left it. ``transient`` there is the one place a judgment says
    the machine, not the file, decided it (SPEC-156's seam).

    ``has_words`` is whether there was anything to judge: a reading with
    text, and not a scan waiting for OCR. ``own`` is :func:`own_forms`,
    ``self_named`` :func:`self_named_forms` (first mention first) and
    ``carries_1099b`` :func:`carries_a_1099b_section`, all of the words.
    ``rows`` and ``names`` answer the questions, keyed by the question.
    """

    extraction: Extraction
    has_words: bool = False
    own: frozenset[str] | None = None
    self_named: tuple[str, ...] = ()
    carries_1099b: bool = False
    rows: dict[RowQuestion, RowJudgment] = field(default_factory=dict)
    names: dict[NameQuestion, object] = field(default_factory=dict)   # NameQuestion -> names.NameVerdict

    def row(self, item: RequestItem) -> RowJudgment:
        """The answers about ``item``; a row that was not asked is a fault
        in the caller, said with the row, never a silent "no"."""
        try:
            return self.rows[row_question(item)]
        except KeyError:
            raise LookupError(
                f"the judgment was not asked about row {item.identifier or '(unnamed)'}"
            ) from None

    def name(self, question: NameQuestion):
        """The name check's verdict for ``question`` (a
        :class:`tracker.names.NameVerdict`); one not asked is a fault."""
        try:
            return self.names[question]
        except KeyError:
            raise LookupError("the judgment was not asked whose document this is") from None


def unjudged(reading: Extraction) -> Judgment:
    """The judgment of a reading that has no words to judge - a reader that
    could not start, a stop, a crash - as :func:`judgment_of` makes it:
    the reading's standing, and no answers."""
    return Judgment(extraction=replace(reading, text=None if reading.text is None else ""))


# ------------------------------------------------------------------- cache ----


#: How many judgments a :class:`ContentCache` holds in memory for the
#: content check that follows an open test (decision 150; a judgment, and
#: no text, since decision 189).
_HELD_READINGS = 8


class ContentCache:
    """Verdict cache: ``(content digest, rules-fingerprint) -> ContentResult``.

    Stores only pass/fail verdicts and reasons — never extracted client
    text. A per-path memo of (size, mtime, digest) spares the hashing of a
    file that has not changed; the verdicts themselves are keyed by what
    the file *is*, so a working copy of a routed drop is a hit under its
    new name.

    **Backed by the store** (decision 107): built for an engagement, it
    loads that engagement's memos and verdicts at :data:`CACHE_VERSION`
    from the store's two tables once, works in memory exactly as it always
    did, and :meth:`save` writes back what changed - the memos and verdicts
    learned, the paths and digests pruned - in one transaction of the
    store's own, under the engagement lock. The engagement must already be
    in the store (both writers ``ensure()`` first); one it does not hold is
    refused by name here, at construction, rather than at the save. Built
    with no engagement it is memory only: the command line's cache, a dry
    run's, a test's - :meth:`save` then touches nothing. Disposable by
    design: a row written under another version simply means re-extraction.
    """

    def __init__(self, engagement_dir: Path | None = None):
        self._engagement = Path(engagement_dir) if engagement_dir is not None else None
        self._files: dict[str, dict] = {}                # path key -> size, mtime_ns, digest
        self._verdicts: dict[str, dict[str, dict]] = {}  # digest -> fingerprint -> verdict
        # What this cache has learned and forgotten since it was loaded, so
        # a save writes exactly those rows and no others.
        self._learned_files: set[str] = set()
        self._learned_verdicts: set[tuple[str, str]] = set()
        self._forgotten_files: set[str] = set()
        self._forgotten_digests: set[str] = set()
        #: Judgments :func:`open_verdict` made in the child and the content
        #: check will want next, by digest (decision 150): in memory, a
        #: few at a time, for this pass only - never saved. Since decision
        #: 189 a judgment, which holds no word of the document: the
        #: scanner held up to eight whole texts here before.
        self._readings: OrderedDict[str, Judgment] = OrderedDict()
        #: The household's deadline for this pass, on ``ocr.awake_clock``,
        #: while the sort or the scan is taking files (decision 189): a
        #: miss past it starts no judgment (:func:`before_a_judgment`);
        #: a hit is answered whatever the time. None is no limit.
        self.deadline: float | None = None
        if self._engagement is not None:
            self._files, self._verdicts = store.cached_verdicts(
                store.connect(), self._engagement, version=CACHE_VERSION)

    @staticmethod
    def _key(file: Path) -> str:
        """The cache's key for ``file``: where it is, without case (Windows
        paths are case-insensitive).

        Built from the folder's held answer and the file's own name (pilot
        P216): ``Path.resolve()`` resolves the parent and appends a final
        component that is not a link unchanged - on Windows perhaps in its
        on-disk case, which ``.lower()`` folds - so the string is the one a
        whole resolve gives, at one ``lstat`` instead of one a segment.
        Inside a household's hold the folder's answer is held
        (:func:`tracker.hold.resolved`); outside one it is asked every
        time, as ``resolve`` was. A name that is not a plain name, or a
        file that is a link, is resolved whole, as before. The key only:
        the verdicts, the digests and the reader's own path are untouched.
        """
        name = file.name
        if name not in ("", ".", "..") and not os.path.islink(file):
            return str(hold.resolved(file.parent) / name).lower()
        return str(file.resolve()).lower()

    def digest_of(self, file: Path) -> str | None:
        """The file's content digest, hashed once per (size, mtime); None if it vanished."""
        try:
            stat = file.stat()
        except OSError:
            return None
        key = self._key(file)
        memo = self._files.get(key)
        if memo and memo.get("size") == stat.st_size and memo.get("mtime_ns") == stat.st_mtime_ns:
            return str(memo["digest"])
        try:
            digest = sha256_of(file)
        except OSError:
            return None
        self._files[key] = {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns, "digest": digest}
        self._learned_files.add(key)
        self._forgotten_files.discard(key)
        return digest

    def remember_digest(self, file: Path, digest: str) -> None:
        """Remember ``digest`` for ``file`` as it now stands, without reading it.

        For a file whose bytes were proved under another name a moment ago
        and renamed to this one (decision 155's working copy: proved on its
        temp, then swapped in) - the rename keeps the size and the
        modification time, so the memo is what :meth:`digest_of` would have
        learned by reading it again. A file that has gone is not remembered.
        """
        try:
            stat = file.stat()
        except OSError:
            return
        key = self._key(file)
        self._files[key] = {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns, "digest": digest}
        self._learned_files.add(key)
        self._forgotten_files.discard(key)

    def get(self, file: Path, fingerprint: str) -> ContentResult | None:
        digest = self.digest_of(file)
        return self.get_by_digest(digest, fingerprint) if digest else None

    def get_by_digest(self, digest: str, fingerprint: str) -> ContentResult | None:
        entry = self._verdicts.get(digest, {}).get(fingerprint)
        if entry is None:
            return None
        defaults = {f.name: f.default for f in fields(ContentResult)}
        values = {name: entry.get(name, default) for name, default in defaults.items()
                  if name in entry or default is not MISSING}
        # asdict() flattened each Evidence on the way in; a verdict read back
        # must be the verdict that was stored, evidence and all.
        if "evidence" in values:
            values["evidence"] = _evidence_from_json(values["evidence"])
        return ContentResult(**values)

    def hold_reading(self, digest: str, judgment: Judgment) -> None:
        """Keep a judgment in memory for the content check about to ask
        (decision 150); never saved, and only the last few."""
        self._readings[digest] = judgment
        while len(self._readings) > _HELD_READINGS:
            self._readings.popitem(last=False)

    def held_reading(self, file: Path) -> Judgment | None:
        """The judgment :meth:`hold_reading` kept for ``file``'s bytes, if any."""
        digest = self.digest_of(file)
        return self._readings.get(digest) if digest else None

    def put(self, file: Path, fingerprint: str, result: ContentResult) -> None:
        digest = self.digest_of(file)
        if digest:
            self.put_by_digest(digest, fingerprint, result)

    def put_by_digest(self, digest: str, fingerprint: str, result: ContentResult) -> None:
        self._verdicts.setdefault(digest, {})[fingerprint] = asdict(result)
        self._learned_verdicts.add((digest, fingerprint))
        self._forgotten_digests.discard(digest)

    def prune(self, existing: set[Path]) -> None:
        """Forget files that are no longer there, and verdicts nothing there refers to."""
        keep = {self._key(p) for p in existing}
        for key in [k for k in self._files if k not in keep]:
            del self._files[key]
            self._learned_files.discard(key)
            self._forgotten_files.add(key)
        referenced = {str(memo.get("digest")) for memo in self._files.values()}
        for digest in [d for d in self._verdicts if d not in referenced]:
            del self._verdicts[digest]
            self._learned_verdicts = {(d, f) for d, f in self._learned_verdicts if d != digest}
            self._forgotten_digests.add(digest)

    def save(self) -> None:
        """Write what changed to the store, whole or nothing; a no-op for a
        cache nothing changed in, and for one built with no engagement."""
        if self._engagement is None:
            return
        if not (self._learned_files or self._learned_verdicts
                or self._forgotten_files or self._forgotten_digests):
            return
        learned: dict[str, dict[str, dict]] = {}
        for digest, fingerprint in self._learned_verdicts:
            learned.setdefault(digest, {})[fingerprint] = self._verdicts[digest][fingerprint]
        # One immediate transaction of the store's own - never store.record(),
        # which is for events - so a pass killed mid-save leaves the previous
        # rows rather than half of the new ones.
        store.remember_verdicts(
            store.connect(), self._engagement, version=CACHE_VERSION,
            memos={key: self._files[key] for key in self._learned_files},
            verdicts=learned,
            forget_paths=set(self._forgotten_files),
            forget_digests=set(self._forgotten_digests),
        )
        self._learned_files.clear()
        self._learned_verdicts.clear()
        self._forgotten_files.clear()
        self._forgotten_digests.clear()
