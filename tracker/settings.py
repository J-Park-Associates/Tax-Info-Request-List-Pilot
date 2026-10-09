"""The one place the app is told where the clients live (component 13).

The desktop app and the scheduled run both need the clients root - the
folder every engagement sits under. It used to exist twice: an environment
variable the Electron shell set for the app (with a stand-in default),
and a path typed on the runner's command line for the job. Nothing tied
them together, so the app could be showing one folder while the schedule
walked another.

Now it is written once, in ``SETTINGS_FILENAME`` beside the app - next to the
packaged executable, or in the repository root when run from source - and
both read it. The app asks for it on first launch and never again; the
scheduled job names this file's folder rather than the root, and reads the
root from here at every run (decision 131), so the root has one home and a
root changed in the app is the root the job walks next.

Deliberately tiny: one JSON object (the clients root, the firm's name and,
since decision 117, the firm's telephone number), read and written whole,
atomic on write. What is here is what belongs to the firm rather than to
an engagement; there is no second copy of any of it to drift.

Its absence is learned by opening it, never by asking whether it exists
(decision 185): ``exists()`` raises no audit event, so the suite's tripwire
sees every attempt on the file, on a machine that has one and on one without.

**What the tracker derives from clients never sits here** (decision 186). The
settings file is a pointer - the clients root, the firm's name and telephone
number, nothing about a client - so it stays beside the app. The store, a
reading's temporary files, the run log and the scheduler's task file live in
:func:`data_home`: the Windows account's own local application-data folder,
never beside the program, in a checkout, on removable media or in the temp
folder, and :func:`data_home` refuses rather than fall back to any of them.

``ENV_REAL_CORPUS`` sits here for the same reason the clients root does:
it is the other folder outside the repository the code is told about - the
firm's own redacted documents, which the harness and the coverage report
route when it is set and skip when it is not. It is an environment
variable rather than a setting because it belongs to the machine a person
develops on, never to an engagement, and because a run must never depend
on it.
"""

from __future__ import annotations

import json
import logging
import os
import re
import secrets
import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

from tracker import layout
from tracker.fsio import write_json_atomically

SETTINGS_FILENAME = "settings.json"
#: The folder decision 137 (L7) kept OCR's page images in, beside the app.
#: Retired by decision 169 - the reader writes none - but an old checkout or
#: install may still hold it with a client's page inside, so the ignore file
#: and the suite's tripwire (decision 185) both name it, from here.
OCR_SCRATCH_DIRNAME = "ocr-scratch"
#: The keys inside it.
KEY_CLIENTS_ROOT = "clients_root"
KEY_FIRM = "firm"
#: The firm's own telephone number (decision 117). It belongs beside the
#: firm's name for the same reason the name is there: it is the firm's,
#: not one engagement's, and typing it into every client's details would
#: be the same number recorded a hundred times. Only the final-notice
#: reminder says it, and a blank one drops that sentence rather than
#: printing an empty invitation to call.
KEY_FIRM_PHONE = "firm_phone"
#: The schedule setting (pilot decision P21): whether this computer runs the
#: scheduled pass, the time of day it first runs, and how often it repeats.
#: Written only when a person saves the setting, so a file holding just the
#: clients root stays just that; every registration of the schedule reads it.
KEY_SCHEDULE_ENABLED = "schedule_enabled"
KEY_SCHEDULE_START = "schedule_start"
KEY_SCHEDULE_EVERY = "schedule_every"
#: What an absent key means. ``tracker.scheduling`` names the same two
#: numbers ``DEFAULT_START`` and ``DEFAULT_REPEAT_MINUTES``.
DEFAULT_SCHEDULE_ENABLED = True
DEFAULT_SCHEDULE_START = "07:00"
#: Filing and scanning repeat through the day this often (minutes); the
#: reminder still drafts only on the drafting day. 0 = once a day.
DEFAULT_SCHEDULE_EVERY = 120
#: The intervals a person may choose: once a day, or every 30, 60, 120,
#: 240 or 480 minutes.
EVERY_CHOICES = (0, 30, 60, 120, 240, 480)
_START_SHAPE = re.compile(r"([01][0-9]|2[0-3]):([0-5][0-9])")
START_REFUSED = "The start time {value!r} is not allowed; write it as HH:MM, two digits each, from 00:00 to 23:59."
EVERY_REFUSED = ("How often {value!r} is not allowed; choose once a day (0) or every 30, 60, 120, 240 "
                 "or 480 minutes.")
ENABLED_REFUSED = "Whether the schedule is on {value!r} is not allowed; it is on (true) or off (false)."
SCHEDULE_KEY_REFUSED = "{file}: {key} - {problem}"
#: How a person is told to set the root without the app.
SET_ROOT_HINT = "python -m tracker.settings <folder>"
#: What a command line with no clients root tells a person: the app first,
#: because the packaged app is what the office runs and has no ``python``
#: to type; the command second (decision 131's review).
NO_ROOT_HINT = f"set the clients folder in the app, or run {SET_ROOT_HINT}"
#: The clients-root example every prompt and document shows.
EXAMPLE_ROOT = r"G:\Shared drives\Clients"
ENV_SETTINGS_DIR = "TRACKER_SETTINGS_DIR"
#: The Electron shell passes package.json's productName; from source the
#: same file is read directly. There is no second copy of the product name.
ENV_PRODUCT_NAME = "TRACKER_PRODUCT_NAME"
PACKAGE_JSON = Path(__file__).resolve().parent.parent / "app" / "package.json"
#: The folder of the firm's own redacted documents, outside the repository.
ENV_REAL_CORPUS = "TRACKER_REAL_CORPUS"
#: A corpus inside the app's own folder is refused by name (decision 186).
CORPUS_INSIDE_APP = (ENV_REAL_CORPUS + " names {folder}, inside the app's own folder (the code "
                     "checkout, from source); the firm's documents never sit there - move them out")
#: Where the tracker keeps what it derives from clients on this machine
#: (decision 186): the store, a reading's temporary files, the run log and the
#: scheduler's task file. An absolute path; the suite and CI set it.
ENV_DATA_HOME = "TRACKER_DATA_HOME"
#: The data home's folder name: app/package.json's "name", held equal by a test.
DATA_HOME_NAME = "tax-document-tracker-pilot"
#: The pilot's name before the rename (P155, product_name() says the new one): the one home
#: of the earlier name. The after-install step reads the settings file left in
#: its program folder and removes its scheduled task (SPEC-rename R5, R6); the
#: installer script, the two Windows check scripts and package.json's
#: config.userDataName type it, and a test holds each copy equal to this. It is
#: never the firm's production product ("Tax Document Tracker", no "Pilot"),
#: whose task and folders nothing here touches. The data home above keeps its
#: name through the rename (R3): it is package.json's internal "name".
EARLIER_PRODUCT_NAME = "Tax Document Tracker Pilot"
SCRATCH_DIR_NAME = "scratch"
LOGS_DIR_NAME = "logs"
#: GetDriveTypeW's answers (WinBase.h). Only DRIVE_FIXED may hold the program
#: the schedule runs, or the data home.
DRIVE_UNKNOWN, DRIVE_NO_ROOT_DIR, DRIVE_REMOVABLE, DRIVE_FIXED, DRIVE_REMOTE, DRIVE_CDROM, DRIVE_RAMDISK = range(7)

