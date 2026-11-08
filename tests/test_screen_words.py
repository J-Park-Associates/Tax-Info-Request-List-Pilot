"""Tests for tracker/screen_words.py — the words the API sends the screen.

Since P340 (SPEC-architecture-p5 P5.3) the API's words live in their own
module, and the API imports back the ones its code reads. What the words
say, and that the screen is sent them, is held where it always was: by
``tests/test_api.py`` and ``tests/test_single_source.py``, which read them
through the vocabulary, and by ``tests/golden/``. No test moved here: a
test's home is a module whose functions or classes it calls, and this one
has neither. This file holds the module to what its docstring promises -
words and fixed values, and nothing that acts - so a function, a class or a
value read from somewhere at run time cannot creep in beside the words.
"""

import ast
from pathlib import Path

from tracker import screen_words

SOURCE = Path(screen_words.__file__)

#: The values a word or a fixed value may be: text, a number or a flag, or a
#: tuple, list, frozenset or dict of those, nested.
PLAIN = (str, int, float, bool)
HOLDERS = (tuple, list, frozenset)


def _is_a_word_or_a_fixed_value(value: object) -> bool:
    if isinstance(value, PLAIN):
        return True
    if isinstance(value, HOLDERS):
        return all(_is_a_word_or_a_fixed_value(one) for one in value)
    if isinstance(value, dict):
        return all(_is_a_word_or_a_fixed_value(key) and _is_a_word_or_a_fixed_value(one)
                   for key, one in value.items())
    return False


def test_the_words_module_holds_words_and_fixed_values_and_nothing_that_acts():
    """R5.3.9: every name the module binds that it did not import is a word
    or a fixed value - a ``str``, ``int``, ``float`` or ``bool``, or a
    ``tuple``, ``list``, ``frozenset`` or ``dict`` of those, nested - and the
    module defines no function and no class, not even a lambda or one
    nested in a value."""
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"), filename=str(SOURCE))
    imported = {alias.asname or alias.name.split(".")[0]
                for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))
                for alias in node.names}
    acts = [f"{type(node).__name__} at line {node.lineno}" for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda))]
    assert acts == []
    bound = {name: value for name, value in vars(screen_words).items()
             if not (name.startswith("__") and name.endswith("__")) and name not in imported}
    assert len(bound) > 200, "the guard reads nothing"
    assert [name for name, value in bound.items() if not _is_a_word_or_a_fixed_value(value)] == []
