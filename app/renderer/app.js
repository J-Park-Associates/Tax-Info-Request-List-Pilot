// Renderer logic — renders tracker state; every action round-trips through
// the Python API so the UI can never disagree with the real scanner.

let paths = null;          // paths of the active engagement
let engagements = [];      // [{name, path}]
let active = null;         // path of the active engagement
let forms = [];            // tax form catalog [{id, label, who, blurb}]
let templatesByForm = {};  // form id -> tailored request template items
let yearsByForm = {};      // form id -> tax year the template is written for
let nameIsAuto = true;     // new-client name follows client + year + form until typed
let selectedForm = null;   // form id chosen on the wizard's first page
let templates = [];        // template items for the chosen form
let customItems = [];      // custom rows added in the wizard
let priors = [];           // engagements a new year can roll forward from
let selectedPrior = null;  // path of the prior engagement chosen on page 0

const $ = (id) => document.getElementById(id);

const CHIP_CLASS = {
  "Received": "chip-received",
  "Partial": "chip-partial",
  "Failed Validation": "chip-failed",
  "Missing": "chip-missing",
  "Pending Sync": "chip-pending",
};

function chip(status) {
  const label = status || "Requested";
  const cls = CHIP_CLASS[status] || "chip-requested";
  return `<span class="chip ${cls}">${label}</span>`;
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"]/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])
  );
}

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

const withEng = (cmd) => (active ? [cmd, "--engagement", active] : [cmd]);

// ── rendering ───────────────────────────────────────────────────────────

function ruleTooltip(item) {
  const rules = [];
  if (item.allowed_extensions.length) rules.push(`Types: ${item.allowed_extensions.join(", ")}`);
  if (item.required_keywords.length) rules.push(`Must contain: ${item.required_keywords.join(", ")}`);
  if (item.any_keywords.length) rules.push(`Any of: ${item.any_keywords.join(", ")}`);
  if (item.expected_count > 1) rules.push(`${item.expected_count} files expected`);
  return rules.join("  ·  ") || "No content rules";
}

function render(state) {
  paths = state.paths;

  const rows = state.items.map((item) => `
    <tr title="${esc(ruleTooltip(item))}">
      <td class="col-id"><span class="req-id">${esc(item.identifier)}</span></td>
      <td>
        <div class="req-doc">${esc(item.document)}</div>
        <div class="req-period">${esc(item.period)}${item.manual_override ? " · override: " + esc(item.manual_override) : ""}</div>
      </td>
      <td class="col-num">${item.file_count ?? "–"}${item.expected_count > 1 ? " / " + item.expected_count : ""}</td>
      <td class="col-status">${chip(item.status)}</td>
      <td class="col-recv"><span class="req-recv">${esc(item.received_date || "—")}</span></td>
      <td><div class="req-notes" title="${esc(item.validation_notes)}">${esc(item.validation_notes) || "—"}</div></td>
    </tr>`);
  $("rows").innerHTML = rows.join("");

  const counts = {};
  for (const item of state.items) {
    const key = item.status || "Requested";
    counts[key] = (counts[key] || 0) + 1;
  }
  const summary = Object.entries(counts).map(([k, n]) => `${k}: ${n}`);
  if (state.pending_statuses) {
    summary.push(`${state.pending_statuses} update(s) waiting for Excel to close`);
  }
  $("summary").textContent = summary.join("   ·   ");

  renderReview(state);
  renderLock(state);

  // Folders and loose files the scanner found that belong to no request.
  // Parked documents are handled above, from the index, where the person
  // can act on them.
  const unfiled = (state.unfiled || []).filter((e) => !String(e.kind).startsWith("needs review"));
  $("unfiled-card").classList.toggle("hidden", unfiled.length === 0);
  $("unfiled-list").innerHTML = unfiled.map((e) => `
    <li>
      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#b45309" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><path d="M12 9v4"/><path d="M12 17h.01"/></svg>
      <span class="u-name">${esc(e.name)}</span>
      <span class="u-kind">${esc(e.kind)}</span>
    </li>`).join("");
}

// ── Needs review: a person's decision, carried out by the filer ──────────

