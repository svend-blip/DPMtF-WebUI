/* ── 1. i18n loader ─────────────────────────────────── */
var labelMap = {};
var locale = "da-DK";

function loadLabels() {
  var metaLocale = document.querySelector("meta[name=locale]");
  if (metaLocale) locale = metaLocale.getAttribute("content") || locale;
  fetch("/api/ui-labels/main?locale=" + locale)
    .then(function (res) {
      if (!res.ok) throw new Error("HTTP " + res.status);
      return res.json();
    })
    .then(function (data) {
      labelMap = data.labels || data;
      document.querySelectorAll("[data-slot]").forEach(function (el) {
        var key = el.getAttribute("data-slot");
        if (labelMap[key]) el.textContent = labelMap[key];
      });
    })
    .catch(function (err) {
      console.warn("Failed to load labels:", err.message);
    });
}

/* ── 2. DOM helpers ─────────────────────────────────── */
function el(tag, className, text) {
  var e = document.createElement(tag);
  if (className) e.className = className;
  if (text !== undefined) e.textContent = text;
  return e;
}

function td(text, className) {
  var cell = document.createElement("td");
  cell.textContent = text;
  if (className) cell.className = className;
  return cell;
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function clear(el) {
  if (el) el.replaceChildren();
}

function lbl(key, fallback) {
  return labelMap[key] || fallback || key;
}

/* ── 3. Database Status ────────────────────────────── */
function loadDbStatus() {
  var container = document.getElementById("db-status-content");
  if (!container) return;
  clear(container);

  fetch("/api/health")
    .then(function (res) { return res.json(); })
    .then(function (data) {
      var card = el("div", "dpmtf-card");
      card.appendChild(el("p", null, (data.status || "unknown") + " — " +
        lbl("lbl_status_success", "Healthy")));
      container.appendChild(card);
    })
    .catch(function (err) {
      var card = el("div", "dpmtf-card");
      card.appendChild(el("p", "dpmtf-error",
        lbl("lbl_status_error_prefix", "Error: ") + escapeHtml(err.message)));
      container.appendChild(card);
    });
}

/* ── 4. Phase Status ───────────────────────────────── */
var showCompleted = true;

function loadPhaseStatus() {
  var container = document.getElementById("phase-status-content");
  if (!container) return;
  clear(container);

  fetch("/api/phase-status")
    .then(function (res) {
      if (!res.ok) throw new Error("HTTP " + res.status);
      return res.json();
    })
    .then(function (data) {
      var completed = data.completed || [];
      var next = data.next || [];
      var planned = data.planned || [];

      // Toggle bar (built after labels are loaded)
      var toggleBar = el("div", null);
      toggleBar.style.marginBottom = "10px";
      var toggleLabel = el("label", null);
      toggleLabel.style.cursor = "pointer";
      toggleLabel.style.color = "#8b949e";
      toggleLabel.style.fontSize = "0.85em";
      var toggleCheck = el("input", null);
      toggleCheck.type = "checkbox";
      toggleCheck.checked = showCompleted;
      toggleCheck.style.marginRight = "6px";
      toggleCheck.onchange = function () {
        showCompleted = this.checked;
        var card = document.getElementById("phase-completed-card");
        if (card) card.style.display = showCompleted ? "block" : "none";
      };
      toggleLabel.appendChild(toggleCheck);
      toggleLabel.appendChild(document.createTextNode(
        lbl("phase_status.show_completed", "Show completed phases")));
      toggleBar.appendChild(toggleLabel);
      container.appendChild(toggleBar);

      // Completed
      var compCard = el("div", "dpmtf-card");
      compCard.id = "phase-completed-card";
      if (!showCompleted) compCard.style.display = "none";
      compCard.appendChild(el("h3", null, lbl("lbl_status_completed", "Completed") + " (" + completed.length + ")"));
      if (completed.length) {
        var compList = el("ul", null);
        completed.forEach(function (p) {
          var li = el("li", null);
          li.textContent = p.phase_key + ": " + escapeHtml(p.phase_title);
          compList.appendChild(li);
        });
        compCard.appendChild(compList);
      } else {
        compCard.appendChild(el("p", "dpmtf-muted", lbl("lbl_status_no_data", "No data")));
      }
      container.appendChild(compCard);

      // Next
      var nextCard = el("div", "dpmtf-card");
      nextCard.appendChild(el("h3", null, lbl("lbl_status_next", "Next")));
      if (next.length) {
        var nextList = el("ul", null);
        next.forEach(function (p) {
          var li = el("li", null);
          li.textContent = p.phase_key + ": " + escapeHtml(p.phase_title);
          nextList.appendChild(li);
        });
        nextCard.appendChild(nextList);
      } else {
        nextCard.appendChild(el("p", "dpmtf-muted", lbl("lbl_status_no_data", "No data")));
      }
      container.appendChild(nextCard);

      // Planned
      var planCard = el("div", "dpmtf-card");
      planCard.appendChild(el("h3", null, lbl("lbl_status_planned", "Planned") + " (" + planned.length + ")"));
      if (planned.length) {
        var planList = el("ul", null);
        planned.forEach(function (p) {
          var li = el("li", null);
          li.textContent = p.phase_key + ": " + escapeHtml(p.phase_title);
          planList.appendChild(li);
        });
        planCard.appendChild(planList);
      } else {
        planCard.appendChild(el("p", "dpmtf-muted", lbl("lbl_status_no_data", "No data")));
      }
      container.appendChild(planCard);
    })
    .catch(function (err) {
      var card = el("div", "dpmtf-card");
      card.appendChild(el("p", "dpmtf-error",
        lbl("lbl_status_error_prefix", "Error: ") + escapeHtml(err.message)));
      container.appendChild(card);
    });
}

/* ── 5. Hitrate Panel ──────────────────────────────── */
function loadHitrates() {
  var container = document.getElementById("hitrate-content");
  if (!container) return;
  clear(container);

  var statusEl = el("span", "dpmtf-status");
  var refreshBtn = el("button", "dpmtf-btn");
  refreshBtn.textContent = lbl("lbl_btn_refresh", "Refresh");
  refreshBtn.onclick = loadHitrates;

  var headerRow = el("div", null);
  headerRow.appendChild(refreshBtn);
  headerRow.appendChild(statusEl);
  container.appendChild(headerRow);

  // ── Phase Hitrate table ────────────────────────────
  var table = el("table", "dpmtf-table");
  var thead = el("thead", null);
  var thr = el("tr", null);
  thr.appendChild(el("th", null, "Phase"));
  thr.appendChild(el("th", null, "Success Rate"));
  thr.appendChild(el("th", null, "Successful / Total"));
  thr.appendChild(el("th", null, "Last Run"));
  thead.appendChild(thr);
  table.appendChild(thead);
  var tbody = el("tbody", null);
  table.appendChild(tbody);
  container.appendChild(table);

  fetch("/api/prompt-hirates")
    .then(function (res) {
      if (!res.ok) throw new Error("HTTP " + res.status);
      return res.json();
    })
    .then(function (data) {
      clear(tbody);
      var hitrates = data.hitrates || [];
      if (!hitrates.length) {
        var row = el("tr", null);
        var cell = el("td", null, lbl("lbl_status_no_data", "No hitrate data yet."));
        cell.colSpan = 4;
        row.appendChild(cell);
        tbody.appendChild(row);
        statusEl.textContent = "0 " + (lbl("lbl_sequences", "phases") || "phases");
        return;
      }
      hitrates.forEach(function (h) {
        var row = el("tr", null);
        var pct = (h.rolling_success_rate * 100).toFixed(0);
        var rateClass = pct >= 80 ? "hitrate-good" : (pct >= 50 ? "hitrate-ok" : "hitrate-low");
        row.appendChild(td(h.phase_key));
        row.appendChild(td(pct + "%", rateClass));
        row.appendChild(td(h.successful_runs + " / " + h.total_runs));
        row.appendChild(td(h.last_run_timestamp ? new Date(h.last_run_timestamp).toLocaleString() : "-"));
        tbody.appendChild(row);
      });
      statusEl.textContent = hitrates.length + " " + (lbl("lbl_sequences", "phases") || "phases");
    })
    .catch(function (err) {
      clear(tbody);
      var row = el("tr", null);
      var cell = el("td", null, lbl("lbl_status_error_prefix", "Error: ") + escapeHtml(err.message));
      cell.colSpan = 4;
      row.appendChild(cell);
      tbody.appendChild(row);
    });

  // ── Implementation Patterns table ───────────────────
  var patHeading = el("h4", null, "Implementation Patterns");
  patHeading.style.marginTop = "20px";
  container.appendChild(patHeading);
  var patTable = el("table", "dpmtf-table");
  var patThead = el("thead", null);
  var patThr = el("tr", null);
  ["Pattern ID", "Files", "Constraints", "Success Rate", "Best Model", "Avg Dur", "Runs"].forEach(function (h) {
    patThr.appendChild(el("th", null, h));
  });
  patThead.appendChild(patThr);
  patTable.appendChild(patThead);
  var patTbody = el("tbody", null);
  patTable.appendChild(patTbody);
  container.appendChild(patTable);

  // Detail container for expanded pattern runs
  var detailDiv = el("div", null);
  detailDiv.id = "pattern-detail";
  detailDiv.style.display = "none";
  container.appendChild(detailDiv);

  fetch("/api/implementation-patterns")
    .then(function (res) {
      if (!res.ok) throw new Error("HTTP " + res.status);
      return res.json();
    })
    .then(function (data) {
      clear(patTbody);
      var patterns = data.patterns || [];
      if (!patterns.length) {
        var row = el("tr", null);
        var cell = el("td", null, lbl("lbl_status_no_data", "No patterns yet. Record runs with file_signature + constraint_set to create patterns."));
        cell.colSpan = 7;
        row.appendChild(cell);
        patTbody.appendChild(row);
        return;
      }
      patterns.forEach(function (p) {
        var row = el("tr", null);
        row.style.cursor = "pointer";
        row.onclick = function () { loadPatternRuns(p.pattern_id); };
        var pct = (p.rolling_success_rate * 100).toFixed(0);
        var rateClass = pct >= 80 ? "hitrate-good" : (pct >= 50 ? "hitrate-ok" : "hitrate-low");
        row.appendChild(td(p.pattern_id));
        row.appendChild(td(truncate(p.file_signature, 50)));
        row.appendChild(td(truncate(p.constraint_set, 40)));
        row.appendChild(td(pct + "%", rateClass));
        row.appendChild(td(p.best_model || "-"));
        row.appendChild(td(p.avg_duration_seconds ? p.avg_duration_seconds + "s" : "-"));
        row.appendChild(td(p.successful_runs + " / " + p.total_runs));
        patTbody.appendChild(row);
      });
    })
    .catch(function (err) {
      clear(patTbody);
      var row = el("tr", null);
      var cell = el("td", null, lbl("lbl_status_error_prefix", "Error: ") + escapeHtml(err.message));
      cell.colSpan = 7;
      row.appendChild(cell);
      patTbody.appendChild(row);
    });

  // ── Recent runs (expandable) ────────────────────────
  var details = el("details", "dpmtf-details");
  var summary = el("summary", null, "Recent Prompt Runs");
  details.appendChild(summary);
  var runsTable = el("table", "dpmtf-table");
  var runsThead = el("thead", null);
  var runsThr = el("tr", null);
  ["Run ID", "Phase", "Project", "Success", "Duration", "Model", "Type", "Tokens", "Cost", "Timestamp"].forEach(function (h) {
    runsThr.appendChild(el("th", null, h));
  });
  runsThead.appendChild(runsThr);
  runsTable.appendChild(runsThead);
  var runsTbody = el("tbody", null);
  runsTable.appendChild(runsTbody);
  details.appendChild(runsTable);
  container.appendChild(details);

  fetch("/api/prompt-runs?limit=20")
    .then(function (res) {
      if (!res.ok) throw new Error("HTTP " + res.status);
      return res.json();
    })
    .then(function (data) {
      clear(runsTbody);
      var runs = data.runs || [];
      if (!runs.length) {
        var row = el("tr", null);
        var cell = el("td", null, lbl("lbl_status_no_data", "No prompt runs recorded yet."));
        cell.colSpan = 10;
        row.appendChild(cell);
        runsTbody.appendChild(row);
        return;
      }
      runs.forEach(function (r) {
        var row = el("tr", null);
        row.appendChild(td(r.run_id));
        row.appendChild(td(r.phase_key));
        row.appendChild(td(r.target_project));
        row.appendChild(td(r.success ? "✓" : "✗", r.success ? "hitrate-good" : "hitrate-low"));
        row.appendChild(td(r.duration_seconds != null ? r.duration_seconds + "s" : "-"));
        row.appendChild(td(r.model_used || "-"));
        // Model type badge
        var typeCell = el("td", null);
        if (r.model_type) {
          var badge = el("span", r.model_type === "cloud" ? "model-badge-cloud" : "model-badge-local");
          badge.textContent = r.model_type;
          typeCell.appendChild(badge);
        } else {
          typeCell.textContent = "-";
        }
        row.appendChild(typeCell);
        // Tokens (cloud only)
        if (r.token_count_input || r.token_count_output) {
          row.appendChild(td(formatTokens(r.token_count_input) + " in / " + formatTokens(r.token_count_output) + " out"));
        } else {
          row.appendChild(td("-"));
        }
        // Cost (cloud only)
        if (r.token_cost_eur != null || r.token_cost_dkk != null) {
          var costStr = "";
          if (r.token_cost_eur != null) costStr += "€" + r.token_cost_eur.toFixed(2);
          if (r.token_cost_dkk != null) costStr += (costStr ? " / " : "") + r.token_cost_dkk.toFixed(2) + " DKK";
          row.appendChild(td(costStr || "-"));
        } else {
          row.appendChild(td("-"));
        }
        row.appendChild(td(r.run_timestamp ? new Date(r.run_timestamp).toLocaleString() : "-"));
        runsTbody.appendChild(row);
      });
    })
    .catch(function (err) {
      clear(runsTbody);
      var row = el("tr", null);
      var cell = el("td", null, lbl("lbl_status_error_prefix", "Error: ") + escapeHtml(err.message));
      cell.colSpan = 10;
      row.appendChild(cell);
      runsTbody.appendChild(row);
    });
}

function loadPatternRuns(patternId) {
  var detailDiv = document.getElementById("pattern-detail");
  if (!detailDiv) return;
  detailDiv.style.display = "block";
  clear(detailDiv);

  var heading = el("h4", null, "Runs for " + patternId);
  detailDiv.appendChild(heading);
  var closeBtn = el("button", "dpmtf-btn dpmtf-small");
  closeBtn.textContent = lbl("lbl_btn_close_drawer", "Close");
  closeBtn.onclick = function () { detailDiv.style.display = "none"; };
  detailDiv.appendChild(closeBtn);

  var table = el("table", "dpmtf-table");
  var thead = el("thead", null);
  var thr = el("tr", null);
  ["Run ID", "Phase", "Success", "Duration", "Model", "Timestamp"].forEach(function (h) {
    thr.appendChild(el("th", null, h));
  });
  thead.appendChild(thr);
  table.appendChild(thead);
  var tbody = el("tbody", null);
  table.appendChild(tbody);
  detailDiv.appendChild(table);

  fetch("/api/implementation-patterns/" + encodeURIComponent(patternId) + "/runs?limit=50")
    .then(function (res) {
      if (!res.ok) throw new Error("HTTP " + res.status);
      return res.json();
    })
    .then(function (data) {
      clear(tbody);
      var runs = data.runs || [];
      if (!runs.length) {
        var row = el("tr", null);
        var cell = el("td", null, "No runs for this pattern.");
        cell.colSpan = 6;
        row.appendChild(cell);
        tbody.appendChild(row);
        return;
      }
      runs.forEach(function (r) {
        var row = el("tr", null);
        row.appendChild(td(r.run_id));
        row.appendChild(td(r.phase_key));
        row.appendChild(td(r.success ? "✓" : "✗", r.success ? "hitrate-good" : "hitrate-low"));
        row.appendChild(td(r.duration_seconds != null ? r.duration_seconds + "s" : "-"));
        row.appendChild(td(r.model_used || "-"));
        row.appendChild(td(r.run_timestamp ? new Date(r.run_timestamp).toLocaleString() : "-"));
        tbody.appendChild(row);
      });
    })
    .catch(function (err) {
      clear(tbody);
      var row = el("tr", null);
      var cell = el("td", null, lbl("lbl_status_error_prefix", "Error: ") + escapeHtml(err.message));
      cell.colSpan = 6;
      row.appendChild(cell);
      tbody.appendChild(row);
    });
}

function truncate(str, maxLen) {
  if (!str) return "";
  if (str.length <= maxLen) return str;
  return str.substring(0, maxLen) + "...";
}

function formatTokens(n) {
  if (n == null) return "-";
  if (n >= 1000) return (n / 1000).toFixed(1) + "K";
  return String(n);
}

/* ── 6. Prompt Sequence Planner ────────────────────── */
var currentSequenceId = null;

function loadPromptSequences() {
  var container = document.getElementById("prompt-sequence-content");
  if (!container) return;
  clear(container);

  // Status bar
  var statusBar = el("div", null);
  statusBar.style.marginBottom = "12px";
  var seqCount = el("span", "dpmtf-badge dpmtf-badge-info");
  seqCount.id = "sequence-count-display";
  seqCount.textContent = lbl("lbl_sequences", "Sequences") + ": 0";
  statusBar.appendChild(seqCount);
  var stepCount = el("span", "dpmtf-badge dpmtf-badge-info");
  stepCount.id = "step-count-display";
  stepCount.style.marginLeft = "8px";
  stepCount.textContent = lbl("lbl_steps", "Steps") + ": 0";
  statusBar.appendChild(stepCount);
  container.appendChild(statusBar);

  // Create form
  var createCard = el("div", "dpmtf-card");
  createCard.appendChild(el("h4", null, lbl("lbl_btn_create", "Create") + " " + (lbl("lbl_sequences", "Sequence") || "Sequence")));
  var nameLabel = el("label", "dpmtf-label", lbl("lbl_project_name", "Name") + ":");
  createCard.appendChild(nameLabel);
  var nameInput = el("input", "dpmtf-input");
  nameInput.id = "sequence-name";
  nameInput.placeholder = "Enter sequence name";
  createCard.appendChild(nameInput);
  var goalLabel = el("label", "dpmtf-label", "Goal:");
  createCard.appendChild(goalLabel);
  var goalInput = el("textarea", "dpmtf-textarea");
  goalInput.id = "sequence-goal";
  goalInput.placeholder = "Enter sequence goal";
  createCard.appendChild(goalInput);
  var createBtn = el("button", "dpmtf-btn dpmtf-btn-primary");
  createBtn.textContent = lbl("lbl_btn_create", "Create") + " " + (lbl("lbl_sequences", "Sequence") || "Sequence");
  createBtn.onclick = createPromptSequence;
  createCard.appendChild(createBtn);
  container.appendChild(createCard);

  // Select sequence
  var selectCard = el("div", "dpmtf-card");
  selectCard.appendChild(el("h4", null, lbl("lbl_select_sequence", "Select a sequence...")));
  var selector = el("select", "dpmtf-select");
  selector.id = "sequence-selector";
  selector.onchange = function () { loadSequenceSteps(selector.value); };
  var opt = el("option", null, lbl("lbl_select_sequence", "Select a sequence..."));
  opt.value = "";
  selector.appendChild(opt);
  selectCard.appendChild(selector);
  var seqStatus = el("div", "dpmtf-status");
  seqStatus.id = "sequence-status";
  selectCard.appendChild(seqStatus);
  container.appendChild(selectCard);

  // Steps container
  var stepsCard = el("div", "dpmtf-card");
  stepsCard.id = "sequence-steps-card";
  stepsCard.appendChild(el("h4", null, lbl("lbl_steps", "Steps")));
  var stepsDiv = el("div", null);
  stepsDiv.id = "sequence-steps-container";
  stepsDiv.appendChild(el("p", "dpmtf-muted", lbl("lbl_empty_steps", "No steps yet.")));
  stepsCard.appendChild(stepsDiv);
  container.appendChild(stepsCard);

  // Add step form
  var addCard = el("div", "dpmtf-card");
  addCard.id = "add-step-card";
  addCard.style.display = "none";
  addCard.appendChild(el("h4", null, lbl("lbl_btn_add_step", "Add Step")));
  var titleLabel = el("label", "dpmtf-label", "Step Title:");
  addCard.appendChild(titleLabel);
  var titleInput = el("input", "dpmtf-input");
  titleInput.id = "step-title";
  addCard.appendChild(titleInput);
  var layerLabel = el("label", "dpmtf-label", "Target Layer:");
  addCard.appendChild(layerLabel);
  var layerSelect = el("select", "dpmtf-select");
  layerSelect.id = "target-layer";
  ["skeleton","database","frontend","css","backend","config","tests","docs","verification","other"].forEach(function (l) {
    var o = el("option", null, l);
    o.value = l;
    layerSelect.appendChild(o);
  });
  addCard.appendChild(layerSelect);
  var promptLabel = el("label", "dpmtf-label", "Prompt Text:");
  addCard.appendChild(promptLabel);
  var promptInput = el("textarea", "dpmtf-textarea");
  promptInput.id = "prompt-text";
  addCard.appendChild(promptInput);
  var addBtn = el("button", "dpmtf-btn dpmtf-btn-primary");
  addBtn.textContent = lbl("lbl_btn_add_step", "Add Step");
  addBtn.onclick = addPromptSequenceStep;
  addCard.appendChild(addBtn);
  container.appendChild(addCard);

  // Prompt preview
  var previewCard = el("div", "dpmtf-card");
  previewCard.appendChild(el("h4", null, lbl("lbl_prompt_preview", "Generate Next Prompt Preview")));
  var genBtn = el("button", "dpmtf-btn dpmtf-btn-primary");
  genBtn.textContent = lbl("lbl_btn_generate_prompt", "Generate Next Prompt Preview");
  genBtn.onclick = generateNextPrompt;
  previewCard.appendChild(genBtn);
  var previewMsg = el("p", "dpmtf-muted");
  previewMsg.id = "prompt-preview-message";
  previewMsg.textContent = lbl("lbl_no_prompts_yet", "No prompt generated yet.");
  previewCard.appendChild(previewMsg);
  var previewTextarea = el("textarea", "dpmtf-textarea");
  previewTextarea.id = "prompt-preview";
  previewTextarea.style.display = "none";
  previewTextarea.readOnly = true;
  previewCard.appendChild(previewTextarea);
  var copyBtn = el("button", "dpmtf-btn");
  copyBtn.id = "copy-prompt-btn";
  copyBtn.textContent = lbl("lbl_btn_copy_prompt", "Copy Prompt");
  copyBtn.style.display = "none";
  copyBtn.onclick = copyPrompt;
  previewCard.appendChild(copyBtn);
  var saveSection = el("div", null);
  saveSection.id = "save-prompt-section";
  saveSection.style.display = "none";
  var saveBtn = el("button", "dpmtf-btn dpmtf-btn-primary");
  saveBtn.textContent = lbl("lbl_btn_save_prompt", "Save Generated Prompt");
  saveBtn.onclick = saveGeneratedPrompt;
  saveSection.appendChild(saveBtn);
  var saveStatus = el("span", "dpmtf-status");
  saveStatus.id = "save-prompt-status";
  saveSection.appendChild(saveStatus);
  previewCard.appendChild(saveSection);
  container.appendChild(previewCard);

  // Prompt history
  var historyCard = el("div", "dpmtf-card");
  historyCard.appendChild(el("h4", null, lbl("lbl_prompt_history", "Prompt History")));
  var historyMsg = el("p", "dpmtf-muted");
  historyMsg.id = "prompt-history-message";
  historyMsg.textContent = lbl("lbl_no_prompts_yet", "No generated prompts yet.");
  historyCard.appendChild(historyMsg);
  var historyList = el("div", null);
  historyList.id = "prompt-history-list";
  historyList.style.display = "none";
  historyCard.appendChild(historyList);
  container.appendChild(historyCard);

  // Load data
  refreshSequenceList();
  updateCounts();
}

function refreshSequenceList() {
  fetch("/api/prompt-sequences")
    .then(function (res) { return res.json(); })
    .then(function (data) {
      var selector = document.getElementById("sequence-selector");
      if (!selector) return;
      while (selector.options.length > 1) selector.remove(1);
      (data.sequences || []).forEach(function (s) {
        var opt = el("option", null, s.name);
        opt.value = s.id;
        selector.appendChild(opt);
      });
    });
}

function createPromptSequence() {
  var name = document.getElementById("sequence-name").value.trim();
  var goal = document.getElementById("sequence-goal").value.trim();
  if (!name) return;
  fetch("/api/prompt-sequences", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name: name, goal: goal })
  })
    .then(function (res) { return res.json(); })
    .then(function () {
      document.getElementById("sequence-name").value = "";
      document.getElementById("sequence-goal").value = "";
      refreshSequenceList();
      updateCounts();
    });
}

