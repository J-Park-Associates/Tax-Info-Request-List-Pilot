"""Where the suite's stand-ins land, and whether the code still reads them there.

A test that swaps in a stand-in with ``monkeypatch.setattr(filer, "sha256_of",
fake)`` replaces one binding: the name ``sha256_of`` in ``filer``'s namespace.
The stand-in reaches only code that looks the name up there. ``filer``
imported ``sha256_of`` from ``fsio`` and calls it, so today it does. Move the
caller to another module and the stand-in still lands, on a name nothing reads
any more, and the test passes or fails for the wrong reason without an error
(SPEC-architecture A-4). Every move in the refactor's later phases carries that
risk, at each of the seven hundred-odd places the suite patches a module.

So this tool reads the suite and the code, and runs neither: standard library
``ast`` only. For every ``setattr`` call under ``tests/`` aimed at a module of
the repository, it marks the patched name as one of three things in that
module:

- **defined**: the module defines it (a ``def``, a ``class``, an assignment,
  or ``globals()[name] = ...``). Every caller that reaches it through the
  module meets the stand-in.
- **imported**: the module reads it but does not define it, a global read in
  its own code outside the import line: a name it imported, or a builtin the
  stand-in shadows. The module's own calls meet the stand-in.
- **unread**: the module never reads it outside its own import or definition
  line. The stand-in lands where no code looks; point it at the module that
  reads the name.

``report <module>`` lists the sites aimed at one module, and ``check`` exits 1
if any site in the suite is unread, if a stand-in cannot be placed, or if a
``setattr`` in the suite's text is none of what the tool accounts for (the
backstop, below). The migration checklist runs both (SPEC-architecture section
10, steps 5 and 12), so the tool keeps its ``__main__`` (P233).

**What it promises (R4.1 as amended by ruling 012 of J4).** A tool that reads
code without running it cannot be complete about what a target holds. It is
complete about two other things. Detection is complete against the source
text: every ``setattr`` token in the suite's Python is a stand-in it read, a
call of the builtin, or the name defined or imported, or ``check`` fails on
it. And placement fails closed: a target is placed only by a rule the tool can
prove, and every other target fails ``check`` as not placed. So a stand-in may
fail the check, but never pass it unseen.

**What it reads of the tests.** Any ``<x>.setattr(...)`` call is a stand-in, so
a fixture that hands its monkeypatch on (``in_a_child``) and
``pytest.MonkeyPatch.context()`` count as well as ``monkeypatch``; one called
on a class or on something outside the repository
(``MonkeyPatch.setattr(monkeypatch, sorter, ...)``, whose first argument is the
instance) is not placed. A module is named three ways: as the test imported it
(``setattr(filer, ...)``, and through a folder with no ``__init__.py``, as
``tests.children`` after ``import tests.children``), under an alias
(``filer_module``, ``here = children`` or ``here: ModuleType = children``), or
in a string (``setattr("tracker.filer.name", value)``). The string may be
written at the call or held in a name, a loop or a helper module's constant, or
made by an f-string. An alias or a string another module of the repository
holds at its top level (a helper module's ``THE_SORTER = sorter``, read as
``aliases.THE_SORTER`` or imported from it) is followed into that module. The
stand-ins most worth checking come in loops: a test that forbids four reads
sets four names in a ``for`` over a literal tuple, and a stand-in there that
misses makes the test pass for nothing. So the tool also follows a module, a
name or a string that comes from a ``for`` over literals (or over a literal
assigned to a name), from a ``parametrize`` mark's list (pytest's own loop, on
the test or its class), from a fixture's ``params``, from a fixture that
returns it, and from a helper's parameter at the helper's calls in the same
file. A fixture is looked for where pytest looks: the classes around the test,
its file, then the conftests on its own path, nearest first; one the file
imports or assigns from a helper module is followed into that module. A
fixture's ``request.param`` is its ``params`` only where no ``parametrize``
mark in the suite may hand the fixture values (``indirect``), since pytest
gives it the mark's values in their place. Values bound together stay together:
``for module, name in ((a, "x"), (b, "y"))`` and a mark's ``("module, name",
[(a, "x"), (b, "y")])`` are two sites each, not four, and inside a loop's body
its name holds the loop's values, whatever else it is bound to.

A top-level name is followed to its value only where nothing rebinds it: not a
function of its own file (``global``, ``globals()[...]``), not an assignment to
``<module>.<name>`` in any other file, and not a stand-in or the builtin
``setattr`` aimed at it. Any of those means it may hold something else by the
time a stand-in is aimed through it, so a stand-in aimed through a seam another
file fills (``children.PROC``, which a test replaces with
``monkeypatch.setattr(children, "PROC", proc)``) is not placed. Following what
each store puts there was the rejected alternative (ruling 009 of J4): which of
them the name holds when the stand-in goes in depends on the order the tests
run in. One scope in, the same holds: a function's local name that the function
or one inside it declares ``nonlocal`` is not followed.

**The backstop.** The rules above say what a stand-in's target holds; the
backstop says that every stand-in was looked at. ``check`` reads the suite's
Python (each file under ``tests/``, and the conftest at the root, which pytest
loads too) with ``tokenize``, so a string or a comment is not read, and holds
each ``setattr`` token to being one of these: a ``<x>.setattr`` the tool read
as a stand-in (a site, one on no module, or a not-placed line); a call of the
builtin ``setattr``, which is not a stand-in, because nothing undoes it; or the
name of a ``def`` or a ``class``, or a name in an import. Any other fails the
check with its file and line: a stand-in made through a name ``setattr`` that
is not the builtin, a parameter or a local of that name, a ``setattr`` passed
as an argument, one in a file the tool does not walk. A new way of writing a
stand-in can then fail the check, but never pass it unseen.

**What a read is.** A global read in the module's own code, by Python's own
scope rules: not a parameter or a local of the same name, not a method reading
its class's names, not a comprehension's own variable, and never an annotation
(which no call reaches, and which 3.11 and 3.14 scope differently). The rules
are written out here rather than taken from ``symtable``, which loses a
module-level comprehension's reads on 3.12 and later (PEP 709 inlines it), so
its answer would depend on the interpreter.

**What it does not read.** This list is the whole of the boundary:

- a store through ``vars()`` or ``__dict__`` (``vars(seams)["ENGINE"] =
  sorter``), which is not seen as rebinding the name; the placeholder rule
  below is the only guard, for a seam whose own value is a constant;
- ``monkeypatch.setitem``, which is not a ``setattr``;
- code built at run time: ``exec``, ``eval``, strings handed to ``importlib``,
  and a name given as a string (``getattr(monkeypatch, "setattr")``), which no
  token of the source text spells.

**What it does not see in the marks.** A name another module copied with ``from
module import name`` is out of reach of a stand-in on ``module``. That site is
reported as defined, because some caller may read the name through the module
and the tool cannot know which caller a test meant. The moves to come make the
other mistake, an imported name the module stops reading, and that is the one
``check`` fails.

**No module is something the tool proves, never its fallback.** One function,
:func:`_no_module`, draws that conclusion, and ``test_patch_sites`` holds it to
being the only one that does. A stand-in passes unlisted only when its target
is one of these: a constant that is not a string, written where it is used; a
literal container; a class the tool sees defined, or what calling one makes; a
builtin other than those that can hand back a module (:data:`_GIVE_A_MODULE`),
and what calling one gives; a value from an outside library, and what calling
it gives, where outside is a dotted name that is neither a module of the
repository nor a folder holding one (:meth:`_Suite.module` is the one place
that concludes it, and ``test_patch_sites`` holds it to that too); and what one
of pytest's own fixtures gives, or one of the installed plugin's
(:data:`_OUTSIDE_FIXTURES`, a fixed list). Each of these lands on that object,
whoever reads it. Every other target fails ``check`` as not placed. That
includes a module stored by an unpacking, a walrus, ``with ... as`` or ``except
... as``; a function (a decorator can make a ``def`` anything) and what any
function, method or instance gives when called; what ``getattr``, ``vars``,
``__import__``, ``globals``, ``locals``, ``eval``, ``next``, ``min`` or ``max``
gives; either side of ``or``, arithmetic, a comparison, a comprehension; an
attribute of anything but a module or an outside library (a class's, an
instance's, ``x.__class__``, one of what an outside call made); a top-level
name that is rebound (by a function of its own file, an assignment from another
file, or a ``setattr`` aimed at it) or that its module never binds, read in
that file or another; a function's local name that it or a function inside it
declares ``nonlocal``; a top-level name bound to a constant that is not a
string (``ENGINE = None``), which is a placeholder another module may fill in a
way the tool does not see; a folder with no ``__init__.py`` (``tests`` itself),
and a name in one that is none of its modules; a fixture the tool does not find
and pytest does not give, and one made some way it does not follow (a call that
returns a fixture, an import from outside the repository); a ``parametrize``
mark whose names or values are not written out, or that hands a name to its
fixture, and a fixture's ``request.param`` where any mark in the suite may hand
it values; a ``setattr`` that is not called where it is written (``put =
monkeypatch.setattr``, or ``functools.partial`` of one), or that is called on a
class or on something outside the repository; and in the string form, a first
argument that is not a string the tool can read, such as one built with ``+``
or ``format``. The remedy is the same each time: name the module and the name
as an import, an alias or a literal, and call ``setattr`` on the instance,
where it is written. The fallback this replaced, no module wherever the tool
did not know, let a stand-in written through a helper module, a lambda, a
class, a string held in a name, a ``parametrize`` mark, a helper's fixture or a
seam another file fills drop out of the check without a word.

Rejected: importing the modules to ask them (it runs code, and the tests'
imports reach the sorting engine); tracing a run of the whole suite (it costs a
full run, and still misses every branch the run does not take).
"""

