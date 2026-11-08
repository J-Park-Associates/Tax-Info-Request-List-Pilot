"""The package's layers, pinned: no load-time import points to a higher layer.

Why a test and not a paragraph: the structural review of 2026-09-18 found
the layering written down in a plan and broken twice in the tree, because
nothing checked it. A rule nobody runs is a wish. This file is the contract;
the table below is the whole of it, and a module that moves layers moves
here in the same commit, with a decision row saying why.

**What an edge is.** A load-time import is an ``import tracker.x`` or
``from tracker.x import ...`` at module level - anything that runs when the
module loads. An import inside a function, a class body or the module's
``if __name__ == "__main__":`` block is a call-time import: it runs when
called, so it can point anywhere, and the map labels it separately. The
scanner never imports the filer: a person's actions (``actions``) reach it
at call time, inside ``_rescan()``. Four two-module cycles remain, each
closing at call time, and :data:`CALL_TIME_CYCLES` names them.

**The layers.** In-layer edges are allowed (``ledger`` and ``manifest``
are both L1, so ``manifest`` reaching ``ledger`` is legal - and wanted,
because decision 104 put the request list's two writes beside its
schema). What is never allowed is an edge from a lower layer to a higher one.
``settings`` sat at L1 only because it borrowed the atomic write from
``manifest``; decision 120 moved that write to ``fsio`` at L0, which takes
``settings`` down with it - it imports ``fsio`` and nothing else of the
package. ``validators`` sits at L1 because ``scaffold`` reads one
helper from it (the placeholder examples the README prints), and its pure
half is not worth a module of its own until that call can move.

**No mail, no network, in code** (decision 115). The fourth standing rule
says nothing is ever sent, and until 115 the only pin was the words "never
sends" in a test. ``FORBIDDEN_MODULES`` names the standard library's mail
and network modules and the one third-party client anyone reaches for, and
the AST walk below finds none of them imported anywhere under ``tracker/``
- at load time or inside a function, plainly or as ``from x.y import``.
``subprocess`` is not on the list: the build and the scheduler use it.
Nor is ``multiprocessing``: since decision 150 the pass reads each
document in a child process, and the two talk over ``multiprocessing``'s
``Pipe`` - a named pipe on Windows, an OS pipe elsewhere. Its connection
module reaches ``socket`` for listeners and clients the package never
makes, and the test below holds it to the pipe.

**Rule 7, amended** (from the implementation plan's rules for every step):
``ledger`` and ``locking`` import nothing of the package but each other,
and ``checkpoint`` (decision 159) imports nothing of the package at all;
``manifest`` imports ``bounds`` and ``records`` and nothing else at load
time, and reaches ``store``, ``ledger`` and ``locking`` at call time;
``runner`` never imports ``scheduling`` or ``api``; the package's
``__init__`` imports nothing at load time (decision 99 removed thirteen
re-exports no file consumed, and with them the one load-time cycle the map
used to name).

The manifest's rule got *narrower* with decision 103 and kept that width
with 104, which is worth saying: it used to import ``ledger`` and
``locking`` at load time because it wrote the scanner columns. Decision
104 gave it the request list's writes - ``create_engagement()`` and
``save_rules()`` record a ``rules_changed`` event under the engagement
lock - and they reach ``store``, ``ledger`` and ``locking`` at call time,
as ``load_manifest()`` already did: in-layer edges, closed where an edge
is allowed to close.

``manifest`` -> ``records`` is the in-layer edge decision 100 added: the
record types moved out of the modules that write them, ``records`` imports
nothing of the package at all, and the manifest names the shapes it loads.

``layout`` joins L0 with decision 125: the shape of the clients root -
the two trees, the household, the year, the return - and the one way a
stored path is written and read back. It imports nothing of the package
and reads no file, so every layer above may ask where a thing belongs
without reaching for the module that puts it there. ``households`` joins
L1 beside ``manifest``, which it is the counterpart of - the manifest owns
a return's list and details, this owns the household's - and it reaches
``store``, ``ledger`` and ``locking`` at call time for exactly the reason
the manifest does. ``ledger`` does not import ``layout``: it holds no path
arithmetic. ``records`` may, since decision 188: the Windows character and
device rule moved down into the layout's one name rule, and the record
imports that rule and nothing else of it (the layout reads no file) -
except ``quoted``, which it imports only to re-export to ``manifest``, so a
refusal quotes at most 80 characters (P293) and ``manifest`` still loads
``records`` and nothing else of the package.

``names`` joins L2 with decision 128, beside ``router``: it is the matcher
for the name on a page - normalising, whole-phrase containment, the
spellings the app proposes and the three-way verdict - and it imports
``records`` for the one way a name is cut into words and for the one
page-break character (``PAGE_BREAK``, records' since SPEC-architecture
P2.8), and nothing else of the package. Like the router it decides nothing
about a folder: the check itself runs one layer up, in the filer's household
pass, where the returns and their people lists are.

``store`` joins L1 with decision 101 and is deliberately narrower than its
layer allows: it imports ``admission`` (P323), ``bounds`` (P321),
``records``, ``ledger``, ``locking`` and (since decision 159)
``checkpoint``, and nothing else of the package, not even the in-layer
``manifest``.
Everything it holds comes out of the journal, so the database that answers
for the readers never depends on the modules that walk folders and move
files; its command line imports the registry, and the check and the export
(P324), at call time, which is where a cycle is allowed to close.

**The domains** (decision P314). A layer says what a module may import; a
domain says what the module is for. There are six: ``record`` (the household's
journal, its request list, the bounds its values are held to and the shape of
the clients root), ``reading`` (opening a client's file and getting the text
out of it), ``sorting`` (deciding where a document belongs), ``pass`` (the
scheduled run and what it drives), ``door`` (the API, the engine that answers
it, what an error is called, where its words are kept and the shape of every
reply) and ``shell`` (the pages a person opens).
A domain is the grouping a folder tree would show, checked here instead: the
modules stay flat in ``tracker/``, because a subpackage would escape every
guard that reads only ``tracker/*.py`` and change every import path, and the
layer table already says what may lean on what. So :data:`DOMAINS` sits beside
:data:`LAYERS`, and ``test_every_module_sits_in_exactly_one_domain`` fails
when a module has no domain, has two, or is named in a domain and not in a
layer. A domain is documentation that is checked: it forbids nothing the
layers allow, and no import is refused for crossing one. Each later job that
adds a module adds it to both tables. The `door` domain is the API's door;
`tracker/door.py` is the record's.

**An allow-list, not only a denylist** (decision 190). The denylist above
names what anyone would think of; a module it does not name would arrive
quietly. So every top-level name imported anywhere under ``tracker/`` must
be in :data:`ALLOWED_STDLIB` or :data:`ALLOWED_THIRD_PARTY`, and a new one
fails the suite until a person adds it here with its reason. The
third-party set is classified, because the first standing rule is about
what may read a client's document: readers, and optical character
recognition. The OCR engine runs models - deterministic models of letter
shapes, which turn a page image into the characters on it and generate
nothing (decision 169) - and it is named as OCR so that nobody reads "a
model" as "generative AI". A named set of generative-AI packages is checked
against the imports and against every requirements file and every lock
file decision 191 installs from (read, never installed), each allowed
third-party import is one a lock file pins, an import made by string
(``importlib``, ``__import__``) is forbidden so the allow-list cannot be
walked around, and the desktop app's scripts are scanned for any network
call - the renderer's policy already refuses one, and the scan pins it.
The denylist stays: it says the rule in the words a reader looks for.
"""

from __future__ import annotations

import ast
from pathlib import Path

from tests.import_graph import PACKAGE, _modules, import_edges
from tests.node_harness import RENDERER, RENDERER_SCRIPTS

REPO = Path(__file__).resolve().parents[1]