NO_LOCAL_APPDATA = ("LOCALAPPDATA is not set for this Windows account, so the app has nowhere "
                    "private to keep its database; it never keeps it beside the program or in the "
                    "temp folder instead. Run the app as the account that runs the schedule")
LOCAL_APPDATA_NOT_A_FOLDER = "LOCALAPPDATA names {folder}, which is not a folder on this computer"
NO_HOME = ("this account has no home folder, so the app has nowhere private to keep its "
           "database; set " + ENV_DATA_HOME + " to a folder of its own")
DATA_HOME_NOT_ABSOLUTE = ENV_DATA_HOME + " must name a whole path, got {value!r}"
DATA_HOME_BESIDE_PROGRAM = ("the app's data folder {home} would be inside the program's own "
                            "folder {program}, or hold it; client data never sits beside the program")
DATA_HOME_NOT_LOCAL = ("the app's data folder {home} is not on this computer's own disk; "
                       "client data never sits on a removable or network drive")
#: F7 (P193): Windows silently redirects what a program started from inside
#: a packaged app (the Claude desktop app, on 9/29) writes under
#: %LOCALAPPDATA% into that package's own copy,
#: %LOCALAPPDATA%\Packages\<package>\LocalCache\Local. Such a process sees the
#: copy at the normal path, so two stores and two checkpoints each refuse the
#: other's lines. The probe file's name starts with this; the rest is the
#: process id and 16 random hex digits, so two probes never meet.
REDIRECT_PROBE_PREFIX = ".tracker-redirect-probe-"
#: Where Windows keeps each package's own folders, inside %LOCALAPPDATA%, and
#: where inside one of them a redirected %LOCALAPPDATA% write lands.
PACKAGES_DIR_NAME = "Packages"
REDIRECTED_LOCAL = ("LocalCache", "Local")
#: The refusal when this process's %LOCALAPPDATA% is redirected (R1); a
#: SettingsError, so the first screen and the pass say it as they say any
#: data home they cannot have. {package} is the package folder's name, never a
#: client's; {product} is product_name(), the product name's one home.
DATA_HOME_REDIRECTED = ("Windows is giving this copy of the app a private data folder of its own, "
                        "because it was started from inside another program ({package}). Close it "
                        "and start {product} from the Start menu.")
#: One first-screen sentence per stale redirected copy (R2). The app never
#: removes it: it holds client-derived data (decision 186).
REDIRECTED_COPY = ("Windows kept a private copy of the app's data folder at {path}, from a time "
                   "the app was started inside another program. The app never uses it and it is "
                   "out of date; move that folder to the Recycle Bin.")
#: When Windows will not list %LOCALAPPDATA%\Packages (combined review S2):
#: the probe cannot tell whether this process is redirected, nor the first
#: screen which stale copies there are, so both say this one sentence. The
#: folder is the machine's, never a client's, and the error is said by its
#: class (decision 190), never its message or a traceback.
PACKAGES_UNREADABLE = ("Windows would not let the app list {folder} ({error}), so it cannot tell "
                       "whether Windows is keeping a private copy of its data folder there; let "
                       "this Windows account read that folder, then start the app again.")
#: Why Install Schedule refuses to schedule the program from where it is
#: (decision 186): the task runs whatever program sits at that path on every
#: pass, so a stick or a share would carry the program - and, beside it, the
#: settings - wherever the drive goes. One sentence per answer Windows gives.
PROGRAM_ON_REMOVABLE = ("The app is running from a removable drive ({folder}). The schedule runs "
                        "whatever program sits there, every pass, so it is not installed from here: "
                        "copy the app's folder to this computer's own disk (a short path, such as "
                        "C:\\Tools), start it from there and press Install Schedule.")
PROGRAM_ON_NETWORK = ("The app is running from a network drive ({folder}). The schedule runs "
                      "whatever program sits there, every pass, so it is not installed from here: "
                      "copy the app's folder to this computer's own disk (a short path, such as "
                      "C:\\Tools), start it from there and press Install Schedule.")
PROGRAM_DRIVE_UNKNOWN = ("Windows cannot say what kind of drive the app is running from ({folder}), "
                         "so the schedule is not installed from here: copy the app's folder to this "
                         "computer's own disk (a short path, such as C:\\Tools), start it from there "
                         "and press Install Schedule.")
#: The file beside them that says where each one belongs, and its columns:
#: the document's own name, the catalog it is routed against, the
#: engagement year, and the identifier it must file under - blank for a
#: document that must park for a person.
EXPECTATIONS_FILENAME = "expectations.csv"
COLUMN_FILE = "file"
COLUMN_CATALOG = "catalog"
COLUMN_YEAR = "year"
COLUMN_EXPECTED = "expected"
EXPECTATIONS_COLUMNS = (COLUMN_FILE, COLUMN_CATALOG, COLUMN_YEAR, COLUMN_EXPECTED)
#: How the ``expected`` column names more than one request: ``A01+A02``
#: means "filed to exactly these, and to nothing else". One document can
#: belong to several when it carries several forms (decision 94), and a
#: harness that could only say one identifier would have had to call the
#: other filing a miss. Blank still means "parks"; a single identifier
#: still means "filed there and nowhere else".
EXPECTED_SEP = "+"


class SettingsError(Exception):
    """The settings file could not be read, or names a folder that is not there."""


class DataHomeRedirected(SettingsError):
    """F7's R1 refusal (``DATA_HOME_REDIRECTED``): its own class so the first
    screen says R1's sentence alone, never also naming the folder this
    process is using as a stale copy the app "never uses" (combined review N3)."""


def settings_dir() -> Path:
    """Where ``SETTINGS_FILENAME`` lives: beside the app.

    The Electron shell passes the folder in ``ENV_SETTINGS_DIR`` (next to
    the packaged executable). A frozen API without it uses its own folder;
    source checkouts use the repository root. It holds the settings file
    and nothing derived from a client (decision 186).
    """
    override = os.environ.get(ENV_SETTINGS_DIR)
    if override:
        return Path(override)
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def settings_path() -> Path:
    return settings_dir() / SETTINGS_FILENAME


def earlier_settings_path() -> Path | None:
    """Where the earlier name's installer put the settings file, or None.

    Inno Setup installed the pilot under ``%LOCALAPPDATA%\\Programs\\<name>``,
    and the settings file lives beside the program, so this is the file a PC
    uninstalled under the earlier name left behind (the uninstaller keeps
    it on purpose). None where ``LOCALAPPDATA`` is unset: there is then no
    such folder to look in, and the caller says there was nothing to carry.
    """
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        return None
    return Path(local) / "Programs" / EARLIER_PRODUCT_NAME / SETTINGS_FILENAME


