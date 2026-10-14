"""Tests for tracker/admission.py - the one rule every line of a record meets.

The admission's own file holds the rule, and this file holds its pin:
:data:`ADMISSION_PIN`, the digest of every part the admission reaches -
each package function ``_refuse_a_malformed_line`` and
``_line_keys_problem`` call, at any depth, and every constant they read -
by the version it is (decision 209, R3b). With it are the walker that finds
the parts (:func:`admission_closure`, :func:`names_bound_in`) and the walker's
own tests. A part that changes fails
:func:`test_admission_version_changes_with_the_admission`, which names it and
says which of two things to do.

And the tests that ask the admission directly, with no store: a moving line
in a household's record, the accepted key's one value, and a related list
that is not folder names. The tests that drive the admission through the
store's door - ``record``, ``catch_up``, ``check`` - or take the store's
fixtures stay in ``tests/test_store.py``: they test the door's wiring as much
as the rule.

All of it came from ``tests/test_store.py`` with P323 (SPEC-architecture-p3
P3.2), cut and pasted. The bodies still read the admission's names through
the store, which holds them by import, until P3.9 reads them here.
"""

from __future__ import annotations

import ast

import pytest

from tracker import ledger, store


def test_a_moving_line_in_a_households_record_is_refused():
    """A household has no steps, so its record carries none."""
    from tracker.layout import PRIVATE_TREE

    moving = ledger.new(ledger.MOVING, key="k", ops=[], by=ledger.BY_PASS)
    with pytest.raises(store.StoreError, match="in a household's record, which has no steps"):
        store._refuse_a_malformed_line(moving, 2, f"{PRIVATE_TREE}/Smith Family",
                                       kind=store.KIND_HOUSEHOLD)
    store._refuse_a_malformed_line(moving, 2, f"{PRIVATE_TREE}/Smith Family/2025/1040 - Smith",
                                   kind=store.KIND_RETURN)