from __future__ import annotations

import argparse
import ast
import builtins
import io
import itertools
import tokenize
from collections import Counter, defaultdict
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: The folders whose modules the suite can patch. A tool is also imported by
#: its bare name (``import repo_map``), since its test puts ``tools/`` on
#: ``sys.path``; it is reported by its dotted one.
PACKAGES = ("tracker", "tools", "tests")
ON_THE_PATH = ("tools",)
TESTS = "tests"

DEFINED = "defined"
IMPORTED = "imported"
UNREAD = "unread"
MARKS = (DEFINED, IMPORTED, UNREAD)

#: The most ways one site may expand, past which it is not placed: a product
#: of loops this large is not a list of literals a person wrote.
MOST_ROWS = 512


@dataclass(frozen=True, order=True)
class Site:
    """One stand-in: where it is written, the module and the name it replaces,
    and how the test wrote the module."""

    file: str
    line: int
    module: str
    name: str
    written: str

    def where(self) -> str:
        return f"{self.file}:{self.line}"


@dataclass(frozen=True, order=True)
class Unplaced:
    """A ``setattr`` whose module or name the tool could not work out: its
    target as written, or the ``setattr`` itself where it is not called there
    (``put = monkeypatch.setattr``), and why."""

    file: str
    line: int
    written: str
    why: str
    called: bool = True
    remedy: str = ""

    def said(self) -> str:
        """The line ``check`` prints for it."""
        if self.remedy:
            return f"{self.file}:{self.line}: {self.written} cannot be placed: {self.why}. {self.remedy}."
        if not self.called:
            return f"{self.file}:{self.line}: {self.written} cannot be placed: {self.why}. Call it where it is written."
        return (f"{self.file}:{self.line}: setattr({self.written}, ...) cannot be placed: {self.why}. "
                f"Name the module and the name as an import, an alias or a literal.")


# --------------------------------------------------------------- the modules ----

_FUNCTIONS = (ast.FunctionDef, ast.AsyncFunctionDef)
_COMPREHENSIONS = (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)


def module_index(root: Path = ROOT) -> dict[str, Path]:
    """Every module of the repository the suite can import, by each dotted
    name it can be imported under."""
    found: dict[str, Path] = {path.stem: path for path in sorted(root.glob("*.py"))}
    for top in PACKAGES:
        for path in sorted((root / top).rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            parts = list(path.relative_to(root).with_suffix("").parts)
            if parts[-1] == "__init__":
                parts.pop()
            found[".".join(parts)] = path
            if top in ON_THE_PATH and len(parts) == 2:
                found.setdefault(parts[1], path)
    return found


def _own_code(nodes: list[ast.AST]):
    """Every node of a scope's own code. A function, class, lambda or
    comprehension it holds is yielded, and its inside is not: that is another
    scope."""
    pending = list(nodes)
    while pending:
        node = pending.pop()
        yield node
        if not isinstance(node, (*_FUNCTIONS, ast.ClassDef, ast.Lambda, *_COMPREHENSIONS)):
            pending.extend(ast.iter_child_nodes(node))


def _own_bindings(nodes: list[ast.AST]) -> tuple[set[str], set[str], set[str]]:
    """What a scope's own code binds: the names it stores, the names it
    imports, and the names it declares ``global``. Inside a comprehension,
    only the target of a walrus, which binds in the enclosing scope."""
    stored: set[str] = set()
    imported: set[str] = set()
    declared: set[str] = set()
    for node in _own_code(nodes):
        if isinstance(node, (*_FUNCTIONS, ast.ClassDef)):
            stored.add(node.name)
        elif isinstance(node, _COMPREHENSIONS):
            stored.update(sub.target.id for sub in ast.walk(node) if isinstance(sub, ast.NamedExpr))
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            imported.update(alias.asname or alias.name.split(".")[0] for alias in node.names if alias.name != "*")
        elif isinstance(node, ast.Global):
            declared.update(node.names)
        elif isinstance(node, ast.Nonlocal):
            stored.update(node.names)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            stored.add(node.id)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            stored.add(node.name)
        elif isinstance(node, (ast.MatchAs, ast.MatchStar)) and node.name:
            stored.add(node.name)
        elif isinstance(node, ast.MatchMapping) and node.rest:
            stored.add(node.rest)
    return stored, imported, declared


def _parameters(arguments: ast.arguments) -> list[ast.arg]:
    every = [*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs, arguments.vararg, arguments.kwarg]
    return [one for one in every if one is not None]


def _globals_key(node: ast.AST) -> str | None:
    """The name in ``globals()["name"]`` or ``globals().get("name")``."""
    if isinstance(node, ast.Subscript):
        holder, key = node.value, node.slice
    elif (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
          and node.func.attr in ("get", "setdefault", "pop") and node.args):
        holder, key = node.func.value, node.args[0]
    else:
        return None
    if (isinstance(holder, ast.Call) and isinstance(holder.func, ast.Name) and holder.func.id == "globals"
            and not holder.args and isinstance(key, ast.Constant) and isinstance(key.value, str)):
        return key.value
    return None


# A scope as the read walk sees it: its kind, the names it binds, the names it
# declares global.
_Scope = tuple[str, frozenset, frozenset]


def _reads_the_global(name: str, scopes: tuple[_Scope, ...]) -> bool:
    """Whether a read of ``name`` in the innermost of ``scopes`` reads the
    module's global, by Python's rules (a class's names are seen only by the
    class body itself)."""
    for depth, (kind, bound, declared) in enumerate(reversed(scopes)):
        if kind == "module" or name in declared:
            return True
        if kind == "class" and depth > 0:
            continue
        if name in bound:
            return False
    return True


def global_reads(tree: ast.Module) -> set[str]:
    """Every name the module's own code reads as a global, annotations left out."""
    reads: set[str] = set()
    pending: list[tuple[ast.AST, tuple[_Scope, ...]]] = [(tree, (("module", frozenset(), frozenset()),))]

    def scope_of(kind: str, body: list[ast.AST], also: set[str] = frozenset()) -> _Scope:
        stored, imported, declared = _own_bindings(body)
        return kind, frozenset((stored | imported | set(also)) - declared), frozenset(declared)

    while pending:
        node, scopes = pending.pop()
        if isinstance(node, ast.Name):
            if isinstance(node.ctx, ast.Load) and _reads_the_global(node.id, scopes):
                reads.add(node.id)
            continue
        key = _globals_key(node)
        if key is not None and not (isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Store)):
            reads.add(key)
        if isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name):
            if _reads_the_global(node.target.id, scopes):
                reads.add(node.target.id)
        if isinstance(node, (*_FUNCTIONS, ast.Lambda)):
            arguments = node.args
            outside = [*getattr(node, "decorator_list", []), *arguments.defaults,
                       *(value for value in arguments.kw_defaults if value is not None)]
            pending.extend((one, scopes) for one in outside)
            body = node.body if isinstance(node.body, list) else [node.body]
            inner = (*scopes, scope_of("function", body, {one.arg for one in _parameters(arguments)}))
            pending.extend((one, inner) for one in body)
            continue
        if isinstance(node, ast.ClassDef):
            outside = [*node.decorator_list, *node.bases, *(keyword.value for keyword in node.keywords)]
            pending.extend((one, scopes) for one in outside)
            inner = (*scopes, scope_of("class", node.body))
            pending.extend((one, inner) for one in node.body)
            continue
        if isinstance(node, _COMPREHENSIONS):
            first = node.generators[0]
            pending.append((first.iter, scopes))
            targets = {sub.id for one in node.generators for sub in ast.walk(one.target) if isinstance(sub, ast.Name)}
            inner = (*scopes, ("function", frozenset(targets), frozenset()))
            parts = [*first.ifs, *(part for one in node.generators[1:] for part in (one.iter, *one.ifs))]
            parts += [node.key, node.value] if isinstance(node, ast.DictComp) else [node.elt]
            pending.extend((one, inner) for one in parts)
            continue
        if isinstance(node, ast.AnnAssign):
            pending.extend((one, scopes) for one in (node.target, node.value) if one is not None)
            continue
        if isinstance(node, ast.arg):
            continue
        pending.extend((child, scopes) for child in ast.iter_child_nodes(node))
    return reads


