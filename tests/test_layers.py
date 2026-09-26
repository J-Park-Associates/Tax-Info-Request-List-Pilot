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
one deliberate cycle in the package, ``filer`` <-> ``scanner`` inside
``_rescan()``, is a call-time cycle and is asserted to stay one.

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
``manifest`` imports ``records`` and nothing else at load time, and
reaches ``store``, ``ledger`` and ``locking`` at call time; ``runner``
never imports ``scheduling`` or ``api``; the package's ``__init__`` imports
nothing at load time (decision 99 removed thirteen re-exports no file
consumed, and with them the one load-time cycle the map used to name).

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
imports that rule and nothing else of it (the layout reads no file).

``names`` joins L2 with decision 128, beside ``router``: it is the matcher
for the name on a page - normalising, whole-phrase containment, the
spellings the app proposes and the three-way verdict - and it imports
``records`` for the one way a name is cut into words and ``content_check``
for the one page-break character. Like the router it decides nothing about
a folder: the check itself runs one layer up, in the filer's household
pass, where the returns and their people lists are.

``store`` joins L1 with decision 101 and is deliberately narrower than its
layer allows: it imports ``records``, ``ledger``, ``locking`` and (since
decision 159) ``checkpoint``, and nothing else of the package, not even the in-layer ``manifest``.
Everything it holds comes out of the journal, so the database that answers
for the readers never depends on the modules that walk folders and move
files; its command line imports the registry at call time, which is where
a cycle is allowed to close.

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

REPO = Path(__file__).resolve().parents[1]
PACKAGE = REPO / "tracker"

#: Layer -> the modules in it. Every file in tracker/ is in exactly one.
LAYERS: dict[int, frozenset[str]] = {
    # ``door`` joins L0 with decision 188: the disk half of the layout. It
    # imports ``layout``, ``fsio`` and ``settings``, all L0, so L0 is the
    # lowest layer the table allows it - and every layer above may ask it.
    0: frozenset({"__init__", "reasons", "locking", "checkpoint", "page", "fsio", "settings",
                  "layout", "door", "errors"}),
    1: frozenset({"households", "ledger", "manifest", "records", "scaffold", "store",
                  "templates", "validators"}),
    2: frozenset({"containers", "content_check", "names", "ocr", "router"}),
    3: frozenset({"filer", "scanner", "reminder", "rollover", "view", "registry", "review"}),
    4: frozenset({"runner", "scheduling"}),
    5: frozenset({"api"}),
}
LAYER_OF: dict[str, int] = {module: layer for layer, modules in LAYERS.items() for module in modules}

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
ALLOWED_STDLIB: frozenset[str] = frozenset({
    "__future__", "argparse", "base64", "builtins", "collections", "contextlib", "csv", "ctypes",
    "dataclasses", "datetime", "email", "errno", "functools", "hashlib", "html", "io", "json",
    "logging", "math",
    "multiprocessing", "ntpath", "os", "pathlib", "platform", "posixpath", "re", "secrets",
    "shutil", "signal", "sqlite3", "stat", "subprocess", "sys", "threading", "time",
    "traceback", "unicodedata", "xml", "zipfile", "zlib",
})