#: The admission, part by part (:func:`admission_closure`), as the first 16
#: hexadecimal characters of each part's SHA-256, by the version it is. A
#: change to any part moves its digest; the test below names every part
#: that moved and says which of two things to do.
#: Version 5 (P301) moved two parts from version 4's: ``records.rule_row_fault``,
#: which now reads the Document, and the new ``records.document_problem``.
#: Version 5 was pinned again, not raised, when the walker stopped following
#: a name the function binds itself (SPEC-architecture J1, finding B-2): 30 parts the
#: admission never runs - 19 of settings', the store's ``kind`` and ``statuses``
#: and what only they reach - left it, and none joined. No rule changed.
#: Pinned again under 5 when P2.4 moved the value rule's bounds to tracker.bounds:
#: their keys follow the module, and a bound a function left in records also reads
#: by name (TEXT_BOUNDS) is keyed by each. No digest changed.
#: Pinned again under 5 when P2.13 pointed the store's reads at tracker.bounds:
#: the keys follow the module (``records.MAX_STAGE`` is ``bounds.MAX_STAGE``, the
#: same digest), and the two admission functions' digests moved only by
#: ``records.`` becoming ``bounds.`` in their source. No rule changed.
#: Pinned again under 5 when P3.1 typed the admission's refusal NoReturn and
#: split_codes' parameter str | None: two annotations, no rule changed.
#: Pinned again under 5 when P3.2 moved the admission to tracker.admission: nine keys
#: follow the module, no digest changed.
ADMISSION_PIN: dict[int, dict[str, str]] = {2: {
    "tracker.layout.CLIENTS": "3b8264d65abeec66",
    "tracker.layout.CLIENTS_TREE": "488530d6164e0dd6",
    "tracker.layout.CLIENT_HOUSEHOLD": "2c784f90e61ac610",
    "tracker.layout.HOUSEHOLD": "8de5259835758e72",
    "tracker.layout.INBOX": "d9c4d1b7a70cb6f2",
    "tracker.layout.INBOX_DIR_NAME": "919dcb2c2a774098",
    "tracker.layout.IN_INBOX": "fc74c5d3e9ae9444",
    "tracker.layout.IN_OPENED": "633c5d64586b470a",
    "tracker.layout.IN_ORIGINALS": "20496354d6f1b26b",
    "tracker.layout.IN_RETURN": "155a1bfd542aaa0d",
    "tracker.layout.LOOK_ALIKES": "54c49454cf2f5689",
    "tracker.layout.MISPLACED": "b8ca0cd70606f6d7",
    "tracker.layout.NAMELESS": "1bad7ce20105964a",
    "tracker.layout.NAME_COMPATIBILITY": "ec65d3d71fd72b3d",
    "tracker.layout.NAME_DEVICE": "620b97404635bcec",
    "tracker.layout.NAME_EMPTY": "aa82b128dcf1c993",
    "tracker.layout.NAME_FIRST_CHARACTER": "bd62babfb5664dc1",
    "tracker.layout.NAME_ILLEGAL": "305df1e9431d3276",
    "tracker.layout.NAME_INVISIBLE": "2401333e2c513d23",
    "tracker.layout.NAME_LAYOUT_WORD": "978aa80c1fbb2b52",
    "tracker.layout.NAME_MAX_CHARS": "48449a14a4ff7d79",
    "tracker.layout.NAME_SCRIPTS": "3de824b29b62bb49",
    "tracker.layout.NAME_TOO_LONG": "7a5e00d8497fbe2d",
    "tracker.layout.NAME_TRAILING": "7fafe7cda3544c33",
    "tracker.layout.OPENED": "33bdc49eaabcbced",
    "tracker.layout.OPENED_DIR_NAME": "5ef673f341874a6f",
    "tracker.layout.ORIGINALS": "535087da73c5868d",
    "tracker.layout.OUTSIDE": "2f2e7ba21585ff28",
    "tracker.layout.PRIVATE": "68a262e0c0fb929f",
    "tracker.layout.PRIVATE_TREE": "27c7f0479a0c896f",
    "tracker.layout.RETURN": "08633b69eed18c1b",
    "tracker.layout.ROOT": "11ccb349ede85740",
    "tracker.layout.STEP_ABOVE_ROOT": "1385e84ae7f46b2d",
    "tracker.layout.STEP_ABSOLUTE": "f523898e69fbc750",
    "tracker.layout.STEP_BLANK": "a4e9e11cd18fd75b",
    "tracker.layout.STEP_CLIENT_TREE": "5f51b518f9526119",
    "tracker.layout.STEP_NOT_A_PLACE": "d1aa6f26861ccbee",
    "tracker.layout.STEP_NOT_A_RETURN": "1e7d015db6355c80",
    "tracker.layout.STEP_OTHER_HOUSEHOLD": "a0f05df5e57d787b",
    "tracker.layout.STEP_OTHER_YEAR": "7994492387ba5850",
    "tracker.layout.WINDOWS_ILLEGAL_CHARS": "0852803faa2a184a",
    "tracker.layout.WINDOWS_RESERVED_NAMES": "99bf9abac32f89f2",
    "tracker.layout.WINDOWS_RESERVED_NAMES_TEXT": "c9d9ad8d312ac5a8",
    "tracker.layout.YEAR": "74c6b2f8351bcc6d",
    "tracker.layout._ASCII_LOOK_ALIKES": "5333fd34ff62ce29",
    "tracker.layout._IGNORABLE_CODES": "999fbf22e2feeb49",
    "tracker.layout._INVISIBLE_CATEGORIES": "bb62d3360fd14a4d",
    "tracker.layout._LAYOUT_WORD_KEYS": "a6d47e2209691833",
    "tracker.layout._ONE_SCRIPT": "17235d2097441c94",
    "tracker.layout._character": "bd5a8cc4e82855fc",
    "tracker.layout._parts": "a2847013a67202c7",
    "tracker.layout._script": "f890f9bb62d24799",
    "tracker.layout.is_invisible": "2b17b033d61a3df2",
    "tracker.layout.is_reserved_name": "3ee144cf8f5c095d",
    "tracker.layout.is_year_folder": "c89c110db3cb607d",
    "tracker.layout.name_key": "749d88cbbd6eb3c3",
    "tracker.layout.parts_below": "522d9b67dfe50b6a",
    "tracker.layout.place_of": "fc1a78ab7179dd32",
    "tracker.layout.place_problem": "2e94883c849c9d08",
    "tracker.layout.recorded_name": "84bfdf3a851f4652",
    "tracker.layout.recorded_subfolder_part": "50620c73d7ae6dab",
    "tracker.layout.root_of": "a6c7013a757965b4",
    "tracker.layout.segment_problem": "13e273e844d2cc2b",
    "tracker.ledger.ACCEPTED_KEY": "f4764fc7a8ddd588",
    "tracker.ledger.ALSO_KEY": "da42922852e5dfcd",
    "tracker.ledger.ASKED_KEY": "46da5b49eea2fbee",
    "tracker.ledger.AT_KEY": "22eb1fa0c521db09",
    "tracker.ledger.DIGEST_KEY": "889a0f98aa32537e",
    "tracker.ledger.DRAFTED": "ef02a62df7dc350b",
    "tracker.ledger.DRAFT_APPROVED": "41bf68b11dd88d88",
    "tracker.ledger.EVENTS": "c6d719a66bc0b51d",
    "tracker.ledger.EVENT_KEY": "9e0d5d1c8d94a5b6",
    "tracker.ledger.FILE_KEY": "0efde3f4308de780",
    "tracker.ledger.FINGERPRINT_KEY": "7df2d13d670e5ed4",
    "tracker.ledger.FOLDER_NAME_ACCEPTED": "b7b92a8807e8bbf9",
    "tracker.ledger.FORMAT_KEY": "04fc6c808adf51ac",
    "tracker.ledger.FROM_KEY": "8ecb478c3dc0d3ae",
    "tracker.ledger.HELD_KEY": "85c4d432c47707ee",
    "tracker.ledger.HOST_KEY": "e293b75405af70cd",
    "tracker.ledger.HOUSEHOLD_CHANGED": "783c776c223a869f",
    "tracker.ledger.HOUSEHOLD_KEY": "8de5259835758e72",
    "tracker.ledger.IDENTIFIER_KEY": "123a87f051936a7e",
    "tracker.ledger.INFO_KEY": "ef3370879a96cf2e",
    "tracker.ledger.KEYWORD_KEY": "a51a9ff6a628d820",
    "tracker.ledger.KEYWORD_LEARNED": "7a5d6590fc40e09a",
    "tracker.ledger.KEYWORD_UNLEARNED": "ce11d4a4c4da44a9",
    "tracker.ledger.KEY_KEY": "632a3e84412d6ea8",
    "tracker.ledger.LINE_KEYS": "bfa2973d92dd93ad",
    "tracker.ledger.LINK_KEY": "67b4e6e1e90cbc98",
    "tracker.ledger.MOVE_ABANDONED": "a11db9ac01cd5285",
    "tracker.ledger.MOVING": "d290155f3097fcde",
    "tracker.ledger.OPS_KEY": "2c35289e43246c9f",
    "tracker.ledger.OP_COPY": "477c02e96b3c4061",
    "tracker.ledger.OP_KEY": "b27b68850018781c",
    "tracker.ledger.OP_MOVE": "c4a4adaf72f566c1",
    "tracker.ledger.OP_REMOVE": "e8c2c1465f168081",
    "tracker.ledger.REASON_KEY": "ffa78aeaf553b544",
    "tracker.ledger.RECORD_FORMAT": "6b86b273ff34fce1",
    "tracker.ledger.RELEASED": "81acce4087249f66",
    "tracker.ledger.REMOVED_KEY": "760f3c525ed93b07",
    "tracker.ledger.RETIRED_EVENTS": "ca06b9854a7990f9",
    "tracker.ledger.ROW_EVENTS": "b53cc1cb7387825b",
    "tracker.ledger.ROW_KEY": "e4d99047ca6a3721",
    "tracker.ledger.RULES_CHANGED": "e4535fc89d8ef96d",
    "tracker.ledger.RULES_IMPORTED": "cddb10ca0e4c2100",
    "tracker.ledger.RULES_KEY": "a29e7581476cd7ad",
    "tracker.ledger.SCANNED": "7e17f4790bff13d5",
    "tracker.ledger.SHARING_CONFIRMED": "c8027ef3eb13f5e3",
    "tracker.ledger.STAGE_KEY": "874095181f94a63d",
    "tracker.ledger.STATUSES_KEY": "18c7785691d58b80",
    "tracker.ledger.TEXT_FINGERPRINT_KEY": "0db6b5095dc3896e",
    "tracker.ledger.TO_KEY": "e28f3243b469e21d",
    "tracker.ledger.WAS_KEY": "1d383f963e096e21",
    "tracker.ledger.op_ends": "a4e5e845ab4c8deb",
    "tracker.reasons.KNOWN_CODES": "4ad3f21d00c7f8e5",
    "tracker.records.BLANK_BOUNDS": "cec8e55a02712202",
    "tracker.records.CANDIDATE_SEP": "3c01b9ef061065a0",
    "tracker.records.COUNT_BOUNDS": "66fbd6100ed5379b",
    "tracker.records.DATE_BOUNDS": "14ca9c3c8c63da08",
    "tracker.records.DATE_FIELDS": "f0aaa0cb84de4063",
    "tracker.records.DATE_PATTERN_ALTERNATES": "6d1924b141e16df5",
    "tracker.records.DATE_PATTERN_BOUND_MAX": "f5ca38f748a1d6ea",
    "tracker.records.DATE_PATTERN_COST_MAX": "b552e632666bbf61",
    "tracker.records.DATE_PATTERN_MAX": "27badc983df1780b",
    "tracker.records.DATE_PATTERN_NESTED": "7b1330f7983d042e",
    "tracker.records.DATE_PATTERN_NOT_A_REGEX": "a158e00f56bf6ba7",
    "tracker.records.DATE_PATTERN_OPEN_MAX": "6b86b273ff34fce1",
    "tracker.records.DATE_PATTERN_OPEN_WIDTH": "0604cd3138feed20",
    "tracker.records.DATE_PATTERN_REFERS_BACK": "25a2057a272ff94c",
    "tracker.records.DATE_PATTERN_REPEATS_MAX": "4e07408562bedb8b",
    "tracker.records.DATE_PATTERN_TOO_COSTLY": "3e2d8a14b8d6a5a6",
    "tracker.records.DATE_PATTERN_TOO_LONG": "02239fb8cdceefd8",
    "tracker.records.DATE_PATTERN_TOO_MANY": "ba11446dcfecda24",
    "tracker.records.DATE_PATTERN_TOO_MANY_OPTIONAL": "eb3c2f5771c5d09f",
    "tracker.records.DATE_PATTERN_TOO_MANY_WAYS": "a322d9761b272d91",
    "tracker.records.DATE_PATTERN_TOO_OPEN": "fcaa25330d84e4d0",
    "tracker.records.DATE_PATTERN_TOO_WIDE": "f7af15030b186a35",
    "tracker.records.DATE_PATTERN_VARIABLE_MAX": "2c624232cdd22177",
    "tracker.records.DATE_PATTERN_WAYS_MAX": "ca902d4a8acbdea1",
    "tracker.records.DATE_YEAR_MAX": "4f5131ea0c5a3e7f",
    "tracker.records.DATE_YEAR_MIN": "e41d64db5703c644",
    "tracker.records.DIGEST_BOUNDS": "677bb2233d3c0d23",
    "tracker.records.FEED_REFUSED": "d601e93b18987f24",
    "tracker.records.FLAG_BOUNDS": "2bfdeea59997694f",
    "tracker.records.HOST_BOUNDS": "72219f0e2bcda110",
    "tracker.records.HOST_MAX": "a68b412c4282555f",
    "tracker.records.LONG_TEXT_BOUNDS": "3de4da1af0b30ef2",
    "tracker.records.LONG_TEXT_MAX": "876c9b16254e157d",
    "tracker.records.MAX_EXPECTED_COUNT": "888df25ae3577242",
    "tracker.records.MAX_FILE_COUNT": "888df25ae3577242",
    "tracker.records.MAX_ROW": "888df25ae3577242",
    "tracker.records.MAX_ROW_SIZE_KB": "02bfbb85ecfba2af",
    "tracker.records.MAX_SIZE_KB": "50b4b069390c1d79",
    "tracker.records.MAX_STAGE": "19581e27de7ced00",
    "tracker.records.MIN_EXPECTED_COUNT": "6b86b273ff34fce1",
    "tracker.records.MIN_SIZE_KB_FLOOR": "5feceb66ffc86f38",
    "tracker.records.MIN_SPELLING_WORDS": "d4735e3a265e16ee",
    "tracker.records.NAME_BOUNDS": "fab0c3e598d1038c",
    "tracker.records.NUMBER_BOUNDS": "d7d2f825d092e462",
    "tracker.records.OVERRIDE_BOUNDS": "22a3650c5fc6e021",
    "tracker.records.PERSON_KINDS": "11ac10e2383de5cc",
    "tracker.records.RULE_FLAG_FIELDS": "c500b9a01ed742b3",
    "tracker.records.RULE_LIST_FIELDS": "8b3d25ca8662bd02",
    "tracker.records.SHORT_TITLE_MAX": "f5ca38f748a1d6ea",
    "tracker.records.STAMP_BOUNDS": "7c7cf7f161dd3671",
    "tracker.records.STAMP_YEAR_MIN": "ad1f3889d0032e7c",
    "tracker.records.TEXT_BOUNDS": "ce369c3539b412af",
    "tracker.records.TEXT_LIST_BOUNDS": "196f901bd54f0f8c",
    "tracker.records.TEXT_MAX": "40510175845988f1",
    "tracker.records.WAITS_FOR_ANSWERS": "f0615f5bcc293884",
    "tracker.records.WAITS_FOR_BOUNDS": "6f57ee0ee5ca0bbc",
    "tracker.records.WAITS_FOR_SEP": "de9881cacd5c858e",
    "tracker.records.WINDOWS_ILLEGAL_CHARS": "0852803faa2a184a",
    "tracker.records.WINDOWS_ILLEGAL_CHARS_TEXT": "e4b68ca2e1ff6518",
    "tracker.records.WINDOWS_RESERVED_NAMES_TEXT": "c9d9ad8d312ac5a8",
    "tracker.records.YEAR_MAX": "1aaf97e300d50bac",
    "tracker.records.YEAR_MIN": "e41d64db5703c644",
    "tracker.records._ENTRY_LONG_TEXT": "108c25e4b80db4c6",
    "tracker.records._ENTRY_NAMES": "5980f2d1176281a2",
    "tracker.records._ENTRY_TEXT": "68e0df1c43ff5282",
    "tracker.records._HEX_DIGEST": "286fa658d6b7911b",
    "tracker.records._INFO_LONG_TEXT": "69674950c21f7eae",
    "tracker.records._INFO_TEXT": "cbdf6035c202636d",
    "tracker.records._ISO_DATE": "3ca3c91bdac79395",
    "tracker.records._ONE_LINE_REFUSED": "f912910f93b16ff7",
    "tracker.records._REFERS_BACK": "6a5a714c08b4ca99",
    "tracker.records._REPEATS": "0429e0cc33348e07",
    "tracker.records._RULE_TEXT": "4dbd8ce696bb0f8e",
    "tracker.records._STAMP": "36e48aca67f1ef08",
    "tracker.records._field": "190cfe96c598c222",
    "tracker.records._first": "afafd6bbd03b4d5a",
    "tracker.records._is_number": "b55a28bc0ae446c7",
    "tracker.records._walk": "58be230437faa42c",
    "tracker.records._ways": "73d93a78035726fd",
    "tracker.records._width": "971b31440953101e",
    "tracker.records.count_problem": "89257d6ec9bdd711",
    "tracker.records.date_pattern_problem": "fa02803a1a99c545",
    "tracker.records.date_problem": "0bf005c4a966d7f8",
    "tracker.records.digest_problem": "217cc9c49f9a6e20",
    "tracker.records.entry_problem": "a79ea9e62a85223a",
    "tracker.records.feed_from_json": "b2e5148af638d97c",
    "tracker.records.feeds_from_json": "b108fd6888f95ec6",
    "tracker.records.flag_problem": "1082a26284942f5c",
    "tracker.records.format_waits_for": "a9f50749433f46ce",
    "tracker.records.host_problem": "7d98945bc57bd382",
    "tracker.records.household_problem": "1188cd47c1c4b37f",
    "tracker.records.identifier_problem": "f8ee13a768acea53",
    "tracker.records.info_problem": "a14147da699ad792",
    "tracker.records.is_a_spelling": "9872f0754c1f928d",
    "tracker.records.name_parts": "2fb3aa450c490a16",
    "tracker.records.name_problem": "435e57a752b587c2",
    "tracker.records.name_words": "888ff2df30e14d73",
    "tracker.records.number_problem": "b8e64da5f5e20b1a",
    "tracker.records.parse_waits_for": "fe2da49df5b9f8ce",
    "tracker.records.people_from_json": "f450ab3614ffbb7c",
    "tracker.records.person_from_json": "7e7a8fed1cb8c27a",
    "tracker.records.received_problem": "2fe803ce248363ca",
    "tracker.records.rule_row_fault": "e63ac46148a8c37f",
    "tracker.records.rule_row_problem": "bfbfa65df0936781",
    "tracker.records.short_title_problem": "cee1ccd1dc44eedd",
    "tracker.records.split_codes": "ac4f6152bb7ad6ee",
    "tracker.records.stamp_problem": "2d66f0bfa7df3a4f",
    "tracker.records.status_from_json": "18fe07346092ffad",
    "tracker.records.status_problem": "0a4507873e497b78",
    "tracker.records.text_list_problem": "5c6a2aa819ebb0cf",
    "tracker.records.text_problem": "3af72e89b781e54e",
    "tracker.records.waits_for_problem": "463d041ef7fa9219",
    "tracker.records.word_list_problem": "64d72805fbba0527",
    "tracker.settings.ENV_SETTINGS_DIR": "b654987367e5160b",
    "tracker.settings.KEY_CLIENTS_ROOT": "3b8f548e07b39dbf",
    "tracker.settings.SETTINGS_FILENAME": "ddf9dfc4d857c464",
    "tracker.settings._SETTINGS_HELD": "6c71e2207cf64f31",
    "tracker.settings._held": "379fbddee2b4b987",
    "tracker.settings._read": "9a09d08e256be9de",
    "tracker.settings.clients_root": "8fbaef8c43dcb573",
    "tracker.settings.resolved": "e42941a71b19eac8",
    "tracker.settings.settings_dir": "0468e63b780056c5",
    "tracker.settings.settings_path": "8a79e7ca2ca7f66a",
    "tracker.store.ALSO_IN": "f91e15416cd81c44",
    "tracker.store.KIND_HOUSEHOLD": "8de5259835758e72",
    "tracker.store.KIND_RETURN": "08633b69eed18c1b",
    "tracker.store.MALFORMED_LINE": "7af462b999c9799b",
    "tracker.store.RULE_LIST_FIELDS": "8b3d25ca8662bd02",
    "tracker.store.STATUS_COLUMNS": "072efbf3b12ac0bd",
    "tracker.store.UNKNOWN_EVENT": "099e89ceccd1e5e9",
    "tracker.store._engagement_row": "e7254ccc28e41fad",
    "tracker.store._line_keys_problem": "0d6016b3dab0c236",
    "tracker.store._positional_root": "f2fce089ca54ef5a",
    "tracker.store._recorded_root_over": "6447409cff0d940e",
    "tracker.store._refuse_a_malformed_line": "3691dbc864c8530f",
    "tracker.store.engagement_path": "354415605ca56669",
    "tracker.store.key_root": "13d66deeca51405a",
    "tracker.store.kind": "c5781c37870424f8",
    "tracker.store.statuses": "d99730d725daf407",
}, 3: {
    "tracker.layout.CLIENTS": "3b8264d65abeec66",
    "tracker.layout.CLIENTS_TREE": "488530d6164e0dd6",
    "tracker.layout.CLIENT_HOUSEHOLD": "2c784f90e61ac610",
    "tracker.layout.HOUSEHOLD": "8de5259835758e72",
    "tracker.layout.INBOX": "d9c4d1b7a70cb6f2",
    "tracker.layout.INBOX_DIR_NAME": "919dcb2c2a774098",
    "tracker.layout.IN_INBOX": "fc74c5d3e9ae9444",
    "tracker.layout.IN_OPENED": "633c5d64586b470a",
    "tracker.layout.IN_ORIGINALS": "20496354d6f1b26b",
    "tracker.layout.IN_RETURN": "155a1bfd542aaa0d",
    "tracker.layout.LOOK_ALIKES": "54c49454cf2f5689",
    "tracker.layout.MISPLACED": "b8ca0cd70606f6d7",
    "tracker.layout.NAMELESS": "1bad7ce20105964a",
    "tracker.layout.NAME_COMPATIBILITY": "ec65d3d71fd72b3d",
    "tracker.layout.NAME_DEVICE": "620b97404635bcec",
    "tracker.layout.NAME_EMPTY": "aa82b128dcf1c993",
    "tracker.layout.NAME_FIRST_CHARACTER": "bd62babfb5664dc1",
    "tracker.layout.NAME_ILLEGAL": "305df1e9431d3276",
    "tracker.layout.NAME_INVISIBLE": "2401333e2c513d23",
    "tracker.layout.NAME_LAYOUT_WORD": "978aa80c1fbb2b52",
    "tracker.layout.NAME_MAX_CHARS": "48449a14a4ff7d79",
    "tracker.layout.NAME_SCRIPTS": "3de824b29b62bb49",
    "tracker.layout.NAME_TOO_LONG": "7a5e00d8497fbe2d",
    "tracker.layout.NAME_TRAILING": "7fafe7cda3544c33",
    "tracker.layout.OPENED": "33bdc49eaabcbced",
    "tracker.layout.OPENED_DIR_NAME": "5ef673f341874a6f",
    "tracker.layout.ORIGINALS": "535087da73c5868d",
    "tracker.layout.OUTSIDE": "2f2e7ba21585ff28",
    "tracker.layout.PRIVATE": "68a262e0c0fb929f",
    "tracker.layout.PRIVATE_TREE": "27c7f0479a0c896f",
    "tracker.layout.RETURN": "08633b69eed18c1b",
    "tracker.layout.ROOT": "11ccb349ede85740",
    "tracker.layout.STEP_ABOVE_ROOT": "1385e84ae7f46b2d",
    "tracker.layout.STEP_ABSOLUTE": "f523898e69fbc750",
    "tracker.layout.STEP_BLANK": "a4e9e11cd18fd75b",
    "tracker.layout.STEP_CLIENT_TREE": "5f51b518f9526119",
    "tracker.layout.STEP_NOT_A_PLACE": "d1aa6f26861ccbee",
    "tracker.layout.STEP_NOT_A_RETURN": "1e7d015db6355c80",
    "tracker.layout.STEP_OTHER_HOUSEHOLD": "a0f05df5e57d787b",
    "tracker.layout.STEP_OTHER_YEAR": "7994492387ba5850",
    "tracker.layout.WINDOWS_ILLEGAL_CHARS": "0852803faa2a184a",
    "tracker.layout.WINDOWS_RESERVED_NAMES": "99bf9abac32f89f2",
    "tracker.layout.WINDOWS_RESERVED_NAMES_TEXT": "c9d9ad8d312ac5a8",
    "tracker.layout.YEAR": "74c6b2f8351bcc6d",
    "tracker.layout._ASCII_LOOK_ALIKES": "5333fd34ff62ce29",
    "tracker.layout._IGNORABLE_CODES": "999fbf22e2feeb49",
    "tracker.layout._INVISIBLE_CATEGORIES": "bb62d3360fd14a4d",
    "tracker.layout._LAYOUT_WORD_KEYS": "a6d47e2209691833",
    "tracker.layout._ONE_SCRIPT": "17235d2097441c94",
    "tracker.layout._character": "bd5a8cc4e82855fc",
    "tracker.layout._parts": "a2847013a67202c7",
    "tracker.layout._parts_below_of": "93c8e3b3dcb1a968",
    "tracker.layout._script": "f890f9bb62d24799",
    "tracker.layout.is_invisible": "0c3785b4672742ba",
    "tracker.layout.is_reserved_name": "3ee144cf8f5c095d",
    "tracker.layout.is_year_folder": "c89c110db3cb607d",
    "tracker.layout.name_key": "26ebf92810e1480a",
    "tracker.layout.parts_below": "024b4df3065f0f7b",
    "tracker.layout.place_of": "fc1a78ab7179dd32",
    "tracker.layout.place_problem": "2e94883c849c9d08",
    "tracker.layout.recorded_name": "84bfdf3a851f4652",
    "tracker.layout.recorded_subfolder_part": "50620c73d7ae6dab",
    "tracker.layout.root_of": "a6c7013a757965b4",
    "tracker.layout.segment_problem": "0dbab0f3b9ccfed7",
    "tracker.ledger.ACCEPTED_KEY": "f4764fc7a8ddd588",
    "tracker.ledger.ALSO_KEY": "da42922852e5dfcd",
    "tracker.ledger.ASKED_KEY": "46da5b49eea2fbee",
    "tracker.ledger.AT_KEY": "22eb1fa0c521db09",
    "tracker.ledger.DIGEST_KEY": "889a0f98aa32537e",
    "tracker.ledger.DRAFTED": "ef02a62df7dc350b",
    "tracker.ledger.DRAFT_APPROVED": "41bf68b11dd88d88",
    "tracker.ledger.EVENTS": "c6d719a66bc0b51d",
    "tracker.ledger.EVENT_KEY": "9e0d5d1c8d94a5b6",
    "tracker.ledger.FILE_KEY": "0efde3f4308de780",
    "tracker.ledger.FINGERPRINT_KEY": "7df2d13d670e5ed4",
    "tracker.ledger.FOLDER_NAME_ACCEPTED": "b7b92a8807e8bbf9",
    "tracker.ledger.FORMAT_KEY": "04fc6c808adf51ac",
    "tracker.ledger.FROM_KEY": "8ecb478c3dc0d3ae",
    "tracker.ledger.HELD_KEY": "85c4d432c47707ee",
    "tracker.ledger.HOST_KEY": "e293b75405af70cd",
    "tracker.ledger.HOUSEHOLD_CHANGED": "783c776c223a869f",
    "tracker.ledger.HOUSEHOLD_KEY": "8de5259835758e72",
    "tracker.ledger.IDENTIFIER_KEY": "123a87f051936a7e",
    "tracker.ledger.INFO_KEY": "ef3370879a96cf2e",
    "tracker.ledger.KEYWORD_KEY": "a51a9ff6a628d820",
    "tracker.ledger.KEYWORD_LEARNED": "7a5d6590fc40e09a",
    "tracker.ledger.KEYWORD_UNLEARNED": "ce11d4a4c4da44a9",
    "tracker.ledger.KEY_KEY": "632a3e84412d6ea8",
    "tracker.ledger.LINE_KEYS": "bfa2973d92dd93ad",
    "tracker.ledger.LINK_KEY": "67b4e6e1e90cbc98",
    "tracker.ledger.MOVE_ABANDONED": "a11db9ac01cd5285",
    "tracker.ledger.MOVING": "d290155f3097fcde",
    "tracker.ledger.OPS_KEY": "2c35289e43246c9f",
    "tracker.ledger.OP_COPY": "477c02e96b3c4061",
    "tracker.ledger.OP_KEY": "b27b68850018781c",
    "tracker.ledger.OP_MOVE": "c4a4adaf72f566c1",
    "tracker.ledger.OP_REMOVE": "e8c2c1465f168081",
    "tracker.ledger.REASON_KEY": "ffa78aeaf553b544",
    "tracker.ledger.RECORD_FORMAT": "6b86b273ff34fce1",
    "tracker.ledger.RELEASED": "81acce4087249f66",
    "tracker.ledger.REMOVED_KEY": "760f3c525ed93b07",
    "tracker.ledger.RETIRED_EVENTS": "ca06b9854a7990f9",
    "tracker.ledger.ROW_EVENTS": "b53cc1cb7387825b",
    "tracker.ledger.ROW_KEY": "e4d99047ca6a3721",
    "tracker.ledger.RULES_CHANGED": "e4535fc89d8ef96d",
    "tracker.ledger.RULES_IMPORTED": "cddb10ca0e4c2100",
    "tracker.ledger.RULES_KEY": "a29e7581476cd7ad",
    "tracker.ledger.SCANNED": "7e17f4790bff13d5",
    "tracker.ledger.SHARING_CONFIRMED": "c8027ef3eb13f5e3",
    "tracker.ledger.STAGE_KEY": "874095181f94a63d",
    "tracker.ledger.STATUSES_KEY": "18c7785691d58b80",
    "tracker.ledger.TEXT_FINGERPRINT_KEY": "0db6b5095dc3896e",
    "tracker.ledger.TO_KEY": "e28f3243b469e21d",
    "tracker.ledger.WAS_KEY": "1d383f963e096e21",
    "tracker.ledger.op_ends": "a4e5e845ab4c8deb",
    "tracker.reasons.KNOWN_CODES": "4ad3f21d00c7f8e5",
    "tracker.records.BLANK_BOUNDS": "cec8e55a02712202",
    "tracker.records.CANDIDATE_SEP": "3c01b9ef061065a0",
    "tracker.records.COUNT_BOUNDS": "66fbd6100ed5379b",
    "tracker.records.DATE_BOUNDS": "14ca9c3c8c63da08",
    "tracker.records.DATE_FIELDS": "f0aaa0cb84de4063",
    "tracker.records.DATE_PATTERN_ALTERNATES": "6d1924b141e16df5",
    "tracker.records.DATE_PATTERN_BOUND_MAX": "f5ca38f748a1d6ea",
    "tracker.records.DATE_PATTERN_COST_MAX": "b552e632666bbf61",
    "tracker.records.DATE_PATTERN_MAX": "27badc983df1780b",
    "tracker.records.DATE_PATTERN_NESTED": "7b1330f7983d042e",
    "tracker.records.DATE_PATTERN_NOT_A_REGEX": "a158e00f56bf6ba7",
    "tracker.records.DATE_PATTERN_OPEN_MAX": "6b86b273ff34fce1",
    "tracker.records.DATE_PATTERN_OPEN_WIDTH": "0604cd3138feed20",
    "tracker.records.DATE_PATTERN_REFERS_BACK": "25a2057a272ff94c",
    "tracker.records.DATE_PATTERN_REPEATS_MAX": "4e07408562bedb8b",
    "tracker.records.DATE_PATTERN_TOO_COSTLY": "3e2d8a14b8d6a5a6",
    "tracker.records.DATE_PATTERN_TOO_LONG": "02239fb8cdceefd8",
    "tracker.records.DATE_PATTERN_TOO_MANY": "ba11446dcfecda24",
    "tracker.records.DATE_PATTERN_TOO_MANY_OPTIONAL": "eb3c2f5771c5d09f",
    "tracker.records.DATE_PATTERN_TOO_MANY_WAYS": "a322d9761b272d91",
    "tracker.records.DATE_PATTERN_TOO_OPEN": "fcaa25330d84e4d0",
    "tracker.records.DATE_PATTERN_TOO_WIDE": "f7af15030b186a35",
    "tracker.records.DATE_PATTERN_VARIABLE_MAX": "2c624232cdd22177",
    "tracker.records.DATE_PATTERN_WAYS_MAX": "ca902d4a8acbdea1",
    "tracker.records.DATE_YEAR_MAX": "4f5131ea0c5a3e7f",
    "tracker.records.DATE_YEAR_MIN": "e41d64db5703c644",
    "tracker.records.DIGEST_BOUNDS": "677bb2233d3c0d23",
    "tracker.records.FEED_REFUSED": "d601e93b18987f24",
    "tracker.records.FLAG_BOUNDS": "2bfdeea59997694f",
    "tracker.records.HOST_BOUNDS": "72219f0e2bcda110",
    "tracker.records.HOST_MAX": "a68b412c4282555f",
    "tracker.records.LONG_TEXT_BOUNDS": "3de4da1af0b30ef2",
    "tracker.records.LONG_TEXT_MAX": "876c9b16254e157d",
    "tracker.records.MAX_EXPECTED_COUNT": "888df25ae3577242",
    "tracker.records.MAX_FILE_COUNT": "888df25ae3577242",
    "tracker.records.MAX_ROW": "888df25ae3577242",
    "tracker.records.MAX_ROW_SIZE_KB": "02bfbb85ecfba2af",
    "tracker.records.MAX_SIZE_KB": "50b4b069390c1d79",
    "tracker.records.MAX_STAGE": "19581e27de7ced00",
    "tracker.records.MIN_EXPECTED_COUNT": "6b86b273ff34fce1",
    "tracker.records.MIN_SIZE_KB_FLOOR": "5feceb66ffc86f38",
    "tracker.records.MIN_SPELLING_WORDS": "d4735e3a265e16ee",
    "tracker.records.NAME_BOUNDS": "fab0c3e598d1038c",
    "tracker.records.NUMBER_BOUNDS": "d7d2f825d092e462",
    "tracker.records.OVERRIDE_BOUNDS": "22a3650c5fc6e021",
    "tracker.records.PERSON_KINDS": "11ac10e2383de5cc",
    "tracker.records.RULE_FLAG_FIELDS": "c500b9a01ed742b3",
    "tracker.records.RULE_LIST_FIELDS": "8b3d25ca8662bd02",
    "tracker.records.SHORT_TITLE_MAX": "f5ca38f748a1d6ea",
    "tracker.records.STAMP_BOUNDS": "7c7cf7f161dd3671",
    "tracker.records.STAMP_YEAR_MIN": "ad1f3889d0032e7c",
    "tracker.records.TEXT_BOUNDS": "ce369c3539b412af",
    "tracker.records.TEXT_LIST_BOUNDS": "196f901bd54f0f8c",
    "tracker.records.TEXT_MAX": "40510175845988f1",
    "tracker.records.WAITS_FOR_ANSWERS": "f0615f5bcc293884",
    "tracker.records.WAITS_FOR_BOUNDS": "6f57ee0ee5ca0bbc",
    "tracker.records.WAITS_FOR_SEP": "de9881cacd5c858e",
    "tracker.records.WINDOWS_ILLEGAL_CHARS": "0852803faa2a184a",
    "tracker.records.WINDOWS_ILLEGAL_CHARS_TEXT": "e4b68ca2e1ff6518",
    "tracker.records.WINDOWS_RESERVED_NAMES_TEXT": "c9d9ad8d312ac5a8",
    "tracker.records.YEAR_MAX": "1aaf97e300d50bac",
    "tracker.records.YEAR_MIN": "e41d64db5703c644",
    "tracker.records._ENTRY_LONG_TEXT": "108c25e4b80db4c6",
    "tracker.records._ENTRY_NAMES": "5980f2d1176281a2",
    "tracker.records._ENTRY_TEXT": "68e0df1c43ff5282",
    "tracker.records._HEX_DIGEST": "286fa658d6b7911b",
    "tracker.records._INFO_LONG_TEXT": "69674950c21f7eae",
    "tracker.records._INFO_TEXT": "cbdf6035c202636d",
    "tracker.records._ISO_DATE": "3ca3c91bdac79395",
    "tracker.records._ONE_LINE_REFUSED": "f912910f93b16ff7",
    "tracker.records._REFERS_BACK": "6a5a714c08b4ca99",
    "tracker.records._REPEATS": "0429e0cc33348e07",
    "tracker.records._RULE_TEXT": "4dbd8ce696bb0f8e",
    "tracker.records._STAMP": "36e48aca67f1ef08",
    "tracker.records._field": "190cfe96c598c222",
    "tracker.records._first": "afafd6bbd03b4d5a",
    "tracker.records._is_number": "b55a28bc0ae446c7",
    "tracker.records._objects_from_json": "150fd8d193ee1603",
    "tracker.records._walk": "58be230437faa42c",
    "tracker.records._ways": "73d93a78035726fd",
    "tracker.records._width": "971b31440953101e",
    "tracker.records.count_problem": "89257d6ec9bdd711",
    "tracker.records.date_pattern_problem": "fa02803a1a99c545",
    "tracker.records.date_problem": "0bf005c4a966d7f8",
    "tracker.records.digest_problem": "217cc9c49f9a6e20",
    "tracker.records.entry_problem": "a79ea9e62a85223a",
    "tracker.records.feed_from_json": "b2e5148af638d97c",
    "tracker.records.feeds_from_json": "73f791f77660a6d8",
    "tracker.records.flag_problem": "1082a26284942f5c",
    "tracker.records.format_waits_for": "a9f50749433f46ce",
    "tracker.records.host_problem": "7d98945bc57bd382",
    "tracker.records.household_problem": "d341e98e6700e560",
    "tracker.records.identifier_problem": "f8ee13a768acea53",
    "tracker.records.info_problem": "a14147da699ad792",
    "tracker.records.is_a_spelling": "9872f0754c1f928d",
    "tracker.records.name_parts": "2fb3aa450c490a16",
    "tracker.records.name_problem": "435e57a752b587c2",
    "tracker.records.name_words": "888ff2df30e14d73",
    "tracker.records.number_problem": "b8e64da5f5e20b1a",
    "tracker.records.parse_waits_for": "fe2da49df5b9f8ce",
    "tracker.records.people_from_json": "bd021c769cc1a5d8",
    "tracker.records.person_from_json": "7e7a8fed1cb8c27a",
    "tracker.records.received_problem": "2fe803ce248363ca",
    "tracker.records.rule_row_fault": "e63ac46148a8c37f",
    "tracker.records.rule_row_problem": "bfbfa65df0936781",
    "tracker.records.short_title_problem": "cee1ccd1dc44eedd",
    "tracker.records.split_codes": "ac4f6152bb7ad6ee",
    "tracker.records.stamp_problem": "2d66f0bfa7df3a4f",
    "tracker.records.status_from_json": "18fe07346092ffad",
    "tracker.records.status_problem": "0a4507873e497b78",
    "tracker.records.text_list_problem": "5c6a2aa819ebb0cf",
    "tracker.records.text_problem": "3af72e89b781e54e",
    "tracker.records.waits_for_problem": "463d041ef7fa9219",
    "tracker.records.word_list_problem": "64d72805fbba0527",
    "tracker.settings.ENV_PRODUCT_NAME": "ea9430f722280e29",
    "tracker.settings.ENV_SETTINGS_DIR": "b654987367e5160b",
    "tracker.settings.HOLD_READING": "635bd5450bece8e4",
    "tracker.settings.KEY_CLIENTS_ROOT": "3b8f548e07b39dbf",
    "tracker.settings.MAC_SUPPORT": "2c8244c3f17e7646",
    "tracker.settings.NO_HOME_FOR_SETTINGS": "c5be5f9efc600e1b",
    "tracker.settings.SETTINGS_FILENAME": "ddf9dfc4d857c464",
    "tracker.settings._HOLDING": "6f49cdbd80e1b95d",
    "tracker.settings._SETTINGS_HELD": "6c71e2207cf64f31",
    "tracker.settings._home": "ba531a10d183af14",
    "tracker.settings._read": "9a09d08e256be9de",
    "tracker.settings.clients_root": "8fbaef8c43dcb573",
    "tracker.settings.held": "19183d0915cfb77e",
    "tracker.settings.host_system": "d4aa9d6d8f91c8f7",
    "tracker.settings.mac_settings_dir": "b9a76a8027ce8ebf",
    "tracker.settings.product_name": "f19bc48fabdb134a",
    "tracker.settings.resolved": "dc9902a73c0115e2",
    "tracker.settings.settings_dir": "ab85b6edd1fe0779",
    "tracker.settings.settings_path": "8a79e7ca2ca7f66a",
    "tracker.store.ALSO_IN": "f91e15416cd81c44",
    "tracker.store.KIND_HOUSEHOLD": "8de5259835758e72",
    "tracker.store.KIND_RETURN": "08633b69eed18c1b",
    "tracker.store.MALFORMED_LINE": "7af462b999c9799b",
    "tracker.store.RULE_LIST_FIELDS": "8b3d25ca8662bd02",
    "tracker.store.STATUS_COLUMNS": "072efbf3b12ac0bd",
    "tracker.store.UNKNOWN_EVENT": "099e89ceccd1e5e9",
    "tracker.store._engagement_key": "cf50c480b543e726",
    "tracker.store._engagement_row": "a9108dc0e45b8442",
    "tracker.store._line_keys_problem": "0d6016b3dab0c236",
    "tracker.store._positional_root": "f2fce089ca54ef5a",
    "tracker.store._recorded_root_over": "6447409cff0d940e",
    "tracker.store._refuse_a_malformed_line": "1fa3ee39286cc582",
    "tracker.store.engagement_path": "354415605ca56669",
    "tracker.store.key_root": "13d66deeca51405a",
    "tracker.store.kind": "c5781c37870424f8",
    "tracker.store.statuses": "d99730d725daf407",
}, 4: {
    "tracker.layout.CLIENTS": "3b8264d65abeec66",
    "tracker.layout.CLIENTS_TREE": "488530d6164e0dd6",
    "tracker.layout.CLIENT_HOUSEHOLD": "2c784f90e61ac610",
    "tracker.layout.HOUSEHOLD": "8de5259835758e72",
    "tracker.layout.INBOX": "d9c4d1b7a70cb6f2",
    "tracker.layout.INBOX_DIR_NAME": "919dcb2c2a774098",
    "tracker.layout.IN_INBOX": "fc74c5d3e9ae9444",
    "tracker.layout.IN_OPENED": "633c5d64586b470a",
    "tracker.layout.IN_ORIGINALS": "20496354d6f1b26b",
    "tracker.layout.IN_RETURN": "155a1bfd542aaa0d",
    "tracker.layout.LOOK_ALIKES": "54c49454cf2f5689",
    "tracker.layout.MISPLACED": "b8ca0cd70606f6d7",
    "tracker.layout.NAMELESS": "1bad7ce20105964a",
    "tracker.layout.NAME_COMPATIBILITY": "ec65d3d71fd72b3d",
    "tracker.layout.NAME_DEVICE": "620b97404635bcec",
    "tracker.layout.NAME_EMPTY": "aa82b128dcf1c993",
    "tracker.layout.NAME_FIRST_CHARACTER": "bd62babfb5664dc1",
    "tracker.layout.NAME_ILLEGAL": "305df1e9431d3276",
    "tracker.layout.NAME_INVISIBLE": "2401333e2c513d23",
    "tracker.layout.NAME_LAYOUT_WORD": "978aa80c1fbb2b52",
    "tracker.layout.NAME_MAX_CHARS": "48449a14a4ff7d79",
    "tracker.layout.NAME_SCRIPTS": "3de824b29b62bb49",
    "tracker.layout.NAME_TOO_LONG": "7a5e00d8497fbe2d",
    "tracker.layout.NAME_TRAILING": "7fafe7cda3544c33",
    "tracker.layout.OPENED": "33bdc49eaabcbced",
    "tracker.layout.OPENED_DIR_NAME": "5ef673f341874a6f",
    "tracker.layout.ORIGINALS": "535087da73c5868d",
    "tracker.layout.OUTSIDE": "2f2e7ba21585ff28",
    "tracker.layout.PRIVATE": "68a262e0c0fb929f",
    "tracker.layout.PRIVATE_TREE": "27c7f0479a0c896f",
    "tracker.layout.RETURN": "08633b69eed18c1b",
    "tracker.layout.ROOT": "11ccb349ede85740",
    "tracker.layout.STEP_ABOVE_ROOT": "1385e84ae7f46b2d",
    "tracker.layout.STEP_ABSOLUTE": "f523898e69fbc750",
    "tracker.layout.STEP_BLANK": "a4e9e11cd18fd75b",
    "tracker.layout.STEP_CLIENT_TREE": "5f51b518f9526119",
    "tracker.layout.STEP_NOT_A_PLACE": "d1aa6f26861ccbee",
    "tracker.layout.STEP_NOT_A_RETURN": "1e7d015db6355c80",
    "tracker.layout.STEP_OTHER_HOUSEHOLD": "a0f05df5e57d787b",
    "tracker.layout.STEP_OTHER_YEAR": "7994492387ba5850",
    "tracker.layout.WINDOWS_ILLEGAL_CHARS": "0852803faa2a184a",
    "tracker.layout.WINDOWS_RESERVED_NAMES": "99bf9abac32f89f2",
    "tracker.layout.WINDOWS_RESERVED_NAMES_TEXT": "c9d9ad8d312ac5a8",
    "tracker.layout.YEAR": "74c6b2f8351bcc6d",
    "tracker.layout._ASCII_LOOK_ALIKES": "5333fd34ff62ce29",
    "tracker.layout._IGNORABLE_CODES": "999fbf22e2feeb49",
    "tracker.layout._INVISIBLE_CATEGORIES": "bb62d3360fd14a4d",
    "tracker.layout._LAYOUT_WORD_KEYS": "a6d47e2209691833",
    "tracker.layout._ONE_SCRIPT": "17235d2097441c94",
    "tracker.layout._SPOOFING_CODES": "136890ff2b21c3ef",
    "tracker.layout._character": "bd5a8cc4e82855fc",
    "tracker.layout._parts": "a2847013a67202c7",
    "tracker.layout._parts_below_of": "93c8e3b3dcb1a968",
    "tracker.layout._script": "f890f9bb62d24799",
    "tracker.layout.invisible_problem": "a95be632ca4ceaf4",
    "tracker.layout.is_invisible": "0c3785b4672742ba",
    "tracker.layout.is_reserved_name": "3ee144cf8f5c095d",
    "tracker.layout.is_year_folder": "c89c110db3cb607d",
    "tracker.layout.name_key": "26ebf92810e1480a",
    "tracker.layout.parts_below": "024b4df3065f0f7b",
    "tracker.layout.place_of": "fc1a78ab7179dd32",
    "tracker.layout.place_problem": "2e94883c849c9d08",
    "tracker.layout.recorded_name": "84bfdf3a851f4652",
    "tracker.layout.recorded_subfolder_part": "50620c73d7ae6dab",
    "tracker.layout.root_of": "a6c7013a757965b4",
    "tracker.layout.segment_problem": "c85f6ed345abe1fd",
    "tracker.layout.spoofing_problem": "7a767da08a51fff8",
    "tracker.ledger.ACCEPTED_KEY": "f4764fc7a8ddd588",
    "tracker.ledger.ALSO_KEY": "da42922852e5dfcd",
    "tracker.ledger.ASKED_KEY": "46da5b49eea2fbee",
    "tracker.ledger.AT_KEY": "22eb1fa0c521db09",
    "tracker.ledger.DIGEST_KEY": "889a0f98aa32537e",
    "tracker.ledger.DRAFTED": "ef02a62df7dc350b",
    "tracker.ledger.DRAFT_APPROVED": "41bf68b11dd88d88",
    "tracker.ledger.EVENTS": "c6d719a66bc0b51d",
    "tracker.ledger.EVENT_KEY": "9e0d5d1c8d94a5b6",
    "tracker.ledger.FILE_KEY": "0efde3f4308de780",
    "tracker.ledger.FINGERPRINT_KEY": "7df2d13d670e5ed4",
    "tracker.ledger.FOLDER_NAME_ACCEPTED": "b7b92a8807e8bbf9",
    "tracker.ledger.FORMAT_KEY": "04fc6c808adf51ac",
    "tracker.ledger.FROM_KEY": "8ecb478c3dc0d3ae",
    "tracker.ledger.HELD_KEY": "85c4d432c47707ee",
    "tracker.ledger.HOST_KEY": "e293b75405af70cd",
    "tracker.ledger.HOUSEHOLD_CHANGED": "783c776c223a869f",
    "tracker.ledger.HOUSEHOLD_KEY": "8de5259835758e72",
    "tracker.ledger.IDENTIFIER_KEY": "123a87f051936a7e",
    "tracker.ledger.INFO_KEY": "ef3370879a96cf2e",
    "tracker.ledger.KEYWORD_KEY": "a51a9ff6a628d820",
    "tracker.ledger.KEYWORD_LEARNED": "7a5d6590fc40e09a",
    "tracker.ledger.KEYWORD_UNLEARNED": "ce11d4a4c4da44a9",
    "tracker.ledger.KEY_KEY": "632a3e84412d6ea8",
    "tracker.ledger.LINE_KEYS": "bfa2973d92dd93ad",
    "tracker.ledger.LINK_KEY": "67b4e6e1e90cbc98",
    "tracker.ledger.MOVE_ABANDONED": "a11db9ac01cd5285",
    "tracker.ledger.MOVING": "d290155f3097fcde",
    "tracker.ledger.OPS_KEY": "2c35289e43246c9f",
    "tracker.ledger.OP_COPY": "477c02e96b3c4061",
    "tracker.ledger.OP_KEY": "b27b68850018781c",
    "tracker.ledger.OP_MOVE": "c4a4adaf72f566c1",
    "tracker.ledger.OP_REMOVE": "e8c2c1465f168081",
    "tracker.ledger.REASON_KEY": "ffa78aeaf553b544",
    "tracker.ledger.RECORD_FORMAT": "6b86b273ff34fce1",
    "tracker.ledger.RELEASED": "81acce4087249f66",
    "tracker.ledger.REMOVED_KEY": "760f3c525ed93b07",
    "tracker.ledger.RETIRED_EVENTS": "ca06b9854a7990f9",
    "tracker.ledger.ROW_EVENTS": "b53cc1cb7387825b",
    "tracker.ledger.ROW_KEY": "e4d99047ca6a3721",
    "tracker.ledger.RULES_CHANGED": "e4535fc89d8ef96d",
    "tracker.ledger.RULES_IMPORTED": "cddb10ca0e4c2100",
    "tracker.ledger.RULES_KEY": "a29e7581476cd7ad",
    "tracker.ledger.SCANNED": "7e17f4790bff13d5",
    "tracker.ledger.SHARING_CONFIRMED": "c8027ef3eb13f5e3",
    "tracker.ledger.STAGE_KEY": "874095181f94a63d",
    "tracker.ledger.STATUSES_KEY": "18c7785691d58b80",
    "tracker.ledger.TEXT_FINGERPRINT_KEY": "0db6b5095dc3896e",
    "tracker.ledger.TO_KEY": "e28f3243b469e21d",
    "tracker.ledger.WAS_KEY": "1d383f963e096e21",
    "tracker.ledger.op_ends": "a4e5e845ab4c8deb",
    "tracker.reasons.KNOWN_CODES": "4ad3f21d00c7f8e5",
    "tracker.records.BLANK_BOUNDS": "cec8e55a02712202",
    "tracker.records.CANDIDATE_SEP": "3c01b9ef061065a0",
    "tracker.records.COUNT_BOUNDS": "66fbd6100ed5379b",
    "tracker.records.DATE_BOUNDS": "14ca9c3c8c63da08",
    "tracker.records.DATE_FIELDS": "f0aaa0cb84de4063",
    "tracker.records.DATE_PATTERN_ALTERNATES": "6d1924b141e16df5",
    "tracker.records.DATE_PATTERN_BOUND_MAX": "f5ca38f748a1d6ea",
    "tracker.records.DATE_PATTERN_COST_MAX": "b552e632666bbf61",
    "tracker.records.DATE_PATTERN_MAX": "27badc983df1780b",
    "tracker.records.DATE_PATTERN_NESTED": "7b1330f7983d042e",
    "tracker.records.DATE_PATTERN_NOT_A_REGEX": "a158e00f56bf6ba7",
    "tracker.records.DATE_PATTERN_OPEN_MAX": "6b86b273ff34fce1",
    "tracker.records.DATE_PATTERN_OPEN_WIDTH": "0604cd3138feed20",
    "tracker.records.DATE_PATTERN_REFERS_BACK": "25a2057a272ff94c",
    "tracker.records.DATE_PATTERN_REPEATS_MAX": "4e07408562bedb8b",
    "tracker.records.DATE_PATTERN_TOO_COSTLY": "3e2d8a14b8d6a5a6",
    "tracker.records.DATE_PATTERN_TOO_LONG": "02239fb8cdceefd8",
    "tracker.records.DATE_PATTERN_TOO_MANY": "ba11446dcfecda24",
    "tracker.records.DATE_PATTERN_TOO_MANY_OPTIONAL": "eb3c2f5771c5d09f",
    "tracker.records.DATE_PATTERN_TOO_MANY_WAYS": "a322d9761b272d91",
    "tracker.records.DATE_PATTERN_TOO_OPEN": "fcaa25330d84e4d0",
    "tracker.records.DATE_PATTERN_TOO_WIDE": "f7af15030b186a35",
    "tracker.records.DATE_PATTERN_VARIABLE_MAX": "2c624232cdd22177",
    "tracker.records.DATE_PATTERN_WAYS_MAX": "ca902d4a8acbdea1",
    "tracker.records.DATE_YEAR_MAX": "4f5131ea0c5a3e7f",
    "tracker.records.DATE_YEAR_MIN": "e41d64db5703c644",
    "tracker.records.DIGEST_BOUNDS": "677bb2233d3c0d23",
    "tracker.records.FEED_REFUSED": "d601e93b18987f24",
    "tracker.records.FLAG_BOUNDS": "2bfdeea59997694f",
    "tracker.records.HOST_BOUNDS": "72219f0e2bcda110",
    "tracker.records.HOST_MAX": "a68b412c4282555f",
    "tracker.records.LONG_TEXT_BOUNDS": "3de4da1af0b30ef2",
    "tracker.records.LONG_TEXT_MAX": "876c9b16254e157d",
    "tracker.records.MAX_EXPECTED_COUNT": "888df25ae3577242",
    "tracker.records.MAX_FILE_COUNT": "888df25ae3577242",
    "tracker.records.MAX_ROW": "888df25ae3577242",
    "tracker.records.MAX_ROW_SIZE_KB": "02bfbb85ecfba2af",
    "tracker.records.MAX_SIZE_KB": "50b4b069390c1d79",
    "tracker.records.MAX_STAGE": "19581e27de7ced00",
    "tracker.records.MIN_EXPECTED_COUNT": "6b86b273ff34fce1",
    "tracker.records.MIN_SIZE_KB_FLOOR": "5feceb66ffc86f38",
    "tracker.records.MIN_SPELLING_WORDS": "d4735e3a265e16ee",
    "tracker.records.NAME_BOUNDS": "fab0c3e598d1038c",
    "tracker.records.NUMBER_BOUNDS": "d7d2f825d092e462",
    "tracker.records.OVERRIDE_BOUNDS": "22a3650c5fc6e021",
    "tracker.records.PERSON_KINDS": "11ac10e2383de5cc",
    "tracker.records.RULE_FLAG_FIELDS": "c500b9a01ed742b3",
    "tracker.records.RULE_LIST_FIELDS": "8b3d25ca8662bd02",
    "tracker.records.SHORT_TITLE_MAX": "f5ca38f748a1d6ea",
    "tracker.records.STAMP_BOUNDS": "7c7cf7f161dd3671",
    "tracker.records.STAMP_YEAR_MIN": "ad1f3889d0032e7c",
    "tracker.records.TEXT_BOUNDS": "ce369c3539b412af",
    "tracker.records.TEXT_LIST_BOUNDS": "196f901bd54f0f8c",
    "tracker.records.TEXT_MAX": "40510175845988f1",
    "tracker.records.WAITS_FOR_ANSWERS": "f0615f5bcc293884",
    "tracker.records.WAITS_FOR_BOUNDS": "6f57ee0ee5ca0bbc",
    "tracker.records.WAITS_FOR_SEP": "de9881cacd5c858e",
    "tracker.records.WINDOWS_ILLEGAL_CHARS": "0852803faa2a184a",
    "tracker.records.WINDOWS_ILLEGAL_CHARS_TEXT": "e4b68ca2e1ff6518",
    "tracker.records.WINDOWS_RESERVED_NAMES_TEXT": "c9d9ad8d312ac5a8",
    "tracker.records.YEAR_MAX": "1aaf97e300d50bac",
    "tracker.records.YEAR_MIN": "e41d64db5703c644",
    "tracker.records._ENTRY_LONG_TEXT": "108c25e4b80db4c6",
    "tracker.records._ENTRY_NAMES": "5980f2d1176281a2",
    "tracker.records._ENTRY_TEXT": "68e0df1c43ff5282",
    "tracker.records._HEX_DIGEST": "286fa658d6b7911b",
    "tracker.records._INFO_LONG_TEXT": "69674950c21f7eae",
    "tracker.records._INFO_TEXT": "cbdf6035c202636d",
    "tracker.records._ISO_DATE": "3ca3c91bdac79395",
    "tracker.records._ONE_LINE_REFUSED": "f912910f93b16ff7",
    "tracker.records._REFERS_BACK": "6a5a714c08b4ca99",
    "tracker.records._REPEATS": "0429e0cc33348e07",
    "tracker.records._RULE_TEXT": "4dbd8ce696bb0f8e",
    "tracker.records._STAMP": "36e48aca67f1ef08",
    "tracker.records._field": "190cfe96c598c222",
    "tracker.records._first": "afafd6bbd03b4d5a",
    "tracker.records._is_number": "b55a28bc0ae446c7",
    "tracker.records._objects_from_json": "150fd8d193ee1603",
    "tracker.records._walk": "58be230437faa42c",
    "tracker.records._ways": "73d93a78035726fd",
    "tracker.records._width": "971b31440953101e",
    "tracker.records.count_problem": "89257d6ec9bdd711",
    "tracker.records.date_pattern_problem": "fa02803a1a99c545",
    "tracker.records.date_problem": "0bf005c4a966d7f8",
    "tracker.records.digest_problem": "217cc9c49f9a6e20",
    "tracker.records.entry_problem": "a79ea9e62a85223a",
    "tracker.records.feed_from_json": "b2e5148af638d97c",
    "tracker.records.feeds_from_json": "73f791f77660a6d8",
    "tracker.records.flag_problem": "1082a26284942f5c",
    "tracker.records.format_waits_for": "a9f50749433f46ce",
    "tracker.records.host_problem": "7d98945bc57bd382",
    "tracker.records.household_problem": "d341e98e6700e560",
    "tracker.records.identifier_problem": "001b7620b5b822f6",
    "tracker.records.info_problem": "a14147da699ad792",
    "tracker.records.is_a_spelling": "9872f0754c1f928d",
    "tracker.records.name_parts": "2fb3aa450c490a16",
    "tracker.records.name_problem": "435e57a752b587c2",
    "tracker.records.name_words": "888ff2df30e14d73",
    "tracker.records.number_problem": "b8e64da5f5e20b1a",
    "tracker.records.parse_waits_for": "fe2da49df5b9f8ce",
    "tracker.records.people_from_json": "bd021c769cc1a5d8",
    "tracker.records.person_from_json": "d6e448c24d1dd1a5",
    "tracker.records.received_problem": "2fe803ce248363ca",
    "tracker.records.rule_row_fault": "e63ac46148a8c37f",
    "tracker.records.rule_row_problem": "bfbfa65df0936781",
    "tracker.records.short_title_problem": "563274b3cd6e71cf",
    "tracker.records.split_codes": "ac4f6152bb7ad6ee",
    "tracker.records.stamp_problem": "2d66f0bfa7df3a4f",
    "tracker.records.status_from_json": "18fe07346092ffad",
    "tracker.records.status_problem": "0a4507873e497b78",
    "tracker.records.text_list_problem": "5c6a2aa819ebb0cf",
    "tracker.records.text_problem": "3af72e89b781e54e",
    "tracker.records.waits_for_problem": "463d041ef7fa9219",
    "tracker.records.word_list_problem": "64d72805fbba0527",
    "tracker.settings.ENV_PRODUCT_NAME": "ea9430f722280e29",
    "tracker.settings.ENV_SETTINGS_DIR": "b654987367e5160b",
    "tracker.settings.HOLD_READING": "635bd5450bece8e4",
    "tracker.settings.KEY_CLIENTS_ROOT": "3b8f548e07b39dbf",
    "tracker.settings.MAC_SUPPORT": "2c8244c3f17e7646",
    "tracker.settings.NO_HOME_FOR_SETTINGS": "c5be5f9efc600e1b",
    "tracker.settings.SETTINGS_FILENAME": "ddf9dfc4d857c464",
    "tracker.settings._HOLDING": "6f49cdbd80e1b95d",
    "tracker.settings._SETTINGS_HELD": "6c71e2207cf64f31",
    "tracker.settings._home": "ba531a10d183af14",
    "tracker.settings._read": "9a09d08e256be9de",
    "tracker.settings.clients_root": "8fbaef8c43dcb573",
    "tracker.settings.held": "19183d0915cfb77e",
    "tracker.settings.host_system": "d4aa9d6d8f91c8f7",
    "tracker.settings.mac_settings_dir": "b9a76a8027ce8ebf",
    "tracker.settings.product_name": "f19bc48fabdb134a",
    "tracker.settings.resolved": "dc9902a73c0115e2",
    "tracker.settings.settings_dir": "ab85b6edd1fe0779",
    "tracker.settings.settings_path": "8a79e7ca2ca7f66a",
    "tracker.store.ALSO_IN": "f91e15416cd81c44",
    "tracker.store.KIND_HOUSEHOLD": "8de5259835758e72",
    "tracker.store.KIND_RETURN": "08633b69eed18c1b",
    "tracker.store.MALFORMED_LINE": "7af462b999c9799b",
    "tracker.store.REFUSED_CHANGE": "ab4d86d9b8b2fffa",
    "tracker.store.RULE_LIST_FIELDS": "8b3d25ca8662bd02",
    "tracker.store.STATUS_COLUMNS": "072efbf3b12ac0bd",
    "tracker.store.UNKNOWN_EVENT": "099e89ceccd1e5e9",
    "tracker.store._engagement_key": "cf50c480b543e726",
    "tracker.store._engagement_row": "a9108dc0e45b8442",
    "tracker.store._line_keys_problem": "0d6016b3dab0c236",
    "tracker.store._positional_root": "f2fce089ca54ef5a",
    "tracker.store._recorded_root_over": "6447409cff0d940e",
    "tracker.store._refuse_a_malformed_line": "28600c2dd20afaa5",
    "tracker.store.engagement_path": "354415605ca56669",
    "tracker.store.key_root": "13d66deeca51405a",
    "tracker.store.kind": "c5781c37870424f8",
    "tracker.store.statuses": "d99730d725daf407",
}, 5: {
    "tracker.admission.ALSO_IN": "f91e15416cd81c44",
    "tracker.admission.KIND_HOUSEHOLD": "8de5259835758e72",
    "tracker.admission.KIND_RETURN": "08633b69eed18c1b",
    "tracker.admission.MALFORMED_LINE": "7af462b999c9799b",
    "tracker.admission.REFUSED_CHANGE": "ab4d86d9b8b2fffa",
    "tracker.admission.RULE_LIST_FIELDS": "8b3d25ca8662bd02",
    "tracker.admission.UNKNOWN_EVENT": "099e89ceccd1e5e9",
    "tracker.admission._line_keys_problem": "5f41ce8742ce125e",
    "tracker.admission._refuse_a_malformed_line": "e8a42feeadda2854",
    "tracker.bounds.COUNT_BOUNDS": "66fbd6100ed5379b",
    "tracker.bounds.DATE_BOUNDS": "14ca9c3c8c63da08",
    "tracker.bounds.DATE_PATTERN_ALTERNATES": "6d1924b141e16df5",
    "tracker.bounds.DATE_PATTERN_BOUND_MAX": "f5ca38f748a1d6ea",
    "tracker.bounds.DATE_PATTERN_COST_MAX": "b552e632666bbf61",
    "tracker.bounds.DATE_PATTERN_MAX": "27badc983df1780b",
    "tracker.bounds.DATE_PATTERN_NESTED": "7b1330f7983d042e",
    "tracker.bounds.DATE_PATTERN_NOT_A_REGEX": "a158e00f56bf6ba7",
    "tracker.bounds.DATE_PATTERN_OPEN_MAX": "6b86b273ff34fce1",
    "tracker.bounds.DATE_PATTERN_OPEN_WIDTH": "0604cd3138feed20",
    "tracker.bounds.DATE_PATTERN_REFERS_BACK": "25a2057a272ff94c",
    "tracker.bounds.DATE_PATTERN_REPEATS_MAX": "4e07408562bedb8b",
    "tracker.bounds.DATE_PATTERN_TOO_COSTLY": "3e2d8a14b8d6a5a6",
    "tracker.bounds.DATE_PATTERN_TOO_LONG": "02239fb8cdceefd8",
    "tracker.bounds.DATE_PATTERN_TOO_MANY": "ba11446dcfecda24",
    "tracker.bounds.DATE_PATTERN_TOO_MANY_OPTIONAL": "eb3c2f5771c5d09f",
    "tracker.bounds.DATE_PATTERN_TOO_MANY_WAYS": "a322d9761b272d91",
    "tracker.bounds.DATE_PATTERN_TOO_OPEN": "fcaa25330d84e4d0",
    "tracker.bounds.DATE_PATTERN_TOO_WIDE": "f7af15030b186a35",
    "tracker.bounds.DATE_PATTERN_VARIABLE_MAX": "2c624232cdd22177",
    "tracker.bounds.DATE_PATTERN_WAYS_MAX": "ca902d4a8acbdea1",
    "tracker.bounds.DATE_YEAR_MAX": "4f5131ea0c5a3e7f",
    "tracker.bounds.DATE_YEAR_MIN": "e41d64db5703c644",
    "tracker.bounds.DIGEST_BOUNDS": "677bb2233d3c0d23",
    "tracker.bounds.FLAG_BOUNDS": "2bfdeea59997694f",
    "tracker.bounds.HOST_BOUNDS": "72219f0e2bcda110",
    "tracker.bounds.HOST_MAX": "a68b412c4282555f",
    "tracker.bounds.LONG_TEXT_BOUNDS": "3de4da1af0b30ef2",
    "tracker.bounds.LONG_TEXT_MAX": "876c9b16254e157d",
    "tracker.bounds.MAX_STAGE": "19581e27de7ced00",
    "tracker.bounds.NAME_BOUNDS": "fab0c3e598d1038c",
    "tracker.bounds.NUMBER_BOUNDS": "d7d2f825d092e462",
    "tracker.bounds.SHORT_TITLE_MAX": "f5ca38f748a1d6ea",
    "tracker.bounds.STAMP_BOUNDS": "7c7cf7f161dd3671",
    "tracker.bounds.STAMP_YEAR_MIN": "ad1f3889d0032e7c",
    "tracker.bounds.TEXT_BOUNDS": "ce369c3539b412af",
    "tracker.bounds.TEXT_LIST_BOUNDS": "196f901bd54f0f8c",
    "tracker.bounds.TEXT_MAX": "40510175845988f1",
    "tracker.bounds._HEX_DIGEST": "286fa658d6b7911b",
    "tracker.bounds._ISO_DATE": "3ca3c91bdac79395",
    "tracker.bounds._ONE_LINE_REFUSED": "f912910f93b16ff7",
    "tracker.bounds._REFERS_BACK": "6a5a714c08b4ca99",
    "tracker.bounds._REPEATS": "0429e0cc33348e07",
    "tracker.bounds._STAMP": "36e48aca67f1ef08",
    "tracker.bounds._field": "190cfe96c598c222",
    "tracker.bounds._first": "afafd6bbd03b4d5a",
    "tracker.bounds._is_number": "dfcf5d69037f4389",
    "tracker.bounds._walk": "58be230437faa42c",
    "tracker.bounds._ways": "73d93a78035726fd",
    "tracker.bounds._width": "971b31440953101e",
    "tracker.bounds.count_problem": "89257d6ec9bdd711",
    "tracker.bounds.date_pattern_problem": "fa02803a1a99c545",
    "tracker.bounds.date_problem": "0bf005c4a966d7f8",
    "tracker.bounds.digest_problem": "217cc9c49f9a6e20",
    "tracker.bounds.document_problem": "7a92f22b5f2cdadc",
    "tracker.bounds.flag_problem": "1082a26284942f5c",
    "tracker.bounds.host_problem": "7d98945bc57bd382",
    "tracker.bounds.identifier_problem": "0e9214164ffa7491",
    "tracker.bounds.name_problem": "435e57a752b587c2",
    "tracker.bounds.number_problem": "b8e64da5f5e20b1a",
    "tracker.bounds.received_problem": "2fe803ce248363ca",
    "tracker.bounds.short_title_problem": "c8c782a76487906f",
    "tracker.bounds.stamp_problem": "2d66f0bfa7df3a4f",
    "tracker.bounds.text_list_problem": "5c6a2aa819ebb0cf",
    "tracker.bounds.text_problem": "3af72e89b781e54e",
    "tracker.layout.CLIENTS": "3b8264d65abeec66",
    "tracker.layout.CLIENTS_TREE": "488530d6164e0dd6",
    "tracker.layout.CLIENT_HOUSEHOLD": "2c784f90e61ac610",
    "tracker.layout.HOUSEHOLD": "8de5259835758e72",
    "tracker.layout.INBOX": "d9c4d1b7a70cb6f2",
    "tracker.layout.INBOX_DIR_NAME": "919dcb2c2a774098",
    "tracker.layout.IN_INBOX": "fc74c5d3e9ae9444",
    "tracker.layout.IN_OPENED": "633c5d64586b470a",
    "tracker.layout.IN_ORIGINALS": "20496354d6f1b26b",
    "tracker.layout.IN_RETURN": "155a1bfd542aaa0d",
    "tracker.layout.LOOK_ALIKES": "54c49454cf2f5689",
    "tracker.layout.MISPLACED": "b8ca0cd70606f6d7",
    "tracker.layout.NAMELESS": "1bad7ce20105964a",
    "tracker.layout.NAME_COMPATIBILITY": "ec65d3d71fd72b3d",
    "tracker.layout.NAME_DEVICE": "620b97404635bcec",
    "tracker.layout.NAME_EMPTY": "aa82b128dcf1c993",
    "tracker.layout.NAME_FIRST_CHARACTER": "bd62babfb5664dc1",
    "tracker.layout.NAME_ILLEGAL": "305df1e9431d3276",
    "tracker.layout.NAME_INVISIBLE": "2401333e2c513d23",
    "tracker.layout.NAME_LAYOUT_WORD": "978aa80c1fbb2b52",
    "tracker.layout.NAME_MAX_CHARS": "48449a14a4ff7d79",
    "tracker.layout.NAME_SCRIPTS": "3de824b29b62bb49",
    "tracker.layout.NAME_TOO_LONG": "7a5e00d8497fbe2d",
    "tracker.layout.NAME_TRAILING": "7fafe7cda3544c33",
    "tracker.layout.OPENED": "33bdc49eaabcbced",
    "tracker.layout.OPENED_DIR_NAME": "5ef673f341874a6f",
    "tracker.layout.ORIGINALS": "535087da73c5868d",
    "tracker.layout.OUTSIDE": "2f2e7ba21585ff28",
    "tracker.layout.PRIVATE": "68a262e0c0fb929f",
    "tracker.layout.PRIVATE_TREE": "27c7f0479a0c896f",
    "tracker.layout.RETURN": "08633b69eed18c1b",
    "tracker.layout.ROOT": "11ccb349ede85740",
    "tracker.layout.STEP_ABOVE_ROOT": "1385e84ae7f46b2d",
    "tracker.layout.STEP_ABSOLUTE": "f523898e69fbc750",
    "tracker.layout.STEP_BLANK": "a4e9e11cd18fd75b",
    "tracker.layout.STEP_CLIENT_TREE": "5f51b518f9526119",
    "tracker.layout.STEP_NOT_A_PLACE": "d1aa6f26861ccbee",
    "tracker.layout.STEP_NOT_A_RETURN": "1e7d015db6355c80",
    "tracker.layout.STEP_OTHER_HOUSEHOLD": "a0f05df5e57d787b",
    "tracker.layout.STEP_OTHER_YEAR": "7994492387ba5850",
    "tracker.layout.WINDOWS_ILLEGAL_CHARS": "0852803faa2a184a",
    "tracker.layout.WINDOWS_ILLEGAL_CHARS_TEXT": "e4b68ca2e1ff6518",
    "tracker.layout.WINDOWS_RESERVED_NAMES": "99bf9abac32f89f2",
    "tracker.layout.WINDOWS_RESERVED_NAMES_TEXT": "c9d9ad8d312ac5a8",
    "tracker.layout.YEAR": "74c6b2f8351bcc6d",
    "tracker.layout._ASCII_LOOK_ALIKES": "5333fd34ff62ce29",
    "tracker.layout._IGNORABLE_CODES": "999fbf22e2feeb49",
    "tracker.layout._INVISIBLE_CATEGORIES": "bb62d3360fd14a4d",
    "tracker.layout._LAYOUT_WORD_KEYS": "a6d47e2209691833",
    "tracker.layout._ONE_SCRIPT": "17235d2097441c94",
    "tracker.layout._SPOOFING_CODES": "136890ff2b21c3ef",
    "tracker.layout._character": "bd5a8cc4e82855fc",
    "tracker.layout._parts": "a2847013a67202c7",
    "tracker.layout._parts_below_of": "93c8e3b3dcb1a968",
    "tracker.layout._script": "f890f9bb62d24799",
    "tracker.layout.file_name_part_problem": "e0c22d722c38392c",
    "tracker.layout.invisible_problem": "a95be632ca4ceaf4",
    "tracker.layout.is_invisible": "0c3785b4672742ba",
    "tracker.layout.is_reserved_name": "3ee144cf8f5c095d",
    "tracker.layout.is_year_folder": "c89c110db3cb607d",
    "tracker.layout.name_key": "26ebf92810e1480a",
    "tracker.layout.parts_below": "024b4df3065f0f7b",
    "tracker.layout.place_of": "fc1a78ab7179dd32",
    "tracker.layout.place_problem": "2e94883c849c9d08",
    "tracker.layout.recorded_name": "84bfdf3a851f4652",
    "tracker.layout.recorded_subfolder_part": "50620c73d7ae6dab",
    "tracker.layout.segment_problem": "c85f6ed345abe1fd",
    "tracker.layout.spoofing_problem": "2dea825aad86d0a7",
    "tracker.ledger.ACCEPTED_KEY": "f4764fc7a8ddd588",
    "tracker.ledger.ALSO_KEY": "da42922852e5dfcd",
    "tracker.ledger.ASKED_KEY": "46da5b49eea2fbee",
    "tracker.ledger.AT_KEY": "22eb1fa0c521db09",
    "tracker.ledger.DIGEST_KEY": "889a0f98aa32537e",
    "tracker.ledger.DRAFTED": "ef02a62df7dc350b",
    "tracker.ledger.DRAFT_APPROVED": "41bf68b11dd88d88",
    "tracker.ledger.EVENTS": "c6d719a66bc0b51d",
    "tracker.ledger.EVENT_KEY": "9e0d5d1c8d94a5b6",
    "tracker.ledger.FILE_KEY": "0efde3f4308de780",
    "tracker.ledger.FINGERPRINT_KEY": "7df2d13d670e5ed4",
    "tracker.ledger.FOLDER_NAME_ACCEPTED": "b7b92a8807e8bbf9",
    "tracker.ledger.FORMAT_KEY": "04fc6c808adf51ac",
    "tracker.ledger.FROM_KEY": "8ecb478c3dc0d3ae",
    "tracker.ledger.HELD_KEY": "85c4d432c47707ee",
    "tracker.ledger.HOST_KEY": "e293b75405af70cd",
    "tracker.ledger.HOUSEHOLD_CHANGED": "783c776c223a869f",
    "tracker.ledger.HOUSEHOLD_KEY": "8de5259835758e72",
    "tracker.ledger.IDENTIFIER_KEY": "123a87f051936a7e",
    "tracker.ledger.INFO_KEY": "ef3370879a96cf2e",
    "tracker.ledger.KEYWORD_KEY": "a51a9ff6a628d820",
    "tracker.ledger.KEYWORD_LEARNED": "7a5d6590fc40e09a",
    "tracker.ledger.KEYWORD_UNLEARNED": "ce11d4a4c4da44a9",
    "tracker.ledger.KEY_KEY": "632a3e84412d6ea8",
    "tracker.ledger.LINE_KEYS": "bfa2973d92dd93ad",
    "tracker.ledger.LINK_KEY": "67b4e6e1e90cbc98",
    "tracker.ledger.MOVE_ABANDONED": "a11db9ac01cd5285",
    "tracker.ledger.MOVING": "d290155f3097fcde",
    "tracker.ledger.OPS_KEY": "2c35289e43246c9f",
    "tracker.ledger.OP_COPY": "477c02e96b3c4061",
    "tracker.ledger.OP_KEY": "b27b68850018781c",
    "tracker.ledger.OP_MOVE": "c4a4adaf72f566c1",
    "tracker.ledger.OP_REMOVE": "e8c2c1465f168081",
    "tracker.ledger.REASON_KEY": "ffa78aeaf553b544",
    "tracker.ledger.RECORD_FORMAT": "6b86b273ff34fce1",
    "tracker.ledger.RELEASED": "81acce4087249f66",
    "tracker.ledger.REMOVED_KEY": "760f3c525ed93b07",
    "tracker.ledger.RETIRED_EVENTS": "ca06b9854a7990f9",
    "tracker.ledger.ROW_EVENTS": "b53cc1cb7387825b",
    "tracker.ledger.ROW_KEY": "e4d99047ca6a3721",
    "tracker.ledger.RULES_CHANGED": "e4535fc89d8ef96d",
    "tracker.ledger.RULES_IMPORTED": "cddb10ca0e4c2100",
    "tracker.ledger.RULES_KEY": "a29e7581476cd7ad",
    "tracker.ledger.SCANNED": "7e17f4790bff13d5",
    "tracker.ledger.SHARING_CONFIRMED": "c8027ef3eb13f5e3",
    "tracker.ledger.STAGE_KEY": "874095181f94a63d",
    "tracker.ledger.STATUSES_KEY": "18c7785691d58b80",
    "tracker.ledger.TEXT_FINGERPRINT_KEY": "0db6b5095dc3896e",
    "tracker.ledger.TO_KEY": "e28f3243b469e21d",
    "tracker.ledger.WAS_KEY": "1d383f963e096e21",
    "tracker.ledger.op_ends": "a4e5e845ab4c8deb",
    "tracker.reasons.KNOWN_CODES": "4ad3f21d00c7f8e5",
    "tracker.records.BLANK_BOUNDS": "cec8e55a02712202",
    "tracker.records.CANDIDATE_SEP": "3c01b9ef061065a0",
    "tracker.records.DATE_FIELDS": "f0aaa0cb84de4063",
    "tracker.records.FEED_REFUSED": "d601e93b18987f24",
    "tracker.records.MAX_EXPECTED_COUNT": "888df25ae3577242",
    "tracker.records.MAX_FILE_COUNT": "888df25ae3577242",
    "tracker.records.MAX_ROW": "888df25ae3577242",
    "tracker.records.MAX_ROW_SIZE_KB": "02bfbb85ecfba2af",
    "tracker.records.MAX_SIZE_KB": "50b4b069390c1d79",
    "tracker.records.MIN_EXPECTED_COUNT": "6b86b273ff34fce1",
    "tracker.records.MIN_SIZE_KB_FLOOR": "5feceb66ffc86f38",
    "tracker.records.MIN_SPELLING_WORDS": "d4735e3a265e16ee",
    "tracker.records.OVERRIDE_BOUNDS": "22a3650c5fc6e021",
    "tracker.records.PERSON_KINDS": "11ac10e2383de5cc",
    "tracker.records.RULE_FLAG_FIELDS": "c500b9a01ed742b3",
    "tracker.records.RULE_LIST_FIELDS": "8b3d25ca8662bd02",
    "tracker.records.TEXT_BOUNDS": "ce369c3539b412af",
    "tracker.records.WAITS_FOR_ANSWERS": "f0615f5bcc293884",
    "tracker.records.WAITS_FOR_BOUNDS": "6f57ee0ee5ca0bbc",
    "tracker.records.WAITS_FOR_SEP": "de9881cacd5c858e",
    "tracker.records.YEAR_MAX": "1aaf97e300d50bac",
    "tracker.records.YEAR_MIN": "e41d64db5703c644",
    "tracker.records._ENTRY_LONG_TEXT": "108c25e4b80db4c6",
    "tracker.records._ENTRY_NAMES": "5980f2d1176281a2",
    "tracker.records._ENTRY_TEXT": "68e0df1c43ff5282",
    "tracker.records._INFO_LONG_TEXT": "69674950c21f7eae",
    "tracker.records._INFO_TEXT": "cbdf6035c202636d",
    "tracker.records._RULE_TEXT": "4dbd8ce696bb0f8e",
    "tracker.records._objects_from_json": "150fd8d193ee1603",
    "tracker.records.entry_problem": "a79ea9e62a85223a",
    "tracker.records.feed_from_json": "b2e5148af638d97c",
    "tracker.records.feeds_from_json": "73f791f77660a6d8",
    "tracker.records.format_waits_for": "a9f50749433f46ce",
    "tracker.records.household_problem": "d341e98e6700e560",
    "tracker.records.info_problem": "a14147da699ad792",
    "tracker.records.is_a_spelling": "9872f0754c1f928d",
    "tracker.records.name_parts": "2fb3aa450c490a16",
    "tracker.records.name_words": "888ff2df30e14d73",
    "tracker.records.parse_waits_for": "fe2da49df5b9f8ce",
    "tracker.records.people_from_json": "bd021c769cc1a5d8",
    "tracker.records.person_from_json": "d6e448c24d1dd1a5",
    "tracker.records.rule_row_fault": "40478ee286dbf2db",
    "tracker.records.rule_row_problem": "bfbfa65df0936781",
    "tracker.records.split_codes": "312e8af4bdb2dc38",
    "tracker.records.status_problem": "0a4507873e497b78",
    "tracker.records.waits_for_problem": "463d041ef7fa9219",
    "tracker.records.word_list_problem": "64d72805fbba0527",
}}


