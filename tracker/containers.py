"""Open an email or a zip a client dropped, in memory, and hand back what
was attached (decision 143).

Clients forward emails (``.msg``, ``.eml``) and zip files with the real
documents attached, and until now each parked as one opaque file ("no
request accepts .msg files"): a W-2 inside was invisible until a person
opened the container by hand. The owner's rule (2026-09-23): **open them
and file each attachment**. The container stays the client's original,
untouched; each attachment becomes its own document and is sorted like any
drop; nothing inside is ever run; a password-protected or damaged container
parks.

This module is the opening and nothing else. It is handed the container's
bytes - already read, under the size ceiling (``validators.MAX_READ_MB``),
by the filer - and gives back plain data: each attachment's own name and
bytes, and each part it skipped with why. It writes nothing, holds no file
open past the call, and decides nothing about a folder: where the
attachments are written, and what becomes of each, is
:mod:`tracker.filer`'s.

**What counts as a container: the extension alone** (:data:`EXTENSIONS`).
Never the bytes' magic number, because an ``.xlsx`` and a ``.docx`` are
zips too and are documents, not containers.

**Untrusted input, every byte of it.** A container arrives from outside the
firm, and three parsers read it:

- ``.eml`` - the standard library's ``email`` (``policy.default``), walking
  the parts and decoding each payload. It is a *parser* here and nothing
  else: no address is ever parsed, no HTML is ever rendered, no message is
  ever composed and nothing is sent (the fourth standing rule; the one
  module under ``tracker/`` allowed to import it is this one, and
  ``tests/test_layers.py`` says so by name).
- ``.zip`` - ``zipfile``, streaming each member through a counting read
  with the caps below. **Never ``extract`` or ``extractall``**, so a member
  name is never a path on this machine; names are decoded as the zip marks
  them (cp437 without the UTF-8 flag, which is what the file says, not a
  guess).
- ``.msg`` - ``olefile`` (BSD-2-Clause, one pure-Python module), reading
  the attachment streams by name. Its stream reader walks a sector chain in
  a loop bounded by the stream's size and refuses a sector index out of
  range, and its directory walk refuses an entry referenced twice, so a
  cycle in a chain or in the tree ends the reading instead of spinning.
  ``extract-msg`` was refused: GPL-3.0 and a large dependency tree for a
  job this narrow.

**The limits** (each a constant here, each with a test at its edge):
nesting :data:`MAX_DEPTH` deep, :data:`MAX_ATTACHMENTS` attachments,
:data:`MAX_TOTAL_MB` decompressed in total - counted from the bytes
actually produced, never from what a zip's directory declares - and no zip
member past :data:`MAX_RATIO` times its compressed size. Hitting any of
them raises :class:`NotOpened` with the limit in its sentence, and the
container parks. The whole container is opened in memory before anything
is written, so a container that hits a limit leaves nothing behind.

**Nesting.** An email holding a zip, or a zip holding an email, is opened
through (depth 2): the inner container's attachments are the outer's. A
container one level deeper is not opened - it is handed back as an
attachment of its own, carrying the limit's sentence, and parks as a
container. So is an inner container that will not open (locked, damaged or
empty): the rest of what was attached still files. An embedded message
that has no bytes of its own to hand back (a ``.msg`` attached as a
message, method 5, past the depth) cannot be handed back as a file, so it
stops the whole container instead.

**Skipped, never a document:** inline images (a ``.msg`` attachment marked
hidden, ``PR_ATTACHMENT_HIDDEN``, or rendered in place,
``PR_ATTACH_FLAGS & 4``; an ``.eml`` part whose ``Content-Disposition`` is
``inline``) - a Content-ID alone is **not** a signal, because real
attachments carry one too; message bodies, never saved and never rendered;
and a ``.msg`` attachment by reference or an OLE object (methods 2, 3, 4,
6 and 7), which hold no bytes of the document or bytes that would be run.
Each skip is named, so the container's row can say what was left and why.
"""

from __future__ import annotations

import io
import zipfile
import zlib
from collections.abc import Callable
from dataclasses import dataclass, field
from email import message_from_bytes, policy
from email.message import Message
from pathlib import PurePath

from tracker import reasons
from tracker.manifest import WINDOWS_ILLEGAL_CHARS, is_reserved_name

#: The extensions that make a drop a container, lower case, no dot. The
#: extension and nothing else decides (the module docstring says why).
EXTENSIONS: tuple[str, ...] = ("eml", "msg", "zip")

