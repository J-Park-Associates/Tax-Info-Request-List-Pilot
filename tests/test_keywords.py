"""Tests for tracker/keywords.py - the matcher and the rules a reading is judged by, on made-up text."""

import pytest

from tests.content_check_helpers import item
from tracker.keywords import evaluate_rules


def test_evaluate_rules_lists_all_missing():
    result = evaluate_rules("nothing here", item(required_keywords=("Alpha", "Beta")))
    assert "'Alpha'" in result.reason and "'Beta'" in result.reason


def test_own_forms_is_none_for_one_family_and_the_named_set_for_two():
    from tests.samples import scanned_1098_lines, scanned_w2_lines
    from tracker.keywords import MULTI_FORM_FAMILIES, own_forms, self_named_forms

    one = "\n".join(scanned_w2_lines(2025))
    two = "\n".join(scanned_w2_lines(2025) + scanned_1098_lines(2025))
    assert MULTI_FORM_FAMILIES == 2
    assert own_forms(self_named_forms(one)) is None                # the ordinary reading
    assert own_forms(self_named_forms("a letter about nothing in particular")) is None
    assert own_forms(self_named_forms(two)) == set(self_named_forms(two)) == {"w2", "1098"}


@pytest.mark.parametrize("text, own", [
    ("Form 1040 (2025)", "1040"), ("Form 1099-DIV (Rev. January 2024)", "1099div"), ("941 for 2026:", "941"),
    ("Form W-2 Wage and Tax Statement 2025", "w2"),        # plain: nothing quotes it, it is named in its own right
])
def test_a_form_names_itself_with_its_year_or_revision(text, own):
    from tracker.keywords import _PLAIN_WEIGHT, _mentions

    (key, _, weight), = list(_mentions(text.lower()))
    assert key == own and weight >= _PLAIN_WEIGHT


@pytest.mark.parametrize("text", [
    "(Form 1040)", "Form 1040 or 1040-SR", "Form 1040 instructions", "Form 1040, line 8", "Form 1040 for individuals",
    "attach Form 1098", "Forms W-2", "reported on Form 1099-INT", "a 1098 - for my return", "see Form 1099-NEC, to use",
    "such as Form 1040)", "Interest and dividends: attach Forms 1099-INT and 1099-DIV",
])
def test_a_form_quoted_in_a_sentence_is_a_reference(text):
    from tracker.keywords import _REFERENCE_WEIGHT, _mentions

    assert all(weight == _REFERENCE_WEIGHT for _, _, weight in _mentions(text.lower()))


def test_the_dominant_form_is_the_heaviest_then_the_first_mentioned():
    from tracker.keywords import dominant_forms

    # A W-2's instructions name Form 1040 many times; the W-2 names itself with its year.
    assert dominant_forms("Form W-2 (2025) " + "see Form 1040 line 1. " * 30) == {"w2"}
    # Two forms named in their own right, equally: the first mentioned.
    assert dominant_forms("Form 1099-INT (2025) Interest Income\nForm 1099-DIV (2025) Dividends") == {"1099int"}
    # Once in passing, beside another form: nobody's.
    assert dominant_forms("You must file Form 941, Form 940 and Form W-2.") == set()
    # A number that is not a known family counts only after "Form", and takes a variant only by a dash.
    assert dominant_forms("Form 4562 (2025) Depreciation and Amortization") == {"4562"}
    assert dominant_forms("4562 4562 4562 (2025)") == set()
    assert dominant_forms("Form 1125-E (Rev. October 2016) Compensation of Officers") == {"1125e"}
    assert dominant_forms("Form 4562 depreciation\nForm 4562 depreciation") == {"4562"}   # "4562 depreciation" is not 4562-DEPR


def test_a_form_told_to_the_reader_is_a_reference_whatever_follows_it():
    # The tenth reading: "attach Form 1098 (2025)" read as a form naming
    # itself, because the year was looked at before the word in front.
    from tracker.keywords import _REFERENCE_WEIGHT, _mentions, says

    for text in ("attach Form 1098 (2025)", "see Form 1098 for 2025 mailed separately", "Forms W-2 2025"):
        assert all(weight == _REFERENCE_WEIGHT for _, _, weight in _mentions(text.lower())), text
    assert not says("2025 Individual Income Tax Organizer\nMortgage interest paid: attach Form 1098 (2025)", "1098")
    assert not says("Annual Escrow Account Disclosure Statement\nFor your deduction, see Form 1098 for 2025.", "1098")


