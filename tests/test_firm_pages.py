"""The firm lists cut into pages (P278, ``pilot/SPEC-ui-menu-speed.md`` section 4).

``tracker/firm_pages.py`` takes the whole reply ``api._cmd_firm`` builds and
the names its walk saw and answers one page: the filter first, then the order
(the window's usual orders and header keys, moved here unchanged), then the
page. The replies below are made up - nobody real - and the words are the
vocabulary's own (``api._firm_words()``), so a status here reads as it does on
screen. What the API does with the module (the saved view, the refusal, the
paged reply of a real walk) is ``tests/test_api.py``'s claim; the window's half
is ``tests/test_shell.py``'s.
"""

from __future__ import annotations

import copy
import datetime as dt
import json
import logging

import pytest

import tracker.api as api
from tests.samples import COLLATION_NAMES, COLLATION_ORDER
from tracker import firm_cache, firm_pages, settings

WORDS = api._firm_words()
ZERO = {"needs_you": 0, "waiting": 0, "received": 0, "set_aside": 0}
TODAY = dt.date(2026, 3, 2)


def a_return(name, household, *, year=2025, form=None, counts=None, oldest=None, due=None, problem="", ready=False,
             stage=0, held=0, drafted=None, paused=False, links=None):
    """One made-up entry of the firm reply's ``returns``."""
    counts = {**ZERO, **(counts or {})}
    return {"path": f"r/{name}", "household": household, "label": f"{household} {year} {name}", "year": year,
            "form": name.split(" - ")[0] if form is None else form, "counts": counts, "files": 0, "oldest": oldest, "due": due,
            "draft": {"ready": ready, "stage": stage, "held": held, "drafted": drafted}, "problem": problem,
            "paused": paused, "links": links or []}


def a_file(return_name, name, *, code="unmatched", received="2026-03-05", suggestion="", key="", year=2025):
    return {"return": f"r/{return_name}", "year": year, "name": name, "handle": f"h-{return_name}-{name}", "code": code,
            "received": received, "suggestion": suggestion, "suggestion_short": suggestion, "open_key": key}


def a_whole(returns, files=(), paths=None):
    """The reply ``api._cmd_firm`` would build for these entries (totals as ``_firm_reply`` counts them)."""
    totals = {"need": 0, "waiting": 0, "complete": 0, "files": len(files), "drafts": sum(1 for one in returns if one["draft"]["ready"])}
    for one in returns:
        if one["counts"]["needs_you"] or one["problem"]:
            totals["need"] += 1
        elif one["counts"]["waiting"]:
            totals["waiting"] += 1
        else:
            totals["complete"] += 1
    return {"returns": returns, "files": list(files), "totals": totals, "paths": paths or {}, "next_sort": "18:00"}


def the_names(returns, forms=None):
    """What the walk saw: each return's name (the last word of its path) and each household with its links and forms."""
    houses: dict[str, dict] = {}
    for one in returns:
        house = houses.setdefault(one["household"], {"name": one["household"], "path": f"h/{one['household']}", "links": one["links"], "forms": []})
        house["forms"].append(one["form"])
    for name, kept in (forms or {}).items():
        houses.setdefault(name, {"name": name, "path": f"h/{name}", "links": [], "forms": []})["forms"] = kept
    return {"returns": {one["path"]: one["path"].split("/")[-1] for one in returns}, "households": list(houses.values())}


def asking(list_, at=0, order=None, **filter):
    return firm_pages.ask_of({"page": {"list": list_, "at": at, "order": order, "filter": filter}}, WORDS["client_types"])


def paged(whole, list_, at=0, order=None, names=None, **filter):
    """The page the engine answers, whole reply and all."""
    return firm_pages.page(whole, names if names is not None else the_names(whole["returns"]), WORDS, asking(list_, at, order, **filter))


def the_rows(reply):
    return [(row.get("household") if row.get("kind") == "paused" else row["path"].split("/")[-1]) for row in reply["page"]["rows"]]


# ── pages ───────────────────────────────────────────────────────────────────

def test_a_page_holds_fifty_rows_in_order_and_says_where_it_is():
    assert firm_pages.PAGE_SIZE == 50
    returns = [a_return(f"1040 - R{i:03d}", "Alpha", counts={"waiting": 1}, due="2026-04-15") for i in range(120)]
    whole = a_whole(returns)
    first = paged(whole, "overview")["page"]
    assert (first["list"], first["at"], first["pages"], first["from"], first["to"], first["total"]) == ("overview", 0, 3, 1, 50, 120)
    assert [row["path"].split("/")[-1] for row in first["rows"]] == [f"1040 - R{i:03d}" for i in range(50)]
    third = paged(whole, "overview", at=2)["page"]
    assert (third["at"], third["from"], third["to"], third["total"], len(third["rows"])) == (2, 101, 120, 120, 20)
    assert paged(whole, "overview", at=1)["page"]["rows"][0]["path"] == "r/1040 - R050"
    assert whole == a_whole(copy.deepcopy(returns)), "the whole reply is not changed"


