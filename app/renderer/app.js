// Renderer logic — renders tracker state; every action round-trips through
// the Python API so the UI can never disagree with the real scanner.

let paths = null;          // paths of the active engagement
let engagements = [];      // [{name, path}]
let active = null;         // path of the active engagement
let forms = [];            // tax form catalog [{id, label, who, blurb}]
let templatesByForm = {};  // form id -> tailored request template items
let defaultYear = null;    // the tax year a new engagement is for (from the calendar)
let nameIsAuto = true;     // new-client name follows client + year + form until typed
let selectedForm = null;   // form id chosen on the wizard's first page
let templates = [];        // template items for the chosen form
let customItems = [];      // custom rows added in the wizard
let priors = [];           // engagements a new year can roll forward from
let selectedPrior = null;  // path of the prior engagement chosen on page 0

const $ = (id) => document.getElementById(id);

// Every word the app compares or shows comes from the API's vocabulary
// (tracker.api._vocab): statuses, overrides, decisions, defaults, patterns.
// Nothing here is typed twice; the CSS classes are derived from the keys.
let vocab = null;

function statusKey(status) {
  const entry = vocab.statuses.find((s) => s.value === status);
  return entry ? entry.key : vocab.unscanned_key;
}

// Every piece of the page is built from API data as DOM nodes, never as an
// HTML string: a client's file name, a keyword somebody typed into the
// request list or a folder name is text, whatever characters it contains.
// `el` is the one builder.
function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === undefined || value === null || value === false) continue;
    if (key === "className") node.className = value;
    else if (key === "dataset") Object.assign(node.dataset, value);
    else if (typeof value === "boolean") node[key] = value;   // checked, selected, disabled
    else node.setAttribute(key, value);
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : String(child));
  }
  return node;
}

function show(id, nodes) {
  $(id).replaceChildren(...nodes);
}

function chip(status, override) {
  if (override === vocab.overrides.waived) {
    return el("span", { className: `chip chip-${vocab.unscanned_key}` }, vocab.overrides.waived);
  }
  const label = status || vocab.unscanned_label;
  return el("span", { className: `chip chip-${statusKey(status)}` }, label);
}

function fill(pattern, values) {
  return pattern.replace(/\{(\w+)\}/g, (_, key) => values[key] ?? "");
}

// The one button label the app owns; the docs that name it are pinned to it.
const SCAN_LABEL = "Sort & Scan";

function toast(msg) {
  const el = $("toast");
  el.textContent = msg;
  el.classList.remove("hidden");
  clearTimeout(el._t);
  el._t = setTimeout(() => el.classList.add("hidden"), 6000);
}

async function call(args, payload) {
  const result = await window.tracker.call(args, payload);
  if (result.error) throw new Error(result.error);
  return result;
}

const withEng = (cmd) => (active ? [cmd, vocab.engagement_flag, active] : [cmd]);

// ── rendering ───────────────────────────────────────────────────────────

function ruleTooltip(item) {
  const rules = [];
  if (item.allowed_extensions.length) rules.push(`Types: ${item.allowed_extensions.join(", ")}`);
  if (item.required_keywords.length) rules.push(`Must contain: ${item.required_keywords.join(", ")}`);
  if (item.any_keywords.length) rules.push(`Any of: ${item.any_keywords.join(", ")}`);
  if (item.expected_count > 1) rules.push(fill(vocab.expected_pattern, { n: item.expected_count }));
  return rules.join("  ·  ") || "No content rules";
}