#: The local debug log (decision 193, security principle 7): an
#: unexpected error's full text and traceback, and every warning the
#: package logs, go here and nowhere else - never on screen, in the record,
#: on the page or in the run log. It can name a client's folder, so it
#: lives beside the tracker's database, on this machine, never in either
#: client tree; rotated by size, and never synced to disk per line.
ERROR_LOG_FILENAME = "tracker-errors.log"
ERROR_LOG_MAX_BYTES = 1_000_000
ERROR_LOG_BACKUPS = 3
ERROR_LOG_FORMAT = "%(asctime)s pid=%(process)d %(name)s %(levelname)s %(message)s"
#: The one line said on stderr when the error log cannot take a record
#: (decision 190's landing review, SF1): the failure's class and code,
#: never the record - whose words go to the log "and nowhere else".
ERROR_LOG_NOT_WRITTEN = "{name} could not be written ({kind}); what it would have held is not said here."


def error_log_path() -> Path:
    """Where :data:`ERROR_LOG_FILENAME` lives: beside the tracker's database
    (the folder of ``store.store_path()``, the one the pass-order hint uses),
    so it moves with the store wherever the store goes. ``store`` is asked
    at call time: it sits above this module."""
    from tracker import store

    return store.store_path().parent / ERROR_LOG_FILENAME


class _ErrorLog(logging.Handler):
    """The error log's own few lines of rotation (decision 193's review,
    S2): not ``logging.handlers``, which loads ``socket`` at import, so
    importing the tracker loads no network module. Before a record that
    would take the file past :data:`ERROR_LOG_MAX_BYTES` the file becomes
    ``.1``, ``.1`` becomes ``.2`` and so on to :data:`ERROR_LOG_BACKUPS`;
    each record is appended whole in UTF-8 and never ``fsync``-ed. Both
    numbers are read when a record is written.

    A record it cannot write is said by :meth:`handleError` as one fixed
    line, never through ``logging``'s own, which prints the record's
    message and arguments - a kept error's whole words - to stderr
    (decision 190's landing review, SF1)."""

    def __init__(self, path: Path) -> None:
        super().__init__(logging.WARNING)
        self.path = path

    def emit(self, record: logging.LogRecord) -> None:
        try:
            data = (self.format(record) + "\n").encode("utf-8")
            try:
                size = self.path.stat().st_size
            except FileNotFoundError:
                size = 0
            if size and size + len(data) > ERROR_LOG_MAX_BYTES:
                self._rotate()
            with self.path.open("ab") as handle:
                handle.write(data)
        except Exception:
            self.handleError(record)

    def handleError(self, record: logging.LogRecord) -> None:
        # At call time, as store is in error_log_path(): this module's
        # load-time imports stay layout and fsio.
        from tracker import errors

        if logging.raiseExceptions and sys.stderr is not None:
            try:
                sys.stderr.write(ERROR_LOG_NOT_WRITTEN.format(
                    name=self.path.name, kind=errors.error_class(sys.exc_info()[1])) + "\n")
            except OSError:
                pass    # no stderr to say it on either: as logging's own handleError does

    def _rotate(self) -> None:
        def kept(n: int) -> Path:
            return self.path.with_name(f"{self.path.name}.{n}")

        kept(ERROR_LOG_BACKUPS).unlink(missing_ok=True)
        for n in range(ERROR_LOG_BACKUPS - 1, 0, -1):
            if kept(n).exists():
                os.replace(kept(n), kept(n + 1))
        os.replace(self.path, kept(1))


@contextmanager
def error_log(logger_name: str = "tracker") -> Iterator[Path | None]:
    """Attach the rotating error log to ``logger_name`` for the block.

    WARNING and above, UTF-8, opened only when something is written, and
    never ``fsync``-ed: it is a debug aid, and a sync per line would cost
    the pass that is failing. A folder that cannot hold it costs the log,
    never the command - and so does a data home that cannot be had
    (decision 186): the log sits beside the store, which lives there, so
    there is no log and the block yields ``None``; the command says why.
    """
    logger = logging.getLogger(logger_name)
    path: Path | None = None
    handler: logging.Handler | None = None
    try:
        path = error_log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        handler = _ErrorLog(path)
    except (OSError, SettingsError):
        handler = None
    if handler is not None:
        handler.setFormatter(logging.Formatter(ERROR_LOG_FORMAT))
        logger.addHandler(handler)
    try:
        yield path
    finally:
        if handler is not None:
            logger.removeHandler(handler)
            handler.close()


def _read() -> dict:
    """What the settings file (:data:`SETTINGS_FILENAME`) says, as a shallow
    copy of the caller's own - read once per reading inside :func:`one_reading`
    (P118), from the file every other time."""
    if _HELD is not None and _SETTINGS_HELD in _HELD:
        return dict(_HELD[_SETTINGS_HELD])
    path = settings_path()
    try:
        text = path.read_text(encoding="utf-8")
    except (FileNotFoundError, NotADirectoryError):
        return {}           # nothing written yet: the same answer exists() gave
    except (OSError, UnicodeDecodeError) as exc:
        raise SettingsError(f"{path} could not be read: {exc}") from None
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise SettingsError(f"{path} could not be read: {exc}") from None
    if not isinstance(data, dict):
        raise SettingsError(f"{path} should hold one JSON object")
    if _HELD is not None:
        _HELD[_SETTINGS_HELD] = data
    return dict(data)


def clients_root() -> Path | None:
    """The configured clients root, or None when nothing has been set yet."""
    raw = str(_read().get(KEY_CLIENTS_ROOT, "") or "").strip()
    return Path(raw) if raw else None


def firm() -> str:
    """The firm's name as typed once at setup; a new return's default Firm."""
    return str(_read().get(KEY_FIRM, "") or "").strip()


def firm_phone() -> str:
    """The firm's telephone number, or "" when nobody has set one."""
    return str(_read().get(KEY_FIRM_PHONE, "") or "").strip()


def product_name() -> str:
    """What the app is called, from app/package.json (or the shell's copy of it)."""
    override = os.environ.get(ENV_PRODUCT_NAME)
    if override:
        return override
    try:
        return str(json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))["productName"])
    except (OSError, json.JSONDecodeError, KeyError) as exc:
        # A frozen build has no package.json; the shell always passes the
        # name in. Naming the product here would be a second copy of it.
        raise SettingsError(
            f"{ENV_PRODUCT_NAME} is not set and {PACKAGE_JSON.name} is not readable: {exc}"
        ) from exc


