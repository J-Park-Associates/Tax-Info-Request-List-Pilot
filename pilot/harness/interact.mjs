// Drives the shell in the harness the way a person would and asserts what
// happens (SPEC-shell 14.4): routes, the search, the sort icon, F6, Esc, the
// setup page, Help > Terms and Help > Take the tour. Made-up names only.
//
//   HARNESS_PYTHON=... node pilot/harness/interact.mjs
import { createRequire } from "node:module";
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { serve } from "./serve.mjs";

const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "/opt/node22/lib/node_modules/playwright");
const here = path.dirname(fileURLToPath(import.meta.url));
const vocabFile = path.join(fs.mkdtempSync(path.join(os.tmpdir(), "harness-")), "vocab.json");
execFileSync(process.env.HARNESS_PYTHON || "python3", [path.join(here, "make_vocab.py"), vocabFile], { cwd: path.resolve(here, "..", ".."), stdio: "inherit" });
const { server, port } = await serve(fs.readFileSync(vocabFile, "utf-8"));
const base = `http://127.0.0.1:${port}/`;

const browser = await chromium.launch({ args: ["--no-sandbox"] });
const failures = [];
const check = (name, ok, got) => { if (!ok) failures.push(`${name}: ${JSON.stringify(got)}`); };

// The shell's own sections run on the double of app.js (the default here); the ones that need the real
// app.js (the side sheet, the writes, the notices) say "?mode=real".
async function open(query = "", { firm = true } = {}) {
  if (!/mode=/.test(query)) query = `${query}${query ? "&" : "?"}mode=double`;
  const context = await browser.newContext({ viewport: { width: 1100, height: 700 } });
  await context.addInitScript(() => { localStorage.setItem("pilot.terms.accepted", "1"); localStorage.setItem("pilot.tour.seen", "1"); });
  const page = await context.newPage();
  page.on("pageerror", (e) => failures.push(`page error: ${e.message}`));
  await page.goto(`${base}${query}`);
  await page.waitForFunction((needsFirm) => window.HARNESS && window.HARNESS.calls.includes(needsFirm ? "firm" : "list") && !document.querySelector("#page[aria-busy=true]") && document.querySelector("#page > *, #notices > *"), firm, { timeout: 8000 });
  return { context, page };
}
const current = (page) => page.evaluate(() => document.querySelector('.side-section[aria-current="page"] .side-name')?.textContent ?? null);
const crumbs = (page) => page.evaluate(() => [...document.querySelectorAll("#crumb-list li")].map((li) => li.textContent));

{ // routes, the side panel and its counts
  const { context, page } = await open();
  check("opens on Overview", (await current(page)) === "Overview", await current(page));
  const counts = await page.evaluate(() => [...document.querySelectorAll(".side-count")].map((n) => n.textContent));
  check("counts on the two that hold work", counts.join("|") === "|27|3|", counts);
  await page.evaluate(() => shellMenu({ id: "needs_review" }));
  check("Ctrl+2 goes to Needs Review", (await current(page)) === "Needs Review", await current(page));
  await page.keyboard.press("Control+4");
  check("Ctrl+4 goes to Clients", (await current(page)) === "Clients", await current(page));
  await page.click('.side-section[data-section="overview"]');
  check("a click goes to Overview", (await current(page)) === "Overview", await current(page));
  const enabled = await page.evaluate(() => window.HARNESS.menuLog.at(-1).enable);
  check("the enable list is sent", enabled.includes("overview") && !enabled.includes("edit_list"), enabled);
  await context.close();
}

{ // search
  const { context, page } = await open();
  await page.keyboard.press("Control+f");
  check("Ctrl+F focuses the search", await page.evaluate(() => document.activeElement.id) === "find", null);
  await page.keyboard.type("rivera");
  const options = await page.evaluate(() => [...document.querySelectorAll(".find-option .find-name")].map((n) => n.textContent));
  check("the search lists households first", options[0] === "Rivera Design" && options.length === 3, options);
  await page.keyboard.press("ArrowDown");
  await page.keyboard.press("Enter");
  check("Enter opens the chosen option", (await crumbs(page)).join("|") === "Clients|Rivera Design|2025|1120-S - Rivera Design LLC", await crumbs(page));
  await page.keyboard.press("Control+f");
  await page.keyboard.type("zzz");
  check("no match says so", (await page.textContent("#find-list")) === "No Match", await page.textContent("#find-list"));
  await page.keyboard.press("Escape");
  check("Esc clears and closes", (await page.inputValue("#find")) === "" && await page.evaluate(() => document.getElementById("find-list").hidden), null);
  await context.close();
}

{ // the sort icon, F6
  const { context, page } = await open();
  check("grey on a firm page", await page.evaluate(() => document.getElementById("sort").disabled), null);
  await page.evaluate(() => shellGo({ level: "household", household: "/clients/J Park & Associates/Smith Family" }));
  check("ready on a household", !(await page.evaluate(() => document.getElementById("sort").disabled)), null);
  await page.keyboard.press("F9");
  await page.waitForTimeout(300);
  check("F9 starts a sort", (await page.evaluate(() => document.getElementById("sort").dataset.sortState)) === "stop", null);
  check("the foot says how far", (await page.textContent("#last-sort")).startsWith("Sorting 1 of 12"), await page.textContent("#last-sort"));
  await page.click("#sort");
  await page.waitForTimeout(200);
  check("a click stops it", (await page.evaluate(() => document.getElementById("sort").dataset.sortState)) === "stopping", null);
  await page.waitForTimeout(1800);
  check("and it gives the icon back", (await page.evaluate(() => document.getElementById("sort").dataset.sortState)) === "now", null);
  await page.focus("#page");
  await page.keyboard.press("F6");
  check("F6 goes to the side panel", await page.evaluate(() => document.activeElement.closest("#side") !== null), null);
  await page.keyboard.press("F6");
  check("then the path row", await page.evaluate(() => document.activeElement.closest("#bar") !== null), null);
  await page.keyboard.press("F6");
  check("then the page", await page.evaluate(() => document.activeElement.id) === "page", null);
  await context.close();
}

