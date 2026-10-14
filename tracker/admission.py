"""The admission: the one rule every line of a record meets.

**The record is untrusted input** (decision 187). The engagement folder is
synced, so a line another machine wrote, or a person's editor saved, may
carry the wrong shape, an impossible value or a place outside its return's.
Every line is held to this rule before the store writes or applies it, and
before the record check, the checkpoint's judgment of a writer or
``verify`` trusts it; a line that fails it is refused by name, and its
household waits for a person. This module holds:

- :func:`_refuse_a_malformed_line`, the rule, with :func:`_line_keys_problem`,
  its judgment of the three keys the record writes on every line since
  decision 159;
- :data:`ADMISSION_VERSION`, which admission a row's applied lines were
  judged by (decision 209, R3b), raised by one whenever the rule starts
  refusing something it used to admit;
- the two sentences a refusal is told in: :data:`MALFORMED_LINE`, for a
  line of the record (decision 137), and :data:`REFUSED_CHANGE`, for a typed
  change that was never written (P292), with :data:`UNKNOWN_EVENT` and
  :data:`ALSO_IN`, the words they say;
- :data:`KIND_RETURN` and :data:`KIND_HOUSEHOLD`, the two records a line is
  judged in, and :class:`StoreError`, what a refusal raises.

**Why it is its own module** (SPEC-architecture-p3 P3.2, P323; the
architecture audit's B-1). The store is the database, and the admission is
a rule about a line. The rule has its own version and its own pin -
``tests/test_admission.py`` holds the source of every function it reaches,
and every constant they read, to :data:`ADMISSION_VERSION` - so a module
whose whole content is the rule makes "what the admission is" a file, and
the pin's roots name it. Left in the store, the rule sat among the 4,000
lines of the database it guards, and the pin's roots named the database.

**Why it sits at layer 1.** It reads the journal's words
(:mod:`tracker.ledger`) and the record's shapes (:mod:`tracker.records`),
which are layer 1, and the bounds (:mod:`tracker.bounds`), layer 0; it reads
the layout and the reasons at call time, inside
:func:`_refuse_a_malformed_line`, as it did in the store. ``RULE_LIST_FIELDS``
is the one name it takes from records by name, as the store took it.

**Who asks it.** The store, and nothing else at load time: ``record`` before
anything is appended, ``_apply`` on every line read in, the re-judging of
the lines a row already applied (decision 209, R3b), ``check`` and
``verify`` over every journal, and the checkpoint's judgment of a writer
(``_judge``), which asks :func:`_line_keys_problem`. The store imports back
the names it uses itself and calls them bare, so a stand-in on
``store._refuse_a_malformed_line`` still replaces what ``store.record``
calls. The store's own errors (``CheckpointNotMade``, ``StoreUnavailable``,
``WouldDiscard``) stay there and subclass :class:`StoreError`, so every
caller that catches ``store.StoreError`` catches a refusal as before.

The code below came from the store byte for byte, with its comments and
docstrings: where they name :func:`record`, :func:`_apply`, :func:`check`
or :func:`_judge`, they mean the store's.
"""

from __future__ import annotations

import json
from typing import NoReturn

from tracker import bounds, ledger, records
from tracker.records import RULE_LIST_FIELDS

#: Which admission (:func:`_refuse_a_malformed_line`, with
#: :func:`_line_keys_problem`) a row's applied lines were judged by
#: (decision 209, R3b). 1 was the rule as of decision 187, with decision
#: 159's line keys; 2 adds decision 190's refusals - a row's or a status's
#: cause code this version does not name, a client subfolder part that is
#: not its recorded form, and an approved letter's fingerprint that is not
#: text - raised when 209 met 190. **Raise it by one, in the same commit, whenever the
#: admission - or anything it calls - starts refusing something it used
#: to admit**: every row
#: judged by an older one then has its applied lines judged again at its
#: next sync, and a line the new rule refuses stops its household instead
#: of standing because it was applied first. ``tests/test_admission.py``
#: (``test_admission_version_changes_with_the_admission``) pins the source
#: of every function the admission reaches, and every constant they read,
#: to this number.
#: 3 adds pilot P170's refusal: a household's related list that is not a
#: list of text, or names something that is not one folder name.
#: 4 adds the form-input audit's refusals (P288, P290): a person's name
#: that is not one line of at most 1,000 characters, and a request
#: identifier or short name that hides a spoofing character (the
#: bidirectional controls and the zero-width characters; a right-to-left
#: override is the classic file-name spoof) - only that narrow set, since a
#: no-break space or a soft hyphen an ordinary paste left in an older record
#: is not a reason to stop its household. Not checked against the office's
#: real records from here: that read-only run is to be made before landing.
#: 5 adds P301's: a request's Document title that hides a spoofing character
#: (the same narrow set), since the Document names a working copy whenever
#: the row has no short name of its own.
ADMISSION_VERSION = 5