#: How deep containers are opened through: an email holding a zip is
#: opened (depth 2); a zip inside that zip is not (it parks as a container).
MAX_DEPTH = 2
#: How many attachments one container may yield, nested ones included.
MAX_ATTACHMENTS = 200
#: How many megabytes one container may decompress to in total, counted
#: from the bytes actually produced.
MAX_TOTAL_MB = 250
MAX_TOTAL_BYTES = MAX_TOTAL_MB * 1024 * 1024
#: How many times its compressed size a zip member may decompress to.
MAX_RATIO = 100
#: How many parts one container may leave inside - message texts, inline
#: pictures, links, folder entries. Not a document limit: every part left
#: is named on the container's line in the record, and a crafted message of
#: a million inline parts would otherwise write a line nobody can read.
MAX_SKIPPED = 200
#: The longest name an attachment keeps on the record (NTFS's own limit for
#: one name). Longer is cut from the end of its stem, keeping its extension;
#: the room its file has on disk is measured, and cut to, where it is written.
NAME_MAX = 255

#: How much a zip member is read at a time: small enough that a member
#: past a limit is stopped within one chunk of it.
_CHUNK = 64 * 1024

#: The limits as the park sentence says them, each with its number.
LIMIT_DEPTH = f"nested more than {MAX_DEPTH} deep"
LIMIT_COUNT = f"more than {MAX_ATTACHMENTS} attachments"
LIMIT_TOTAL = f"more than {MAX_TOTAL_MB} MB once unpacked"
LIMIT_RATIO = f"a file inside unpacks to more than {MAX_RATIO} times its packed size"
LIMIT_SKIPPED = f"more than {MAX_SKIPPED} parts that are not documents"

#: Why a part was skipped, as the container's record says it.
SKIP_INLINE = "inline image, shown in the message rather than attached"
SKIP_BODY = "the message's own text, never saved"
SKIP_REFERENCE = "attached by reference: it holds a link, not the document"
SKIP_OLE = "an embedded object that would have to be run to be read"
SKIP_EMPTY = "attached with nothing in it"
SKIP_FOLDER = "a folder entry"

#: What a part with no name of its own is called, numbered in its order.
UNNAMED = "attachment {n}"
#: How a container is spoken of in the sentence a nested one parks with.
KIND_EMAIL = "an email"
KIND_ZIP = "a zip"

#: ``.msg`` attachment methods (MS-OXCMSG ``PidTagAttachMethod``).
_BY_VALUE = 1
_EMBEDDED = 5
_BY_REFERENCE = (2, 3, 4, 7)
_OLE = 6
#: ``.msg`` property ids read off an attachment's properties stream.
_PROP_METHOD = 0x3705
_PROP_HIDDEN = 0x7FFE
_PROP_FLAGS = 0x3714
_RENDERED_IN_PLACE = 0x4          # PR_ATTACH_FLAGS: ATT_MHTML_REF
_ATTACH_PREFIX = "__attach_version1.0_#"
_EMBEDDED_STORAGE = "__substg1.0_3701000D"
_DATA_STREAM = "__substg1.0_37010102"
_PROPERTIES = "__properties_version1.0"
#: The name streams, best first: the long file name, the short one, the
#: display name - each in Unicode (001F) before the 8-bit form (001E).
_NAME_STREAMS = tuple(f"__substg1.0_{prop}{kind}" for prop in ("3707", "3704", "3001")
                      for kind in ("001F", "001E"))
#: An attachment's properties stream begins with 8 reserved bytes.
_ATTACHMENT_HEADER = 8
_PROPERTY_SIZE = 16


@dataclass(frozen=True, slots=True)
class Attachment:
    """One document taken out of a container: its own name (a basename, made
    safe by :func:`safe_name`, never cut) and its bytes.

    ``parks`` is empty for an ordinary attachment. A container nested past
    :data:`MAX_DEPTH`, or one that would not open, is handed back whole as
    an attachment of its own and carries the sentence it parks with."""

    name: str
    data: bytes
    parks: str = ""


@dataclass(frozen=True, slots=True)
class Skipped:
    """One part that is not a document, and why (``SKIP_*``)."""

    name: str
    why: str


@dataclass(frozen=True, slots=True)
class Opened:
    """What one container held: the documents, in order, and what was left."""

    attachments: tuple[Attachment, ...]
    skipped: tuple[Skipped, ...]


class NotOpened(Exception):
    """The container does not open, and the sentence it parks with."""

    def __init__(self, sentence: str):
        super().__init__(sentence)
        self.sentence = sentence