function loadSequenceSteps(seqId) {
  if (!seqId) return;
  currentSequenceId = parseInt(seqId);
  var container = document.getElementById("sequence-steps-container");
  var addCard = document.getElementById("add-step-card");
  var statusEl = document.getElementById("sequence-status");
  if (!container) return;

  fetch("/api/prompt-sequences/" + seqId + "/steps")
    .then(function (res) { return res.json(); })
    .then(function (data) {
      clear(container);
      var steps = data.steps || [];
      if (!steps.length) {
        container.appendChild(el("p", "dpmtf-muted", lbl("lbl_empty_steps", "No steps yet.")));
      } else {
        var table = el("table", "dpmtf-table");
        var thead = el("thead", null);
        var thr = el("tr", null);
        thr.appendChild(el("th", null, "#"));
        thr.appendChild(el("th", null, "Title"));
        thr.appendChild(el("th", null, "Layer"));
        thr.appendChild(el("th", null, "Status"));
        thead.appendChild(thr);
        table.appendChild(thead);
        var tbody = el("tbody", null);
        steps.forEach(function (s) {
          var row = el("tr", null);
          row.appendChild(td(String(s.step_number)));
          row.appendChild(td(escapeHtml(s.step_title || "-")));
          row.appendChild(td(s.target_layer || "-"));
          row.appendChild(td(s.status || "planned"));
          tbody.appendChild(row);
        });
        table.appendChild(tbody);
        container.appendChild(table);
      }
      if (addCard) addCard.style.display = "block";
      if (statusEl) statusEl.textContent = steps.length + " " + (lbl("lbl_steps", "steps") || "steps");
    })
    .catch(function (err) {
      if (statusEl) statusEl.textContent = lbl("lbl_status_error_prefix", "Error: ") + escapeHtml(err.message);
    });
}