def test_a_title_that_lists_three_forms_names_none_of_them():
    from tracker.keywords import _title_forms, says

    checklist = ("2025 Individual Income Tax Organizer\nIncome Documents Checklist\n"
                 "Form W-2 - Wage and Tax Statement\nForm 1098 - Mortgage Interest Statement\n"
                 "Form 1099-INT - Interest Income\nForm 1099-DIV - Dividends and Distributions")
    assert _title_forms(checklist.lower()) == set()
    assert not says(checklist, "1098") and not says(checklist, "1099-int")
    # A transmittal lists its forms with commas, and every form after one
    # continues the list (the thirteenth reading), which leaves the first
    # naming itself - and the firm's letter is still none of the rows'
    # documents, because none of them asks for a W-2 by its number alone.
    transmittal = "Enclosed please find: Form W-2 2025, Form 1098 2025, Form 1099-INT 2025"
    assert _title_forms(transmittal.lower()) == {"w2"}
    assert not says(transmittal, "1098") and not says(transmittal, "1099-int")
    # Families, not numbers: a broker's consolidated 1099 names the family and
    # its parts and is one family's document, which the rows then contest.
    composite = ("vanguard brokerage services\n2025 consolidated form 1099 - account 8812-4455\n"
                 "form 1099-int   interest income\nform 1099-div   dividends and distributions\n"
                 "form 1099-b   proceeds from broker and barter exchange transactions")
    assert _title_forms(composite) == {"1099int", "1099div", "1099b"}   # "Form 1099 - Account" is set off by its dash
    assert says(composite, "1099-int") and says(composite, "1099-b")
    # A checklist sets a form off from its title with a dash; no form names itself that way.
    assert _title_forms("form 1099-int - interest income\nform 1099-div - dividends and distributions") == set()
    assert _title_forms("form 1099-int   interest income   2025\nform 1099-div   dividends   2025") == {"1099int", "1099div"}
    assert _title_forms("form w-2 - 2025 wage and tax statement") == {"w2"}     # a dash before the year is still dated
    # A sentence wraps where it will: the word before a form may end the line above.
    assert not says("2025 organizer\nmortgage interest paid: please attach\nform 1098 (2025) from each lender", "1098")
    assert not says("annual escrow account disclosure\nfor your deduction, see\nform 1098 for 2025 mailed separately", "1098")


def test_a_form_number_in_the_title_counts_only_when_named_in_its_own_right():
    from tracker.keywords import says

    attention = ("Attention: Which Revision To Use for Which Year. For all forms that we do not issue annually "
                 "(such as Form 1099-NEC), we issue the revision to use for the next calendar year. ")
    assert not says(attention + "Form 1098-T Tuition Statement 2025", "1099-nec")
    assert says(attention + "Form 1098-T Tuition Statement 2025", "1098-t")
    assert not says("2025 Tax Organizer\nMortgage interest: attach Form 1098\nRetirement: attach Forms 1099-R", "1098")
    assert says("Form 1098 Mortgage Interest Statement 2025", "1098")
    assert says("Attached: Form 1099-INT, Form 1098 and W-2 for 2025 tax prep\nForm W-2 Wage and Tax Statement", "w-2")
    assert not says("Subject: Your 2025 Form 1099-R is ready\nForm 5498 IRA Contribution Information 2025", "1099-r")


def test_a_single_dash_set_off_form_beside_its_year_names_itself():
    # Decision 69 made a dash after a form number a checklist's line, which
    # parked a payer's own substitute form: "2025 Form 1099-INT - Interest
    # Income" is how a bank prints its title. A menu *lists* - two such
    # lines or more in the title window - and a single one, dated on its
    # own line, is a form naming itself.
    from tracker.keywords import _title_forms, says

    assert says("2025 Form 1099-INT - Interest Income\nAlly Bank  1 Interest income 1,842.55", "1099-int")
    assert says("Form 1098 - Mortgage Interest Statement  2025\n1 Mortgage interest received 14,220.19", "1098")
    menu = ("2025 Individual Income Tax Organizer - Interest and Dividend Income\n"
            "Form 1099-INT - Interest Income\nForm 1099-DIV - Dividends and Distributions")
    assert _title_forms(menu.lower()) == set()
    # No year beside it: a checklist's line, as before.
    assert not says("Income Documents\nForm 1099-INT - Interest Income\nPayer  Amount", "1099-int")
    # An ask before it is an ask, year or no year.
    assert not says("2025 Organizer\nPlease attach Form 1098 - Mortgage Interest Statement 2025", "1098")