#: What a row of ``engagements`` holds the record of: one return, or one
#: household (decision 125). Both are folders with a journal, keyed by
#: path and folded by the same machinery, and this is what tells a reader
#: which of the two it has. A row is a return until a ``household_changed``
#: line says otherwise.
KIND_RETURN = "return"
KIND_HOUSEHOLD = "household"


class StoreError(RuntimeError):
    """The store could not be opened, written to, or read as one."""


#: The one sentence a line the store will not apply is refused with
#: (decision 137, L4): which line of which record, that it is malformed,
#: and what is wrong with it.
MALFORMED_LINE = ("{where}: line {seq} of the record is malformed ({event} {problem}); "
                  "the journal is not applied past it")
#: What a *typed* change the store's admission refuses is told as (P292):
#: a change, not a line. The admission is the same rule as the read path's,
#: but a line that was never written is not a corrupt record, and a person
#: who mistyped a member must not read that the journal is broken. The
#: problem phrases already read as a clause of "This change ...".
REFUSED_CHANGE = "This change {problem}; nothing was written"
#: What :data:`MALFORMED_LINE` calls an event whose name this version does
#: not know, rather than quoting it (decision 187).
UNKNOWN_EVENT = "an event this version does not know"
#: The key decision 129's hand-over intent carried the other record's half
#: under. Named here, by the one reader that still speaks of it, so that
#: the refusal says it by name (decision 132).
ALSO_IN = "also_in"


def _line_keys_problem(event: dict) -> str:
    """What is wrong with the three keys the record itself writes on every
    line since decision 159 (``ledger.LINE_KEYS``), said as the gate says a
    problem, or ``""``: a link that is not blank or a digest, a format that
    is not one this version writes, and - on a line that carries a link or
    a writer - a writer that is not a machine's name
    (``bounds.host_problem``). Part of the one admission
    (:func:`_refuse_a_malformed_line`), and asked by the checkpoint's
    judgment of a line before it trusts its writer (:func:`_judge`), so no
    line is judged this machine's or another's on a name the rule refuses.
    The link's *place* in the chain is the ledger reader's, which alone
    has the chain."""
    if ledger.LINK_KEY in event and (problem := bounds.digest_problem(event[ledger.LINK_KEY])):
        return f"carries {ledger.LINK_KEY!r} that {problem}"
    if ledger.FORMAT_KEY in event and (
            problem := bounds.count_problem(event[ledger.FORMAT_KEY], 1, ledger.RECORD_FORMAT)):
        return f"carries {ledger.FORMAT_KEY!r} that {problem}"
    if (ledger.LINK_KEY in event or ledger.HOST_KEY in event) and (
            problem := bounds.host_problem(event.get(ledger.HOST_KEY))):
        return f"carries {ledger.HOST_KEY!r} that {problem}"
    return ""