function renderReview(state) {
  const parked = (state.index || []).filter((e) => e.decision === "Needs Review");
  $("review-card").classList.toggle("hidden", parked.length === 0);
  const options = state.items
    .filter((i) => i.manual_override !== "Waived")
    .map((i) => `<option value="${esc(i.identifier)}">${esc(i.identifier)} — ${esc(i.document)}</option>`)
    .join("");
  $("review-list").innerHTML = parked.map((e) => `
    <li data-original="${esc(e.pbc_location)}">
      <span class="r-name">${esc(e.original_name)}</span>
      <span class="r-why">${esc(e.reason)}</span>
      <select aria-label="Request for ${esc(e.original_name)}">
        <option value="">Belongs to…</option>${options}
      </select>
      <input type="text" placeholder="keyword to learn (optional)" aria-label="Keyword to add to the request" title="A word this document contains that others like it will too. Added to the request's Any Keywords so the next one files itself." />
      <button class="btn btn-primary r-file">File it</button>
    </li>`).join("");
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
      keyword: li.querySelector("input").value.trim(),
    });
    render(result.state);
    const a = result.assigned;
    const notes = [`${a.original_name} filed as ${a.filed_as}`];
    if (a.keyword) notes.push(`"${a.keyword}" added to ${a.identifier} so the next one files itself`);
    if (a.keyword_note) notes.push(a.keyword_note);
    if (a.index_deferred) notes.push("the index is open in Excel — the row is saved beside it and merges on the next run");
    if (a.scan_note) notes.push(a.scan_note);
    banner(notes.join(". ") + ".", a.keyword_note || a.index_deferred || a.scan_note ? "warn" : "ok");
  } catch (err) {
    toast(err.message);
    btn.disabled = false;
  }
}

function renderEngagements() {
  const select = $("eng-select");
  select.innerHTML = engagements
    .map((e) => `<option value="${esc(e.path)}"${e.path === active ? " selected" : ""}>${esc(e.name)}</option>`)
    .join("");
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
      `A run${since} left its lock behind (${lock.age_minutes} min old) — it has most likely died. Nothing will sort or scan this engagement until the lock is cleared.`;
    notice.className = "banner warn";
    $("btn-unlock").classList.remove("hidden");
  } else {
    $("lock-text").textContent =
      `A run${since} is still going (${lock.age_minutes} min). Sort & Scan will wait for it; a lock older than an hour can be cleared here.`;
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
    banner(`Stale lock cleared (${result.age_minutes} min old). Run Sort & Scan when ready.`, "ok");
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

async function loadEngagements(preferPath) {
  engagements = (await call(["list"])).engagements;
  if (!engagements.length) return false;
  active =
    (preferPath && engagements.find((e) => e.path === preferPath)?.path) ||
    (active && engagements.find((e) => e.path === active)?.path) ||
    engagements[0].path;
  renderEngagements();
  return true;
}

let autoResetDone = false;

async function refresh(preferPath) {
  try {
    if (!(await loadEngagements(preferPath))) throw new Error("No demo data yet");
    render(await call(withEng("state")));
  } catch (err) {
    // First launch on a fresh machine: build the demo data automatically.
    if (!autoResetDone) {
      autoResetDone = true;
      try {
        await call(["reset"]);
        await loadEngagements();
        render(await call(withEng("state")));
        banner("Welcome — demo data built and ready.", "ok");
        return;
      } catch (resetErr) {
        toast(resetErr.message);
        return;
      }
    }
    toast(`${err.message} — click Reset Demo to build the demo data.`);
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
    const counts = {};
    for (const u of Object.values(result.updates)) counts[u.status] = (counts[u.status] || 0) + 1;
    const summary = Object.entries(counts).map(([k, n]) => `${k}: ${n}`).join("  ·  ");
    const sorted = result.sorted || {};
    const problems = [];
    if ((sorted.errors || []).length) {
      problems.push(`${sorted.errors.length} file(s) could not be sorted: ${sorted.errors.map((e) => e.name).join(", ")}`);
    }
    if (sorted.index_deferred) {
      problems.push("the index is open in Excel — new rows are saved beside it and will merge on the next scan");
    }
    if (!result.written) {
      problems.push("the manifest is open in Excel — updates saved to a sidecar and will merge on the next scan");
    }
    if (problems.length) {
      banner(`Scan complete, but ${problems.join("; ")}.   ${summary}`, "warn");
    } else {
      banner(`Scan complete — manifest updated.   ${summary}`, "ok");
    }
  } catch (err) {
    toast(err.message);
  } finally {
    btn.disabled = false;
    btn.classList.remove("spinning");
    $("scan-label").textContent = "Sort & Scan";
  }
}

async function resetDemo() {
  if (!confirm("Rebuild the demo from scratch?\n\nThis wipes ALL demo engagements (including ones you created) and regenerates the sample documents.")) return;
  const btn = $("btn-reset");
  btn.disabled = true;
  try {
    await call(["reset"]);
    active = null;
    await loadEngagements();
    render(await call(withEng("state")));
    banner("Demo reset — every request is waiting on the client again.", "ok");
  } catch (err) {
    toast(err.message);
  } finally {
    btn.disabled = false;
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
      yearsByForm = result.years || {};
    }
    priors = (await call(["priors"])).priors;
  } catch (err) {
    toast(err.message);
    return;
  }
  selectedForm = null;
  selectedPrior = priors.length ? priors[priors.length - 1].path : null;
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
  if (p.year) bits.push(`TY${p.year}`);
  bits.push(`${p.requests} request${p.requests === 1 ? "" : "s"}`);
  if (p.requests) bits.push(`${p.received} received`);
  return bits.join(" · ");
}