{ // the setup page
  const { context, page } = await open("?scenario=setup", { firm: false });
  check("first run shows the setup page", (await page.textContent("#page h1")) === "Choose Your Clients Folder", null);
  check("start waits for a folder", await page.evaluate(() => document.getElementById("setup-start").disabled), null);
  check("the sections are disabled", await page.evaluate(() => [...document.querySelectorAll(".side-section")].every((n) => n.disabled)), null);
  await page.click("#setup-pick");
  await page.waitForFunction(() => document.getElementById("setup-chosen").textContent === "Client Files");
  check("only the folder's own name shows", (await page.textContent("#setup-chosen")) === "Client Files", null);
  await page.click("#setup-start");
  await page.waitForFunction(() => document.querySelector('.side-section[aria-current="page"]'), null, { timeout: 8000 });
  check("start lands on Overview", (await current(page)) === "Overview", await current(page));
  await page.evaluate(() => shellMenu({ id: "change_root" }));
  check("Change clients folder shows the page with Cancel", await page.evaluate(() => Boolean(document.getElementById("setup-cancel"))), null);
  await page.click("#setup-cancel");
  check("Cancel goes back", (await current(page)) === "Overview", await current(page));
  await context.close();
}

{ // the pilot layer and the tooltip
  const { context, page } = await open();
  await page.evaluate(() => shellMenu({ id: "terms" }));
  check("Help > Terms shows the card read only", await page.evaluate(() => Boolean(document.getElementById("pilot-terms-close")) && !document.getElementById("pilot-terms-agree")), null);
  await page.keyboard.press("Escape");
  check("Esc closes it", await page.evaluate(() => !document.getElementById("pilot-terms")), null);
  await page.evaluate(() => shellMenu({ id: "tour" }));
  check("Help > Take the tour starts the tour", await page.evaluate(() => Boolean(document.getElementById("pilot-tour"))), null);
  const steps = [];
  for (let i = 0; i < 11; i += 1) {
    steps.push(await page.evaluate(() => document.querySelector("#pilot-tour p").textContent));
    await page.keyboard.press("ArrowRight");
  }
  check("the tour says one short line per step", steps.every((s) => s.split(" ").length <= 5) && steps[0] === "Sorts what your clients send", steps);
  check("the tour ends", await page.evaluate(() => !document.getElementById("pilot-tour")), null);
  await page.hover("#sort");
  await page.waitForTimeout(700);
  check("a tooltip shows after hover", await page.evaluate(() => !document.getElementById("tip").hidden), null);
  await page.keyboard.press("Escape");
  check("Esc hides it", await page.evaluate(() => document.getElementById("tip").hidden), null);
  await context.close();
}

{ // the pages: a row list by keyboard and mouse
  const { context, page } = await open();
  const active = () => page.evaluate(() => { const list = document.querySelector("#page .rows"); return list && list.getAttribute("aria-activedescendant"); });
  await page.focus("#page .rows");
  const first = await active();
  check("focus lands on the first row", Boolean(first), first);
  await page.keyboard.press("ArrowDown");
  const second = await active();
  check("Down moves to the next row", second && second !== first, [first, second]);
  await page.keyboard.press("End");
  await page.keyboard.press("Home");
  check("Home goes back to the first row", (await active()) === first, await active());
  const named = await page.evaluate(() => { const row = document.querySelector("#page .row"); return [row.getAttribute("role"), row.querySelector(".row-step").getAttribute("aria-hidden"), row.getAttribute("aria-description")]; });
  check("a row is an option, its step hidden and named", named.join("|") === "option|true|Open", named);
  await page.hover("#page .row");
  const shown = await page.evaluate(() => getComputedStyle(document.querySelector("#page .row .row-step")).visibility);
  check("hover shows the step", shown === "visible", shown);
  await page.keyboard.press("Enter");
  await page.waitForFunction(() => document.querySelector("#crumb-list li:last-child")?.textContent.startsWith("1"));
  check("Enter runs the step and opens the return", (await crumbs(page)).length === 4, await crumbs(page));
  await page.evaluate(() => shellGo({ level: "return", household: "/clients/J Park & Associates/Smith Family", year: 2025, ret: "/clients/J Park & Associates/Smith Family/2025/1040 - John & Jane Smith" }));
  await page.waitForFunction(() => document.querySelector("#page details") && !document.querySelector("#page[aria-busy=true]"), null, { timeout: 5000 });
  const titles = await page.evaluate(() => [...document.querySelectorAll("#page .group-title")].map((n) => n.textContent));
  check("the return draws its groups in order", titles.join("|") === "Needs You|Waiting on Client|Received|Set Aside", titles);
  check("Set aside is shut", await page.evaluate(() => !document.querySelector("#page details").open), null);
  await page.focus("#page .rows");
  const before = await page.evaluate(() => document.querySelectorAll("#notices .notice").length);
  await page.keyboard.press("Enter");
  await page.waitForTimeout(300);
  const after = await page.evaluate(() => document.querySelectorAll("#notices .notice").length);
  check("on the double, a Check step says so in a notice: never silence", after === before + 1, [before, after]);
  await context.close();
}

{ // Clients: the switch, and no H1 on a firm page
  const { context, page } = await open();
  await page.click('.side-section[data-section="clients"]');
  const work = await page.evaluate(() => document.querySelectorAll("#page .row").length);
  await page.click(".switch-option:nth-child(2)");
  const all = await page.evaluate(() => document.querySelectorAll("#page .row").length);
  check("All lists more households than Work waiting", all > work && all >= 500, [work, all]);
  check("a firm page draws no H1", await page.evaluate(() => document.querySelectorAll("#page h1").length) === 0, null);
  await context.close();
}

