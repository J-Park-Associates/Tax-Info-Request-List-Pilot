// The harness's stand-in for the tracker (SPEC-shell 14.4).
//
// Defines window.tracker with made-up data only - the Smith Family, Rivera
// Design LLC, Ana Lopez and 500 generated households with made-up names -
// and the vocabulary blocks of SPEC section 11 in their key shape (`screen`
// and `menu`), laid over the real API's vocabulary (window.__VOCAB__, dumped
// from tracker.api by shoot.mjs) so the renderer can be drawn before the
// engine part lands. Never loaded by the app; pytest does not run it.
"use strict";

(() => {
  const params = new URLSearchParams(location.search);
  const scenario = params.get("scenario") || "normal";

  // ── SPEC 11.3 and 11.4, in their key shape ────────────────────────────
  const screen = {
    sections: { overview: "Overview", needs_review: "Needs review", reminders: "Reminders", clients: "Clients" },
    side_label: "Sections", path_label: "Path", find: "Find a client", find_none: "No match",
    sort: { now: "Sort now", stop: "Stop sorting", firm: "Open a client to sort", locked: "In use elsewhere", stopping: "Stopping" },
    last_sort: { today: "Sorted {time}", other_day: "Sorted {date}", failed: "Sort failed", never: "Not sorted yet", running: "Sorting {n} of {total}", done: "Sorted" },
    figures: { need: "Need a person", waiting: "Waiting on clients", complete: "Complete" },
    work: "Work waiting",
    empty: { overview: "Nothing is waiting", next_sort: "Next sort {time}", needs_review: "Nothing needs review", reminders: "No drafts ready", clients: "No clients yet", work: "No work waiting", returns: "No returns yet", received: "Nothing received yet" },
    filters: { work: "Work waiting", all: "All" },
    counts: { need: "{n} need you", waiting: "{n} waiting", complete: "Complete", returns: "{n} returns", one_return: "1 return", files: "{n} files" },
    due: "Due {date}", partly: "{n} of {total}",
    groups: { needs_you: "Needs you", waiting: "Waiting on client", received: "Received", set_aside: "Set aside" },
    steps: { check: "Check", open: "Open", draft: "Draft reminder", edit: "Edit" },
    moved: "Moved by hand", held: "Held", inactive: "Inactive", rolled: "Rolled forward", contact: "Contact {name}", shared: "Shared", not_shared: "Not shared",
    icons: { dismiss: "Dismiss", open: "Open", next: "Next", more: "More" },
    sheet: { reminder: "Reminder", drafted: "Drafted {date}, stage {n}" },
    loading: "Loading",
    setup: { title: "Choose your clients folder", choose: "Choose folder…", start: "Start", missing: "Folder not found" },
    notices: { firm_failed: "Counts not available", skipped: "{n} folders skipped", show: "Show", no_log: "No error log yet", drive: "Drive not signed in" },
    misfits: { title: "Folders skipped" }, safeguards: { title: "Safeguards" }, about: { edition: "Pilot {version}" },
    retry: "Retry", copied: "Copied", saved: "Saved", schedule: { move_warning: "Only if {host} is retired" },
  };
  const menu = {
    file: "&File", new_household: "New household…", change_root: "Change clients folder…", open_root: "Open clients folder", exit: "Exit",
    edit: "&Edit", client: "&Client", edit_household: "Edit household…", add_return: "Add a return…", roll_forward: "Roll forward…",
    mark_shared: "Mark as shared", edit_list: "Edit request list…", draft_reminder: "Draft reminder…", open_client_folder: "Open client folder",
    open_inbox: "Open inbox", open_working: "Open working folder", check: "Check…", not_requested: "Not requested", another_return: "Another return…",
    put_back: "Put back", keep_here: "Keep here", edit_request: "Edit request…", view: "&View", overview: "Overview", needs_review: "Needs review",
    reminders: "Reminders", clients: "Clients", find: "Find", refresh: "Refresh", tools: "&Tools", sort_now: "Sort now", stop_sorting: "Stop sorting",
    schedule: "Schedule…", repair_schedule: "Repair schedule", firm_report: "Firm report", clear_lock: "Clear stuck lock", help: "&Help",
    tour: "Take the tour", safeguards: "Safeguards", terms: "Terms", error_log: "Open error log", about: "About", unfile: "Unfile", mark_missing: "Mark missing",
  };
  const vocab = Object.assign({}, window.__VOCAB__, { screen, menu });
  vocab.commands = [...vocab.commands, "firm"];

  // ── made-up people ────────────────────────────────────────────────────
  let seq = 0;
  const item = (kind, name, detail, status, date, extra) => Object.assign({ id: `i${++seq}`, kind, name, detail, status, date }, extra || {});
  const file = (name, detail, status, date, extra) => item("file", name, detail, status, date, extra);
  const moved = (name, detail, date) => item("moved", name, detail, "Moved by hand", date);
  const request = (name, detail, status, date) => item("request", name, detail, status, date || "");

  function smith() {
    return {
      needs: [
        file("scan0012.pdf", "W-2 - Acme Corp", "Could not tell", "Mar 3", { suggest: ["W-2 - Acme Corp", "1099-R - Evergreen Funds"] }),
        file("IMG_2231.jpg", "1099-INT", "Fits two requests", "Mar 4", { suggest: ["1099-INT - Bluebird Credit Union", "1099-INT - Harbor Bank"] }),
        moved("northwind-2025.pdf", "1099-B - Northwind", "Mar 5"),
        request("1098 - Harbor Bank", "", "Could not use", "Mar 2"),
      ],
      waiting: [request("1099-B - Northwind Brokerage", "Dec 2025", "Outstanding"), request("K-1 - Hillside Partners LP", "1 of 2", "Partly in")],
      received: [
        request("W-2 - Brightline Health", "w2-jane.pdf", "Received", "Mar 1"),
        request("1099-INT - Bluebird Credit Union", "bluebird-int.pdf", "Received", "Mar 1"),
        request("1099-DIV - Evergreen Funds", "evergreen-div.pdf", "Accepted", "Feb 27"),
        request("1095-C - Brightline Health", "1095c.pdf", "Received", "Feb 26"),
        request("Property tax bill", "county-tax.pdf", "Received", "Feb 24"),
        request("Childcare receipts", "3 files", "Received", "Feb 20"),
      ],
      setAside: [
        request("1099-G - State refund", "", "Not asked"),
        request("1098-T - Tuition", "", "Not applicable 2025"),
        file("old-scan.pdf", "", "Not requested", "Jan 30"),
      ],
      due: "Due Apr 15", draft: { ready: true, stage: 1, held: 3, drafted: "2026-03-03" },
    };
  }
  function generic(need, waiting, received, due) {
    const body = { needs: [], waiting: [], received: [], setAside: [], due, draft: null };
    const files = ["scan_0041.pdf", "IMG_4410.jpg", "statement.pdf", "k1-2025.pdf", "bank-mar.pdf"];
    const why = ["Could not tell", "Fits two requests", "Scan not readable", "Names another return", "Wrong period"];
    for (let i = 0; i < need; i += 1) body.needs.push(file(files[i % 5], "", why[i % 5], `Mar ${2 + i}`));
    const w = ["1099-INT - Harbor Bank", "1099-DIV - Evergreen Funds", "W-2 - Acme Corp", "1098 - Harbor Bank", "K-1 - Hillside Partners LP"];
    for (let i = 0; i < waiting; i += 1) body.waiting.push(request(w[i % 5], "", i % 3 === 2 ? "Partly in" : "Outstanding"));
    const g = ["W-2 - Acme Corp", "1099-INT - Bluebird Credit Union", "Property tax bill", "1098 - Harbor Bank", "Charitable letters", "1095-A - Marketplace"];
    for (let i = 0; i < received; i += 1) body.received.push(request(g[i % 6], "received.pdf", "Received", `Feb ${10 + i}`));
    return body;
  }

  const ROOT = "/clients/J Park & Associates";
  const bodies = {};       // return path -> body
  const households = [];
  const engagements = [];
  function household(name, contact, returns) {
    const path = `${ROOT}/${name}`;
    const rows = returns.map(([form, year, body]) => {
      const returnName = form;
      const rpath = `${path}/${year}/${returnName}`;
      bodies[rpath] = body;
      engagements.push({ name: `${name} ${year} ${returnName}`, path: rpath, household: path, year, return_name: returnName });
      return { label: returnName, path: rpath, year, return_name: returnName, active: true, superseded_by: null, rollable: year === 2025 };
    });
    households.push({
      name, path, client_folder: `/clients/Clients/${name}`, inbox: `/clients/Clients/${name}/Drop files here`,
      members: [contact], contact, link: "", problem: "", open_years: rows.length ? [Math.max(...rows.map((r) => r.year))] : [], returns: rows,
    });
  }
  if (scenario !== "empty-clients") {
    household("Smith Family", "John Smith", [["1040 - John & Jane Smith", 2025, smith()], ["1040 - John & Jane Smith", 2024, generic(0, 0, 11, "")]]);
    household("Rivera Design", "Marco Rivera", [["1120-S - Rivera Design LLC", 2025, generic(1, 3, 6, "Due Mar 16")], ["1040 - Marco Rivera", 2025, Object.assign(generic(0, 2, 7, "Due Apr 15"), { draft: { ready: true, stage: 0, held: 0, drafted: "2026-03-03" } })]]);
    household("Lopez Household", "Ana Lopez", [["1040 - Ana Lopez", 2025, Object.assign(generic(0, 2, 5, "Due Apr 15"), { draft: { ready: true, stage: 1, held: 0, drafted: "2026-03-03" } })]]);
    household("Chen Family", "Wei Chen", [["1040 - Wei & Lin Chen", 2025, generic(2, 1, 8, "Due Apr 15")]]);
    household("Okafor Family", "Ada Okafor", [["1040 - Chidi & Ada Okafor", 2025, generic(0, 0, 12, "")]]);
    household("Alexandria Montgomery-Whitfield & Christopher Delacroix Family", "Alexandria Whitfield", [["1040 - Alexandria Montgomery-Whitfield & Christopher Delacroix (married filing jointly)", 2025, generic(0, 3, 2, "Due Apr 15")]]);
    household("Patel Family", "Nina Patel", []);
    household("Novak Household", "Petra Novak", [["1040 - Petra Novak", 2025, generic(0, 2, 0, "Due Apr 15")]]);
    const last = ["Abbott", "Barros", "Castell", "Dunmore", "Ellery", "Farrow", "Garland", "Hale", "Ingram", "Jessop", "Kerrigan", "Lindqvist", "Marlow", "Nyberg", "Oakes", "Pembrook", "Quill", "Rowntree", "Sallow", "Thorne"];
    const first = ["Avery", "Blake", "Casey", "Drew", "Emery", "Finley", "Harper", "Jordan", "Kendall", "Morgan"];
    let s = 7;
    const rnd = () => { s = (s * 16807) % 2147483647; return s / 2147483647; };
    for (let i = 0; i < 500; i += 1) {
      const l = last[i % 20];
      const f = first[Math.floor(i / 50)];
      const roll = rnd();
      const body = roll < 0.035 ? generic(1, 1, 6, "Due Apr 15") : roll < 0.16 ? generic(0, 1 + (i % 3), 6, "Due Apr 15") : generic(0, 0, 8, "");
      household(`${l} Household (${f} ${i})`, `${f} ${l}`, [[`1040 - ${f} ${l}`, 2025, body]]);
    }
  }

  const groupCounts = (body) => ({ needs_you: body.needs.length, waiting: body.waiting.length, received: body.received.length, set_aside: body.setAside.length });
  function firm() {
    const returns = engagements.filter((e) => e.year === 2025).map((e) => {
      const body = bodies[e.path];
      const owner = households.find((one) => one.path === e.household);
      return {
        path: e.path, household: owner.name, counts: groupCounts(body), files: body.needs.filter((x) => x.kind !== "request").length,
        oldest: body.needs.length ? "2026-03-02" : null, due: body.due ? "2026-04-15" : null,
        draft: body.draft || { ready: false, stage: 0, held: 0, drafted: null }, problem: "",
      };
    });
    const totals = {
      need: returns.filter((r) => r.counts.needs_you).length,
      waiting: returns.filter((r) => !r.counts.needs_you && r.counts.waiting).length,
      complete: returns.filter((r) => !r.counts.needs_you && !r.counts.waiting).length,
      files: returns.reduce((n, r) => n + r.files, 0),
      drafts: returns.filter((r) => r.draft.ready).length,
    };
    return { returns, files: [], totals, next_sort: "6:00 PM" };
  }

  const lastWhen = new Date();
  lastWhen.setHours(6, 0, 0, 0);
  const lastPass = scenario === "failed"
    ? { text: "The last sort failed.", level: "err", ok: false, when: lastWhen.toISOString() }
    : scenario === "setup" ? null : { text: "Sorted.", level: "ok", ok: true, when: lastWhen.toISOString() };

  let rootSet = scenario !== "setup";
  const wait = (ms, value) => new Promise((resolve) => setTimeout(() => resolve(value), ms));
  const calls = [];

  window.HARNESS = { scenario, bodies, households, engagements, calls, menuLog: [], opened: [], logged: [] };
  window.tracker = {
    call: async (args, payload) => {
      calls.push(args[0]);
      const command = args[0];
      if (command === "list") {
        const base = { engagements: rootSet ? engagements : [], households: rootSet ? households : [], misfits: [], root: rootSet ? ROOT : "", needs_root: !rootSet, vocab,
          reader_warning: "", last_pass: lastPass, after_install: null, machine_warnings: [] };
        if (rootSet) base.paths = { clients_root: ROOT, status: `${ROOT}/status.html` };
        return wait(20, base);
      }
      if (command === "firm") {
        if (scenario === "firm-fails") return wait(20, { error: "The counts could not be read.", failure: { sentence: "The counts could not be read.", kind: "failed" } });
        return wait(scenario === "slow" ? 1500 : 30, firm());
      }
      if (command === "state") {
        const path = args[args.length - 1];
        const owner = households.find((one) => path.indexOf(one.path) === 0);
        return wait(20, { paths: { engagement: path, inbox: owner ? owner.inbox : "", client_folder: owner ? owner.client_folder : "", status: `${ROOT}/status.html` },
          household: { shared_on: owner && owner.name === "Lopez Household" ? "" : "2026-02-01" }, harness: bodies[path] || generic(0, 0, 0, "") });
      }
      if (command === "pilot-record") return wait(10, { terms: "1", tour_seen: true });
      if (command === "set-root") {
        rootSet = true;
        return wait(50, { root: ROOT, settings_path: "", after_install: { schedule_sentence: "", failed: [] }, short_of_room: [] });
      }
      return wait(10, { error: "The harness does not answer this.", failure: { sentence: "The harness does not answer this.", kind: "failed" } });
    },
    open: (path) => window.HARNESS.opened.push(path),
    pickFolder: async () => "/clients/Client Files",
    logError: (text) => window.HARNESS.logged.push(text),
    onProgress: () => {},
    onAfterInstallDone: null,
    menu: {
      onCommand: (listener) => { window.HARNESS.menuListener = listener; },
      send: (message) => window.HARNESS.menuLog.push(message),
    },
  };
})();