def _refuse_a_malformed_line(event: dict, seq: int, where: str, *, kind: str = KIND_RETURN,
                             written: bool = True) -> None:
    """A line that parses as JSON and names an event but carries the wrong
    shape, an impossible value or a place outside its return's is refused
    by name, before a value of it reaches a table.

    The engagement folder is synced, so a line another machine wrote is
    not trusted to be well formed: a ``rules_changed`` whose ``rules`` holds
    a string, a ``scanned`` whose statuses are a list. Left to the writers
    below, such a line surfaces as an AttributeError inside discovery and
    ends the whole practice's pass before one document is filed. Refused
    here it is one folder's problem, said in a sentence that names the
    line, and the pass goes on to the next engagement.

    **The record is untrusted input** (decision 187). A line of the right
    shape is still obeyed: a count is stored in a column SQLite bounds, a
    date is parsed by every reader, a Date Pattern is run over a client's
    pages, a step is carried out on the disk. So every value is held to the
    value rule (``tracker.records``: the bounds the editor holds a person
    to) and every location to the layout's rule for where a step of this
    return may act (``tracker.layout.place_problem``, asked at call time as
    this module already asks the layout); a household or return label must
    be one folder name (``layout.segment_problem``), because a label is
    joined onto a path; and a household's record, which has no steps,
    carries no ``moving`` line. This is the one admission, run by
    :func:`record` before anything is appended, by :func:`_apply` on every
    line read in and by :func:`check` over every journal. Each refusal names
    the field and the class of problem and never quotes the value, which is
    whatever the line said (security principle 7).

    A keyword taught or taken back is checked here for the first time with
    decision 113: until then the two tables this file writes from a line
    were the rules and the statuses, and a ``keyword_learned`` of any shape
    at all was written with ``str()`` around whatever it carried - a number
    for a keyword became the text of that number in the table while the
    journal's own fold kept the number, which is a disagreement
    :func:`check` would now report and nobody could act on. Both keyword
    events name a request and a word, both as text and neither blank, or
    the line is refused like any other.

    ``written`` says whether the line is one on disk. A line read back is
    refused as :data:`MALFORMED_LINE`, naming its place in the record; the
    admission :func:`record` runs on a change that has not been appended
    passes ``written=False`` and is refused as :data:`REFUSED_CHANGE`,
    because nothing in the record is malformed (P292).
    """
    from tracker import layout, reasons

    name = event.get(ledger.EVENT_KEY)

    # The event's name is said only when it is one this version knows: an
    # unknown one is whatever the line said (security principle 7).
    known = name if name in ledger.EVENTS | ledger.RETIRED_EVENTS else UNKNOWN_EVENT

    def refuse(problem: str) -> NoReturn:
        if not written:
            raise StoreError(REFUSED_CHANGE.format(problem=problem))
        raise StoreError(MALFORMED_LINE.format(where=where, seq=seq, event=known, problem=problem))

    def a_place(field: str, location: object, *, writes: bool, what: str = "a step",
                removes: bool = False) -> None:
        if (problem := bounds.name_problem(location)):
            refuse(f"carries {what} whose {field!r} {problem}")
        if (code := layout.place_problem(where, str(location), writes=writes,
                                         removes=removes)) is not None:
            refuse(f"carries {what} whose {field!r} is outside this return's places ({code})")

    def a_segment(field: str, label: object) -> None:
        if label in (None, ""):
            return
        if (problem := bounds.text_problem(label)):
            refuse(f"carries {field!r} that {problem}")
        if (code := layout.segment_problem(str(label))) is not None:
            refuse(f"carries {field!r} that is not one folder name ({code})")

    def a_code(field: str, code: object, what: str) -> None:
        # A cause's code is read by the letter, its holds and the review
        # card (decision 190), so it is one this version names, or none.
        if code and code not in reasons.KNOWN_CODES:
            refuse(f"carries {what} whose {field!r} is not a cause's code")

    def a_row(row: dict) -> None:
        if problem := records.entry_problem(row):
            refuse(f"carries a row whose {problem}")
        a_code("code", row.get("code"), "a row")
        # The client's subfolder is written one folder name per part, each
        # through layout.recorded_subfolder_part - the filer joins the parts
        # below the inbox with a backslash. A part that rule would change
        # ("." or "..", one holding "/", ":" or a control, one with nothing
        # visible) is a name no writer wrote: the writer and this admission
        # share the one rule (decision 190's review of the port, S2). Not
        # the household and return name rule (layout.segment_problem): since
        # decision 188 that refuses "2025", "_old" and "(scans)", which are
        # folders a client may well make in their inbox.
        subfolder = row.get("subfolder")
        if subfolder and any(layout.recorded_subfolder_part(part) != part
                             for part in str(subfolder).split("\\")):
            refuse("carries a row whose 'subfolder' is not a name as the record keeps one")
        for field in ("pbc_location", "prepared_location", "container"):
            if row.get(field):
                a_place(field, row[field], writes=False, what="a row")
        for part in str(row.get("also_filed") or "").split(records.CANDIDATE_SEP):
            if part.strip():
                a_place("also_filed", part.strip(), writes=False, what="a row")

    if ledger.AT_KEY in event and (problem := bounds.stamp_problem(event[ledger.AT_KEY])):
        refuse(f"carries {ledger.AT_KEY!r} that {problem}")
    # A person's word that a folder's name is accepted (decision 188): on
    # the two events that name a household or a return, with the one value.
    if ledger.ACCEPTED_KEY in event and (
            name not in (ledger.RULES_CHANGED, ledger.HOUSEHOLD_CHANGED)
            or event[ledger.ACCEPTED_KEY] != ledger.FOLDER_NAME_ACCEPTED):
        refuse(f"carries {ledger.ACCEPTED_KEY!r} that is not a folder's name accepted")
    if problem := _line_keys_problem(event):
        refuse(problem)
    if name in (ledger.RULES_CHANGED, ledger.RULES_IMPORTED):
        rows = event.get(ledger.RULES_KEY)
        if rows is not None and not isinstance(rows, list):
            refuse(f"carries {ledger.RULES_KEY!r} that is not a list")
        for row in rows or []:
            if not isinstance(row, dict):
                refuse("carries a rule that is not a row")
            # A list field that is not a list of words (decision 137, L4):
            # a string there would be read as one keyword per letter.
            for field_name in sorted(RULE_LIST_FIELDS):
                if problem := records.word_list_problem(row.get(field_name)):
                    refuse(f"carries a rule whose {field_name!r} {problem}")
            if problem := records.rule_row_problem(row):
                refuse(f"carries a rule whose {problem}")
        removed = event.get(ledger.REMOVED_KEY)
        if removed is not None and not isinstance(removed, list):
            refuse(f"carries {ledger.REMOVED_KEY!r} that is not a list")
        for identifier in removed or []:
            if bounds.text_problem(identifier):
                refuse("names a removed identifier that is not one line of text")
        info = event.get(ledger.INFO_KEY)
        if info is not None and not isinstance(info, dict):
            refuse(f"carries {ledger.INFO_KEY!r} that is not a mapping")
        # The return's people (decision 128). The journal is a synced file
        # somebody may have opened, and a person of a kind nothing knows or
        # a spelling of one word is a line the name check would either pass
        # over or misfile on - so it is refused here, by the record's own
        # reader, rather than written into a column a later pass trusts.
        if isinstance(info, dict) and "people" in info:
            try:
                records.people_from_json(info["people"])
            except (ValueError, TypeError, json.JSONDecodeError):
                refuse("carries people this version cannot read")
        if isinstance(info, dict):
            if problem := records.info_problem(info):
                refuse(f"carries details whose {problem}")
            a_segment("household", info.get("household"))
            a_segment("return_name", info.get("return_name"))
    elif name in ledger.ROW_EVENTS:
        # An index row (decision 137, L4). Its key is the row's identity and
        # its row is a mapping; left to the fold, a row that is a string or
        # a key that is missing ended the whole pass inside discovery.
        key = event.get(ledger.KEY_KEY)
        if not isinstance(key, str) or not key:
            refuse(f"carries no {ledger.KEY_KEY!r}")
        if problem := bounds.name_problem(key):
            refuse(f"carries {ledger.KEY_KEY!r} that {problem}")
        if not isinstance(event.get(ledger.ROW_KEY), dict):
            refuse(f"carries {ledger.ROW_KEY!r} that is not a row")
        leaving = event.get(ledger.WAS_KEY)
        if leaving is not None and bounds.name_problem(leaving):
            refuse(f"carries {ledger.WAS_KEY!r} that is not a location")
        a_row(event[ledger.ROW_KEY])
    elif name == ledger.SCANNED:
        statuses = event.get(ledger.STATUSES_KEY)
        if statuses is not None and not isinstance(statuses, dict):
            refuse(f"carries {ledger.STATUSES_KEY!r} that is not a mapping")
        for identifier, stored in (statuses or {}).items():
            if bounds.text_problem(identifier):
                refuse("carries a status for an identifier that is not one line of text")
            if not isinstance(stored, dict):
                refuse("carries a status that is not a mapping")
            if problem := records.status_problem(stored):
                refuse(f"carries a status whose {problem}")
            for code in records.split_codes(stored.get("note_codes")):
                a_code("note_codes", code, "a status")
    elif name == ledger.MOVING:
        # The intent is what a later pass will finish a half-made move
        # from, so its shape is checked here rather than trusted in the
        # middle of a recovery with a file already moved: the operations
        # are a list, each one names what it does, where from and - unless
        # it is a stand-down - where to, and the row it carries is a row.
        # Since decision 187 every place a step names is one this return's
        # steps may act in, and a household's record - which has no steps -
        # carries none.
        if kind == KIND_HOUSEHOLD:
            refuse("in a household's record, which has no steps")
        key = event.get(ledger.KEY_KEY)
        if key is not None and bounds.name_problem(key):
            refuse(f"carries {ledger.KEY_KEY!r} that is not one line of text")
        ops = event.get(ledger.OPS_KEY)
        if not isinstance(ops, list):
            refuse(f"carries {ledger.OPS_KEY!r} that is not a list")
        for op in ops:
            if not isinstance(op, dict):
                refuse("carries an operation that is not one")
            step = op.get(ledger.OP_KEY)
            if step not in (ledger.OP_MOVE, ledger.OP_COPY, ledger.OP_REMOVE):
                refuse("carries an operation this version does not know")
            if not isinstance(op.get(ledger.FROM_KEY), str):
                refuse(f"carries a {step} with no {ledger.FROM_KEY!r}")
            if step != ledger.OP_REMOVE and not isinstance(op.get(ledger.TO_KEY), str):
                refuse(f"carries a {step} with no {ledger.TO_KEY!r}")
            if not isinstance(op.get(ledger.DIGEST_KEY, ""), str):
                refuse(f"carries a {step} whose {ledger.DIGEST_KEY!r} is not text")
            if problem := bounds.digest_problem(op.get(ledger.DIGEST_KEY, "")):
                refuse(f"carries a {step} whose {ledger.DIGEST_KEY!r} {problem}")
            named = (ledger.FROM_KEY,) if step == ledger.OP_REMOVE else (ledger.FROM_KEY, ledger.TO_KEY)
            for field, (location, writes) in zip(named, ledger.op_ends(op), strict=True):
                a_place(field, location, writes=writes, removes=step == ledger.OP_REMOVE)
        row = event.get(ledger.ROW_KEY)
        if row is not None and not isinstance(row, dict):
            refuse(f"carries {ledger.ROW_KEY!r} that is not a row")
        if isinstance(row, dict):
            a_row(row)
        leaving = event.get(ledger.WAS_KEY)
        if leaving is not None and bounds.name_problem(leaving):
            refuse(f"carries {ledger.WAS_KEY!r} that is not a location")
        also = event.get(ledger.ALSO_KEY)
        if also is not None and not isinstance(also, list):
            refuse(f"carries {ledger.ALSO_KEY!r} that is not a list")
        for one in also or []:
            # What travels with the row is recorded as it stands, so it is
            # admitted as it stands - by this same rule, now.
            if not isinstance(one, dict) or one.get(ledger.EVENT_KEY) not in ledger.EVENTS:
                refuse(f"carries {ledger.ALSO_KEY!r} holding something that is not an event")
            _refuse_a_malformed_line(one, seq, where, kind=kind, written=written)
        reason = event.get(ledger.REASON_KEY)
        if reason is not None and bounds.text_problem(reason, long=True):
            refuse(f"carries {ledger.REASON_KEY!r} that is not text")
        # Decision 129's intent carried the events it would write into
        # another return's record. Decision 132 retired that: nothing ever
        # writes into another record, and an intent whose second half this
        # version cannot write must not be recovered as if it had none.
        if ALSO_IN in event:
            refuse(f"carries {ALSO_IN!r}, the other record's half of a decision 129 "
                   f"hand-over, which this version does not write; finish it with the "
                   f"version that began it")
    elif name == ledger.MOVE_ABANDONED:
        key = event.get(ledger.KEY_KEY)
        if not isinstance(key, str) or not key or bounds.name_problem(key):
            refuse(f"carries no {ledger.KEY_KEY!r}")
    elif name == ledger.RELEASED:
        # A release names the row it takes out and says where it went -
        # and carries no row, because there is none left to carry.
        if not isinstance(event.get(ledger.KEY_KEY), str) or not event.get(ledger.KEY_KEY):
            refuse(f"carries no {ledger.KEY_KEY!r}")
        if ledger.ROW_KEY in event:
            refuse(f"carries {ledger.ROW_KEY!r}; a release carries no row")
        if bounds.text_problem(event.get(ledger.REASON_KEY, ""), long=True):
            refuse(f"carries {ledger.REASON_KEY!r} that is not text")
    elif name in (ledger.KEYWORD_LEARNED, ledger.KEYWORD_UNLEARNED):
        for key in (ledger.IDENTIFIER_KEY, ledger.KEYWORD_KEY):
            value = event.get(key)
            if not isinstance(value, str):
                refuse(f"carries {key!r} that is not text")
            if not value:
                refuse(f"carries a blank {key!r}")
            if problem := bounds.text_problem(value):
                refuse(f"carries {key!r} that {problem}")
    elif name in (ledger.DRAFTED, ledger.DRAFT_APPROVED):
        # A week's draft (decision 118): what was asked and held, the file,
        # its fingerprint and the stage - each read back by the app - and,
        # on an approval, the fingerprint of the letter approved (decision
        # 190), which the pass compares.
        for key in (ledger.ASKED_KEY, ledger.HELD_KEY):
            if key in event and (problem := bounds.text_list_problem(event[key])):
                refuse(f"carries {key!r} that {problem}")
        for key in (ledger.FILE_KEY, ledger.FINGERPRINT_KEY, ledger.TEXT_FINGERPRINT_KEY):
            if key in event and (problem := bounds.text_problem(event[key])):
                refuse(f"carries {key!r} that {problem}")
        if event.get(ledger.STAGE_KEY) is not None and (
                problem := bounds.count_problem(event[ledger.STAGE_KEY], 0, bounds.MAX_STAGE)):
            refuse(f"carries {ledger.STAGE_KEY!r} that {problem}")
    elif name == ledger.HOUSEHOLD_CHANGED:
        # The household's details travel exactly as a return's do, so the
        # line is checked exactly as one: a mapping of fields, and the one
        # field that is a list of words is a list of words.
        household = event.get(ledger.HOUSEHOLD_KEY)
        if household is not None and not isinstance(household, dict):
            refuse(f"carries {ledger.HOUSEHOLD_KEY!r} that is not a mapping")
        members = (household or {}).get("members")
        # A hand-written line naming one person is read as one member
        # (``records.household_from_json``) rather than refused: the
        # journal is a synced file somebody may have opened. A list
        # holding something that is not a name is not a members list.
        if members is not None and not isinstance(members, (list, str)):
            refuse("carries 'members' that is neither a list nor a name")
        for member in members if isinstance(members, list) else []:
            if not isinstance(member, str):
                refuse("names a member that is not text")
        # The feed list (decision 129). A feed naming no household or no
        # return line points at nothing a pass could resolve, so it is
        # refused here by the record's own reader rather than written into
        # a column the sort would later read as a route.
        if isinstance(household, dict) and "feeds" in household:
            try:
                feeds = records.feeds_from_json(household["feeds"])
            except (ValueError, TypeError, json.JSONDecodeError):
                refuse("carries feeds this version cannot read")
            for feed in feeds:
                a_segment("feeds.household", feed.household)
                a_segment("feeds.return_name", feed.return_name)
        # The related households (pilot P170): a list of names, each one
        # household folder's name, or the line is not one this version
        # writes.
        if isinstance(household, dict) and "related" in household:
            related = household["related"]
            if not isinstance(related, list) or not all(isinstance(one, str) for one in related):
                refuse("carries 'related' that is not a list of household names")
            for one in related:
                a_segment("related", one)
        if isinstance(household, dict):
            if problem := records.household_problem(household):
                refuse(f"carries details whose {problem}")
            a_segment("name", household.get("name"))
    elif name == ledger.SHARING_CONFIRMED:
        # The firm's word, dated, and nothing else (decision 126): the
        # stamp is the whole of it. A line carrying a payload is either a
        # newer version's or a hand-written one, and either way this
        # version would be storing something it cannot fold - so it is
        # refused by name here rather than silently kept in the events
        # table where a reader would later trust it.
        # The three keys the record itself writes on every line since
        # decision 159 (``ledger.LINE_KEYS``) are the line's, not a payload.
        if set(event) - {ledger.EVENT_KEY, ledger.AT_KEY} - ledger.LINE_KEYS:
            refuse("carries fields; it carries nothing")