{ // a household's notices come with its state
  const { context, page } = await open("?mode=real&scenario=household-notices");
  await page.evaluate(() => shellGo({ level: "household", household: "/clients/J Park & Associates/Smith Family" }));
  await page.waitForFunction(() => document.querySelectorAll("#notices .notice").length >= 3, null, { timeout: 5000 });
  const text = await page.textContent("#notices");
  check("two years, folder renamed with Accept", text.includes("Two Years Open") && text.includes("Accept"), text);
  const logged = await page.evaluate(() => window.HARNESS.logged.join("\n"));
  check("the pause and the feed are short lines on screen and long sentences in the error log", !text.includes("Paused:") && !text.includes("drop folder") && logged.includes("Paused: this folder's name") && logged.includes("this drop folder is set to feed"), [text, logged]);
  await page.evaluate(() => shellGo({ level: "clients" }));
  check("they go when the household's pages do", await page.evaluate(() => !document.querySelector("#notices .notice")), null);
  await context.close();
}

{ // the page's tally of a return equals the firm's counts, so opening it does not read the firm again
  const { context, page } = await open("?mode=real");
  const before = await page.evaluate(() => window.HARNESS.calls.filter((c) => c === "firm").length);
  await page.evaluate(() => shellGo({ level: "return", household: "/clients/J Park & Associates/Smith Family", year: 2025, ret: "/clients/J Park & Associates/Smith Family/2025/1040 - John & Jane Smith" }));
  await page.waitForFunction(() => document.querySelector("#page h1") && document.querySelectorAll("#page .group-title").length >= 3, null, { timeout: 5000 });
  await page.waitForTimeout(500);
  const after = await page.evaluate(() => window.HARNESS.calls.filter((c) => c === "firm").length);
  check("opening a return with a moved file marked missing does not re-read the firm", after === before, [before, after]);
  await page.click(".group-fold summary");
  const rows = await page.evaluate(() => [...document.querySelectorAll(".group-fold .row-name")].map((n) => n.textContent));
  check("the marked-missing moved file is under Set aside", rows.includes("lost-in-move.pdf"), rows);
  await context.close();
}

{ // a live lock: one notice, and the request list is not offered
  const { context, page } = await open("?mode=real&scenario=locked");
  await page.evaluate(() => shellGo({ level: "return", household: "/clients/J Park & Associates/Smith Family", year: 2025, ret: "/clients/J Park & Associates/Smith Family/2025/1040 - John & Jane Smith" }));
  await page.waitForFunction(() => document.querySelector("#notices .notice"), null, { timeout: 5000 });
  const steps = await page.evaluate(() => [...document.querySelectorAll("#page .row-step")].map((n) => n.textContent));
  check("the lock is one notice", (await page.textContent("#notices")).includes("In Use on"), await page.textContent("#notices"));
  check("no row offers Edit while locked", !steps.includes("Edit") && steps.includes("Check"), steps);
  await page.focus("#page .rows");
  await page.keyboard.press("Enter");
  await page.waitForFunction(() => !document.getElementById("sheet").hidden && document.querySelector("#check-actions .btn"), null, { timeout: 5000 });
  const greyed = await page.evaluate(() => [...document.querySelectorAll("#check-actions .btn")].map((b) => b.disabled));
  check("a locked return's sheet opens and its writing buttons are greyed", greyed.length === 2 && greyed.every(Boolean), greyed);
  await context.close();
}