#: Every third-party module the package may import, by what it is for.
#: Readers turn a file's bytes into its text, tables or pixels, by rule.
#: Optical character recognition turns a page's pixels into its letters:
#: RapidOCR and the ONNX Runtime it runs on, with NumPy for the arrays. Its
#: models are deterministic models of letter shapes - the same page gives
#: the same text - and they generate nothing (decision 169), which is why
#: they are named here as OCR and not left to be mistaken for generative AI.
ALLOWED_THIRD_PARTY: dict[str, frozenset[str]] = {
    "readers": frozenset({"pypdf", "pdfplumber", "pypdfium2", "openpyxl", "olefile", "PIL",
                          "pillow_heif"}),
    "optical character recognition": frozenset({"rapidocr", "onnxruntime", "numpy"}),
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


def _is_main_guard(node: ast.If) -> bool:
    test = node.test
    return (isinstance(test, ast.Compare) and isinstance(test.left, ast.Name)
            and test.left.id == "__name__")


def _modules() -> set[str]:
    return {path.stem for path in PACKAGE.glob("*.py")}


def _target(name: str, modules: set[str]) -> str:
    """Which module a ``from tracker import name`` reaches: the submodule of
    that name, or the package itself when the name is something it defines."""
    return name if name in modules else "__init__"


def _collect(body: list[ast.stmt], modules: set[str], load: set[str], call: set[str], *, in_call: bool) -> None:
    for node in body:
        into = call if in_call else load
        if isinstance(node, ast.If) and _is_main_guard(node):
            _collect(node.body, modules, load, call, in_call=True)
            _collect(node.orelse, modules, load, call, in_call=in_call)
            continue
        if isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[0] == "tracker":
            parts = node.module.split(".")
            if len(parts) == 1:
                into.update(_target(alias.name, modules) for alias in node.names)
            else:
                into.add(parts[1])
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "tracker":
                    into.add("__init__")
                elif alias.name.startswith("tracker."):
                    into.add(alias.name.split(".")[1])
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            _collect(node.body, modules, load, call, in_call=True)
        else:
            for field in ("body", "orelse", "finalbody"):
                child = getattr(node, field, None)
                if isinstance(child, list):
                    _collect(child, modules, load, call, in_call=in_call)
            for handler in getattr(node, "handlers", None) or []:
                _collect(handler.body, modules, load, call, in_call=in_call)


def import_edges() -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """(load-time edges, call-time edges) for every module in the package."""
    modules = _modules()
    load: dict[str, set[str]] = {}
    call: dict[str, set[str]] = {}
    for path in sorted(PACKAGE.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        load[path.stem], call[path.stem] = set(), set()
        _collect(tree.body, modules, load[path.stem], call[path.stem], in_call=False)
        load[path.stem].discard(path.stem)
        call[path.stem] -= load[path.stem] | {path.stem}
    return load, call


def test_every_module_is_in_exactly_one_layer():
    modules = _modules()
    listed = [module for layer in LAYERS.values() for module in layer]
    assert sorted(listed) == sorted(set(listed)), "a module is named in two layers"
    assert set(listed) == modules, set(listed) ^ modules


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


def test_the_store_imports_only_the_record_the_journal_the_lock_and_the_checkpoint():
    """Decision 101: narrower than its layer, on purpose - the store must
    not depend on what opens a workbook, or it cannot replace it. Decision
    159 adds the checkpoint, which is below it and imports nothing."""
    load, _ = import_edges()
    assert load["store"] == {"checkpoint", "ledger", "locking", "records"}, load["store"]


def test_the_manifest_imports_the_record_and_nothing_else():
    """Narrower since decision 103, and kept so by 104.

    The manifest used to append to the journal and take the engagement
    lock at load time, because it wrote the scanner columns. Decision 104
    gave it the request list's writes, and they reach the store, the
    journal and the lock at call time - where an in-layer edge is allowed
    to close - so at load time it names the shapes it validates into and
    nothing else.
    """
    load, call = import_edges()
    assert load["manifest"] == {"records"}, load["manifest"]
    assert {"store", "ledger", "locking"} <= call["manifest"], call["manifest"]


def test_the_settings_import_only_the_atomic_write_and_the_layout():
    """Decision 120: the one import that held it a layer up is gone.

    ``settings`` borrowed ``write_json_atomically`` from ``manifest``, and
    that single name was the whole of its dependence on L1. The write is
    ``fsio`` now, so the settings file - which the app, the scheduler and
    every command line read before anything else - is written by a module
    that knows nothing of request lists. Decision 188 adds ``layout``, at
    the same layer and reading no file: a root one level too deep is one
    that lies inside a tree of a real root, and the trees are the layout's.
    """
    load, _ = import_edges()
    assert load["settings"] == {"fsio", "layout"}, load["settings"]


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


def test_the_package_init_imports_nothing_at_load_time():
    load, _ = import_edges()
    assert load["__init__"] == set(), load["__init__"]


def test_the_runner_never_imports_the_scheduler_or_the_api():
    load, call = import_edges()
    assert not {"scheduling", "api"} & (load["runner"] | call["runner"])


def test_the_filer_and_scanner_cycle_closes_only_at_call_time():
    load, call = import_edges()
    assert "scanner" not in load["filer"] and "filer" not in load["scanner"]
    assert "scanner" in call["filer"] and "filer" in call["scanner"], (call["filer"], call["scanner"])


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
DISTRIBUTION_OF: dict[str, str] = {"PIL": "pillow", "pillow_heif": "pillow-heif"}


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
    ("tracker/settings.py", "_inside"): "the machine's own folders (decision 137), not a client's",
    ("tracker/locking.py", "holds"): ("whether a held token was written to this very lock file, "
                                      "under any spelling (decision 159) - one file, not a place "
                                      "in either tree"),
    ("tracker/validators.py", "bears_macros"): ("a member's name inside an Office package's zip "
                                                "(decision 190), never a folder of the layout"),
    ("tools/repo_map.py", "*"): "the repository's paths, never a client's",
    ("tools/vocab_report.py", "*"): "the repository's paths, never a client's",
    ("tools/backtest.py", "*"): "the repository's paths, never a client's",
    ("tools/learned_keywords.py", "out_path"): "the repository's paths, never a client's",
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
    no ``startsWith(`` in ``main.js`` or ``app.js`` - the API says where a
    path is below the root, in the layout's words."""
    for rel in ("app/main.js", "app/renderer/app.js"):
        text = (REPO / rel).read_text(encoding="utf-8")
        assert "path.relative(" not in text, rel
        assert "startsWith(" not in text, rel