def test_a_page_past_the_end_is_the_last_page():
    whole = a_whole([a_return(f"1040 - R{i:03d}", "Alpha", counts={"waiting": 1}) for i in range(120)])
    last = paged(whole, "overview", at=40)["page"]
    assert (last["at"], last["from"], last["to"], len(last["rows"])) == (2, 101, 120, 20)
    empty = paged(a_whole([]), "overview", at=3)["page"]
    assert (empty["at"], empty["pages"], empty["from"], empty["to"], empty["total"], empty["rows"]) == (0, 0, 0, 0, 0, [])


def test_needs_review_pages_by_whole_groups_up_to_fifty_files_and_a_larger_group_is_a_page_alone():
    returns = [a_return(f"1040 - {name}", "Alpha", counts={"needs_you": 1}) for name in ("Alpha", "Bravo", "Charlie")]
    files = [a_file(f"1040 - {name}", f"{name} {i:02d}.pdf", received=day)
             for name, n, day in (("Alpha", 30, "2026-03-01"), ("Bravo", 30, "2026-03-02"), ("Charlie", 60, "2026-03-03")) for i in range(n)]
    whole = a_whole(returns, files)
    pages = [paged(whole, "needs_review", at=at)["page"] for at in range(4)]
    assert [(p["at"], p["from"], p["to"], p["total"], p["pages"]) for p in pages] == [
        (0, 1, 30, 120, 3), (1, 31, 60, 120, 3), (2, 61, 120, 120, 3), (2, 61, 120, 120, 3)]
    assert [[group["path"].split("/")[-1] for group in p["rows"]] for p in pages[:3]] == [["1040 - Alpha"], ["1040 - Bravo"], ["1040 - Charlie"]]
    assert [len(p["rows"][0]["files"]) for p in pages[:3]] == [30, 30, 60], "a group is never split, and a larger one stands alone"
    small = a_whole(returns[:2], [a_file("1040 - Alpha", "a.pdf", received="2026-03-01"), a_file("1040 - Bravo", "b.pdf", received="2026-03-02")])
    both = paged(small, "needs_review")["page"]
    assert (both["pages"], [len(group["files"]) for group in both["rows"]]) == (1, [1, 1]), "groups share a page while they fit"


def test_the_tab_the_reason_and_the_client_type_narrow_the_whole_list_before_order_and_pages():
    returns = ([a_return(f"1040 - N{i:03d}", "Alpha", counts={"needs_you": 1}, oldest="2026-03-01") for i in range(60)]
               + [a_return(f"1040 - W{i:03d}", "Bravo", counts={"waiting": 1}, due="2026-04-15") for i in range(30)])
    whole = a_whole(returns)
    every = paged(whole, "overview")["page"]
    need = paged(whole, "overview", tab="need")["page"]
    waiting = paged(whole, "overview", tab="waiting")["page"]
    assert every["counts"] == need["counts"] == waiting["counts"] == {"all": 90, "need": 60, "waiting": 30}, "the tabs' counts are the whole list's"
    assert (every["total"], every["pages"]) == (90, 2) and (need["total"], need["pages"]) == (60, 2) and (waiting["total"], waiting["pages"]) == (30, 1)
    assert {row["bucket"] for row in need["rows"]} == {"need"} and {row["bucket"] for row in waiting["rows"]} == {"wait"}
    assert need["filter"] == {"tab": "need"}
    # A header's order is applied to the narrowed list, over all its pages.
    backwards = paged(whole, "overview", order={"cell": "taxpayer", "dir": -1}, tab="need", at=1)["page"]
    assert [row["path"].split("/")[-1] for row in backwards["rows"]] == [f"1040 - N{i:03d}" for i in range(9, -1, -1)]
    # A reason narrows Needs Review; its cards count every file.
    files = [a_file("1040 - N000", f"a{i}.pdf", code="unmatched") for i in range(3)] + [a_file("1040 - N001", "z.zip", code="opened-not-across")]
    reasons = paged(a_whole(returns[:2], files), "needs_review", reason="opened-not-across")["page"]
    assert reasons["counts"] == {"all": 4, "reasons": [["unmatched", 3], ["opened-not-across", 1]]}
    assert (reasons["total"], [group["path"] for group in reasons["rows"]]) == (1, ["r/1040 - N001"]) and reasons["filter"] == {"reason": "opened-not-across"}
    # A Client Type keeps the households with a return of one of its forms, shown or not; Work Waiting then counts within it.
    people = [a_return("1040 - Ann", "Ann Household", counts={"needs_you": 1}), a_return("1065 - Bo LLC", "Bo Household", counts={"waiting": 1})]
    walk = the_names(people, forms={"Cy Household": ["1040"], "Di Household": [""]})
    kept = firm_pages.page(a_whole(people), walk, WORDS, asking("clients", all=True, type="individuals"))["page"]
    assert [row["name"] for row in kept["rows"]] == ["Ann Household", "Cy Household"] and kept["counts"] == {"work": 1}
    assert kept["filter"] == {"all": True, "type": "individuals"}
    nobody = firm_pages.page(a_whole(people), walk, WORDS, asking("clients", type="nonprofits"))["page"]
    assert (nobody["total"], nobody["counts"], nobody["rows"]) == (0, {"work": 0}, [])