def test_a_form_after_a_comma_continues_a_list():
    # A cover's last form carries no punctuation after it, so it was read as
    # named in its own right and blinded the form printed behind it.
    from tracker.keywords import says

    cover = ("Charles Schwab  2025 Tax Reporting Package\n"
             "Enclosed: Form 1099-INT, Form 1098, Form 5498\n"
             "Form 1099-INT Interest Income 2025\n1 Interest income 1,842.55")
    assert not says(cover, "5498") and not says(cover, "1098")
    assert says(cover, "1099-int")


def test_a_menu_line_names_neither_the_form_nor_its_title():
    # The form and its title on a checklist line are one reference: the
    # firm's organizer sets "Form 1099-B" off from "Proceeds From Broker
    # and Barter Exchange Transactions" with a dash, and the row that keys
    # on the broker's words filed the organizer page as the client's 1099-B.
    from tracker.keywords import says

    page = ("2025 Individual Income Tax Organizer - Investment Income\n"
            "Form 1099-B - Proceeds From Broker and Barter Exchange Transactions\n"
            "Form 1099-DIV - Dividends and Distributions\n"
            "Please list every brokerage account below.  Broker  Account number")
    assert not says(page, "1099-b")
    assert not says(page, "proceeds from broker")
    # A comma sets a form off from its title the same way.
    assert not says("Form 1099-INT, Interest Income\nPayer  Amount", "interest income")
    # The form's own page is not a menu, so its title is its own.
    assert says("Form 1099-B Proceeds From Broker and Barter Exchange Transactions 2025\n"
                "1d Proceeds 24,318.55", "proceeds from broker")


def test_a_document_does_not_ask_for_itself():
    # An ask governs the rest of its sentence, because one ask names several
    # documents; across a line break it governs only the wrap.
    from tracker.keywords import says

    organizer = ("2025 Individual Income Tax Organizer - Investment Income\n"
                 "Did you sell any stocks, bonds or mutual funds in 2025?\n"
                 "If yes, attach your brokerage statement and any realized gain and loss report.")
    assert not says(organizer, "brokerage statement")
    assert not says(organizer, "realized gain and loss")
    fiduciary = ("2025 Fiduciary Organizer - Investment Income\n"
                 "Attach the year-end account statement for each brokerage account.\n"
                 "Attach the realized gain and loss report for the year.")
    assert not says(fiduciary, "year-end account statement")
    assert not says(fiduciary, "realized gain and loss")
    assert not says("Mortgage interest: please attach\nyour brokerage statement", "brokerage statement")
    # The broker's own statement says it plainly, and a line further up than
    # the wrap is another label, not the rest of a request: a return's
    # "Attach Forms W-2G and 1099-R if tax was withheld" two lines above its
    # jurat asks for nothing on the jurat's line.
    assert says("Charles Schwab & Co., Inc.\nYear-End Brokerage Statement January 1, 2025 - December 31, 2025\n"
                "Realized Gain and Loss Summary", "brokerage statement")
    assert says("Attach Forms W-2G and 1099-R if tax was withheld\n1e Taxable dependent care benefits\n"
                "Sign Here Under penalties of perjury, I declare", "under penalties of perjury")


def test_a_keyword_may_name_alternatives_and_the_words_one_of_them_wants_together():
    # Decision 90. Required Keywords is an AND over its cells and Any
    # Keywords an OR over theirs, and neither can say "these three words,
    # or this one" - which is what the prior-year return row has to say,
    # because a standalone state return shares none of the federal
    # return's lines, jurat included.
    from tracker.keywords import contains_keyword, says

    prior_return = ("individual income tax return + filing status + under penalties of perjury"
                    " | resident income tax return")
    federal = ("Form 1040 2024 U.S. Individual Income Tax Return\n"
               "Filing Status Single Married filing jointly\n"
               "Sign Here Under penalties of perjury, I declare")
    state = "TAXABLE YEAR FORM\n2024 California Resident Income Tax Return 540"
    assert says(federal, prior_return)
    assert says(state, prior_return)
    # Two of the three is not the federal alternative: the firm's own
    # organizer says both and signs nothing (decision 65).
    assert not says("2024 Individual Income Tax Organizer\nFiling Status Single", prior_return)
    # A keyword holding neither character is one phrase, exactly as before.
    assert says("Trial Balance - Year-End 2025", "trial balance")
    # A file name is read the same way, phrase by phrase.
    assert contains_keyword("2024 california resident income tax return", prior_return)
    assert not contains_keyword("2024 individual income tax return", prior_return)


