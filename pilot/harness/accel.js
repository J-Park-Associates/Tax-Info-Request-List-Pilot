// The menu's accelerators, mapped to the menu channel's commands because a
// browser has no menu bar (SPEC-shell 14.4): Ctrl+1 to Ctrl+4, Ctrl+F, Ctrl+N,
// Ctrl+E, F5 and F9. Loaded in both modes. Never loaded by the app.
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