def test_a_reason_no_longer_present_falls_back_to_all():
    returns = [a_return("1040 - Alpha", "Alpha", counts={"needs_you": 1})]
    whole = a_whole(returns, [a_file("1040 - Alpha", "a.pdf"), a_file("1040 - Alpha", "b.pdf", code="opened-not-across")])
    page = paged(whole, "needs_review", reason="password")["page"]
    assert page["filter"] == {"reason": ""} and page["total"] == 2 and page["counts"]["all"] == 2


def test_each_header_orders_by_its_key_blanks_last_both_ways_and_ties_keep_the_usual_order():
    returns = [
        a_return("1040 - Zeta Zed", "Zed", year=2025, counts={"needs_you": 1}, oldest="2026-03-04"),
        a_return("1065 - Beta Bee", "Bee", year=2024, counts={"needs_you": 1}, oldest="2026-03-02"),
        a_return("1040 - Cy Cee", "Cee", year=2025, counts={"waiting": 1}, due="2026-04-15"),
        a_return("1040 - Dee Dee", "Dee", year=2025, counts={"waiting": 1}, due="2026-04-15"),     # ties Cee on year, form and date
        a_return("Loose Name", "Eve", year=2025, form="", counts={"waiting": 1}),                  # no recorded form, no date
    ]
    whole = a_whole(returns)
    usual = the_rows(paged(whole, "overview"))
    assert usual == ["1065 - Beta Bee", "1040 - Zeta Zed", "1040 - Cy Cee", "1040 - Dee Dee", "Loose Name"]

    def order(cell, direction):
        return the_rows(paged(whole, "overview", order={"cell": cell, "dir": direction}))

    assert order("year", 1) == ["1065 - Beta Bee", "1040 - Zeta Zed", "1040 - Cy Cee", "1040 - Dee Dee", "Loose Name"]
    assert order("year", -1) == ["1040 - Zeta Zed", "1040 - Cy Cee", "1040 - Dee Dee", "Loose Name", "1065 - Beta Bee"], "equal keys keep the usual order in either direction"
    assert order("taxpayer", 1) == ["1065 - Beta Bee", "1040 - Cy Cee", "1040 - Dee Dee", "Loose Name", "1040 - Zeta Zed"]
    assert order("taxpayer", -1) == ["1040 - Zeta Zed", "Loose Name", "1040 - Dee Dee", "1040 - Cy Cee", "1065 - Beta Bee"]
    assert order("form", 1)[-1] == "Loose Name" and order("form", -1)[-1] == "Loose Name", "a blank form goes last both ways"
    assert order("end", 1) == ["1065 - Beta Bee", "1040 - Zeta Zed", "1040 - Cy Cee", "1040 - Dee Dee", "Loose Name"]
    assert order("end", -1) == ["1040 - Cy Cee", "1040 - Dee Dee", "1040 - Zeta Zed", "1065 - Beta Bee", "Loose Name"]
    assert paged(whole, "overview", order={"cell": "end", "dir": -1})["page"]["order"] == {"cell": "end", "dir": -1}