def test_the_any_keywords_are_read_apart_from_every_other_rule():
    # The year a Period implies is a check on a document a keyword already
    # matched, so the router can ask which rows a document's words fit
    # without reading a verdict's sentence back.
    from tracker.keywords import any_keyword_matched

    childcare = item(any_keywords=("child care statement",), date_pattern=r"(?i)\b2025\b")
    assert any_keyword_matched("2024 Child Care Statement", childcare)
    assert not any_keyword_matched("2024 Tuition Statement", childcare)
    assert not any_keyword_matched("anything at all", item(required_keywords=("w-2",)))


def test_a_keywords_words_are_on_one_line_or_wrap_as_a_heading():
    from tracker.keywords import contains_keyword

    # Two labels on two lines are not one phrase.
    assert not contains_keyword("19 Distributions\nSchedule K-1 (Form 1065) 2025", "distribution schedule")
    assert not contains_keyword("16 Items affecting shareholder basis\nSchedule K-1 (Form 1120-S)", "shareholder basis schedule")
    # A heading wraps from the start of its line, two words or more on the first.
    assert contains_keyword("Balance Sheet\nAs of December 31, 2025", "balance sheet as of")
    assert contains_keyword("  Fixed Asset\n  Schedule", "fixed asset schedule")
    assert contains_keyword("Statement of\nFinancial Position", "statement of financial position")
    # One word over another is two labels; the 1098's one-word-per-line title is known by its number.
    assert not contains_keyword("Mortgage\nInterest\nStatement", "mortgage interest statement")
    assert not contains_keyword("Distributions\nSchedule", "distribution schedule")
    # A phrase that begins mid-line and runs on is a sentence, not a heading.
    assert not contains_keyword("the items affecting shareholder basis\nschedule", "shareholder basis schedule")
    # One line, as before: spaces, tabs, a no-break space, a dash.
    assert contains_keyword("Fixed\xa0Asset\tSchedule", "fixed asset schedule")
    assert contains_keyword("fixed-asset-schedule.pdf", "fixed asset schedule")
    assert not contains_keyword("W\n2", "w-2")


#: A W-2 as a reader meets it: its number and title at the top, its own
#: number again at the foot of page 1 the way the IRS sets it, and a box
#: label deep on page 2 that no footer and no title carries.
_FILLER = "Wage and Tax Statement for the employee named below. " * 12


TWO_PAGE_W2 = (
    "Form W-2 (2025) Wage and Tax Statement\n" + _FILLER
    + "\nemployer identification number 00-0000000\nForm W-2 (2025)\n"
    + "\f" + "dependent care benefits paid in the year\n" + _FILLER
    + "\nsafe harbor election\nCopy B to be filed with the return\n"
)


def test_a_title_self_mention_is_evidence_from_the_title():
    from tracker.records import RULE_REQUIRED, WHERE_TITLE

    result = evaluate_rules(TWO_PAGE_W2, item(required_keywords=("W-2", "wage and tax statement")))
    assert result.ok
    assert [(e.rule, e.term, e.where, e.page) for e in result.evidence] == [
        (RULE_REQUIRED, "W-2", WHERE_TITLE, 1),
        (RULE_REQUIRED, "wage and tax statement", WHERE_TITLE, 1),
    ]


def test_a_footer_hit_names_the_footer_and_the_page_it_was_on():
    from tracker.records import WHERE_FOOTER

    result = evaluate_rules(TWO_PAGE_W2, item(required_keywords=("safe harbor election",)))
    assert result.ok
    assert [(e.where, e.page) for e in result.evidence] == [(WHERE_FOOTER, 2)]
    # Page 1's own footer is a footer too, not "the first page".
    first = evaluate_rules(TWO_PAGE_W2, item(required_keywords=("employer identification number",)))
    assert [(e.where, e.page) for e in first.evidence] == [(WHERE_FOOTER, 1)]


def test_a_deep_any_keyword_says_it_was_deep_and_which_page():
    from tracker.records import RULE_ANY, WHERE_DEEP

    result = evaluate_rules(TWO_PAGE_W2, item(any_keywords=("dependent care benefits", "tips")))
    assert result.ok
    # Only the keyword that matched leaves evidence; "tips" said nothing.
    assert [(e.rule, e.term, e.where, e.page) for e in result.evidence] == [
        (RULE_ANY, "dependent care benefits", WHERE_DEEP, 2),
    ]