def is_container(name: str | PurePath) -> bool:
    """Whether a file by this name is opened rather than read: its
    extension, and nothing else."""
    return PurePath(str(name)).suffix.lower().lstrip(".") in EXTENSIONS


def safe_name(raw: object, fallback: str | Callable[[], str]) -> str:
    """An attachment's name as a file name that cannot leave its folder.

    **The one function every attachment name passes through.** The
    basename only: any folder part is dropped, whichever separator it uses,
    so ``../x.pdf``, ``C:\\x.pdf`` and ``\\\\server\\share\\x.pdf`` are each
    ``x.pdf``; a drive letter left behind (``C:x.pdf``) goes with the
    characters Windows forbids, which become ``_``; a name Windows reads as
    a device (``CON.pdf``, decision 137's L6 rule,
    :func:`tracker.manifest.is_reserved_name`) is refused and the part is
    called ``fallback`` with its extension; nothing but dots, or nothing at
    all, is ``fallback`` (a string, or a function asked only when it is
    needed, so an unnamed part's number is spent only on an unnamed part).
    A name the record cannot hold as UTF-8 is mended first. Not cut: the
    room a name has on disk is measured where it is written; a name past
    :data:`NAME_MAX` is cut here only so that the record never holds one
    longer than a file name can be.
    """
    text = str(raw or "").encode("utf-8", "replace").decode("utf-8")
    text = text.replace("\\", "/").rsplit("/", 1)[-1]
    text = WINDOWS_ILLEGAL_CHARS.sub("_", text).strip().rstrip(". ")
    if len(text) > NAME_MAX:
        suffix = PurePath(text).suffix
        suffix = suffix if 1 < len(suffix) <= 11 else ""
        text = (text[:NAME_MAX - len(suffix)].rstrip(". ") + suffix) if suffix else text[:NAME_MAX]
    if text.strip("._ ") and not is_reserved_name(text):
        return text
    instead = fallback() if callable(fallback) else fallback
    suffix = PurePath(text).suffix if text.strip("._ ") else ""
    return f"{instead}{suffix}" if suffix.strip("._ ") else instead


def open_container(data: bytes, extension: str) -> Opened:
    """Open a container's bytes and hand back what it held.

    ``extension`` is the container file's own (``msg``, ``.EML``, ...).
    Raises :class:`NotOpened` with the sentence the container parks with:
    locked, damaged, past a limit, or nothing attached at all.
    """
    walk = _Walk()
    walk.open(data, extension.lower().lstrip("."), depth=1)
    if not walk.attachments:
        kind = KIND_ZIP if extension.lower().lstrip(".") == "zip" else KIND_EMAIL
        raise NotOpened(reasons.CONTAINER_EMPTY.format(kind=kind))
    return Opened(tuple(walk.attachments), tuple(walk.skipped))