function addPromptSequenceStep() {
  if (!currentSequenceId) return;
  var title = document.getElementById("step-title").value.trim();
  var layer = document.getElementById("target-layer").value;
  var prompt = document.getElementById("prompt-text").value.trim();
  if (!title) return;
  fetch("/api/prompt-sequences/" + currentSequenceId + "/steps", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ step_title: title, target_layer: layer, prompt_text: prompt })
  })
    .then(function (res) { return res.json(); })
    .then(function () {
      document.getElementById("step-title").value = "";
      document.getElementById("prompt-text").value = "";
      loadSequenceSteps(currentSequenceId);
      updateCounts();
    });
}

function generateNextPrompt() {
  if (!currentSequenceId) return;
  fetch("/api/prompt-sequences/" + currentSequenceId + "/next-prompt")
    .then(function (res) { return res.json(); })
    .then(function (data) {
      var msg = document.getElementById("prompt-preview-message");
      var textarea = document.getElementById("prompt-preview");
      var copyBtn = document.getElementById("copy-prompt-btn");
      var saveSection = document.getElementById("save-prompt-section");
      if (msg) msg.style.display = "none";
      if (textarea) { textarea.value = data.prompt || ""; textarea.style.display = "block"; }
      if (copyBtn) copyBtn.style.display = "block";
      if (saveSection) saveSection.style.display = "block";
    });
}

