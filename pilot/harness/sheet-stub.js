// A stand-in for the side sheet's frame (SPEC-shell 14.4), so its edge, its
// shadow and its scrim can be seen and a row's Check and Draft reminder steps
// have somewhere to go. The sheet's content is S5's (sheet.js). Never loaded
// by the app.
"use strict";

function closeSheet() {
  $("sheet").hidden = true;
  $("sheet-scrim").hidden = true;
}

function openSheetFrame(title) {
  $("sheet-title").textContent = title;
  $("sheet-body").replaceChildren(Object.assign(document.createElement("p"), { textContent: "Sheet content is S5's." }));
  $("sheet-scrim").hidden = false;
  $("sheet").hidden = false;
  $("sheet-title").focus();
}

// The row steps of pages.js call these two when they exist.
function openCheck(ret, name) {
  openSheetFrame(name);
}
function openReminder(ret) {
  openSheetFrame(vocab.screen.sheet.reminder);
}
