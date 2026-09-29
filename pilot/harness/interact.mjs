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

async function open(query = "", { firm = true, forcedColors } = {}) {
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
  check("counts on the two that hold work", counts.join("|") === "|25|3|", counts);
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

{ // a count failure is one notice with Retry
  const { context, page } = await open("?scenario=firm-fails");
  const text = await page.textContent("#notices");
  check("counts failure is one notice", text.includes("Counts not available") && text.includes("Retry"), text);
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
  check("hover on the search icon shows the tip", (await tipShown()) && (await page.textContent("#tip")) === "Find a client", await page.textContent("#tip"));
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
  await page.hover("#sort");
  await page.waitForTimeout(700);
  const box = await page.evaluate(() => { const t = document.getElementById("tip"); const r = t.getBoundingClientRect(); return { shown: !t.hidden, w: r.width, h: r.height, right: r.right, bottom: r.bottom, iw: innerWidth, ih: innerHeight, color: getComputedStyle(t).color }; });
  check("the tip shows, sized and inside the window", box.shown && box.w > 0 && box.h > 0 && box.right <= box.iw && box.bottom <= box.ih, box);
  await context.close();
}

await browser.close();
server.close();
if (failures.length) {
  console.log("FAILED:\n" + failures.join("\n"));
  process.exit(1);
}
console.log("all interactions pass");
