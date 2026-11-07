"""What the reader's and the reading child's test files share: the fixtures
that put the reading in a real child (``in_a_child``) and patch its stops
down (``a_short_stop``), and the fake graphics card (``a_card``) with the
engine it builds (:class:`FakeEngine`) and the page that engine reads
(:data:`PAGE_WORDS`).

``tests/test_ocr.py`` wrote them for itself. With P338 (SPEC-architecture-p4
P4.12) the reading child's own tests left it for
``tests/test_reader_child.py``, and tests in both files take these: one child
per pass, the memory watch and the scratch moved, while the stage's fit in
the child and the stop a page never finishes stayed; the reader that cannot
run moved, while the card's run-log tests stayed. A test file may not import
another (``tests/test_suite_shape.py``), so what both read sits here, in a
module that is not a test file; the map draws the edge as "exercised by".

Nothing here is new behaviour: each came with its words. **The fixtures are
named, not imported.** A test file names each once by assignment
(``in_a_child = ocr_helpers.in_a_child``), as ``tests/filer_helpers.py``'s
are named: a fixture imported by name and then taken as a parameter trips
ruff's F811. :class:`FakeEngine` and :data:`PAGE_WORDS` are not fixtures,
so ``tests/test_ocr.py`` imports them by name.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from tests.builders import named_page
from tests.children import STOP_IN_TESTS
from tracker import content_check, ocr, reader_child


class FakeEngine:
    """An engine whose sessions say which provider they got, reading every
    page as ``lines``; from its ``fail_from``-th call it raises what a
    faulted card raises, for ever (the card poisons the engine)."""

    def __init__(self, provider: str, lines: list[str], *, fail_from: int = 0):
        self.calls = 0
        self.lines = lines
        self.fail_from = fail_from
        self.providers = {part: [provider, "CPUExecutionProvider"] for part in ocr.SESSIONS}
        for part in ocr.SESSIONS:
            session = SimpleNamespace(get_providers=lambda part=part: self.providers[part])
            setattr(self, part, SimpleNamespace(session=SimpleNamespace(session=session)))

    def __call__(self, pixels):
        self.calls += 1
        if self.fail_from and self.calls >= self.fail_from:
            raise RuntimeError("[ONNXRuntimeError] : 1 : FAIL : CUDA failure 999: unknown error ; GPU=0")
        boxes = [[(0, 40 * i), (500, 40 * i), (500, 40 * i + 30), (0, 40 * i + 30)]
                 for i in range(len(self.lines))]
        return SimpleNamespace(boxes=boxes, txts=tuple(self.lines),
                               scores=tuple(0.99 for _ in self.lines))


PAGE_WORDS = named_page("Form W-2 Wage and Tax Statement 2025").splitlines()


@pytest.fixture
def a_card(monkeypatch, tmp_path):
    """A machine with a graphics card pack beside the app, a card engine
    and a processor engine that are fakes, and a record of what was built
    and what was loaded. ``card.gpu`` is set by each test before the pass."""
    import onnxruntime

    pack = tmp_path / ocr.GPU_PACK_DIR_NAME
    pack.mkdir()
    card = SimpleNamespace(pack=pack, built=[], loaded=[], gpu=None, cpu=FakeEngine("CPUExecutionProvider", PAGE_WORDS))

    def build(*, cuda):
        card.built.append("card" if cuda else "processor")
        return card.gpu if cuda else card.cpu

    monkeypatch.setattr(ocr, "_ENGINE", None)
    monkeypatch.setattr(ocr, "_DEVICE", "")
    monkeypatch.setattr(ocr, "_PROCESSOR_ONLY", False)
    monkeypatch.setattr(ocr, "_NOTES", [])
    monkeypatch.setattr(ocr, "_build_engine", build)
    for module in (ocr, reader_child):
        monkeypatch.setattr(module, "gpu_pack", lambda: card.pack)
    monkeypatch.setattr(onnxruntime, "preload_dlls",
                        lambda **kwargs: card.loaded.append(kwargs.get("directory")))
    return card


@pytest.fixture
def in_a_child(monkeypatch):
    """The reading in a real child process, as the pass makes it."""
    monkeypatch.setattr(content_check, "READ_IN_A_CHILD", True)
    return monkeypatch


@pytest.fixture
def a_short_stop(in_a_child):
    in_a_child.setattr(content_check, "READING_STOP_DOCUMENT_SECONDS", STOP_IN_TESTS)
    in_a_child.setattr(content_check, "READING_STOP_PAGE_SECONDS", STOP_IN_TESTS)
    return in_a_child
