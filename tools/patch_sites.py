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
if any site in the suite is unread or cannot be placed. The migration checklist
runs both (SPEC-architecture section 10, steps 5 and 12), so the tool keeps its
``__main__`` (P233).

**What it reads of the tests.** Any ``<x>.setattr(...)`` call is a site, so a
fixture that hands its monkeypatch on (``in_a_child``) and
``pytest.MonkeyPatch.context()`` count as well as ``monkeypatch``. A module is
named three ways: as the test imported it (``setattr(filer, ...)``), under an
alias (``filer_module``, ``here = children`` or ``here: ModuleType =
children``), or in a string (``setattr("tracker.filer.name", value)``). The
string may be written at the call or held in a name, a loop or a helper
module's constant, or made by an f-string. An alias or a string another module
of the repository holds at its top level (a helper module's ``THE_SORTER =
sorter``, read as ``aliases.THE_SORTER`` or imported from it) is followed into
that module. The stand-ins most worth checking come in loops: a test that
forbids four reads sets four names in a ``for`` over a literal tuple, and a
stand-in there that misses makes the test pass for nothing. So the tool also
follows a module, a name or a string that comes from a ``for`` over literals
(or over a literal assigned to a name), from a fixture's ``params``, from a
fixture that returns it, and from a helper's parameter at the helper's calls in
the same file. Values bound together stay together: ``for module, name in ((a,
"x"), (b, "y"))`` is two sites, not four, and inside a loop's body its name
holds the loop's values, whatever else it is bound to.

**What a read is.** A global read in the module's own code, by Python's own
scope rules: not a parameter or a local of the same name, not a method reading
its class's names, not a comprehension's own variable, and never an annotation
(which no call reaches, and which 3.11 and 3.14 scope differently). The rules
are written out here rather than taken from ``symtable``, which loses a
module-level comprehension's reads on 3.12 and later (PEP 709 inlines it), so
its answer would depend on the interpreter.

**What it does not see.** A name another module copied with ``from module
import name`` is out of reach of a stand-in on ``module``. That site is
reported as defined, because some caller may read the name through the module
and the tool cannot know which caller a test meant. The moves to come make the
other mistake, an imported name the module stops reading, and that is the one
``check`` fails.