def names_bound_in(tree: ast.Module) -> set[str]:
    """Every name the function in ``tree`` binds inside itself: its
    parameters (a nested function's and a lambda's too), the targets of an
    assignment, an augmented or annotated assignment, a ``:=``, a ``for``, a
    ``with``, a comprehension, a ``del`` and an ``except ... as``, a match
    pattern's captures, the names of a nested ``def`` or ``class``, and what
    an ``import`` inside it binds. Not the function's own name, which belongs
    to the scope around it, and not a name it declares ``global``, which is
    the module's. A name in this set is not the module-level name that
    happens to be spelled the same, so :func:`admission_closure` never reads
    it as a callee or a constant: the store's ``kind`` parameter is not the
    function ``store.kind``, and following it hashed 30 parts the
    admission never runs (the architecture audit's B-2). Whole-tree on
    purpose: a name bound only in a nested scope also hides the outer
    function's read of a module name spelled the same, which would leave a
    part out of the pin; no function in the closure does that today."""
    root = tree.body[0]
    bound: set[str] = set()
    declared_global: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            bound.add(node.id)
        elif isinstance(node, ast.arg):
            bound.add(node.arg)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node is not root:
            bound.add(node.name)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            bound.add(node.name)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            bound.update((alias.asname or alias.name.split(".")[0]) for alias in node.names)
        elif isinstance(node, (ast.MatchAs, ast.MatchStar)) and node.name:
            bound.add(node.name)
        elif isinstance(node, ast.MatchMapping) and node.rest:
            bound.add(node.rest)
        elif isinstance(node, ast.Global):
            declared_global.update(node.names)
    return bound - declared_global