def test_the_date_rule_records_the_period_it_checked_never_the_document():
    from tracker.records import RULE_DATE

    rule = item(period="TY2025", date_pattern=r"(?i)\b2025\b",
                required_keywords=("wage and tax statement",))
    result = evaluate_rules(TWO_PAGE_W2, rule)
    assert result.ok
    dates = [e for e in result.evidence if e.rule == RULE_DATE]
    # The row's own Period, which a person can read; the regex it derives is
    # in the reason when the check fails, and no word of the document is here.
    assert [e.term for e in dates] == ["TY2025"]


def test_a_failing_verdict_keeps_what_did_match():
    # The verdict and its sentence are untouched; what matched is the lead a
    # person works the parked file from.
    result = evaluate_rules(
        TWO_PAGE_W2, item(required_keywords=("wage and tax statement", "1099-INT")),
    )
    assert not result.ok and "'1099-INT'" in result.reason
    assert [e.term for e in result.evidence] == ["wage and tax statement"]


def test_the_compact_evidence_parses_back_to_what_was_formatted():
    from tracker.records import RULE_FILENAME, WHERE_TITLE, Evidence, format_evidence, parse_evidence

    record = {
        "C01": evaluate_rules(TWO_PAGE_W2, item(
            period="TY2025", date_pattern=r"(?i)\b2025\b",
            required_keywords=("W-2", "safe harbor election"),
            any_keywords=("dependent care benefits",),
        )).evidence,
        "L01": (Evidence(RULE_FILENAME, "1098-t", WHERE_TITLE),),
    }
    written = format_evidence(record)
    assert "C01: W-2@title:1 required" in written
    assert "L01: 1098-t@title filename" in written   # a name has no page
    assert parse_evidence(written) == record
    assert parse_evidence("") == {}


def test_a_date_pattern_runs_line_by_line_and_skips_lines_over_the_limit():
    """Decision 137 (L3): a staff Date Pattern is compiled and run one line
    at a time, and a line longer than ``DATE_LINE_MAX`` is skipped, so a
    typo that backtracks is bounded by one short line rather than the whole
    OCR text. Where it matched is still found in the whole text."""
    import tracker.keywords as keywords

    rules = item(period="TY2025", date_pattern=r"2025")
    text = "Statement\n" + "2025 " * 200 + "\nPeriod ending 12/31/2025\n"
    verdict = evaluate_rules(text, rules)
    assert verdict.ok
    assert keywords.date_pattern_at(r"2025", text) == text.index("12/31/2025") + 6

    only_long = "x" + "2025 " * 200
    assert keywords.date_pattern_at(r"2025", only_long) is None
    assert not evaluate_rules(only_long, rules).ok
    assert keywords.date_pattern_at(r"(unclosed", "anything") is None
    # A catastrophic pattern over a long run of what it backtracks on
    # finishes at once: the line holding the run is past the limit.
    evil = "a" * 5000 + "!"
    assert keywords.date_pattern_at(r"(a+)+b", evil) is None


def test_only_a_staff_date_pattern_runs_line_by_line():
    """Decision 137's review (F7): the line-by-line bound is for a pattern a
    person typed. The one the tracker derives from the Period is its own and
    runs over the whole text as it always did, so a month and its year split
    by a line break still say the year."""
    import re

    from tracker.manifest import derived_date_pattern

    derived = derived_date_pattern("TY2025")
    split = "Statement period\nDecember\n2025 and more\n"
    assert derived and re.search(derived, split) is not None       # the premise
    firm = item(period="TY2025", date_pattern=derived, date_pattern_derived=True)
    assert evaluate_rules(split, firm).ok

    typed = item(period="TY2025", date_pattern=r"December\s2025", date_pattern_derived=False)
    assert not evaluate_rules(split, typed).ok                      # a person's: line by line
    assert evaluate_rules("December 2025\n", typed).ok


def test_a_pattern_the_record_calls_derived_runs_line_by_line_unless_it_is():
    """Decision 187 (the review's M2): "derived" is what the pattern is -
    the Period's own, recomputed - never what the record's flag claims. A
    forged pattern flagged derived runs line by line like any typed one."""
    split = "Statement period\nDecember\n2025 and more\n"
    forged = item(period="TY2025", date_pattern=r"December\s2025", date_pattern_derived=True)
    assert not evaluate_rules(split, forged).ok                     # line by line, whatever the flag
    assert evaluate_rules("December 2025\n", forged).ok