def test_status_orders_by_urgency_then_the_larger_count_then_its_words():
    returns = [
        a_return("1040 - A Small", "A", counts={"needs_you": 3}, oldest="2026-03-01"),
        a_return("1040 - B Large", "B", counts={"needs_you": 12}, oldest="2026-03-02"),
        a_return("1040 - C Wait", "C", counts={"waiting": 5}, due="2026-04-15"),
        a_return("1040 - D Wait", "D", counts={"waiting": 2}, due="2026-04-01"),
        a_return("1040 - E Broken", "E", problem="Could Not Be Read"),
    ]
    whole = a_whole(returns)
    up = the_rows(paged(whole, "overview", order={"cell": "status", "dir": 1}))
    assert up == ["1040 - E Broken", "1040 - B Large", "1040 - A Small", "1040 - C Wait", "1040 - D Wait"]
    assert the_rows(paged(whole, "overview", order={"cell": "status", "dir": -1})) == list(reversed(up))
    # Reminders: Held first (a person must act), then the later stage first.
    drafts = [a_return("1040 - A Early", "A", ready=True, stage=1, drafted="2026-03-01"), a_return("1040 - B Late", "B", ready=True, stage=3, drafted="2026-03-02"),
              a_return("1040 - C Held", "C", ready=True, stage=2, held=1, drafted="2026-03-03")]
    reminders = paged(a_whole(drafts), "reminders", order={"cell": "status", "dir": 1})
    assert the_rows(reminders) == ["1040 - C Held", "1040 - B Late", "1040 - A Early"]
    # Clients: a household whose return cannot be read leads, then what needs a person, then what waits.
    clients = paged(whole, "clients", order={"cell": "status", "dir": 1}, all=True)
    assert [row["name"] for row in clients["page"]["rows"]] == ["E", "B", "A", "C", "D"]


def test_the_usual_orders_are_the_pages_own():
    returns = [
        a_return("1040 - Late Need", "Lena", counts={"needs_you": 1}, oldest="2026-03-09"),
        a_return("1040 - Early Need", "Earl", counts={"needs_you": 1}, oldest="2026-03-01"),
        a_return("1040 - Also Early", "Alma", counts={"needs_you": 1}, oldest="2026-03-01"),
        a_return("1040 - Broken", "Brok", problem="Could Not Be Read"),
        a_return("1040 - Both", "Both", counts={"needs_you": 2, "waiting": 1}, oldest="2026-03-20", due="2026-03-25"),   # a person AND the client: the first bucket only
        a_return("1040 - Soon", "Soon", counts={"waiting": 1}, due="2026-04-01"),
        a_return("1040 - Zebra Wait", "Zeb", counts={"waiting": 1}, due="2026-04-15"),
        a_return("1040 - Apple Wait", "App", counts={"waiting": 1}, due="2026-04-15"),
        a_return("1040 - No Date", "Nod", counts={"waiting": 1}),
        a_return("1040 - Paused One", "Pau", paused=True, counts={"waiting": 1}, due="2026-05-01"),
        a_return("1040 - Paused Two", "Pau", paused=True, counts={"waiting": 1}, due="2026-05-02"),
        a_return("1040 - Another", "Ana", paused=True, counts={"waiting": 1}, due="2026-05-03"),
        a_return("1040 - Done", "Done", counts={"received": 2}),
    ]
    whole = a_whole(returns)
    rows = paged(whole, "overview")["page"]["rows"]
    assert [(row["kind"], row["household"] if row["kind"] == "paused" else row["path"].split("/")[-1]) for row in rows] == [
        ("paused", "Ana"), ("paused", "Pau"),                      # paused households, by name, first
        ("return", "1040 - Broken"),                               # then what needs a person: a return with a problem first,
        ("return", "1040 - Also Early"), ("return", "1040 - Early Need"),   # then the oldest waiting file, then the name,
        ("return", "1040 - Late Need"), ("return", "1040 - Both"),
        ("return", "1040 - Soon"),                                 # then what waits: the due date, then the name,
        ("return", "1040 - Apple Wait"), ("return", "1040 - Zebra Wait"),
        ("return", "1040 - Paused One"), ("return", "1040 - Paused Two"), ("return", "1040 - Another"),
        ("return", "1040 - No Date"),                              # a return with no date after those with one
    ]
    assert [row["bucket"] for row in rows if row["kind"] == "return"] == ["need"] * 5 + ["wait"] * 7
    assert [row.get("path") for row in rows].count("r/1040 - Both") == 1, "a return with both counts is listed once, in the first bucket only"
    counts = paged(whole, "overview")["page"]["counts"]
    assert counts == {"all": 14, "need": 7, "waiting": 7}, "Both is under Need You and not under Waiting"
    assert "r/1040 - Both" not in [row.get("path") for row in paged(whole, "overview", tab="waiting")["page"]["rows"]]
    assert "r/1040 - Both" in [row.get("path") for row in paged(whole, "overview", tab="need")["page"]["rows"]]
    assert [row["household_path"] for row in rows[:2]] == ["h/Ana", "h/Pau"]
    # Reminders by return name; Clients by household name, a household with no return among them.
    drafts = [a_return("1040 - Zed", "Z", ready=True, stage=1, drafted="2026-03-01"), a_return("1040 - Amy", "A", ready=True, stage=1, drafted="2026-03-02"),
              a_return("1040 - Mid", "M", ready=False)]
    assert the_rows(paged(a_whole(drafts), "reminders")) == ["1040 - Amy", "1040 - Zed"]
    walk = the_names(drafts, forms={"Nobody Yet": []})
    people = firm_pages.page(a_whole(drafts), walk, WORDS, asking("clients", all=True))["page"]
    assert [row["name"] for row in people["rows"]] == ["A", "M", "Nobody Yet", "Z"]
    assert [(row["name"], row["returns"], row["work"]) for row in people["rows"]] == [("A", 1, False), ("M", 1, False), ("Nobody Yet", 0, False), ("Z", 1, False)]
    work = firm_pages.page(a_whole(returns), the_names(returns), WORDS, asking("clients"))["page"]
    assert [row["name"] for row in work["rows"]] == sorted(row["name"] for row in work["rows"]) and all(row["work"] for row in work["rows"])
    assert work["counts"]["work"] == len(work["rows"]) == 11, "Done has nothing waiting"