@dataclass(frozen=True)
class ModuleNames:
    """What one module does with its top-level names."""

    defined: frozenset[str]
    read: frozenset[str]

    def mark(self, name: str) -> str:
        if name in self.defined:
            return DEFINED
        return IMPORTED if name in self.read else UNREAD


def module_names(source: str, filename: str = "<module>") -> ModuleNames:
    """Which names a module defines, and which its code reads."""
    tree = ast.parse(source, filename)
    defined, _imported, _declared = _own_bindings(tree.body)
    for node in ast.walk(tree):
        if isinstance(node, _FUNCTIONS):
            declared = {name for sub in ast.walk(node) if isinstance(sub, ast.Global) for name in sub.names}
            defined |= {sub.id for sub in ast.walk(node)
                        if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Store) and sub.id in declared}
        elif isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Store) and _globals_key(node):
            defined.add(_globals_key(node))
    return ModuleNames(frozenset(defined), frozenset(global_reads(tree)))


# ------------------------------------------------------- what the tests name ----

# What an expression in a test can hold, as far as the tool follows it: a
# module of the repository (by its dotted name), a folder of the repository
# that holds modules but has no ``__init__.py`` (a namespace package, as
# ``tests`` and ``tools`` are), a string, something outside the repository (a
# builtin among them), a class the tool sees defined or an instance of one, a
# thing the tool can prove is no module (a constant that is not a string, a
# literal container, what a builtin or an outside library gives), or a value
# the tool cannot work out. A value is ``(kind, what)``.
MODULE, TEXT, OUTSIDE, THING, UNKNOWN = "module", "text", "outside", "thing", "unknown"
CLASS, INSTANCE = "class", "instance"
PACKAGE = "package"
_A_THING = (THING, None)

#: The name slot of a target the tool cannot place: which name the stand-in
#: replaces is not read, since the target fails the check whatever it is.
_NAME_NOT_READ = (UNKNOWN, None)

#: The kinds a stand-in's target may have and pass unlisted: each is proved no
#: module, so the stand-in lands on that object whoever reads it. "No module"
#: is something the tool proves, never its fallback: every other target fails
#: the check.
_NO_MODULE = (OUTSIDE, THING, CLASS, INSTANCE)

#: The calls whose one argument a loop walks as written, the calls that
#: import the module their one argument names, and the builtins that can give
#: a module the tool does not follow (every other builtin's result is no module).
_SEQUENCE_CALLS = ("sorted", "list", "tuple", "set", "reversed")
_IMPORT_CALLS = ("import_module", "importorskip")
_GIVE_A_MODULE = frozenset(f"builtins.{name}" for name in (
    "getattr", "vars", "__import__", "globals", "locals", "eval", "next", "min", "max"))

#: The fixtures pytest gives, and those of the one plugin the locks install
#: (pytest-xdist): what each gives comes from outside the repository, so it is
#: no module. A fixture the suite defines is looked for first, where pytest
#: looks; a name found neither there nor here is a fixture the tool did not
#: find, and is not followed.
_OUTSIDE_FIXTURES = frozenset((
    "cache", "capfd", "capfdbinary", "caplog", "capsys", "capsysbinary", "capteesys", "doctest_namespace",
    "monkeypatch", "pytestconfig", "record_property", "record_testsuite_property", "record_xml_attribute",
    "recwarn", "request", "subtests", "tmp_path", "tmp_path_factory", "tmpdir", "tmpdir_factory",
    "testrun_uid", "worker_id",
))


def _no_module(node: ast.AST, module: str = "", callee: tuple | None = None) -> tuple:
    """The one place the tool concludes that a value is no module (ruling 009
    of J4), from the syntax it is handed: a constant that is not a string, a
    literal container, a ``class`` the tool sees defined in ``module``, what a
    call makes of a class (``callee`` the class) or gives from a builtin
    outside :data:`_GIVE_A_MODULE` or an outside library (``callee`` that), and
    what a fixture parameter gives that no file of the suite defines, where
    its name is one of :data:`_OUTSIDE_FIXTURES`. Anything
    else it is handed is a value the tool cannot work out, and every other
    path of the tool follows a value or gives that, so "no module" is never
    reached by a fallback. ``test_patch_sites`` holds the tool to building
    the no-module kinds here and nowhere else."""
    if isinstance(node, ast.Constant) and not isinstance(node.value, str):
        return _A_THING
    if isinstance(node, (ast.List, ast.Tuple, ast.Dict, ast.Set)):
        return _A_THING
    if isinstance(node, ast.ClassDef):
        return (CLASS, f"{module}.{node.name}")
    if isinstance(node, ast.Call) and callee is not None:
        kind, held = callee
        if kind == CLASS:
            return (INSTANCE, held)
        if kind == OUTSIDE and held not in _GIVE_A_MODULE:
            return _A_THING
    if isinstance(node, ast.arg):
        return _A_THING if node.arg in _OUTSIDE_FIXTURES else (UNKNOWN, node.arg)
    return (UNKNOWN, ast.unparse(node))


_SCOPES = (ast.Module, *_FUNCTIONS, ast.Lambda)
_BUILTINS = frozenset(dir(builtins))
_LITERALS = (ast.Constant, ast.JoinedStr, ast.List, ast.Tuple, ast.Dict, ast.Set)


def _named(call: ast.AST) -> str:
    """The last part of the name a call or a decorator is written with: ``fixture`` for ``@pytest.fixture(...)``."""
    called = call.func if isinstance(call, ast.Call) else call
    return called.attr if isinstance(called, ast.Attribute) else getattr(called, "id", "")


def _fixture_decorator(function: ast.AST) -> ast.expr | None:
    """The ``@pytest.fixture`` (or ``@pytest.fixture(...)``) on ``function``."""
    for decorator in getattr(function, "decorator_list", []):
        if _named(decorator) == "fixture":
            return decorator
    return None


def _fixture_name(function: ast.AST, decorator: ast.expr) -> str | None:
    """The name pytest knows the fixture ``function`` by: its ``name=``, or
    else the name it is defined under; None where ``name=`` is not a string
    written out."""
    given = _argument(decorator, None, "name") if isinstance(decorator, ast.Call) else None
    if given is None:
        return function.name
    return given.value if isinstance(given, ast.Constant) and isinstance(given.value, str) else None


def _argument(call: ast.Call, at: int | None, keyword: str) -> ast.expr | None:
    """The argument ``call`` gives by ``keyword``, or else at position ``at``
    (None for a keyword-only one)."""
    for one in call.keywords:
        if one.arg == keyword:
            return one.value
    return call.args[at] if at is not None and len(call.args) > at else None


def _strings(expr: ast.AST | None) -> list[str] | None:
    """The strings a literal list or tuple of strings holds, or None."""
    if isinstance(expr, (ast.List, ast.Tuple)) and all(
            isinstance(one, ast.Constant) and isinstance(one.value, str) for one in expr.elts):
        return [one.value for one in expr.elts]
    return None


def _argnames(mark: ast.Call) -> list[str] | None:
    """The names a ``parametrize`` mark gives, where they are written out."""
    given = _argument(mark, 0, "argnames")
    if isinstance(given, ast.Constant) and isinstance(given.value, str):
        return [one.strip() for one in given.value.split(",") if one.strip()]
    return _strings(given)


def _indirect(mark: ast.Call, names: list[str]) -> set[str] | None:
    """The names a ``parametrize`` mark hands to their fixtures (``indirect=``),
    or None where that is not written out."""
    given = _argument(mark, 2, "indirect")
    if given is None:
        return set()
    if isinstance(given, ast.Constant) and isinstance(given.value, bool):
        return set(names) if given.value else set()
    listed = _strings(given)
    return None if listed is None else set(listed)


def _a_placeholder(parent: dict[ast.AST, ast.AST], node: ast.AST) -> bool:
    """Whether ``node`` binds a top-level name to a constant that is not a
    string (``ENGINE = None``): a placeholder for a seam another module fills."""
    holder = parent.get(node)
    value = holder.value if isinstance(holder, (ast.Assign, ast.AnnAssign)) else None
    return isinstance(node, ast.Name) and isinstance(value, ast.Constant) and not isinstance(value.value, str)