@pytest.mark.parametrize("lines, carries", [
    (["Charles Schwab", "2025 Consolidated Form 1099", "Form 1099-DIV Dividends and Distributions",
      "Form 1099-INT Interest Income", "Form 1099-B Proceeds From Broker and Barter Exchange Transactions"],
     True),
    (["Form 1099-B Proceeds From Broker and Barter Exchange Transactions 2025", "1d Proceeds 24,318.55"], True),
    (["Vanguard Brokerage Services", "2025 Consolidated Form 1099 - Account 8812-4455",
      "Form 1099-INT   Interest Income", "Form 1099-DIV   Dividends and Distributions"], False),
    (["Harborline Savings Bank", "Consolidated Statement December 2025",
      "Form 1099-INT Interest Income 2025"], False),
    (["Your 2025 Consolidated Form 1099 is now available online.",
      "Log in to view your Form 1099-B and Form 1099-DIV."], False),
    (["2025 Individual Income Tax Organizer - Investment Income",
      "Form 1099-B - Proceeds From Broker and Barter Exchange Transactions",
      "Form 1099-DIV - Dividends and Distributions"], False),
], ids=["d146-consolidated", "d146-loose-1099b", "d146-int-div-only", "d146-bank",
        "d146-notice", "d146-organizer"])
def test_a_1099b_section_is_read_as_a_form_label_not_as_the_word_consolidated(lines, carries):
    """d146. The predicate reads the 1099-B the way a ``1099-b`` keyword is
    read - named in its own right in the title, or the page's own number -
    so a notice that mentions it and a checklist that lists it carry none,
    and "consolidated" decides nothing either way."""
    from tracker.keywords import carries_a_1099b_section

    assert carries_a_1099b_section("\n".join(lines)) is carries


def _the_old_line_of(low: str, start: int, end: int) -> tuple[int, int]:
    """``_line_of`` as it was before decision 178, walking the whole text
    once for every kind of break: the answer the new one must give."""
    breaks = "\r\n\f\v"
    left = max(low.rfind(ch, 0, start) for ch in breaks) + 1
    right = min((i for i in (low.find(ch, end) for ch in breaks) if i >= 0), default=len(low))
    return left, right


def test_the_line_a_mention_is_on_is_found_as_before_without_walking_the_text():
    """Two thousand random texts - with every kind of break, with ``\r``
    line ends only, and with no break at all, short and past the first
    window the look back reaches - each asked about several mentions in a
    row, so the line remembered from one is tried on the next."""
    import random

    from tracker.keywords import _line_of

    rng = random.Random(163)
    alphabets = ("ab w-2 \r\n\f\v", "ab w-2 \r", "ab w-2 ")
    for n in range(2000):
        alphabet = alphabets[n % len(alphabets)]
        size = rng.randint(0, 40) if n % 4 else rng.randint(200, 1500)
        low = "".join(rng.choice(alphabet) for _ in range(size))
        for _ in range(5):
            start = rng.randint(0, len(low))
            end = rng.randint(start, min(len(low), start + 12))
            assert _line_of(low, start, end) == _the_old_line_of(low, start, end), (low, start, end)


def test_the_line_finder_is_quick_on_a_text_with_no_line_feed():
    """The review's S-5: the first quick look back was anchored on the
    nearest line feed, so a text with none before a mention - one line, or
    ``\r``-only line ends - was walked to its start once for every kind of
    break, for every mention. Three texts of about 2 MB, two thousand
    mentions each: every answer is the old one, and all of them together
    take under half a second (the old walk takes about two seconds on the
    office machine, and the look back anchored on the line feed as long on
    the first two texts; the new one about a hundredth of that)."""
    import time

    from tracker.keywords import _line_of

    word = "w-2 wages "
    texts = {
        "one line": word * 200_000,
        "carriage returns only": (word * 7 + "\r") * 28_000,
        "line feeds": (word * 7 + "\n") * 28_000,
    }
    for kind, low in texts.items():
        step = len(low) // 2000
        mentions = [(i * step, i * step + 3) for i in range(2000)]
        began = time.perf_counter()
        found = [_line_of(low, start, end) for start, end in mentions]
        took = time.perf_counter() - began
        assert took < 0.5, (kind, took)
        assert found == [_the_old_line_of(low, start, end) for start, end in mentions], kind