def real_corpus_dir() -> Path | None:
    """The folder of the firm's own redacted documents, or None.

    ``ENV_REAL_CORPUS`` names it and it lives outside the repository, so
    an unset variable and a folder that is not there mean the same thing -
    there is nothing to route - and both answer None. Raising instead
    would fail the suite on every machine that has no corpus, CI's
    included; the harness and the report skip on None and say so.

    A corpus inside the app's own folder is another matter (decision 186):
    not a machine with nothing to route but a positive mistake - the
    firm's documents one ``git add -A`` from every clone - so it raises
    ``CORPUS_INSIDE_APP`` and fails loudly on that one machine.
    """
    named = os.environ.get(ENV_REAL_CORPUS, "").strip()
    if not named:
        return None
    folder = Path(named)
    if not folder.is_dir():
        return None
    if inside_the_app(folder):
        raise SettingsError(CORPUS_INSIDE_APP.format(folder=folder))
    return folder


def _write(data: dict) -> None:
    refuse_a_write_while_reading("the settings file")
    # Inside a household's hold too (P207, the review's SHOULD-3): every
    # setter writes back what _read() handed it, which there is the copy
    # held since the household began, so a save the app made meanwhile
    # would be undone in silence. The pass never writes the file; a write
    # that ever tried is refused, loudly, rather than losing a save.
    if _HELD is not None:
        raise RuntimeError(WRITE_WHILE_HOLDING.format(what="the settings file"))
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomically(path, data)


class ScheduleChoiceError(ValueError):
    """A schedule choice that is not allowed; the message is the sentence
    that names the value and what is allowed."""


@dataclass(frozen=True, slots=True)
class SchedulePreference:
    """The saved schedule choice: on or off, the first run's time (``HH:MM``)
    and the minutes between runs (0 = once a day). One type for the
    settings file, the registration and the API."""

    enabled: bool = DEFAULT_SCHEDULE_ENABLED
    start: str = DEFAULT_SCHEDULE_START
    every: int = DEFAULT_SCHEDULE_EVERY


def check_start(value: object) -> str:
    """``value`` as a start time, ``HH:MM`` from 00:00 to 23:59, or the
    sentence saying what is allowed. The one check every door shares."""
    text = value.strip() if isinstance(value, str) else ""
    if not _START_SHAPE.fullmatch(text):
        raise ScheduleChoiceError(START_REFUSED.format(value=value))
    return text


def check_every(value: object) -> int:
    """``value`` as the minutes between runs - one of :data:`EVERY_CHOICES`
    - or the sentence saying what is allowed. A whole number in a string
    (a command line's) is taken; a fraction, a truth value and anything
    else is refused, never rounded."""
    number = value
    if isinstance(value, str) and re.fullmatch(r"[0-9]{1,4}", value.strip()):
        number = int(value.strip())
    if isinstance(number, bool) or not isinstance(number, int) or number not in EVERY_CHOICES:
        raise ScheduleChoiceError(EVERY_REFUSED.format(value=value))
    return number


def schedule_preference() -> SchedulePreference:
    """The saved schedule choice; an absent key is its default. A value that
    is not allowed - a hand-edited file - is refused in a sentence naming
    the file and the key, never guessed and never reset."""
    data = _read()
    chosen: dict = {}
    for key, name, check in ((KEY_SCHEDULE_ENABLED, "enabled", _check_enabled),
                             (KEY_SCHEDULE_START, "start", check_start),
                             (KEY_SCHEDULE_EVERY, "every", check_every)):
        if key not in data:
            continue
        try:
            chosen[name] = check(data[key])
        except ScheduleChoiceError as exc:
            raise ScheduleChoiceError(
                SCHEDULE_KEY_REFUSED.format(file=settings_path(), key=key, problem=exc)) from None
    return SchedulePreference(**chosen)


def _check_enabled(value: object) -> bool:
    if not isinstance(value, bool):
        raise ScheduleChoiceError(ENABLED_REFUSED.format(value=value))
    return value


def set_schedule(enabled: object, start: object, every: object) -> SchedulePreference:
    """Record the schedule choice beside the clients root, all three keys,
    after every one is checked (nothing is written if any is refused)."""
    chosen = SchedulePreference(_check_enabled(enabled), check_start(start), check_every(every))
    data = _read()
    data[KEY_SCHEDULE_ENABLED] = chosen.enabled
    data[KEY_SCHEDULE_START] = chosen.start
    data[KEY_SCHEDULE_EVERY] = chosen.every
    _write(data)
    return chosen


def _set_text(key: str, value: object) -> str:
    """Record one piece of text the firm typed under ``key``, stripped and
    otherwise as typed, and return what was recorded."""
    data = _read()
    data[key] = str(value).strip()
    _write(data)
    return data[key]


def set_firm(name: str) -> str:
    """Record the firm's name beside the clients root."""
    return _set_text(KEY_FIRM, name)


def set_firm_phone(number: str) -> str:
    """Record the firm's telephone number beside its name.

    Stripped and otherwise taken as typed: a firm writes its own number
    its own way - with an extension, a country code, two numbers - and a
    format this code invented would be a number read out to a client in
    the firm's name that the firm never wrote.
    """
    return _set_text(KEY_FIRM_PHONE, number)


def app_dir() -> Path:
    """The app's own folder: the packaged executable's, or the repository
    root when run from source.

    Not :func:`settings_dir`, which the Electron shell may point elsewhere:
    this is where the program itself lives, whatever the settings say.
    Answered once per reading inside :func:`one_reading` (P118).
    """
    return held(("app_dir",), _the_app_dir)


def _the_app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def inside_the_app(path: Path | str) -> bool:
    """Whether ``path`` is the app's own folder or lies inside it - the
    repository, when run from source (decision 185).

    The one answer the report tools ask before writing, because a file there
    is one `git add -A` away from every clone; judged by the folder itself
    as well as its spelling (:func:`_inside`). Decision 186 asks it too:
    client data never lives in a code checkout.
    """
    return _inside(Path(path).expanduser().resolve(), app_dir())


def system_drive_root() -> Path:
    """The root of the drive the operating system lives on
    (``%SystemDrive%\\``), or ``/`` where there are no drive letters."""
    if os.name == "nt":
        return Path(os.environ.get("SystemDrive", "C:") + os.sep)
    return Path("/")


def drive_type(path: Path) -> int:
    """GetDriveTypeW for the drive ``path`` is on (DRIVE_*). Off Windows there
    are no drive letters to ask about and the program is never scheduled from
    there (install_task only prints the command), so it answers DRIVE_FIXED.

    What it buys (SPEC-186 section 10, the review's S2): it refuses what
    Windows *reports* as removable, network or unknown - the stick the old
    build script named - not every portable disk. A USB hard disk reports
    DRIVE_FIXED and passes; so do a ``subst`` letter and a mounted VHD on a
    fixed disk. Only ``path``'s own drive letter or share is asked, so a
    folder junctioned onto another drive is judged by the drive its
    spelling names: :func:`app_dir` and :func:`settings_dir` are resolved
    first and are seen through a junction, the data home is not.
    """
    if os.name != "nt":
        return DRIVE_FIXED
    import ctypes
    drive = os.path.splitdrive(os.path.abspath(str(path)))[0]   # "E:" or "\\\\server\\share"
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetDriveTypeW.argtypes = (ctypes.c_wchar_p,)
    kernel32.GetDriveTypeW.restype = ctypes.c_uint
    return int(kernel32.GetDriveTypeW(drive + "\\"))