function render(state) {
  paths = state.paths;

  show("rows", state.items.map((item) =>
    el("tr", { title: ruleTooltip(item) },
      el("td", { className: "col-id" }, el("span", { className: "req-id" }, item.identifier)),
      el("td", {},
        el("div", { className: "req-doc" }, item.document),
        el("div", { className: "req-period" },
          item.period, item.manual_override ? ` · override: ${item.manual_override}` : ""),
      ),
      el("td", { className: "col-num" },
        `${item.file_count ?? "–"}${item.expected_count > 1 ? ` / ${item.expected_count}` : ""}`),
      el("td", { className: "col-status" }, chip(item.status, item.manual_override)),
      el("td", { className: "col-recv" }, el("span", { className: "req-recv" }, item.received_date || "—")),
      el("td", {}, el("div", { className: "req-notes", title: item.validation_notes || "" },
        item.validation_notes || "—")),
    )));

  // The one count, from the same summarize() the run log and the reminder use.
  // Nothing waits for Excel any more: the statuses are in the record
  // (decision 103), and the request list is the person's file alone.
  $("summary").textContent = state.summary ? state.summary.line : "";

  // The catalog the engagement was cut from, beside its name in the
  // toolbar. It is shown exactly as the sheet records it — the catalog's
  // own key is how a person names the return — so the app carries no word
  // of its own for it, and an engagement made before it was recorded shows
  // nothing rather than a guess.
  const engForm = state.engagement ? state.engagement.form : "";
  $("eng-form").textContent = engForm;
  $("eng-form").classList.toggle("hidden", !engForm);

  // The engagement's own page beside it: current, behind, or unknown.
  // Both the label and the word are the API's — the page compares nothing
  // and names no state — and the class is derived from the word, the same
  // way a status chip's is.
  const viewState = state.view ? state.view.state : "";
  const chipEl = $("view-state");
  chipEl.textContent = viewState ? `${vocab.view.label}: ${viewState}` : "";
  chipEl.className = `eng-form view-${viewState}`;
  chipEl.classList.toggle("hidden", !viewState);

  renderReview(state);
  renderUnfileList(state);
  renderLock(state);
}

// ── Needs review: a person's decision, carried out by the filer ──────────

function renderReview(state) {
  const rows = state.index || [];
  const parked = rows.filter((e) => e.decision === vocab.decisions.needs_review);
  // A document a person said nothing asks for keeps its copy and its row;
  // it is out of the way, not gone, and filing it undoes the decision.
  const dismissed = rows.filter((e) => e.decision === vocab.decisions.dismissed);
  $("review-card").classList.toggle("hidden", parked.length === 0 && dismissed.length === 0);
  const choices = state.items.filter((i) => i.manual_override !== vocab.overrides.waived);
  const ids = new Set(state.items.map((i) => i.identifier));
  // The triage the API computed, by the same handle every review command
  // takes. Only a parked row has one; a set-aside row is not triaged.
  const triaged = new Map((state.review || []).map((t) => [t.pbc_location, t]));
  show("review-list", parked.map((e) =>
    reviewRow(e, choices, ids, true, triaged.get(e.pbc_location))));
  $("dismissed-card").classList.toggle("hidden", dismissed.length === 0);
  $("dismissed-heading").textContent =
    fill(vocab.review_labels.dismissed_heading, { n: dismissed.length });
  show("dismissed-list", dismissed.map((e) => reviewRow(e, choices, ids, false, null)));
}

// One entry of the picker: the identifier and the document, joined by the
// one separator a reason sentence uses between the same two things.
function requestOption(item, picked) {
  return el("option", { value: item.identifier, selected: item.identifier === picked },
    `${item.identifier}${vocab.triage.identifier_separator}${item.document}`);
}

// One row of the card. The question is the same whether the document is
// waiting or has been set aside - which request does this belong to - so it
// is asked the same way; only an open question offers the two boxes, the
// button that sets a document aside, and the shortlist.
//
// The shortlist is the picker's first entries, in the order the API ranked
// them, and the sentence behind each is listed beneath the row: an <option>
// can carry no second line, and the reason is the whole point - a person
// reads why before they pick. Everything below the divider is every other
// request, because a suggestion is a suggestion and nothing is taken away.
function reviewRow(e, choices, ids, open, triage) {
  const shortlist = (triage && triage.shortlist) || [];
  const suggested = shortlist.map((s) => s.identifier);
  const byId = new Map(choices.map((i) => [i.identifier, i]));
  const best = suggested.map((id) => byId.get(id)).filter(Boolean);
  const rest = choices.filter((i) => !suggested.includes(i.identifier));
  // The picker starts on the best suggestion; failing that, on the router's
  // own first candidate, which is what it started on before there was one.
  const guess = suggested[0] || (e.candidates || [])[0] || "";
  const picked = guess && ids.has(guess) ? guess : "";
  return el("li", { dataset: { original: e.pbc_location } },
    el("span", { className: "r-name" }, e.original_name),
    el("span", { className: "r-why" }, e.reason),
    el("select", { "aria-label": `Request for ${e.original_name}` },
      el("option", { value: "" }, "Belongs to…"),
      best.length
        ? [el("optgroup", { label: vocab.review_labels.suggested },
            best.map((i) => requestOption(i, picked))),
           el("optgroup", { label: vocab.review_labels.other_requests },
            rest.map((i) => requestOption(i, picked)))]
        : rest.map((i) => requestOption(i, picked)),
    ),
    open && el("ul", { className: "r-reasons" },
      shortlist.length
        ? shortlist.map((s) => el("li", {}, s.reason))
        : el("li", { className: "r-nothing" }, vocab.triage.nothing_suggested)),
    open && el("input", {
      type: "text", className: "r-keyword", placeholder: "keyword to learn (optional)",
      "aria-label": "Keyword to add to the request",
      title: "A word this document contains that others like it will too. Added to the request's Any Keywords so the next one files itself.",
    }),
    open && el("input", {
      type: "text", className: "r-note", placeholder: vocab.review_labels.dismiss_note,
      "aria-label": vocab.review_labels.dismiss_note,
    }),
    el("button", { className: "btn btn-primary r-file" },
      open ? vocab.review_labels.file : vocab.review_labels.file_anyway),
    open && el("button", { className: "btn r-dismiss" }, vocab.review_labels.dismiss),
  );
}

