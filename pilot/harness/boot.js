// The harness's start of the double: app.js begins its own bootstrap() as its
// last line; the double is started here, once every script is in place (the
// accelerators are accel.js's). Never loaded by the app.
"use strict";

document.addEventListener("keydown", (e) => { shellKey(e); });
bootstrap();