def program_folders() -> list[Path]:
    """The folders the data home may neither sit in nor hold (decision 186):
    the app's own folder (as :func:`inside_the_app` judges it - on a source
    install, the checkout), and the settings folder **when it holds the app**
    - the packaged app, whose shell keeps its settings in the unzipped
    package the executable sits inside. A settings folder that does not
    hold the program (the suite's per-test folder) is not the program.
    Answered once per reading inside :func:`one_reading` (P118)."""
    return list(held(("program_folders",), _the_program_folders))


def _the_program_folders() -> list[Path]:
    app = app_dir()
    folders = [app]
    settings = settings_dir().resolve()
    if settings != app and _inside(app, settings):
        folders.append(settings)
    return folders


def beside_the_program() -> list[Path]:
    """Where an earlier version kept client data **beside the program**
    (decision 186): the settings folder, and the frozen executable's own
    folder when it is another (a package without the shell kept its store
    there). The one answer to "beside the program": what was left behind
    (:func:`tracker.runner.left_behind`) is looked for here, and the store
    refuses to make a fresh record checkpoint while the old one sits here
    (the rebase review's MF1). Not :func:`program_folders`, which is where
    the data home may not be; in a source checkout this is the settings
    folder alone, the repository root unless the shell names another."""
    folders = [settings_dir().resolve()]
    app = app_dir()
    spelled = [os.path.normcase(os.path.abspath(str(folder))) for folder in (app, folders[0])]
    if getattr(sys, "frozen", False) and spelled[0] != spelled[1]:
        folders.append(app)
    return folders


def resolve_data_home(environ, *, windows: bool, home: Path | None, program, drive_type) -> Path:
    """The data home for this environment - the pure core of :func:`data_home`,
    so every branch is testable on any machine (decision 186).

    In order: ``ENV_DATA_HOME`` when set and not blank, which must be a whole
    path (a relative one would land in the working folder, which for a
    source install's scheduled job is the checkout); on Windows
    ``%LOCALAPPDATA%`` + ``DATA_HOME_NAME`` - the account's own local
    application-data folder, never roamed, unlike ``%APPDATA%`` - and **no
    fallback** when it is unset or not a folder; elsewhere
    ``$XDG_STATE_HOME`` (when absolute) or ``~/.local/state``. Then, whoever
    answered: never inside any of ``program`` nor holding one, and only on a
    disk ``drive_type`` calls fixed. Only a path is answered; nothing is made.
    """
    override = (environ.get(ENV_DATA_HOME) or "").strip()
    if override:
        answer = Path(override)
        if not answer.is_absolute():
            raise SettingsError(DATA_HOME_NOT_ABSOLUTE.format(value=override))
    elif windows:
        local = (environ.get("LOCALAPPDATA") or "").strip()
        if not local:
            raise SettingsError(NO_LOCAL_APPDATA)
        folder = Path(local)
        if not folder.is_absolute() or not folder.is_dir():
            raise SettingsError(LOCAL_APPDATA_NOT_A_FOLDER.format(folder=local))
        answer = folder / DATA_HOME_NAME
    else:
        state = (environ.get("XDG_STATE_HOME") or "").strip()
        if state and Path(state).is_absolute():
            answer = Path(state) / DATA_HOME_NAME
        elif home is None:
            raise SettingsError(NO_HOME)
        else:
            answer = Path(home) / ".local" / "state" / DATA_HOME_NAME
    for folder in program:
        if _inside(answer, Path(folder)) or _inside(Path(folder), answer):
            raise SettingsError(DATA_HOME_BESIDE_PROGRAM.format(home=answer, program=folder))
    if drive_type(answer) != DRIVE_FIXED:
        raise SettingsError(DATA_HOME_NOT_LOCAL.format(home=answer))
    return answer


def _home() -> Path | None:
    try:
        return Path.home()
    except (RuntimeError, KeyError, OSError):   # no home folder for this account
        return None


def data_home() -> Path:
    """Where this account keeps what the tracker derives from clients on this
    machine (decision 186): the store, a reading's temporary files, the run
    log and the scheduler's task file. :func:`resolve_data_home` over this
    process's environment; not cached, so an override takes effect at once.
    It creates nothing - each writer makes its own path when it writes.

    What it buys (SPEC-186 section 10, the review's S2): it moves
    client-derived data off the program's folder, the checkout, removable
    media and the temp folder. It is not a wall: the folder is readable by
    this Windows account, the machine's administrators, SYSTEM and any
    program running as this account - which is why the AI tooling runs
    under another account - and it is not encrypted. A ``TRACKER_DATA_HOME``
    a person sets is trusted to be where they mean, within the two checks;
    it is not resolved, so one junctioned elsewhere is judged by its own
    spelling's drive (:func:`drive_type`).

    Inside :func:`one_reading` - one read-only reply - it is answered once
    and then from memory (P118): the proof that it is not inside the
    program asks the disk a few dozen times, and every store read asks it.

    On Windows, with no ``ENV_DATA_HOME``, a data home Windows is
    redirecting is refused (F7, P193): see :func:`_the_data_home`."""
    return held(("data_home",), lambda: _the_data_home(os.environ, windows=os.name == "nt"))


def _the_data_home(environ, *, windows: bool) -> Path:
    """:func:`resolve_data_home`, then the redirect refusal (F7, P193, R1).

    Why here and not in :func:`resolve_data_home` or
    :func:`default_data_home`: the suite always sets ``ENV_DATA_HOME``, and
    the tripwire must still learn the real place without a probe. Why only
    with no ``ENV_DATA_HOME``: a person who names a folder means it. Why
    once a process (:func:`_redirected_package`): a redirect is fixed when
    the process starts and cannot change while it lives.

    Two copies of the store and checkpoint, each trusted by the programs
    that see it, is the one thing decision 159's checkpoint cannot survive -
    each copy refuses the other's lines, and a pass on the copy would record
    moves in a store the schedule never reads - so the copy is refused
    before anything reads or writes it."""
    answer = resolve_data_home(environ, windows=windows, home=_home(),
                               program=program_folders(), drive_type=drive_type)
    if windows and not (environ.get(ENV_DATA_HOME) or "").strip():
        package = _redirected_package(Path(environ["LOCALAPPDATA"].strip()))
        if package:
            raise DataHomeRedirected(DATA_HOME_REDIRECTED.format(package=package, product=product_name()))
    return answer


#: This process's one answer to "is %LOCALAPPDATA% redirected?" - the
#: package's name, or None - once asked; ``_UNASKED`` until then.
_UNASKED = object()
_redirect_answer: object = _UNASKED


def _redirected_package(local: Path) -> str | None:
    """:func:`redirect_probe` of ``local``, asked once per process."""
    global _redirect_answer
    if _redirect_answer is _UNASKED:
        _redirect_answer = redirect_probe(local)
    return _redirect_answer