function typed(li, className) {
  const box = li.querySelector(className);
  return box ? box.value.trim() : "";
}

async function assignParked(li) {
  const identifier = li.querySelector("select").value;
  if (!identifier) {
    toast("Pick the request this document belongs to first.");
    return;
  }
  const btn = li.querySelector(".r-file");
  btn.disabled = true;
  try {
    const result = await call(withEng("assign"), {
      original: li.dataset.original,
      identifier,
      keyword: typed(li, ".r-keyword"),
    });
    render(result.state);
    const a = result.assigned;
    const notes = [`${a.original_name} filed as ${a.filed_as}`];
    if (a.keyword) notes.push(`"${a.keyword}" added to ${a.identifier} so the next one files itself`);
    if (a.keyword_note) notes.push(a.keyword_note);
    if (a.left_in_review) notes.push(a.left_in_review);
    if (a.scan_note) notes.push(a.scan_note);
    banner(notes.join(". ") + ".", a.keyword_note || a.left_in_review || a.scan_note ? "warn" : "ok");
  } catch (err) {
    toast(err.message);
    btn.disabled = false;
  }
}

// ── The way back, so nobody corrects a filing in Explorer ────────────────

// Folded away by default. It is a list of what is already right, there for
// the one row that is not, and the index is the only thing that knows where
// a working copy went: a correction made in Explorer is one it never learns.
// One original can have a copy in more than one request folder (a page that
// carried two forms), so each destination is named; Unfile still takes the
// one original, because the row is one row and every copy goes back with it.
function renderUnfileList(state) {
  const filed = (state.index || []).filter((e) => e.decision === vocab.decisions.filed);
  $("filed-card").classList.toggle("hidden", filed.length === 0);
  $("filed-heading").textContent = fill(vocab.review_labels.filed_heading, { n: filed.length });
  show("filed-list", filed.map((e) =>
    el("li", { dataset: { original: e.pbc_location } },
      el("span", { className: "r-name" }, e.original_name),
      el("span", { className: "r-why" }, `${e.identifier} — ${e.filed_names.join(", ")}`),
      el("input", {
        type: "text", className: "r-note", placeholder: vocab.review_labels.unfile_note,
        "aria-label": vocab.review_labels.unfile_note,
      }),
      el("button", { className: "btn r-unfile" }, vocab.review_labels.unfile),
    )));
}

// Nothing is deleted and nothing is moved: the row is rewritten, so the
// banner says what the row now reads and the file is still where it was.
async function dismissParked(li) {
  const btn = li.querySelector(".r-dismiss");
  btn.disabled = true;
  try {
    const result = await call(withEng("dismiss"), {
      original: li.dataset.original,
      note: typed(li, ".r-note"),
    });
    render(result.state);
    const d = result.dismissed;
    const notes = [`${d.original_name}: ${d.decision}`, d.reason];
    banner(notes.join(". ") + ".", "ok");
  } catch (err) {
    toast(err.message);
    btn.disabled = false;
  }
}