@dataclass(slots=True)
class _Walk:
    """One container's opening: what it has yielded so far, and the budget
    it is spending, shared by every container nested inside it."""

    attachments: list[Attachment] = field(default_factory=list)
    skipped: list[Skipped] = field(default_factory=list)
    produced: int = 0
    unnamed: int = 0

    # -- the budget ---------------------------------------------------------

    def spend(self, count: int) -> None:
        """Count bytes produced by decoding; stop the container past the total."""
        self.produced += count
        if self.produced > MAX_TOTAL_BYTES:
            raise NotOpened(reasons.CONTAINER_LIMIT.format(error=LIMIT_TOTAL))

    def skip(self, part: Skipped) -> None:
        """Name one part left inside; stop the container past
        :data:`MAX_SKIPPED`, because every one is named on the record's line."""
        if len(self.skipped) >= MAX_SKIPPED:
            raise NotOpened(reasons.CONTAINER_LIMIT.format(error=LIMIT_SKIPPED))
        self.skipped.append(Skipped(part.name[:NAME_MAX], part.why))

    def fallback(self) -> str:
        self.unnamed += 1
        return UNNAMED.format(n=self.unnamed)

    def add(self, name: str, data: bytes, depth: int) -> None:
        """One part with bytes of its own: a document, or a container to
        open through (or to hand back whole, where it is too deep or will
        not open)."""
        if len(self.attachments) >= MAX_ATTACHMENTS:
            raise NotOpened(reasons.CONTAINER_LIMIT.format(error=LIMIT_COUNT))
        extension = PurePath(name).suffix.lower().lstrip(".")
        if extension not in EXTENSIONS:
            self.attachments.append(Attachment(name, data))
            return
        if depth + 1 > MAX_DEPTH:
            self.attachments.append(Attachment(
                name, data, parks=reasons.CONTAINER_LIMIT.format(error=LIMIT_DEPTH)))
            return
        # An inner container: its attachments are this one's. One that will
        # not open is handed back whole with its own sentence - unless what
        # stopped it is the budget this whole container shares, which stops
        # the whole container.
        inner = _Walk(produced=self.produced, unnamed=self.unnamed)
        try:
            inner.open(data, extension, depth=depth + 1)
            if not inner.attachments:
                kind = KIND_ZIP if extension == "zip" else KIND_EMAIL
                raise NotOpened(reasons.CONTAINER_EMPTY.format(kind=kind))
        except NotOpened as exc:
            if reasons.CONTAINER_LIMIT.matches(exc.sentence) and LIMIT_DEPTH not in exc.sentence:
                raise
            self.attachments.append(Attachment(name, data, parks=exc.sentence))
            return
        if len(self.attachments) + len(inner.attachments) > MAX_ATTACHMENTS:
            raise NotOpened(reasons.CONTAINER_LIMIT.format(error=LIMIT_COUNT))
        self.attachments.extend(inner.attachments)
        for one in inner.skipped:
            self.skip(one)
        self.produced, self.unnamed = inner.produced, inner.unnamed

    # -- the three parsers --------------------------------------------------

    def open(self, data: bytes, extension: str, *, depth: int) -> None:
        if extension == "zip":
            self._zip(data, depth)
        elif extension == "eml":
            self._eml(data, depth)
        elif extension == "msg":
            self._msg(data, depth)
        else:           # the caller asked for a container this module does not know
            raise NotOpened(reasons.CONTAINER_DAMAGED.format(error=f"not a container: .{extension}"))

    def _zip(self, data: bytes, depth: int) -> None:
        try:
            archive = zipfile.ZipFile(io.BytesIO(data))
        except (zipfile.BadZipFile, zipfile.LargeZipFile, ValueError, OSError, EOFError) as exc:
            raise NotOpened(reasons.CONTAINER_DAMAGED.format(error=_said(exc))) from exc
        with archive:
            members = [info for info in archive.infolist() if not info.is_dir()]
            for info in archive.infolist():
                if info.is_dir():
                    self.skip(Skipped(info.filename, SKIP_FOLDER))
            # Counted before a byte is decompressed: the directory lists them.
            if len(self.attachments) + len(members) > MAX_ATTACHMENTS:
                raise NotOpened(reasons.CONTAINER_LIMIT.format(error=LIMIT_COUNT))
            for info in members:
                if info.flag_bits & 0x1:
                    raise NotOpened(reasons.CONTAINER_LOCKED.format())
                name = safe_name(info.filename, self.fallback)
                self.add(name, self._member(archive, info), depth)

    def _member(self, archive: zipfile.ZipFile, info: zipfile.ZipInfo) -> bytes:
        """One member's bytes, read through a counting loop: the total and
        the ratio are judged on what the decompressor actually produced,
        never on the sizes the directory declares."""
        ceiling = MAX_RATIO * max(info.compress_size, 1)
        out = bytearray()
        try:
            with archive.open(info) as member:
                while chunk := member.read(_CHUNK):
                    out += chunk
                    self.spend(len(chunk))
                    if len(out) > ceiling:
                        raise NotOpened(reasons.CONTAINER_LIMIT.format(error=LIMIT_RATIO))
        except NotImplementedError as exc:       # a compression this reader has not got (AES...)
            raise NotOpened(reasons.CONTAINER_LOCKED.format()) from exc
        except RuntimeError as exc:              # zipfile's "is encrypted, password required"
            raise NotOpened(reasons.CONTAINER_LOCKED.format()) from exc
        except (zipfile.BadZipFile, zlib.error, EOFError, ValueError, OSError) as exc:
            raise NotOpened(reasons.CONTAINER_DAMAGED.format(error=_said(exc))) from exc
        return bytes(out)

    def _eml(self, data: bytes, depth: int) -> None:
        try:
            message = message_from_bytes(data, policy=policy.default)
        except Exception as exc:         # the parser records defects; anything raised is damage
            raise NotOpened(reasons.CONTAINER_DAMAGED.format(error=_said(exc))) from exc
        if not list(message.keys()):
            raise NotOpened(reasons.CONTAINER_DAMAGED.format(error="no message headers"))
        try:
            self._eml_part(message, depth)
        except NotOpened:
            raise
        except (LookupError, ValueError, TypeError, AttributeError, RecursionError) as exc:
            raise NotOpened(reasons.CONTAINER_DAMAGED.format(error=_said(exc))) from exc

    def _eml_part(self, part: Message, depth: int) -> None:
        """One MIME part: a multipart is walked, an attached message is a
        container of its own, and a leaf is a document, an inline image or
        the message's own text."""
        content_type = part.get_content_type()
        if content_type == "message/rfc822":
            inner = part.get_payload()
            embedded = inner[0] if isinstance(inner, list) and inner else None
            if not isinstance(embedded, Message):
                self.skip(Skipped(part.get_filename() or "attached message", SKIP_EMPTY))
                return
            if depth + 1 > MAX_DEPTH:
                # Handed back whole, as an .eml, and parks as a container.
                raw = embedded.as_bytes(policy=policy.default)
                self.spend(len(raw))
                name = safe_name(part.get_filename() or "", lambda: self.fallback() + ".eml")
                if not name.lower().endswith(".eml"):
                    name += ".eml"
                self.add(name, raw, depth)
                return
            self._eml_part(embedded, depth + 1)
            return
        if part.is_multipart():
            for child in part.iter_parts():
                self._eml_part(child, depth)
            return
        disposition = part.get_content_disposition()
        filename = part.get_filename()
        if disposition == "inline" and (filename or part.get_content_maintype() != "text"):
            self.skip(Skipped(filename or content_type, SKIP_INLINE))
            return
        if not filename and disposition != "attachment" and part.get_content_maintype() in ("text", "multipart"):
            self.skip(Skipped(content_type, SKIP_BODY))
            return
        payload = part.get_payload(decode=True)
        if not isinstance(payload, (bytes, bytearray)) or not payload:
            self.skip(Skipped(filename or content_type, SKIP_EMPTY))
            return
        self.spend(len(payload))
        name = safe_name(filename, lambda: self.fallback() + _extension_for(content_type))
        self.add(name, bytes(payload), depth)

    def _msg(self, data: bytes, depth: int) -> None:
        import olefile

        try:
            ole = olefile.OleFileIO(io.BytesIO(data), raise_defects=olefile.DEFECT_INCORRECT)
        except Exception as exc:         # olefile raises OSError and its own kinds for damage
            raise NotOpened(reasons.CONTAINER_DAMAGED.format(error=_said(exc))) from exc
        try:
            self._msg_storage(ole, [], depth)
        except NotOpened:
            raise
        except Exception as exc:         # a malformed stream, a chain out of range, a loop
            raise NotOpened(reasons.CONTAINER_DAMAGED.format(error=_said(exc))) from exc
        finally:
            ole.close()

    def _msg_storage(self, ole, prefix: list[str], depth: int) -> None:
        """Every attachment storage directly under ``prefix``, in order."""
        storages = sorted(
            {tuple(entry[:len(prefix) + 1]) for entry in ole.listdir(streams=True, storages=True)
             if len(entry) > len(prefix) and entry[:len(prefix)] == prefix
             and entry[len(prefix)].startswith(_ATTACH_PREFIX)}
        )
        for storage in storages:
            self._msg_attachment(ole, list(storage), depth)

    def _msg_attachment(self, ole, storage: list[str], depth: int) -> None:
        properties = _msg_properties(ole, storage)
        method = properties.get(_PROP_METHOD, _BY_VALUE)
        name = _msg_name(ole, storage)
        shown = name or f"attachment {storage[-1][len(_ATTACH_PREFIX):]}"
        if properties.get(_PROP_HIDDEN, 0) or properties.get(_PROP_FLAGS, 0) & _RENDERED_IN_PLACE:
            self.skip(Skipped(shown, SKIP_INLINE))
            return
        if method in _BY_REFERENCE:
            self.skip(Skipped(shown, SKIP_REFERENCE))
            return
        if method == _OLE:
            self.skip(Skipped(shown, SKIP_OLE))
            return
        if method == _EMBEDDED:
            inner = [*storage, _EMBEDDED_STORAGE]
            if not ole.exists("/".join(inner)):
                self.skip(Skipped(shown, SKIP_EMPTY))
                return
            if depth + 1 > MAX_DEPTH:
                # An embedded message has no bytes of its own to hand back
                # as a file; it stops the whole container.
                raise NotOpened(reasons.CONTAINER_LIMIT.format(error=LIMIT_DEPTH))
            self._msg_storage(ole, inner, depth + 1)
            return
        stream = "/".join([*storage, _DATA_STREAM])
        if not ole.exists(stream):
            self.skip(Skipped(shown, SKIP_EMPTY))
            return
        size = ole.get_size(stream)
        if self.produced + size > MAX_TOTAL_BYTES:
            raise NotOpened(reasons.CONTAINER_LIMIT.format(error=LIMIT_TOTAL))
        with ole.openstream(stream) as handle:
            payload = handle.read()
        if not payload:
            self.skip(Skipped(shown, SKIP_EMPTY))
            return
        self.spend(len(payload))
        self.add(safe_name(name, self.fallback), payload, depth)