def _make_empty(path: Path) -> None:
    with open(path, "x", encoding="utf-8"):
        pass


def redirect_probe(local: Path, *, make=_make_empty) -> str | None:
    """The package whose copy Windows writes this process's ``local``
    (%LOCALAPPDATA%) into, or None (F7, P193, R1).

    It writes a uniquely named empty file directly in ``local`` with
    ``make``, looks for that name in every
    ``local\\Packages\\*\\LocalCache\\Local``, and removes it from wherever it
    landed, in a ``finally``. A hit is a redirect, named by the package
    folder. ``make`` is injected, as ``drive_type`` is, because a test cannot
    make Windows redirect.

    Rejected: asking Windows for this process's package identity - a
    process started from inside the Claude desktop app has none
    (``GetCurrentPackageFamilyName`` answers 15700) yet is redirected, so
    that question is blind here; comparing the file IDs of the normal path
    and a package copy - blind until a first redirected write has already
    made the copy. A probe that cannot write raises nothing new: the data
    home's own writers say what they cannot do, as they always have. A
    Packages folder it cannot list is ``PACKAGES_UNREADABLE``, a
    SettingsError (:func:`_package_names`): having written its file, the
    probe cannot rule a redirect out, and two stores are the one thing
    decision 159's checkpoint cannot survive, so the data home is refused
    loudly rather than guessed (combined review S2). The file is still
    removed in the ``finally``."""
    name = f"{REDIRECT_PROBE_PREFIX}{os.getpid()}-{secrets.token_hex(8)}"
    probe = Path(local) / name
    landed: list[Path] = []
    try:
        try:
            make(probe)
        except OSError:
            return None
        packages = Path(local) / PACKAGES_DIR_NAME
        for package in _package_names(packages):
            copy = packages.joinpath(package, *REDIRECTED_LOCAL, name)
            if os.path.lexists(copy):
                landed.append(copy)
        return landed[0].parent.parent.parent.name if landed else None
    finally:
        for where in (probe, *landed):
            where.unlink(missing_ok=True)


def _package_names(packages: Path) -> list[str]:
    """The package folders in `packages`, sorted; none when it is absent.

    Any other refusal - access denied, a disk error - is a SettingsError
    with ``PACKAGES_UNREADABLE``, never a raw OSError: the first screen
    says it as one sentence and still shows the rest, and the probe refuses
    the data home with it (combined review S2)."""
    try:
        return sorted(entry.name for entry in os.scandir(packages) if entry.is_dir())
    except (FileNotFoundError, NotADirectoryError):
        return []
    except OSError as exc:
        # At call time, as in the error log's handleError: this module's
        # load-time imports stay layout and fsio.
        from tracker import errors

        raise SettingsError(PACKAGES_UNREADABLE.format(
            folder=packages, error=errors.error_class(exc))) from None


def redirected_copies(environ=None, *, windows: bool | None = None) -> list[Path]:
    """Every stale copy of the data home Windows kept for a package (F7,
    P193, R2): each existing
    ``%LOCALAPPDATA%\\Packages\\*\\LocalCache\\Local\\`` + ``DATA_HOME_NAME``.
    Windows only, read-only, and nothing when there is no Packages folder -
    nor when `ENV_DATA_HOME` names the data home: the app then never uses
    %LOCALAPPDATA%, so a copy of that place is no copy of its data folder,
    and the suite, which always names one, never reads the real machine.

    The first screen names each one (``REDIRECTED_COPY``) and asks a person
    to move it to the Recycle Bin; the app never removes it, because it holds
    client-derived data (decision 186). A Packages folder Windows will not
    list raises SettingsError (``PACKAGES_UNREADABLE``). Not in
    :func:`tracker.runner.left_behind`: that is decision 186's "beside the
    program", and its move would carry the copy into the data home."""
    environ = os.environ if environ is None else environ
    windows = os.name == "nt" if windows is None else windows
    local = (environ.get("LOCALAPPDATA") or "").strip()
    if not windows or not local or (environ.get(ENV_DATA_HOME) or "").strip():
        return []
    packages = Path(local) / PACKAGES_DIR_NAME
    copies = [packages.joinpath(package, *REDIRECTED_LOCAL, DATA_HOME_NAME)
              for package in _package_names(packages)]
    return [copy for copy in copies if os.path.isdir(copy)]


# ------------------------------------------------------- one reading ----

#: The answers held for the one read-only reply under way (P118) or the one
#: household a pass is serving (P207), or None when neither is under way -
#: which is always, outside :func:`one_reading` and :func:`one_household`.
_HELD: dict | None = None
#: Which of the two holds :data:`_HELD`: :data:`HOLD_READING` refuses every
#: write, :data:`HOLD_HOUSEHOLD` lets the pass write its records and the
#: store and refuses only a write to the settings file.
_HOLDING = ""
HOLD_READING = "reading"
HOLD_HOUSEHOLD = "household"
#: The key :func:`_read` holds the settings file's answer under.
_SETTINGS_HELD = ("settings",)
#: Whatever one held answer is (:func:`held`).
T = TypeVar("T")


@contextmanager
def one_reading() -> Iterator[None]:
    """Hold this process's answers to the machine's questions for one
    read-only reply (P118, ``pilot/SPEC-firm-cache.md``): where the data
    folder is (:func:`data_home`), where the program is (:func:`app_dir`,
    :func:`program_folders`), what the settings file says (:func:`_read`)
    and what each path resolves to (:func:`resolved`).

    **Why.** A firm-wide reply asks them thousands of times - every store
    read asks where the store is, and every answer re-proves that the data
    folder is not inside the program by asking the disk - and on the
    office PC a question to the disk costs a tenth of a millisecond: 750
    returns took 53 s, nearly all of it these repeats.

    **Why only here.** A read-only command changes none of the answers - no
    environment variable, no settings file, no folder of its own - so the
    first answer is the answer for the whole reply. A writer, the pass and
    the suite may change them between two questions, and outside a reading
    nothing is held: :func:`data_home` still takes an override at once. An
    error is never held; the question is asked again. Nested readings are
    one reading, and a reading inside a household's hold is part of that
    hold."""
    yield from _holding(HOLD_READING)


@contextmanager
def one_household() -> Iterator[None]:
    """Hold the same answers as :func:`one_reading` for one household of a
    pass (P207, ``pilot/SPEC-scale-1000.md``), while the pass writes.

    **Why.** The pass asks them as often as the firm view did: at 1,000
    households a pass with nothing new to file asked the disk 6.9 million
    times, nearly all of them these repeats, and on the office PC a
    question to the disk costs a tenth of a millisecond.

    **Why it is safe while the pass writes** (the doubt P121 left open).
    The pass changes no environment variable and never writes the settings
    file, and nothing it does moves the program or the data folder, so
    those answers stand for the household. A path is held only once it is
    there (:func:`resolved`): a folder the pass makes later is resolved
    again rather than answered from before it existed. Held for one
    household and dropped after it, so a person's change between two
    households - a settings save, a folder renamed in the app - is seen by
    the next one. A write to the settings file inside it is refused
    (:func:`_write`): every setter writes back what it read, which here is
    the held copy, and would undo a save the app made meanwhile. An error
    is never held. Nested inside a reading or another household's hold, it
    is part of that hold."""
    yield from _holding(HOLD_HOUSEHOLD)


