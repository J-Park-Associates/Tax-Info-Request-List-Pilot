"""The shipped catalogs against the IRS's own forms.

``tests/irs/`` holds fifty forms as the IRS publishes them (irs.gov, public
domain, fetched 2026-09-17): the blank Copy B with its Instructions for
Recipient, a return with its schedules, a K-1 of each flavour, the
notices and transmittals that mention forms they are not. Each is routed
against a shipped catalog the way an engagement routes it - through
create_template() and load_manifest() - and must land where it belongs,
or park. A reconstruction typed from memory omits the instruction page
that names three other forms; these do not.

Two rules are lifted, as tests/test_catalog.py lifts them: the size floor
(a blank form is small) and the Period's year check (a continuous-use
form prints "For calendar year 20__" and no year; a filled one prints the
year). The year check has its own tests. ``None`` means the form must
park: no row in that catalog asks for it, or it is another form's own
document, and misfiling a tax document is worse than not filing it.
"""

from dataclasses import replace
from pathlib import Path

import pytest

from tracker.manifest import create_template, load_manifest
from tracker.router import route_file
from tracker.templates import template_items

IRS = Path(__file__).parent / "irs"

#: (form as the IRS names its file, catalog, engagement year, where it belongs)
EXPECT = [
    ("fw2.pdf", "1040", 2025, "A01"), ("fw3.pdf", "1040", 2025, None), ("fw3.pdf", "1120", 2025, "E01"),
    ("f1099int.pdf", "1040", 2025, "A02"), ("f1099div.pdf", "1040", 2025, "A02"), ("f1099oid.pdf", "1040", 2025, "A02"),
    ("f1099int.pdf", "1041", 2025, "B01"), ("f1099div.pdf", "1041", 2025, "B01"), ("f1099nec.pdf", "1041", 2025, "B01"),
    ("f1099msc.pdf", "1041", 2025, "B01"), ("f1099r.pdf", "1040", 2025, "E02"),
    ("f1099nec.pdf", "1040", 2025, None), ("f1099nec_2024.pdf", "1040", 2025, None), ("f1099msc.pdf", "1040", 2025, None),
    ("f1099g.pdf", "1040", 2025, None), ("f1099k.pdf", "1040", 2025, None), ("f1099s.pdf", "1040", 2025, None),
    ("f1099sa.pdf", "1040", 2025, None), ("f1098.pdf", "1040", 2025, "C01"), ("f1098t.pdf", "1040", 2025, "L01"),
    ("f1095a.pdf", "1040", 2025, "I01"), ("f1095b.pdf", "1040", 2025, None), ("f1095c.pdf", "1040", 2025, None),
    ("f5498.pdf", "1040", 2025, "K01"), ("f5498sa.pdf", "1040", 2025, "K01"),
    ("f1040.pdf", "1040", 2026, "B01"), ("f1040x.pdf", "1040", 2026, "B01"), ("f1040nr.pdf", "1040", 2026, None),
    ("f1040s.pdf", "1040", 2026, None), ("f1040sa.pdf", "1040", 2026, None), ("f1040sb.pdf", "1040", 2026, None),
    ("f1040sd.pdf", "1040", 2026, None), ("f1040s1.pdf", "1040", 2026, None),
    # The 1040-ES booklet's instructions say "estimated tax payment voucher" in prose, which is not
    # a voucher; the 2025 package's vouchers are within the pages read and say what a voucher says.
    ("f1040es.pdf", "1040", 2026, None), ("f1040es_2025.pdf", "1040", 2025, "H01"), ("f1040es.pdf", "1120", 2026, None),
    ("f4868.pdf", "1040", 2026, None), ("f8879.pdf", "1040", 2026, None), ("f1096.pdf", "1040", 2025, None),
    ("f1096.pdf", "1120", 2025, None), ("f1096.pdf", "1041", 2025, None),
    ("f1120.pdf", "1120", 2026, "A01"), ("f1120h.pdf", "1120", 2026, None), ("f1120s.pdf", "1120", 2026, None),
    ("f1120s.pdf", "1120S", 2026, "A01"), ("f1120ssk.pdf", "1120S", 2025, None), ("f1120ssk.pdf", "1040", 2025, "F01"),
    ("f1120ssk_2024.pdf", "1040", 2025, "F01"),          # the year check, lifted here, is what parks last year's
    ("f1065.pdf", "1065", 2026, "A01"), ("f1065sk1.pdf", "1040", 2025, "F01"), ("f1065sk1_2024.pdf", "1040", 2025, "F01"),
    ("f1065sk1.pdf", "1065", 2025, None), ("f1065sk1.pdf", "1041", 2025, None), ("f1065sk1.pdf", "1120", 2025, None),
    ("f1041.pdf", "1041", 2026, "A03"), ("f1041sk1.pdf", "1040", 2025, "F01"), ("f1041sk1.pdf", "1041", 2025, None),
    ("f1041sk1.pdf", "1120S", 2025, None),
    ("f990.pdf", "990", 2026, "A01"), ("f990ez.pdf", "990", 2026, "A01"), ("f990pf.pdf", "990", 2026, None),
    ("f940.pdf", "1120", 2025, "E01"), ("f941.pdf", "1120", 2025, "E01"), ("f940.pdf", "1120S", 2025, "E01"),
    ("f941.pdf", "990", 2025, "G01"), ("f941.pdf", "1040", 2025, None), ("f940.pdf", "1041", 2025, None),
    ("f4562.pdf", "1120", 2025, "C02"), ("f1125e.pdf", "1120", 2025, None),
    # The ninth reading: the IRS "Attention" page ahead of every information
    # return names Form 1099-NEC by way of example, and is not a 1099; a
    # return's own lines ("dividends and distributions in exchange for
    # stock", "the ownership percentage (by vote or value)", "D-Donation")
    # are not a 1099-DIV, a shareholder list or a charitable receipt.
    ("f5498.pdf", "1041", 2025, None), ("f1098t.pdf", "1041", 2025, None), ("f1099g.pdf", "1041", 2025, None),
    ("f1099k.pdf", "1041", 2025, None), ("f1099s.pdf", "1041", 2025, None),
    ("f1120.pdf", "1040", 2026, None), ("f1120.pdf", "1120S", 2026, None), ("f1120.pdf", "1065", 2026, None),
    ("f1065.pdf", "1120", 2026, None), ("f1065.pdf", "1120S", 2026, None), ("f990pf.pdf", "1040", 2026, None),
]


@pytest.fixture(scope="module")
def catalogs(tmp_path_factory):
    folder = tmp_path_factory.mktemp("catalogs")
    built = {}

    def rows(form, year):
        if (form, year) not in built:
            manifest = folder / f"{form}-{year}.xlsx"
            create_template(manifest, template_items(form, year=year))
            built[(form, year)] = [replace(i, min_size_kb=0, date_pattern="") for i in load_manifest(manifest)]
        return built[(form, year)]

    return rows


@pytest.mark.parametrize("pdf, form, year, expected", EXPECT, ids=[f"{p}-{f}" for p, f, _, _ in EXPECT])
def test_the_irs_forms_file_where_they_belong_or_park(catalogs, pdf, form, year, expected):
    routing = route_file(IRS / pdf, catalogs(form, year))
    assert routing.identifier == expected, (pdf, form, routing.reason)
