// Shoots the harness scenarios (SPEC-shell 14.4) in the cloud's Chromium:
// light and dark, 1100 x 700 and 1400 x 900, plus the checks that a
// screenshot cannot show (the smoke run of the real app.js, contrast
// theme by forced-colors emulation). Made-up names only.
//
//   node pilot/harness/shoot.mjs <out-dir> [scenario ...]
//
// Needs: playwright (global), the repo's Python for the vocabulary
// (HARNESS_PYTHON, default python3).
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
const repo = path.resolve(here, "..", "..");
const out = path.resolve(process.argv[2] || path.join(os.tmpdir(), "shell-shots"));
const only = process.argv.slice(3);
fs.mkdirSync(out, { recursive: true });

const vocabFile = path.join(out, "vocab.json");
execFileSync(process.env.HARNESS_PYTHON || "python3", [path.join(here, "make_vocab.py"), vocabFile], { cwd: repo, stdio: "inherit" });
const { server, port } = await serve(fs.readFileSync(vocabFile, "utf-8"));
const base = `http://127.0.0.1:${port}/`;

const SIZES = [[1100, 700], [1400, 900]];
const THEMES = ["light", "dark"];
const go = (route) => `shellGo(${JSON.stringify(route)})`;
const smith = "/clients/J Park & Associates/Smith Family";
const smithReturn = `${smith}/2025/1040 - John & Jane Smith`;
const SCENARIOS = [
  { name: "overview", query: "" },
  { name: "overview-empty", query: "?scenario=empty-clients" },
  { name: "needs-review", query: "", run: go({ level: "needs-review" }) },
  { name: "reminders", query: "", run: go({ level: "reminders" }) },
  { name: "clients", query: "", run: go({ level: "clients" }) },
  { name: "household", query: "", run: go({ level: "household", household: smith }) },
  { name: "household-no-returns", query: "", run: go({ level: "household", household: "/clients/J Park & Associates/Patel Family" }) },
  { name: "year", query: "", run: go({ level: "year", household: smith, year: 2025 }) },
  { name: "return", query: "", run: go({ level: "return", household: smith, year: 2025, ret: smithReturn }) },
  { name: "return-empty", query: "", run: go({ level: "return", household: "/clients/J Park & Associates/Novak Household", year: 2025, ret: "/clients/J Park & Associates/Novak Household/2025/1040 - Petra Novak" }) },
  { name: "sheet-frame", query: "", run: `${go({ level: "return", household: smith, year: 2025, ret: smithReturn })}; setTimeout(() => openSheetFrame("scan0012.pdf"), 200)` },
  { name: "setup", query: "?scenario=setup" },
  { name: "loading", query: "?scenario=slow" },
  { name: "sort-running", query: "", run: `${go({ level: "household", household: smith })}; scanning = { pass: "p1", stopping: false }; shellProgress({ n: 3, of: 12, household: "Smith Family" }); shellChanged()` },
  { name: "sort-failed", query: "?scenario=failed", run: "" },
  { name: "locked", query: "", run: `${go({ level: "return", household: smith, year: 2025, ret: smithReturn })}; setTimeout(() => { locked = true; shellChanged(); }, 200)` },
  { name: "counts-fail", query: "?scenario=firm-fails" },
  { name: "search", query: "", search: "smith" },
  { name: "tooltip-mouse", query: "", run: go({ level: "household", household: smith }), hover: "#sort" },
  { name: "tooltip-keyboard", query: "", run: go({ level: "household", household: smith }), focusKey: "#sort" },
];