def _msg_properties(ole, storage: list[str]) -> dict[int, int]:
    """The three numbers read off an attachment's properties stream: its
    method, whether it is hidden, and its flags. Each entry is 16 bytes -
    the tag (type in the low word, id in the high), 4 bytes of flags, then
    the value, whose first 4 bytes are a fixed-size number's."""
    path = "/".join([*storage, _PROPERTIES])
    if not ole.exists(path):
        return {}
    with ole.openstream(path) as handle:
        raw = handle.read()
    found: dict[int, int] = {}
    for at in range(_ATTACHMENT_HEADER, len(raw) - _PROPERTY_SIZE + 1, _PROPERTY_SIZE):
        tag = int.from_bytes(raw[at:at + 4], "little")
        prop, kind = tag >> 16, tag & 0xFFFF
        if prop in (_PROP_METHOD, _PROP_FLAGS) and kind == 0x0003:
            found[prop] = int.from_bytes(raw[at + 8:at + 12], "little")
        elif prop == _PROP_HIDDEN and kind == 0x000B:
            found[prop] = int.from_bytes(raw[at + 8:at + 10], "little")
    return found


def _msg_name(ole, storage: list[str]) -> str:
    """The attachment's own name, from the first name stream it has."""
    for stream in _NAME_STREAMS:
        path = "/".join([*storage, stream])
        if not ole.exists(path):
            continue
        with ole.openstream(path) as handle:
            raw = handle.read(4096)
        text = (raw.decode("utf-16-le", "replace") if stream.endswith("001F")
                else raw.decode("cp1252", "replace"))
        text = text.split("\x00", 1)[0].strip()
        if text:
            return text
    return ""