{ // every loud failure, over the API's long sentences: five words at most, no path (SPEC 11.1)
  for (const scenario of ["notices", "household-notices", "locked", "stale-lock"]) {
    const { context, page } = await open(`?mode=real&scenario=${scenario}`);
    if (scenario !== "notices") {
      await page.evaluate(() => shellGo({ level: "return", household: "/clients/J Park & Associates/Smith Family", year: 2025, ret: "/clients/J Park & Associates/Smith Family/2025/1040 - John & Jane Smith" }));
      await page.waitForFunction(() => document.querySelector("#notices .notice"), null, { timeout: 5000 });
    }
    await page.waitForTimeout(300);
    const texts = await page.evaluate(() => [...document.querySelectorAll("#notices .notice-text")].map((n) => n.textContent.trim()));
    check(`${scenario}: notices are drawn`, texts.length > 0, texts);
    check(`${scenario}: no notice is over five words or holds a path`, texts.every((t) => t.split(/\s+/).length <= 5 && !/[A-Za-z]:\\|\\|\//.test(t)), texts);
    await context.close();
  }
}

{ // a count failure is one notice with Retry
  const { context, page } = await open("?scenario=firm-fails");
  const text = await page.textContent("#notices");
  check("counts failure is one notice", text.includes("Counts Not Available") && text.includes("Retry"), text);
  await context.close();
}

{ // ruling 20: a failed sort is a notice with Retry at the top of every page; the side line stays; it clears when a sort works
  for (const mode of ["double", "real"]) {
    const { context, page } = await open(`?mode=${mode}&scenario=failed`);
    const failedNotice = () => page.evaluate(() => [...document.querySelectorAll("#notices .notice-failed")].filter((n) => n.querySelector(".notice-text").textContent === "Sort Failed").map((n) => [...n.querySelectorAll("button")].map((b) => b.textContent)[0]));
    check(`ruling 20 (${mode}): Overview shows the failed sort with Retry`, (await failedNotice()).join() === "Retry", await failedNotice());
    for (const level of ["needs-review", "reminders", "clients"]) {
      await page.evaluate((l) => shellGo({ level: l }), level);
      await page.waitForTimeout(150);
      check(`ruling 20 (${mode}): it is still there on ${level}, once`, (await failedNotice()).length === 1, await failedNotice());
    }
    check(`ruling 20 (${mode}): the side panel's Sort Failed line stays`, (await page.textContent("#last-sort")).includes("Sort Failed"), await page.textContent("#last-sort"));
    await page.evaluate(() => { shellLastPass = { ...shellLastPass, ok: true, text: "Sorted." }; shellChanged(); });
    check(`ruling 20 (${mode}): it clears when a sort works`, (await failedNotice()).length === 0, await failedNotice());
    await context.close();
  }
  const { context, page } = await open("?mode=double");
  const none = await page.evaluate(() => [...document.querySelectorAll("#notices .notice-text")].map((n) => n.textContent));
  check("ruling 20: a good last sort shows no failure notice", !none.includes("Sort Failed"), none);
  await context.close();
}

{ // ruling 21: a household paused for two open years is marked beside its name on Clients and is a row on Overview's Work Waiting
  const { context, page } = await open("?mode=real&scenario=paused");
  const overview = await page.evaluate(() => [...document.querySelectorAll("#page .row")].map((r) => [r.querySelector(".row-name").textContent, r.querySelector(".row-status").textContent]));
  check("ruling 21: Overview leads Work Waiting with the paused household, in the vocabulary's words", overview[0].join("|") === "Okafor Family|Two Years Open; Sorting Paused" && overview.filter((r) => r[1].includes("Paused")).length === 1, overview.slice(0, 3));
  await page.click("#page .row-name .row-link");
  await page.waitForFunction(() => document.querySelector("#page h1")?.textContent.includes("Okafor"), null, { timeout: 5000 });
  check("ruling 21: the paused household's row opens the household", true, null);
  await page.evaluate(() => shellGo({ level: "clients" }));
  await page.waitForSelector("#page .row");
  const marks = await page.evaluate(() => [...document.querySelectorAll("#page .row")].filter((r) => r.querySelector(".row-mark")).map((r) => [r.querySelector(".row-name .row-link").textContent, r.querySelector(".row-mark").textContent]));
  check("ruling 21: Clients marks the paused household beside its name, in Work Waiting too, and no other", marks.length === 1 && marks[0].join("|") === "Okafor Family|Two Years Open; Sorting Paused", marks);
  await context.close();
  const plain = await open("?mode=real");
  const none = await plain.page.evaluate(() => document.querySelectorAll("#page .row-mark").length + [...document.querySelectorAll("#page .row-status")].filter((n) => n.textContent.includes("Paused")).length);
  check("ruling 21: with no paused field on any return nothing is drawn", none === 0, none);
  await plain.context.close();
}

// ── the side sheet, the links, the right-click menus and the dialogs (S5), on the real app.js ──
const smith = "/clients/J Park & Associates/Smith Family";
const smithReturn = `${smith}/2025/1040 - John & Jane Smith`;
const smithRoute = { level: "return", household: smith, year: 2025, ret: smithReturn };
const goReturn = async (page) => {
  await page.evaluate((r) => shellGo(r), smithRoute);
  await page.waitForFunction(() => document.querySelector("#page h1") && document.querySelectorAll("#page .group-title").length >= 3, null, { timeout: 5000 });
};
const sheetTitle = (page) => page.evaluate(() => (document.getElementById("sheet").hidden ? null : document.getElementById("sheet-title").textContent));
const settle = (page) => page.waitForTimeout(250);

{ // Check a file: it opens on the row, keeps focus inside, closes on Esc and gives focus back
  const { context, page } = await open("?mode=real");
  await goReturn(page);
  await page.focus("#page .rows");
  await page.keyboard.press("Enter");
  await page.waitForFunction(() => document.querySelector("#sheet-check select"), null, { timeout: 5000 });
  check("Enter on a Check row opens the sheet on that file", (await sheetTitle(page)) === "scan0012.pdf", await sheetTitle(page));
  check("focus goes to the sheet's title", await page.evaluate(() => document.activeElement.id) === "sheet-title", null);
  check("the sheet is a modal dialog with the scrim behind it", await page.evaluate(() => document.getElementById("sheet").getAttribute("aria-modal") === "true" && !document.getElementById("sheet-scrim").hidden), null);
  const status = await page.textContent(".sheet-status");
  check("the status line is the short reason and the date", status.includes("Could Not Sort") && status.includes("Mar 3"), status);
  const footer = await page.evaluate(() => [...document.querySelectorAll("#check-actions .btn")].map((b) => b.textContent));
  check("the footer is Not Requested, then File It", footer.join("|") === "Not Requested|File It", footer);
  const icons = await page.evaluate(() => ["sheet-open", "sheet-more", "sheet-next", "sheet-close"].map((id) => !document.getElementById(id).hidden));
  check("Check offers open, more, next and dismiss", icons.every(Boolean), icons);
  for (let i = 0; i < 14; i += 1) await page.keyboard.press("Tab");
  check("Tab stays inside the sheet", await page.evaluate(() => document.activeElement.closest("#sheet") !== null), null);
  await page.keyboard.press("Escape");
  await settle(page);
  check("Esc closes the sheet", (await sheetTitle(page)) === null, await sheetTitle(page));
  check("and puts focus back on the row list", await page.evaluate(() => document.activeElement.getAttribute("role")) === "listbox", null);
  await page.focus("#page .rows");
  await page.keyboard.press("Enter");
  await page.waitForFunction(() => document.querySelector("#sheet-check select"), null, { timeout: 5000 });
  await page.click("#sheet-scrim", { position: { x: 20, y: 400 } });
  await settle(page);
  check("a click on the scrim closes it too", (await sheetTitle(page)) === null, await sheetTitle(page));
  await context.close();
}

{ // More folds the rarely used fields; Next moves on without writing
  const { context, page } = await open("?mode=real");
  await goReturn(page);
  await page.focus("#page .rows");
  await page.keyboard.press("Enter");
  await page.waitForFunction(() => document.querySelector("#sheet-check select"), null, { timeout: 5000 });
  const folded = await page.evaluate(() => document.querySelector(".sheet-more").classList.contains("hidden"));
  await page.click("#sheet-more");
  const shown = await page.evaluate(() => [!document.querySelector(".sheet-more").classList.contains("hidden"), document.getElementById("sheet-more").getAttribute("aria-expanded"), [...document.querySelectorAll(".sheet-more label > span")].map((n) => n.textContent)]);
  check("More is shut until it is opened, then holds Keyword and Reason", folded && shown[0] && shown[1] === "true" && shown[2].length >= 2, shown);
  const writes = await page.evaluate(() => window.HARNESS.writes.length);
  await page.click("#sheet-next");
  await page.waitForFunction(() => document.getElementById("sheet-title").textContent === "IMG_2231.jpg", null, { timeout: 5000 });
  check("Next shows the following file and writes nothing", (await page.evaluate(() => window.HARNESS.writes.length)) === writes, null);
  check("More is shut again on the next file", await page.evaluate(() => document.getElementById("sheet-more").getAttribute("aria-expanded")) === "false", null);
  await page.click("#sheet-next");
  await page.waitForFunction(() => document.getElementById("sheet-title").textContent === "northwind-2025.pdf", null, { timeout: 5000 });
  const moved = await page.evaluate(() => [...document.querySelectorAll("#check-actions .btn")].map((b) => b.textContent));
  check("a moved-by-hand copy offers Keep and Put Back, and no open icon", moved.length === 2 && await page.evaluate(() => document.getElementById("sheet-open").hidden), moved);
  await page.click("#sheet-next");
  await page.waitForFunction(() => document.getElementById("sheet-title").textContent === "statement-march.eml", null, { timeout: 5000 });
  check("an email offers no open icon: it has no review copy to open", await page.evaluate(() => document.getElementById("sheet-open").hidden), null);
  await page.click("#sheet-next");
  await page.waitForFunction(() => document.getElementById("sheet-title").textContent === "scan-of-a-postcard.heic", null, { timeout: 5000 });
  check("the last file has no Next", await page.evaluate(() => document.getElementById("sheet-next").hidden), null);
  const type = await page.textContent("#sheet-check");
  check("a file that is not a document says its true type and offers only the set-aside answer", type.includes(".heic") && (await page.evaluate(() => [...document.querySelectorAll("#check-actions .btn")].map((b) => b.textContent))).join("|") === "Not Requested", type);
  await context.close();
}

{ // a write that works: the file leaves the list, the sheet shows the next, and closes after the last
  const { context, page } = await open("?mode=real");
  await goReturn(page);
  await page.focus("#page .rows");
  await page.keyboard.press("Enter");
  await page.waitForFunction(() => document.querySelector("#sheet-check select"), null, { timeout: 5000 });
  await page.click("#check-actions .btn-primary");
  await page.waitForFunction(() => document.getElementById("sheet-title").textContent === "IMG_2231.jpg", null, { timeout: 5000 });
  const first = await page.evaluate(() => window.HARNESS.writes.map((w) => w.command));
  check("File It writes once and the sheet moves to the next file", first.join() === "assign", first);
  const names = await page.evaluate(() => [...document.querySelectorAll("#page .rows")].flatMap((l) => [...l.querySelectorAll(".row-name")].map((n) => n.textContent)));
  check("the filed file is gone from the page behind", !names.includes("scan0012.pdf"), names);
  await page.click("#check-actions .btn:not(.btn-primary)");
  await page.waitForFunction(() => document.getElementById("sheet-title").textContent === "northwind-2025.pdf", null, { timeout: 5000 });
  check("Not Requested writes a dismissal", (await page.evaluate(() => window.HARNESS.writes.map((w) => w.command))).join() === "assign,dismiss", null);
  await page.click("#check-actions .btn-primary");
  await page.waitForFunction(() => document.getElementById("sheet-title").textContent === "statement-march.eml", null, { timeout: 5000 });
  await page.click("#check-actions .btn:not(.btn-primary)");
  await page.waitForFunction(() => document.getElementById("sheet-title").textContent === "scan-of-a-postcard.heic", null, { timeout: 5000 });
  await page.click("#check-actions .btn");
  await page.waitForFunction(() => document.getElementById("sheet").hidden, null, { timeout: 5000 });
  check("after the last file the sheet closes, with no message", await page.evaluate(() => document.querySelectorAll("#notices .notice").length) === 0, null);
  await context.close();
}

{ // Check from the firm-wide Needs Review page reads that return's state, then writes and moves on
  const { context, page } = await open("?mode=real");
  await page.evaluate(() => shellGo({ level: "needs-review" }));
  await page.waitForSelector("#page .row");
  const reads = await page.evaluate(() => window.HARNESS.calls.filter((c) => c === "state").length);
  await page.focus("#page .rows");
  await page.keyboard.press("Enter");
  await page.waitForFunction(() => document.querySelector("#sheet-check select"), null, { timeout: 5000 });
  check("opening a firm-page file reads that return's state once", (await page.evaluate(() => window.HARNESS.calls.filter((c) => c === "state").length)) === reads + 1, null);
  const first = await page.evaluate(() => sheetNow.ret);
  await page.click("#check-actions .btn-primary");
  await page.waitForFunction((was) => sheetNow && sheetNow.ret !== was && sheetNow.ready && document.querySelector("#sheet-check select"), first, { timeout: 5000 });
  check("the next file may belong to another return: its state is read too", (await page.evaluate(() => window.HARNESS.calls.filter((c) => c === "state").length)) >= reads + 2, null);
  await page.keyboard.press("Escape");
  await settle(page);
  check("closing it leaves the firm page as it was", await page.evaluate(() => shellRoute.level) === "needs-review" && await page.evaluate(() => document.querySelectorAll("#notices .notice").length) === 0, null);
  await context.close();
}

{ // a read that fails: one notice, the sheet closes
  const { context, page } = await open("?mode=real&scenario=state-fails");
  await page.evaluate(() => shellGo({ level: "needs-review" }));
  await page.waitForSelector("#page .row");
  await page.focus("#page .rows");
  await page.keyboard.press("Enter");
  await page.waitForFunction(() => document.getElementById("sheet").hidden && document.querySelector("#notices .notice"), null, { timeout: 5000 });
  check("a failed read is said once and the sheet is shut", (await page.textContent("#notices")).includes("The return could not be read"), await page.textContent("#notices"));
  await context.close();
}

{ // Draft reminder: from the Reminders page, with Next across the drafts; held has no buttons
  const { context, page } = await open("?mode=real");
  await page.evaluate(() => shellGo({ level: "reminders" }));
  await page.waitForSelector("#page .row");
  await page.focus("#page .rows");
  await page.keyboard.press("Enter");
  await page.waitForFunction(() => !document.getElementById("sheet").hidden && document.getElementById("reminder-stages").children.length === 4, null, { timeout: 5000 });
  check("the reminder sheet's title is the API's word", (await sheetTitle(page)) === "Reminder", await sheetTitle(page));
  const buttons = await page.evaluate(() => [...document.querySelectorAll("#reminder-actions .btn")].map((b) => b.textContent));
  check("Approve, then Copy: nothing sends", buttons.join("|") === "Approve|Copy for Outlook", buttons);
  const stages = await page.evaluate(() => [...document.querySelectorAll(".rem-stage")].map((b) => b.textContent.replace(/^\d\s*/, "")));
  check("the four stages read by their short names", stages.join("|") === "Heads Up|Checking In|Deadline Near|Final Notice", stages);
  const caption = await page.textContent("#reminder-status");
  check("the caption says when it was drafted and at which stage", /^Drafted Mar 3, Stage \d$/.test(caption), caption);
  check("no Open the draft file, no hint", await page.evaluate(() => !document.getElementById("btn-open-draft") && !document.getElementById("reminder-hint")), null);
  const reads = await page.evaluate(() => window.HARNESS.calls.filter((c) => c === "state").length);
  check("Next is offered on the Reminders page", await page.evaluate(() => !document.getElementById("sheet-next").hidden), null);
  await page.click("#sheet-next");
  await page.waitForFunction((n) => window.HARNESS.calls.filter((c) => c === "state").length > n, reads, { timeout: 5000 });
  await settle(page);
  check("Next reads the next return's draft and stays a reminder", (await sheetTitle(page)) === "Reminder", await sheetTitle(page));
  await context.close();
}

{ // Draft reminder from a return page has no Next, and a held reminder has no Copy or Approve
  const { context, page } = await open("?mode=real");
  await goReturn(page);
  await page.evaluate((r) => openReminder(r), smithReturn);
  await page.waitForFunction(() => !document.getElementById("sheet").hidden && document.getElementById("reminder-held-rows").children.length, null, { timeout: 5000 });
  check("a return page's reminder has no Next", await page.evaluate(() => document.getElementById("sheet-next").hidden), null);
  const held = await page.textContent("#reminder-held");
  check("held says so in the API's words and offers no Copy or Approve", held.length > 0 && await page.evaluate(() => document.getElementById("reminder-actions").classList.contains("hidden")), held);
  const heldRows = await page.evaluate(() => [...document.querySelectorAll("#reminder-held-rows li")].map((li) => li.textContent));
  check("a held row draws its document alone: no request code, no hold sentence", heldRows.length > 0 && heldRows.every((t) => /^Held request \d$/.test(t)), heldRows);
  await context.close();
}

{ // the three link kinds (rulings 8-13)
  const { context, page } = await open("?mode=real");
  await goReturn(page);
  const link = await page.evaluate(() => { const l = document.querySelector("#page .row-link"); return [l.textContent, l.dataset.link, l.dataset.tip]; });
  check("a file name is a link with the vocabulary's tooltip", link.join("|") === "scan0012.pdf|file|Show in File Explorer", link);
  await page.click("#page .row-link");
  const opened = await page.evaluate(() => window.HARNESS.opened);
  check("it asks the shell to reveal the reported path", opened.length === 1 && opened[0][1] === "reveal" && opened[0][0].endsWith("scan0012.pdf"), opened);
  check("no path is drawn anywhere on the page or the sheet", await page.evaluate(() => !/\/clients\/|Prepared|\\\\/.test(document.body.innerText)), await page.evaluate(() => document.body.innerText.slice(0, 200)));
  const noneFor = await page.evaluate(() => [...document.querySelectorAll("#page .row-name")].filter((n) => n.textContent === "scan-of-a-postcard.heic").map((n) => n.querySelector(".row-link") === null));
  check("a file with no copy is plain text", noneFor.length === 1 && noneFor[0], noneFor);
  const filed = await page.evaluate(() => [...document.querySelectorAll("#page .row-detail .row-link")].map((n) => n.textContent));
  check("a filed file's own name is a link on its Received row, and \"3 files\" is not", filed.includes("w2-jane.pdf") && !filed.includes("3 files"), filed);
  await page.evaluate(() => shellGo({ level: "household", household: "/clients/J Park & Associates/Smith Family" }));
  await page.waitForFunction(() => document.querySelector("#page .row-link[data-link=return]"), null, { timeout: 5000 });
  const returns = await page.evaluate(() => [...document.querySelectorAll("#page .row-link[data-link=return]")].map((n) => [n.textContent, n.dataset.tip]));
  check("a return name reads with its year and says where it goes", returns.length === 2 && returns[0][0].endsWith("(2025)") && returns[1][0].endsWith("(2024)") && returns.every((r) => r[1] === "Navigate to Return"), returns);
  await page.click("#page .row-link[data-link=return]");
  await page.waitForFunction(() => shellRoute.level === "return", null, { timeout: 5000 });
  check("clicking a return name goes to its page", await page.evaluate(() => shellRoute.level === "return" && shellRoute.year === 2025), null);
  await page.evaluate(() => shellGo({ level: "overview" }));
  await page.waitForSelector("#page .row-link[data-link=household]");
  const before = await page.evaluate(() => window.HARNESS.opened.length);
  const hh = await page.evaluate(() => { const l = document.querySelector("#page .row-link[data-link=household]"); return [l.textContent, l.dataset.tip]; });
  await page.click("#page .row-link[data-link=household]");
  await page.waitForFunction(() => shellRoute.level === "household", null, { timeout: 5000 });
  check("a household name goes to the client's page, with its tooltip, and never opens File Explorer", hh[1] === "Navigate to Client" && (await page.evaluate(() => window.HARNESS.opened.length)) === before, hh);
  await context.close();
}

{ // Needs Review: a file name is a link from the firm reply's open key and paths; a return heading has its year
  const { context, page } = await open("?mode=real");
  await page.evaluate(() => shellGo({ level: "needs-review" }));
  await page.waitForSelector("#page .row-link");
  const head = await page.evaluate(() => [document.querySelector(".group-title .row-link").textContent, document.querySelector(".group-count .row-link").dataset.tip]);
  check("a group heading is a return link with its year; its caption a household link", head[0].endsWith("(2025)") && head[1] === "Navigate to Client", head);
  await page.click("#page .rows .row-link");
  const opened = await page.evaluate(() => window.HARNESS.opened);
  check("a firm-page file name reveals the path of the key the firm's reply gave", opened.length === 1 && opened[0][1] === "reveal", opened);
  await context.close();
}

{ // a copy that has changed: the shell says so and the link says it as a notice
  const { context, page } = await open("?mode=real&scenario=changed-copy");
  await goReturn(page);
  await page.click("#page .row-link");
  await page.waitForFunction(() => document.querySelector("#notices .notice"), null, { timeout: 5000 });
  check("a link that cannot act says Not Opened", (await page.textContent("#notices")).includes("Not Opened; It Has Changed"), await page.textContent("#notices"));
  await context.close();
}

{ // right-click and the menu key: the native menu of a row's template, with the ids that apply
  const { context, page } = await open("?mode=real");
  await goReturn(page);
  await page.click("#page .rows .row:nth-child(1)", { button: "right" });
  let sent = await page.evaluate(() => window.HARNESS.menuLog.at(-1));
  check("right-click on a parked file asks for the file menu, without Another Return where there is no return to hand it to", sent.popup === "file" && /^row-/.test(sent.token) && sent.enable.join() === "check,not_requested,show_in_explorer", sent);
  await page.click("#page .rows .row:nth-child(3)", { button: "right" });
  sent = await page.evaluate(() => window.HARNESS.menuLog.at(-1));
  check("right-click on a moved-by-hand file asks for the moved menu, with Keep only where it applies", sent.popup === "moved" && sent.enable.includes("put_back") && sent.enable.includes("keep_here"), sent);
  await page.click("#page .rows .row:nth-child(4)", { button: "right" });
  sent = await page.evaluate(() => window.HARNESS.menuLog.at(-1));
  check("right-click on a request asks for the request menu", sent.popup === "request" && sent.enable.includes("edit_request"), sent);
  await page.focus("#page .rows");
  await page.keyboard.press("Home");
  await page.keyboard.press("Shift+F10");
  sent = await page.evaluate(() => window.HARNESS.menuLog.at(-1));
  check("Shift+F10 opens the same menu under the active row", sent.popup === "file" && sent.x > 0 && sent.y > 0, sent);
  await page.keyboard.press("ContextMenu");
  check("and so does the menu key", (await page.evaluate(() => window.HARNESS.menuLog.at(-1))).popup === "file", null);
  const token = sent.token;
  await page.evaluate((tk) => shellMenu({ id: "show_in_explorer", token: tk }), token);
  check("Show in File Explorer from the menu reveals the same copy", (await page.evaluate(() => window.HARNESS.opened.at(-1)))[1] === "reveal", null);
  await page.evaluate((tk) => shellMenu({ id: "not_requested", token: tk }), token);
  await page.waitForFunction(() => window.HARNESS.writes.some((w) => w.command === "dismiss"), null, { timeout: 5000 });
  check("Not Requested from the menu opens the sheet on the file and writes through it", true, null);
  await page.evaluate(() => closeSheet());
  await page.locator("#page .row", { hasText: "W-2 - Brightline Health" }).click({ button: "right", position: { x: 400, y: 10 } });
  sent = await page.evaluate(() => window.HARNESS.menuLog.at(-1));
  check("right-click on a received request asks for the received menu: Unfile only where one original answers it", sent.popup === "received" && sent.enable.includes("unfile") && !sent.enable.includes("mark_missing"), sent);
  await page.locator("#page .row", { hasText: "Childcare receipts" }).click({ button: "right", position: { x: 400, y: 10 } });
  sent = await page.evaluate(() => window.HARNESS.menuLog.at(-1));
  check("a request with several files gets no Unfile itself: each file has its own row", sent.popup === "received" && !sent.enable.includes("unfile"), sent);
  const kids = await page.evaluate(() => [...document.querySelectorAll("#page .row-child")].map((n) => [n.querySelector(".row-name").textContent, Boolean(n.querySelector(".row-name .row-link"))]));
  check("ruling 17: each of the three files gets its own row, each name a file link", kids.length === 3 && kids.every((k) => k[1]) && kids[0][0] === "childcare-receipts-1.pdf", kids);
  const before = await page.evaluate(() => window.HARNESS.opened.length);
  await page.locator("#page .row-child .row-link").nth(1).click();
  const revealed = await page.evaluate(() => window.HARNESS.opened.at(-1));
  check("ruling 17: a file row's link reveals its own copy in File Explorer", (await page.evaluate(() => window.HARNESS.opened.length)) === before + 1 && revealed[1] === "reveal" && revealed[0].endsWith("childcare-receipts-2.pdf"), revealed);
  const counted = await page.evaluate(() => {
    const title = [...document.querySelectorAll("#page .group-title")].find((n) => n.textContent === "Received");
    const list = document.querySelector(`[aria-labelledby="${title.id}"]`);
    return [title.parentElement.querySelector(".group-count").textContent, list.querySelectorAll(".row:not(.row-child)").length, list.querySelectorAll(".row-child").length];
  });
  check("ruling 17: the Received count is requests, not files", counted[0] === String(counted[1]) && counted[2] === 3, counted);
  await page.locator("#page .row-child").nth(2).click({ button: "right" });
  sent = await page.evaluate(() => window.HARNESS.menuLog.at(-1));
  check("ruling 17: a file row's right-click offers Show in File Explorer and Unfile", sent.popup === "received" && sent.enable.join() === "unfile,show_in_explorer", sent);
  await page.evaluate((tk) => shellMenu({ id: "unfile", token: tk }), sent.token);
  await page.waitForSelector("#unfile-modal:not(.hidden)");
  const box = await page.evaluate(() => ({ focus: document.activeElement.id, title: document.getElementById("uf-title").textContent, label: document.getElementById("uf-note-label").textContent,
    confirm: document.getElementById("uf-confirm").textContent, cancel: document.getElementById("uf-cancel").textContent, name: document.getElementById("uf-name").textContent, unfiles: window.HARNESS.writes.filter((w) => w.command === "unfile").length }));
  check("ruling 16: Unfile opens a small confirm box on the reason field with the vocabulary's words, and writes nothing yet",
    box.focus === "uf-note" && box.title === "Unfile" && box.label === "Reason (Optional)" && box.confirm === "Unfile" && box.cancel === "Cancel" && box.name === "childcare-receipts-3.pdf" && box.unfiles === 0, box);
  await page.click("#uf-cancel");
  check("ruling 16: Cancel closes the box and writes nothing", (await page.evaluate(() => document.getElementById("unfile-modal").classList.contains("hidden") && !window.HARNESS.writes.some((w) => w.command === "unfile"))), null);
  await page.evaluate((tk) => shellMenu({ id: "unfile", token: tk }), sent.token);
  await page.waitForSelector("#unfile-modal:not(.hidden)");
  await page.fill("#uf-note", "Wrong client");
  await page.click("#uf-confirm");
  await page.waitForFunction(() => document.getElementById("unfile-modal").classList.contains("hidden"), null, { timeout: 5000 });
  const wrote = await page.evaluate(() => window.HARNESS.writes.filter((w) => w.command === "unfile"));
  check("ruling 16: the confirm sends the reason as the write's note, once", wrote.length === 1 && wrote[0].payload.note === "Wrong client", wrote);
  await page.locator("#page .row-child").nth(1).click({ button: "right" });
  await page.evaluate((tk) => shellMenu({ id: "unfile", token: tk }), (await page.evaluate(() => window.HARNESS.menuLog.at(-1))).token);
  await page.waitForSelector("#unfile-modal:not(.hidden)");
  await page.click("#uf-confirm");
  await page.waitForFunction(() => window.HARNESS.writes.filter((w) => w.command === "unfile").length === 2, null, { timeout: 5000 });
  check("ruling 16: an empty reason is sent as an empty note", (await page.evaluate(() => window.HARNESS.writes.at(-1))).payload.note === "", null);
  await page.evaluate(() => shellGo({ level: "overview" }));
  await page.waitForSelector("#page .row");
  await page.click("#page .row:nth-child(1)", { button: "right" });
  sent = await page.evaluate(() => window.HARNESS.menuLog.at(-1));
  check("right-click on a return row asks for the return menu, its ids read for that return", sent.popup === "return" && sent.enable.includes("edit_list") && sent.enable.includes("draft_reminder"), sent);
  await context.close();
}

{ // the menu channel that throws must not stop navigation
  const { context, page } = await open("?mode=real&scenario=menu-throws");
  await page.click('.side-section[data-section="clients"]');
  check("a route change goes on when the menu channel throws", (await current(page)) === "Clients", await current(page));
  const text = await page.textContent("#notices");
  check("and the failure is one notice", text.length > 0 && !text.includes("menu channel closed"), text);
  await context.close();
}

{ // the four dialogs
  const { context, page } = await open("?mode=real&scenario=notices");
  await page.evaluate(() => shellMenu({ id: "safeguards" }));
  const rules = await page.evaluate(() => [...document.querySelectorAll("#safeguards-list li")].map((n) => n.textContent));
  check("Help > Safeguards lists four short lines", rules.length === 4 && rules.every((r) => r.split(" ").length <= 5), rules);
  check("focus is inside and Esc closes it", await page.evaluate(() => document.activeElement.closest("#safeguards-modal") !== null), null);
  await page.keyboard.press("Escape");
  check("Esc shuts the dialog", await page.evaluate(() => document.getElementById("safeguards-modal").classList.contains("hidden")), null);
  await page.evaluate(() => shellMenu({ id: "about" }));
  check("Help > About names the product and the edition", (await page.textContent("#about-modal")).includes("Pilot 0.2"), await page.textContent("#about-modal"));
  await page.click("#about-close");
  await page.click("#notices .notice-act[data-act=action]");
  const names = await page.evaluate(() => [...document.querySelectorAll("#misfits-list .misfit-name")].map((n) => n.textContent));
  check("Show lists the folders skipped by their own names, never a path", names.join("|") === "Old Files|Scans|Misc", names);
  const whys = await page.evaluate(() => [...document.querySelectorAll("#misfits-list li")].map((n) => n.textContent));
  check("each skipped folder has the vocabulary's reason beside its name; a code without a word draws the name alone", whys.join("|") === "Old FilesUnknown Folder|ScansNo Return|Misc" && (await page.locator("#misfits-list .misfit-why").count()) === 2, whys);
  await page.keyboard.press("Escape");
  await context.close();
}

{ // Roll forward: the Client menu opens it on the household, with the ticks, Cancel and the roll
  const { context, page } = await open("?mode=real");
  await page.evaluate(() => shellGo({ level: "household", household: "/clients/J Park & Associates/Chen Family" }));
  await page.waitForFunction(() => window.lastState && window.lastState.household && window.lastState.household.roll_year || (typeof lastState !== "undefined" && lastState && lastState.household && lastState.household.roll_year), null, { timeout: 5000 });
  await page.evaluate(() => shellMenu({ id: "roll_forward" }));
  check("Roll Forward opens its dialog titled with the year", (await page.textContent("#roll-title")) === "Roll Forward to 2026", await page.textContent("#roll-title"));
  const ticks = await page.evaluate(() => [...document.querySelectorAll(".roll-tick")].map((b) => b.checked));
  check("every rollable return is ticked", ticks.length === 1 && ticks[0], ticks);
  check("the intro and the template note are cut", !(await page.textContent("#roll-body")).toLowerCase().includes("carried over"), null);
  await page.click("#roll-cancel");
  check("Cancel shuts it", await page.evaluate(() => document.getElementById("roll-modal").classList.contains("hidden")), null);
  await context.close();
}

await browser.close();
server.close();
if (failures.length) {
  console.log("FAILED:\n" + failures.join("\n"));
  process.exit(1);
}
console.log("all interactions pass");