def admission_closure(roots=None) -> dict[str, str]:
    """Every part of the store's admission, by its qualified name: the
    source of every package function reachable from
    ``store._refuse_a_malformed_line`` - through the store, ``records``,
    ``ledger``, ``layout`` or anything else under ``tracker/``, including
    modules it imports at call time - and the ``repr`` of every package
    constant those functions read (a bound, a limit, a pattern). Found by
    walking each function's syntax tree, so a new callee joins by itself
    (the re-review's SF1: the rule R3b was built for lives in ``records``,
    not in the two functions a narrower pin hashed). A name the function
    binds itself (:func:`names_bound_in`) is not looked up among the module's
    names. ``roots`` are the functions to start from, the store's two
    admission functions when none are given; a test names a made-up one."""
    import importlib
    import inspect
    import re as _re
    import textwrap
    import types

    parts: dict[str, str] = {}
    todo = list(roots) if roots is not None else [store._refuse_a_malformed_line, store._line_keys_problem]
    seen: set[str] = set()
    while todo:
        function = todo.pop()
        name = f"{function.__module__}.{function.__qualname__}"
        if name in seen:
            continue
        seen.add(name)
        source = textwrap.dedent(inspect.getsource(function))
        parts[name] = source
        tree = ast.parse(source)
        local = names_bound_in(tree)
        names = {key: value for key, value in function.__globals__.items() if key not in local}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("tracker"):
                module = importlib.import_module(node.module)
                for alias in node.names:
                    names[alias.asname or alias.name] = getattr(module, alias.name, None) \
                        or importlib.import_module(f"{node.module}.{alias.name}")
        for node in ast.walk(tree):
            found = None
            # A dunder (``__file__``, ``__name__``) is where the code sits, not a rule,
            # and ``__file__`` differs on every machine.
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id in names                     and not node.id.startswith("__"):
                found = (f"{function.__module__}.{node.id}", names[node.id])
            elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and \
                    isinstance(names.get(node.value.id), types.ModuleType):
                module = names[node.value.id]
                if module.__name__.startswith("tracker") and hasattr(module, node.attr)                         and not node.attr.startswith("__"):
                    found = (f"{module.__name__}.{node.attr}", getattr(module, node.attr))
            if found is None:
                continue
            where, value = found
            # A remembered rule (P219's ``functools.lru_cache``) is the rule
            # it wraps: followed through, so the pin still reaches it.
            value = inspect.unwrap(value) if callable(value) and hasattr(value, "__wrapped__") else value
            if inspect.isfunction(value) and value.__module__.startswith("tracker"):
                todo.append(value)
            elif isinstance(value, (set, frozenset)):
                parts.setdefault(where, repr(sorted(map(repr, value))))
            elif isinstance(value, (str, int, float, bytes, tuple, dict, _re.Pattern)):
                parts.setdefault(where, repr(value))
    return parts