def test_needs_review_orders_files_in_each_group_and_groups_follow_their_first_file():
    returns = [a_return("1040 - Alpha", "Alpha", counts={"needs_you": 1}), a_return("1065 - Bravo", "Bravo", counts={"needs_you": 1})]
    files = [a_file("1040 - Alpha", "b.pdf", received="2026-03-05", suggestion="W-2"),
             a_file("1040 - Alpha", "a.pdf", received="2026-03-07", code="opened-not-across"),
             a_file("1065 - Bravo", "z.pdf", received="2026-03-01", suggestion="K-1")]
    whole = a_whole(returns, files)

    def groups(order=None):
        return [(group["path"].split("-")[-1].strip(), [one["name"] for one in group["files"]]) for group in paged(whole, "needs_review", order=order)["page"]["rows"]]

    assert groups() == [("Bravo", ["z.pdf"]), ("Alpha", ["b.pdf", "a.pdf"])], "groups by their oldest file, files by received date then name"
    assert groups({"cell": "end", "dir": -1}) == [("Alpha", ["a.pdf", "b.pdf"]), ("Bravo", ["z.pdf"])]
    assert groups({"cell": "name", "dir": 1}) == [("Alpha", ["a.pdf", "b.pdf"]), ("Bravo", ["z.pdf"])]
    assert groups({"cell": "status", "dir": 1}) == [("Bravo", ["z.pdf"]), ("Alpha", ["b.pdf", "a.pdf"])], "Could Not Sort before Email or Zip; a tie keeps the usual order"
    assert groups({"cell": "status", "dir": -1}) == [("Alpha", ["a.pdf", "b.pdf"]), ("Bravo", ["z.pdf"])]
    assert groups({"cell": "detail", "dir": 1}) == [("Bravo", ["z.pdf"]), ("Alpha", ["b.pdf", "a.pdf"])], "K-1 before W-2, and a blank suggestion goes last"
    heading = paged(whole, "needs_review")["page"]["rows"][1]
    assert (heading["household"], heading["household_path"], heading["year"], heading["form"], heading["links"]) == ("Alpha", "h/Alpha", 2025, "1040", [])


def test_names_order_as_the_windows_collator_orders_the_shared_list():
    assert sorted(COLLATION_NAMES, key=firm_pages.name_order) == COLLATION_ORDER
    assert sorted(reversed(COLLATION_NAMES), key=firm_pages.name_order) == COLLATION_ORDER
    # Runs of digits are numbers, white space comes before punctuation before digits before letters, then accents, then case.
    keyed = firm_pages.name_order
    assert keyed("Client 2") < keyed("Client 10") and keyed("a b") < keyed("a-b") < keyed("a1") < keyed("ab")
    assert keyed("eclair") < keyed("Eclair") < keyed("Éclair") < keyed("eclairs"), "case and accents only break ties"
    assert keyed("Éclair") < keyed("Eclairs") and keyed("Zoe") < keyed("Zoë")