class _Suite:
    """The repository's modules and the files under ``tests/``, each parsed once."""

    def __init__(self, root: Path):
        self.root = root
        self.index = module_index(root)
        # The folders that hold a module but are none themselves: ``tests``
        # and ``tools`` have no ``__init__.py``, and ``import tests.children``
        # reaches a module through one.
        self.packages = frozenset(".".join(dotted.split(".")[:cut]) for dotted in self.index
                                  for cut in range(1, dotted.count(".") + 1)) - set(self.index)
        # A tool imported by its bare name is reported by its dotted one.
        self._dotted: dict[Path, str] = {}
        for dotted, path in self.index.items():
            if dotted.count(".") >= self._dotted.get(path, "").count("."):
                self._dotted[path] = dotted
        self._names: dict[str, ModuleNames] = {}
        self._files: dict[Path, _TestFile] = {}
        self._stored: frozenset[tuple[str, str]] | None = None

    def canonical(self, dotted: str) -> str:
        """A module's dotted name from the root, however the test imported it."""
        return self._dotted[self.index[dotted]]

    def canonical_of(self, path: Path) -> str:
        """The dotted name a module of the repository is reported by."""
        return self._dotted.get(path, ".".join(path.relative_to(self.root).with_suffix("").parts))

    def module(self, dotted: str) -> tuple:
        """What importing ``dotted`` gives: a module of the repository, a
        folder of it that holds one (:attr:`packages`), or something outside
        the repository. This is the one place the tool takes a value for
        outside the repository, and it does so only for a name that is
        neither, which ``test_patch_sites`` holds it to: a module reached
        through ``tests.`` or ``tools.`` is followed, not passed unlisted."""
        if dotted in self.index:
            return (MODULE, self.canonical(dotted))
        if dotted in self.packages:
            return (PACKAGE, dotted)
        return (OUTSIDE, dotted)

    def names(self, module: str) -> ModuleNames:
        if module not in self._names:
            path = self.index[module]
            self._names[module] = module_names(path.read_text(encoding="utf-8"), str(path))
        return self._names[module]

    def test_file(self, path: Path) -> _TestFile:
        if path not in self._files:
            self._files[path] = _TestFile(self, path)
        return self._files[path]

    def test_files(self) -> list[_TestFile]:
        """Every file under ``tests/``."""
        return [self.test_file(path) for path in sorted((self.root / TESTS).rglob("*.py"))
                if "__pycache__" not in path.parts]

    def conftests_for(self, path: Path) -> list[_TestFile]:
        """The conftests pytest gives the file at ``path``: the one in its own
        folder and the one in each folder above it, up to the repository's
        root, nearest first. A conftest in another branch of ``tests/`` is
        not among them."""
        found = []
        for folder in path.parents:
            conftest = folder / "conftest.py"
            if conftest != path and conftest.is_file():
                found.append(self.test_file(conftest))
            if folder == self.root:
                break
        return found

    def suite_files(self) -> list[_TestFile]:
        """Every file of the suite's own Python: each file under ``tests/``,
        and the conftest at the repository's root, which pytest loads too."""
        return [*self.test_files(), *self.conftests_for(self.root / TESTS)]

    @cached_property
    def handed_on(self) -> frozenset[str] | None:
        """Every name a ``parametrize`` call in the suite hands to its fixture
        (``indirect``), which then gives the call's values as
        ``request.param`` in place of its own ``params``. A call whose
        ``indirect`` is not written out hands on every name it gives, and
        None means some call's names are not written out, so that any
        fixture may be handed values the tool does not see."""
        names: set[str] = set()
        for test_file in self.suite_files():
            for node in ast.walk(test_file.tree):
                if not (isinstance(node, ast.Call) and _named(node) == "parametrize"):
                    continue
                given = _argnames(node)
                if given is None:
                    return None
                indirect = _indirect(node, given)
                names |= set(given) if indirect is None else indirect
        return frozenset(names)

    def stored(self) -> frozenset[tuple[str, str]]:
        """Each (module, name) that a file of the repository stores in a module
        of the repository through the module: an assignment to
        ``<module>.<name>``, an augmented one or a ``del``, a stand-in, or the
        builtin ``setattr``. While this is worked out it is empty, so what a
        store is aimed at is read from the modules alone."""
        if self._stored is None:
            self._stored = frozenset()
            self._stored = frozenset(key for path in sorted(set(self.index.values()))
                                     for node in ast.walk(self.test_file(path).tree)
                                     for key in self.test_file(path).stores(node))
        return self._stored

    @staticmethod
    def base(statement: ast.ImportFrom, importer: str) -> str:
        """The module a ``from ... import`` in the module ``importer`` imports from."""
        base = statement.module or ""
        if statement.level:
            package = importer.split(".")[: -statement.level]
            base = ".".join([*package, base] if base else package)
        return base

    def imported(self, statement: ast.AST, alias: ast.alias, importer: str, seen: frozenset = frozenset()) -> list[tuple]:
        """What an import statement in the module ``importer`` binds to ``alias``'s name."""
        if isinstance(statement, ast.Import):
            return [self.module(alias.name if alias.asname else alias.name.split(".")[0])]
        base = self.base(statement, importer)
        return self.attribute(self.module(base), alias.name, f"{base}.{alias.name}", seen)

    def attribute(self, value: tuple, attr: str, written: str, seen: frozenset = frozenset()) -> list[tuple]:
        """What ``<value>.<attr>`` can hold, written as ``written``.

        Of a module of the repository: its submodule, or what the module binds
        to the name at its top level, followed in that module's own code (an
        import, a ``class`` or an assignment; a ``def`` is not followed). Of a
        folder with no ``__init__.py``: its module or folder of that name, and
        anything else is not followed (nothing but a run can have put it
        there). Of something outside the repository: what :meth:`module`
        makes of the dotted name, so the index is looked in before a name is
        taken for outside. Anything else - a class's attribute, an instance's,
        a function's, a string's method, an attribute of what a builtin or an
        outside library gave - may hold a module, so it is not followed."""
        kind, held = value
        if kind == MODULE or kind == PACKAGE or kind == OUTSIDE:
            found = self.module(f"{held}.{attr}")
            if found[0] != OUTSIDE or kind == OUTSIDE:
                return [found]
            if kind == PACKAGE:
                return [(UNKNOWN, written)]
            return self.test_file(self.index[held]).top_level(attr, written, seen)
        return [value if kind == UNKNOWN else (UNKNOWN, written)]