def admission_digests() -> dict[str, str]:
    import hashlib

    return {name: hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
            for name, text in sorted(admission_closure().items())}


def test_admission_version_changes_with_the_admission():
    """Decision 209, R3b: every applied line is judged again only when
    ``ADMISSION_VERSION`` rises, so a change that makes the admission - or
    anything it calls - refuse something it used to admit must raise it in
    the same commit, or a line applied before the change stands for good."""
    now = admission_digests()
    pinned = ADMISSION_PIN.get(store.ADMISSION_VERSION, {})
    moved = sorted(name for name in now.keys() | pinned.keys() if now.get(name) != pinned.get(name))
    assert not moved, (
        f"The store's admission changed in: {', '.join(moved)}. If it now refuses anything it used "
        f"to admit, raise store.ADMISSION_VERSION by one and pin admission_digests() under the new "
        f"version, so every line an earlier version applied is judged again. If it refuses nothing "
        f"new (a comment, a rewording, a wider admission, a part that is not a rule), pin "
        f"admission_digests() under version {store.ADMISSION_VERSION} instead.")


def test_the_admission_pin_reaches_the_rules_it_calls():
    """The re-review's SF1: the pin reaches past the two functions into the
    rules they delegate to - the Date Pattern rule R3b was built for, the
    place and label rules, a move's two ends - and the bounds they read."""
    parts = admission_closure()
    for name in ("tracker.bounds.date_pattern_problem", "tracker.records.rule_row_problem",
                 "tracker.layout.place_problem", "tracker.layout.segment_problem",
                 "tracker.ledger.op_ends", "tracker.records.MAX_EXPECTED_COUNT"):
        assert name in parts, name


