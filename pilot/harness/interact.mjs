// Drives the shell in the harness the way a person would and asserts what
// happens (SPEC-shell 14.4): routes, the search, the Sort Now button, F6, Esc, the
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
// The edition the badge shows, read from between pilot-content.js's markers
// (plain JSON there, for the tests and the installer build), so the About
// check follows the version rather than typing it.
const pilotContent = fs.readFileSync(path.resolve(here, "..", "..", "app", "renderer", "pilot-content.js"), "utf-8");
const edition = JSON.parse(pilotContent.split("// PILOT-CONTENT-BEGIN")[1].split("// PILOT-CONTENT-END")[0]).edition.version;

const browser = await chromium.launch({ args: ["--no-sandbox"] });
const failures = [];
const check = (name, ok, got) => { if (!ok) failures.push(`${name}: ${JSON.stringify(got)}`); };

// The shell's own sections run on the double of app.js (the default here); the ones that need the real
// app.js (the side sheet, the writes, the notices) say "?mode=real".
async function open(query = "", { firm = true, forcedColors } = {}) {
  if (!/mode=/.test(query)) query = `${query}${query ? "&" : "?"}mode=double`;
  const context = await browser.newContext({ viewport: { width: 1100, height: 700 }, ...(forcedColors ? { forcedColors } : {}) });
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
  check("Ctrl+4 goes to Households", (await current(page)) === "Households", await current(page));
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

{ // the Sort Now button (P274), F6
  const { context, page } = await open();
  check("absent on a firm page", await page.evaluate(() => document.getElementById("sort").classList.contains("hidden")), null);
  await page.evaluate(() => shellGo({ level: "household", household: "/clients/J Park & Associates/Smith Family" }));
  check("ready on a household, and says Sort Now", !(await page.evaluate(() => document.getElementById("sort").disabled)) && (await page.evaluate(() => document.getElementById("sort").querySelector(".sort-word:not([aria-hidden])")?.textContent === "Sort Now")), null);
  await page.keyboard.press("F9");
  await page.waitForTimeout(300);
  check("F9 starts a sort", (await page.evaluate(() => document.getElementById("sort").dataset.sortState)) === "stop", null);
  check("the foot says how far", (await page.textContent("#last-sort")).startsWith("Sorting 1 of 12"), await page.textContent("#last-sort"));
  await page.keyboard.press("Control+1");
  await page.waitForTimeout(200);
  check("Stop Sorting shows on the Overview while the app's sort runs", await page.evaluate(() => { const b = document.getElementById("sort"); return !b.classList.contains("hidden") && !b.disabled && b.dataset.sortState === "stop" && b.querySelector('.sort-word:not([aria-hidden])').textContent === "Stop Sorting"; }), null);
  await page.click("#sort");
  await page.waitForTimeout(200);
  check("a click stops it", (await page.evaluate(() => document.getElementById("sort").dataset.sortState)) === "stopping", null);
  await page.waitForTimeout(1800);
  check("and it goes away on the Overview once the sort ends", await page.evaluate(() => document.getElementById("sort").classList.contains("hidden")), null);
  await page.evaluate(() => shellGo({ level: "household", household: "/clients/J Park & Associates/Smith Family" }));
  check("and it gives the button back on the household", (await page.evaluate(() => document.getElementById("sort").dataset.sortState)) === "now", null);
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
  check("the tour says one short line per step", steps.every((s) => s.split(" ").length <= 5) && steps[0] === "Sorts What Your Taxpayers Send", steps);
  check("the tour ends", await page.evaluate(() => !document.getElementById("pilot-tour")), null);
  await page.evaluate(() => shellGo({ level: "household", household: "/clients/J Park & Associates/Smith Family" }));
  await page.waitForFunction(() => !document.getElementById("sort").classList.contains("hidden"));
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
  // The step's words come first; after them the description names the household (P195), the links and
  // (P268) the year when the list holds only one: "Open, Abbott Household (Avery 0), 2025".
  check("a row is an option, its step hidden and named", named[0] === "option" && named[1] === "true" && /^Open(, .+)?$/.test(named[2] || ""), named);
  // P270: the chevron rests in the caption colour with its words not drawn; under the pointer the words
  // are drawn and the step is in the link colour. A row that is not the keyboard's active one, so the
  // list's focus does not show it.
  await page.evaluate(() => { const rows = [...document.querySelectorAll("#page .row")].filter((row) => row.querySelector(".row-step") && !row.classList.contains("is-active")); rows[0].setAttribute("data-probe", "step"); });
  const stepState = () => page.evaluate(() => {
    const row = document.querySelector("[data-probe]");
    const token = (name) => { const probe = document.createElement("span"); probe.style.color = `var(${name})`; document.body.append(probe); const color = getComputedStyle(probe).color; probe.remove(); return color; };
    return { words: getComputedStyle(row.querySelector(".row-step-words")).display, color: getComputedStyle(row.querySelector(".row-step")).color, caption: token("--text-caption"), link: token("--link") };
  });
  await page.mouse.move(1, 1);
  const rest = await stepState();
  check("at rest the step is a chevron in the caption colour, its words not drawn", rest.words === "none" && rest.color === rest.caption && rest.color !== rest.link, rest);
  await page.hover("[data-probe]");
  const under = await stepState();
  check("hover shows the step's words, in the link colour", under.words !== "none" && under.color === under.link && under.color !== under.caption, under);
  await page.hover("#page .row");
  await page.keyboard.press("Enter");
  await page.waitForFunction(() => document.querySelector("#crumb-list li:last-child")?.textContent.startsWith("1"));
  check("Enter runs the step and opens the return", (await crumbs(page)).length === 4, await crumbs(page));
  await page.evaluate(() => shellGo({ level: "return", household: "/clients/J Park & Associates/Smith Family", year: 2025, ret: "/clients/J Park & Associates/Smith Family/2025/1040 - John & Jane Smith" }));
  await page.waitForFunction(() => document.querySelector("#page details") && !document.querySelector("#page[aria-busy=true]"), null, { timeout: 5000 });
  const titles = await page.evaluate(() => [...document.querySelectorAll("#page .group-title")].map((n) => n.textContent));
  check("the return draws its groups in order", titles.join("|") === "Needs You|Waiting on Taxpayer|Received|Set Aside", titles);
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

{ // rulings 20 and 28: a failed sort is a notice with NO Retry at the top of every page; the side line stays; it clears when the record says a sort worked
  for (const mode of ["double", "real"]) {
    const { context, page } = await open(`?mode=${mode}&scenario=failed`);
    const failedNotice = () => page.evaluate(() => [...document.querySelectorAll("#notices .notice-failed")].filter((n) => n.querySelector(".notice-text").textContent === "Sort Failed").map((n) => [...n.querySelectorAll("button")].map((b) => b.textContent).filter((t) => t.trim()).join("|")));
    check(`ruling 28 (${mode}): Overview shows the failed sort with no Retry`, (await failedNotice()).length === 1 && !(await failedNotice()).join().includes("Retry"), await failedNotice());
    check(`ruling 28 (${mode}): nothing on it can send a sort or draw a flag`, await page.evaluate(() => { const n = document.querySelector("#notices .notice-failed"); return !/--engagement|Pick an engagement/i.test(n.textContent) && !n.querySelector('[data-act]:not([data-act="dismiss"])'); }), "notice");
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
  check("a return reads as its taxpayer, once under each year, and says where it goes (P195)", returns.length === 2 && returns.every((r) => !/\(\d{4}\)$/.test(r[0]) && r[1] === "Navigate to Return"), returns);
  await page.click("#page .row-link[data-link=return]");
  await page.waitForFunction(() => shellRoute.level === "return", null, { timeout: 5000 });
  check("clicking a return name goes to its page", await page.evaluate(() => shellRoute.level === "return" && shellRoute.year === 2025), null);
  await page.evaluate(() => shellGo({ level: "clients" }));
  await page.waitForSelector("#page .row-link[data-link=household]");
  const before = await page.evaluate(() => window.HARNESS.opened.length);
  const hh = await page.evaluate(() => { const l = document.querySelector("#page .row-link[data-link=household]"); return [l.textContent, l.dataset.tip]; });
  await page.click("#page .row-link[data-link=household]");
  await page.waitForFunction(() => shellRoute.level === "household", null, { timeout: 5000 });
  check("a household name goes to the client's page, with its tooltip, and never opens File Explorer", hh[1] === "Navigate to Household" && (await page.evaluate(() => window.HARNESS.opened.length)) === before, hh);
  await context.close();
}

{ // Needs Review: a file name is a link from the firm reply's open key and paths; a return heading has its year
  const { context, page } = await open("?mode=real");
  await page.evaluate(() => shellGo({ level: "needs-review" }));
  await page.waitForSelector("#page .row-link");
  const head = await page.evaluate(() => [document.querySelector(".group-title .head-year").textContent, document.querySelector(".group-count .row-link").dataset.tip]);
  check("a group heading says its year once, beside the taxpayer's return link; its caption a household link (P195)", head[0] === "2025" && head[1] === "Navigate to Household", head);
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
  check("a route change goes on when the menu channel throws", (await current(page)) === "Households", await current(page));
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
  check("Help > About names the product and the edition", (await page.textContent("#about-modal")).includes(`Pilot ${edition}`), await page.textContent("#about-modal"));
  await page.click("#about-close");
  await page.click("#notices .notice-act[data-act=action]");
  const names = await page.evaluate(() => [...document.querySelectorAll("#misfits-list .misfit-name")].map((n) => n.textContent));
  check("Show lists the folders skipped by their own names, never a path", names.join("|") === "Old Files|Scans|Misc|Loose", names);
  const whys = await page.evaluate(() => [...document.querySelectorAll("#misfits-list li")].map((n) => n.textContent));
  check("each skipped folder has the vocabulary's reason beside its name; a code without a word draws the name alone", whys.join("|") === "Old FilesUnknown Folder|ScansNo Return|MiscName Refused|Loose" && (await page.locator("#misfits-list .misfit-why").count()) === 3, whys);
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

{ // the tooltip: keyboard focus, hover, Esc, the window's edges (SPEC-shell 8.5, ruling 2)
  const { context, page } = await open();
  const tipShown = () => page.evaluate(() => !document.getElementById("tip").hidden);
  const tipBox = () => page.evaluate(() => { const r = document.getElementById("tip").getBoundingClientRect(); return { left: r.left, top: r.top, right: r.right, bottom: r.bottom, w: innerWidth, h: innerHeight }; });
  await page.evaluate(() => shellGo({ level: "household", household: "/clients/J Park & Associates/Smith Family" }));
  await page.waitForFunction(() => !document.getElementById("sort").disabled);
  await page.keyboard.press("Tab");
  await page.focus("#sort");
  await page.waitForTimeout(150);
  check("a focused button shows its tip at once", await tipShown(), null);
  check("the tip is described-by on its button", await page.evaluate(() => document.getElementById("sort").getAttribute("aria-describedby") === "tip" && document.getElementById("tip").getAttribute("role") === "tooltip"), null);
  await page.keyboard.press("Escape");
  check("Esc hides a focus tip", !(await tipShown()), null);
  await page.keyboard.press("Control+f");
  await page.waitForTimeout(150);
  check("the focused search box shows no tip", !(await tipShown()), null);
  await page.mouse.move(0, 0);
  await page.hover("#sort");
  await page.waitForTimeout(200);
  check("hover shows no tip at 200 ms", !(await tipShown()), null);
  await page.waitForTimeout(250);
  check("hover shows the tip by 450 ms", await tipShown(), null);
  await page.mouse.move(0, 0);
  await page.waitForTimeout(100);
  const icon = await page.evaluate(() => { const r = document.querySelector("#find-wrap .icon").getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; });
  await page.mouse.move(icon.x, icon.y);
  await page.waitForTimeout(700);
  check("hover on the search icon shows the tip", (await tipShown()) && (await page.textContent("#tip")) === "Find a Household", await page.textContent("#tip"));
  await page.mouse.move(0, 0);
  await page.waitForTimeout(100);
  check("moving away hides it", !(await tipShown()), null);
  // A control in each corner of the window, with a tip wider than the button.
  for (const [where, css] of [["right", "right:0;top:100px"], ["bottom", "left:500px;bottom:0"], ["bottom-right", "right:0;bottom:0"]]) {
    await page.evaluate(([place, rule]) => {
      const b = document.createElement("button");
      b.id = `edge-${place}`;
      b.style.setProperty("position", "fixed");
      for (const part of rule.split(";")) { const [prop, value] = part.split(":"); b.style.setProperty(prop, value); }
      b.textContent = "x";
      document.body.append(b);
      setTip(b, "A tip wider than its button");
    }, [where, css]);
    await page.hover(`#edge-${where}`);
    await page.waitForTimeout(700);
    const box = await tipBox();
    check(`the tip stays inside the window at the ${where} edge`, box.left >= 7.5 && box.top >= 7.5 && box.right <= box.w - 7.5 && box.bottom <= box.h - 7.5, box);
    await page.mouse.move(0, 0);
  }
  // A focused control inside a scrolling box: the tip follows it, then goes when it is scrolled away.
  await page.evaluate(() => {
    const box = document.createElement("div");
    box.id = "scroll-box";
    for (const [prop, value] of [["position", "fixed"], ["left", "300px"], ["top", "200px"], ["width", "200px"], ["height", "100px"], ["overflow", "auto"]]) box.style.setProperty(prop, value);
    const b = document.createElement("button");
    b.id = "scroll-anchor";
    b.style.setProperty("margin-top", "40px");
    b.textContent = "x";
    const pad = document.createElement("div");
    pad.style.setProperty("height", "600px");
    box.append(b, pad);
    document.body.append(box);
    setTip(b, "Follows its button");
  });
  await page.focus("#scroll-anchor");
  await page.keyboard.press("Shift+Tab");
  await page.keyboard.press("Tab");
  await page.waitForTimeout(150);
  check("a tip shows on a control inside a scrolling box", await tipShown(), null);
  await page.evaluate(() => { document.getElementById("scroll-box").scrollTop = 10; });
  await page.waitForTimeout(150);
  check("the tip stays while its element is in view", await tipShown(), null);
  await page.evaluate(() => { document.getElementById("scroll-box").scrollTop = 300; });
  await page.waitForTimeout(150);
  check("the tip is hidden once its element is scrolled out of view", !(await tipShown()), null);
  await context.close();
}

{ // the tooltip in a contrast theme
  const { context, page } = await open("", { forcedColors: "active" });
  check("the contrast theme is on", await page.evaluate(() => matchMedia("(forced-colors: active)").matches), null);
  await page.evaluate(() => shellGo({ level: "household", household: "/clients/J Park & Associates/Smith Family" }));
  await page.waitForFunction(() => !document.getElementById("sort").classList.contains("hidden"));
  await page.hover("#sort");
  await page.waitForTimeout(700);
  const box = await page.evaluate(() => { const t = document.getElementById("tip"); const r = t.getBoundingClientRect(); return { shown: !t.hidden, w: r.width, h: r.height, right: r.right, bottom: r.bottom, iw: innerWidth, ih: innerHeight, color: getComputedStyle(t).color }; });
  check("the tip shows, sized and inside the window", box.shown && box.w > 0 && box.h > 0 && box.right <= box.iw && box.bottom <= box.ih, box);
  await context.close();
}

{ // rulings 21 and 27, at the 1100px minimum: a return link shows its year and the paused words are whole, on every page
  const { context, page } = await open("?mode=real&scenario=paused");
  const clipped = () => page.evaluate(() => {
    const bad = [];
    for (const row of document.querySelectorAll("#page .row-wrap")) {
      for (const cell of row.querySelectorAll(".row-year, .row-name, .row-status")) {
        if (cell.scrollWidth > cell.clientWidth + 1 || cell.scrollHeight > cell.clientHeight + 1) bad.push(cell.textContent);
      }
      const total = Math.round(row.getBoundingClientRect().height), height = total > 40 ? total - Math.round(parseFloat(getComputedStyle(row).borderBottomWidth)) : total;   // the 1px rule under a row is not part of the grid
      if (height % 4) bad.push(`height ${height}: ${row.textContent}`);
    }
    // P195: a return row on Overview and Reminders says its year in its own column (P268: with one year in the list
    // the column is left out and the row's description ends with the year); a Needs Review heading beside the taxpayer.
    const years = [...[...document.querySelectorAll("#page .row-return")].filter((r) => {
        if (!r.querySelector('.row-link[data-link="return"]')) return false;
        const cell = r.querySelector(".row-year");
        return cell ? !/^\d{4}$/.test(cell.textContent) : !/\d{4}$/.test(r.getAttribute("aria-description") || "");
      }),
      ...[...document.querySelectorAll("#page .group-title")].filter((t) => t.querySelector('.row-link[data-link="return"]') && !t.querySelector(".head-year"))].map((n) => n.textContent);
    return { bad, years, links: document.querySelectorAll('#page .row-link[data-link="return"]').length };
  });
  for (const [where, level, all] of [["Overview", "overview", false], ["Needs Review", "needs-review", false], ["Reminders", "reminders", false],
    ["Households", "clients", false], ["Households (All)", "clients", true]]) {
    await page.evaluate((l) => shellGo({ level: l }), level);
    await page.waitForTimeout(250);
    if (all) { await page.click(".switch-option:nth-child(2)"); await page.waitForTimeout(250); }
    const found = await clipped();
    check(`ruling 27 at 1100px: nothing wrapped is cut on ${where}`, found.bad.length === 0, found.bad.slice(0, 3));
    check(`P195 at 1100px: every return on ${where} says its year once, in its own place`, found.years.length === 0, found.years);
  }
  await page.evaluate(() => shellGo({ level: "household", household: "/clients/J Park & Associates/Smith Family" }));
  await page.waitForTimeout(250);
  const household = await clipped();
  check("ruling 27 at 1100px: the household page shows both years whole", household.bad.length === 0 && household.years.length === 0 && household.links >= 2, household);
  await page.evaluate(() => shellGo({ level: "clients" }));
  await page.waitForTimeout(250);
  await page.click(".switch-option:nth-child(2)");
  await page.waitForTimeout(250);
  const paused = await page.evaluate(() => { const mark = document.querySelector("#page .row-mark"); return mark ? { text: mark.textContent, whole: mark.scrollWidth <= mark.parentElement.clientWidth + 1 } : null; });
  check("ruling 21 at 1100px: the paused words are whole on Clients", paused && paused.text === "Two Years Open; Sorting Paused" && paused.whole, paused);
  await context.close();
}

{ // final review B finding 6, as P267 changed it: a name link is underlined on hover in light and dark, always in the contrast theme; a status such as "n Waiting" never is
  for (const [name, opts, scheme] of [["light", {}, "light"], ["dark", {}, "dark"], ["contrast", { forcedColors: "active" }, "light"]]) {
    const { context, page } = await open("", opts);
    await page.emulateMedia({ colorScheme: scheme });
    const seen = await page.evaluate(() => {
      const line = (node) => getComputedStyle(node).textDecorationLine;
      const links = [...document.querySelectorAll("#page .row-link")];
      const waiting = [...document.querySelectorAll("#page .row-status.is-waiting")];
      return { links: links.length, plainLinks: links.filter((l) => !line(l).includes("underline")).length, waiting: waiting.length,
               underlinedWaiting: waiting.filter((w) => line(w).includes("underline") || getComputedStyle(w).cursor === "pointer").length };
    });
    if (opts.forcedColors) check(`links are underlined at rest in the ${name} theme`, seen.links > 3 && seen.plainLinks === 0, seen);
    else {
      check(`links are not underlined at rest in the ${name} theme`, seen.links > 3 && seen.plainLinks === seen.links, seen);
      await page.hover("#page .rows .row:nth-child(2) .row-link");
      await page.waitForTimeout(100);
      check(`a name link is underlined under the pointer in the ${name} theme`, await page.evaluate(() => getComputedStyle(document.querySelector("#page .rows .row:nth-child(2) .row-link")).textDecorationLine.includes("underline")), null);
    }
    check(`a status such as n Waiting does not look like a link in the ${name} theme`, seen.waiting > 0 && seen.underlinedWaiting === 0, seen);
    await context.close();
  }
}

{ // P279 (SPEC-ui-menu-speed 2.7): a long list draws only the rows in view; the keys reach every row; focus stays on the list
  const smith = "/clients/J Park & Associates/Smith Family";
  const ret = { level: "return", household: smith, year: 2025, ret: `${smith}/2025/1040 - John & Jane Smith` };
  const { context, page } = await open("?mode=real&scenario=long-return&n=500");
  await page.evaluate((route) => shellGo(route), ret);
  await page.waitForFunction(() => document.querySelectorAll("#page .rows.is-virtual").length > 0, null, { timeout: 15000 });
  await page.waitForTimeout(400);
  // What the document holds, and what it may: the rows in view, a screen either side, the active row (one row of slack for a sub-heading's slot).
  const state = () => page.evaluate(() => {
    const list = document.querySelector("#page .rows.is-virtual");
    const model = list.pagesModel;
    const view = document.getElementById("page").clientHeight;
    const over = Math.max(15, Math.ceil(view / model.H));
    const active = list.getAttribute("aria-activedescendant");
    return { drawn: list.children.length, allowed: Math.ceil(view / model.H) + 2 * over + 2, rows: model.ids.length, registered: pagesTokens.size, active: model.active, H: model.H,
             activeDrawn: active ? Boolean(document.getElementById(active)) : null, focusOnList: document.activeElement === list, step: Math.max(1, Math.floor(view / model.H) - 1),
             height: list.style.height, items: model.items.length, top: document.getElementById("page").scrollTop };
  });
  // After every step: the document holds at most the allowed rows and the active row is drawn (SPEC 2.7).
  const bounded = (one) => one.drawn <= one.allowed + 1 && (one.active < 0 || one.activeDrawn === true);
  const holds = async (step) => {
    const one = await state();
    check(`after ${step}, the document holds at most window + over + 1 rows and the active row is drawn`, bounded(one), one);
    return one;
  };
  let at = await state();
  check("a long return draws a window of its rows, and every row stays registered", at.rows > 400 && at.drawn <= at.allowed && at.registered >= at.rows, at);
  await page.focus("#page .rows.is-virtual");
  at = await holds("focusing the list");
  check("focusing the list makes its first row active", at.active === 0 && at.activeDrawn === true && at.focusOnList, at);
  await page.keyboard.press("End");
  const end = await holds("End");
  check("End goes to the last row of the list, drawn now, and focus stays on the list", end.active === end.rows - 1 && end.activeDrawn && end.focusOnList && end.drawn <= end.allowed, end);
  for (let i = 0; i < 3; i += 1) {
    await page.keyboard.press("PageUp");
    await holds(`PageUp ${i + 1}`);
  }
  at = await state();
  check("PageUp three times moves three screens back through rows never drawn before", at.active === end.rows - 1 - 3 * at.step && at.activeDrawn && at.focusOnList && at.drawn <= at.allowed, [at, end.rows]);
  const say = await page.evaluate(() => { const row = document.getElementById(document.querySelector("#page .rows.is-virtual").getAttribute("aria-activedescendant")); return [row.getAttribute("aria-posinset"), row.getAttribute("aria-setsize"), row.getAttribute("aria-selected")]; });
  check("every drawn row says its place and the list's size", say[0] === String(at.active + 1) && say[1] === String(at.rows) && say[2] === "true", say);
  await page.evaluate(() => { document.getElementById("page").scrollTop = 0; });
  await page.waitForTimeout(250);
  at = await holds("a scroll to the top");
  check("a scroll to the top draws the top and keeps the active row in the document", at.drawn <= at.allowed + 1 && at.activeDrawn && at.focusOnList, at);
  const clicked = await page.evaluate(() => { const list = document.querySelector("#page .rows.is-virtual"); const row = list.querySelectorAll(".row")[3]; row.click(); return row.id; });
  at = await holds("a click on a row");
  check("a click makes the row clicked the active one", at.active === 3 && (await page.evaluate((id) => document.getElementById(id).classList.contains("is-active"), clicked)), at);
  await page.keyboard.press("Home");
  const home = await holds("Home");
  check("Home goes back to the first row", home.active === 0, home);
  // The registered rows reach the sheet's next arrow: every Check step of the page, in order.
  const steps = await page.evaluate(() => pagesFiles().length);
  check("the sheet's next arrow sees every file, drawn or not", steps >= 500, steps);
  await page.evaluate(() => shellToggleCompact());
  await page.waitForTimeout(300);
  at = await holds("Compact Rows");
  check("Compact Rows measures the rows again: the height is the density's, the list is as tall", at.H === 32 && at.height === `${at.items * 32}px` && at.drawn <= at.allowed + 1, at);
  const rowHeight = await page.evaluate(() => document.querySelector("#page .rows.is-virtual .row").getBoundingClientRect().height);
  check("a drawn row is the density's own height", rowHeight === 32, rowHeight);
  await context.close();
}

{ // P279: the editor's long table keeps the row being typed in on the page, and Tab walks every row's inputs in order
  const smith = "/clients/J Park & Associates/Smith Family";
  const ret = { level: "return", household: smith, year: 2025, ret: `${smith}/2025/1040 - John & Jane Smith` };
  const { context, page } = await open("?mode=real&scenario=long-editor&n=300");
  await page.evaluate((route) => shellGo(route), ret);
  await page.waitForFunction(() => document.querySelectorAll("#page .group-title").length > 0, null, { timeout: 15000 });
  await page.evaluate(() => openEditor());
  await page.waitForTimeout(500);
  const table = () => page.evaluate(() => {
    const box = document.querySelector("#ed-rows .editor-rows");
    const modal = document.querySelector("#editor .modal");
    const held = document.activeElement.closest && document.activeElement.closest("tr[data-index]");
    const indexes = [...new Set([...box.querySelectorAll("tr[data-index]")].map((tr) => Number(tr.dataset.index)))];
    const first = box.querySelector("tr[data-index]");
    const rowHeight = first ? first.offsetHeight : 1;
    const view = Math.ceil(modal.clientHeight / rowHeight);
    const over = Math.max(15, view);
    // The rows in view, a screen either side, and the `over` rows a focus at an edge widens by (+ 1 of slack).
    return { rows: box.editorWindow ? box.editorWindow.rows.length : null, drawn: box.querySelectorAll("tr[data-index]").length, spacers: box.querySelectorAll(".ed-spacer").length,
             top: Math.round(modal.scrollTop), held: held ? Number(held.dataset.index) : null, indexes: indexes.length, first: Math.min(...indexes), last: Math.max(...indexes), allowed: view + 3 * over + 1 };
  });
  const tableHolds = async (step) => {
    const one = await table();
    check(`after ${step}, the editor's document holds at most window + over + 1 rows and the focused row is drawn`, one.indexes <= one.allowed && (one.held === null || one.held >= one.first && one.held <= one.last), one);
    return one;
  };
  let t = await tableHolds("opening the editor");
  check("the editor's long table draws a window of its rows between two spacers", t.rows > 250 && t.spacers === 2 && t.drawn < t.rows, t);
  await page.evaluate(() => { const m = document.querySelector("#editor .modal"); m.scrollTop = (m.scrollHeight - m.clientHeight) / 2; });
  await page.waitForTimeout(300);
  t = await tableHolds("a scroll to the middle");
  check("a scroll to the middle draws the middle and drops the top", t.drawn < t.rows && t.drawn > 10 && !(await page.evaluate(() => Boolean(document.querySelector("#ed-rows .editor-rows").querySelector("tr[data-index='2']")))), t);
  await page.evaluate(() => focusEditorRow("R141"));
  await page.waitForTimeout(300);
  t = await tableHolds("focus_editor_row");
  check("focus_editor_row draws the row it was asked for, focuses it and scrolls to it", t.held !== null && (await page.evaluate(() => document.activeElement.closest("tr").querySelector(".req-id").textContent.startsWith("R141"))), t);
  // The walk starts at the window's last drawn row, so it crosses the edge, and runs far enough to pass it.
  const edge = (await table()).last;
  await page.focus(`#ed-rows .editor-rows tr[data-index='${edge}'] input, #ed-rows .editor-rows tr[data-index='${edge}'] select`);
  const rowOf = () => page.evaluate(() => { const tr = document.activeElement.closest && document.activeElement.closest("tr[data-index]"); return tr ? Number(tr.dataset.index) : -1; });
  const walked = [await rowOf()];
  const overs = [];
  for (let i = 0; i < 120; i += 1) {
    await page.keyboard.press("Tab");
    walked.push(await rowOf());
    const one = await table();
    if (one.indexes > one.allowed || one.held === null) overs.push([i, one]);
  }
  check("Tab walks every row's inputs from the window's edge in order, never skipping a row", walked.every((n, i) => i === 0 || (n - walked[i - 1] === 0 || n - walked[i - 1] === 1)) && walked[0] === edge && walked.at(-1) >= edge + 3, [edge, walked]);
  check("after every Tab, the editor's document holds at most window + over + 1 rows and the focused row is drawn", overs.length === 0, overs.slice(0, 2));
  // A value typed in a row that then leaves the document is in the rows the save reads.
  const row = walked.at(-1);
  await page.focus(`#ed-rows .editor-rows tr[data-index='${row}'] .ed-expected_count input`);
  await page.keyboard.press("End");
  await page.keyboard.type("7");
  const typed = await page.evaluate((i) => document.querySelector("#ed-rows .editor-rows").editorWindow.rows[i].expected_count, row);
  await page.evaluate(() => { document.activeElement.blur(); const m = document.querySelector("#editor .modal"); m.scrollTop = 0; });
  await page.waitForTimeout(300);
  const left = await page.evaluate((i) => { const box = document.querySelector("#ed-rows .editor-rows"); return [!box.querySelector(`tr[data-index='${i}']`), box.editorWindow.rows[i].expected_count, editorRows.includes(box.editorWindow.rows[i])]; }, row);
  check("a value typed in a row scrolled out of the document is in the saved list", left[0] === true && left[2] === true && String(left[1]).endsWith("7") && String(typed).endsWith("7"), [left, typed, row]);
  await context.close();
}

await browser.close();
server.close();
if (failures.length) {
  console.log("FAILED:\n" + failures.join("\n"));
  process.exit(1);
}
console.log("all interactions pass");