class _TestFile:
    """One file the tool follows values in: its tree, each node's parent, its
    scopes. A file under ``tests/``, or a module of the repository whose
    top-level name a test reads through it (``helpers.THE_SORTER``)."""

    def __init__(self, suite: _Suite, path: Path):
        self.suite = suite
        self.path = path
        self.relative = path.relative_to(suite.root).as_posix()
        self.dotted = ".".join(path.relative_to(suite.root).with_suffix("").parts)
        self.canonical = suite.canonical_of(path)
        self.tree = ast.parse(path.read_text(encoding="utf-8"), self.relative)
        self.parent: dict[ast.AST, ast.AST] = {}
        self.calls: dict[str, list[ast.Call]] = defaultdict(list)
        for node in ast.walk(self.tree):
            for child in ast.iter_child_nodes(node):
                self.parent[child] = node
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                self.calls[node.func.id].append(node)
        self._bound: dict[ast.AST, dict[str, list[ast.AST]]] = {}
        self._nonlocal: dict[ast.AST, frozenset[str]] = {}
        # The top-level names a function rebinds with ``global``, or that are
        # set through ``globals()``: what they hold is not their top-level value.
        self.rebound = {name for node in ast.walk(self.tree) if isinstance(node, ast.Global) for name in node.names}
        self.rebound |= {_globals_key(node) for node in ast.walk(self.tree)
                         if isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Store) and _globals_key(node)}

    # -- where a name is bound

    def chain(self, node: ast.AST) -> list[ast.AST]:
        """The scopes ``node`` sits in, innermost first."""
        found = []
        while node in self.parent:
            node = self.parent[node]
            if isinstance(node, _SCOPES):
                found.append(node)
        return found

    def classes_around(self, node: ast.AST) -> list[ast.ClassDef]:
        """The classes ``node`` sits in, innermost first."""
        found = []
        while node in self.parent:
            node = self.parent[node]
            if isinstance(node, ast.ClassDef):
                found.append(node)
        return found

    def bound_in(self, scope: ast.AST) -> dict[str, list[ast.AST]]:
        """Each name bound directly in ``scope`` (the module, a function, a
        lambda or a class body), with the nodes that bind it: an ``ast.arg``,
        an ``ast.alias``, a stored ``ast.Name``, a ``def`` or a ``class``."""
        if scope not in self._bound:
            bound: dict[str, list[ast.AST]] = defaultdict(list)
            for one in [] if isinstance(scope, (ast.Module, ast.ClassDef)) else _parameters(scope.args):
                bound[one.arg].append(one)
            for node in _own_code(scope.body if isinstance(scope.body, list) else [scope.body]):
                if isinstance(node, (*_FUNCTIONS, ast.ClassDef)):
                    bound[node.name].append(node)
                elif isinstance(node, (ast.Import, ast.ImportFrom)):
                    for alias in node.names:
                        bound[alias.asname or alias.name.split(".")[0]].append(alias)
                elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                    bound[node.id].append(node)
            self._bound[scope] = dict(bound)
        return self._bound[scope]

    def binding(self, name: str, at: ast.AST) -> tuple[ast.AST | None, list[ast.AST]]:
        """The innermost scope around ``at`` that binds ``name``, and the nodes that bind it there."""
        for scope in self.chain(at):
            found = self.bound_in(scope).get(name)
            if found:
                return scope, found
        return None, []

    def binders(self, name: str, at: ast.AST) -> list[ast.AST]:
        """The nodes that bind ``name`` in the innermost scope around ``at`` that binds it."""
        return self.binding(name, at)[1]

    def shared(self, name: str, scope: ast.AST | None) -> bool:
        """Whether ``name``, bound in the function ``scope``, is one that a
        function inside it, or the function itself, declares ``nonlocal``:
        the name is then rebound in another scope, at a time the tool does
        not know, so what it holds is not followed (as :meth:`rebinds` does
        for a top-level name)."""
        if scope is None or isinstance(scope, ast.Module):
            return False
        if scope not in self._nonlocal:
            self._nonlocal[scope] = frozenset(name for node in ast.walk(scope) if isinstance(node, ast.Nonlocal)
                                              for name in node.names)
        return name in self._nonlocal[scope]

    def rebinds(self, name: str) -> bool:
        """Whether this file's top-level ``name`` is bound anywhere but its top
        level: by a function of the file (``global``, ``globals()``), or
        through the module, by an assignment or a ``setattr`` in any file
        (:meth:`_Suite.stored`)."""
        return name in self.rebound or (self.canonical, name) in self.suite.stored()

    def top_level(self, name: str, written: str, seen: frozenset) -> list[tuple]:
        """What this file's top-level ``name`` can hold, read from another
        file as ``written``. A name the file never binds at its top level is
        not followed."""
        bound = self.bound_in(self.tree).get(name)
        if not bound:
            return [(UNKNOWN, written)]
        return self.module_level(name, written, bound, seen)

    def module_level(self, name: str, written: str, bound: list[ast.AST], seen: frozenset) -> list[tuple]:
        """What this file's top-level ``name``, bound there by ``bound``, can
        hold wherever it is read, in this file or another: each binding's
        value, followed only where nothing rebinds the name (:meth:`rebinds`).
        A binding to a constant other than a string is not followed either: it
        is a placeholder for a seam, which another module may fill in a way
        the tool does not see."""
        if self.rebinds(name):
            return [(UNKNOWN, written)]
        placeholders = [node for node in bound if _a_placeholder(self.parent, node)]
        followed = [node for node in bound if node not in placeholders]
        found = [(UNKNOWN, written)] if placeholders else []
        if followed:
            found += self._bound_values(name, followed, seen)
        return found

    def stores(self, node: ast.AST) -> list[tuple[str, str]]:
        """Each (module, name) that ``node`` stores in a module of the
        repository through the module: an assignment to ``<module>.<name>``,
        an augmented one or a ``del``, a stand-in, or the builtin ``setattr``."""
        if isinstance(node, ast.Attribute) and isinstance(node.ctx, (ast.Store, ast.Del)):
            return [(held, node.attr) for kind, held in self.values(node.value, {}) if kind == MODULE]
        if isinstance(node, ast.Call) and _named(node) == "setattr":
            ways, _written = _aimed_at(self, node)
            return [(held, name) for (kind, held), (name_kind, name) in ways if kind == MODULE and name_kind == TEXT]
        return []

    # -- what an expression holds

    def values(self, expr: ast.AST, env: dict[str, list[tuple]], seen: frozenset = frozenset()) -> list[tuple]:
        """Every value ``expr`` can hold, with the names in ``env`` fixed."""
        if isinstance(expr, ast.Constant):
            return [(TEXT, expr.value) if isinstance(expr.value, str) else _no_module(expr)]
        if isinstance(expr, ast.Name):
            if self.shared(expr.id, self.binding(expr.id, expr)[0]):
                return [(UNKNOWN, expr.id)]
            return env[expr.id] if expr.id in env else self._held_by(expr, seen)
        if isinstance(expr, ast.Attribute):
            if isinstance(expr.value, ast.Name) and expr.value.id == "request" and expr.attr == "param":
                return self._fixture_params(expr, seen)
            written = ast.unparse(expr)
            return [value for one in self.values(expr.value, env, seen)
                    for value in self.suite.attribute(one, expr.attr, written, seen)]
        if isinstance(expr, ast.JoinedStr):
            return self._joined(expr, env, seen)
        if isinstance(expr, ast.Call):
            return self._called(expr, env, seen)
        if isinstance(expr, ast.Subscript):
            if isinstance(expr.value, ast.Attribute) and expr.value.attr == "modules":
                return [self._module_named(one) for one in self.values(expr.slice, env, seen)]
            return [(UNKNOWN, ast.unparse(expr))]
        if isinstance(expr, (ast.List, ast.Tuple, ast.Dict, ast.Set)):
            return [_no_module(expr)]
        # Anything else - ``a or b``, a lambda, arithmetic, a comparison, a
        # comprehension - is not followed.
        return [(UNKNOWN, ast.unparse(expr))]

    def _called(self, call: ast.Call, env, seen) -> list[tuple]:
        """What a call gives: the module an import call names, the module
        ``reload`` is given, the module ``sys.modules.get`` names (as
        ``sys.modules[...]`` does), an instance of a class the tool sees
        defined, and no module from a builtin or from anything outside the
        repository. A function - a ``def`` or a ``lambda``, in the test file
        or in another module of the repository - can return a module, and so
        can a method, an instance, and ``getattr``, ``vars``, ``__import__``
        and the other builtins of :data:`_GIVE_A_MODULE` however they are
        reached, so a call to any of them is not followed, nor is a call to
        anything else the tool cannot work out."""
        func = call.func
        called = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
        if called in _IMPORT_CALLS and len(call.args) == 1:
            return [self._module_named(one) for one in self.values(call.args[0], env, seen)]
        if called == "reload" and len(call.args) == 1:
            return self.values(call.args[0], env, seen)
        if (called == "get" and isinstance(func, ast.Attribute) and isinstance(func.value, ast.Attribute)
                and func.value.attr == "modules" and len(call.args) in (1, 2)):
            given = [self._module_named(one) for one in self.values(call.args[0], env, seen)]
            return given + [value for default in call.args[1:] for value in self.values(default, env, seen)]
        return [_no_module(call, callee=value) for value in self.values(func, env, seen)]

    def _module_named(self, value: tuple) -> tuple:
        kind, held = value
        if kind == TEXT:
            return self.suite.module(held)
        return value if kind == UNKNOWN else (UNKNOWN, "a module named by something not a string")

    def _joined(self, expr: ast.JoinedStr, env, seen) -> list[tuple]:
        parts: list[list[str]] = []
        for piece in expr.values:
            if isinstance(piece, ast.Constant):
                parts.append([piece.value])
                continue
            said = self.values(piece.value, env, seen)
            if any(kind != TEXT for kind, _ in said):
                return [(UNKNOWN, ast.unparse(expr))]
            parts.append([text for _, text in said])
        return [(TEXT, "".join(row)) for row in itertools.product(*parts)]

    def _fixture_params(self, at: ast.AST, seen) -> list[tuple]:
        """What ``request.param`` holds at ``at``: the ``params`` of the
        fixture it is read in, where they are written out. A fixture that a
        ``parametrize`` mark anywhere in the suite may hand values to
        (``indirect``) is not followed: pytest gives it the mark's values as
        ``request.param`` in place of its own ``params``, for a test that
        asks for it or for one that reaches it through another fixture."""
        for scope in self.chain(at):
            decorator = _fixture_decorator(scope)
            if decorator is None:
                continue
            handed_on, name = self.suite.handed_on, _fixture_name(scope, decorator)
            given = _argument(decorator, None, "params") if isinstance(decorator, ast.Call) else None
            items = None if given is None else self.items(given, seen)
            if handed_on is None or name is None or name in handed_on or items is None:
                break
            return [value for item in items for value in self.values(item, {}, seen)]
        return [(UNKNOWN, "request.param")]

    def _held_by(self, expr: ast.Name, seen) -> list[tuple]:
        scope, bound = self.binding(expr.id, expr)
        if not bound:
            # A builtin is outside the repository. Any other name the file
            # never binds (a comprehension's variable, a star import's) is not
            # followed.
            return [self.suite.module(f"builtins.{expr.id}")] if expr.id in _BUILTINS else [(UNKNOWN, expr.id)]
        if isinstance(scope, ast.Module):
            return self.module_level(expr.id, expr.id, bound, seen)
        return self._bound_values(expr.id, bound, seen)

    def _bound_values(self, name: str, bound: list[ast.AST], seen) -> list[tuple]:
        """What ``name`` can hold, bound by the nodes ``bound``."""
        if any(id(node) in seen for node in bound):
            return [(UNKNOWN, name)]
        seen = seen | {id(node) for node in bound}
        found: list[tuple] = []
        for node in bound:
            if isinstance(node, ast.alias):
                found.extend(self.suite.imported(self.parent[node], node, self.dotted, seen))
            elif isinstance(node, ast.arg):
                _source, rows = self.parameter_rows(node, seen)
                found.extend(value for row in rows for value in row[node.arg])
            elif isinstance(node, ast.Name):
                found.extend(self._stored(node, seen))
            elif isinstance(node, ast.ClassDef):
                found.append(_no_module(node, self.dotted))
            else:
                # A function, or whatever its decorators made of it.
                found.append((UNKNOWN, f"{self.dotted}.{node.name}"))
        return found

    def _stored(self, target: ast.Name, seen) -> list[tuple]:
        """What a name holds where ``target`` stores it: the value of a plain
        or annotated assignment, or a ``for``'s values. Any other store (an
        unpacking, a walrus, ``with ... as``, an augmented assignment, an
        annotation with no value) is not followed, so a module stored that
        way fails the check rather than passing as no module."""
        holder = self.parent[target]
        if isinstance(holder, ast.Assign) and holder.targets == [target]:
            return self.values(holder.value, {}, seen)
        if isinstance(holder, ast.AnnAssign) and holder.target is target and holder.value is not None:
            return self.values(holder.value, {}, seen)
        loop = self.loop_of(target)
        if loop is None:
            return [(UNKNOWN, target.id)]
        rows = self.loop_rows(loop, seen)
        if rows is None:
            return [(UNKNOWN, ast.unparse(loop.iter))]
        return [value for row in rows for value in row[target.id]]

    # -- loops and parameters

    def loop_of(self, target: ast.Name) -> ast.For | None:
        """The ``for`` whose target ``target`` is, or is inside."""
        node = target
        while node in self.parent:
            holder = self.parent[node]
            if isinstance(holder, (ast.For, ast.AsyncFor)) and holder.target is node:
                return holder
            if not isinstance(holder, (ast.Tuple, ast.List)):
                return None
            node = holder
        return None

    def enclosing_loop(self, name: str, at: ast.AST) -> ast.For | None:
        """The innermost ``for`` in ``at``'s own scope whose body holds
        ``at`` and whose target binds ``name``."""
        node = at
        while node in self.parent:
            holder = self.parent[node]
            if isinstance(holder, _SCOPES):
                return None
            if (isinstance(holder, (ast.For, ast.AsyncFor)) and node is not holder.iter and node is not holder.target
                    and any(isinstance(one, ast.Name) and one.id == name for one in ast.walk(holder.target))):
                return holder
            node = holder
        return None

    def items(self, expr: ast.AST, seen) -> list[ast.AST] | None:
        """The elements a ``for`` over ``expr`` walks, where they are written out."""
        if isinstance(expr, (ast.Tuple, ast.List, ast.Set)):
            return list(expr.elts)
        if isinstance(expr, ast.Dict):
            return [key for key in expr.keys if key is not None]
        if isinstance(expr, _COMPREHENSIONS):
            element = expr.key if isinstance(expr, ast.DictComp) else expr.elt
            [generator, *more] = expr.generators
            if (not more and not generator.ifs and isinstance(element, ast.Name)
                    and isinstance(generator.target, ast.Name) and generator.target.id == element.id):
                return self.items(generator.iter, seen)
            return None
        if (isinstance(expr, ast.Call) and isinstance(expr.func, ast.Name) and expr.func.id in _SEQUENCE_CALLS
                and len(expr.args) == 1 and not expr.keywords):
            return self.items(expr.args[0], seen)
        if isinstance(expr, ast.Name):
            scope, bound = self.binding(expr.id, expr)
            if (isinstance(scope, ast.Module) and self.rebinds(expr.id)) or self.shared(expr.id, scope):
                return None
            if (len(bound) == 1 and isinstance(bound[0], ast.Name) and id(bound[0]) not in seen
                    and isinstance(self.parent.get(bound[0]), ast.Assign) and self.parent[bound[0]].targets == bound):
                return self.items(self.parent[bound[0]].value, seen | {id(bound[0])})
        return None

    def loop_rows(self, loop: ast.For, seen) -> list[dict[str, list[tuple]]] | None:
        """The names ``loop`` binds, one row per pass, or None where its
        elements are not written out."""
        items = self.items(loop.iter, seen)
        if items is None:
            return None
        rows = [self._unpack(loop.target, item, seen) for item in items]
        return None if any(row is None for row in rows) else rows

    def _unpack(self, target: ast.AST, item: ast.AST, seen) -> dict[str, list[tuple]] | None:
        if isinstance(target, ast.Name):
            return {target.id: self.values(item, {}, seen)}
        if (isinstance(target, (ast.Tuple, ast.List)) and isinstance(item, (ast.Tuple, ast.List))
                and len(target.elts) == len(item.elts)):
            row: dict[str, list[tuple]] = {}
            for one, value in zip(target.elts, item.elts, strict=True):
                inner = self._unpack(one, value, seen)
                if inner is None:
                    return None
                row.update(inner)
            return row
        return None

    def parameter_rows(self, parameter: ast.arg, seen) -> tuple[ast.AST, list[dict[str, list[tuple]]]]:
        """What fixes ``parameter``, and its values, one row per way.

        A helper's parameters are fixed together, by each of its calls in this
        file, so the rows hold every parameter and the helper is the source. A
        test's parameter that a ``parametrize`` mark names is fixed by the
        mark, with the names it gives together. Any other parameter of a test
        or a fixture is a fixture, fixed alone."""
        function = self.parent[self.parent[parameter]]
        unknown = (parameter, [{parameter.arg: [(UNKNOWN, parameter.arg)]}])
        if isinstance(function, ast.Lambda):
            return unknown
        if _fixture_decorator(function) or function.name.startswith("test_"):
            marked = self._parametrized(parameter, function, seen)
            if marked is not None:
                return marked
            return parameter, [{parameter.arg: self._fixture_values(parameter, function, seen)}]
        rows = [row for call in self.calls.get(function.name, [])
                if (row := self._arguments(function, call, seen)) is not None]
        return (function, rows) if rows else unknown

    def _arguments(self, function, call: ast.Call, seen) -> dict[str, list[tuple]] | None:
        arguments = function.args
        positional = [*arguments.posonlyargs, *arguments.args]
        defaults = {one.arg: value for one, value in zip(positional[len(positional) - len(arguments.defaults):],
                                                          arguments.defaults, strict=True)}
        defaults |= {one.arg: value for one, value in zip(arguments.kwonlyargs, arguments.kw_defaults, strict=True)
                     if value is not None}
        if any(isinstance(value, ast.Starred) for value in call.args) or any(kw.arg is None for kw in call.keywords):
            return None
        given = dict(zip((one.arg for one in positional), call.args, strict=False))
        given |= {keyword.arg: keyword.value for keyword in call.keywords}
        row = {}
        for one in [*positional, *arguments.kwonlyargs]:
            value = given.get(one.arg, defaults.get(one.arg))
            row[one.arg] = self.values(value, {}, seen) if value is not None else [(UNKNOWN, one.arg)]
        return row

    def _parametrize_marks(self, function: ast.AST) -> list[ast.Call] | None:
        """The ``parametrize`` marks on a test: its own decorators, those of
        the classes around it, and those a ``pytestmark`` assigned in those
        classes or in the file holds. None where a ``pytestmark`` is bound
        some other way, which the tool does not read."""
        classes = self.classes_around(function)
        marks = [decorator for holder in (function, *classes) for decorator in holder.decorator_list
                 if isinstance(decorator, ast.Call) and _named(decorator) == "parametrize"]
        for scope in (*classes, self.tree):
            for node in self.bound_in(scope).get("pytestmark", []):
                holder = self.parent.get(node)
                if not (isinstance(node, ast.Name) and isinstance(holder, (ast.Assign, ast.AnnAssign))
                        and holder.value is not None):
                    return None
                marks += [one for one in ast.walk(holder.value) if isinstance(one, ast.Call) and _named(one) == "parametrize"]
        return marks

    def _parametrized(self, parameter: ast.arg, function: ast.AST, seen):
        """What a ``parametrize`` mark gives a test's ``parameter``: the mark
        as the source, and one row per set of values it lists, holding each
        name the mark gives that set together. None where no mark names the
        parameter. A mark whose names, values or ``indirect`` are not written
        out gives a value the tool does not follow, and so does one that
        hands the parameter to its fixture (``indirect``): pytest gives that
        fixture the mark's values as ``request.param``, and what the fixture
        makes of them is not followed, nor are the fixture's own ``params``
        read in their place."""
        name = parameter.arg
        unknown = (parameter, [{name: [(UNKNOWN, name)]}])
        marks = self._parametrize_marks(function)
        if marks is None:
            return unknown
        for mark in marks:
            names = _argnames(mark)
            if names is None:
                return unknown
            if name not in names:
                continue
            indirect = _indirect(mark, names)
            if indirect is None:
                return unknown
            if name in indirect:
                return unknown
            direct = [one for one in names if one not in indirect]
            argvalues = _argument(mark, 1, "argvalues")
            items = None if argvalues is None else self.items(argvalues, seen)
            if items is None:
                return mark, [{one: [(UNKNOWN, one)] for one in direct}]
            return mark, [self._parametrize_row(names, direct, item, seen) for item in items]
        return None

    def _parametrize_row(self, names: list[str], direct: list[str], item: ast.AST, seen) -> dict[str, list[tuple]]:
        """The values one item of a ``parametrize`` mark's list gives its
        names: the item itself for one name, the elements of a tuple or a
        list for several, and the values of ``pytest.param(...)`` either way."""
        if isinstance(item, ast.Call) and _named(item) == "param":
            elements = item.args
        elif len(names) == 1:
            elements = [item]
        else:
            elements = item.elts if isinstance(item, (ast.Tuple, ast.List)) else []
        if len(elements) != len(names) or any(isinstance(one, ast.Starred) for one in elements):
            return {one: [(UNKNOWN, one)] for one in direct}
        return {one: self.values(value, {}, seen) for one, value in zip(names, elements, strict=True) if one in direct}

    def _fixture_values(self, parameter: ast.arg, function: ast.AST, seen) -> list[tuple]:
        """What the fixture ``parameter`` names gives the test or fixture
        ``function``, found where pytest looks for it: the classes around
        ``function``, this file, then the conftests on this file's own path,
        nearest first (:meth:`_Suite.conftests_for`). A name none of them
        holds is no module only where it is pytest's own fixture or a
        plugin's (:data:`_OUTSIDE_FIXTURES`); any other is not followed."""
        holders = [(self, scope) for scope in (*self.classes_around(function), self.tree)]
        holders += [(conftest, conftest.tree) for conftest in self.suite.conftests_for(self.path)]
        for holder, scope in holders:
            given = holder.fixture_in(scope, parameter.arg, seen)
            if given is not None:
                return given
        return [_no_module(parameter)]

    def fixture_in(self, scope: ast.AST, name: str, seen) -> list[tuple] | None:
        """What the fixture ``name`` gives where ``scope`` (this file's top
        level, or a class in it) holds it, or None where it holds no fixture of
        that name. A fixture is a ``def`` under ``@pytest.fixture``, known by
        its ``name=`` or else by the name it is bound to. A name the scope
        imports or assigns is followed, into another module of the repository
        or to a name of the scope's own (:meth:`_fixture_followed`)."""
        bound = self.bound_in(scope)
        found: list[tuple] = []
        for nodes in bound.values():
            for node in nodes:
                decorator = _fixture_decorator(node) if isinstance(node, _FUNCTIONS) else None
                if decorator is None:
                    continue
                known_as = _fixture_name(node, decorator)
                if known_as is None:
                    return [(UNKNOWN, name)]
                if known_as != name:
                    continue
                if id(node) in seen:
                    return [(UNKNOWN, name)]
                # A bare return or yield, or none, gives None.
                returned = [sub.value or ast.Constant(None) for sub in ast.walk(node)
                            if isinstance(sub, (ast.Return, ast.Yield))] or [ast.Constant(None)]
                found += [value for one in returned for value in self.values(one, {}, seen | {id(node)})]
        if found:
            return found
        for node in bound.get(name, []):
            if isinstance(node, (ast.alias, ast.Name)):
                given = self._fixture_followed(scope, node, name, seen)
                if given is not None:
                    return given
        return None

    def _fixture_followed(self, scope: ast.AST, node: ast.AST, name: str, seen) -> list[tuple] | None:
        """What the fixture ``name`` gives where ``scope`` binds the name by
        ``node``, an import or a store, or None where that binds no fixture.
        ``from <module> import <fixture>`` and ``<name> = <module>.<fixture>``
        are followed into a module of the repository, and ``<name> = <other
        name>`` to the other name; a module, a constant and a literal are no
        fixture. Anything else - an import from outside the repository, a
        call, a store the tool does not read - may be a fixture the tool does
        not follow."""
        if id(node) in seen:
            return [(UNKNOWN, name)]
        seen = seen | {id(node)}
        statement = self.parent[node]
        if isinstance(node, ast.alias):
            if isinstance(statement, ast.Import):
                return None
            base = self.suite.base(statement, self.dotted)
            if f"{base}.{node.name}" in self.suite.index:
                return None
            if base not in self.suite.index:
                return [(UNKNOWN, name)]
            there = self.suite.test_file(self.suite.index[base])
            return there.fixture_in(there.tree, node.name, seen)
        if not (isinstance(statement, (ast.Assign, ast.AnnAssign)) and statement.value is not None
                and (getattr(statement, "target", None) is node or getattr(statement, "targets", None) == [node])):
            return [(UNKNOWN, name)]
        value = statement.value
        if isinstance(value, ast.Name):
            return self.fixture_in(scope, value.id, seen)
        if isinstance(value, _LITERALS):
            return None
        if not isinstance(value, ast.Attribute):
            return [(UNKNOWN, name)]
        found: list[tuple] = []
        for kind, held in self.values(value.value, {}, seen):
            if kind != MODULE:
                return [(UNKNOWN, name)]
            there = self.suite.test_file(self.suite.index[held])
            found += there.fixture_in(there.tree, value.attr, seen) or []
        return found or None