#: Layer -> the modules in it. Every file in tracker/ is in exactly one.
LAYERS: dict[int, frozenset[str]] = {
    # ``door`` joins L0 with decision 188: the disk half of the layout. It
    # imports ``layout``, ``fsio`` and ``settings``, all L0, so L0 is the
    # lowest layer the table allows it - and every layer above may ask it.
    # ``progress`` joins L0 with decision 193: the one progress-line format
    # and the cancel marker, stdlib only, so the filer, the scanner and the
    # runner can take a Watch without reaching up to ``api``.
    # ``firm_cache`` joins L0 with P120: the firm view's cache file, its head
    # and the households' fingerprints - the standard library, ``settings``,
    # ``fsio`` and ``errors``; the API does the reading and decides what is kept.
    # ``page_rows`` joins L0 with P227: the practice page's kept rows - the
    # standard library, ``settings``, ``fsio``, ``errors`` and ``firm_cache``'s
    # head; the status page reads the records and asks the store for the tokens.
    # ``firm_pages`` joins L0 with P278: a firm reply cut into one page, and
    # the view file - the standard library, ``settings``, ``fsio``, ``errors``,
    # ``layout`` (the return naming pattern) and ``firm_cache``'s head and file
    # readers; the API hands it the words.
    # ``replies`` joins L0 with SPEC-architecture-p2 R2.3.1: the shape of every
    # reply the API prints, as ``TypedDict``s - ``typing`` only; the API and the
    # suite import it.
    # ``bounds`` joins L0 with P316 (SPEC-architecture-p2 P2.4): the value rule's
    # bounds out of ``records``, which imports them back - the standard library
    # and ``layout``'s name rule, which reads no file.
    # ``hold`` joins L0 with P317 (SPEC-architecture-p2 P2.6): the per-reply memo
    # out of ``settings``, which reads it through the module - the standard
    # library only.
    # ``errlog`` joins L0 with P318 (SPEC-architecture-p2 P2.7): the rotating
    # error log out of ``settings``, which no longer imports the store - the
    # standard library and ``settings``' ``SettingsError``; the store and
    # ``errors`` only at call time. Nothing in ``settings`` offers it.
    0: frozenset({"__init__", "reasons", "locking", "checkpoint", "page", "fsio", "settings",
                  "layout", "door", "errors", "progress", "firm_cache", "page_rows", "firm_pages",
                  "replies", "bounds", "hold", "errlog"}),
    # ``index`` joins L1 with P319 (SPEC-architecture-p2 P2.9): the index's
    # words and readers out of ``filer``, which imports them back - ``ledger``,
    # ``records``, ``store`` and ``validators`` (L1) and ``layout`` and
    # ``reasons`` (L0); it reads the index and sorts nothing.
    # ``admission`` joins L1 with P323 (SPEC-architecture-p3 P3.2): the one rule
    # a line of the record meets, out of ``store``, which imports it back -
    # ``bounds`` (L0), ``ledger`` and ``records`` (L1); ``layout`` and
    # ``reasons`` at call time.
    # ``store_check`` joins L1 with P324 (SPEC-architecture-p3 P3.4): the gate
    # and the export out of ``store`` - ``admission``, ``ledger``, ``records``
    # and ``store`` (L1), ``locking`` (L0); ``fsio`` at call time; the store's
    # command line asks it at call time.
    # ``screen_words`` joins L1 with P340 (SPEC-architecture-p5 P5.3): the words
    # the API sends the screen, out of ``api``, which imports them back -
    # ``manifest`` and ``records`` (L1), ``errlog`` and ``settings`` (L0); nothing
    # the runner loads may import it (``SCREEN`` reads the product's name at
    # import).
    1: frozenset({"households", "ledger", "manifest", "records", "scaffold", "store",
                  "templates", "validators", "index", "admission", "store_check",
                  "screen_words"}),
    # ``copies`` joins L2 with P331 (SPEC-architecture-p4 P4.4): the filer's
    # naming, room, byte-proved copy and rename-only move, the client README's
    # lock and the stranded-temp sweep - L1 and L0, and ``containers`` and
    # ``verdicts``' ``ContentCache`` in-layer; the filer and a person's
    # actions import it.
    # ``keywords`` joins L2 with P336 (SPEC-architecture-p4 P4.10): the matcher
    # and the rules out of ``content_check``, which imports them back -
    # ``manifest`` and ``records`` (L1) and ``reasons`` (L0); nothing at L2 or
    # above. It sits at L2 beside the one reading it judges for.
    # ``verdicts`` joins L2 with P337 (SPEC-architecture-p4 P4.11): the
    # judgment's shapes and decision 107's verdict cache out of
    # ``content_check``, which imports them back - ``keywords`` (L2, the rules'
    # verdict), ``store``, ``validators``, ``records`` and ``manifest`` (L1)
    # and ``hold`` (L0).
    # ``reader_child`` joins L2 with P338 (SPEC-architecture-p4 P4.12): the
    # reading's child, its supervisor and the pass's session out of ``ocr``,
    # which it imports (in-layer); ``content_check`` imports it, and
    # ``errors``, ``locking`` and ``settings`` are below it.
    2: frozenset({"containers", "content_check", "copies", "keywords", "names", "ocr", "router",
                  "verdicts", "reader_child"}),
    # ``verify`` joins L3 with P325 (SPEC-architecture-p3 P3.5): decision 159's
    # read-only firm-wide proof out of ``store`` - ``admission``, ``ledger``,
    # ``records`` and ``store`` (L1) and ``checkpoint`` (L0) at load time, and
    # ``registry`` (L3), ``index`` and ``validators`` (L1) and ``layout`` (L0)
    # at call time. Its place is set by the registry it asks, not by what it
    # loads; the store's command line asks it at call time.
    # ``intents`` joins L3 with P332 (SPEC-architecture-p4 P4.6): decision
    # 119's write-ahead intents and finishing an interrupted move, out of
    # ``filer`` - ``copies`` and ``verdicts``' ``ContentCache`` (L2), and
    # L1 and L0; the filer and a person's actions import it. It imports
    # nothing above L2, and sits at L3 beside the two it serves.
    # ``inbox`` joins L3 with P333 (SPEC-architecture-p4 P4.7): the inbox's
    # walk and the drops that cannot be read, listed or tied to a row, out of
    # ``filer`` - ``copies`` (L2) and L1 and L0; the filer imports it, and
    # the reminder at call time. It imports nothing above L2, and sits at L3
    # beside the two it serves.
    # ``readme_ack`` joins L3 with P334 (SPEC-architecture-p4 P4.8): decision
    # 130's received list and the README's refresh, out of ``filer`` -
    # ``copies`` (L2) and L1 and L0; the pass (``runner``), the API and a
    # person's actions import it, and the rollover at call time. It imports
    # nothing above L2, and sits at L3 beside the filer and the rollover that
    # read it.
    # ``actions`` joins L3 with P335 (SPEC-architecture-p4 P4.9): a person's
    # actions on the record and the rescan after them, out of ``filer`` -
    # ``filer`` (in-layer, the hand-over's shared pieces), ``intents``,
    # ``inbox``, ``readme_ack``, ``copies`` and L1 and L0 at load, ``scanner``
    # at call time; the API and ``request_edit`` import it.
    # ``request_edit`` joins L3 with P341 (SPEC-architecture-p5 P5.4): the editor's
    # save rules and the spec's details, out of ``api``, which imports them back -
    # ``actions`` (in-layer, the documents a request holds), ``copies`` (L2, the
    # room), ``screen_words``, ``manifest``, ``records``, ``bounds`` and ``settings``
    # (L1 and L0).
    # ``household_edit`` joins L3 with P342 (SPEC-architecture-p5 P5.5): a
    # household's members, feeds and related households and P170's mirror, out
    # of ``api``, which imports them back - ``registry`` (in-layer),
    # ``households``, ``manifest``, ``records`` and ``screen_words`` (L1),
    # ``locking`` and ``layout`` (L0).
    # ``creation`` joins L3 with P343 (SPEC-architecture-p5 P5.6): the create
    # transaction's folder, its refusals and decision 137's undo, out of ``api``,
    # which imports them back - ``household_edit`` (in-layer), ``copies`` (L2),
    # ``households``, ``ledger``, ``manifest``, ``store`` and ``screen_words``
    # (L1), ``errors`` and ``layout`` (L0).
    # ``run_log`` joins L3 with P345 (SPEC-architecture-p5 P5.8): the pass's
    # report, its codes, the run log and the last-pass file, out of ``runner``,
    # which imports them back - ``registry`` and ``reminder`` (in-layer),
    # ``ocr`` (L2), ``store``, ``records``, ``ledger`` (L1), ``checkpoint`` and
    # L0; never ``scheduling`` or ``api``.
    # ``status_page`` joins L3 with P346 (SPEC-architecture-p5 P5.9): the
    # practice status page, out of ``runner`` - ``run_log``, ``registry`` and
    # ``reminder`` (in-layer), ``store``, ``index``, ``manifest`` (L1) and
    # ``page``, ``page_rows``, ``hold`` (L0); never ``scheduling`` or ``api``.
    3: frozenset({"filer", "scanner", "reminder", "rollover", "view", "registry", "review",
                  "verify", "intents", "inbox", "readme_ack", "actions", "request_edit",
                  "household_edit", "creation", "run_log", "status_page"}),
    # ``after_install`` joins L4 with decision 209, beside the scheduler it
    # drives: it imports ``scheduling`` (L4), ``store`` (L1), ``registry``
    # (L3) and L0; the API imports it, and nothing lower may.
    # ``firm_view`` joins L4 with P344 (SPEC-architecture-p5 P5.7): the
    # Overview's rows, their cache and the group rule, out of ``api``, which
    # imports them back - ``runner`` (in-layer, the draft-day rule),
    # ``reminder``, ``review``, ``registry``, ``run_log`` (``why_skipped``,
    # since P345) and ``view`` (L3), ``containers`` (L2), L1 and L0; never
    # ``screen_words``.
    4: frozenset({"runner", "scheduling", "after_install", "firm_view"}),
    # ``resident`` joins L5 with P276: the engine's loop over ``api.main``; it
    # imports ``api``, ``errlog``, ``locking``, ``reader_child`` and the
    # standard library; nothing imports it but ``api_entry.py``, at call time.
    5: frozenset({"api", "resident"}),
}
LAYER_OF: dict[str, int] = {module: layer for layer, modules in LAYERS.items() for module in modules}

