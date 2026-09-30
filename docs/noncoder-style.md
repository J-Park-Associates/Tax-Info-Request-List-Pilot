# How to write a "For NonCoders" page

The reader is the firm's owner, a CPA who does not code. Write so a third
grader could follow: short sentences, common words, one idea per sentence.

## Hard rules

1. **Never invent a fact.** Every claim must come from the original file
   (or a file it names, which you may open to check). If you are unsure, leave
   it out. Keep numbers, names, dates, decision numbers and file names exactly.
2. **Define every technical word the first time you use it**, in plain words,
   in the text itself (for example: "a *lock file* - a list of every outside
   part the program uses, with a fingerprint for each"). Also list them under
   "Words to know" at the end.
3. Do **not** copy code. A command may be shown only if a person would type
   it; then say in words what it does.
4. Keep it short: about 40-120 lines per page. A long original gets a
   summary, not a line-by-line retelling.
5. Never write a sentence telling a person to run something "once after
   installing" or "once after upgrading" (a repository test forbids it).
6. Do not include any real client's name or data. Made-up test names in the
   original (Smith Family, Rivera Design LLC, Ana Lopez) may be mentioned as
   made-up examples.
7. Use plain Markdown. Start the file with the exact header block below.

## Page layout for a PROGRAM FILE

```
# <Plain-English name of the file>

**Original file:** `<exact path(s) from the repository root>`
**Kind of file:** <one plain phrase, e.g. "installer recipe", "Windows batch script">
**Tags:** Kind: <kind> · Topic: <topic>[, <topic>...][ · Stage: <S1>]

## In one sentence
## What it is
## What it does, step by step
## Why it matters to the firm
## What must never be changed without a programmer
## Words to know
```

## Page layout for a HANDOFF NOTE

A handoff note is a message one work session left for the next. Translate
what it says, not the code it talks about.

```
# <Plain-English title: what this session did>

**Original file:** `<exact path from the repository root>`
**Kind of file:** handoff note (a message from one work session to the next)
**Tags:** Kind: <kind> · Topic: <topic>[, <topic>...][ · Stage: <S1>]
**Date:** <date in the note, or "not stated">

## In one sentence
## What this session was asked to do
## What it did
## What it found wrong, or what was left to do
## Decisions (made by Jason, or waiting for Jason)
## Words to know
```

If a section truly has nothing, write "Nothing is stated in the note."

## Tags

The Tags line uses the fixed vocabularies in `tools/noncoder_pages.py` (Kind,
Topic, and an optional Stage such as S6a). The start page is generated from
these lines; a page with an unknown tag fails the check.

## Keeping the library current

The library is kept honest by `tools/noncoder_pages.py`. A Stop hook and
`tests/test_noncoder_pages.py` fail when a page is missing or stale. A session
uses four commands:

```
python tools/noncoder_pages.py todo                  # what is out of date: page, originals to read, this file
python tools/noncoder_pages.py place NOTE            # where a new handoff note's page goes
python tools/noncoder_pages.py stamp ['PAGE' ...]    # after writing, updating or confirming a page
python tools/noncoder_pages.py organize [--dry-run]  # move and rename pages to where the rules say
```

The Stop hook runs `organize` by itself, so a page in the wrong folder or with
the wrong number is fixed without anyone asking; `todo` shows what it would do.
A page whose original was removed is moved to `7 - History/Retired Pages`, and
`stamp` keeps the version it replaces in `7 - History/Earlier Versions`. History
pages are records: never edit them, and they are not checked like pages.

Write or update the page from its original (never from memory), then `stamp`
it. Stamp a page you only reviewed and found still accurate; do not stamp one
you did not read. `pages.json` and the start page are generated - never edit
them by hand.

Name as an original only files a person or a session writes. Never name a
generated file that the code map hashes (`docs/repo-map.json`, `docs/repo-map.md`):
the map hashes `pages.json`, `pages.json` would hash the map, and the two could
never both be current.