function copyPrompt() {
  var textarea = document.getElementById("prompt-preview");
  if (!textarea) return;
  textarea.select();
  document.execCommand("copy");
}

function saveGeneratedPrompt() {
  if (!currentSequenceId) return;
  var textarea = document.getElementById("prompt-preview");
  if (!textarea || !textarea.value) return;
  fetch("/api/prompt-sequences/" + currentSequenceId + "/steps")
    .then(function (res) { return res.json(); })
    .then(function (data) {
      var steps = data.steps || [];
      var planned = steps.filter(function (s) { return s.status === "planned"; });
      if (!planned.length) return;
      fetch("/api/prompt-sequences/" + currentSequenceId + "/steps/" + planned[0].id + "/generated-prompts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt_text: textarea.value })
      })
        .then(function () {
          var saveStatus = document.getElementById("save-prompt-status");
          if (saveStatus) saveStatus.textContent = lbl("lbl_status_success", "Saved!") || "Saved!";
          loadPromptHistory(currentSequenceId);
        });
    });
}

function loadPromptHistory(seqId) {
  if (!seqId) return;
  var list = document.getElementById("prompt-history-list");
  var msg = document.getElementById("prompt-history-message");
  if (!list) return;
  fetch("/api/prompt-sequences/" + seqId + "/generated-prompts")
    .then(function (res) { return res.json(); })
    .then(function (data) {
      var prompts = data.prompts || [];
      if (!prompts.length) {
        if (msg) msg.style.display = "block";
        list.style.display = "none";
        return;
      }
      if (msg) msg.style.display = "none";
      list.style.display = "block";
      clear(list);
      prompts.forEach(function (p) {
        var card = el("div", "dpmtf-card");
        card.appendChild(el("p", "dpmtf-muted dpmtf-small", "Step " + p.step_number + " — " + (p.generated_at || "")));
        var pre = el("pre", null);
        pre.style.whiteSpace = "pre-wrap";
        pre.style.fontSize = "0.85em";
        pre.textContent = p.prompt_text || "";
        card.appendChild(pre);
        list.appendChild(card);
      });
    });
}