def test_the_taxpayer_and_form_keys_follow_the_recorded_form_never_a_guess():
    taxpayer = firm_pages._taxpayer
    assert taxpayer("1040 - John & Maria Park", "1040") == "John & Maria Park"
    assert taxpayer("1120-S - Rivera Design LLC", "1120S") == "Rivera Design LLC", "a hyphen inside the form number and letter case are not differences"
    assert taxpayer("1040 - John Park", "1065") == "1040 - John Park", "the name begins with another form: shown whole"
    assert taxpayer("John Park 1040", "1040") == "John Park 1040" and taxpayer("1040 - John Park", "") == "1040 - John Park"
    assert taxpayer("1040 -", "1040") == "1040 -", "a name with nothing after the form is never cut to nothing"
    # The form key is its place in the Client Types' forms, then the form by its name; a blank form is blank.
    key = firm_pages._form_key
    forms = [one for forms in WORDS["client_types"].values() for one in forms]
    assert key("1040", WORDS) == [forms.index("1040"), "1040"] and key("", WORDS) == ""
    assert key("5500", WORDS) == [len(forms), "5500"] and key("5500", WORDS) > key("990", WORDS)
    returns = [a_return("5500 - Plan", "P", form="5500", counts={"waiting": 1}), a_return("1065 - Firm", "F", counts={"waiting": 1}),
               a_return("1040 - Pers", "I", counts={"waiting": 1}), a_return("990 - Charity", "C", counts={"waiting": 1})]
    assert the_rows(paged(a_whole(returns), "overview", order={"cell": "form", "dir": 1})) == ["1040 - Pers", "1065 - Firm", "990 - Charity", "5500 - Plan"]
    # The taxpayer a return shows is the name the walk saw, less its recorded form - not the row's label.
    named = the_names(returns)
    named["returns"]["r/5500 - Plan"] = "5500 - Zed Plan"
    ordered = firm_pages.page(a_whole(returns), named, WORDS, asking("overview", order={"cell": "taxpayer", "dir": 1}))
    assert [row["path"] for row in ordered["page"]["rows"]][-1] == "r/5500 - Plan"


def test_many_years_counts_the_whole_list_before_its_tab_and_pages():
    returns = [a_return(f"1040 - N{i:02d}", "Alpha", year=2025, counts={"needs_you": 1}, oldest="2026-03-01") for i in range(60)]
    returns.append(a_return("1040 - Old", "Bravo", year=2024, counts={"waiting": 1}, due="2026-04-01"))
    whole = a_whole(returns)
    assert paged(whole, "overview")["page"]["many_years"] is True
    assert paged(whole, "overview", tab="need")["page"]["many_years"] is True, "a tab does not change it"
    assert paged(whole, "overview", tab="need", at=1)["page"]["many_years"] is True, "nor does a page"
    assert paged(a_whole(returns[:60]), "overview")["page"]["many_years"] is False
    # A paused household's blank year is not a year.
    paused = [a_return("1040 - Pa", "Pau", paused=True, counts={"waiting": 1}, due="2026-04-01")]
    assert paged(a_whole(paused), "overview")["page"]["many_years"] is False
    drafts = [a_return("1040 - A", "A", year=2025, ready=True, stage=1), a_return("1040 - B", "B", year=2024, ready=True, stage=1)]
    assert paged(a_whole(drafts), "reminders")["page"]["many_years"] is True
    for other, reply in (("needs_review", paged(a_whole(returns[:1], [a_file("1040 - N00", "a.pdf")]), "needs_review")),
                         ("clients", paged(whole, "clients", all=True))):
        assert reply["page"]["many_years"] is False, other


def test_an_order_by_tax_year_is_not_applied_while_the_list_holds_one_year():
    returns = [a_return("1040 - Zeta", "Z", counts={"waiting": 1}, due="2026-04-01"), a_return("1040 - Alpha", "A", counts={"waiting": 1}, due="2026-04-02")]
    one_year = paged(a_whole(returns), "overview", order={"cell": "year", "dir": -1})["page"]
    assert [row["path"] for row in one_year["rows"]] == ["r/1040 - Zeta", "r/1040 - Alpha"], "the usual order"
    assert one_year["order"] == {"cell": "year", "dir": -1}, "kept and echoed, so it applies again when the column comes back"
    returns[1] = a_return("1040 - Alpha", "A", year=2024, counts={"waiting": 1}, due="2026-04-02")
    two_years = paged(a_whole(returns), "overview", order={"cell": "year", "dir": -1})["page"]
    assert [row["path"] for row in two_years["rows"]] == ["r/1040 - Zeta", "r/1040 - Alpha"]
    assert [row["path"] for row in paged(a_whole(returns), "overview", order={"cell": "year", "dir": 1})["page"]["rows"]] == ["r/1040 - Alpha", "r/1040 - Zeta"]