#: The extension a part with no name of its own is given, by what its
#: Content-Type says. A fixed table rather than ``mimetypes``, whose answer
#: on Windows is read from the machine's registry: two machines would name
#: one part two ways. A type not here gets no extension, and parks.
_EXTENSION_FOR: dict[str, str] = {
    "application/pdf": ".pdf",
    "image/jpeg": ".jpg", "image/png": ".png", "image/gif": ".gif", "image/tiff": ".tif",
    "image/heic": ".heic", "image/heif": ".heif",
    "text/csv": ".csv", "text/plain": ".txt", "text/html": ".html",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "application/vnd.ms-excel": ".xls",
    "application/zip": ".zip", "application/x-zip-compressed": ".zip",
    "message/rfc822": ".eml", "application/vnd.ms-outlook": ".msg",
}


def _extension_for(content_type: str) -> str:
    """The extension a part with no name gets, from :data:`_EXTENSION_FOR`."""
    return _EXTENSION_FOR.get(content_type.lower(), "")


def _said(exc: BaseException) -> str:
    """An exception as a short clause: its kind, and its first line."""
    text = str(exc).splitlines()[0][:120] if str(exc) else ""
    return f"{exc.__class__.__name__}: {text}" if text else exc.__class__.__name__


if __name__ == "__main__":
    import argparse
    import sys
    from pathlib import Path

    from tracker.page import tolerant_console

    # It prints the names of a client's attachments.
    tolerant_console()
    parser = argparse.ArgumentParser(
        description="List what one email or zip holds, in memory; nothing is written.")
    parser.add_argument("container", type=Path)
    args = parser.parse_args()
    try:
        opened = open_container(args.container.read_bytes(), args.container.suffix)
    except NotOpened as exc:
        print(f"not opened: {exc.sentence}")
        sys.exit(1)
    for one in opened.attachments:
        print(f"{len(one.data):>10,}  {one.name}" + (f"  (parks: {one.parks})" if one.parks else ""))
    for one in opened.skipped:
        print(f"{'skipped':>10}  {one.name}: {one.why}")