# ----------------------------------------------------------------- the sites ----


def _rows(test_file: _TestFile, call: ast.Call, args: list[ast.AST]) -> list[dict[str, list[tuple]]] | None:
    """Every way the loops and calls that fix the names in ``args`` can fix
    them together, or None where there are more than :data:`MOST_ROWS`."""
    sources: dict[object, list[dict[str, list[tuple]]]] = {}
    for name in (node for arg in args for node in ast.walk(arg) if isinstance(node, ast.Name)):
        loop = test_file.enclosing_loop(name.id, call)
        if loop is not None:
            # The loop the call sits in is the one binding that reaches it.
            sources.setdefault(loop, test_file.loop_rows(loop, frozenset()) or [{}])
            continue
        found: dict[ast.AST, list[dict[str, list[tuple]]]] = {}
        for node in test_file.binders(name.id, call):
            if isinstance(node, ast.arg):
                source, rows = test_file.parameter_rows(node, frozenset())
                found.setdefault(source, rows)
            elif isinstance(node, ast.Name) and (loop := test_file.loop_of(node)):
                found.setdefault(loop, test_file.loop_rows(loop, frozenset()) or [{}])
        if len(found) == 1:
            sources.update(found)
        elif found:
            # A name bound by several loops or helpers is any one of them.
            sources.setdefault(tuple(found), [row for rows in found.values() for row in rows])
    ways = list(itertools.islice(itertools.product(*sources.values()), MOST_ROWS + 1))
    if len(ways) > MOST_ROWS:
        return None
    return [{name: values for row in way for name, values in row.items()} for way in ways]