**No module is something the tool knows, never its fallback.** A stand-in
passes unlisted only when its target is one of these: a constant that is not a
string, a literal container, a comparison or arithmetic; a function (a
``def`` or a ``lambda``); a class the tool sees defined, or what calling one
makes; ``x.__class__``; what one of pytest's own fixtures gives
(``tmp_path``); and anything outside the repository - a builtin, an outside
library, and what calling either gives. Each of these lands on that object,
whoever reads it. Every other target fails ``check`` as not placed: a
module stored by an unpacking, a walrus, ``with ... as`` or ``except ... as``;
what a ``def``, a ``lambda``, a method or an instance gives when called, in the
test file or in another module; what ``getattr``, ``vars``, ``__import__``,
``globals``, ``locals``, ``eval``, ``next``, ``min`` or ``max`` gives; either
side of ``or``; an attribute of anything but a module or something outside (a
class's, an instance's, a function's, one of what an outside call made); a
top-level name its module rebinds in a function or never binds; and in the
string form, a first argument that is not a string the tool can read, such as
one built with ``+`` or ``format``. The remedy is the same each time: name the
module and the name as an import, an alias or a literal. The fallback this
replaced, no module wherever the tool did not know, let a stand-in written
through a helper module, a lambda, a class or a string held in a name drop out
of the check without a word.

Rejected: importing the modules to ask them (it runs code, and the tests'
imports reach the sorting engine); tracing a run of the whole suite (it costs a
full run, and still misses every branch the run does not take).
"""

from __future__ import annotations

import argparse
import ast
import builtins
import itertools
from collections import Counter, defaultdict
from dataclasses import dataclass
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
    """A ``setattr`` whose module or name the tool could not work out."""

    file: str
    line: int
    written: str
    why: str


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
# module of the repository (by its dotted name), a string, something outside
# the repository (a builtin among them), a function, a class or an instance of
# a class the tool sees defined, a thing the tool knows is no module (a
# constant, a literal container, what an outside call returns), or a value the
# tool cannot work out. A value is ``(kind, what)``. Only ``MODULE`` and
# ``UNKNOWN`` reach the check; "no module" is a kind the tool has to know,
# never the fallback.
MODULE, TEXT, OUTSIDE, THING, UNKNOWN = "module", "text", "outside", "thing", "unknown"
FUNCTION, CLASS, INSTANCE = "function", "class", "instance"
_A_THING = (THING, None)

#: The calls whose one argument a loop walks as written, the calls that
#: import the module their one argument names, and the builtins that can give
#: a module the tool does not follow (every other builtin's result is no module).
_SEQUENCE_CALLS = ("sorted", "list", "tuple", "set", "reversed")
_IMPORT_CALLS = ("import_module", "importorskip")
_GIVE_A_MODULE = frozenset(f"builtins.{name}" for name in (
    "getattr", "vars", "__import__", "globals", "locals", "eval", "next", "min", "max"))

_SCOPES = (ast.Module, *_FUNCTIONS, ast.Lambda)
_BUILTINS = frozenset(dir(builtins))


def _fixture_decorator(function: ast.AST) -> ast.expr | None:
    """The ``@pytest.fixture`` (or ``@pytest.fixture(...)``) on ``function``."""
    for decorator in getattr(function, "decorator_list", []):
        called = decorator.func if isinstance(decorator, ast.Call) else decorator
        if (called.attr if isinstance(called, ast.Attribute) else getattr(called, "id", "")) == "fixture":
            return decorator
    return None


class _Suite:
    """The repository's modules and the files under ``tests/``, each parsed once."""

    def __init__(self, root: Path):
        self.root = root
        self.index = module_index(root)
        # A tool imported by its bare name is reported by its dotted one.
        self._dotted: dict[Path, str] = {}
        for dotted, path in self.index.items():
            if dotted.count(".") >= self._dotted.get(path, "").count("."):
                self._dotted[path] = dotted
        self._names: dict[str, ModuleNames] = {}
        self._files: dict[Path, _TestFile] = {}

    def canonical(self, dotted: str) -> str:
        """A module's dotted name from the root, however the test imported it."""
        return self._dotted[self.index[dotted]]

    def module(self, dotted: str) -> tuple:
        return (MODULE, self.canonical(dotted)) if dotted in self.index else (OUTSIDE, dotted)

    def names(self, module: str) -> ModuleNames:
        if module not in self._names:
            path = self.index[module]
            self._names[module] = module_names(path.read_text(encoding="utf-8"), str(path))
        return self._names[module]

    def test_file(self, path: Path) -> _TestFile:
        if path not in self._files:
            self._files[path] = _TestFile(self, path)
        return self._files[path]

    def conftests(self) -> list[_TestFile]:
        return [self.test_file(path) for path in sorted((self.root / TESTS).rglob("conftest.py"))]

    def imported(self, statement: ast.AST, alias: ast.alias, importer: str, seen: frozenset = frozenset()) -> list[tuple]:
        """What an import statement in the module ``importer`` binds to ``alias``'s name."""
        if isinstance(statement, ast.Import):
            return [self.module(alias.name if alias.asname else alias.name.split(".")[0])]
        base = statement.module or ""
        if statement.level:
            package = importer.split(".")[: -statement.level]
            base = ".".join([*package, base] if base else package)
        if f"{base}.{alias.name}" in self.index:
            return [self.module(f"{base}.{alias.name}")]
        if base in self.index:
            return self.attribute(self.module(base), alias.name, f"{base}.{alias.name}", seen)
        return [(OUTSIDE, f"{base}.{alias.name}")]

    def attribute(self, value: tuple, attr: str, written: str, seen: frozenset = frozenset()) -> list[tuple]:
        """What ``<value>.<attr>`` can hold, written as ``written``.

        Of a module of the repository: its submodule, or what the module binds
        to the name at its top level, followed in that module's own code (an
        import, a ``def``, a ``class``, an assignment). Of something outside
        the repository: something outside. ``x.__class__`` is a class whatever
        ``x`` is. Anything else - a class's attribute, an instance's, a
        function's, a string's method, an attribute of a value the tool knows
        is no module - may hold a module, so it is not followed."""
        kind, held = value
        if kind == OUTSIDE:
            return [(OUTSIDE, f"{held}.{attr}")]
        if attr == "__class__":
            return [_A_THING]
        if kind == MODULE:
            if f"{held}.{attr}" in self.index:
                return [self.module(f"{held}.{attr}")]
            return self.test_file(self.index[held]).top_level(attr, written, seen)
        return [value if kind == UNKNOWN else (UNKNOWN, written)]


class _TestFile:
    """One file the tool follows values in: its tree, each node's parent, its
    scopes. A file under ``tests/``, or a module of the repository whose
    top-level name a test reads through it (``helpers.THE_SORTER``)."""

    def __init__(self, suite: _Suite, path: Path):
        self.suite = suite
        self.relative = path.relative_to(suite.root).as_posix()
        self.dotted = ".".join(path.relative_to(suite.root).with_suffix("").parts)
        self.tree = ast.parse(path.read_text(encoding="utf-8"), self.relative)
        self.parent: dict[ast.AST, ast.AST] = {}
        self.calls: dict[str, list[ast.Call]] = defaultdict(list)
        for node in ast.walk(self.tree):
            for child in ast.iter_child_nodes(node):
                self.parent[child] = node
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                self.calls[node.func.id].append(node)
        self._bound: dict[ast.AST, dict[str, list[ast.AST]]] = {}
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

    def bound_in(self, scope: ast.AST) -> dict[str, list[ast.AST]]:
        """Each name bound directly in ``scope``, with the nodes that bind it:
        an ``ast.arg``, an ``ast.alias``, a stored ``ast.Name``, or a ``def``."""
        if scope not in self._bound:
            bound: dict[str, list[ast.AST]] = defaultdict(list)
            for one in [] if isinstance(scope, ast.Module) else _parameters(scope.args):
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

    def binders(self, name: str, at: ast.AST) -> list[ast.AST]:
        """The nodes that bind ``name`` in the innermost scope around ``at`` that binds it."""
        for scope in self.chain(at):
            found = self.bound_in(scope).get(name)
            if found:
                return found
        return []

    def top_level(self, name: str, written: str, seen: frozenset) -> list[tuple]:
        """What this file's top-level ``name`` can hold, read from another
        file as ``written``. A name the file never binds at its top level, or
        one it rebinds elsewhere, is not followed."""
        bound = self.bound_in(self.tree).get(name)
        if not bound or name in self.rebound:
            return [(UNKNOWN, written)]
        return self._bound_values(name, bound, seen)

    # -- what an expression holds

    def values(self, expr: ast.AST, env: dict[str, list[tuple]], seen: frozenset = frozenset()) -> list[tuple]:
        """Every value ``expr`` can hold, with the names in ``env`` fixed."""
        if isinstance(expr, ast.Constant):
            return [(TEXT, expr.value) if isinstance(expr.value, str) else _A_THING]
        if isinstance(expr, ast.Name):
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
        if isinstance(expr, ast.Lambda):
            return [(FUNCTION, "lambda")]
        if isinstance(expr, (ast.List, ast.Tuple, ast.Dict, ast.Set, ast.BinOp, ast.Compare, ast.UnaryOp,
                             *_COMPREHENSIONS)):
            return [_A_THING]
        # ``a or b`` gives one of its operands, and anything else not named
        # above is not followed.
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
        something the tool cannot work out."""
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
        found = []
        for kind, held in self.values(func, env, seen):
            if kind == CLASS:
                found.append((INSTANCE, held))
            elif kind == OUTSIDE and held not in _GIVE_A_MODULE:
                found.append(_A_THING)
            else:
                found.append((UNKNOWN, ast.unparse(call)))
        return found

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
        for scope in self.chain(at):
            decorator = _fixture_decorator(scope)
            given = [keyword.value for keyword in getattr(decorator, "keywords", []) if keyword.arg == "params"]
            items = self.items(given[0], seen) if given else None
            if items is not None:
                return [value for item in items for value in self.values(item, {}, seen)]
        return [(UNKNOWN, "request.param")]

    def _held_by(self, expr: ast.Name, seen) -> list[tuple]:
        bound = self.binders(expr.id, expr)
        if not bound:
            # A builtin is outside the repository. Any other name the file
            # never binds (a comprehension's variable, a star import's) is not
            # followed.
            return [(OUTSIDE, f"builtins.{expr.id}")] if expr.id in _BUILTINS else [(UNKNOWN, expr.id)]
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
                found.append((CLASS, f"{self.dotted}.{node.name}"))
            else:
                found.append((FUNCTION, f"{self.dotted}.{node.name}"))
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
            bound = self.binders(expr.id, expr)
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
        test's or a fixture's parameter is a fixture, fixed alone."""
        function = self.parent[self.parent[parameter]]
        unknown = (parameter, [{parameter.arg: [(UNKNOWN, parameter.arg)]}])
        if isinstance(function, ast.Lambda):
            return unknown
        if _fixture_decorator(function) or function.name.startswith("test_"):
            return parameter, [{parameter.arg: self._fixture_values(parameter.arg, seen)}]
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

    def _fixture_values(self, name: str, seen) -> list[tuple]:
        """What the fixture called ``name`` gives, where this file or a
        conftest under ``tests/`` defines it; a thing that is no module
        otherwise (pytest's own, such as ``tmp_path`` or ``monkeypatch``)."""
        for holder in (self, *self.suite.conftests()):
            for node in holder.tree.body:
                if isinstance(node, _FUNCTIONS) and node.name == name and _fixture_decorator(node):
                    given = [sub.value for sub in ast.walk(node)
                             if isinstance(sub, (ast.Return, ast.Yield)) and sub.value is not None]
                    return [value for one in given for value in holder.values(one, {}, seen)] or [_A_THING]
        return [_A_THING]


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
    the repository is the module, the parts after it but the last are its
    attributes, and the last part is the name. A string that names no module of
    the repository is outside it."""
    parts = text.split(".")
    for cut in range(len(parts) - 1, 0, -1):
        if ".".join(parts[:cut]) in suite.index:
            values = [suite.module(".".join(parts[:cut]))]
            for at in range(cut, len(parts) - 1):
                values = [value for one in values for value in suite.attribute(one, parts[at], ".".join(parts[:at + 1]))]
            return [(value, (TEXT, parts[-1])) for value in values]
    return [((OUTSIDE, text), (TEXT, parts[-1]))]


def _aimed_at(test_file: _TestFile, call: ast.Call) -> tuple[list[tuple[tuple, tuple]], str]:
    """Every (module, name) a ``setattr`` call can replace, and how its
    target is written.

    Two arguments and no ``value=`` is the string form, whose first argument
    pytest requires to be a string: each string it can hold is read as the
    dotted name it is, and any other value it can hold is a string the tool
    cannot read, so it is not placed."""
    args = call.args
    string_form = len(args) == 2 and not {"name", "value"} & {keyword.arg for keyword in call.keywords}
    if string_form and isinstance(args[0], ast.Constant) and isinstance(args[0].value, str):
        return _dotted(test_file.suite, args[0].value), repr(args[0].value)
    written = ast.unparse(args[0]) if args else ast.unparse(call)
    if len(args) < 2:
        return [((UNKNOWN, written), _A_THING)], written
    ways = _rows(test_file, call, args[:2])
    if ways is None:
        return [((UNKNOWN, written), _A_THING)], written
    found: list[tuple[tuple, tuple]] = []
    for env in ways:
        for kind, held in test_file.values(args[0], env):
            if not string_form:
                found.extend(((kind, held), name) for name in test_file.values(args[1], env))
            elif kind == TEXT:
                found.extend(_dotted(test_file.suite, held))
            else:
                found.append(((UNKNOWN, held if kind == UNKNOWN else written), _A_THING))
    return found, written


def stand_ins(root: Path = ROOT) -> tuple[list[tuple[Site, str]], list[Unplaced]]:
    """Every stand-in under ``tests/`` aimed at a module of the repository,
    each with its mark, and every ``setattr`` the tool could not place."""
    suite = _Suite(root)
    sites: set[Site] = set()
    unplaced: set[Unplaced] = set()
    for path in sorted((root / TESTS).rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        test_file = suite.test_file(path)
        for call in ast.walk(test_file.tree):
            if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
                    and call.func.attr == "setattr"):
                continue
            ways, written = _aimed_at(test_file, call)
            for (kind, held), (name_kind, name) in ways:
                if kind == MODULE and name_kind == TEXT:
                    sites.add(Site(test_file.relative, call.lineno, held, name, written))
                elif kind == MODULE:
                    unplaced.add(Unplaced(test_file.relative, call.lineno, written,
                                          f"which name of {held} it replaces is not written out"))
                elif kind == UNKNOWN:
                    unplaced.add(Unplaced(test_file.relative, call.lineno, written,
                                          f"what {held} holds is not written out"))
    return [(site, suite.names(site.module).mark(site.name)) for site in sorted(sites)], sorted(unplaced)


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
    """Whether every stand-in lands where the code reads it, and what to say."""
    marked, unplaced = stand_ins(root)
    index = module_index(root)
    lines = [f"{site.where()}: {site.module}.{site.name} is unread there: "
             f"{index[site.module].relative_to(root).as_posix()} never reads it outside its import "
             f"or definition. Point the stand-in at the module that reads it."
             for site, mark in marked if mark == UNREAD]
    lines += [f"{one.file}:{one.line}: setattr({one.written}, ...) cannot be placed: {one.why}. "
              f"Name the module and the name as an import, an alias or a literal." for one in unplaced]
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