def test_an_unknown_list_cell_or_filter_is_refused_by_name():
    types = WORDS["client_types"]

    def ask(**page):
        return {"page": {"list": "overview", **page}}

    refused = [
        ask(list="payroll"), {"page": {}}, {"page": "overview"}, {"view": "x"}, {"page": {"list": "overview"}, "extra": 1},
        ask(order={"cell": "bogus", "dir": 1}), ask(order={"cell": "year", "dir": 2}), ask(order={"cell": "year"}), ask(order="year"),
        ask(list="clients", order={"cell": "end", "dir": 1}),
        ask(filter={"tab": "everything"}), ask(filter={"reason": ""}), ask(filter={"tab": "all", "extra": True}), ask(filter="all"),
        ask(list="needs_review", filter={"reason": 5}), ask(list="reminders", filter={"tab": "all"}),
        ask(list="clients", filter={"all": "yes"}), ask(list="clients", filter={"type": "dentists"}), ask(list="clients", filter={"type": 3}),
        ask(at=-1), ask(at="1"), ask(at=True), ask(at=1.5), ask(at=None),
        {"page": {"list": "overview"}, "view": 7},
    ]
    for spec in refused:
        with pytest.raises(firm_pages.PageAskError):
            firm_pages.ask_of(spec, types)
    assert firm_pages.ask_of({}, types) is None, "no page: today's whole reply"
    kept = firm_pages.ask_of({"page": {"list": "clients", "at": 2, "order": {"cell": "name", "dir": -1}, "filter": {"all": True, "type": "trusts"}}, "view": "abc"}, types)
    assert (kept.list, kept.at, kept.order, kept.filter, kept.view) == ("clients", 2, ("name", -1), {"all": True, "type": "trusts"}, "abc")
    plain = firm_pages.ask_of({"page": {"list": "overview"}}, types)
    assert (plain.at, plain.order, plain.filter, plain.view) == (0, None, {"tab": "all"}, "")


# ── the paged reply ─────────────────────────────────────────────────────────

def test_the_reply_carries_one_page_the_totals_every_returns_counts_and_only_its_rows_paths():
    returns = [a_return("1040 - Alpha", "Alpha", counts={"needs_you": 2}, oldest="2026-03-01", links=[{"name": "Bravo", "path": "h/Bravo", "kind": "related"}]),
               a_return("1065 - Bravo", "Bravo", counts={"needs_you": 1}, oldest="2026-03-02")]
    files = [a_file("1040 - Alpha", "a.pdf", received="2026-03-01", key="shown_copy 1"), a_file("1065 - Bravo", "b.pdf", received="2026-03-02", key="shown_copy 2")]
    whole = a_whole(returns, files, paths={"shown_copy 1": "/made/up/a.pdf", "shown_copy 2": "/made/up/b.pdf"})
    reply = paged(whole, "needs_review")
    assert set(reply) == {"view", "totals", "next_sort", "return_counts", "page", "paths", "files_found"}
    assert reply["view"] is None and reply["totals"] == whole["totals"] and reply["next_sort"] == "18:00"
    assert [set(one) for one in reply["return_counts"]] == [{"path", "household", "year", "form", "counts", "files", "problem", "paused"}] * 2
    assert set(reply["page"]) == {"list", "at", "pages", "from", "to", "total", "order", "filter", "counts", "many_years", "rows"}
    assert [(one["name"], one["return"], one["year"], one["handle"]) for one in reply["files_found"]] == [(f["name"], f["return"], f["year"], f["handle"]) for f in files]
    assert reply["paths"] == whole["paths"]
    # A page of the first group alone names only its own key; the search still finds every file.
    long_first = a_whole(returns, [a_file("1040 - Alpha", f"a{i:02d}.pdf", received="2026-03-01", key="shown_copy 1") for i in range(50)]
                         + [a_file("1065 - Bravo", "b.pdf", received="2026-03-02", key="shown_copy 2")], paths=whole["paths"])
    first = paged(long_first, "needs_review")
    assert first["paths"] == {"shown_copy 1": "/made/up/a.pdf"} and len(first["files_found"]) == 51 and first["page"]["pages"] == 2
    for other in ("overview", "reminders", "clients"):
        assert "files_found" not in paged(whole, other) and paged(whole, other)["paths"] == {}, other
    assert "returns" not in reply and "files" not in reply


# ── the view ────────────────────────────────────────────────────────────────

def a_head(root="/clients", day=TODAY):
    return firm_cache.head(root, day)