def _dotted(suite: _Suite, text: str) -> list[tuple[tuple, tuple]]:
    """Every (module, name) the string form ``setattr("tracker.filer.name",
    value)`` replaces: the longest start of the string that names a module of
    the repository (or a folder of it with no ``__init__.py``) is the module,
    the parts after it but the last are its attributes, and the last part is
    the name. A string that names no module of the repository is outside it."""
    parts = text.split(".")
    for cut in range(len(parts) - 1, 0, -1):
        start = suite.module(".".join(parts[:cut]))
        if start[0] != OUTSIDE:
            values = [start]
            for at in range(cut, len(parts) - 1):
                values = [value for one in values for value in suite.attribute(one, parts[at], ".".join(parts[:at + 1]))]
            return [(value, (TEXT, parts[-1])) for value in values]
    return [(suite.module(text), (TEXT, parts[-1]))]


def _string_form(call: ast.Call) -> bool:
    """Whether a ``setattr`` call is the string form: two arguments, and no ``name=`` or ``value=``."""
    return len(call.args) == 2 and not {"name", "value"} & {keyword.arg for keyword in call.keywords}


def _aimed_at(test_file: _TestFile, call: ast.Call) -> tuple[list[tuple[tuple, tuple]], str]:
    """Every (module, name) a ``setattr`` call can replace, and how its
    target is written.

    Two arguments and no ``value=`` is the string form, whose first argument
    pytest requires to be a string: each string it can hold is read as the
    dotted name it is, and any other value it can hold is a string the tool
    cannot read, so it is not placed."""
    args = call.args
    string_form = _string_form(call)
    if string_form and isinstance(args[0], ast.Constant) and isinstance(args[0].value, str):
        return _dotted(test_file.suite, args[0].value), repr(args[0].value)
    written = ast.unparse(args[0]) if args else ast.unparse(call)
    if len(args) < 2:
        return [((UNKNOWN, written), _NAME_NOT_READ)], written
    ways = _rows(test_file, call, args[:2])
    if ways is None:
        return [((UNKNOWN, written), _NAME_NOT_READ)], written
    found: list[tuple[tuple, tuple]] = []
    for env in ways:
        for kind, held in test_file.values(args[0], env):
            if not string_form:
                found.extend(((kind, held), name) for name in test_file.values(args[1], env))
            elif kind == TEXT:
                found.extend(_dotted(test_file.suite, held))
            else:
                found.append(((UNKNOWN, held if kind == UNKNOWN else written), _NAME_NOT_READ))
    return found, written


