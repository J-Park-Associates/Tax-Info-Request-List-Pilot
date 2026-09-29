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

async function open(query = "", { firm = true } = {}) {
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
  check("Ctrl+2 goes to Needs review", (await current(page)) === "Needs review", await current(page));
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
  check("no match says so", (await page.textContent("#find-list")) === "No match", await page.textContent("#find-list"));
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
  check("first run shows the setup page", (await page.textContent("#page h1")) === "Choose your clients folder", null);
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
  check("the return draws its groups in order", titles.join("|") === "Needs you|Waiting on client|Received|Set aside", titles);
  check("Set aside is shut", await page.evaluate(() => !document.querySelector("#page details").open), null);
  await page.focus("#page .rows");
  await page.keyboard.press("Enter");
  await page.waitForTimeout(300);
  check("Enter on a Check row asks the sheet to open", await page.evaluate(() => !document.getElementById("sheet").hidden), null);
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
  check("two years, folder renamed with Accept", text.includes("Two years open") && text.includes("Accept"), text);
  const logged = await page.evaluate(() => window.HARNESS.logged.join("\n"));
  check("the pause and the feed are short lines on screen and long sentences in the error log", !text.includes("Paused:") && !text.includes("drop folder") && logged.includes("Paused: this folder's name") && logged.includes("this drop folder is set to feed"), [text, logged]);
  await page.evaluate(() => shellGo({ level: "clients" }));
  check("they go when the household's pages do", await page.evaluate(() => !document.querySelector("#notices .notice")), null);
  await context.close();
}

{ // a live lock: one notice, and the request list is not offered
  const { context, page } = await open("?mode=real&scenario=locked");
  await page.evaluate(() => shellGo({ level: "return", household: "/clients/J Park & Associates/Smith Family", year: 2025, ret: "/clients/J Park & Associates/Smith Family/2025/1040 - John & Jane Smith" }));
  await page.waitForFunction(() => document.querySelector("#notices .notice"), null, { timeout: 5000 });
  const steps = await page.evaluate(() => [...document.querySelectorAll("#page .row-step")].map((n) => n.textContent));
  check("the lock is one notice", (await page.textContent("#notices")).includes("In use on"), await page.textContent("#notices"));
  check("no row offers Edit while locked", !steps.includes("Edit") && steps.includes("Check"), steps);
  const before = await page.evaluate(() => document.querySelectorAll("#notices .notice").length);
  await page.focus("#page .rows");
  await page.keyboard.press("Enter");
  await page.waitForTimeout(300);
  const after = await page.evaluate(() => document.querySelectorAll("#notices .notice").length);
  check("a step nothing answers yet is one loud notice, never silence", after === before + 1, [before, after]);
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
  check("counts failure is one notice", text.includes("Counts not available") && text.includes("Retry"), text);
  await context.close();
}

await browser.close();
server.close();
if (failures.length) {
  console.log("FAILED:\n" + failures.join("\n"));
  process.exit(1);
}
console.log("all interactions pass");