function updateCounts() {
  fetch("/api/prompt-sequences")
    .then(function (res) { return res.json(); })
    .then(function (data) {
      var seqs = data.sequences || [];
      var seqDisplay = document.getElementById("sequence-count-display");
      if (seqDisplay) seqDisplay.textContent = (lbl("lbl_sequences", "Sequences") || "Sequences") + ": " + seqs.length;
      var totalSteps = 0;
      Promise.all(seqs.map(function (s) {
        return fetch("/api/prompt-sequences/" + s.id + "/steps")
          .then(function (r) { return r.json(); })
          .then(function (d) { totalSteps += (d.steps || []).length; });
      })).then(function () {
        var stepDisplay = document.getElementById("step-count-display");
        if (stepDisplay) stepDisplay.textContent = (lbl("lbl_steps", "Steps") || "Steps") + ": " + totalSteps;
      });
    });
}

/* ── 7. Project Planning ───────────────────────────── */
function loadProjectPlanning() {
  var container = document.getElementById("project-planning-content");
  if (!container) return;
  clear(container);

  // Create form
  var formCard = el("div", "dpmtf-card");
  formCard.appendChild(el("h4", null, lbl("lbl_btn_create_project_plan", "Create Project Plan")));

  var fields = [
    ["lbl_project_name", "project-name", "text", "Enter project name", "Project Name"],
    ["lbl_target_folder", "target-folder", "text", "Enter absolute target folder path", "Target Folder"],
    ["lbl_app_port", "app-port", "number", "Enter app port (optional)", "App Port"],
  ];
  fields.forEach(function (f) {
    var label = el("label", "dpmtf-label", lbl(f[0], f[4]) + ":");
    formCard.appendChild(label);
    var input = el("input", "dpmtf-input");
    input.id = f[1];
    input.type = f[2];
    input.placeholder = f[3];
    formCard.appendChild(input);
  });

  // App profile dropdown
  var profileLabel = el("label", "dpmtf-label", lbl("lbl_app_profile", "App Profile") + ":");
  formCard.appendChild(profileLabel);
  var profileSelect = el("select", "dpmtf-select");
  profileSelect.id = "app-profile";
  profileSelect.appendChild(el("option", null, lbl("lbl_select_sequence", "Select...") || "Select..."));
  formCard.appendChild(profileSelect);

  // Prompt sequence dropdown
  var seqLabel = el("label", "dpmtf-label", lbl("lbl_prompt_sequence_select", "Prompt Sequence") + ":");
  formCard.appendChild(seqLabel);
  var seqSelect = el("select", "dpmtf-select");
  seqSelect.id = "prompt-sequence";
  seqSelect.appendChild(el("option", null, lbl("lbl_select_sequence", "Select...") || "Select..."));
  formCard.appendChild(seqSelect);

  // Notes
  var notesLabel = el("label", "dpmtf-label", lbl("lbl_notes", "Notes") + ":");
  formCard.appendChild(notesLabel);
  var notesInput = el("textarea", "dpmtf-textarea");
  notesInput.id = "notes";
  notesInput.placeholder = "Enter project notes (optional)";
  formCard.appendChild(notesInput);

  var createBtn = el("button", "dpmtf-btn dpmtf-btn-primary");
  createBtn.textContent = lbl("lbl_btn_create_project_plan", "Create Project Plan");
  createBtn.onclick = createProjectPlan;
  formCard.appendChild(createBtn);
  var planStatus = el("span", "dpmtf-status");
  planStatus.id = "project-plan-status";
  formCard.appendChild(planStatus);
  container.appendChild(formCard);

  // Existing plans
  var plansCard = el("div", "dpmtf-card");
  plansCard.appendChild(el("h4", null, "Existing Project Plans"));
  var plansDiv = el("div", null);
  plansDiv.id = "project-plans-container";
  plansDiv.appendChild(el("p", "dpmtf-muted", lbl("lbl_status_loading", "Loading...")));
  plansCard.appendChild(plansDiv);
  container.appendChild(plansCard);

  loadProjectPlans();
  loadProjectPlanningDropdowns();
}