#: Domain -> the modules in it (decision P314). A layer says what a module may
#: import; a domain says what the module is for, the grouping a folder tree
#: would show. It forbids nothing the layers allow: no import is refused for
#: crossing a domain. Every file in tracker/ is in exactly one, and a module
#: that is added is added here and in :data:`LAYERS` in the same commit.
DOMAINS: dict[str, frozenset[str]] = {
    # The household's record: the journal and its lock, the request list and
    # the catalog it is built from, the bounds its values are held to, the
    # index its rows are read as, and the shape of the clients root.
    # ``door`` here is ``tracker/door.py``, the module that knows which
    # household a path is in (decision 188); it is not the API's door, which
    # is the ``door`` domain below.
    "record": frozenset({"__init__", "ledger", "locking", "checkpoint", "fsio", "layout", "door",
                         "settings", "hold", "records", "bounds", "store", "index", "manifest",
                         "households", "templates", "scaffold", "admission", "store_check",
                         "verify", "request_edit", "household_edit", "creation"}),
    # Opening a client's file, checking it and getting the text out of it.
    "reading": frozenset({"validators", "containers", "content_check", "ocr", "verdicts",
                          "reader_child"}),
    # Deciding where a document belongs, or that it belongs nowhere yet, and
    # the shortlist a person gets for the ones that do not.
    "sorting": frozenset({"reasons", "router", "names", "filer", "copies", "intents", "inbox",
                          "readme_ack", "actions", "keywords", "scanner", "review"}),
    # The scheduled run and what it drives: the engagements it finds, the
    # year it rolls over, the reminder it drafts, what it reports and how it
    # is watched.
    "pass": frozenset({"progress", "registry", "rollover", "reminder", "runner", "scheduling",
                       "after_install", "run_log"}),
    # The one way the app reaches the rest, the engine that answers it, what
    # an error is called, where its words are kept, the words it sends the
    # screen and the shape of every reply it prints.
    "door": frozenset({"errors", "errlog", "api", "resident", "replies", "screen_words"}),
    # What a person opens: the pages, their kept rows and the firm's view.
    "shell": frozenset({"page", "page_rows", "firm_cache", "firm_pages", "view", "firm_view",
                        "status_page"}),
}

#: Load-time edges that may point upward. None today; an entry here is a
#: debt with a decision row behind it, removed by the step that pays it.
ALLOWED_UPWARD: frozenset[tuple[str, str]] = frozenset()

#: What "nothing is ever sent" forbids any module under tracker/ to import,
#: at any depth: a name here, or any ``name.sub`` under it.
FORBIDDEN_MODULES: tuple[str, ...] = (
    "smtplib", "email", "imaplib", "poplib", "ftplib", "urllib", "http", "socket", "ssl",
    "requests",
)

#: The one exception to :data:`FORBIDDEN_MODULES`, by module and by name
#: (decision 143): ``tracker/containers.py`` opens a client's ``.eml``, and
#: the standard library's ``email`` package is its parser - the message is
#: read from bytes already on disk, no address is parsed, nothing is
#: composed and nothing is sent. Only the parsing names, and only there:
#: ``smtplib``, ``imaplib`` and the rest stay forbidden everywhere, this
#: module included, and ``email`` stays forbidden in every other module.
MAIL_PARSING_ALLOWED: dict[str, frozenset[str]] = {
    "containers": frozenset({"email", "email.message", "email.policy"}),
}

#: The readers, imported inside the functions that need them
#: (``content_check`` and ``ocr`` for the reading, ``validators`` for the
#: HEIC opener) and named here so the test below can say what they drag in.
#: Decision 127 pinned four; decision 169 took Tesseract's wrapper out and
#: put RapidOCR (``rapidocr.main`` is what building its engine imports)
#: and ONNX Runtime in.
READER_MODULES: tuple[str, ...] = ("PIL.Image", "pillow_heif", "pypdfium2", "onnxruntime",
                                   "rapidocr.main")

#: The forbidden names the readers reach on the way in, which the package
#: itself may still never import. ``pypdfium2`` and ONNX Runtime reach
#: ``socket`` through the standard library. RapidOCR imports ``requests``
#: at load time for the model downloader it carries (decision 169), and
#: with it what ``requests`` imports - ``urllib``, ``http``, ``ssl``,
#: ``email`` (its header parsing) and ``socket``. None of it opens
#: anything: every model is named by path, ``tracker.ocr`` replaces the
#: downloader with a refusal, and tests/test_ocr.py reads a whole page with
#: ``socket.socket`` made to raise. Naming them is the point - a reader
#: that reached for a mail client (``smtplib``, ``imaplib``, ``poplib``)
#: or ``ftplib`` would fail the test below rather than arrive quietly in a
#: build.
READER_IMPORTS_ALLOWED: frozenset[str] = frozenset(
    {"socket", "urllib", "requests", "http", "ssl", "email"})


#: Every standard-library module the package may import, by top-level name
#: (decision 190). ``email`` is here for :data:`MAIL_PARSING_ALLOWED` alone -
#: the denylist still forbids it everywhere else. ``errno``, ``logging`` and
#: ``traceback`` are what the error module is built on, and ``builtins`` is
#: where its command line looks up the built-in exception it is named.
#: ``math`` is decision 187's value rule in ``records`` (a number the record
#: holds must be finite). ``functools`` is decision 204's ``cache`` in
#: ``api``: the feed list read once for a state, and only if a row waits.
#: Named when 190 landed on main 63aef39: ``types`` is decision 192's
#: ``SimpleNamespace`` in ``api`` (a registry of the stored households),
#: ``typing`` the ``TYPE_CHECKING`` guard in ``containers``, ``tempfile`` decision 186's
#: reading child pointing its temp folder at its own scratch in ``reader_child``,
#: and ``fnmatch`` the checkpoint set-asides ``runner`` finds left behind
#: beside the program (decision 186). ``fcntl`` is POSIX's ``flock`` in
#: ``locking`` and a Mac's ``F_FULLFSYNC`` in the two copies of ``full_sync``
#: (``fsio`` and ``locking``; SPEC-mac R19 and R22), imported at call time.
#: ``plistlib`` is the Mac's launchd agent in ``scheduling``: the property list
#: is rendered with the standard library's own writer, never by hand (SPEC-mac
#: R23); it loads no network module.
ALLOWED_STDLIB: frozenset[str] = frozenset({
    "__future__", "argparse", "base64", "builtins", "collections", "contextlib", "csv", "ctypes",
    "dataclasses", "datetime", "email", "errno", "fcntl", "fnmatch", "functools", "hashlib", "html", "io",
    "json", "logging", "math",
    "multiprocessing", "ntpath", "os", "pathlib", "platform", "plistlib", "posixpath", "re", "secrets",
    "shutil", "signal", "sqlite3", "stat", "subprocess", "sys", "tempfile", "threading", "time",
    "traceback", "types", "typing", "unicodedata", "xml", "zipfile", "zlib",
})

#: Every third-party module the package may import, by what it is for.
#: Readers turn a file's bytes into its text, tables or pixels, by rule.
#: Optical character recognition turns a page's pixels into its letters:
#: RapidOCR and the ONNX Runtime it runs on, with NumPy for the arrays. Its
#: models are deterministic models of letter shapes - the same page gives
#: the same text - and they generate nothing (decision 169), which is why
#: they are named here as OCR and not left to be mistaken for generative AI.
#: OpenCV (``cv2``) is there for page clean-up arithmetic on pixels (P283,
#: ``ocr.delined``): deterministic, generating nothing - the same library
#: RapidOCR itself imports.
ALLOWED_THIRD_PARTY: dict[str, frozenset[str]] = {
    "readers": frozenset({"pypdf", "pdfplumber", "pypdfium2", "openpyxl", "olefile", "PIL",
                          "pillow_heif"}),
    "optical character recognition": frozenset({"rapidocr", "onnxruntime", "numpy", "cv2"}),
}

