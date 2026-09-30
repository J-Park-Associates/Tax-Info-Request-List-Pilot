// The harness's stand-in for the tracker (SPEC-shell 14.4).
//
// Defines window.tracker with made-up data only - the Smith Family, Rivera
// Design LLC, Ana Lopez and 500 generated households with made-up names - and
// answers in the shapes the joined engine sends: `list`, `firm` (with the
// returns' `year` and `label`, the files' `handle`, `year` and `open_key`, and
// the top-level `paths` of those keys), `state` (with `shown_key`, `open_key`,
// `open_keys` and `paths`, and the reminder card), and the writes the side sheet
// makes (assign, dismiss, restore, reminder, approve), which change the made-up
// return so the sheet moves on. The words are the joined engine's (see below).
// Never loaded by the app; pytest does not run it.
"use strict";

(() => {
  const params = new URLSearchParams(location.search);
  const scenario = params.get("scenario") || "normal";

  // The words are the engine's own: tracker.api._vocab() of this tree, dumped
  // by make_vocab.py and served as window.__VOCAB__ (no snapshot since S6b).
  // The stub adds nothing to them.
  const vocab = Object.assign({}, window.__VOCAB__);
  const SHORT = Object.fromEntries(Object.entries(vocab.reasons).map(([code, one]) => [code, typeof one === "object" ? one.short : one]));
  // The words a made-up row is authored in: the vocabulary's own (a short reason,
  // a status label, the moved and set-aside words), never typed twice.
  const REASON = (code) => SHORT[code];
  const LB = (word) => vocab.labels[word].label;
  const NA = (year) => vocab.labels["Not Applicable"].label.replace("{year}", String(year));
  const MOVED = vocab.screen.moved;
  const ASIDE = vocab.review_labels.dismiss;
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
  const moved = (name, detail, date, extra) => item("moved", name, detail, MOVED, date, extra);
  const request = (name, detail, status, date) => item("request", name, detail, status, date || "");

  function smith() {
    return {
      needs: [
        file("scan0012.pdf", "", REASON("unmatched"), "Mar 3", { suggest: ["1099-B - Northwind Brokerage", "K-1 - Hillside Partners LP"], review: true }),
        file("IMG_2231.jpg", "", REASON("ambiguous"), "Mar 4", { suggest: ["1099-INT - Bluebird Credit Union", "1098 - Harbor Bank"] }),
        moved("northwind-2025.pdf", "", "Mar 5", { inRequest: "1099-B - Northwind Brokerage" }),
        file("statement-march.eml", "", REASON("opened-not-across"), "Mar 6", { bucket: "container" }),
        file("scan-of-a-postcard.heic", "", REASON("not-a-document"), "Mar 6", { bucket: "not_a_document", copy: false }),
        request("1098 - Harbor Bank", "", LB("Failed Validation"), "Mar 2"),
      ],
      waiting: [request("1099-B - Northwind Brokerage", "Dec 2025", LB("Missing")), request("K-1 - Hillside Partners LP", "1 of 2", LB("Partial"))],
      received: [
        request("W-2 - Brightline Health", "w2-jane.pdf", LB("Received"), "Mar 1"),
        request("1099-INT - Bluebird Credit Union", "bluebird-int.pdf", LB("Received"), "Mar 1"),
        request("1099-DIV - Evergreen Funds", "evergreen-div.pdf", LB("Accepted"), "Feb 27"),
        request("1095-C - Brightline Health", "1095c.pdf", LB("Received"), "Feb 26"),
        request("Property tax bill", "county-tax.pdf", LB("Received"), "Feb 24"),
        request("Childcare receipts", "3 files", LB("Received"), "Feb 20"),
      ],
      setAside: [
        request("1099-G - State refund", "", LB("Not asked")),
        request("1098-T - Tuition", "", NA(2025)),
        file("old-scan.pdf", "", ASIDE, "Jan 30"),
        item("missing", "lost-in-move.pdf", "", MOVED, "Jan 28"),
      ],
      due: "Due Apr 15", draft: { ready: true, stage: 1, held: 3, drafted: "2026-03-03" },
    };
  }
  function generic(need, waiting, received, due) {
    const body = { needs: [], waiting: [], received: [], setAside: [], due, draft: null };
    const files = ["scan_0041.pdf", "IMG_4410.jpg", "statement.pdf", "k1-2025.pdf", "bank-mar.pdf"];
    const why = [REASON("unmatched"), REASON("ambiguous"), REASON("no-text-layer"), REASON("name-other"), REASON("wrong-period")];
    for (let i = 0; i < need; i += 1) body.needs.push(file(files[i % 5], "", why[i % 5], `Mar ${2 + i}`, { suggest: ["1099-INT - Harbor Bank"] }));
    const w = ["1099-INT - Harbor Bank", "1099-DIV - Evergreen Funds", "W-2 - Acme Corp", "1098 - Harbor Bank", "K-1 - Hillside Partners LP"];
    for (let i = 0; i < waiting; i += 1) body.waiting.push(request(w[i % 5], "", i % 3 === 2 ? LB("Partial") : LB("Missing")));
    const g = ["W-2 - Acme Corp", "1099-INT - Bluebird Credit Union", "Property tax bill", "1098 - Harbor Bank", "Charitable letters", "1095-A - Marketplace"];
    for (let i = 0; i < received; i += 1) body.received.push(request(g[i % 6], "received.pdf", LB("Received"), `Feb ${10 + i}`));
    return body;
  }

  const ROOT = "/clients/J Park & Associates";
  const bodies = {};       // return path -> body
  const households = [];
  const engagements = [];
  function household(name, contact, returns, extra) {
    const path = `${ROOT}/${name}`;
    const rows = returns.map(([form, year, body]) => {
      const returnName = form;
      const rpath = `${path}/${year}/${returnName}`;
      bodies[rpath] = body;
      // `label` is the engine's pattern (layout.ENGAGEMENT_LABEL_PATTERN): household, year, return name.
      const label = `${name} ${year} ${returnName}`;
      engagements.push({ name: label, path: rpath, household: path, year, return_name: returnName });
      return { label, path: rpath, year, return_name: returnName, active: year === 2025, superseded_by: year === 2025 ? null : "next", rollable: year === 2025, form: "1040", people: [contact] };
    });
    households.push(Object.assign({
      name, path, client_folder: `/clients/Clients/${name}`, inbox: `/clients/Clients/${name}/Drop files here`,
      members: [contact], contact, link: "", problem: "", open_years: rows.length ? [Math.max(...rows.map((r) => r.year))] : [], returns: rows,
    }, extra || {}));
  }
  if (scenario === "quiet") {
    // Nothing waits anywhere: the empty Overview, Needs Review and Reminders.
    household("Okafor Family", "Ada Okafor", [["1040 - Chidi & Ada Okafor", 2025, generic(0, 0, 12, "")]]);
    household("Patel Family", "Nina Patel", [["1040 - Nina Patel", 2025, generic(0, 0, 9, "")]]);
  } else if (scenario !== "empty-clients") {
    household("Smith Family", "John Smith", [["1040 - John & Jane Smith", 2025, smith()], ["1040 - John & Jane Smith", 2024, generic(0, 0, 11, "")]]);
    household("Rivera Design", "Marco Rivera", [["1120-S - Rivera Design LLC", 2025, generic(1, 3, 6, "Due Mar 16")], ["1040 - Marco Rivera", 2025, Object.assign(generic(0, 2, 7, "Due Apr 15"), { draft: { ready: true, stage: 2, held: 0, drafted: "2026-03-03" } })]]);
    household("Lopez Household", "Ana Lopez", [["1040 - Ana Lopez", 2025, Object.assign(generic(0, 2, 5, "Due Apr 15"), { draft: { ready: true, stage: 3, held: 0, drafted: "2026-03-03" } })]]);
    household("Chen Family", "Wei Chen", [["1040 - Wei & Lin Chen", 2025, generic(2, 1, 8, "Due Apr 15")]], { rollYear: 2026 });
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
  const LABEL = Object.fromEntries(Object.entries(vocab.labels).map(([word, one]) => [one.label, word]));
  LABEL[NA(2025)] = "Not Applicable";
  const GROUP_OF = { needs: "needs_you", waiting: "waiting", received: "received", setAside: "set_aside" };

  // The keys the engine names a working copy by, and the absolute paths under
  // them (made-up; never drawn). `review_copy` opens, the others only reveal.
  const keyOf = (kind, handle, n) => (n === undefined ? `${kind} ${handle}` : `${kind} ${handle} ${n}`);
  const copyPath = (rpath, folder, name) => `${rpath}/${folder}/${name}`;
  const handleOf = (one, n) => (n === undefined ? `h-${one.id}` : `h-${one.id}-${n}`);

  function stateOf(path) {
    const body = bodies[path] || generic(0, 0, 0, "");
    const items = [];
    const index = [];
    const review = [];
    const movedList = [];
    const keys = {};
    const push = (key, one) => {
      const group = GROUP_OF[key];
      if (one.kind === "request") {
        const partly = /^(\d+) of (\d+)$/.exec(one.detail);
        const period = /^[A-Z][a-z]{2} \d{4}$/.test(one.detail) ? one.detail : "";
        const filedAs = group === "received" ? one.detail : "";
        const identifier = `R${String(items.length + 1).padStart(2, "0")}`;
        items.push({
          identifier, document: one.name, short_name: one.name, period, year: period ? Number(period.slice(-4)) : null, group,
          status_key: LABEL[one.status], manual_override: one.status === NA(2025) ? "Not Applicable" : one.status === LB("Accepted") ? "Accepted" : "",
          side: null, side_sentence: "", file_count: partly ? Number(partly[1]) : group === "received" ? 1 : 0, expected_count: partly ? Number(partly[2]) : 1,
          received_date: dayOf(one.date) || null, asked: one.status !== LB("Not asked"), not_asked_idle: one.status === LB("Not asked"), has_document: group === "received",
        });
        const many = /^(\d+) files$/.exec(filedAs);
        const names = many ? Array.from({ length: Number(many[1]) }, (_, i) => `${one.name.toLowerCase().replace(/\W+/g, "-")}-${i + 1}.pdf`) : filedAs ? [filedAs] : [];
        names.forEach((original, n) => {
          const handle = handleOf(one, n);
          const copy = keyOf("filed_copy", handle, 0);
          keys[copy] = copyPath(path, `Prepared/${identifier}`, original);
          index.push({ handle, original_name: original, received: dayOf(one.date), decision: vocab.decisions.filed, group: "received", identifier, code: "matched",
            answered: [], filed_names: [original], open_keys: [copy], seq: 1 });
        });
        return;
      }
      const handle = handleOf(one);
      if (one.kind === "moved") {
        const copy = keyOf("moved_copy", handle);
        keys[copy] = copyPath(path, "Prepared/Elsewhere", one.name);
        movedList.push({ original_name: one.name, handle, seq: 1, home: "", now: "", in_request: "", gone: false, identifier: "", open_key: copy, pbc_location: "", group: "needs_you" });
        if (one.inRequest) movedList[movedList.length - 1].named = one.inRequest;
        index.push({ handle, original_name: one.name, received: dayOf(one.date), decision: vocab.decisions.file_moved, group: "needs_you", identifier: "", code: "file-moved", answered: [], open_keys: [], seq: 1 });
        return;
      }
      if (one.kind === "missing") {
        // A moved file a person marked missing: on the record only, set aside by the engine (index[].group).
        index.push({ handle, original_name: one.name, received: dayOf(one.date), decision: vocab.decisions.file_moved, group: "set_aside", identifier: "", code: "file-moved", answered: [], open_keys: [], seq: 1 });
        return;
      }
      const dismissed = group === "set_aside";
      const entry = {
        handle, original_name: one.name, received: dayOf(one.date), decision: dismissed ? vocab.decisions.dismissed : vocab.decisions.needs_review,
        group: dismissed ? "set_aside" : "needs_you", identifier: "", code: dismissed ? "not-requested" : CODE[one.status], bucket: one.bucket || "document",
        answered: [], open_keys: [], open_key: "", shown_key: "", extension: (/\.([^.]+)$/.exec(one.name) || [])[1] || "", seq: one.seq || 1,
      };
      // An email or a zip has a working copy but no key (ruling 24): its name is plain text.
      if (one.copy !== false && (one.bucket || "document") !== "container") {
        // A parked read document's shown key is its review copy's (S8a review 2); the rest only reveal.
        const shown = one.review ? keyOf("review_copy", handle) : keyOf("shown_copy", handle);
        keys[shown] = copyPath(path, "Prepared/_Review", one.name);
        entry.shown_key = shown;
        if (one.review) entry.open_key = shown;
      }
      index.push(entry);
      if (!dismissed) {
        review.push({ handle, seq: 1, shortlist: (one.suggest || []).map((name) => ({ identifier: "", name, reason: name })), set_aside: [], genre: "", group: one.bucket || "document" });
      }
    };
    for (const key of Object.keys(GROUP_OF)) for (const one of body[key]) push(key, one);
    // A moved copy sits in a request's folder: that request's identifier, from the items.
    for (const one of movedList) {
      const at = items.find((it) => it.document === one.named);
      if (at) Object.assign(one, { in_request: at.identifier, identifier: at.identifier });
      delete one.named;
    }
    // A suggestion names a request of this return: its identifier, from the items.
    for (const one of review) for (const s of one.shortlist) s.identifier = (items.find((it) => it.document === s.name) || items[0] || {}).identifier || "";
    for (const one of review) one.shortlist = one.shortlist.map((s) => ({ identifier: s.identifier, reason: s.name }));
    const owner = households.find((one) => path.indexOf(one.path) === 0);
    const hh = owner ? owner.name : "";
    const noticing = scenario === "household-notices" && hh === "Smith Family";
    const lock = scenario === "locked" ? { started: "2026-03-03T06:00:00", host: "OFFICE-PC", age_minutes: 3, stale: false, engagement: path, label: "",
      pass: { household: "Smith Family", name: "1040 - John & Jane Smith" } }
      : scenario === "stale-lock" ? { started: "2026-03-02T06:00:00", host: "OFFICE-PC", age_minutes: 900, stale: true, engagement: path, label: "" } : null;
    return {
      paths: Object.assign({ engagement: path, inbox: owner ? owner.inbox : "", client_folder: owner ? owner.client_folder : "", status: `${ROOT}/status.html` }, keys),
      items, index, review, moved: movedList, lock, engagement: { due: dueOf(body.due) || "", form: "", people: [] },
      reminder_card: reminderReply(body, path, null),
      household: {
        path: owner ? owner.path : "", name: hh, members: owner ? owner.members : [], contact: owner ? owner.contact : "", link: "",
        open_years: noticing ? [2025, 2024] : [2025],
        pause: noticing ? { sentence: LONG.paused, scope: "household", engagement: path, seq: 3 } : {},
        feeds: noticing ? [{ label: "", warning: LONG.feed }] : [],
        returns: owner ? owner.returns : [], queue: 0, roll_year: owner && owner.rollYear ? owner.rollYear : null, shared_on: hh === "Lopez Household" ? "" : "2026-02-01",
      },
    };
  }

  // ── the reminder card, in the shape state.reminder_card and `reminder` send ──
  const approved = {};   // return path -> {date, stage}
  function reminderReply(body, path, stage) {
    if (!body.draft) return { reminder: null, not_yet: vocab.reminder.not_yet };
    const at = stage || body.draft.stage;
    const held = Array.from({ length: body.draft.held }, (_, i) => ({ identifier: `R${String(i + 1).padStart(2, "0")}`, document: `Held request ${i + 1}`, reason: "held - a file the client sent for this could not be used (it is a photo); a person decides whether the client resends it or we file what came" }));
    const letter = {
      greeting: "Hi John and Jane,", progress: "", intro: "A few documents are still needed for your 2025 return.",
      sections: [{ heading: "Still needed", items: ["1099-B - Northwind Brokerage", "K-1 - Hillside Partners LP"] }],
      drop: [], link: "", deadline: [], close: "Thank you,", signoff: ["Jason", "J Park & Associates"],
    };
    const text = [letter.greeting, letter.intro, letter.sections[0].heading, ...letter.sections[0].items, letter.close, ...letter.signoff].join("\n\n");
    return { reminder: {
      stage: at, editable: !held.length, held, unsorted: 0, asked: held.length ? [] : ["R01"], file: { edited: false, exists: true },
      subject: "Documents needed for your 2025 return", text, html: `<p>${text}</p>`, fingerprint: `fp-${path}-${at}`,
      last: { date: body.draft.drafted, stage: body.draft.stage }, approved: approved[path] || null, lapsed: false, held_too_long: "", link_dropped: "", letter,
    } };
  }

  const groupCounts = (body) => ({ needs_you: body.needs.length, waiting: body.waiting.length, received: body.received.length, set_aside: body.setAside.length });
  const filesOf = (body) => body.needs.filter((x) => x.kind !== "request");
  function firm() {
    const paths = {};
    const returns = engagements.filter((e) => e.year === 2025).map((e) => {
      const body = bodies[e.path];
      const owner = households.find((one) => one.path === e.household);
      const days = filesOf(body).map((x) => dayOf(x.date)).sort();
      return {
        path: e.path, household: owner.name, label: e.name, year: e.year, counts: groupCounts(body), files: filesOf(body).length,
        oldest: days[0] || null, due: dueOf(body.due) || null,
        draft: body.draft || { ready: false, stage: 0, held: 0, drafted: null }, problem: "",
        // The engine (tracker/api.py firm, ruling 21) sends `paused` on every entry: true for each return of a household
        // paused for two open years. The scenario "paused" pauses Okafor Family, which has no other work.
        paused: scenario === "paused" && owner.name === "Okafor Family",
      };
    });
    // Each file's key is that of the copy `state` names for it; the reply's
    // `paths` holds the path of every key some file carries (ruling 15), and
    // a file with no copy has the key "".
    const files = engagements.filter((e) => e.year === 2025).flatMap((e) => filesOf(bodies[e.path]).map((x) => {
      let open_key = "";
      if (x.kind === "moved") {
        open_key = keyOf("moved_copy", handleOf(x));
        paths[open_key] = copyPath(e.path, "Prepared/Elsewhere", x.name);
      } else if (x.copy !== false && (x.bucket || "document") !== "container") {
        open_key = keyOf(x.review ? "review_copy" : "shown_copy", handleOf(x));
        paths[open_key] = copyPath(e.path, "Prepared/_Review", x.name);
      }
      return {
        return: e.path, year: e.year, name: x.name, handle: handleOf(x), code: x.kind === "moved" ? "file-moved" : CODE[x.status], received: dayOf(x.date),
        suggestion: (x.suggest || [])[0] || "", open_key,
      };
    }));
    const totals = {
      need: returns.filter((r) => r.counts.needs_you).length,
      waiting: returns.filter((r) => !r.counts.needs_you && r.counts.waiting).length,
      complete: returns.filter((r) => !r.counts.needs_you && !r.counts.waiting).length,
      files: returns.reduce((n, r) => n + r.files, 0),
      drafts: returns.filter((r) => r.draft.ready).length,
    };
    return { returns, files, totals, paths, next_sort: "18:00" };
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
    misfits: [{ path: "x", where: "Clients/Old Files", sentence: "Not a household.", code: "not_a_tree" }, { path: "y", where: "Clients/Scans", sentence: "Not a household.", code: "no_return" }, { path: "z", where: "Clients/Misc", sentence: "Not a household.", code: "bad_name" },
      // The one code the vocabulary has no word for: the page must draw the name alone (the engine never sends one; the registry test sees to that).
      { path: "w", where: "Clients/Loose", sentence: "Not a household.", code: "unwritten_code" }],
  } : {};

  // ── the writes the side sheet makes: they change the made-up return ───
  // A file leaves Needs you; the reply carries the state and the sentences
  // the page reads. Nothing here is a rule of the engine.
  function takeFile(path, handle) {
    const body = bodies[path];
    const at = body.needs.findIndex((one) => one.kind !== "request" && handleOf(one) === handle);
    return at === -1 ? null : body.needs.splice(at, 1)[0];
  }
  function write(command, path, payload) {
    const body = bodies[path];
    if (command === "assign") {
      const one = takeFile(path, payload.original);
      if (!one) return null;
      body.received.push(request(`Filed ${payload.identifier}`, one.name, LB("Received"), "Mar 7"));
      return { state: stateOf(path), assigned: { original_name: one.name, filed_as: payload.identifier, identifier: payload.identifier, keyword: "", keyword_note: "", spelling: "", spelling_note: "", left_in_review: "", overrode_shortlist: "", scan_note: "" } };
    }
    if (command === "dismiss") {
      const one = takeFile(path, payload.original);
      if (!one) return null;
      // The engine rewrites the same index row: the handle stays, the record version moves on (F1).
      body.setAside.push(file(one.name, "", ASIDE, "Mar 7", { copy: one.copy, id: one.id, seq: (one.seq || 1) + 1 }));
      return { state: stateOf(path), dismissed: { original_name: one.name, decision: vocab.decisions.dismissed, reason: ASIDE } };
    }
    if (command === "restore") {
      const one = takeFile(path, payload.original);
      if (!one) return null;
      body.received.push(request(`Put back ${one.name}`, one.name, LB("Received"), "Mar 7"));
      return { state: stateOf(path), restored: { original_name: one.name, decision: vocab.decisions.filed, reason: "", parked_as: "", scan_note: "" } };
    }
    if (command === "unfile") {
      // The made-up return keeps its rows; the reply is the engine's shape, and the payload (with its note) is what the harness checks.
      const one = stateOf(path).index.find((row) => row.handle === payload.original);
      if (!one) return null;
      return { state: stateOf(path), unfiled: { original_name: one.original_name, decision: vocab.decisions.needs_review, reason: "", prepared_location: "", moved_working_copy: false, left_filed: "", scan_note: "" } };
    }
    if (command === "approve") {
      approved[path] = { date: "2026-03-07", stage: payload.stage };
      return { reminder: reminderReply(body, path, payload.stage).reminder, set_aside: "" };
    }
    return null;
  }

  window.HARNESS = { scenario, bodies, households, engagements, calls, menuLog: [], opened: [], logged: [], writes: [] };
  window.tracker = {
    call: async (args, payload) => {
      calls.push(args[0]);
      const command = args[0];
      if (command === "list") {
        const base = { engagements: rootSet ? engagements : [], households: rootSet ? households.map(({ rollYear, ...sent }) => sent) : [], misfits: loud.misfits || [], root: rootSet ? ROOT : "", needs_root: !rootSet, vocab,
          reader_warning: loud.reader_warning || "", last_pass: lastPass, after_install: loud.after_install || null, machine_warnings: loud.machine_warnings || [] };
        if (rootSet) base.paths = { clients_root: ROOT, status: `${ROOT}/status.html` };
        return wait(20, base);
      }
      if (command === "firm") {
        if (scenario === "firm-fails") return wait(20, { error: "The counts could not be read.", failure: { sentence: "The counts could not be read.", kind: "failed" } });
        return wait(scenario === "slow" ? 1500 : 30, firm());
      }
      if (command === "state") {
        if (scenario === "state-fails" && calls.filter((c) => c === "state").length > 0) return wait(20, { error: "The return could not be read.", failure: { sentence: "The return could not be read.", kind: "failed" } });
        return wait(scenario === "slow-state" ? 600 : 20, stateOf(args[args.length - 1]));
      }
      if (command === "reminder") return wait(10, reminderReply(bodies[args[args.length - 1]], args[args.length - 1], payload && payload.stage));
      if (["assign", "dismiss", "restore", "unfile", "approve"].indexOf(command) !== -1) {
        window.HARNESS.writes.push({ command, payload });
        const path = args[args.length - 1];
        const reply = write(command, path, payload);
        if (reply) return wait(20, reply);
        return wait(10, { error: "The row is no longer there.", failure: { sentence: "The row is no longer there.", kind: "failed" } });
      }
      if (command === "templates") return wait(10, { forms: [{ id: "1040", label: "1040", who: "Individual", blurb: "" }], templates: { 1040: [] }, default_year: 2026 });
      if (command === "pilot-record") return wait(10, { terms: "1", tour_seen: true });
      if (command === "set-root") {
        rootSet = true;
        return wait(50, { root: ROOT, settings_path: "", after_install: { schedule_sentence: "", failed: [], findings: [] }, short_of_room: [] });
      }
      return wait(10, { error: "The harness does not answer this.", failure: { sentence: "The harness does not answer this.", kind: "failed" } });
    },
    // `how` is the second argument the joined shell's open takes ("reveal"); the
    // harness records both and answers "" (opened) unless a scenario says the
    // copy has changed.
    open: async (path, how) => {
      window.HARNESS.opened.push(how ? [path, how] : path);
      return scenario === "changed-copy" ? vocab.shell.not_opened : "";
    },
    pickFolder: async () => "/clients/Client Files",
    logError: (text) => window.HARNESS.logged.push(text),
    onProgress: () => {},
    onAfterInstallDone: null,
    menu: {
      onCommand: (listener) => { window.HARNESS.menuListener = listener; },
      send: (message) => {
        if (scenario === "menu-throws") throw new Error("menu channel closed");
        window.HARNESS.menuLog.push(message);
      },
    },
  };
})();
