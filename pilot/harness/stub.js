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

  // SPEC 11.5 and 11.6: a short label for each reason code and a short name
  // for each reminder stage (S1 adds them to the real vocabulary). Only the
  // codes the made-up files use.
  const SHORT = {
    unmatched: "Could not tell", ambiguous: "Fits two requests", "no-text-layer": "Scan not readable", "name-other": "Names another return",
    "wrong-period": "Wrong period", "opened-not-across": "Came in email or zip", "not-a-document": "Not a document",
  };
  vocab.reasons = Object.fromEntries(Object.entries(SHORT).map(([code, short]) => [code, { short }]));
  const STAGE_SHORT = ["Heads up", "Checking in", "Deadline near", "Final notice"];
  vocab.reminder = Object.assign({}, vocab.reminder, { stages: vocab.reminder.stages.map((one, i) => Object.assign({}, one, { short: STAGE_SHORT[i] })) });
  // The words S1's API sends for the notices (claude/sharp-goldberg-jmfynk:
  // tracker/api.py), constant for constant - including the LONG sentences the
  // app must not draw (the lock's `on` and `greyed`, the reader's warning, the
  // pause, a feed). The vocabulary this branch dumps still holds older words.
  vocab.household = Object.assign({}, vocab.household, { two_open_years: "Two years open; sorting paused", accept_folder_name: "Accept the folder's name" });
  vocab.room = Object.assign({}, vocab.room, { heading: "Names shortened to fit" });
  // SPEC 2.5 E68: the bucket headings are the words alone (S1 cuts the descriptions).
  vocab.review_labels = Object.assign({}, vocab.review_labels, {
    buckets: { document: "Documents", container: "Emails and zips", not_a_document: "Not documents" },
  });
  vocab.after_install = Object.assign({}, vocab.after_install, { heading: "After installing: needs a person", wait: "Setup needs attention" });
  vocab.lock = Object.assign({}, vocab.lock, {
    running: "In use on {host}", running_other: "{label} in use on {host}", on: "It is on {household}: {name}.",
    greyed: "This return's buttons are greyed while it runs and come back by themselves the moment it lets go.",
    left_behind: "Stuck lock from {host}",
  });
  // The long sentences of the API's other sources, as sent (tracker/ocr.py,
  // households.py, runner.py, settings.py at S1's tip); paths made up.
  const LONG = {
    reader: "Move the app to a shorter folder, for example C:\\JPA Tracker; scans can't be read from here",
    machine: [
      "Left over from an earlier version and no longer used: C:\\Made Up\\Tracker\\old-run.log. They hold client names, and nothing deletes them for you - delete them. "
        + "The tracker keeps its database and its run log in C:\\Users\\Someone\\AppData\\Local\\Tracker now.",
      "The app is running from a removable drive (E:\\Tracker). The schedule runs whatever program sits there, every pass, so it is not installed from here: "
        + "copy the app's folder to this computer's own disk (a short path, such as C:\\Tools), start it from there and press Install Schedule.",
    ],
    paused: "Paused: this folder's name and its record's name disagree. Nothing is sorted, laid out or drafted for the household until a person opens it in the app and "
      + "accepts the folder's name, or gives the folder back the name its record holds.",
    feed: "this drop folder is set to feed Lopez Household / 1040 - Ana Lopez, which has no active return for 2025",
    findingsWait: "A household named above as malformed or as changed behind the tracker's back waits in the app until a person repairs it (runbook \u00a79); "
      + "any other line above is for a person to look at. The rest of the practice runs as normal.",
  };

  // ── made-up people ────────────────────────────────────────────────────
  // A body is the authoring format of one return: the four groups of rows a
  // page will show. `stateOf` turns it into the shape of the API's `state`
  // reply (items with `group`, the index, the triage, the moved list).
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
        file("statement-march.eml", "", "Came in email or zip", "Mar 6", { bucket: "container" }),
        file("scan-of-a-postcard.heic", "", "Not a document", "Mar 6", { bucket: "not_a_document" }),
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
      return { label: returnName, path: rpath, year, return_name: returnName, active: year === 2025, superseded_by: year === 2025 ? null : "next", rollable: year === 2025 };
    });
    households.push({
      name, path, client_folder: `/clients/Clients/${name}`, inbox: `/clients/Clients/${name}/Drop files here`,
      members: [contact], contact, link: "", problem: "", open_years: rows.length ? [Math.max(...rows.map((r) => r.year))] : [], returns: rows,
    });
  }
  if (scenario === "quiet") {
    // Nothing waits anywhere: the empty Overview, Needs review and Reminders.
    household("Okafor Family", "Ada Okafor", [["1040 - Chidi & Ada Okafor", 2025, generic(0, 0, 12, "")]]);
    household("Patel Family", "Nina Patel", [["1040 - Nina Patel", 2025, generic(0, 0, 9, "")]]);
  } else if (scenario !== "empty-clients") {
    household("Smith Family", "John Smith", [["1040 - John & Jane Smith", 2025, smith()], ["1040 - John & Jane Smith", 2024, generic(0, 0, 11, "")]]);
    household("Rivera Design", "Marco Rivera", [["1120-S - Rivera Design LLC", 2025, generic(1, 3, 6, "Due Mar 16")], ["1040 - Marco Rivera", 2025, Object.assign(generic(0, 2, 7, "Due Apr 15"), { draft: { ready: true, stage: 2, held: 0, drafted: "2026-03-03" } })]]);
    household("Lopez Household", "Ana Lopez", [["1040 - Ana Lopez", 2025, Object.assign(generic(0, 2, 5, "Due Apr 15"), { draft: { ready: true, stage: 3, held: 0, drafted: "2026-03-03" } })]]);
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

  // ── the API's shapes, from a body ─────────────────────────────────────
  const MONTH = { Jan: "01", Feb: "02", Mar: "03", Apr: "04", May: "05", Jun: "06" };
  const dayOf = (text) => {
    const parts = /^([A-Z][a-z]{2}) (\d{1,2})$/.exec(text || "");
    return parts ? `2026-${MONTH[parts[1]]}-${parts[2].padStart(2, "0")}` : "";
  };
  const dueOf = (text) => dayOf((text || "").replace("Due ", ""));
  const CODE = Object.fromEntries(Object.entries(SHORT).map(([code, short]) => [short, code]));
  const LABEL = { "Could not use": "Failed Validation", Outstanding: "Missing", "Partly in": "Partial", "Not yet checked": "Requested", Received: "Received", Accepted: "Accepted", "Not asked": "Not asked", "Not applicable 2025": "Not Applicable" };
  const GROUP_OF = { needs: "needs_you", waiting: "waiting", received: "received", setAside: "set_aside" };
  let handleSeq = 0;

  function stateOf(path) {
    const body = bodies[path] || generic(0, 0, 0, "");
    const items = [];
    const index = [];
    const review = [];
    const movedList = [];
    const year = 2025;
    const push = (key, one) => {
      const group = GROUP_OF[key];
      if (one.kind === "request") {
        const partly = /^(\d+) of (\d+)$/.exec(one.detail);
        const period = /^[A-Z][a-z]{2} \d{4}$/.test(one.detail) ? one.detail : "";
        const filedAs = group === "received" ? one.detail : "";
        const identifier = `R${String(items.length + 1).padStart(2, "0")}`;
        items.push({
          identifier, document: one.name, short_name: one.name, period, year: period ? Number(period.slice(-4)) : null, group,
          status_key: LABEL[one.status], manual_override: one.status === "Not applicable 2025" ? "Not Applicable" : one.status === "Accepted" ? "Accepted" : "",
          side: null, side_sentence: "", file_count: partly ? Number(partly[1]) : group === "received" ? 1 : 0, expected_count: partly ? Number(partly[2]) : 1,
          received_date: dayOf(one.date) || null, asked: one.status !== "Not asked", not_asked_idle: one.status === "Not asked", has_document: group === "received",
        });
        const many = /^(\d+) files$/.exec(filedAs);
        const names = many ? Array.from({ length: Number(many[1]) }, (_, i) => `${one.name.toLowerCase().replace(/\W+/g, "-")}-${i + 1}.pdf`) : filedAs ? [filedAs] : [];
        for (const original of names) {
          handleSeq += 1;
          index.push({ handle: `h${handleSeq}`, original_name: original, received: dayOf(one.date), decision: "Filed", identifier, code: "matched", answered: [], filed_names: [original], seq: handleSeq });
        }
        return;
      }
      handleSeq += 1;
      const handle = `h${handleSeq}`;
      if (one.kind === "moved") {
        movedList.push({ original_name: one.name, handle, seq: handleSeq, home: "", now: "", in_request: "", gone: false, identifier: "" });
        index.push({ handle, original_name: one.name, received: dayOf(one.date), decision: "File Moved", identifier: "", code: "file-moved", answered: [], seq: handleSeq });
        return;
      }
      const dismissed = group === "set_aside";
      index.push({
        handle, original_name: one.name, received: dayOf(one.date), decision: dismissed ? "Not Requested" : "Needs Review", identifier: "",
        code: dismissed ? "not-requested" : CODE[one.status], bucket: one.bucket || "document", answered: [], seq: handleSeq,
      });
      if (!dismissed) {
        review.push({ handle, seq: handleSeq, shortlist: (one.suggest || []).map((name) => ({ identifier: name, reason: name })), set_aside: [], genre: "", group: one.bucket || "document" });
      }
    };
    for (const key of Object.keys(GROUP_OF)) for (const one of body[key]) push(key, one);
    const owner = households.find((one) => path.indexOf(one.path) === 0);
    const hh = owner ? owner.name : "";
    const noticing = scenario === "household-notices" && hh === "Smith Family";
    const lock = scenario === "locked" ? { started: "2026-03-03T06:00:00", host: "OFFICE-PC", age_minutes: 3, stale: false, engagement: path, label: "",
      pass: { household: "Smith Family", name: "1040 - John & Jane Smith" } }
      : scenario === "stale-lock" ? { started: "2026-03-02T06:00:00", host: "OFFICE-PC", age_minutes: 900, stale: true, engagement: path, label: "" } : null;
    return {
      paths: { engagement: path, inbox: owner ? owner.inbox : "", client_folder: owner ? owner.client_folder : "", status: `${ROOT}/status.html` },
      items, index, review, moved: movedList, lock, engagement: { due: dueOf(body.due) || "", form: "", people: [] },
      household: {
        path: owner ? owner.path : "", name: hh, members: [], contact: owner ? owner.contact : "", link: "",
        open_years: noticing ? [2025, 2024] : [2025],
        pause: noticing ? { sentence: LONG.paused, scope: "household", engagement: path, seq: 3 } : {},
        feeds: noticing ? [{ label: "", warning: LONG.feed }] : [],
        returns: [], queue: 0, roll_year: null, shared_on: hh === "Lopez Household" ? "" : "2026-02-01",
      },
    };
  }

  const groupCounts = (body) => ({ needs_you: body.needs.length, waiting: body.waiting.length, received: body.received.length, set_aside: body.setAside.length });
  const filesOf = (body) => body.needs.filter((x) => x.kind !== "request");
  function firm() {
    const returns = engagements.filter((e) => e.year === 2025).map((e) => {
      const body = bodies[e.path];
      const owner = households.find((one) => one.path === e.household);
      const days = filesOf(body).map((x) => dayOf(x.date)).sort();
      return {
        path: e.path, household: owner.name, counts: groupCounts(body), files: filesOf(body).length,
        oldest: days[0] || null, due: dueOf(body.due) || null,
        draft: body.draft || { ready: false, stage: 0, held: 0, drafted: null }, problem: "",
      };
    });
    const files = engagements.filter((e) => e.year === 2025).flatMap((e) => filesOf(bodies[e.path]).map((x) => ({
      return: e.path, name: x.name, code: CODE[x.status], received: dayOf(x.date), suggestion: (x.suggest || [])[0] || "",
    })));
    const totals = {
      need: returns.filter((r) => r.counts.needs_you).length,
      waiting: returns.filter((r) => !r.counts.needs_you && r.counts.waiting).length,
      complete: returns.filter((r) => !r.counts.needs_you && !r.counts.waiting).length,
      files: returns.reduce((n, r) => n + r.files, 0),
      drafts: returns.filter((r) => r.draft.ready).length,
    };
    return { returns, files, totals, next_sort: "18:00" };
  }

  const lastWhen = new Date();
  lastWhen.setHours(6, 0, 0, 0);
  const lastPass = scenario === "failed"
    ? { text: "The last sort failed.", level: "err", ok: false, when: lastWhen.toISOString() }
    : scenario === "setup" ? null : { text: "Sorted.", level: "ok", ok: true, when: lastWhen.toISOString() };

  let rootSet = scenario !== "setup";
  const wait = (ms, value) => new Promise((resolve) => setTimeout(() => resolve(value), ms));
  const calls = [];

  // The loud failures the old screen kept in banners, now notices (SPEC 2.2).
  const loud = scenario === "notices" ? {
    reader_warning: LONG.reader,
    machine_warnings: LONG.machine,
    after_install: { failed: ["The daily job could not be registered."], findings: ["A household is malformed."], wait: LONG.findingsWait },
    misfits: [{ path: "x", where: "Clients/Old Files", sentence: "Not a household." }, { path: "y", where: "Clients/Scans", sentence: "Not a household." }, { path: "z", where: "Clients/Misc", sentence: "Not a household." }],
  } : {};

  window.HARNESS = { scenario, bodies, households, engagements, calls, menuLog: [], opened: [], logged: [] };
  window.tracker = {
    call: async (args, payload) => {
      calls.push(args[0]);
      const command = args[0];
      if (command === "list") {
        const base = { engagements: rootSet ? engagements : [], households: rootSet ? households : [], misfits: loud.misfits || [], root: rootSet ? ROOT : "", needs_root: !rootSet, vocab,
          reader_warning: loud.reader_warning || "", last_pass: lastPass, after_install: loud.after_install || null, machine_warnings: loud.machine_warnings || [] };
        if (rootSet) base.paths = { clients_root: ROOT, status: `${ROOT}/status.html` };
        return wait(20, base);
      }
      if (command === "firm") {
        if (scenario === "firm-fails") return wait(20, { error: "The counts could not be read.", failure: { sentence: "The counts could not be read.", kind: "failed" } });
        return wait(scenario === "slow" ? 1500 : 30, firm());
      }
      if (command === "state") return wait(20, stateOf(args[args.length - 1]));
      if (command === "pilot-record") return wait(10, { terms: "1", tour_seen: true });
      if (command === "set-root") {
        rootSet = true;
        return wait(50, { root: ROOT, settings_path: "", after_install: { schedule_sentence: "", failed: [], findings: [] }, short_of_room: [] });
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