// The copy goes back under the client's own name and the request reverts in
// the same breath, so the banner says where the document is now, not what
// it stopped being.
async function unfileDocument(li) {
  const btn = li.querySelector(".r-unfile");
  btn.disabled = true;
  try {
    const result = await call(withEng("unfile"), {
      original: li.dataset.original,
      note: typed(li, ".r-note"),
    });
    render(result.state);
    const u = result.unfiled;
    const notes = [`${u.original_name}: ${u.decision}`];
    if (u.left_filed) notes.push(u.left_filed);
    if (u.scan_note) notes.push(u.scan_note);
    banner(notes.join(". ") + ".", u.left_filed || u.scan_note ? "warn" : "ok");
  } catch (err) {
    toast(err.message);
    btn.disabled = false;
  }
}

function renderEngagements() {
  show("eng-select", engagements.map((e) =>
    el("option", { value: e.path, selected: e.path === active }, e.name)));
}

function banner(text, cls) {
  const el = $("banner");
  el.textContent = text;
  el.className = `banner ${cls}${text.includes("\n") ? " multi" : ""}`;
}

// ── the engagement lock, shown instead of left as a mystery file ─────────

function renderLock(state) {
  const lock = state.lock;
  const notice = $("lock-notice");
  notice.classList.toggle("hidden", !lock);
  if (!lock) return;
  const since = lock.started ? ` started at ${lock.started.replace("T", " ").slice(0, 16)}` : "";
  if (lock.stale) {
    $("lock-text").textContent =
      `A run${since} left its lock behind (${lock.age_minutes} min old) — it has most likely died. The next ${SCAN_LABEL} or scheduled pass will replace it; clear it here to tidy up now.`;
    notice.className = "banner warn";
    $("btn-unlock").classList.remove("hidden");
  } else {
    $("lock-text").textContent =
      `A run${since} is still going (${lock.age_minutes} min). ${SCAN_LABEL} will wait for it; a lock older than ${lock.stale_after_minutes} minutes can be cleared here.`;
    notice.className = "banner ok";
    $("btn-unlock").classList.add("hidden");
  }
}

async function clearLock() {
  const btn = $("btn-unlock");
  btn.disabled = true;
  try {
    const result = await call(withEng("unlock"));
    render(result.state);
    banner(`Stale lock cleared (${result.age_minutes} min old). Run ${SCAN_LABEL} when ready.`, "ok");
  } catch (err) {
    toast(err.message);
  } finally {
    btn.disabled = false;
  }
}

async function checkManifest() {
  const btn = $("btn-check");
  btn.disabled = true;
  try {
    const result = await call(withEng("check"));
    if (!result.ok) {
      banner(`The manifest cannot be used until this is fixed:\n${result.problems.map((p) => "• " + p).join("\n")}`, "err");
    } else if (result.warnings.length) {
      banner(`The manifest is valid. Worth a look:\n${result.warnings.map((w) => "• " + w).join("\n")}`, "warn");
    } else {
      banner("The manifest is valid: every row has a rule the filer can act on.", "ok");
    }
  } catch (err) {
    toast(err.message);
  } finally {
    btn.disabled = false;
  }
}

// ── data flows ──────────────────────────────────────────────────────────

// Everything static on the page that names a Python-owned fact is filled
// here, once, from the vocabulary: the product, the rules, the folder the
// originals go to, the year bounds, the example root, the button label.
function applyVocabulary() {
  document.title = vocab.firm ? `${vocab.product} — ${vocab.firm}` : vocab.product;
  $("brand-product").textContent = vocab.product;
  $("scan-label").textContent = SCAN_LABEL;
  $("view-label").textContent = vocab.view.open;
  $("root-input").placeholder = `e.g. ${vocab.example_root}`;
  $("ro-include-note").textContent =
    `Also add checklist rows this client has never had (otherwise they are listed as offers on the ${vocab.carried_sheet} sheet)`;
  for (const id of ["ro-year", "ne-year"]) {
    $(id).min = vocab.year_min;
    $(id).max = vocab.year_max;
    $(id).title = vocab.year_note;
  }
  $("ro-client").placeholder = vocab.origin_prior;
  $("cu-ext").title = vocab.extension_default_note;
  $("cu-kw").title = `A word the document itself contains, e.g. 'Schedule E'. Keyword ${vocab.keyword_default_note}; shorten it to something the file really says.`;
  const cards = document.querySelectorAll("#assurances .assure div");
  vocab.rules.forEach((rule, i) => {
    if (!cards[i]) return;
    cards[i].querySelector("strong").textContent = rule.headline;
    cards[i].querySelector("span").textContent = rule.detail;
  });
}