const browser = await chromium.launch({ executablePath: process.env.CHROMIUM || undefined, args: ["--no-sandbox"] });
const problems = [];
let shots = 0;
for (const scenario of SCENARIOS) {
  if (only.length && !only.includes(scenario.name)) continue;
  for (const theme of THEMES) {
    for (const [width, height] of SIZES) {
      const context = await browser.newContext({ viewport: { width, height }, colorScheme: theme, reducedMotion: "reduce" });
      await context.addInitScript(() => { localStorage.setItem("pilot.terms.accepted", "1"); localStorage.setItem("pilot.tour.seen", "1"); });
      const page = await context.newPage();
      page.on("pageerror", (e) => problems.push(`${scenario.name} ${theme} ${width}: ${e.message}`));
      page.on("console", (m) => m.type() === "error" && problems.push(`${scenario.name} ${theme} ${width}: console ${m.text()}`));
      await page.goto(`${base}${scenario.query}`);
      if (scenario.name !== "loading") await page.waitForFunction(() => window.HARNESS && window.HARNESS.calls.includes("firm") && !document.querySelector("#page[aria-busy=true]"), null, { timeout: 8000 }).catch(() => {});
      if (scenario.run) await page.evaluate(scenario.run);
      if (scenario.search) { await page.focus("#find"); await page.keyboard.type(scenario.search); }
      if (scenario.hover) { await page.hover(scenario.hover); await page.waitForTimeout(700); }
      if (scenario.focusKey) { await page.keyboard.press("F6"); await page.keyboard.press("F6"); await page.focus(scenario.focusKey); await page.keyboard.press("Shift+Tab"); await page.keyboard.press("Tab"); await page.waitForTimeout(200); }
      await page.waitForTimeout(scenario.name === "loading" ? 300 : 350);
      await page.screenshot({ path: path.join(out, `${scenario.name}-${theme}-${width}x${height}.png`) });
      shots += 1;
      await context.close();
    }
  }
}

// Contrast theme, emulated once at the minimum size.
if (!only.length || only.includes("forced-colors")) {
  for (const width of [1100]) {
    const context = await browser.newContext({ viewport: { width, height: 700 }, forcedColors: "active" });
    await context.addInitScript(() => { localStorage.setItem("pilot.terms.accepted", "1"); localStorage.setItem("pilot.tour.seen", "1"); });
    const page = await context.newPage();
    await page.goto(`${base}`);
    await page.waitForTimeout(600);
    await page.evaluate(go({ level: "return", household: smith, year: 2025, ret: smithReturn }));
    await page.waitForTimeout(400);
    await page.screenshot({ path: path.join(out, `forced-colors-${width}x700.png`) });
    shots += 1;
    await context.close();
  }
}

// The real app.js on the stub tracker: it must load, bootstrap and hand the
// shell its data without a page error.
if (!only.length || only.includes("real-app")) {
  const context = await browser.newContext({ viewport: { width: 1100, height: 700 } });
  await context.addInitScript(() => { localStorage.setItem("pilot.terms.accepted", "1"); localStorage.setItem("pilot.tour.seen", "1"); });
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto(`${base}?mode=real`);
  await page.waitForTimeout(1500);
  const side = await page.evaluate(() => [...document.querySelectorAll(".side-name")].map((n) => n.textContent).join("|"));
  const title = await page.evaluate(() => document.querySelector("#page h1")?.textContent);
  // app.js catches its own errors, draws a notice and logs them, so an uncaught
  // "page error" count alone hides them: read the log and the visible notice too.
  const logged = await page.evaluate(() => window.HARNESS.logged.slice());
  const notice = await page.evaluate(() => [...document.querySelectorAll("#notices .notice, #error, .error")].map((n) => n.textContent.trim()).filter(Boolean).join("; "));
  if (errors.length) problems.push(`real app.js: ${errors.join("; ")}`);
  if (logged.length) problems.push(`real app.js logged: ${logged.join("; ")}`);
  if (notice) problems.push(`real app.js shows an error: ${notice}`);
  if (side !== "Overview|Needs review|Reminders|Clients") problems.push(`real app.js: side panel is "${side}"`);
  await page.screenshot({ path: path.join(out, "real-app-1100x700.png") });
  console.log(`real app.js: side panel "${side}", page title "${title}", ${errors.length} page errors, ${logged.length} logged, ${notice ? `shows "${notice}"` : "no visible error"}`);
  await context.close();
}

await browser.close();
server.close();
console.log(`${shots} screenshots in ${out}`);
if (problems.length) {
  console.log("PROBLEMS:\n" + problems.join("\n"));
  process.exit(1);
}