def test_the_view_is_one_file_in_the_data_folder_written_whole_and_set_aside_when_damaged(caplog):
    assert firm_pages.PAGES_FILENAME == "firm-pages.json"
    assert firm_pages.pages_path() == settings.data_home() / firm_pages.PAGES_FILENAME
    assert firm_pages.pages_path().parent == firm_cache.cache_path().parent
    whole = a_whole([a_return("1040 - Alpha", "Alpha", counts={"waiting": 1}, due="2026-04-01")])
    walk = the_names(whole["returns"])
    head = a_head()
    token = firm_pages.save_view(whole, walk, head)
    assert isinstance(token, str) and len(token) == 16 and int(token, 16) >= 0
    kept = json.loads(firm_pages.pages_path().read_text(encoding="utf-8"))
    assert kept == {"format": firm_pages.FORMAT, "view": token, "head": head, "names": walk, "reply": whole}
    assert sorted(path.name for path in firm_pages.pages_path().parent.iterdir() if path.name.startswith("firm-pages")) == ["firm-pages.json"], "no temporary file is left"
    viewed = firm_pages.load_view(token, head)
    assert viewed is not None and viewed.whole == whole and viewed.names == walk
    # A newer view replaces the file; the old token is not found.
    newer = firm_pages.save_view(whole, walk, head)
    assert newer != token and firm_pages.load_view(token, head) is None and firm_pages.load_view(newer, head) is not None
    # A damaged file is not used, and the error log says its class, never its words.
    with caplog.at_level(logging.WARNING):
        for ruin in ("{ not json", json.dumps({"format": firm_pages.FORMAT, "view": newer, "head": head, "names": walk, "reply": {"returns": 3}}),
                     json.dumps(["a", "list"])):
            firm_pages.pages_path().write_text(ruin, encoding="utf-8")
            assert firm_pages.load_view(newer, head) is None
        firm_pages.pages_path().write_bytes(b"\xff\xfe\x00 not text")
        assert firm_pages.load_view(newer, head) is None
    assert caplog.records and not any("Alpha" in record.getMessage() for record in caplog.records)
    firm_pages.pages_path().unlink()
    assert firm_pages.load_view(newer, head) is None, "a view that is gone is the ordinary way a view ends"
    assert firm_pages.load_view("", head) is None


def test_a_view_that_cannot_be_written_has_no_token(monkeypatch, caplog):
    whole = a_whole([])

    def refuses(path, text):
        raise PermissionError("made-up refusal that names Alpha Household")

    monkeypatch.setattr(firm_pages, "write_text_atomically", refuses)
    with caplog.at_level(logging.WARNING):
        assert firm_pages.save_view(whole, the_names([]), a_head()) is None
    assert any("PermissionError" in record.getMessage() for record in caplog.records)
    assert not any("Alpha" in record.getMessage() for record in caplog.records), "the class, never the words"


def test_a_view_of_another_token_root_program_day_or_data_folder_is_never_used(monkeypatch, tmp_path):
    whole = a_whole([a_return("1040 - Alpha", "Alpha", counts={"waiting": 1}, due="2026-04-01")])
    walk = the_names(whole["returns"])
    head = a_head()
    token = firm_pages.save_view(whole, walk, head)
    assert firm_pages.load_view(token, head) is not None
    assert firm_pages.load_view("0" * 16, head) is None, "another token"
    assert firm_pages.load_view(token, a_head(root="/another/clients")) is None, "another clients folder"
    assert firm_pages.load_view(token, a_head(day=TODAY + dt.timedelta(days=1))) is None, "another day"
    assert firm_pages.load_view(token, {**head, "program": "another"}) is None, "another program"
    assert firm_pages.load_view(token, {**head, "data_home": "/another/data"}) is None, "another data folder"
    assert firm_pages.load_view(token, {**head, "settings": [1, 2]}) is None, "other settings"
    with monkeypatch.context() as patch:
        patch.setattr(firm_cache, "program_stamp", lambda: "a program changed on disk")
        assert firm_pages.load_view(token, a_head()) is None, "the program's own stamp is in the head"
    # Another format is another file's shape.
    kept = json.loads(firm_pages.pages_path().read_text(encoding="utf-8"))
    firm_pages.pages_path().write_text(json.dumps({**kept, "format": firm_pages.FORMAT + 1}), encoding="utf-8")
    assert firm_pages.load_view(token, head) is None
    # A data folder with no such file has no view.
    monkeypatch.setenv(settings.ENV_DATA_HOME, str(tmp_path / "elsewhere"))
    assert firm_pages.load_view(token, head) is None