let clientsRoot = "";      // the one folder every engagement sits under

async function loadEngagements(preferPath) {
  const listed = await call(["list"]);
  vocab = listed.vocab;
  applyVocabulary();
  engagements = listed.engagements;
  clientsRoot = listed.root || "";
  $("setup-card").classList.toggle("hidden", !listed.needs_root);
  if (listed.needs_root) {
    $("root-input").value = clientsRoot;
    $("firm-input").value = vocab.firm || "";
    $("setup-note").textContent = clientsRoot
      ? `${clientsRoot} is not a folder any more. Point the app at the right one.`
      : "The scheduled job walks this same folder, so this is the only place it is set.";
    return false;
  }
  if (!engagements.length) return false;
  active =
    (preferPath && engagements.find((e) => e.path === preferPath)?.path) ||
    (active && engagements.find((e) => e.path === active)?.path) ||
    engagements[0].path;
  renderEngagements();
  return true;
}

async function refresh(preferPath) {
  try {
    if (!(await loadEngagements(preferPath))) {
      if (!$("setup-card").classList.contains("hidden")) return;   // waiting for the folder
      banner(`No engagements under ${clientsRoot} yet — click ${$("btn-new").textContent.trim()} to create the first.`, "ok");
      show("rows", []);
      return;
    }
    render(await call(withEng("state")));
  } catch (err) {
    toast(err.message);
  }
}

async function saveRoot() {
  const btn = $("btn-save-root");
  btn.disabled = true;
  try {
    const result = await call(["set-root"], {
      root: $("root-input").value.trim(),
      firm: $("firm-input").value.trim(),
    });
    banner(`Clients folder set to ${result.root} (written to ${result.settings_path}).`, "ok");
    await refresh();
  } catch (err) {
    toast(err.message);
  } finally {
    btn.disabled = false;
  }
}

async function installSchedule() {
  const sched = vocab.schedule;
  if (!confirm(`Register the daily job with Task Scheduler for this clients folder?\n\nIt files, scans and (on ${sched.draft_day}s) drafts reminders. Nothing is ever sent.`)) return;
  const btn = $("btn-schedule");
  btn.disabled = true;
  try {
    const result = await call(["install-schedule"], {});
    if (result.installed) {
      banner(`Scheduled: every day from ${result.start}, repeating every ${result.every} minutes, over ${result.root}. Re-run this to change it.`, "ok");
    } else {
      banner(`Not Windows here. On the scheduling machine run:  ${result.command.join(" ")}`, "warn");
    }
  } catch (err) {
    toast(err.message);
  } finally {
    btn.disabled = false;
  }
}

async function runScan() {
  const btn = $("btn-scan");
  btn.disabled = true;
  btn.classList.add("spinning");
  $("scan-label").textContent = "Scanning…";
  try {
    const result = await call(withEng("scan"));
    render(result.state);
    const run = result.run;
    const summary = result.state.summary ? result.state.summary.line : "";
    if (run.skipped) {
      banner(`Nothing done: ${run.skipped}.`, "warn");
      return;
    }
    if (run.error) {
      banner(`The pass reported a problem: ${run.error}`, "err");
      return;
    }
    const did = [`filed ${run.filed}`];
    if (run.review) did.push(`${run.review} to review`);
    if (run.waiting) did.push(`${run.waiting} still syncing`);
    const problems = [];
    if (run.file_errors.length) problems.push(`${run.file_errors.length} file(s) could not be sorted`);
    const lines = [`Pass complete — ${did.join(", ")}.   ${summary}`];
    if (problems.length) lines.push(`But ${problems.join("; ")}.`);
    for (const w of run.warnings) lines.push(`• ${w}`);
    banner(lines.join("\n"), problems.length ? "warn" : run.warnings.length ? "warn" : "ok");
  } catch (err) {
    toast(err.message);
  } finally {
    btn.disabled = false;
    btn.classList.remove("spinning");
    $("scan-label").textContent = SCAN_LABEL;
  }
}