#: Generative-AI packages, by import name and by distribution name, that no
#: module may import and no requirements file may name (decision 190). A
#: name ending in ``*`` is a family.
GENERATIVE_AI_IMPORTS: tuple[str, ...] = (
    "anthropic", "openai", "google.generativeai", "google.genai", "transformers", "torch",
    "tensorflow", "langchain*", "llama_cpp", "ollama", "mistralai", "cohere", "huggingface_hub",
    "sentence_transformers",
)
GENERATIVE_AI_DISTRIBUTIONS: tuple[str, ...] = (
    "anthropic", "openai", "google-generativeai", "google-genai", "transformers", "torch",
    "tensorflow", "langchain*", "llama-cpp-python", "ollama", "mistralai", "cohere",
    "huggingface-hub", "sentence-transformers",
)

#: What the desktop app's own scripts may never do: open a connection of
#: their own, fetch, load a page from anywhere but its own files, or hand a
#: link to the system browser (decision 190). A tripwire over the source's
#: text, not a proof: it names the shapes a network call takes, and a
#: ``require`` it cannot read - a template, a sum, a variable - is refused
#: for being unreadable, so the shapes cannot be spelled around it.
_NETWORK_MODULE = r"(?:node:)?(?:net|http|https|http2|tls|dgram)"
APP_NETWORK_CALLS: dict[str, str] = {
    "a network module": rf"""\brequire\s*\(\s*["'`]{_NETWORK_MODULE}["'`]\s*\)""",
    "a network module imported": rf"""\bfrom\s*["'`]{_NETWORK_MODULE}["'`]""",
    "a require of anything but a plain string": r"""\brequire\s*\(\s*(?!["'][^"'`\n]*["']\s*\))""",
    "a dynamic import": r"\bimport\s*\(",
    "electron's net": r"\bnet\s*\.\s*(?:request|fetch)\b|\{[^}]*\bnet\b[^}]*\}\s*=\s*require\b",
    "loadURL of anything but a file": r"""\.loadURL\s*\(\s*(?!["'`]file:)""",
    "fetch": r"\bfetch\s*\(",
    "XMLHttpRequest": r"\bXMLHttpRequest\b",
    "WebSocket": r"\bWebSocket\b",
    "EventSource": r"\bEventSource\b",
    "sendBeacon": r"\bsendBeacon\b",
    "window.open": r"\bwindow\s*\.\s*open\s*\(",
    "openExternal": r"\bopenExternal\b",
}


def test_every_module_is_in_exactly_one_layer():
    modules = _modules()
    listed = [module for layer in LAYERS.values() for module in layer]
    assert sorted(listed) == sorted(set(listed)), "a module is named in two layers"
    assert set(listed) == modules, set(listed) ^ modules


def test_every_module_sits_in_exactly_one_domain():
    assert set(DOMAINS) == {"record", "reading", "sorting", "pass", "door", "shell"}
    listed = [module for members in DOMAINS.values() for module in members]
    twice = sorted({module for module in listed if listed.count(module) > 1})
    assert not twice, f"in two domains: {twice}"
    assert set(listed) == set(LAYER_OF), {
        "in a domain with no layer": sorted(set(listed) - set(LAYER_OF)),
        "in a layer with no domain": sorted(set(LAYER_OF) - set(listed)),
    }


def test_no_load_time_import_points_to_a_higher_layer():
    load, _ = import_edges()
    upward = sorted(
        (module, target)
        for module, targets in load.items()
        for target in targets
        if LAYER_OF[target] > LAYER_OF[module] and (module, target) not in ALLOWED_UPWARD
    )
    assert not upward, [f"{m} (L{LAYER_OF[m]}) imports {t} (L{LAYER_OF[t]}) at load time" for m, t in upward]


def test_every_allowed_upward_edge_is_still_needed():
    """An allowance that nothing uses is a hole in the contract."""
    load, _ = import_edges()
    stale = [edge for edge in ALLOWED_UPWARD if edge[1] not in load.get(edge[0], set())]
    assert not stale, stale


def test_the_bottom_two_import_nothing_of_the_package_but_each_other():
    load, _ = import_edges()
    assert load["locking"] == set(), load["locking"]
    assert load["ledger"] <= {"locking"}, load["ledger"]


def test_the_checkpoint_imports_nothing_of_the_package():
    """Decision 159: the record checkpoint sits at the bottom beside the
    journal and the lock, and is handed keys, counts, heads and hosts - so
    it imports nothing of the package; its command line alone reaches the
    console guard every command line that prints a client's name uses, and
    the door (decision 188) for the root a person types."""
    load, call = import_edges()
    assert load["checkpoint"] == set(), load["checkpoint"]
    assert call.get("checkpoint", set()) <= {"page", "door"}, call["checkpoint"]


def test_the_store_imports_only_the_admission_the_bounds_the_record_the_journal_the_lock_and_the_checkpoint():
    """Decision 101: narrower than its layer, on purpose - the store must
    not depend on what opens a workbook, or it cannot replace it. Decision
    159 adds the checkpoint, which is below it and imports nothing. P321
    adds the bounds, which are L0 and read no file. P323 adds the admission,
    which is L1 and imports only the bounds, the journal and the record."""
    load, _ = import_edges()
    assert load["store"] == {"admission", "bounds", "checkpoint", "ledger", "locking", "records"}, load["store"]


def test_the_admission_imports_the_bounds_the_journal_and_the_record():
    """P323: the one rule a line of the record meets reads the journal's
    words, the record's shapes and the bounds at load time, and the layout's
    place rules and the reasons' codes at call time, as it did in the
    store - so the store can import it at load time and no cycle closes."""
    load, call = import_edges()
    assert load["admission"] == {"bounds", "ledger", "records"}, load["admission"]
    assert call["admission"] == {"layout", "reasons"}, call["admission"]


def test_the_check_imports_the_store_and_the_record_and_writes_through_fsio_alone():
    """P324: the gate and the export read the store, the admission, the
    journal and the record (L1) and the lock (L0, whose ``full_sync`` the
    export's write calls) at load time, and reach ``fsio`` at call time for
    the one file they write that is not the database. The store does not
    import the check at load time; its command line asks it at call time."""
    load, call = import_edges()
    assert load["store_check"] == {"admission", "ledger", "locking", "records", "store"}, load["store_check"]
    assert call["store_check"] == {"fsio"}, call["store_check"]


def test_verify_reads_the_walk_and_the_proof_at_call_time():
    """P325: the read-only firm-wide proof loads only what the store's
    judgment of a record needs - the store, the admission, the journal and
    the record (L1) and the checkpoint (L0) - and asks the registry's walk,
    the index's proof of a row's bytes, the layout and the validators'
    placeholder test at call time, when a person runs it. It sits at L3 for
    the registry it asks; the store's command line asks it at call time."""
    load, call = import_edges()
    assert load["verify"] == {"admission", "checkpoint", "ledger", "records", "store"}, load["verify"]
    assert call["verify"] == {"index", "layout", "registry", "validators"}, call["verify"]


#: The modules that compose a record event - a call of ``ledger.new`` - by
#: name: the modules whose decisions the record holds, each writing its own
#: family. The door asks them and never composes an event itself (B-4,
#: P327); a new composer is a decision. ``intents`` joined with P332: the
#: intent (``ledger.MOVING``), the abandon (``ledger.MOVE_ABANDONED``) and the
#: finish of an interrupted move compose the record's events, and moved out
#: of the filer with the code that writes them. ``actions`` joined with P335:
#: a filing's issuer row and taught keyword and a rename's intents are
#: composed by a person's actions, which left the filer with them; the filer
#: stays, for the spelling a filing teaches and the hand-over.
COMPOSERS: frozenset[str] = frozenset({"actions", "filer", "households", "intents", "manifest",
                                       "reminder", "scanner"})