function loadProjectPlans() {
  var container = document.getElementById("project-plans-container");
  if (!container) return;
  fetch("/api/project-plans")
    .then(function (res) { return res.json(); })
    .then(function (data) {
      clear(container);
      var plans = data.plans || [];
      if (!plans.length) {
        container.appendChild(el("p", "dpmtf-muted", lbl("lbl_status_no_data", "No project plans yet.")));
        return;
      }
      var table = el("table", "dpmtf-table");
      var thead = el("thead", null);
      var thr = el("tr", null);
      ["Name", "Folder", "Port", "Status"].forEach(function (h) {
        thr.appendChild(el("th", null, h));
      });
      thead.appendChild(thr);
      table.appendChild(thead);
      var tbody = el("tbody", null);
      plans.forEach(function (p) {
        var row = el("tr", null);
        row.appendChild(td(escapeHtml(p.project_name)));
        row.appendChild(td(escapeHtml(p.target_folder)));
        row.appendChild(td(p.app_port || "-"));
        row.appendChild(td(p.status || "planned"));
        tbody.appendChild(row);
      });
      table.appendChild(tbody);
      container.appendChild(table);
    })
    .catch(function (err) {
      clear(container);
      container.appendChild(el("p", "dpmtf-error", lbl("lbl_status_error_prefix", "Error: ") + escapeHtml(err.message)));
    });
}

function createProjectPlan() {
  var name = document.getElementById("project-name").value.trim();
  var folder = document.getElementById("target-folder").value.trim();
  if (!name || !folder) return;
  var portVal = document.getElementById("app-port").value.trim();
  var profileId = document.getElementById("app-profile").value;
  var seqId = document.getElementById("prompt-sequence").value;
  var notes = document.getElementById("notes").value.trim();

  var body = { project_name: name, target_folder: folder };
  if (portVal) body.app_port = parseInt(portVal);
  if (profileId) body.app_profile_id = parseInt(profileId);
  if (seqId) body.prompt_sequence_id = parseInt(seqId);
  if (notes) body.notes = notes;

  fetch("/api/project-plans", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  })
    .then(function (res) { return res.json(); })
    .then(function () {
      document.getElementById("project-name").value = "";
      document.getElementById("target-folder").value = "";
      document.getElementById("app-port").value = "";
      document.getElementById("notes").value = "";
      var statusEl = document.getElementById("project-plan-status");
      if (statusEl) statusEl.textContent = lbl("lbl_status_success", "Created!") || "Created!";
      loadProjectPlans();
    });
}

function loadProjectPlanningDropdowns() {
  fetch("/api/app-profiles")
    .then(function (res) { return res.json(); })
    .then(function (data) {
      var sel = document.getElementById("app-profile");
      if (!sel) return;
      (data.profiles || []).forEach(function (p) {
        var opt = el("option", null, p.name);
        opt.value = p.id;
        sel.appendChild(opt);
      });
    });
  fetch("/api/prompt-sequences")
    .then(function (res) { return res.json(); })
    .then(function (data) {
      var sel = document.getElementById("prompt-sequence");
      if (!sel) return;
      (data.sequences || []).forEach(function (s) {
        var opt = el("option", null, s.name);
        opt.value = s.id;
        sel.appendChild(opt);
      });
    });
}

/* ── 8. System Setup Drawer ────────────────────────── */
function initDrawer() {
  var btn = document.getElementById("system-setup-btn");
  var drawer = document.getElementById("system-setup-drawer");
  var content = document.getElementById("drawer-content");
  if (!btn || !drawer || !content) return;

  btn.onclick = function () { drawer.classList.add("open"); buildDrawerContent(); };
  clear(content);

  var closeBtn = el("button", "drawer-close-btn");
  closeBtn.innerHTML = "&times;";
  closeBtn.onclick = function () { drawer.classList.remove("open"); };
  content.appendChild(closeBtn);
}

