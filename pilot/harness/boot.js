// The harness's start: app.js begins its own bootstrap() as its last line;
// the double is started here, once every script is in place. The accelerators
// the menu owns in the app are mapped to the menu channel's commands here,
// because a browser has no menu bar. Never loaded by the app.
"use strict";

document.addEventListener("keydown", (e) => {
  const map = { "1": "overview", "2": "needs_review", "3": "reminders", "4": "clients", f: "find", n: "new_household", e: "edit_list" };
  if (e.ctrlKey && map[e.key]) {
    e.preventDefault();
    shellMenu({ id: map[e.key] });
  } else if (e.key === "F9") {
    e.preventDefault();
    shellMenu({ id: "sort_now" });
  } else if (e.key === "F5") {
    e.preventDefault();
    shellMenu({ id: "refresh" });
  }
}, true);
document.addEventListener("keydown", (e) => { shellKey(e); });
bootstrap();