def _holding(kind: str) -> Iterator[None]:
    """The one body of both holds: a fresh :data:`_HELD` of ``kind``, or,
    when a hold is already under way, that hold unchanged - so a nested
    hold is the outer one - and nothing held once the outermost ends,
    whatever ended it."""
    global _HELD, _HOLDING
    if _HELD is not None:
        yield
        return
    _HELD, _HOLDING = {}, kind
    try:
        yield
    finally:
        _HELD, _HOLDING = None, ""


def held(key: tuple, answer: Callable[[], T], *, there: Path | str | None = None) -> T:
    """``answer()``, kept for the hold under way: **the one memo whose life
    is a hold** (pilot P215). Every answer the package keeps for one reply
    or one household is kept here, so what is held, and for how long, is
    worded once.

    - Outside a hold: ``answer()`` every time - nothing is kept.
    - Inside a reading (P118): asked once and kept for the reading, which
      changes nothing.
    - Inside a household's hold (P207): asked once, and kept only when
      ``there`` is None or the folder ``there`` names resolves to an answer
      that is itself held - which, by :func:`resolved`'s rule, means it was
      there when it was resolved. An answer about a folder the pass makes
      later is never kept from before the folder existed.
    - An exception is never kept: the question is asked again.

    ``key`` must name everything the answer depends on, as text - never a
    ``Path``'s equality, which on Windows folds case (P219)."""
    if _HELD is None:
        return answer()
    if key in _HELD:
        return _HELD[key]
    value = answer()
    if there is not None and _HOLDING != HOLD_READING:
        try:
            resolved(there)
        except OSError:
            return value
        if ("resolved", str(Path(there))) not in _HELD:
            return value
    _HELD[key] = value
    return value


#: What a write inside :func:`one_reading` is refused with.
WRITE_WHILE_READING = ("{what} may not be written inside a read-only reply (P118): the reply holds "
                       "its answers, and a write would leave them stale")
#: What a settings write inside :func:`one_household` is refused with.
WRITE_WHILE_HOLDING = ("{what} may not be written while a pass holds a household's answers (P207): "
                       "it would write back the copy read when the household began")


def refuse_a_write_while_reading(what: str) -> None:
    """Raise when a write is asked for inside :func:`one_reading` (the
    review of P118, SHOULD-3): a read-only command writes nothing, and a
    write under held answers would leave the rest of the reply answering
    from before it. The settings file and the store's recorded events ask
    it; the store's own catch-up from a journal is derivation, not a
    write of anything new, and does not. Inside :func:`one_household` the
    pass writes, and nothing is refused."""
    if _HELD is not None and _HOLDING == HOLD_READING:
        raise RuntimeError(WRITE_WHILE_READING.format(what=what))


def resolved(path: Path | str) -> Path:
    """``Path(path).resolve()``, asked once per spelling inside
    :func:`one_reading` (P118) - the store's key for every return is its
    folder resolved, asked on every store read - and every time outside
    one. Inside :func:`one_household` an answer is held only when what it
    names is there (P207): a folder the pass makes later is resolved again,
    because a path resolves differently once it exists (Windows gives the
    folder's own case, a link is followed). An ``OSError`` is raised as
    ``resolve`` raises it, and not held."""
    folder = Path(path)
    key = ("resolved", str(folder))
    if _HELD is not None and key in _HELD:
        return _HELD[key]
    answer = folder.resolve()
    if _HELD is not None and (_HOLDING == HOLD_READING or os.path.lexists(answer)):
        _HELD[key] = answer
    return answer


def default_data_home() -> Path:
    """:func:`data_home` as it would be with no ``ENV_DATA_HOME``: the real
    place on this machine, for a guard that must know it while an override
    is set."""
    environ = {key: value for key, value in os.environ.items() if key != ENV_DATA_HOME}
    return resolve_data_home(environ, windows=os.name == "nt", home=_home(),
                             program=program_folders(), drive_type=drive_type)


def scratch_root() -> Path:
    """The parent of every process's own temp folder, in the data home."""
    return data_home() / SCRATCH_DIR_NAME


def process_scratch() -> Path:
    """This process's own temp folder in the data home: named by its pid, so
    only a folder whose process is gone is ever swept."""
    return scratch_root() / str(os.getpid())


def logs_dir() -> Path:
    """The folder of the tracker's logs, in the data home."""
    return data_home() / LOGS_DIR_NAME


def program_drive_refusal(*, app: Path | None = None, settings: Path | None = None,
                          drive_type=None) -> str:
    """Why the schedule may not run the program from where it is, or "".

    The program's folder and its settings folder are each asked; only
    DRIVE_FIXED passes. DRIVE_REMOVABLE and DRIVE_CDROM -> PROGRAM_ON_REMOVABLE,
    DRIVE_REMOTE -> PROGRAM_ON_NETWORK, anything else (unknown, no root, a RAM
    disk) -> PROGRAM_DRIVE_UNKNOWN: nothing is guessed (decision 186).

    Asked by the schedule's registration (``scheduling.schedule_decision``,
    the first answer of every door of the after-install step, decision 209)
    and by the scheduling command line, and said on the app's first screen -
    never by the scheduled pass, which would only go quiet if it refused: a
    job installed from a stick keeps running until the schedule is
    registered again from the copy on the disk. ``drive_type`` is
    looked up when called, not bound at definition, so a test's patch of
    the module's :func:`drive_type` reaches it. Off Windows every drive is
    fixed and the answer is "".
    """
    ask = drive_type if drive_type is not None else globals()["drive_type"]
    folders = (app if app is not None else app_dir(),
               settings if settings is not None else settings_dir().resolve())
    for folder in folders:
        kind = ask(Path(folder))
        if kind == DRIVE_FIXED:
            continue
        if kind in (DRIVE_REMOVABLE, DRIVE_CDROM):
            return PROGRAM_ON_REMOVABLE.format(folder=folder)
        if kind == DRIVE_REMOTE:
            return PROGRAM_ON_NETWORK.format(folder=folder)
        return PROGRAM_DRIVE_UNKNOWN.format(folder=folder)
    return ""


#: Why a folder is refused as the clients root (decision 137). One sentence
#: per reason, each naming the folder, so a person knows what to choose
#: instead. The walk every two hours, the run log and the status page, and
#: the API's "under the clients root" check all follow the root, so a root
#: that holds the app's own folder would walk it, write into it and accept
#: its files as engagements.
ROOT_IS_SYSTEM_DRIVE = ("{root} is the whole system drive; the app would walk all of it. "
                        "Choose the folder the firm keeps its clients in")