def _composers() -> set[str]:
    """Every module under tracker/ that calls ``ledger.new`` - the attribute
    ``new`` on the name the journal module is bound to - or a bare ``new``
    from-imported from ``tracker.ledger``, anywhere in it: at load time, in
    a function or in its ``__main__`` block."""
    found: set[str] = set()
    for path in sorted(PACKAGE.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        module, bare = {"ledger"}, set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "tracker":
                module |= {alias.asname for alias in node.names if alias.name == "ledger" and alias.asname}
            elif isinstance(node, ast.ImportFrom) and node.module == "tracker.ledger":
                bare |= {alias.asname or alias.name for alias in node.names if alias.name == "new"}
            elif isinstance(node, ast.Import):
                module |= {alias.asname for alias in node.names if alias.name == "tracker.ledger" and alias.asname}
        for node in ast.walk(tree):
            func = node.func if isinstance(node, ast.Call) else None
            if (isinstance(func, ast.Attribute) and func.attr == "new"
                    and isinstance(func.value, ast.Name) and func.value.id in module) or (
                    isinstance(func, ast.Name) and func.id in bare):
                found.add(path.stem)
    return found


def test_only_the_domain_writers_compose_a_record_event():
    """B-4, one door into the record (P327, SPEC-architecture-p3 R3.7.5): a
    line of the record is composed by the module whose decision it records -
    the filer's filings, the scanner's statuses, the manifest's list, the
    household's own record, the reminder's approved draft - and the door
    (the API, the engine, the error words, the replies) asks one of them
    and never composes an event itself, so what a line carries is decided
    in one place. The walk must find the filer, or it found nothing."""
    found = _composers()
    assert "filer" in found, "the walk must find the filer's events"
    assert found == COMPOSERS, sorted(found ^ COMPOSERS)
    assert not COMPOSERS & DOMAINS["door"], sorted(COMPOSERS & DOMAINS["door"])


def test_the_manifest_imports_the_bounds_and_the_record_and_nothing_else():
    """Narrower since decision 103, and kept so by 104.

    The manifest used to append to the journal and take the engagement
    lock at load time, because it wrote the scanner columns. Decision 104
    gave it the request list's writes, and they reach the store, the
    journal and the lock at call time - where an in-layer edge is allowed
    to close - so at load time it names the shapes it validates into and
    the bounds it holds them to (P321), and nothing else.
    """
    load, call = import_edges()
    assert load["manifest"] == {"bounds", "records"}, load["manifest"]
    assert {"store", "ledger", "locking"} <= call["manifest"], call["manifest"]


def test_the_settings_import_only_the_atomic_write_the_layout_and_the_hold():
    """Decision 120: the one import that held it a layer up is gone.

    ``settings`` borrowed ``write_json_atomically`` from ``manifest``, and
    that single name was the whole of its dependence on L1. The write is
    ``fsio`` now, so the settings file - which the app, the scheduler and
    every command line read before anything else - is written by a module
    that knows nothing of request lists. Decision 188 adds ``layout``, at
    the same layer and reading no file: a root one level too deep is one
    that lies inside a tree of a real root, and the trees are the layout's.
    P317 (SPEC-architecture-p2 P2.6) adds ``hold``, at the same layer and
    importing nothing of the package: the per-reply memo moved out, and the
    settings read it through the module, because a copy of ``_HELD`` taken
    at import would never see a hold begin.
    """
    load, _ = import_edges()
    assert load["settings"] == {"fsio", "hold", "layout"}, load["settings"]


def test_the_door_imports_only_the_layout_the_atomic_write_and_the_settings():
    """Decision 188: ``door`` is the disk half of the layout and holds no
    rule of its own, so it reaches the layout for every rule, ``fsio`` for
    the one test of a link and ``settings`` for the root - nothing else."""
    load, call = import_edges()
    assert load["door"] == {"layout", "fsio", "settings"}, load["door"]
    assert call["door"] <= {"page"}, call["door"]


def test_the_atomic_write_imports_nothing_of_the_package():
    """It is the bottom of the package: anything may reach it, it reaches
    nothing, and it holds no policy to reach for."""
    load, call = import_edges()
    assert load["fsio"] == set(), load["fsio"]
    assert call["fsio"] == set(), call["fsio"]


def test_the_layout_imports_nothing_of_the_package():
    """The layout is path arithmetic on one shape (decision 125), and since
    decision 187 the one wording of where a step of a return may act: the
    filer and the store both ask it, so it may reach neither, at load time
    or at call time."""
    load, call = import_edges()
    assert load["layout"] == set(), load["layout"]
    assert call["layout"] == set(), call["layout"]


def test_the_reply_shapes_import_nothing_of_the_package():
    """SPEC-architecture-p2 R2.3.1: ``replies`` is the written shape of what
    the API prints, and the API and the suite both name it - so it reaches
    nothing of the package, at load time or at call time."""
    load, call = import_edges()
    assert load["replies"] == set() and call["replies"] == set(), (load["replies"], call["replies"])


def test_the_package_init_imports_nothing_at_load_time():
    load, _ = import_edges()
    assert load["__init__"] == set(), load["__init__"]


def test_the_runner_never_imports_the_scheduler_or_the_api():
    load, call = import_edges()
    assert not {"scheduling", "api"} & (load["runner"] | call["runner"])


def test_nothing_the_scheduled_pass_loads_reads_the_products_name_at_import():
    """SPEC-architecture-p5 R5.3.5 (P340): the scheduled task starts the
    runner with no product name in its environment (``api_entry.py``'s
    docstring; P220), and there ``settings.product_name()`` raises. Three
    modules read the name at their top level - ``screen_words`` (``SCREEN``'s
    side panel), ``scheduling`` (``TASK_NAME``, P220) and ``api``, which imports
    both - so none of them may be in what the runner loads. The test above
    checks the runner's own imports; this one follows its load-time imports
    to every module they load in turn, so a word module imported two steps
    down would still be caught before it stopped the scheduled pass.

    SPEC-architecture-p5 R5.7.9 (P344): it walks ``firm_view``'s load-time
    closure too, so the pass could call the builder in-process (Q-C) without
    reading the product's name."""
    load, _ = import_edges()
    for start in ("runner", "firm_view"):
        loaded: set[str] = set()
        waiting = [start]
        while waiting:
            for module in load[waiting.pop()] - loaded:
                loaded.add(module)
                waiting.append(module)
        reached = {"screen_words", "scheduling", "api"} & loaded
        assert reached == set(), (start, sorted(reached))


def test_the_scanner_never_imports_the_filer_or_a_persons_actions_and_they_reach_it_only_at_call_time():
    load, call = import_edges()
    for module in ("filer", "actions"):
        assert module not in load["scanner"] and module not in call["scanner"], (load["scanner"], call["scanner"])
    assert "scanner" not in load["filer"] and "scanner" not in call["filer"], (load["filer"], call["filer"])
    assert "scanner" not in load["actions"] and "scanner" in call["actions"], (load["actions"], call["actions"])


#: Every pair of modules that import each other, and the only pairs allowed to.
#: Each closes at call time: one of its two edges is an import inside a
#: function or a ``__main__`` block, so neither module needs the other to exist
#: before it loads. A new pair is a decision, not an accident: it is added here
#: with the place it closes, or the import that closes it is removed.
CALL_TIME_CYCLES: frozenset[frozenset[str]] = frozenset({
    frozenset({"registry", "store"}),       # the store's ``__main__`` asks the registry
    frozenset({"store", "store_check"}),    # the store's ``__main__`` asks the check
    frozenset({"store", "verify"}),         # the store's ``__main__`` asks verify
    frozenset({"scaffold", "validators"}),  # validators' ``__main__`` block asks scaffold
})


def test_the_only_two_module_cycles_are_the_named_call_time_ones():
    load, call = import_edges()
    reaches = {module: load[module] | call[module] for module in load}
    pairs = {frozenset({a, b}) for a in reaches for b in reaches[a]
             if a != b and b in reaches and a in reaches[b]}
    assert pairs == CALL_TIME_CYCLES, (sorted(map(sorted, pairs)), sorted(map(sorted, CALL_TIME_CYCLES)))
    for pair in pairs:
        a, b = sorted(pair)
        assert not (b in load[a] and a in load[b]), f"{a} and {b} import each other at load time"


def _imported_names(tree: ast.AST) -> list[str]:
    """Every dotted module name an import anywhere in ``tree`` reaches:
    ``import x.y`` and ``from x.y import z`` both give ``x.y``; the walk
    covers function bodies, class bodies and the ``__main__`` block alike."""
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return names


def test_no_module_under_tracker_imports_a_mail_or_network_module():
    """Decision 115 pins the fourth standing rule in code: no SMTP, no mail
    client, no network call - no module that could make one is imported
    anywhere under tracker/, at load time or at call time."""
    found = []
    for path in sorted(PACKAGE.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for name in _imported_names(tree):
            top = name.split(".")[0]
            if top in FORBIDDEN_MODULES and name not in MAIL_PARSING_ALLOWED.get(path.stem, ()):
                found.append(f"{path.name} imports {name}")
    assert not found, found


def _tracker_trees() -> list[tuple[Path, ast.AST]]:
    return [(path, ast.parse(path.read_text(encoding="utf-8"), filename=str(path)))
            for path in sorted(PACKAGE.rglob("*.py"))]


def test_every_import_under_tracker_is_allowed():
    """Decision 190: every top-level name imported anywhere under tracker/,
    at load time or at call time, is the package itself, a standard-library
    module on :data:`ALLOWED_STDLIB` or a reader or the OCR engine on
    :data:`ALLOWED_THIRD_PARTY`. An unknown import fails here, whatever it
    is, until a person names it and says what it is for. A relative import
    is refused too: it would reach a module this walk does not name."""
    allowed = {"tracker"} | ALLOWED_STDLIB | set().union(*ALLOWED_THIRD_PARTY.values())
    found = []
    for path, tree in _tracker_trees():
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level:
                found.append(f"{path.name}: a relative import of {node.module or '.'}")
        for name in _imported_names(tree):
            if name.split(".")[0] not in allowed:
                found.append(f"{path.name} imports {name}")
    assert not found, found


def _generative(name: str, names: tuple[str, ...]) -> bool:
    for listed in names:
        if listed.endswith("*"):
            if name.startswith(listed[:-1]):
                return True
        elif name == listed or name.startswith(listed + "."):
            return True
    return False


def _required_names(path: Path) -> list[str]:
    """The distribution names a requirements or lock file lists,
    normalised as pip compares them (lower case, ``_`` and ``.`` as ``-``)."""
    import re

    names = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        match = re.match(r"[A-Za-z0-9][A-Za-z0-9._-]*", line)
        if match:
            names.append(re.sub(r"[-_.]+", "-", match.group(0)).lower())
    return names


def _requirement_files() -> list[Path]:
    """Every requirements file and every lock file decision 191 installs
    from, as the repository holds them."""
    return sorted(REPO.glob("requirements*.txt")) + sorted(REPO.glob("requirements*.lock"))


#: The distribution each allowed third-party import comes from, where the
#: two names differ (the rest are the same name, as pip normalises it).
DISTRIBUTION_OF: dict[str, str] = {"PIL": "pillow", "pillow_heif": "pillow-heif",
                                   "cv2": "opencv-python-headless"}


def test_every_allowed_third_party_import_is_a_locked_package():
    """The allow-list and decision 191's lock name one set: each allowed
    third-party import is pinned, with its hash, by a lock file, so a name
    added here that nothing installs - or a package the lock drops - fails
    here rather than at a client's pass. Read, never installed from."""
    locked = {name for path in sorted(REPO.glob("requirements*.lock")) for name in _required_names(path)}
    assert locked, "no lock file found"
    allowed = {name for group in ALLOWED_THIRD_PARTY.values() for name in group}
    unpinned = sorted(name for name in allowed
                      if DISTRIBUTION_OF.get(name, name).replace("_", "-").lower() not in locked)
    assert unpinned == [], unpinned


def test_no_generative_ai_package_is_imported_or_required():
    """The first standing rule, pinned (decision 190): no generative AI ever
    reads a client document, so no generative-AI package is imported under
    tracker/ - by any name, at any depth - and none is named in any
    requirements file or in any lock file (decision 191's hash-checked
    install), where a build would install it. The files are read, never
    installed from."""
    files = _requirement_files()
    assert (REPO / "requirements.txt") in files and (REPO / "requirements.lock") in files, files
    found = [f"{path.name} imports {name}"
             for path, tree in _tracker_trees() for name in _imported_names(tree)
             if _generative(name, GENERATIVE_AI_IMPORTS)]
    found += [f"{path.name} requires {name}"
              for path in files for name in _required_names(path)
              if _generative(name, GENERATIVE_AI_DISTRIBUTIONS)]
    assert not found, found


def test_nothing_under_tracker_imports_by_string():
    """An import made from a string - ``importlib``, ``__import__`` - is
    one no walk of the source can see, so the allow-list above could be
    walked around by it. None is made under tracker/ (decision 190)."""
    found = []
    for path, tree in _tracker_trees():
        found += [f"{path.name} imports {name}" for name in _imported_names(tree)
                  if name.split(".")[0] == "importlib"]
        found += [f"{path.name}:{node.lineno} names __import__" for node in ast.walk(tree)
                  if (isinstance(node, ast.Name) and node.id == "__import__")
                  or (isinstance(node, ast.Attribute) and node.attr == "__import__")]
    assert not found, found


def test_the_app_has_no_network_call():
    """The desktop app talks to the tracker through the API's command line
    and to nothing else (decision 190). Its own scripts - the main process,
    the preload and the renderer, never a dependency under node_modules -
    load no network module, fetch nothing, open no socket and hand no link
    to the system browser.

    The scan is a tripwire over the scripts' text, not a proof that no
    call exists: it catches the shapes :data:`APP_NETWORK_CALLS` names,
    and refuses a ``require`` it cannot read, so that a change that means
    to reach the network has to do it in a shape a reviewer will see."""
    import re

    scripts = sorted(path for path in (REPO / "app").rglob("*.js")
                     if "node_modules" not in path.relative_to(REPO / "app").parts)
    assert {path.name for path in scripts} >= {"main.js", "preload.js", "app.js"}, scripts
    found = []
    for path in scripts:
        text = path.read_text(encoding="utf-8")
        for what, pattern in APP_NETWORK_CALLS.items():
            for match in re.finditer(pattern, text):
                line = text.count("\n", 0, match.start()) + 1
                found.append(f"{path.relative_to(REPO).as_posix()}:{line}: {what}")
    assert not found, found


def test_the_network_tripwire_catches_the_shapes_that_walked_around_it():
    """Each line here reached the network, or could, and passed the first
    scan (the review of decision 190): electron's own ``net``, a page
    loaded from a URL, a beacon, a template-literal ``require`` and one
    built from a sum. Each is caught now, and the app's own requires - a
    plain string naming electron, a Node module or its own file - and its
    ``loadFile`` are not."""
    import re

    def caught(line: str) -> list[str]:
        return [what for what, pattern in APP_NETWORK_CALLS.items() if re.search(pattern, line)]

    walked_around = [
        'const { net, shell } = require("electron");',
        "const https = require(`https`);",
        'net.request("https://example.com");',
        'net.fetch("https://example.com");',
        'win.loadURL("https://example.com");',
        "win.loadURL(address);",
        'navigator.sendBeacon("https://example.com", "x");',
        'const h2 = require("node:" + "https");',
        "const mod = require(name);",
        'import https from "node:https";',
        'const later = await import("https");',
        'new EventSource("https://example.com");',
        'window.open("https://example.com");',
    ]
    missed = [line for line in walked_around if not caught(line)]
    assert not missed, missed

    the_apps_own = [
        'const { app, BrowserWindow, ipcMain, shell, dialog } = require("electron");',
        'const { spawn } = require("child_process");',
        'const PKG = require("./package.json");',
        'win.loadFile(path.join(__dirname, "renderer", "index.html"));',
        'win.loadURL("file:///local/index.html");',
        "// blocks on the look: strict parking is the safety net.",
    ]
    flagged = {line: caught(line) for line in the_apps_own if caught(line)}
    assert not flagged, flagged


def test_the_email_parser_reaches_no_mail_client_and_no_network_call():
    """Decision 143's one exception, measured rather than trusted: the
    module that opens a client's ``.eml`` is imported in an interpreter of
    its own, and of the forbidden names only ``email`` itself and the two
    the standard library's own helpers reach (:data:`READER_IMPORTS_ALLOWED`:
    ``email.utils`` imports ``socket`` for a message id it is never asked
    for, and ``urllib.parse`` to unquote a parameter) may come back - never
    ``smtplib``, ``imaplib``, ``poplib``, ``http`` or ``ssl``."""
    import json
    import subprocess
    import sys

    program = (
        "import json,sys\n"
        "before={m.split('.')[0] for m in sys.modules}\n"
        "import tracker.containers\n"
        "print(json.dumps(sorted({m.split('.')[0] for m in sys.modules}-before)))\n"
    )
    done = subprocess.run([sys.executable, "-c", program], capture_output=True, text=True,
                          check=True, cwd=REPO)
    reached = {name for name in json.loads(done.stdout) if name in FORBIDDEN_MODULES}
    assert reached <= READER_IMPORTS_ALLOWED | {"email"}, sorted(reached)


def test_no_reader_imports_a_network_module():
    """Decision 127 put four readers inside the package's reading path, and
    the standing rule is about what the machine can reach, not about who
    wrote the code: a reader that could open a connection would put a
    client's document one import away from leaving the office.

    Each is imported in an interpreter of its own, so what it drags in is
    measured rather than guessed, and the only forbidden names allowed
    back are the two :data:`READER_IMPORTS_ALLOWED` explains. Nothing here
    is a network *call* - it is the capability being held to a list that
    somebody has to change on purpose.
    """
    import json
    import subprocess
    import sys

    program = (
        "import json,sys\n"
        "before={m.split('.')[0] for m in sys.modules}\n"
        "names=json.loads(sys.argv[1])\n"
        "missing=[]\n"
        "for name in names:\n"
        "    try:\n"
        "        __import__(name)\n"
        "    except ImportError:\n"
        "        missing.append(name)\n"
        "after={m.split('.')[0] for m in sys.modules}\n"
        "print(json.dumps({'added':sorted(after-before),'missing':missing}))\n"
    )
    for reader in READER_MODULES:
        done = subprocess.run(
            [sys.executable, "-c", program, json.dumps([reader])],
            capture_output=True, text=True, check=True,
        )
        result = json.loads(done.stdout)
        if result["missing"]:
            continue          # not installed here; requirements.txt pins it for CI
        reached = {name for name in result["added"] if name in FORBIDDEN_MODULES}
        assert reached <= READER_IMPORTS_ALLOWED, (reader, sorted(reached))


#: What of ``multiprocessing`` could open a socket: its listener and client,
#: and the managers that serve objects over one. The reading's child
#: (decision 150) needs none of them - ``Pipe`` is a named pipe on Windows.
SOCKET_SHAPED = frozenset({"Listener", "Client", "Manager", "BaseManager", "SyncManager"})


def test_the_readings_child_talks_over_a_named_pipe_never_a_socket():
    """Decision 150 put a child process in the reading path. What passes
    between it and the pass is one document's reading, so it goes over a
    named pipe: no module under tracker/ imports ``multiprocessing``'s
    connection or managers modules, or names their listener, client or
    manager."""
    found = []
    for path in sorted(PACKAGE.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for name in _imported_names(tree):
            if name in ("multiprocessing.connection", "multiprocessing.managers"):
                found.append(f"{path.name} imports {name}")
        for node in ast.walk(tree):
            named = node.attr if isinstance(node, ast.Attribute) else getattr(node, "id", None)
            if named in SOCKET_SHAPED:
                found.append(f"{path.name}:{node.lineno} names {named}")
    assert not found, found


# ------------------- decision 188: which household is this, and may this path exist ----

#: Where a rule about the trees may still be spelled outside ``layout`` and
#: ``door``, by (file, function) - ``"*"`` for a whole file - and why.
ALLOWED_SPELLINGS: dict[tuple[str, str], str] = {
    ("tracker/settings.py", "_within"): "the machine's own folders (decision 137), not a client's",
    ("tracker/settings.py", "inside"): "the machine's own folders (decision 137), not a client's",
    ("tracker/locking.py", "holds"): ("whether a held token was written to this very lock file, "
                                      "under any spelling (decision 159) - one file, not a place "
                                      "in either tree"),
    ("tracker/validators.py", "bears_macros"): ("a member's name inside an Office package's zip "
                                                "(decision 190), never a folder of the layout"),
    ("tracker/firm_pages.py", "<module>"): ("the order a person reads displayed names in, as the window's collator "
                                            "gave it (P278) - never a folder's identity or its key"),
    ("tools/repo_map.py", "*"): "the repository's paths, never a client's",
    ("tools/vocab_report.py", "*"): "the repository's paths, never a client's",
    ("tools/backtest.py", "*"): "the repository's paths, never a client's",
    ("tools/patch_sites.py", "*"): "the repository's paths, never a client's",
}
#: The owners: the only modules that may spell a rule about the trees.
SPELLING_OWNERS = ("tracker/layout.py", "tracker/door.py")
_PATH_RELATIONS = {"relative_to", "is_relative_to", "commonpath", "commonprefix", "relpath",
                   "samefile"}
_TREE_WORDS = {"CLIENTS_TREE", "PRIVATE_TREE", "INBOX_DIR_NAME", "OPENED_DIR_NAME"}
_NAME_RULES = {"WINDOWS_RESERVED_NAMES", "is_reserved_name", "segment_problem", "name_key",
               "MACHINE_PREFIXES"}
_FOLDS = {"casefold", "lower", "normcase"}
_JOINS = {"joinpath", "join", "Path", "PurePath", "PureWindowsPath", "PurePosixPath"}


def _layout_words() -> set[str]:
    """The layout's own words, as text: a literal equal to one is the
    layout spelled again (the review's S1)."""
    from tracker import layout

    return {layout.CLIENTS_TREE, layout.PRIVATE_TREE, layout.INBOX_DIR_NAME,
            layout.PREPARED_DIR_NAME, layout.REVIEW_DIR_NAME, layout.OPENED_DIR_NAME}


def _is_text_of_a_path(node: ast.AST) -> bool:
    """``str(...)`` or ``os.fspath(...)``: a path made text to be compared."""
    return isinstance(node, ast.Call) and (
        (isinstance(node.func, ast.Name) and node.func.id == "str")
        or (isinstance(node.func, ast.Attribute) and node.func.attr == "fspath"))


def _is_parts(node: ast.AST) -> bool:
    """A path's ``.parts``, or a subscript of it."""
    while isinstance(node, ast.Subscript):
        node = node.value
    return isinstance(node, ast.Attribute) and node.attr == "parts"


def _named(node: ast.AST) -> str:
    """The name or attribute a node spells, or ""."""
    return node.id if isinstance(node, ast.Name) else node.attr if isinstance(node, ast.Attribute) else ""


def _mentions(node: ast.AST, test) -> bool:
    return any(test(inner) for inner in ast.walk(node))


def _is_os_path(node: ast.AST) -> bool:
    """``os.sep``, or anything under ``os.path``."""
    return (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name)
            and node.value.id == "os" and node.attr in ("sep", "path"))


def spellings(source: str) -> list[tuple[str, int, str]]:
    """Every rule about the trees ``source`` spells for itself, as
    (enclosing function, line, what) - decision 188's R13."""
    found: list[tuple[str, int, str]] = []
    words = _layout_words()

    def tree_word(node: ast.AST) -> bool:
        return _named(node) in _TREE_WORDS or (
            isinstance(node, ast.Constant) and node.value in words)

    def visit(node: ast.AST, where: str) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name in _NAME_RULES:
                found.append((where, node.lineno, f"defines {node.name}"))
            where = node.name
        if isinstance(node, ast.Call):
            called = _named(node.func)
            if called in _PATH_RELATIONS:
                found.append((where, node.lineno, f"calls {called}"))
            if called in ("startswith", "endswith") and any(
                    _mentions(arg, _is_os_path) for arg in node.args):
                found.append((where, node.lineno, f"{called} on a path separator"))
            elif called in ("startswith", "endswith") and isinstance(node.func, ast.Attribute) and (
                    _is_text_of_a_path(node.func.value) or any(map(_is_text_of_a_path, node.args))):
                found.append((where, node.lineno, f"{called} on a path's text"))
            if called in _JOINS and any(tree_word(arg) for arg in node.args):
                found.append((where, node.lineno, "joins a tree word onto a path"))
        if isinstance(node, ast.Compare):
            operands = [node.left, *node.comparators]
            if any(tree_word(one) for one in operands):
                found.append((where, node.lineno, "compares a tree word"))
            if any(_is_parts(one) for one in operands):
                found.append((where, node.lineno, "compares a path's parts"))
            folded = [one for one in operands
                      if isinstance(one, ast.Call) and _named(one.func) in _FOLDS]
            if folded and _mentions(node, lambda n: (
                    isinstance(n, ast.Attribute) and n.attr == "name")
                    or "household" in _named(n) or "return_name" in _named(n)):
                found.append((where, node.lineno, "compares a folded folder name"))
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div) and (
                tree_word(node.left) or tree_word(node.right)):
            found.append((where, node.lineno, "joins a tree word onto a path"))
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            modules = [alias.name for alias in node.names] if isinstance(node, ast.Import) \
                else [node.module or ""]
            if "unicodedata" in modules:
                found.append((where, node.lineno, "imports unicodedata"))
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if _named(target) in _NAME_RULES:
                    found.append((where, node.lineno, f"defines {_named(target)}"))
        for child in ast.iter_child_nodes(node):
            visit(child, where)

    visit(ast.parse(source), "<module>")
    return found


def _every_spelling() -> dict[tuple[str, str], list[tuple[int, str]]]:
    """Every spelling in tracker/ and tools/, by (file, function)."""
    by_place: dict[tuple[str, str], list[tuple[int, str]]] = {}
    for path in sorted([*PACKAGE.glob("*.py"), *(REPO / "tools").glob("*.py")]):
        rel = path.relative_to(REPO).as_posix()
        if rel in SPELLING_OWNERS:
            continue
        for function, line, what in spellings(path.read_text(encoding="utf-8")):
            by_place.setdefault((rel, function), []).append((line, what))
    return by_place


def _allowed(place: tuple[str, str]) -> bool:
    return place in ALLOWED_SPELLINGS or (place[0], "*") in ALLOWED_SPELLINGS


def test_no_under_the_root_decision_survives_outside_the_layout():
    """Decision 188 (R13): which household a folder is, and whether a path
    may exist there, is answered in ``layout`` (and on the disk by
    ``door``) and nowhere else. Outside them no module tests one path for
    lying under another, compares or joins a tree's word, spells the name
    rule or the key, or compares a folded folder name - but where the
    allow-list says why it may."""
    offending = {place: hits for place, hits in _every_spelling().items() if not _allowed(place)}
    assert not offending, [f"{file}:{line} {function}: {what}"
                           for (file, function), hits in sorted(offending.items())
                           for line, what in hits]


def test_no_rule_about_the_trees_is_spelled_outside_the_layout():
    """The scanner sees what it is for: a resolved path made relative to
    the root, a tree word compared with a folder's name, a separator test
    and a folded household name - and it passes the layout's own answer."""
    caught = spellings(
        "def f(p, root, x, h):\n"
        "    a = p.resolve().relative_to(root)\n"
        "    b = x.name == CLIENTS_TREE\n"
        "    c = str(p).startswith(str(root) + os.sep)\n"
        "    d = x.name.casefold() == h.household.casefold()\n"
        "    e = root / PRIVATE_TREE\n"
        "    import unicodedata\n"
        "def name_key(n):\n"
        "    return n\n")
    assert [what for _, _, what in caught] == [
        "calls relative_to", "compares a tree word", "startswith on a path separator",
        "compares a folded folder name", "joins a tree word onto a path", "imports unicodedata",
        "defines name_key"]
    # The review's S1: the spellings the first scanner missed.
    missed = spellings(
        "def g(p, root, h):\n"
        "    a = str(p).startswith(str(root))\n"
        "    b = Path(root).joinpath(CLIENTS_TREE, h)\n"
        "    c = os.path.join(root, PRIVATE_TREE)\n"
        "    d = Path(root, 'Clients', h)\n"
        "    e = p.parts[:2] == (root.name, 'x')\n"
        "    f = root / 'Drop files here'\n")
    assert [what for _, _, what in missed] == [
        "startswith on a path's text", "joins a tree word onto a path",
        "joins a tree word onto a path", "joins a tree word onto a path",
        "compares a path's parts", "joins a tree word onto a path"]
    assert spellings("def f(root, p):\n    return layout.place_of(root, p).kind == layout.RETURN\n"
                     "def g(n):\n    return f'the {CLIENTS_TREE} folder'\n") == []


def test_every_allowed_spelling_is_still_needed():
    """An allowance nothing uses is a hole in the rule."""
    every = _every_spelling()
    stale = [place for place in ALLOWED_SPELLINGS
             if not any(found == place or (place[1] == "*" and found[0] == place[0])
                        for found in every)]
    assert not stale, stale


def test_the_app_never_works_out_whether_a_path_lies_under_another():
    """The same rule for the shell and the page: no ``path.relative(`` and
    no ``startsWith(`` in ``main.js`` or in any script the page loads
    (SPEC-architecture R3.3) - the API says where a path is below the root,
    in the layout's words."""
    for path in (REPO / "app" / "main.js", *(RENDERER / name for name in RENDERER_SCRIPTS)):
        text = path.read_text(encoding="utf-8")
        assert "path.relative(" not in text, path.name
        assert "startsWith(" not in text, path.name


def test_importing_the_api_loads_no_network_module():
    """Decision 193's review (S2): importing the tracker - the API, which
    imports every other module - loads no module that could open a
    connection. The error log rotates by its own few lines rather than
    ``logging.handlers`` (which loads ``socket``), and the two standard
    library helpers that drag one in - the email parser and XML escaping -
    are imported where they are used. Measured in a fresh interpreter.

    Decision 194 (D8) closes the escape for good: ``tracker.scheduling``
    escapes the task file with ``html.escape(quote=False)``, byte for byte
    what ``xml.sax.saxutils`` gave, so ``xml.sax`` - which loads
    ``urllib.request``, ``http.client`` and ``ssl`` - is not in the process
    at all, and the scheduling module is held to it on its own too."""
    import json
    import subprocess
    import sys

    for module in ("tracker.api", "tracker.scheduling"):
        program = (
            "import json,sys\n"
            f"import {module}\n"
            "print(json.dumps(sorted(m for m in ('socket', 'http', 'ssl', 'urllib.request', "
            "'xml.sax') if m in sys.modules)))\n"
        )
        done = subprocess.run([sys.executable, "-c", program], capture_output=True, text=True,
                              check=True, cwd=REPO)
        assert json.loads(done.stdout) == [], module


def test_the_engine_imports_the_api_the_error_log_the_lock_and_the_reader_and_nothing_imports_the_engine():
    """P276: ``resident`` is the app's engine, a loop over ``api.main``; it
    reaches only those four, and nothing in the package reaches it - the
    entry point (``api_entry.py``, outside the package) starts it."""
    load, call = import_edges()
    assert load["resident"] == {"api", "errlog", "locking", "reader_child"}, load["resident"]
    assert call["resident"] == set(), call["resident"]
    assert [m for m in load if "resident" in load[m] | call[m]] == []
    assert LAYER_OF["resident"] == LAYER_OF["api"] == 5


# ── P278 (SPEC-ui-menu-speed §4) ───────────────────────────────────────────

def test_firm_pages_joins_layer_0_and_reaches_only_the_standard_library_and_the_low_modules():
    """P278: the firm lists cut into pages and the view file are layer 0 -
    the API builds the whole reply and hands the words; this module decides
    no count and reads no record. Nothing but the API reaches it."""
    load, call = import_edges()
    assert LAYER_OF["firm_pages"] == 0
    assert load["firm_pages"] == {"errors", "firm_cache", "fsio", "layout", "settings"}, load["firm_pages"]
    assert call["firm_pages"] == set(), call["firm_pages"]
    assert [m for m in load if "firm_pages" in load[m] | call[m]] == ["api"]


# ── P4.13 (SPEC-architecture-p4 R4.13.1): moved names are read from home ───

# Where each old module's names went in phase 4 (P331-P338 and SPEC-architecture-p4).
# P4.13 holds them: a test, a tool or the program reads a moved name from the
# module that defines it, never through the module it left, because an old
# module that happens to import the name back for its own use would keep the
# read working until the day it stops needing the import.
MOVED_OUT = {
    "filer": ("copies", "intents", "inbox", "readme_ack", "actions", "index"),
    "content_check": ("keywords", "verdicts"),
    "ocr": ("reader_child",),
}

# A read through an old module that must stay, with the reason. It starts empty:
# an entry is a stop and ask (SPEC-architecture-p4, P4.13).
READ_THROUGH_ON_PURPOSE: dict[tuple[str, int, str], str] = {}

# The carry-forward's two names count for the filer too: scaffold's and
# layout's, so they do not come back.
_MOVED_BEFORE_PHASE_4 = {"filer": {"OTHER_DOCUMENT", "PREPARED_DIR_NAME"}}


def _top_level_names(module: str) -> set[str]:
    tree = ast.parse((REPO / "tracker" / f"{module}.py").read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                names.update(n.id for n in ast.walk(target) if isinstance(n, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def _moved_names() -> dict[str, set[str]]:
    moved: dict[str, set[str]] = {}
    for old, homes in MOVED_OUT.items():
        names: set[str] = set()
        for home in homes:
            # P2.9's decision words moved to index in phase 2; only OPENED is phase 4's.
            names |= {"OPENED"} if home == "index" else _top_level_names(home)
        moved[old] = (names - _top_level_names(old)) | _MOVED_BEFORE_PHASE_4.get(old, set())
    return moved


def _reads_of_moved_names(tree: ast.AST, moved: dict[str, set[str]]) -> list[tuple[int, str, str]]:
    """(line, old module, name) for every code read of a moved name through its old module."""
    found: list[tuple[int, str, str]] = []
    alias: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            if node.module == "tracker":
                for a in node.names:
                    if a.name in moved:
                        alias[a.asname or a.name] = a.name
            elif node.module.startswith("tracker."):
                old = node.module.split(".", 1)[1]
                found += [(node.lineno, old, a.name) for a in node.names if a.name in moved.get(old, ())]
        elif isinstance(node, ast.Import):
            for a in node.names:
                old = a.name.split(".", 1)[1] if a.name.startswith("tracker.") else ""
                if old in moved and a.asname:
                    alias[a.asname] = old
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in alias:
            old = alias[node.value.id]
            if node.attr in moved[old]:
                found.append((node.lineno, old, node.attr))
    return found


def test_a_name_this_phase_moved_is_read_from_its_home_never_through_the_module_it_left():
    """P4.13 (R4.13.1): no ``from tracker.filer import room_for`` and no
    ``filer.room_for`` for a name phase 4 moved out of the filer, the content
    check or the OCR module. It reads code only: a ``setattr`` target is a
    string and patch_sites' concern, and a string program is swept by hand."""
    moved = _moved_names()
    assert all(moved[old] for old in MOVED_OUT), moved
    misses = []
    for root in ("tracker", "tools", "tests"):
        for path in sorted((REPO / root).rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            rel = path.relative_to(REPO).as_posix()
            for line, old, name in _reads_of_moved_names(tree, moved):
                if rel == f"tracker/{old}.py" or (rel, line, name) in READ_THROUGH_ON_PURPOSE:
                    continue
                misses.append(f"{rel}:{line} {old}.{name}")
    assert misses == [], "\n".join(misses)