function renderPriorPage() {
  $("prior-list").innerHTML = priors.map((p) => `
    <label class="prior-item">
      <input type="radio" name="prior" value="${esc(p.path)}"${p.path === selectedPrior ? " checked" : ""} />
      <span class="prior-name">${esc(p.name)}</span>
      <span class="prior-meta">${esc(priorMeta(p))}</span>
    </label>`).join("");
  $("prior-list").classList.toggle("hidden", priors.length === 0);
  $("prior-empty").classList.toggle("hidden", priors.length > 0);
  $("ro-create").disabled = priors.length === 0;

  $("ro-form").innerHTML =
    `<option value="">No template — carry last year's list as it is</option>` +
    forms.map((f) => `<option value="${esc(f.id)}">${esc(f.label)} · ${esc(f.who)}</option>`).join("");
  syncPriorDefaults();
}

function syncPriorDefaults() {
  const prior = priors.find((p) => p.path === selectedPrior);
  const year = prior && prior.year ? prior.year + 1 : "";
  $("ro-year").value = year;
  $("ro-name").value = "";
  $("ro-client").value = prior ? prior.client || "" : "";
  $("ro-link").value = "";
  $("ro-due").value = "";
  $("ro-name").placeholder = prior
    ? `${prior.name} - ${year || "next year"}`
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
    if (r.offered.length) parts.push(`${r.offered.length} template row(s) offered but not added — see the Carried Forward sheet`);
    if (r.unfiled_last_year.length) parts.push(`${r.unfiled_last_year.length} file(s) sent last year were never filed — check the Carried Forward sheet`);
    banner(`Engagement "${result.created}" rolled forward: ${parts.join("; ")}.`, "ok");
  } catch (err) {
    toast(err.message);
  } finally {
    btn.disabled = false;
  }
}

function renderFormGrid() {
  $("form-grid").innerHTML = forms.map((f) => `
    <button class="form-card" data-form="${esc(f.id)}">
      <span class="form-num">${esc(f.label)}</span>
      <span class="form-who">${esc(f.who)}</span>
      <span class="form-blurb">${esc(f.blurb)}</span>
    </button>`).join("");
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
  $("ne-name").placeholder = `e.g. Smith Family TY${yearsByForm[formId] || ""} ${form.label}`;
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
  const year = yearsByForm[selectedForm];
  $("ne-name").value = client
    ? [client, year ? `TY${year}` : "", form ? form.label : ""].filter(Boolean).join(" ")
    : "";
}