// ── New Engagement wizard ───────────────────────────────────────────────
// Opens on the returning-client page — rolling last year forward is the
// default action. Behind it: pick a tax form type, then trim its list.

async function openWizard() {
  try {
    if (!forms.length) {
      const result = await call(["templates"]);
      forms = result.forms;
      templatesByForm = result.templates;
      defaultYear = result.default_year || null;
    }
    priors = (await call(["priors"])).priors;
  } catch (err) {
    toast(err.message);
    return;
  }
  selectedForm = null;
  const open = priors.filter((p) => !p.superseded_by);
  selectedPrior = open.length ? open[open.length - 1].path : priors.length ? priors[priors.length - 1].path : null;
  renderPriorPage();
  renderFormGrid();
  showStep("prior");
  $("modal").classList.remove("hidden");
}

function showStep(step) {
  $("wiz-prior").classList.toggle("hidden", step !== "prior");
  $("wiz-form").classList.toggle("hidden", step !== "form");
  $("wiz-items").classList.toggle("hidden", step !== "items");
}

// ── page 0: returning client ────────────────────────────────────────────

function priorMeta(p) {
  const bits = [];
  if (p.superseded_by) bits.push(`already rolled forward into ${p.superseded_by}`);
  if (p.year) bits.push(fill(vocab.period_pattern, { year: p.year }));
  bits.push(`${p.requests} request${p.requests === 1 ? "" : "s"}`);
  if (p.requests) bits.push(`${p.received} received`);
  return bits.join(" · ");
}

function renderPriorPage() {
  show("prior-list", priors.map((p) =>
    el("label", { className: "prior-item" },
      el("input", { type: "radio", name: "prior", value: p.path, checked: p.path === selectedPrior }),
      el("span", { className: "prior-name" }, p.name),
      el("span", { className: "prior-meta" }, priorMeta(p)),
    )));
  $("prior-list").classList.toggle("hidden", priors.length === 0);
  $("prior-empty").classList.toggle("hidden", priors.length > 0);
  $("ro-create").disabled = priors.length === 0;

  show("ro-form", [
    el("option", { value: "" }, "No template — carry last year's list as it is"),
    forms.map((f) => el("option", { value: f.id }, `${f.label} · ${f.who}`)),
  ]);
  syncPriorDefaults();
}

function syncPriorDefaults() {
  const prior = priors.find((p) => p.path === selectedPrior);
  const year = prior && prior.next_year ? prior.next_year : "";
  $("ro-year").value = year;
  $("ro-name").value = "";
  $("ro-client").value = prior ? prior.client || "" : "";
  $("ro-link").value = "";
  $("ro-due").value = "";
  $("ro-name").placeholder = prior
    ? fill(vocab.rollover_name_pattern, { prior: prior.name, year: year || vocab.unknown_year_label })
    : "defaults to last year's name and the new year";
}

async function rollForward() {
  if (!selectedPrior) {
    toast("Pick the engagement to roll forward, or start from a form template.");
    return;
  }
  const btn = $("ro-create");
  btn.disabled = true;
  try {
    const result = await call(["rollover"], {
      prior: selectedPrior,
      name: $("ro-name").value.trim(),
      form: $("ro-form").value,
      year: Number($("ro-year").value) || null,
      include_new: $("ro-include-new").checked,
      client: $("ro-client").value.trim(),
      link: $("ro-link").value.trim(),
      due: $("ro-due").value,
    });
    $("modal").classList.add("hidden");
    await refresh(result.state.paths.engagement);
    const r = result.rollover;
    const parts = [`${r.carried.length} request(s) carried from ${r.prior}`];
    if (r.offered.length) parts.push(`${r.offered.length} template row(s) offered but not added — see the ${r.carried_sheet} sheet`);
    if (r.unfiled_last_year.length) parts.push(`${r.unfiled_last_year.length} file(s) sent last year were never filed — check the ${r.carried_sheet} sheet`);
    banner(`Engagement "${result.created}" rolled forward: ${parts.join("; ")}.`, "ok");
  } catch (err) {
    toast(err.message);
  } finally {
    btn.disabled = false;
  }
}

function renderFormGrid() {
  show("form-grid", forms.map((f) =>
    el("button", { className: "form-card", dataset: { form: f.id } },
      el("span", { className: "form-num" }, f.label),
      el("span", { className: "form-who" }, f.who),
      el("span", { className: "form-blurb" }, f.blurb),
    )));
}