function buildDrawerContent() {
  var content = document.getElementById("drawer-content");
  if (!content) return;
  while (content.children.length > 1) content.removeChild(content.lastChild);

  // ── Layout Slots ─────────────────────────────────────
  var layoutCard = el("div", "dpmtf-card");
  layoutCard.appendChild(el("h4", null, lbl("lbl_drawer_layout_slots", "Layout Slots")));
  var layoutBody = el("div", null);
  layoutBody.appendChild(el("p", "dpmtf-muted", lbl("lbl_status_loading", "Loading...")));
  layoutCard.appendChild(layoutBody);
  content.appendChild(layoutCard);

  fetch("/api/frontend-layout")
    .then(function (res) { return res.json(); })
    .then(function (data) {
      clear(layoutBody);
      var slots = data.layout_slots || [];
      var panels = data.layout_panels || [];
      if (!slots.length && !panels.length) {
        layoutBody.appendChild(el("p", "dpmtf-muted", lbl("lbl_status_no_data", "No data")));
        return;
      }
      var p = el("p", "dpmtf-small", null);
      p.textContent = slots.length + " slots, " + panels.length + " panels";
      layoutBody.appendChild(p);
    })
    .catch(function (err) {
      clear(layoutBody);
      layoutBody.appendChild(el("p", "dpmtf-error", lbl("lbl_status_error_prefix", "Error: ") + escapeHtml(err.message)));
    });

  // ── Database Layout Preview ──────────────────────────
  var dbLayoutCard = el("div", "dpmtf-card");
  dbLayoutCard.appendChild(el("h4", null, lbl("lbl_drawer_db_layout", "Database Layout Preview")));
  var dbLayoutBody = el("div", null);
  dbLayoutBody.appendChild(el("p", "dpmtf-muted", lbl("lbl_status_loading", "Loading...")));
  dbLayoutCard.appendChild(dbLayoutBody);
  content.appendChild(dbLayoutCard);

  fetch("/api/frontend-layout")
    .then(function (res) { return res.json(); })
    .then(function (data) {
      clear(dbLayoutBody);
      var panels = data.layout_panels || [];
      if (!panels.length) {
        dbLayoutBody.appendChild(el("p", "dpmtf-muted", lbl("lbl_status_no_data", "No data")));
        return;
      }
      var table = el("table", "dpmtf-table");
      var thead = el("thead", null);
      var thr = el("tr", null);
      thr.appendChild(el("th", null, "Panel"));
      thr.appendChild(el("th", null, "Slot"));
      thr.appendChild(el("th", null, "Type"));
      thead.appendChild(thr);
      table.appendChild(thead);
      var tbody = el("tbody", null);
      panels.forEach(function (p) {
        var row = el("tr", null);
        row.appendChild(td(escapeHtml(p.panel_title)));
        row.appendChild(td(p.slot_id));
        row.appendChild(td(p.panel_type));
        tbody.appendChild(row);
      });
      table.appendChild(tbody);
      dbLayoutBody.appendChild(table);
    })
    .catch(function (err) {
      clear(dbLayoutBody);
      dbLayoutBody.appendChild(el("p", "dpmtf-error", lbl("lbl_status_error_prefix", "Error: ") + escapeHtml(err.message)));
    });

  // ── UI Labels / i18n ─────────────────────────────────
  var i18nCard = el("div", "dpmtf-card");
  i18nCard.appendChild(el("h4", null, lbl("lbl_drawer_i18n", "UI Labels / i18n")));
  var i18nBody = el("div", null);
  i18nBody.appendChild(el("p", "dpmtf-muted", lbl("lbl_status_loading", "Loading...")));
  i18nCard.appendChild(i18nBody);
  content.appendChild(i18nCard);

  fetch("/api/ui-labels/main?locale=" + locale)
    .then(function (res) { return res.json(); })
    .then(function (data) {
      clear(i18nBody);
      var labels = data.labels || {};
      var keys = Object.keys(labels);
      if (!keys.length) {
        i18nBody.appendChild(el("p", "dpmtf-muted", lbl("lbl_status_no_data", "No data")));
        return;
      }
      var p = el("p", "dpmtf-small", null);
      p.textContent = keys.length + " labels loaded for " + (data.locale || locale);
      i18nBody.appendChild(p);
      // Show first 10 labels as sample
      var table = el("table", "dpmtf-table");
      var thead = el("thead", null);
      var thr = el("tr", null);
      thr.appendChild(el("th", null, "Key"));
      thr.appendChild(el("th", null, "Text"));
      thead.appendChild(thr);
      table.appendChild(thead);
      var tbody = el("tbody", null);
      keys.slice(0, 10).forEach(function (k) {
        var row = el("tr", null);
        row.appendChild(td(k));
        row.appendChild(td(labels[k]));
        tbody.appendChild(row);
      });
      table.appendChild(tbody);
      i18nBody.appendChild(table);
    })
    .catch(function (err) {
      clear(i18nBody);
      i18nBody.appendChild(el("p", "dpmtf-error", lbl("lbl_status_error_prefix", "Error: ") + escapeHtml(err.message)));
    });

  // ── Endpoint Registry ────────────────────────────────
  var epCard = el("div", "dpmtf-card");
  epCard.appendChild(el("h4", null, lbl("lbl_drawer_endpoint_registry", "Endpoint Registry")));
  var epBody = el("div", null);
  epBody.appendChild(el("p", "dpmtf-muted", lbl("lbl_status_loading", "Loading...")));
  epCard.appendChild(epBody);
  content.appendChild(epCard);

  fetch("/api/endpoint-registry")
    .then(function (res) { return res.json(); })
    .then(function (data) {
      clear(epBody);
      var endpoints = data.endpoint_registry || [];
      if (!endpoints.length) {
        epBody.appendChild(el("p", "dpmtf-muted", lbl("lbl_status_no_data", "No data")));
        return;
      }
      var p = el("p", "dpmtf-small", null);
      p.textContent = endpoints.length + " endpoints registered";
      epBody.appendChild(p);
      var table = el("table", "dpmtf-table");
      var thead = el("thead", null);
      var thr = el("tr", null);
      thr.appendChild(el("th", null, "Method"));
      thr.appendChild(el("th", null, "Path"));
      thr.appendChild(el("th", null, "Purpose"));
      thead.appendChild(thr);
      table.appendChild(thead);
      var tbody = el("tbody", null);
      endpoints.forEach(function (ep) {
        var row = el("tr", null);
        row.appendChild(td(ep.http_method));
        row.appendChild(td(ep.route_path));
        row.appendChild(td(escapeHtml(ep.endpoint_purpose)));
        tbody.appendChild(row);
      });
      table.appendChild(tbody);
      epBody.appendChild(table);
    })
    .catch(function (err) {
      clear(epBody);
      epBody.appendChild(el("p", "dpmtf-error", lbl("lbl_status_error_prefix", "Error: ") + escapeHtml(err.message)));
    });

  // ── Bootstrap Dataset ────────────────────────────────
  var bsCard = el("div", "dpmtf-card");
  bsCard.appendChild(el("h4", null, lbl("lbl_drawer_bootstrap", "Bootstrap Dataset")));
  var bsBody = el("div", null);
  bsBody.appendChild(el("p", "dpmtf-muted", lbl("lbl_status_loading", "Loading...")));
  bsCard.appendChild(bsBody);
  content.appendChild(bsCard);

  fetch("/api/bootstrap-dataset-status")
    .then(function (res) { return res.json(); })
    .then(function (data) {
      clear(bsBody);
      var datasets = data.bootstrap_dataset_status || [];
      if (!datasets.length) {
        bsBody.appendChild(el("p", "dpmtf-muted", lbl("lbl_status_no_data", "No data")));
        return;
      }
      var p = el("p", "dpmtf-small", null);
      p.textContent = datasets.length + " datasets";
      bsBody.appendChild(p);
      var table = el("table", "dpmtf-table");
      var thead = el("thead", null);
      var thr = el("tr", null);
      thr.appendChild(el("th", null, "Dataset"));
      thr.appendChild(el("th", null, "Table"));
      thr.appendChild(el("th", null, "Script"));
      thead.appendChild(thr);
      table.appendChild(thead);
      var tbody = el("tbody", null);
      datasets.forEach(function (ds) {
        var row = el("tr", null);
        row.appendChild(td(ds.dataset_key));
        row.appendChild(td(ds.table_name));
        row.appendChild(td(ds.source_script));
        tbody.appendChild(row);
      });
      table.appendChild(tbody);
      bsBody.appendChild(table);
    })
    .catch(function (err) {
      clear(bsBody);
      bsBody.appendChild(el("p", "dpmtf-error", lbl("lbl_status_error_prefix", "Error: ") + escapeHtml(err.message)));
    });

  // ── Security / Permissions (placeholder) ─────────────
  var secCard = el("div", "dpmtf-card");
  secCard.appendChild(el("h4", null, lbl("lbl_drawer_security", "Security / Permissions")));
  secCard.appendChild(el("p", "dpmtf-muted", "Security and permissions management — planned for future phase."));
  content.appendChild(secCard);
}

