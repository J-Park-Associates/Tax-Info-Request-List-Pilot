# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

A Windows desktop app: an Electron window around plain HTML, CSS and
JavaScript, with a Python engine behind it. The design language is web, tuned
to Windows (Segoe UI, Windows contrast themes, a real menu bar).

## Users

Staff at a CPA firm (J Park & Associates first, then a small group of pilot
firms) who prepare individual and business tax returns. In season they track
which documents each client has sent, check the files the system could not
place, and remind clients about what is still missing. A firm keeps roughly
200 to 500 households in the app in a season (Jason, 2026-09-29).

## Product Purpose

Tracks tax-document requests per return. The client drops everything into one
folder; a scheduled job files each document against the return's request list,
keeps the originals untouched, and drafts (never sends) reminder emails.
Success: a preparer sees at a glance what each return still needs and what is
waiting for a person, without opening folders.

## Positioning

Deterministic filing with no guessing: a document is filed only when exactly
one request accepts it, otherwise it waits for a person. No generative AI reads
a client document, and nothing is ever sent.

## Operating Context

Windows PCs in the office, one of which runs the schedule. Client folders live
on a Google Drive Shared Drive synced to the PC. Households hold tax years;
years hold returns (1040, 1120, 1120-S, 1065, 1041, 990). Remote Desktop use is
common, so the screen must stay fast without a graphics card.

## Capabilities and Constraints

- The four standing rules in `tracker/__init__.py` (`STANDING_RULES`) hold
  everywhere and stay reachable in the app.
- Every word on screen comes from the Python API's vocabulary; the renderer
  types no sentences of its own.
- No new packages for the screen; no network call; the page's content security
  policy stays (`script-src 'self'; style-src 'self'`).
- Changes that reach the engine (`tracker/`) need their own SPEC.

## Brand Commitments

The navy design of `style.css` and the Build E tokens in `pilot-ui.css` (P50,
P51-P53): navy, Segoe UI, flat surfaces, 4px grid. No glass, blur or window
material (P48-P50). Microsoft's Fluent guidance is the reference (P57).

## Evidence on Hand

No real client data may enter the repository or any mock-up; stubbed pages use
made-up names only (for example the Smith Family sample).

## Product Principles

1. Nothing is guessed: when unsure, show it to a person rather than decide.
2. Every element must earn its place; explanation lives one hover away.
3. The firm view comes first; one client is a drill-down from it.
4. Daily work is on screen; one-time actions live in the menu bar.

## Accessibility & Inclusion

WCAG AA contrast at minimum, AAA for body text where the palette allows;
Windows contrast themes honoured; full keyboard use; nothing conveyed by colour
alone.
