// The harness's page stand-in (SPEC-shell 14.4): draws the row, the group
// and the empty state of shell.css from the harness data, so the foundation's
// components can be seen before pages.js (S4) exists. It is not the pages:
// no menu, no listbox keys, no sheet content. Never loaded by the app.
"use strict";

(() => {
  const words = () => vocab.screen;
  const node = (tag, className, ...kids) => {
    const one = document.createElement(tag);
    if (className) one.className = className;
    one.append(...kids.filter((k) => k !== null && k !== undefined && k !== false));
    return one;
  };
  const TONE = { needs: "is-attention", waiting: "is-waiting", received: "is-done", set: "is-plain" };

  function row(r, tone, stepWords) {
    const step = stepWords ? node("span", "row-step", stepWords) : null;
    const one = node("div", `row${stepWords ? " has-step" : ""}`,
      node("span", "row-name", r.name),
      node("span", "row-detail", r.detail || ""),
      node("span", `row-status ${TONE[tone] || ""}`, r.status || ""),
      node("span", "row-end", node("span", "row-date", r.date || ""), step));
    one.setAttribute("role", "option");
    setTipIfCut(one.querySelector(".row-name"), r.name);
    return one;
  }
  function group(title, rows, first, emptyLine) {
    const head = node("div", `group-head${first ? " is-first" : ""}`, node("h2", "group-title", title), node("span", "group-count", String(rows.length)));
    const list = node("div", "rows");
    list.setAttribute("role", "listbox");
    list.tabIndex = 0;
    list.append(...rows);
    return [head, rows.length ? list : node("div", "group-none", emptyLine)];
  }
  const returnRows = (list) => list.map((e) => {
    const body = window.HARNESS.bodies[e.path];
    const owner = households.find((h) => h.path === e.household);
    const need = body.needs.length;
    const wait = body.waiting.length;
    const status = need ? fill(words().counts.need, { n: need }) : wait ? fill(words().counts.waiting, { n: wait }) : words().counts.complete;
    const tone = need ? "needs" : wait ? "waiting" : "received";
    return row({ name: e.return_name, detail: owner.name, status, date: need ? "Mar 3" : wait ? body.due : "" }, tone, words().steps.open);
  });
  const thisYear = () => engagements.filter((e) => e.year === 2025);

  function draw(route, page) {
    const w = words();
    const firm = shellFirm().data;
    const out = [];
    if (route.level === "overview") {
      const t = firm.totals;
      out.push(node("h1", "page-title", w.sections.overview));
      out.push(node("div", "figures", ...[[t.need, w.figures.need], [t.waiting, w.figures.waiting], [t.complete, w.figures.complete]]
        .map(([n, label]) => node("div", "figure", node("b", "figure-number", String(n)), node("span", "figure-label", label)))));
      const work = thisYear().filter((e) => { const b = window.HARNESS.bodies[e.path]; return b.needs.length || b.waiting.length; }).slice(0, 12);
      out.push(...group(w.work, returnRows(work), true, w.empty.work));
    } else if (route.level === "needs-review") {
      out.push(node("h1", "page-title", w.sections.needs_review));
      const rows = [];
      for (const e of thisYear()) for (const f of window.HARNESS.bodies[e.path].needs.filter((x) => x.kind !== "request")) rows.push(row({ name: f.name, detail: e.return_name, status: f.status, date: f.date }, "needs", w.steps.check));
      out.push(node("div", "page-caption", fill(w.counts.files, { n: rows.length })));
      out.push(...group(w.groups.needs_you, rows.slice(0, 14), true, w.empty.needs_review));
    } else if (route.level === "reminders") {
      out.push(node("h1", "page-title", w.sections.reminders));
      const rows = thisYear().filter((e) => window.HARNESS.bodies[e.path].draft).map((e) => row({ name: e.return_name, detail: households.find((h) => h.path === e.household).name, status: w.held, date: "Mar 3" }, "waiting", w.steps.draft));
      out.push(...group(w.sections.reminders, rows, true, w.empty.reminders));
    } else if (route.level === "clients") {
      out.push(node("h1", "page-title", w.sections.clients));
      const rows = households.slice(0, 30).map((h) => row({ name: h.name, detail: fill(h.returns.length === 1 ? w.counts.one_return : w.counts.returns, { n: h.returns.length }), status: h.returns.length ? w.counts.complete : "", date: "" }, "received", w.steps.open));
      out.push(...group(w.filters.all, rows, true, w.empty.clients));
    } else if (route.level === "household") {
      const h = households.find((x) => x.path === route.household);
      out.push(node("h1", "page-title", h.name), node("div", "page-caption", fill(w.contact, { name: h.contact })));
      out.push(...(h.returns.length ? group(w.sections.clients, returnRows(engagements.filter((e) => e.household === h.path)), true, "") : [node("div", "page-empty", w.empty.returns)]));
    } else if (route.level === "year") {
      out.push(node("h1", "page-title", String(route.year)));
      out.push(...group(w.sections.clients, returnRows(engagements.filter((e) => e.household === route.household && e.year === route.year)), true, w.empty.returns));
    } else if (route.level === "return") {
      const b = lastState && lastState.harness;
      const e = engagements.find((x) => x.path === route.ret);
      out.push(node("h1", "page-title", e.return_name), node("div", "page-caption", b.due ? b.due.replace("Due ", fill(w.due, { date: "" })) : ""));
      const rows = (list, tone, step) => list.map((r) => row(r, tone, step(r)));
      out.push(...group(w.groups.needs_you, rows(b.needs, "needs", (r) => (r.kind === "request" ? w.steps.edit : w.steps.check)), true, ""));
      out.push(...group(w.groups.waiting, rows(b.waiting, "waiting", () => w.steps.draft), false, ""));
      out.push(...group(w.groups.received, rows(b.received, "received", () => null), false, w.empty.received));
      out.push(...group(w.groups.set_aside, rows(b.setAside, "set", () => null), false, ""));
    }
    page.replaceChildren(...out);
  }
  window.pagesDraw = draw;

  // A stand-in for the sheet's frame, so its edge, shadow and scrim can be seen.
  window.closeSheet = () => { $("sheet").hidden = true; $("sheet-scrim").hidden = true; };
  window.openSheetFrame = (title) => {
    $("sheet-title").textContent = title;
    $("sheet-body").replaceChildren(node("p", "", "Sheet content is S5's."));
    $("sheet-scrim").hidden = false;
    $("sheet").hidden = false;
    $("sheet-title").focus();
  };
})();