/* ── 9. Prompt Template Manager ────────────────────── */
function loadTemplateManager() {
  var container = document.getElementById("template-manager-content");
  if (!container) return;
  clear(container);

  // Template list
  var listCard = el("div", "dpmtf-card");
  listCard.appendChild(el("h4", null, "Templates"));
  var table = el("table", "dpmtf-table");
  var thead = el("thead", null);
  var thr = el("tr", null);
  ["Key", "Name", "Suitable For", "Tokens (in/out)", "Preview"].forEach(function (h) {
    thr.appendChild(el("th", null, h));
  });
  thead.appendChild(thr);
  table.appendChild(thead);
  var tbody = el("tbody", null);
  table.appendChild(tbody);
  listCard.appendChild(table);
  container.appendChild(listCard);

  // Detail card (hidden until click)
  var detailCard = el("div", "dpmtf-card");
  detailCard.id = "template-detail";
  detailCard.style.display = "none";
  container.appendChild(detailCard);

  fetch("/api/prompt-templates")
    .then(function (res) { return res.json(); })
    .then(function (data) {
      clear(tbody);
      var templates = data.templates || [];
      if (!templates.length) {
        var row = el("tr", null);
        var cell = el("td", null, "No templates.");
        cell.colSpan = 5;
        row.appendChild(cell);
        tbody.appendChild(row);
        return;
      }
      templates.forEach(function (t) {
        var row = el("tr", null);
        row.style.cursor = "pointer";
        row.onclick = function () { showTemplateDetail(t.template_key); };
        row.appendChild(td(t.template_key));
        row.appendChild(td(t.template_name));
        var suitableCell = el("td", null);
        var badge = el("span", t.suitable_for === "local" ? "model-badge-local" :
                              t.suitable_for === "cloud" ? "model-badge-cloud" : "dpmtf-badge dpmtf-badge-info");
        badge.textContent = t.suitable_for;
        suitableCell.appendChild(badge);
        row.appendChild(suitableCell);
        row.appendChild(td((t.avg_token_count_input || "-") + " / " + (t.avg_token_count_output || "-")));
        row.appendChild(td("Click to view"));
        tbody.appendChild(row);
      });
    })
    .catch(function (err) {
      clear(tbody);
      var row = el("tr", null);
      var cell = el("td", null, lbl("lbl_status_error_prefix", "Error: ") + escapeHtml(err.message));
      cell.colSpan = 5;
      row.appendChild(cell);
      tbody.appendChild(row);
    });
}

function showTemplateDetail(templateKey) {
  var card = document.getElementById("template-detail");
  if (!card) return;
  card.style.display = "block";
  clear(card);

  var closeBtn = el("button", "dpmtf-btn dpmtf-small");
  closeBtn.textContent = lbl("lbl_btn_close_drawer", "Close");
  closeBtn.onclick = function () { card.style.display = "none"; };
  card.appendChild(closeBtn);

  var loadingEl = el("p", "dpmtf-muted", lbl("lbl_status_loading", "Loading..."));
  card.appendChild(loadingEl);

  fetch("/api/prompt-templates/" + encodeURIComponent(templateKey))
    .then(function (res) {
      if (!res.ok) throw new Error("HTTP " + res.status);
      return res.json();
    })
    .then(function (t) {
      clear(card);
      card.appendChild(closeBtn);

      card.appendChild(el("h4", null, t.template_name + " (" + t.template_key + ")"));
      if (t.description) card.appendChild(el("p", "dpmtf-muted", t.description));

      // Suitable for badge
      var suitableP = el("p", null);
      var badge = el("span", t.suitable_for === "local" ? "model-badge-local" :
                            t.suitable_for === "cloud" ? "model-badge-cloud" : "dpmtf-badge dpmtf-badge-info");
      badge.textContent = "Suitable for: " + t.suitable_for;
      suitableP.appendChild(badge);
      card.appendChild(suitableP);

      // Token estimates
      card.appendChild(el("p", "dpmtf-small", "Estimated tokens: " +
        (t.avg_token_count_input || "?") + " in / " +
        (t.avg_token_count_output || "?") + " out"));

      // Preview
      if (t.preview) {
        card.appendChild(el("h4", null, "Preview"));
        var pre = el("pre", null);
        pre.style.whiteSpace = "pre-wrap";
        pre.style.fontSize = "0.85em";
        pre.style.background = "#0d1117";
        pre.style.padding = "12px";
        pre.style.borderRadius = "4px";
        pre.textContent = t.preview;
        card.appendChild(pre);
      }
    })
    .catch(function (err) {
      clear(card);
      card.appendChild(closeBtn);
      card.appendChild(el("p", "dpmtf-error", lbl("lbl_status_error_prefix", "Error: ") + escapeHtml(err.message)));
    });
}

/* ── 10. Init ──────────────────────────────────────── */
function onReady() {
  loadLabels();
  loadDbStatus();
  loadPhaseStatus();
  loadHitrates();
  loadTemplateManager();
  loadPromptSequences();
  loadProjectPlanning();
  initDrawer();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", onReady);
} else {
  onReady();
}