def _survey(suite: _Suite) -> tuple[set[Site], set[Unplaced], set[tuple[str, int, int]]]:
    """Every stand-in under ``tests/`` aimed at a module of the repository,
    every ``setattr`` the tool could not place, and where each
    ``<x>.setattr`` it read ends (its file, line and column), which the
    backstop (:func:`_unaccounted`) holds the source text to.

    A ``<x>.setattr`` read but not called where it is written (``put =
    monkeypatch.setattr``, or handed to ``functools.partial``) is not placed:
    its arguments are written somewhere the tool does not look. Nor is one
    called on a class or on something outside the repository
    (``MonkeyPatch.setattr(monkeypatch, sorter, ...)``): its first argument
    is then the monkeypatch, and what it replaces comes after."""
    sites: set[Site] = set()
    unplaced: set[Unplaced] = set()
    read: set[tuple[str, int, int]] = set()
    for test_file in suite.test_files():
        for call in ast.walk(test_file.tree):
            if (isinstance(call, ast.Attribute) and call.attr == "setattr" and isinstance(call.ctx, ast.Load)
                    and not (isinstance(test_file.parent.get(call), ast.Call) and test_file.parent[call].func is call)):
                read.add((test_file.relative, call.end_lineno, call.end_col_offset))
                unplaced.add(Unplaced(test_file.relative, call.lineno, ast.unparse(call),
                                      "it is not called where it is written, so what it replaces is not written out",
                                      called=False))
                continue
            if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
                    and call.func.attr == "setattr"):
                continue
            read.add((test_file.relative, call.func.end_lineno, call.func.end_col_offset))
            if any(kind == CLASS or kind == OUTSIDE for kind, _held in test_file.values(call.func.value, {})):
                unplaced.add(Unplaced(test_file.relative, call.lineno, ast.unparse(call.func),
                                      "it is called on a class, so its first argument is the instance and what it "
                                      "replaces comes after", remedy="Call it on the instance"))
                continue
            ways, written = _aimed_at(test_file, call)
            for (kind, held), (name_kind, name) in ways:
                if kind == MODULE and name_kind == TEXT:
                    sites.add(Site(test_file.relative, call.lineno, held, name, written))
                elif kind == MODULE:
                    unplaced.add(Unplaced(test_file.relative, call.lineno, written,
                                          f"which name of {held} it replaces is not written out"))
                elif kind == TEXT:
                    unplaced.add(Unplaced(test_file.relative, call.lineno, written,
                                          "a string names a module only in the form setattr(\"module.name\", value)"))
                elif kind == PACKAGE:
                    unplaced.add(Unplaced(test_file.relative, call.lineno, written,
                                          f"{held} is a folder with no __init__.py, not a module"))
                elif kind not in _NO_MODULE:
                    unplaced.add(Unplaced(test_file.relative, call.lineno, written,
                                          f"what {held} holds is not written out"))
    return sites, unplaced, read


def _marked(suite: _Suite, sites: set[Site]) -> list[tuple[Site, str]]:
    return [(site, suite.names(site.module).mark(site.name)) for site in sorted(sites)]


def stand_ins(root: Path = ROOT) -> tuple[list[tuple[Site, str]], list[Unplaced]]:
    """Every stand-in under ``tests/`` aimed at a module of the repository,
    each with its mark, and every ``setattr`` the tool could not place
    (:func:`_survey`)."""
    suite = _Suite(root)
    sites, unplaced, _read = _survey(suite)
    return _marked(suite, sites), sorted(unplaced)


# -------------------------------------------------------------- the backstop ----


@dataclass(frozen=True, order=True)
class Unaccounted:
    """A ``setattr`` in the suite's text that is none of what the tool
    accounts for: a ``<x>.setattr`` it read, a call of the builtin
    ``setattr``, or the name defined or imported."""

    file: str
    line: int

    def said(self) -> str:
        """The line ``check`` prints for it."""
        return (f"{self.file}:{self.line}: setattr is written here in a form the tool does not read, so a stand-in "
                f"made through it is not checked. Write the stand-in as <x>.setattr(...) in a file under tests/, "
                f"called where it is written.")


def _unaccounted(suite: _Suite, read: set[tuple[str, int, int]]) -> list[Unaccounted]:
    """Every ``setattr`` token in the suite's Python (:meth:`_Suite.suite_files`,
    read with ``tokenize``, so a string or a comment is not one) that is none
    of these: a ``<x>.setattr`` the survey read (``read``, by where the name
    ends); a call of the builtin ``setattr``, which nothing undoes and so is
    no stand-in; the name of a ``def`` or a ``class``; or a name in an
    import. A stand-in written in a form the survey does not recognise -
    through a name ``setattr`` that is not the builtin, in a file it does
    not walk - can then fail the check, but never pass it unseen."""
    found: list[Unaccounted] = []
    for test_file in suite.suite_files():
        text = test_file.path.read_text(encoding="utf-8")
        lines = io.StringIO(text).readlines()
        builtin = {(node.end_lineno, node.end_col_offset) for node in ast.walk(test_file.tree)
                   if isinstance(node, ast.Name) and node.id == "setattr" and isinstance(node.ctx, ast.Load)
                   and isinstance(test_file.parent.get(node), ast.Call) and test_file.parent[node].func is node
                   and not test_file.binders("setattr", node)}
        imports = [((node.lineno, node.col_offset), (node.end_lineno, node.end_col_offset))
                   for node in ast.walk(test_file.tree) if isinstance(node, (ast.Import, ast.ImportFrom))]
        before = ""
        for token in tokenize.generate_tokens(io.StringIO(text).readline):
            if token.type == tokenize.NAME and token.string == "setattr":
                # The syntax tree counts a column in bytes, tokenize in characters.
                start = (token.start[0], len(lines[token.start[0] - 1][:token.start[1]].encode("utf-8")))
                end = (token.end[0], len(lines[token.end[0] - 1][:token.end[1]].encode("utf-8")))
                if not ((test_file.relative, *end) in read or end in builtin or before in ("def", "class")
                        or any(first <= start and end <= last for first, last in imports)):
                    found.append(Unaccounted(test_file.relative, token.start[0]))
            if token.type not in _LAYOUT:
                before = token.string
    return sorted(found)


_LAYOUT = (tokenize.NL, tokenize.NEWLINE, tokenize.COMMENT, tokenize.INDENT, tokenize.DEDENT)


def unaccounted(root: Path = ROOT) -> list[Unaccounted]:
    """Every ``setattr`` in the suite's text the tool does not account for (:func:`_unaccounted`)."""
    suite = _Suite(root)
    return _unaccounted(suite, _survey(suite)[2])


# ------------------------------------------------------------------- the CLI ----


def _module_asked(asked: str, root: Path) -> str:
    """``tracker.filer`` or ``tracker/filer.py``, as the dotted name."""
    dotted = asked.removesuffix(".py").replace("/", ".").replace("\\", ".")
    suite = _Suite(root)
    if dotted not in suite.index:
        raise SystemExit(f"patch_sites: no module {asked!r} in the repository")
    return suite.canonical(dotted)


def _count(number: int, thing: str) -> str:
    return f"{number} {thing}" + ("" if number == 1 else "s")


def report(module: str, root: Path = ROOT) -> list[str]:
    """The lines ``report`` prints: a summary, then one line per site."""
    module = _module_asked(module, root)
    marked, _unplaced = stand_ins(root)
    mine = [(site, mark) for site, mark in marked if site.module == module]
    counts = Counter(mark for _site, mark in mine)
    files = len({site.file for site, _mark in mine})
    lines = [f"{module}: {_count(len(mine), 'stand-in')} in {_count(files, 'file')} ("
             + ", ".join(f"{counts[mark]} {mark}" for mark in MARKS) + ")"]
    width = max((len(site.where()) for site, _mark in mine), default=0)
    lines += [f"  {site.where():<{width}}  {mark:<8}  {site.name}  ({site.written})" for site, mark in mine]
    return lines


def check(root: Path = ROOT) -> tuple[bool, list[str]]:
    """Whether every stand-in lands where the code reads it, every one can
    be placed, and every ``setattr`` in the suite's text is accounted for;
    and what to say."""
    suite = _Suite(root)
    sites, unplaced, read = _survey(suite)
    marked = _marked(suite, sites)
    lines = [f"{site.where()}: {site.module}.{site.name} is unread there: "
             f"{suite.index[site.module].relative_to(root).as_posix()} never reads it outside its import "
             f"or definition. Point the stand-in at the module that reads it."
             for site, mark in marked if mark == UNREAD]
    lines += [one.said() for one in sorted(unplaced)]
    lines += [one.said() for one in _unaccounted(suite, read)]
    if lines:
        return False, lines
    modules = len({site.module for site, _mark in marked})
    return True, [f"{_count(len(marked), 'stand-in')} on {_count(modules, 'module')}, each where the code reads the name."]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    asked = sub.add_parser("report", help="list every stand-in aimed at one module, each marked")
    asked.add_argument("module", help="a module, e.g. tracker.filer or tracker/filer.py")
    sub.add_parser("check", help="exit 1 if any stand-in is unread or cannot be placed")
    ns = parser.parse_args(argv)
    if ns.command == "report":
        print("\n".join(report(ns.module, ROOT)))
        return 0
    ok, lines = check(ROOT)
    print("\n".join(lines))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