function chooseForm(formId) {
  const form = forms.find((f) => f.id === formId);
  if (!form) return;
  selectedForm = formId;
  templates = templatesByForm[formId] || [];
  customItems = [];
  $("items-title").textContent = `New ${form.label} Engagement`;
  $("chosen-form").textContent = `${form.label} · ${form.who}`;
  $("tmpl-head-label").textContent = `${form.label} request list — tick what applies`;
  $("ne-name").value = "";
  nameIsAuto = true;
  $("cu-ext").placeholder = vocab.default_extensions;
  $("cu-kw").placeholder = vocab.keyword_default_note;
  $("ne-year").value = defaultYear || "";
  $("ne-name").placeholder = fill(vocab.name_pattern, { client: vocab.new_client_placeholder, year: $("ne-year").value, form: form.label });
  $("ne-client").value = "";
  $("ne-link").value = "";
  $("ne-due").value = "";
  renderTemplateList();
  renderCustomList();
  showStep("items");
  $("ne-client").focus();
}

// The engagement name is what the client, the year and the form already
// say. It follows the client field until the user types a name of their own.
function syncNameDefault() {
  if (!nameIsAuto) return;
  const client = $("ne-client").value.trim();
  const form = forms.find((f) => f.id === selectedForm);
  const year = Number($("ne-year").value) || defaultYear;
  $("ne-name").value = client
    ? fill(vocab.name_pattern, { client, year, form: form ? form.label : "" }).replace(/\s+/g, " ").trim()
    : "";
}

function templateSummary(t) {
  const bits = [];
  if (t.extensions) bits.push(t.extensions);
  if (t.required_keywords) bits.push(`must contain "${t.required_keywords}"`);
  if (t.any_keywords) bits.push(`any of: ${t.any_keywords}`);
  if (t.expected_count > 1) bits.push(fill(vocab.expected_pattern, { n: t.expected_count }));
  return bits.join(" · ");
}

function renderTemplateList() {
  show("tmpl-list", templates.map((t, i) =>
    el("label", { className: "tmpl-item" },
      el("input", { type: "checkbox", dataset: { index: String(i) }, checked: Boolean(t.core) }),
      el("span", { className: "tmpl-id" }, t.identifier),
      el("span", { className: "tmpl-doc" }, t.document, " ",
        el("span", { className: "tmpl-rules" }, templateSummary(t))),
    )));
}

function renderCustomList() {
  show("cu-list", customItems.map((c, i) =>
    el("li", {},
      el("span", { className: "tmpl-id" }, c.identifier),
      el("span", {}, c.document, " ",
        el("span", { className: "tmpl-rules" },
          `${c.extensions || vocab.extension_default_note} · `,
          c.required_keywords ? `must contain "${c.required_keywords}"` : `keyword ${vocab.keyword_default_note}`)),
      el("button", { className: "cu-remove", dataset: { index: String(i) }, "aria-label": `Remove ${c.document}` }, "✕"),
    )));
}

// Blank fields are sent blank: the catalog's item_from_spec() fills the
// file types and the keyword (the document name) by the one rule, and the
// manifest shows the result. The placeholders say what that rule does.
function customIdentifier(position) {
  return `X${String(position).padStart(2, "0")}`;
}

function addCustomItem() {
  const doc = $("cu-doc").value.trim();
  if (!doc) {
    toast("Give the custom request a document name first.");
    return;
  }
  customItems.push({
    identifier: customIdentifier(customItems.length + 1),
    document: doc,
    extensions: $("cu-ext").value.trim(),
    required_keywords: $("cu-kw").value.trim(),
  });
  $("cu-doc").value = "";
  $("cu-kw").value = "";
  renderCustomList();
}

