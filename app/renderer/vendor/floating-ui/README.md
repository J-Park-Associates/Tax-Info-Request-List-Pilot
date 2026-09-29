# Floating UI, vendored (tooltip placement only)

`app/renderer/tooltip.js` uses this for one job: placing the tooltip beside its
element, flipped and shifted so it stays inside the window. It is third-party
code, MIT licensed, copied here byte for byte and never edited. It is loaded by
plain `<script src>` tags before `tooltip.js`; there is no bundler, no
`node_modules` in the app and no network call (CSP `script-src 'self'`).

| Package | Version | Licence | Registry tarball integrity (`npm view <pkg>@<ver> dist.integrity`) |
|---|---|---|---|
| `@floating-ui/dom` | 1.8.0 | MIT | `sha512-yXSrzeHZBTZadLOlfyhCkJHNeLJnHRnRInwdZ40L7ZiaAtrBwoYlsDrX3v5zB1Utk7CLfzcOVnVVWoXEky7Ceg==` |
| `@floating-ui/core` | 1.8.0 | MIT | `sha512-0CIZ5itps/8x7BG8dEIhs53BvCUH2PCoogtakwRTut+Arm58sJooJ0AuZhLw2HJYIR5cMLNPBSS728sPho2khQ==` |
| `@floating-ui/utils` | 0.2.12 | MIT | `sha512-HpCo8tmWzLVad5s2d19EhAz5zqrrQ6s69qd6moPMQvkOuSwDT1YgRfWSVuc4ennqrgv3OHppiOGMQ7oC13yIww==` |

Each tarball was fetched with `npm pack` and its integrity compared with the
registry's before use.

## The files

| File | Taken from | SHA-256 |
|---|---|---|
| `floating-ui.core.umd.min.js` | `@floating-ui/core@1.8.0` `dist/floating-ui.core.umd.min.js` | `65940d866a6b6d831394a4bbed99ed0a39330bac98b643386d9a2f87a1a1d5da` |
| `floating-ui.dom.umd.min.js` | `@floating-ui/dom@1.8.0` `dist/floating-ui.dom.umd.min.js` | `61a46f943c4e99379eaf073447811aec7e8b8f120d2f646316e01b7694bc90a3` |
| `LICENSE-dom`, `LICENSE-core`, `LICENSE-utils` | each package's `LICENSE` | `0e4c9a9b6c71019cbbea3bdc20b01223110a9035700f9c960c8fcbf78c2325ce` (the three are identical) |

Why two script files and not three or one: the `core` UMD build already has
`@floating-ui/utils` compiled into it, and the `dom` UMD build has its own DOM
helpers compiled in and asks only for the `FloatingUICore` global. So loading
`floating-ui.core.umd.min.js` and then `floating-ui.dom.umd.min.js` gives the
one global `tooltip.js` uses, `FloatingUIDOM`, with nothing concatenated and
every byte checkable against the published package. The `utils` package is not
a file here; its licence is, because its code is inside `core`.

`tests/test_shell.py` pins the SHA-256 values above. To upgrade: `npm pack` the
new versions in a folder outside the repository, compare each integrity with
`npm view`, copy the same files, and change this page and the test together.