#: A made-up module for the walker (SPEC-architecture J1, R1.2). Every function
#: reads the name ``helper``. ``unshadowed`` and ``by_global_declaration`` read
#: the module's function of that name; each of the others binds the name itself,
#: in one of the ways Python binds a name, so none of them calls the module's.
#: The module is never run - the walker reads source.
SHADOWING_MODULE = """
def helper(row):
    return row


def unshadowed(row):
    return helper(row)


def by_parameter(row, helper):
    return helper(row)


def by_assignment(row):
    helper = len
    return helper(row)


def by_augmented_assignment(row):
    helper += 1
    return helper


def by_annotated_assignment(row):
    helper: int = 1
    return helper


def by_walrus(row):
    return (helper := len) and helper(row)


def by_for_target(rows):
    for helper in rows:
        helper(rows)


def by_with_target(path):
    with open(path) as helper:
        return helper(path)


def by_comprehension(rows):
    return [helper(row) for helper in rows]


def by_except_clause(row):
    try:
        return row
    except ValueError as helper:
        return helper(row)


def by_nested_def(row):
    def helper(item):
        return item
    return helper(row)


def by_nested_class(row):
    class helper:
        pass
    return helper(row)


def by_import_inside(row):
    from os.path import join as helper
    return helper(row)


def by_global_declaration(row):
    global helper
    taken = helper
    helper = None
    return taken(row)
"""
SHADOWED_BY = ["by_assignment", "by_augmented_assignment", "by_annotated_assignment", "by_walrus",
               "by_for_target", "by_with_target", "by_comprehension", "by_except_clause",
               "by_nested_def", "by_nested_class", "by_import_inside"]