async function createEngagement() {
  const checked = [...$("tmpl-list").querySelectorAll("input:checked")]
    .map((box) => templates[Number(box.dataset.index)]);
  const items = [...checked, ...customItems];
  if (!items.length) {
    toast("Select at least one request item.");
    return;
  }
  const btn = $("ne-create");
  btn.disabled = true;
  try {
    const result = await call(["create"], {
      name: $("ne-name").value.trim(),
      form: selectedForm,
      items,
      client: $("ne-client").value.trim(),
      link: $("ne-link").value.trim(),
      due: $("ne-due").value,
      year: Number($("ne-year").value) || null,
    });
    $("modal").classList.add("hidden");
    await refresh(result.state.paths.engagement);
    banner(
      `Engagement "${result.created}" created — ${items.length} request folder(s) scaffolded, client README generated. Open the Client Folder to show it.`,
      "ok"
    );
  } catch (err) {
    toast(err.message);
  } finally {
    btn.disabled = false;
  }
}

// ── wiring ──────────────────────────────────────────────────────────────

$("btn-scan").addEventListener("click", runScan);
$("btn-new").addEventListener("click", openWizard);
$("btn-shared").addEventListener("click", () => paths && window.tracker.open(paths.shared));
$("btn-excel").addEventListener("click", () => paths && window.tracker.open(paths.manifest));
$("btn-view").addEventListener("click", () => paths && window.tracker.open(paths.view));
$("btn-status").addEventListener("click", () => paths && window.tracker.open(paths.status));
$("eng-select").addEventListener("change", (e) => {
  active = e.target.value;
  refresh(active);
});
$("form-grid").addEventListener("click", (e) => {
  const card = e.target.closest(".form-card");
  if (card) chooseForm(card.dataset.form);
});
$("wi-back").addEventListener("click", () => showStep("form"));
$("wf-back").addEventListener("click", () => showStep("prior"));
$("wf-cancel").addEventListener("click", () => $("modal").classList.add("hidden"));
$("wp-cancel").addEventListener("click", () => $("modal").classList.add("hidden"));
$("wp-new-client").addEventListener("click", () => showStep("form"));
$("prior-list").addEventListener("change", (e) => {
  if (e.target.name === "prior") {
    selectedPrior = e.target.value;
    syncPriorDefaults();
  }
});
$("ro-create").addEventListener("click", rollForward);
$("ro-name").addEventListener("keydown", (e) => e.key === "Enter" && rollForward());
$("btn-check").addEventListener("click", checkManifest);
$("btn-schedule").addEventListener("click", installSchedule);
$("btn-save-root").addEventListener("click", saveRoot);
$("root-input").addEventListener("keydown", (e) => e.key === "Enter" && saveRoot());
$("btn-browse").addEventListener("click", async () => {
  const picked = await window.tracker.pickFolder($("setup-title").textContent);
  if (picked) $("root-input").value = picked;
});
$("btn-unlock").addEventListener("click", clearLock);
$("ne-client").addEventListener("input", syncNameDefault);
$("ne-year").addEventListener("input", syncNameDefault);
$("ne-name").addEventListener("input", () => {
  nameIsAuto = $("ne-name").value.trim() === "";
  syncNameDefault();
});
$("cu-add").addEventListener("click", addCustomItem);
$("cu-doc").addEventListener("input", () => {
  $("cu-kw").placeholder = $("cu-doc").value.trim() || vocab.keyword_default_note;
});
$("cu-doc").addEventListener("keydown", (e) => e.key === "Enter" && addCustomItem());
$("ne-create").addEventListener("click", createEngagement);
$("ne-cancel").addEventListener("click", () => $("modal").classList.add("hidden"));
$("modal").addEventListener("click", (e) => {
  if (e.target === $("modal")) $("modal").classList.add("hidden");
});
$("review-list").addEventListener("click", (e) => {
  const file = e.target.closest(".r-file");
  if (file) assignParked(file.closest("li"));
  const dismiss = e.target.closest(".r-dismiss");
  if (dismiss) dismissParked(dismiss.closest("li"));
});
$("dismissed-list").addEventListener("click", (e) => {
  const btn = e.target.closest(".r-file");
  if (btn) assignParked(btn.closest("li"));
});
$("filed-list").addEventListener("click", (e) => {
  const btn = e.target.closest(".r-unfile");
  if (btn) unfileDocument(btn.closest("li"));
});
$("cu-list").addEventListener("click", (e) => {
  const btn = e.target.closest(".cu-remove");
  if (btn) {
    customItems.splice(Number(btn.dataset.index), 1);
    customItems.forEach((c, i) => (c.identifier = customIdentifier(i + 1)));
    renderCustomList();
  }
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") $("modal").classList.add("hidden");
});

refresh();