function templateSummary(t) {
  const bits = [];
  if (t.extensions) bits.push(t.extensions);
  if (t.required_keywords) bits.push(`must contain "${t.required_keywords}"`);
  if (t.any_keywords) bits.push(`any of: ${t.any_keywords}`);
  if (t.expected_count > 1) bits.push(`${t.expected_count} files`);
  return bits.join(" · ");
}

function renderTemplateList() {
  $("tmpl-list").innerHTML = templates.map((t, i) => `
    <label class="tmpl-item">
      <input type="checkbox" data-index="${i}" ${t.core ? "checked" : ""} />
      <span class="tmpl-id">${esc(t.identifier)}</span>
      <span class="tmpl-doc">${esc(t.document)}
        <span class="tmpl-rules">${esc(templateSummary(t))}</span>
      </span>
    </label>`).join("");
}

function renderCustomList() {
  $("cu-list").innerHTML = customItems.map((c, i) => `
    <li>
      <span class="tmpl-id">${esc(c.identifier)}</span>
      <span>${esc(c.document)} <span class="tmpl-rules">${esc(c.extensions)}${c.required_keywords ? ` · must contain "${esc(c.required_keywords)}"` : ""}</span></span>
      <button class="cu-remove" data-index="${i}" aria-label="Remove ${esc(c.document)}">✕</button>
    </li>`).join("");
}

// The keyword field follows the document name until the user types their
// own. A request with no keyword can never auto-file, so the default is
// visible here and again in the manifest, never silent.
let keywordIsAuto = true;

function syncKeywordDefault() {
  if (keywordIsAuto) $("cu-kw").value = $("cu-doc").value.trim();
}

function addCustomItem() {
  const doc = $("cu-doc").value.trim();
  if (!doc) {
    toast("Give the custom request a document name first.");
    return;
  }
  customItems.push({
    identifier: `X${String(customItems.length + 1).padStart(2, "0")}`,
    document: doc,
    extensions: $("cu-ext").value.trim() || "pdf",
    required_keywords: $("cu-kw").value.trim() || doc,
  });
  $("cu-doc").value = "";
  $("cu-kw").value = "";
  keywordIsAuto = true;
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
$("btn-reset").addEventListener("click", resetDemo);
$("btn-new").addEventListener("click", openWizard);
$("btn-shared").addEventListener("click", () => paths && window.tracker.open(paths.shared));
$("btn-samples").addEventListener("click", () => paths && window.tracker.open(paths.samples));
$("btn-excel").addEventListener("click", () => paths && window.tracker.open(paths.manifest));
$("btn-index").addEventListener("click", () => paths && window.tracker.open(paths.index));
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
$("btn-unlock").addEventListener("click", clearLock);
$("ne-client").addEventListener("input", syncNameDefault);
$("ne-name").addEventListener("input", () => {
  nameIsAuto = $("ne-name").value.trim() === "";
  syncNameDefault();
});
$("cu-add").addEventListener("click", addCustomItem);
$("cu-doc").addEventListener("input", syncKeywordDefault);
$("cu-kw").addEventListener("input", () => {
  keywordIsAuto = $("cu-kw").value.trim() === "";
  syncKeywordDefault();
});
$("cu-doc").addEventListener("keydown", (e) => e.key === "Enter" && addCustomItem());
$("ne-create").addEventListener("click", createEngagement);
$("ne-cancel").addEventListener("click", () => $("modal").classList.add("hidden"));
$("modal").addEventListener("click", (e) => {
  if (e.target === $("modal")) $("modal").classList.add("hidden");
});
$("review-list").addEventListener("click", (e) => {
  const btn = e.target.closest(".r-file");
  if (btn) assignParked(btn.closest("li"));
});
$("cu-list").addEventListener("click", (e) => {
  const btn = e.target.closest(".cu-remove");
  if (btn) {
    customItems.splice(Number(btn.dataset.index), 1);
    customItems.forEach((c, i) => (c.identifier = `X${String(i + 1).padStart(2, "0")}`));
    renderCustomList();
  }
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") $("modal").classList.add("hidden");
});

refresh();