@pytest.fixture(scope="module")
def shadowing(tmp_path_factory):
    import importlib.util

    path = tmp_path_factory.mktemp("shadowing") / "tracker_shadowing.py"
    path.write_text(SHADOWING_MODULE, encoding="utf-8")
    spec = importlib.util.spec_from_file_location("tracker_shadowing", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a_parameter_that_shadows_a_function_does_not_pull_it_into_the_closure(shadowing):
    """The architecture audit's B-2: ``_refuse_a_malformed_line`` has a
    parameter ``kind``, and the walker followed it into the store's function
    ``kind`` and on into settings, so the pin held 30 parts the admission
    never runs. A parameter is the caller's value, not the module's
    function of the same spelling; the same function without the parameter
    does call it, so the walker still follows a real callee."""
    assert set(admission_closure([shadowing.unshadowed])) == {
        "tracker_shadowing.unshadowed", "tracker_shadowing.helper"}
    assert set(admission_closure([shadowing.by_parameter])) == {"tracker_shadowing.by_parameter"}


@pytest.mark.parametrize("function", SHADOWED_BY)
def test_a_name_the_function_binds_itself_is_not_followed_as_a_callee(shadowing, function):
    """Every way a function binds a name hides the module's name from the
    walker: the module-level ``helper`` is not a callee of a function that
    assigns, loops, opens, catches, defines or imports its own ``helper``."""
    assert set(admission_closure([getattr(shadowing, function)])) == {f"tracker_shadowing.{function}"}


def test_a_name_declared_global_is_still_the_modules(shadowing):
    """``global helper`` says the name is the module's, so a read of it is a
    read of the module's function though the body also assigns the name, and
    the walker follows it."""
    assert set(admission_closure([shadowing.by_global_declaration])) == {
        "tracker_shadowing.by_global_declaration", "tracker_shadowing.helper"}


def test_the_store_admits_the_accepted_key_with_one_value():
    """Decision 188 (T15): a person's word that a folder's name is accepted
    is admitted on the two events that name a household or a return, with
    its one value - and refused with any other value, or on any other
    event, without quoting what the line said."""
    from tracker.layout import PRIVATE_TREE

    household = f"{PRIVATE_TREE}/Park Household"
    word = {ledger.ACCEPTED_KEY: ledger.FOLDER_NAME_ACCEPTED}
    store._refuse_a_malformed_line(ledger.new(
        ledger.HOUSEHOLD_CHANGED, household={"name": "Park Household"}, **word), 2, household,
        kind=store.KIND_HOUSEHOLD)
    store._refuse_a_malformed_line(ledger.new(
        ledger.RULES_CHANGED, info={"household": "Park Household"}, **word), 2,
        f"{household}/2025/1040 - Park", kind=store.KIND_RETURN)
    for event in (
        ledger.new(ledger.HOUSEHOLD_CHANGED, household={"name": "X"},
                   **{ledger.ACCEPTED_KEY: "everything"}),
        ledger.new(ledger.RULES_CHANGED, info={}, **{ledger.ACCEPTED_KEY: True}),
        ledger.new(ledger.SHARING_CONFIRMED, **word),
    ):
        with pytest.raises(store.StoreError) as refused:
            store._refuse_a_malformed_line(event, 2, household, kind=store.KIND_HOUSEHOLD)
        assert "'accepted' that is not a folder's name accepted" in str(refused.value)
        assert "everything" not in str(refused.value)


def test_a_related_list_that_is_not_folder_names_is_refused_at_admission():
    """Pilot P170 (admission 3): a ``household_changed`` line whose related
    list is not a list of text, or names something that is not one folder
    name, is refused by name before it reaches a column."""
    from tracker.layout import NAME_ILLEGAL, PRIVATE_TREE

    household = f"{PRIVATE_TREE}/Smith Family"
    for related in ("Lee Family", [1], [{"name": "Lee"}]):
        with pytest.raises(store.StoreError, match="'related' that is not a list of household names"):
            store._refuse_a_malformed_line(ledger.new(ledger.HOUSEHOLD_CHANGED, household={"related": related}),
                                           2, household, kind=store.KIND_HOUSEHOLD)
    with pytest.raises(store.StoreError) as refused:
        store._refuse_a_malformed_line(ledger.new(ledger.HOUSEHOLD_CHANGED, household={"related": ["Lee/.."]}),
                                       2, household, kind=store.KIND_HOUSEHOLD)
    assert f"'related' that is not one folder name ({NAME_ILLEGAL})" in str(refused.value)
    store._refuse_a_malformed_line(ledger.new(ledger.HOUSEHOLD_CHANGED, household={"related": ["Lee Family"]}),
                                   2, household, kind=store.KIND_HOUSEHOLD)
