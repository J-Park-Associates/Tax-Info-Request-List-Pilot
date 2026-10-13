"""The command line as main.js drives it: argv in, one JSON reply out.

Every claim about the API is made through ``run(capsys, *argv)``, which calls
``api.main`` exactly as the window's ``main.js`` does and reads the one reply
back; ``scan`` is Sort & Scan as the app runs it (``run-now`` and then one
``list`` and one ``state``), and ``sample_engagement`` is a 1040 created through
the API with the sample pile dropped in. ``test_api`` wrote them and
``test_shell`` and ``test_rollover`` imported them from it; they live here so
the borrowing names a module that is not a test file (SPEC-architecture E-4, R2.1). Moved with their words from
``tests/test_api.py``, with the household, the people and ``where`` they lean on.
"""

import json
from pathlib import Path

import pytest

import tracker.api as api
from tests.conftest import TEST_CLIENT, app_stdin
from tests.samples import SCRATCH_PEOPLE
from tracker import ledger
from tracker.layout import inbox_of, return_dir_for
from tracker.manifest import ManifestError
from tracker.names import propose_spellings

#: The one household every spec below names unless the claim is about
#: households. A client folder is a household since decision 125, and a
#: return lives under its year inside it.
HOUSEHOLD = "Test Household"


#: Who every spec below says the return is for, unless the claim is about
#: the people list. A return is refused without one since decision 128.
PEOPLE = [{"kind": "taxpayer", "name": TEST_CLIENT,
           "spellings": list(propose_spellings(TEST_CLIENT, "taxpayer"))}]


#: Who the sample pile's documents are addressed to, as a spec sends them.
SAMPLE_PEOPLE = [{"kind": one.kind, "name": one.name, "spellings": list(one.spellings)}
                 for one in SCRATCH_PEOPLE]


def where(root, return_name, year=None, household=HOUSEHOLD):
    """Where the return a spec named landed.

    The layout's answer, never a name a test typed: the private tree, the
    household, the year, the return (decision 125).
    """
    from tracker.templates import default_tax_year

    return return_dir_for(root, household, year or default_tax_year(), return_name)


def _head_now(argv) -> str:
    """The version of the list ``state`` would hand the editor now (decision
    160), for an ``edit`` or a ``rename`` that does not name its own - blank
    where the command names no engagement, which it then refuses anyway."""
    from tracker.manifest import list_head

    try:
        return list_head(argv[list(argv).index(api.ENGAGEMENT_FLAG) + 1])
    except (ValueError, IndexError, ManifestError):
        return ""


def run(capsys, *argv, stdin=None):
    """Run one command the way main.js does: argv in, one JSON object out.

    A ``create`` spec that names no household, or names the one these
    claims use, is given that one - by its folder once it exists, as the wizard picks it in the list
    (decision 188 refuses a household name typed again): since decision 125 every return belongs to a household, and most
    of what is claimed here is about the API rather than about households.
    The same for the people it is for: since decision 128 a return is
    refused without one, and most of what is claimed here is not about the
    name tier. And an ``edit`` or a ``rename`` carries the version of the
    list it was made from, as the editor's does (decision 160): the current
    one, unless the claim is about a stale one and names it.
    """
    if (stdin is not None and argv and argv[0] == "create"
            and stdin.get("household", HOUSEHOLD) == HOUSEHOLD and "household_path" not in stdin):
        stdin = {key: value for key, value in stdin.items() if key != "household"}
        # Picked in the list once it exists, as the wizard does: since
        # decision 188 a household name typed again is refused.
        from tracker.layout import private_household_dir
        from tracker.settings import clients_root

        root = clients_root()
        known = private_household_dir(root, HOUSEHOLD) if root else None
        stdin = ({"household_path": str(known), **stdin}
                 if known is not None and ledger.path_for(known).is_file()
                 else {"household": HOUSEHOLD, **stdin})
    if stdin is not None and argv and argv[0] == "create" and "people" not in stdin:
        stdin = {"people": PEOPLE, **stdin}
    if stdin is not None and argv and argv[0] in ("edit", "rename") and "head" not in stdin:
        stdin = {**stdin, "head": _head_now(argv)}
    if stdin is not None:
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("sys.stdin", app_stdin(stdin))
            code = api.main(list(argv))
    else:
        code = api.main(list(argv))
    return code, one_reply(capsys.readouterr().out)


def one_reply(out: str) -> dict:
    """The one reply a command printed, the way main.js reads stdout
    (decision 193): every line but the last is a progress line, and the
    last - the only one without ``progress`` - is the reply."""
    from tracker.progress import PROGRESS_KEY

    lines = [json.loads(line) for line in out.strip().splitlines()]
    assert lines, "expected a reply, got nothing"
    assert all(PROGRESS_KEY in line for line in lines[:-1]), lines
    assert PROGRESS_KEY not in lines[-1], lines[-1]
    return lines[-1]


def scan(capsys, engagement) -> tuple[int, dict]:
    """Sort & Scan the way the app runs it since decision 203: ``run-now``,
    which hands this return's household to the runner's own pass in this
    process, then - when the pass ends - one ``list`` and one ``state``, as
    the renderer redraws (the lane's ruling on 194's Q5).

    Answers with the pass's exit code and the reply the claims below read:
    ``run`` is the asked return's entry in the final line, ``household``
    the household's other returns, ``pass_warnings`` and ``pass`` the final
    line's own, ``lock`` the lock a locked-out return met, and ``state``,
    ``list`` and ``warnings`` the redraw's. A refusal is its envelope."""
    code = api.main([api.PASS_COMMAND, api.ENGAGEMENT_FLAG, str(engagement)])
    final = one_reply(capsys.readouterr().out)
    if "error" in final:
        return code, final
    # Matched as the renderer matches (decision 203's review, S2): the
    # path's own spelling, the one the API gives the app, so a mismatch
    # fails here rather than hiding the counts on screen.
    asked = str(api._return_dir(engagement))
    [run] = [one for one in final["runs"] if one["path"] == asked]
    held = next((one["locked_at"] for one in final["runs"] if one["locked_at"]), None)
    assert api.main(["list"]) == 0
    listed = one_reply(capsys.readouterr().out)
    state_code = api.main(["state", api.ENGAGEMENT_FLAG, str(engagement)])
    state = one_reply(capsys.readouterr().out)
    return code, {
        "run": run,
        "household": [one for one in final["runs"] if one is not run],
        "pass_warnings": final["pass_warnings"],
        "pass": final["pass"],
        "lock": api._lock_payload(Path(held)) if held else None,
        "state": state if state_code == 0 else None,
        "list": {key: listed[key] for key in ("engagements", "households", "misfits", "root")},
        "warnings": state.get("warnings", []),
    }


def sample_engagement(capsys, demo_root, tmp_path, *names):
    """A 1040 engagement created through the API with sample documents dropped in."""
    from tests.samples import build_samples

    # The pile is addressed to the two people the samples name, so the
    # return lists them (decision 128) exactly as the office's would.
    spec = {"household": HOUSEHOLD, "return_name": "Smith Family 2025", "form": "1040", "client": "John Smith",
            "people": SAMPLE_PEOPLE,
            "items": [t for t in api.FORM_TEMPLATES["1040"] if t["core"]]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    engagement = where(demo_root, "Smith Family 2025")
    samples = tmp_path / "samples"
    build_samples(samples)
    for sample in samples.iterdir():
        if not names or sample.name in names:
            (inbox_of(engagement) / sample.name).write_bytes(sample.read_bytes())
    return engagement