ROOT_HOLDS_SETTINGS = ("{root} holds the app's own settings ({settings}); "
                       "choose the folder the firm keeps its clients in")
ROOT_INSIDE_SETTINGS = ("{root} is inside the app's settings folder ({settings}); "
                        "choose the folder the firm keeps its clients in")
ROOT_HOLDS_APP = ("{root} holds the app itself ({app}); "
                  "choose the folder the firm keeps its clients in")
#: The data home and the clients root never overlap (decision 186).
ROOT_HOLDS_DATA = ("{root} holds the app's own data folder ({data}); "
                   "choose the folder the firm keeps its clients in")
ROOT_INSIDE_DATA = ("{root} is inside the app's own data folder ({data}); "
                    "choose the folder the firm keeps its clients in")
#: A root one level too deep (decision 188, D-3): a folder above it holds
#: both trees, and the root lies inside one of them.
ROOT_INSIDE_A_TREE = "{root} is inside the {tree} folder of the clients root {real}; choose {real}"


def _holding_both_trees(root: Path) -> tuple[Path, str] | None:
    """The nearest folder above ``root`` that holds both trees as folders,
    with the tree ``root`` lies inside - or ``None``.

    Both trees, and not a tree's name alone: the runbook's own example
    root is a folder named ``Clients``, and a spelling would refuse it. A
    folder that holds the two trees is a clients root, and anything inside
    one of them is one level (or more) too deep."""
    for above in root.parents:
        if (layout.clients_tree_of(above).is_dir() and layout.private_tree_of(above).is_dir()
                and (tree := layout.tree_of(above, root)) is not None):
            return above, tree
    return None


def _within(inner: Path, outer: Path) -> bool:
    """Whether ``inner`` is ``outer`` or lies below it, compared as the
    filesystem compares names (without case on Windows)."""
    a = os.path.normcase(os.path.normpath(str(inner)))
    b = os.path.normcase(os.path.normpath(str(outer)))
    if a == b:
        return True
    return a.startswith(b.rstrip(os.sep) + os.sep)


def _inside(inner: Path, outer: Path) -> bool:
    r"""Whether ``inner`` is ``outer`` or lies below it - by its spelling, or
    by **the folder itself** (decision 137's review, F1).

    The spelling alone is a string check, and ``\\?\C:\``,
    ``\\localhost\C$\`` and ``\\127.0.0.1\C$`` are the system drive under
    other names. So where both exist, ``inner`` and every folder above it
    are asked whether they *are* ``outer`` (``os.path.samefile``: the same
    volume and file id), which no spelling changes. A folder that is not
    there has no identity, and only its spelling is compared.
    """
    if _within(inner, outer):
        return True
    if not os.path.exists(outer):
        return False
    for level in (inner, *inner.parents):
        try:
            if os.path.samefile(level, outer):
                return True
        except OSError:
            continue
    return False


def root_refusal(root: Path, *, settings: Path, app: Path, system: Path,
                 data: Path | None = None) -> str:
    """Why ``root`` may not be the clients root, or ``""`` when it may.

    Pure, so every rule is testable on any machine: ``settings`` is the
    folder holding ``SETTINGS_FILENAME``, ``data`` the data home, ``app`` the
    app's own folder, ``system`` the system drive's root. Refused (decision
    137): the system drive's root; the settings folder, any folder that
    holds it, and any folder inside it; the data home, any folder that
    holds it and any folder inside it (decision 186); the app's folder and
    any folder that holds it. **Another drive's root is allowed**: a letter mapped to
    the clients share (``S:``, a Shared Drive letter) is a real root. And
    since decision 188 a folder inside one of the two trees of a real root
    (``ROOT_INSIDE_A_TREE``), which is the one rule here that looks at what
    is on the disk: whether a folder above the root holds both trees.
    """
    if _inside(system, root) and _inside(root, system):
        return ROOT_IS_SYSTEM_DRIVE.format(root=root)
    if _inside(settings, root):
        return ROOT_HOLDS_SETTINGS.format(root=root, settings=settings)
    if _inside(root, settings):
        return ROOT_INSIDE_SETTINGS.format(root=root, settings=settings)
    if data is not None and _inside(data, root):
        return ROOT_HOLDS_DATA.format(root=root, data=data)
    if data is not None and _inside(root, data):
        return ROOT_INSIDE_DATA.format(root=root, data=data)
    if _inside(app, root):
        return ROOT_HOLDS_APP.format(root=root, app=app)
    if (deeper := _holding_both_trees(root)) is not None:
        return ROOT_INSIDE_A_TREE.format(root=root, tree=deeper[1], real=deeper[0])
    return ""


def clients_root_refusal(root: Path | str) -> str:
    """:func:`root_refusal` for ``root`` on this machine, with this app's
    settings folder, its data home, its own folder and the system drive:
    ``""`` when it may be the clients root. What :func:`set_clients_root` asks before it
    records a root, and what the scheduled pass asks again of the root it
    was saved with (decision 137's review, F12), so a root recorded before
    the rule is not walked either."""
    return root_refusal(Path(root), settings=settings_dir().resolve(), app=app_dir(),
                        system=system_drive_root(), data=data_home())


def set_clients_root(root: Path | str) -> Path:
    """Record ``root`` as the clients root. It must already be a folder.

    Creating it here would turn a typo into an empty "clients" folder that
    the run walks for ever and finds nothing in. And it may not be a folder
    that would swallow the app (decision 137, :func:`root_refusal`): the
    system drive's root, the settings folder or anything around or inside
    it, the app's own folder or anything around it. That replaced a check
    against the working folder, which in the packaged build is whatever
    folder the app happened to be started from.
    """
    typed = str(root).strip()
    if not typed:
        # Path("") is the working folder, which is a folder: a cleared box
        # would record the app's own folder and lose the real one.
        raise SettingsError("no folder given")
    root = Path(typed)
    if not root.is_dir():
        raise SettingsError(f"not a folder: {root}")
    if str(root).rstrip("/") == root.drive:       # "D:" is the drive's current folder to Windows
        root = Path(root.drive + os.sep)
    root = root.resolve()   # the scheduled job and the app do not share a working folder
    refusal = clients_root_refusal(root)
    if refusal:
        raise SettingsError(refusal)
    data = _read()
    data[KEY_CLIENTS_ROOT] = str(root)
    _write(data)
    return root


# -------------------------------------------------------------------- CLI ----

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Show or set the clients root")
    parser.add_argument("root", nargs="?", help="the folder the firm keeps its clients in")
    ns = parser.parse_args()
    if ns.root:
        try:
            print(f"clients root: {set_clients_root(ns.root)}  ({settings_path()})")
        except SettingsError as exc:
            raise SystemExit(str(exc)) from None
    else:
        root = clients_root()
        print(f"clients root: {root or '(not set)'}  ({settings_path()})")
