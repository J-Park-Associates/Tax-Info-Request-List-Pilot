"""Tests for tools/lockfiles.py - every install is of a file whose hash is known.

Decision 191. The committed locks are held to the rules here (every line
hashed, the direct pins and the locks agreeing, the GUI OpenCV nowhere), and
the commands that reach the network - ``hash`` and ``audit`` - are run
against answers made up for the test and handed in as ``fetch``: the suite
never opens a socket. The packages and advisories below are fabricated.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from tools import lockfiles
from tools.lockfiles import (
    CHANGED,
    LOCK_FILES,
    NATIVE_ENGINES,
    NOT_SET_UP,
    NPM_LOCK,
    OSV_BATCH,
    STALE_DAYS,
    STAMP_NAME,
    audit,
    check,
    hash_locks,
    read_lock,
    stamp,
    verify,
)

REPO = Path(__file__).resolve().parent.parent
DIGEST_A = "a" * 64
DIGEST_B = "b" * 64
DIGEST_C = "c" * 64


def fake_repo(root: Path, overrides: dict[str, str] | None = None) -> Path:
    """A repository holding the four locks and their requirement files, all agreeing."""
    files = {
        "requirements.txt": "# runtime\nexamplepkg==1.0\nnumpy==2.0; python_version < \"3.12\"\n",
        "requirements-build.txt": "-r requirements.txt\nfreezer==2.0\n",
        "requirements-nodeps.txt": "readerpkg==3.0\n",
        "requirements-gpu.txt": "nvidia-example==4.0\n",
        "requirements.lock": ("# header kept\nexamplepkg==1.0 \\\n    --hash=sha256:" + DIGEST_A + "\n"
                              "numpy==2.0; python_version < \"3.12\" \\\n    --hash=sha256:" + DIGEST_B + "\n"),
        "requirements-build.lock": "freezer==2.0 \\\n    --hash=sha256:" + DIGEST_C + "\n",
        "requirements-nodeps.lock": "readerpkg==3.0 \\\n    --hash=sha256:" + DIGEST_A + "\n",
        "requirements-gpu.lock": "nvidia-example==4.0 \\\n    --hash=sha256:" + DIGEST_B + "\n",
        NPM_LOCK: json.dumps({"packages": {
            "": {"name": "app", "version": "1.0.0"},
            "node_modules/electron": {"version": "40.0.0"},
            "node_modules/@scope/tool": {"version": "2.1.0"},
        }}),
    }
    files.update(overrides or {})
    for name, text in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text, encoding="utf-8", newline="\n")
    return root


# ------------------------------------------------------------ the committed locks ----


def test_every_committed_lock_line_carries_a_hash():
    for lock_name in LOCK_FILES:
        pins = read_lock(REPO / lock_name)
        assert pins, lock_name
        for name, version, _marker, hashes in pins:
            assert hashes, (lock_name, name, version)
            assert all(len(digest) == 64 for digest in hashes), (lock_name, name)
    assert check(REPO) == []


def test_the_direct_pins_and_the_locks_agree():
    """Each ``requirements*.txt`` pin is in its lock at the same version and
    marker, and no package is pinned twice under one marker across the four."""
    assert check(REPO) == []
    locked = {(lockfiles.normalise(name), version, marker)
              for lock_name in LOCK_FILES for name, version, marker, _hashes in read_lock(REPO / lock_name)}
    for source in LOCK_FILES.values():
        for name, version, marker in lockfiles.direct_pins(REPO / source):
            assert (lockfiles.normalise(name), version, marker) in locked, (source, name)


def test_the_gui_opencv_is_in_no_lock():
    for lock_name in LOCK_FILES:
        names = {lockfiles.normalise(name) for name, _v, _m, _h in read_lock(REPO / lock_name)}
        assert "opencv-python" not in names, lock_name
    assert "opencv-python-headless" in {lockfiles.normalise(name) for name, _v, _m, _h
                                        in read_lock(REPO / "requirements.lock")}


def test_the_native_engines_are_pinned_in_the_runtime_lock():
    """The cadence the audit enforces is about packages the app really ships."""
    names = {lockfiles.normalise(name) for name, _v, _m, _h in read_lock(REPO / "requirements.lock")}
    assert set(NATIVE_ENGINES) <= names
    assert STALE_DAYS == 90


def test_the_constraints_file_is_gone_and_no_install_names_it():
    """The locks replaced it: a constraint named a version, never a file."""
    assert not (REPO / "constraints.txt").exists()
    installers = [REPO / name for name in ("Setup.bat", "Start App.bat", "Build App.bat", "Build GPU Pack.bat",
                                           "README.md", "CLAUDE.md")]
    installers += sorted((REPO / ".github" / "workflows").glob("*.yml"))
    for path in installers:
        assert "constraints.txt" not in path.read_text(encoding="utf-8"), path.name


# ------------------------------------------------------------------- check ----


def test_a_fabricated_repository_that_agrees_is_clean(tmp_path):
    assert check(fake_repo(tmp_path)) == []


def test_a_pin_missing_its_hash_is_named(tmp_path):
    repo = fake_repo(tmp_path, {"requirements.lock": "examplepkg==1.0\n"
                     "numpy==2.0; python_version < \"3.12\" \\\n    --hash=sha256:" + DIGEST_B + "\n"})
    assert check(repo) == ["requirements.lock: examplepkg==1.0 carries no hash"]


def test_a_direct_pin_the_lock_holds_at_another_version_is_named(tmp_path):
    repo = fake_repo(tmp_path, {"requirements-nodeps.lock": "readerpkg==3.1 \\\n    --hash=sha256:" + DIGEST_A + "\n"})
    assert check(repo) == ["requirements-nodeps.txt pins readerpkg==3.0 and requirements-nodeps.lock does not"]


def test_a_direct_pin_whose_marker_differs_is_named(tmp_path):
    repo = fake_repo(tmp_path, {"requirements.lock": ("examplepkg==1.0 \\\n    --hash=sha256:" + DIGEST_A + "\n"
                                                  "numpy==2.0 \\\n    --hash=sha256:" + DIGEST_B + "\n")})
    assert check(repo) == ['requirements.txt pins numpy==2.0; python_version < "3.12" '
                           "and requirements.lock does not"]


def test_a_package_pinned_twice_under_one_marker_is_named(tmp_path):
    repo = fake_repo(tmp_path, {"requirements-build.lock": ("freezer==2.0 \\\n    --hash=sha256:" + DIGEST_C + "\n"
                                                        "examplepkg==1.1 \\\n    --hash=sha256:" + DIGEST_C + "\n")})
    assert check(repo) == ["requirements-build.lock: examplepkg is pinned again (at 1.0 in requirements.lock)"]


def test_the_gui_opencv_in_a_lock_is_named(tmp_path):
    repo = fake_repo(tmp_path, {"requirements-nodeps.lock": ("readerpkg==3.0 \\\n    --hash=sha256:" + DIGEST_A + "\n"
                                                         "opencv-python==5.0 \\\n    --hash=sha256:" + DIGEST_A + "\n")})
    assert check(repo) == ["requirements-nodeps.lock: opencv-python is the GUI build of OpenCV, "
                           "which the app never ships"]


def test_a_range_in_a_lock_is_refused_with_its_line(tmp_path):
    repo = fake_repo(tmp_path, {"requirements-gpu.lock": "nvidia-example>=4.0\n"})
    [problem] = check(repo)
    assert problem.startswith("requirements-gpu.lock line 1: not a name==version pin")


# ----------------------------------------------------------- stamp and verify ----


def test_verify_names_setup_when_there_is_no_stamp(tmp_path):
    repo = fake_repo(tmp_path / "repo")
    venv = tmp_path / "venv"
    venv.mkdir()
    assert verify(venv, repo) == NOT_SET_UP
    assert "Setup.bat" in NOT_SET_UP


def test_verify_is_quiet_when_the_stamp_matches(tmp_path):
    repo = fake_repo(tmp_path / "repo")
    venv = tmp_path / "venv"
    venv.mkdir()
    assert stamp(venv, repo) == venv / STAMP_NAME
    assert verify(venv, repo) is None


def test_verify_names_setup_when_a_lock_changed_after_the_stamp(tmp_path):
    repo = fake_repo(tmp_path / "repo")
    venv = tmp_path / "venv"
    venv.mkdir()
    stamp(venv, repo)
    lock = repo / "requirements.lock"
    lock.write_text(lock.read_text(encoding="utf-8") + "# a comment is a change too\n", encoding="utf-8")
    assert verify(venv, repo) == CHANGED
    assert "Setup.bat" in CHANGED


def test_verify_names_setup_when_the_npm_lock_changed_after_the_stamp(tmp_path):
    repo = fake_repo(tmp_path / "repo")
    venv = tmp_path / "venv"
    venv.mkdir()
    stamp(venv, repo)
    (repo / NPM_LOCK).write_text("{}", encoding="utf-8")
    assert verify(venv, repo) == CHANGED


def test_the_verify_command_prints_the_sentence_and_exits_one(tmp_path, capsys, monkeypatch):
    repo = fake_repo(tmp_path / "repo")
    monkeypatch.setattr(lockfiles, "ROOT", repo)
    venv = tmp_path / "venv"
    venv.mkdir()
    assert lockfiles.main(["verify", str(venv)]) == 1
    assert NOT_SET_UP in capsys.readouterr().err


# -------------------------------------------------------------------- hash ----


def test_hash_writes_every_file_hash_pypi_publishes_and_keeps_the_marker(tmp_path):
    repo = fake_repo(tmp_path)
    asked = []

    def fetch(url, body):
        asked.append(url)
        assert body is None
        # Two wheels and an sdist, out of order: every one is written, sorted.
        return {"urls": [{"digests": {"sha256": DIGEST_C}}, {"digests": {"sha256": DIGEST_A}},
                         {"digests": {"sha256": DIGEST_B}}]}

    assert hash_locks(repo, fetch=fetch) == list(LOCK_FILES)
    text = (repo / "requirements.lock").read_text(encoding="utf-8")
    assert text.startswith("# header kept\n")
    assert ('numpy==2.0; python_version < "3.12" \\\n'
            f"    --hash=sha256:{DIGEST_A} \\\n    --hash=sha256:{DIGEST_B} \\\n    --hash=sha256:{DIGEST_C}\n") in text
    assert "https://pypi.org/pypi/numpy/2.0/json" in asked
    assert read_lock(repo / "requirements.lock")[1] == ("numpy", "2.0", 'python_version < "3.12"',
                                                        [DIGEST_A, DIGEST_B, DIGEST_C])
    assert check(repo) == []


def test_hash_refuses_a_version_pypi_lists_no_files_for(tmp_path):
    repo = fake_repo(tmp_path)
    with pytest.raises(lockfiles.LockError, match="PyPI lists no files for examplepkg==1.0"):
        hash_locks(repo, fetch=lambda url, body: {"urls": []})


# ------------------------------------------------------------------- audit ----


def _answers(*, vulns: dict[tuple[str, str], list[str]] | None = None,
             newest: dict[str, tuple[str, str]] | None = None,
             releases: dict[str, dict[str, str]] | None = None):
    """A fetch that answers OSV with ``vulns`` and PyPI's project page with
    ``releases`` (name -> version -> first upload), the last listed being the
    newest; ``newest`` is the one-release shorthand."""
    vulns = vulns or {}
    releases = {**{name: {version: uploaded} for name, (version, uploaded) in (newest or {}).items()},
                **(releases or {})}
    seen = []

    def fetch(url, body):
        seen.append((url, body))
        if url == OSV_BATCH:
            return {"results": [
                {"vulns": [{"id": vuln} for vuln in vulns.get((query["package"]["name"], query["version"]), [])]}
                for query in body["queries"]]}
        name = url.split("/pypi/", 1)[1].split("/", 1)[0]
        listed = releases[name]
        return {"info": {"version": list(listed)[-1]},
                "releases": {version: [{"upload_time_iso_8601": uploaded}] for version, uploaded in listed.items()}}

    return fetch, seen


def _engines_repo(root: Path, pillow: str = "12.0", pdfium: str = "5.0") -> Path:
    return fake_repo(root, {"requirements.lock": (
        f"pillow=={pillow} \\\n    --hash=sha256:{DIGEST_A}\n"
        f"pypdfium2=={pdfium} \\\n    --hash=sha256:{DIGEST_B}\n")})


def test_audit_names_each_advisory_by_id_package_and_version(tmp_path):
    repo = _engines_repo(tmp_path)
    fetch, _seen = _answers(vulns={("pillow", "12.0"): ["GHSA-fake-0001", "PYSEC-0000-1"]},
                            newest={"pillow": ("12.0", "2026-01-01T00:00:00Z"),
                                    "pypdfium2": ("5.0", "2026-01-01T00:00:00Z")})
    assert audit(repo, fetch=fetch, today=date(2026, 9, 26)) == [
        "GHSA-fake-0001: pillow 12.0 (PyPI)", "PYSEC-0000-1: pillow 12.0 (PyPI)"]


def test_audit_fails_a_native_engine_behind_a_release_older_than_ninety_days(tmp_path):
    repo = _engines_repo(tmp_path)
    fetch, _seen = _answers(newest={"pillow": ("13.0", "2026-06-01T00:00:00Z"),      # 117 days
                                    "pypdfium2": ("5.1", "2026-08-01T00:00:00Z")})   # 56 days
    assert audit(repo, fetch=fetch, today=date(2026, 9, 26)) == [
        "pillow 12.0 is pinned, and 13.0, the first newer release, was published 2026-06-01, "
        "more than 90 days ago (newest: 13.0): bump the native engine"]
    # An engine at the newest release is never stale, however old that is.
    fetch, _seen = _answers(newest={"pillow": ("12.0", "2020-01-01T00:00:00Z"),
                                    "pypdfium2": ("5.0", "2020-01-01T00:00:00Z")})
    assert audit(repo, fetch=fetch, today=date(2026, 9, 26)) == []


def test_audit_measures_staleness_from_the_first_release_newer_than_the_pin(tmp_path):
    """Review S-1: an engine that releases every few weeks keeps its newest
    release young; the cadence runs from the day a newer release first
    existed. Pinned 5.11.0, 5.12.0 out 139 days ago, the newest a month old:
    red. Older releases, pre-releases and yanked files do not count."""
    repo = _engines_repo(tmp_path, pdfium="5.11.0")
    fetch, _seen = _answers(newest={"pillow": ("12.0", "2026-01-01T00:00:00Z")}, releases={"pypdfium2": {
        "5.10.0": "2026-01-01T00:00:00Z",
        "5.11.0": "2026-06-29T00:00:00Z",
        "5.12.0": "2026-07-15T00:00:00Z",
        "5.13.0": "2026-08-13T00:00:00Z",
        "5.14.0": "2026-11-01T00:00:00Z"}})
    assert audit(repo, fetch=fetch, today=date(2026, 12, 1)) == [
        "pypdfium2 5.11.0 is pinned, and 5.12.0, the first newer release, was published 2026-07-15, "
        "more than 90 days ago (newest: 5.14.0): bump the native engine"]
    # The same history on the day the first newer release is 90 days old: not yet.
    assert audit(repo, fetch=fetch, today=date(2026, 10, 13)) == []

    def pre_and_yanked(url, body):
        answer = fetch(url, body)
        if "pypdfium2" in url:
            answer["releases"] = {"5.11.0": [{"upload_time_iso_8601": "2026-06-29T00:00:00Z"}],
                                  "5.12.0rc1": [{"upload_time_iso_8601": "2026-01-01T00:00:00Z"}],
                                  "5.12.0": [{"upload_time_iso_8601": "2026-01-01T00:00:00Z", "yanked": True}],
                                  "5.13.0": [{"upload_time_iso_8601": "2026-11-01T00:00:00Z"}]}
        return answer

    assert audit(repo, fetch=pre_and_yanked, today=date(2026, 12, 1)) == []


def test_audit_reads_the_npm_lock_too(tmp_path):
    repo = _engines_repo(tmp_path)
    fetch, seen = _answers(vulns={("electron", "40.0.0"): ["GHSA-fake-0002"]},
                           newest={"pillow": ("12.0", "2026-01-01T00:00:00Z"),
                                   "pypdfium2": ("5.0", "2026-01-01T00:00:00Z")})
    assert audit(repo, fetch=fetch, today=date(2026, 9, 26)) == ["GHSA-fake-0002: electron 40.0.0 (npm)"]
    [(url, body)] = [(url, body) for url, body in seen if url == OSV_BATCH]
    npm = {(q["package"]["name"], q["version"]) for q in body["queries"] if q["package"]["ecosystem"] == "npm"}
    assert npm == {("electron", "40.0.0"), ("@scope/tool", "2.1.0")}      # the app itself is not a package
    pypi = {(q["package"]["name"], q["version"]) for q in body["queries"] if q["package"]["ecosystem"] == "PyPI"}
    assert ("readerpkg", "3.0") in pypi and ("nvidia-example", "4.0") in pypi   # every lock, not one


def test_nothing_in_the_tracker_imports_the_lock_tool():
    """The fourth standing rule: no network in tracker/, and this tool has two network commands."""
    for path in (REPO / "tracker").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "lockfiles" not in text, path
