"""Hands-on demo of the manifest layer. Run from the repo root:

    python demo/demo_manifest.py          # full walkthrough (recreates demo manifest)
    python demo/demo_manifest.py write    # just do a scanner-style status write
                                          # (use this while the file is OPEN in Excel
                                          #  to watch the lock-retry + sidecar behavior)
"""

import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import logging

from tracker.manifest import (
    ManifestError,
    RequestItem,
    Status,
    StatusUpdate,
    create_template,
    load_manifest,
    pending_path,
    write_statuses,
)

logging.basicConfig(level=logging.INFO, format="  [log] %(message)s")

DEMO_DIR = Path(__file__).resolve().parent
MANIFEST = DEMO_DIR / "_manifest.xlsx"

SAMPLE_ITEMS = [
    RequestItem(
        identifier="A01",
        document="W-2 Wage Statements - All Employers",
        period="TY2025",
        expected_count=2,
        allowed_extensions=("pdf",),
        required_keywords=("W-2",),
        date_pattern=r"(?i)\b2025\b",
    ),
    RequestItem(
        identifier="A02",
        document="1099-INT / 1099-DIV - Interest & Dividend Income",
        period="TY2025",
        expected_count=3,
        allowed_extensions=("pdf", "csv"),
        any_keywords=("1099", "interest income", "dividend"),
    ),
    RequestItem(
        identifier="B01",
        document="Prior-Year Federal & State Tax Returns",
        period="TY2024",
        allowed_extensions=("pdf",),
        min_size_kb=10,
    ),
    RequestItem(
        identifier="C01",
        document="Mortgage Interest Statement - Form 1098",
        period="TY2025",
        allowed_extensions=("pdf",),
    ),
]


def show(items):
    print(f"  {'ID':<5} {'Document':<46} {'Status':<18} {'Recv Date':<11} {'Files':<6} Notes")
    print(f"  {'-'*5} {'-'*46} {'-'*18} {'-'*11} {'-'*6} {'-'*20}")
    for i in items:
        print(
            f"  {i.identifier:<5} {i.document[:46]:<46} {i.status or '-':<18} "
            f"{i.received_date or '-'!s:<11} {i.file_count if i.file_count is not None else '-':<6} "
            f"{i.validation_notes[:40]}"
        )


def scanner_style_write():
    """Pretend a scan just finished and write its results back."""
    updates = {
        "A01": StatusUpdate(
            status=Status.RECEIVED, file_count=2, received_date=dt.date.today(),
        ),
        "A02": StatusUpdate(
            status=Status.PARTIAL, file_count=2,
            validation_notes="2 of 3 1099 forms received",
        ),
        "B01": StatusUpdate(
            status=Status.FAILED, file_count=1,
            validation_notes="prior_return.pdf is 2 KB (< 10 KB minimum); possible placeholder",
        ),
        "C01": StatusUpdate(status=Status.MISSING, file_count=0),
    }
    print("\n>> Writing scanner results (watch for retry logs if Excel has the file open)...")
    written = write_statuses(MANIFEST, updates, retries=3, retry_delay=1.0)
    if written:
        print(">> Written directly to the workbook.")
        print("\n>> Reloading manifest to prove the roundtrip:")
        show(load_manifest(MANIFEST))
    else:
        print(f">> Workbook was LOCKED. Updates deferred to sidecar: {pending_path(MANIFEST).name}")
        print(">> Close Excel and run 'python demo/demo_manifest.py write' again --")
        print(">>   the sidecar will be merged in automatically and deleted.")


def full_demo():
    print("=" * 78)
    print("STEP 1 - create_template(): build a fresh demo manifest")
    print("=" * 78)
    if MANIFEST.exists():
        MANIFEST.unlink()
        pending_path(MANIFEST).unlink(missing_ok=True)
    create_template(MANIFEST, SAMPLE_ITEMS)
    print(f">> Created {MANIFEST}")
    print(">> Open it in Excel now if you like -- bold headers, frozen top row, sized columns.")

    print()
    print("=" * 78)
    print("STEP 2 - load_manifest(): parse + validate every row")
    print("=" * 78)
    items = load_manifest(MANIFEST)
    show(items)
    a02 = items[1]
    print(f"\n  Parsed detail for A02: expected_count={a02.expected_count}, "
          f"extensions={a02.allowed_extensions}, any_keywords={a02.any_keywords}")

    print()
    print("=" * 78)
    print("STEP 3 - write_statuses(): simulate a scanner pass writing results back")
    print("=" * 78)
    scanner_style_write()

    print()
    print("=" * 78)
    print("STEP 4 - validation is LOUD: a broken manifest refuses to load")
    print("=" * 78)
    broken = DEMO_DIR / "_broken.xlsx"
    broken.unlink(missing_ok=True)
    create_template(broken, [
        RequestItem(identifier="X01", document="Bad regex demo", date_pattern="([unclosed"),
    ])
    try:
        load_manifest(broken)
    except ManifestError as exc:
        print(f">> ManifestError raised, as designed:\n     {exc}")
    finally:
        broken.unlink(missing_ok=True)

    print()
    print("=" * 78)
    print("TRY IT YOURSELF - the Excel-lock test")
    print("=" * 78)
    print(f"  1. Open {MANIFEST.name} in Excel (double-click it) and LEAVE IT OPEN")
    print( "  2. Run:  python demo/demo_manifest.py write")
    print( "     -> you will see retry warnings, then a _manifest.pending.json sidecar")
    print( "  3. Close Excel, run the same command again")
    print( "     -> sidecar merges into the workbook and disappears")
    print( "  Also try: edit a Status cell in Excel to 'Done-ish', save, then run")
    print( "  'write' again -- load isn't involved in writes, but re-run the full demo")
    print( "  after typing garbage into Expected Count to see row-level errors.")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "write":
        scanner_style_write()
    else:
        full_demo()
