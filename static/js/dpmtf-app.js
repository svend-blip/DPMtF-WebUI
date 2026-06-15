/* ── 1. i18n loader ─────────────────────────────────── */
var labelMap = {};
var currentLocale = "en-US";  // fallback indtil API svarer

function loadLabels() {
  // Hent brugerens gemte sprog fra API
  fetch("/api/user-language")
    .then(function (res) {
      if (!res.ok) throw new Error("HTTP " + res.status);
      return res.json();
    })
    .then(function (data) {
      currentLocale = data.locale || "en-US";
      var dropdown = document.getElementById("lang-dropdown");
      if (dropdown) dropdown.value = currentLocale;
      return fetch("/api/ui-labels/main?locale=" + encodeURIComponent(currentLocale));
    })
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
      // Fallback: prøv med nuværende locale direkte
      fetch("/api/ui-labels/main?locale=" + encodeURIComponent(currentLocale))
        .then(function (res) { return res.json(); })
        .then(function (data) {
          labelMap = data.labels || data;
          document.querySelectorAll("[data-slot]").forEach(function (el) {
            var key = el.getAttribute("data-slot");
            if (labelMap[key]) el.textContent = labelMap[key];
          });
        })
        .catch(function () {});
    });
}

function switchLanguage(newLocale) {
  if (newLocale === currentLocale) return;
  currentLocale = newLocale;

  // Gem valg på server
  fetch("/api/user-language", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ locale: newLocale }),
  }).catch(function (err) {
    console.warn("Failed to save language preference:", err.message);
  });

  // Genindlæs labels
  fetch("/api/ui-labels/main?locale=" + encodeURIComponent(newLocale))
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
      // Genindlæs alle panels med nye labels
      if (typeof loadDbStatus === "function") loadDbStatus();
      if (typeof loadPhaseStatus === "function") loadPhaseStatus();
      if (typeof loadHitrates === "function") loadHitrates();
      if (typeof loadPromptSequences === "function") loadPromptSequences();
      if (typeof loadTemplates === "function") loadTemplates();
      if (typeof loadProjectPlans === "function") loadProjectPlans();
    })
    .catch(function (err) {
      console.warn("Failed to switch language:", err.message);
    });
}

/* ── 1b. Panel structure (groups + subgroups) ────────── */
var panelStructure = {};

function loadPanelStructure() {
  fetch("/api/panel-structure?locale=" + encodeURIComponent(currentLocale))
    .then(function (res) {
      if (!res.ok) throw new Error("HTTP " + res.status);
      return res.json();
    })
    .then(function (data) {
      panelStructure = data.groups || {};
      buildPanelStructure();
    })
    .catch(function () {
      buildPanelStructure();
    });
}

function buildPanelStructure() {
  var groupNames = ["daily", "journals", "reports", "periodic", "setup"];
  for (var i = 0; i < groupNames.length; i++) {
    var gn = groupNames[i];
    var pg = document.getElementById("pg-" + gn);
    if (!pg) continue;
    var info = panelStructure[gn] || { is_visible: true, state: "expanded", subgroups: [] };

    // Skjul tomme grupper
    if (!info.is_visible) {
      pg.classList.add("dpmtf-hidden");
      continue;
    }
    pg.classList.remove("dpmtf-hidden");

    // Sæt group collapse state
    var toggle = pg.querySelector(".panel-group-toggle");
    var body = pg.querySelector(".panel-group-body");
    if (info.state === "collapsed") {
      pg.classList.add("collapsed");
      if (body) body.style.display = "none";
      if (toggle) toggle.textContent = "▶";
    } else {
      pg.classList.remove("collapsed");
      if (body) body.style.display = "";
      if (toggle) toggle.textContent = "▼";
    }

    // Byg subgroups inde i body
    if (body) buildSubgroups(body, gn, info.subgroups);
  }
}

function buildSubgroups(body, groupName, subgroups) {
  // Flyt paneler tilbage til body før subgroups fjernes (undgå at slette paneler)
  var existing = body.querySelectorAll(".panel-subgroup");
  for (var i = 0; i < existing.length; i++) {
    var sgBody = existing[i].querySelector(".panel-subgroup-body");
    if (sgBody) {
      while (sgBody.firstChild) {
        body.appendChild(sgBody.firstChild);
      }
    }
    existing[i].remove();
  }

  if (!subgroups || !subgroups.length) {
    return;
  }

  for (var s = 0; s < subgroups.length; s++) {
    var sg = subgroups[s];
    if (!sg.is_visible) continue;

    var sgEl = document.createElement("section");
    sgEl.className = "panel-subgroup";
    if (sg.key && sg.key.endsWith("_all")) {
      sgEl.classList.add("panel-subgroup-all");
    }
    sgEl.setAttribute("data-subgroup", sg.key);

    // Header
    var header = document.createElement("div");
    header.className = "panel-subgroup-header";
    var title = document.createElement("h3");
    title.textContent = sg.title || "";
    header.appendChild(title);
    var sgToggle = document.createElement("span");
    sgToggle.className = "panel-subgroup-toggle";
    sgToggle.textContent = sg.state === "collapsed" ? "▶" : "▼";
    header.appendChild(sgToggle);
    sgEl.appendChild(header);

    // Body
    var sgBody = document.createElement("div");
    sgBody.className = "panel-subgroup-body";
    if (sg.state === "collapsed") {
      sgEl.classList.add("collapsed");
      sgBody.style.display = "none";
    }

    // Flyt paneler ind i subgroup baseret på slot mapping
    if (sg.slots && sg.slots.length) {
      for (var k = 0; k < sg.slots.length; k++) {
        var slotKey = sg.slots[k];
        var panel = body.querySelector('[data-slot="' + slotKey + '"]');
        if (panel) {
          var section = panel.closest("section") || panel.parentElement;
          if (section && section !== body) {
            sgBody.appendChild(section);
          }
        }
      }
    }

    sgEl.appendChild(sgBody);
    body.appendChild(sgEl);

    // Click handler for collapse
    header.addEventListener("click", (function (subgroupKey, el, bodyEl, toggleEl) {
      return function () {
        var isCollapsed = el.classList.contains("collapsed");
        var newState = isCollapsed ? "expanded" : "collapsed";
        if (newState === "collapsed") {
          el.classList.add("collapsed");
          if (bodyEl) bodyEl.style.display = "none";
          if (toggleEl) toggleEl.textContent = "▶";
        } else {
          el.classList.remove("collapsed");
          if (bodyEl) bodyEl.style.display = "";
          if (toggleEl) toggleEl.textContent = "▼";
        }
        fetch("/api/panel-structure/subgroup-state", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ subgroup_key: subgroupKey, state: newState }),
        }).catch(function (err) {
          console.warn("Failed to save subgroup state:", err.message);
        });
      };
    })(sg.key, sgEl, sgBody, sgToggle));
  }
}

function initPanelGroupToggles() {
  var headers = document.querySelectorAll(".panel-group-header");
  for (var i = 0; i < headers.length; i++) {
    headers[i].addEventListener("click", function () {
      var groupName = this.getAttribute("data-group");
      var pg = document.getElementById("pg-" + groupName);
      if (!pg) return;
      var isCollapsed = pg.classList.contains("collapsed");
      var newState = isCollapsed ? "expanded" : "collapsed";

      if (panelStructure[groupName]) {
        panelStructure[groupName].state = newState;
      }
      buildPanelStructure();

      fetch("/api/user-panel-groups", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ group_name: groupName, state: newState }),
      }).catch(function (err) {
        console.warn("Failed to save panel group state:", err.message);
      });
    });
  }
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
var showCompleted = false;

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
  thr.appendChild(el("th", null, lbl("lbl_col_phase", "Phase")));
  thr.appendChild(el("th", null, lbl("lbl_col_success_rate", "Success Rate")));
  thr.appendChild(el("th", null, lbl("lbl_col_successful_total", "Successful / Total")));
  thr.appendChild(el("th", null, lbl("lbl_col_last_run", "Last Run")));
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
  var patHeading = el("h4", null, lbl("lbl_pat_heading", "Implementation Patterns"));
  patHeading.style.marginTop = "20px";
  container.appendChild(patHeading);
  var patTable = el("table", "dpmtf-table");
  var patThead = el("thead", null);
  var patThr = el("tr", null);
  [
    lbl("lbl_col_pattern_id", "Pattern ID"),
    lbl("lbl_col_files", "Files"),
    lbl("lbl_col_constraints", "Constraints"),
    lbl("lbl_col_success_rate", "Success Rate"),
    lbl("lbl_col_best_model", "Best Model"),
    lbl("lbl_col_avg_dur", "Avg Dur"),
    lbl("lbl_col_runs", "Runs")
  ].forEach(function (h) {
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
  var summary = el("summary", null, lbl("lbl_runs_heading", "Recent Prompt Runs"));
  details.appendChild(summary);
  var runsTable = el("table", "dpmtf-table");
  var runsThead = el("thead", null);
  var runsThr = el("tr", null);
  [
    lbl("lbl_col_run_id", "Run ID"),
    lbl("lbl_col_phase", "Phase"),
    lbl("lbl_col_project", "Project"),
    lbl("lbl_col_status", "Status"),
    lbl("lbl_status_success", "Success"),
    lbl("lbl_col_first_try", "1st-Try"),
    lbl("lbl_col_corrections", "Corr"),
    lbl("lbl_col_duration", "Duration"),
    lbl("lbl_col_model", "Model"),
    lbl("lbl_tpl_suitable_for", "Type"),
    lbl("lbl_tpl_tokens", "Tokens"),
    lbl("lbl_col_cost", "Cost"),
    lbl("lbl_col_timestamp", "Timestamp")
  ].forEach(function (h) {
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
        cell.colSpan = 13;
        row.appendChild(cell);
        runsTbody.appendChild(row);
        return;
      }
      runs.forEach(function (r) {
        var row = el("tr", null);
        row.appendChild(td(r.run_id));
        row.appendChild(td(r.phase_key));
        row.appendChild(td(r.target_project));

        // Execution status badge
        var statusCell = el("td", null);
        var statusBadge = el("span", "status-" + (r.execution_status || "unknown"));
        statusBadge.textContent = r.execution_status || "unknown";
        statusCell.appendChild(statusBadge);
        row.appendChild(statusCell);

        row.appendChild(td(r.success ? "✓" : "✗", r.success ? "hitrate-good" : "hitrate-low"));

        // First-try success
        var ftCell = el("td", null);
        if (r.first_try_success === 1) ftCell.textContent = "✅";
        else if (r.first_try_success === 0) ftCell.textContent = "❌";
        else ftCell.textContent = "◻";
        row.appendChild(ftCell);

        // Manual corrections
        var corrCell = el("td", null);
        if (r.manual_corrections > 0) {
          var corrBadge = el("span", "dpmtf-badge dpmtf-badge-warning");
          corrBadge.textContent = r.manual_corrections;
          corrCell.appendChild(corrBadge);
        } else {
          corrCell.textContent = "0";
        }
        row.appendChild(corrCell);

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
      cell.colSpan = 13;
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

/* ── 2H Redesign helpers ────────────────────────────── */

function formatRate(rate) {
  if (rate == null || rate === 0) return "-";
  return (rate * 100).toFixed(0) + "%";
}

function rateClass(rate) {
  if (rate == null) return "";
  var pct = rate * 100;
  if (pct >= 80) return "hitrate-good";
  if (pct >= 50) return "hitrate-ok";
  return "hitrate-low";
}

function complexityBadge(tier) {
  var badge = el("span", "complexity-tier-" + (tier || 2));
  var labels = {1: "🟢 T1", 2: "🟡 T2", 3: "🔴 T3"};
  badge.textContent = labels[tier] || "T" + tier;
  return badge;
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

  fetch("/api/ui-labels/main?locale=" + encodeURIComponent(currentLocale))
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
      p.textContent = keys.length + " labels loaded for " + (data.locale || currentLocale);
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

  // ── Validation ───────────────────────────────────────
  var valCard = el("div", "dpmtf-card");
  valCard.appendChild(el("h4", null, "Validation"));
  var valBody = el("div", null);
  valBody.appendChild(el("p", "dpmtf-muted", lbl("lbl_status_loading", "Loading...")));
  valCard.appendChild(valBody);
  content.appendChild(valCard);

  fetch("/api/validation-rules")
    .then(function (res) { return res.json(); })
    .then(function (data) {
      clear(valBody);
      var rules = data.rules || [];
      if (!rules.length) {
        valBody.appendChild(el("p", "dpmtf-muted", lbl("lbl_val_no_rules", "No validation rules.")));
        return;
      }
      var p = el("p", "dpmtf-small", null);
      p.textContent = rules.length + " rules available";
      valBody.appendChild(p);

      // Run validation button
      var runBtn = el("button", "dpmtf-btn dpmtf-btn-primary");
      runBtn.textContent = "Run Validation";
      runBtn.onclick = function () { runValidationDrawer(); };
      valBody.appendChild(runBtn);

      // Results container
      var resultsDiv = el("div", null);
      resultsDiv.id = "drawer-validation-results";
      resultsDiv.style.marginTop = "10px";
      valBody.appendChild(resultsDiv);
    })
    .catch(function (err) {
      clear(valBody);
      valBody.appendChild(el("p", "dpmtf-error", escapeHtml(err.message)));
    });

  // ── Platform ─────────────────────────────────────────
  var platCard = el("div", "dpmtf-card");
  platCard.appendChild(el("h4", null, "Platform"));
  var platBody = el("div", null);
  platBody.appendChild(el("p", "dpmtf-muted", lbl("lbl_status_loading", "Loading...")));
  platCard.appendChild(platBody);
  content.appendChild(platCard);

  fetch("/api/platform")
    .then(function (res) { return res.json(); })
    .then(function (data) {
      clear(platBody);
      var info = [];
      info.push("OS: " + (data.platform || "?") + " (" + (data.os_release || "?") + ")");
      info.push("Python: " + (data.python_version || "?"));
      info.push("Home: " + (data.home_dir || "?"));
      info.push("GPUs: " + (data.gpu_count || 0));
      if (data.home_disk) {
        info.push("Home disk: " + data.home_disk.use_percent + "% used (" +
          data.home_disk.available + " free)");
      }
      platBody.appendChild(el("div", "dpmtf-small", info.join(" | ")));
    })
    .catch(function (err) {
      clear(platBody);
      platBody.appendChild(el("p", "dpmtf-error", escapeHtml(err.message)));
    });

  // ── Claude Code Sessions ─────────────────────────────
  var sessCard = el("div", "dpmtf-card");
  sessCard.appendChild(el("h4", null, "Claude Code Sessions"));
  var sessBody = el("div", null);
  sessBody.appendChild(el("p", "dpmtf-muted", lbl("lbl_status_loading", "Loading...")));
  sessCard.appendChild(sessBody);
  content.appendChild(sessCard);

  fetch("/api/sessions/current")
    .then(function (res) { return res.json(); })
    .then(function (data) {
      clear(sessBody);
      if (data.active && data.session) {
        var s = data.session;
        var statusBadge = el("span", "dpmtf-badge dpmtf-badge-success");
        statusBadge.textContent = "Active";
        sessBody.appendChild(statusBadge);
        sessBody.appendChild(el("div", "dpmtf-small", null));
        var info = [];
        info.push("Model: " + (s.model_used || "unknown"));
        info.push("Project: " + (s.project_context || "unknown"));
        info.push("Started: " + (s.started_at ? new Date(s.started_at).toLocaleString() : "?"));
        sessBody.appendChild(el("div", "dpmtf-small", info.join(" | ")));
      } else {
        var inactiveBadge = el("span", "dpmtf-badge dpmtf-badge-info");
        inactiveBadge.textContent = "No active session";
        sessBody.appendChild(inactiveBadge);
      }
    })
    .catch(function (err) {
      clear(sessBody);
      sessBody.appendChild(el("p", "dpmtf-error", escapeHtml(err.message)));
    });

  // ── Workflow (P→I→V loop) ────────────────────────────
  var wfCard = el("div", "dpmtf-card");
  wfCard.appendChild(el("h4", null, "Workflow — P→I→V Loop"));
  var wfBody = el("div", null);
  wfBody.appendChild(el("p", "dpmtf-muted", lbl("lbl_status_loading", "Loading...")));
  wfCard.appendChild(wfBody);
  content.appendChild(wfCard);

  fetch("/api/workflow/runs?limit=5")
    .then(function (res) { return res.json(); })
    .then(function (data) {
      clear(wfBody);
      var runs = data.runs || [];
      if (!runs.length) {
        wfBody.appendChild(el("p", "dpmtf-muted", "No workflow runs yet."));
        return;
      }
      var table = el("table", "dpmtf-table");
      var thead = el("thead", null);
      var thr = el("tr", null);
      ["Run", "Phase", "Status", "Started"].forEach(function (h) {
        thr.appendChild(el("th", null, h));
      });
      thead.appendChild(thr);
      table.appendChild(thead);
      var tbody = el("tbody", null);
      runs.forEach(function (r) {
        var row = el("tr", null);
        row.appendChild(td(r.run_id));
        row.appendChild(td(r.phase_key));
        var statusCell = el("td", null);
        var badge = el("span", "dpmtf-badge " +
          (r.status === "done" ? "dpmtf-badge-success" :
           r.status === "failed" ? "dpmtf-badge-danger" :
           r.status === "implementing" ? "dpmtf-badge-warning" :
           "dpmtf-badge-info"));
        badge.textContent = r.status;
        statusCell.appendChild(badge);
        row.appendChild(statusCell);
        row.appendChild(td(r.started_at ? new Date(r.started_at).toLocaleString() : "-"));
        tbody.appendChild(row);
      });
      table.appendChild(tbody);
      wfBody.appendChild(table);
    })
    .catch(function (err) {
      clear(wfBody);
      wfBody.appendChild(el("p", "dpmtf-error", escapeHtml(err.message)));
    });

  // ── Git Sync ─────────────────────────────────────────
  var gitCard = el("div", "dpmtf-card");
  gitCard.appendChild(el("h4", null, "Git Sync Status"));
  var gitBody = el("div", null);
  gitBody.appendChild(el("p", "dpmtf-muted", lbl("lbl_status_loading", "Loading...")));
  gitCard.appendChild(gitBody);
  content.appendChild(gitCard);

  fetch("/api/git/status")
    .then(function (res) { return res.json(); })
    .then(function (data) {
      clear(gitBody);
      var projects = data.projects || [];
      if (!projects.length) {
        gitBody.appendChild(el("p", "dpmtf-muted", "No projects tracked."));
        return;
      }
      projects.forEach(function (p) {
        var projDiv = el("div", null);
        projDiv.style.marginBottom = "8px";
        projDiv.appendChild(el("div", null, escapeHtml(p.project_key)));

        var info = [];
        info.push("Branch: " + (p.branch || "?"));
        info.push("Unpushed: " + (p.unpushed_commits || 0));
        if (p.last_commit) info.push("Last: " + p.last_commit);
        projDiv.appendChild(el("div", "dpmtf-small dpmtf-muted", info.join(" | ")));

        if (p.unpushed_list && p.unpushed_list.length) {
          var listDiv = el("div", "dpmtf-small");
          listDiv.style.marginTop = "4px";
          p.unpushed_list.forEach(function (c) {
            listDiv.appendChild(el("div", null, c));
          });
          projDiv.appendChild(listDiv);
        }
        gitBody.appendChild(projDiv);
      });
    })
    .catch(function (err) {
      clear(gitBody);
      gitBody.appendChild(el("p", "dpmtf-error", escapeHtml(err.message)));
    });

  // ── Sync Phases button ─────────────────────────────────
  var syncBtn = el("button", "dpmtf-btn");
  syncBtn.textContent = "Sync Phases from Git";
  syncBtn.style.marginTop = "8px";
  syncBtn.onclick = function () {
    syncBtn.disabled = true;
    syncBtn.textContent = "Syncing...";
    fetch("/api/phases/sync-from-git", { method: "POST" })
      .then(function (res) { return res.json(); })
      .then(function (data) {
        syncBtn.disabled = false;
        syncBtn.textContent = "Sync Phases from Git";
        if (data.advanced && data.advanced.length) {
          alert("Phases advanced: " + data.advanced.join(", ") +
            "\nNew next: " + (data.new_next || []).join(", "));
          if (typeof loadPhaseStatus === "function") loadPhaseStatus();
        } else if (data.reason) {
          alert("No phases advanced.\n" + data.reason);
        } else {
          alert("No changes. All phases up to date.");
        }
      })
      .catch(function (err) {
        syncBtn.disabled = false;
        syncBtn.textContent = "Sync Phases from Git";
        alert("Sync failed: " + err.message);
      });
  };
  gitCard.appendChild(syncBtn);

  // ── Comparison Runs ───────────────────────────────────
  var cmpCard = el("div", "dpmtf-card");
  cmpCard.appendChild(el("h4", null, lbl("lbl_drawer_comparisons", "Comparison Runs")));
  var cmpBody = el("div", null);
  cmpBody.appendChild(el("p", "dpmtf-muted", lbl("lbl_status_loading", "Loading...")));
  cmpCard.appendChild(cmpBody);
  content.appendChild(cmpCard);

  fetch("/api/comparison-runs?limit=10")
    .then(function (res) { return res.json(); })
    .then(function (data) {
      clear(cmpBody);
      var comparisons = data.comparisons || [];
      if (!comparisons.length) {
        cmpBody.appendChild(el("p", "dpmtf-muted", lbl("lbl_status_no_data", "No data")));
        return;
      }
      var table = el("table", "dpmtf-table");
      var thead = el("thead", null);
      var thr = el("tr", null);
      [lbl("lbl_cmp_id", "ID"), lbl("lbl_cmp_task", "Task"), lbl("lbl_cmp_tier", "Tier"),
       lbl("lbl_cmp_cloud", "Cloud"), lbl("lbl_cmp_local", "Local"),
       lbl("lbl_cmp_winner", "Winner")].forEach(function (h) {
        thr.appendChild(el("th", null, h));
      });
      thead.appendChild(thr);
      table.appendChild(thead);
      var tbody = el("tbody", null);
      comparisons.forEach(function (c) {
        var row = el("tr", null);
        row.appendChild(td(c.comparison_id));
        row.appendChild(td(c.task_type));
        row.appendChild(td(String(c.complexity_tier)));

        // Cloud celle: verdict + output_quality badge
        var cloudCell = el("td", null);
        var cloudBadge = el("span", "dpmtf-badge " +
          (c.cloud_verdict === "completed" ? "dpmtf-badge-success" : "dpmtf-badge-warning"));
        cloudBadge.textContent = (c.cloud_output_quality || "?") + "/5";
        cloudCell.appendChild(cloudBadge);
        row.appendChild(cloudCell);

        // Local celle: verdict + output_quality badge
        var localCell = el("td", null);
        var localBadge = el("span", "dpmtf-badge " +
          (c.local_verdict === "completed" ? "dpmtf-badge-success" : "dpmtf-badge-warning"));
        localBadge.textContent = (c.local_output_quality || "?") + "/5";
        localCell.appendChild(localBadge);
        row.appendChild(localCell);

        // Winner badge
        var winnerCell = el("td", null);
        var winnerBadge = el("span", "dpmtf-badge " +
          (c.winner === "cloud" ? "dpmtf-badge-success" :
           c.winner === "local" ? "dpmtf-badge-info" :
           "dpmtf-badge-muted"));
        winnerBadge.textContent = c.winner || "tie";
        winnerCell.appendChild(winnerBadge);
        row.appendChild(winnerCell);

        tbody.appendChild(row);
      });
      table.appendChild(tbody);
      cmpBody.appendChild(table);
    })
    .catch(function (err) {
      clear(cmpBody);
      cmpBody.appendChild(el("p", "dpmtf-error", escapeHtml(err.message)));
    });

  // ── Security / Permissions (placeholder) ─────────────
  var secCard = el("div", "dpmtf-card");
  secCard.appendChild(el("h4", null, lbl("lbl_drawer_security", "Security / Permissions")));
  secCard.appendChild(el("p", "dpmtf-muted", "Security and permissions management — planned for future phase."));
  content.appendChild(secCard);
}

function runValidationDrawer() {
  var resultsDiv = document.getElementById("drawer-validation-results");
  if (!resultsDiv) return;
  clear(resultsDiv);
  resultsDiv.appendChild(el("p", "dpmtf-muted", lbl("lbl_val_running", "Running validation...")));

  fetch("/api/validate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      target_project: "/home/svend/DPMtF-WebUI",
      rule_keys: ["all"]
    })
  })
    .then(function (res) { return res.json(); })
    .then(function (data) {
      clear(resultsDiv);
      var verdictClass = data.verdict === "PASS" ? "hitrate-good" :
                         data.verdict === "FAIL" ? "hitrate-low" : "hitrate-ok";
      var verdictEl = el("p", null);
      verdictEl.appendChild(document.createTextNode("Verdict: "));
      var verdictSpan = el("span", verdictClass, data.verdict);
      verdictEl.appendChild(verdictSpan);
      verdictEl.appendChild(document.createTextNode(
        " (" + data.rules_passed + "/" + data.rules_total + " passed)"));
      resultsDiv.appendChild(verdictEl);

      var table = el("table", "dpmtf-table");
      var thead = el("thead", null);
      var thr = el("tr", null);
      thr.appendChild(el("th", null, lbl("lbl_col_rule", "Rule")));
      thr.appendChild(el("th", null, lbl("lbl_col_result", "Result")));
      thr.appendChild(el("th", null, lbl("lbl_col_notes", "Notes")));
      thead.appendChild(thr);
      table.appendChild(thead);
      var tbody = el("tbody", null);
      (data.results || []).forEach(function (r) {
        var row = el("tr", null);
        row.appendChild(td(r.rule_name));
        row.appendChild(td(r.passed ? "✓" : "✗", r.passed ? "hitrate-good" : "hitrate-low"));
        row.appendChild(td(r.notes || r.actual_output || ""));
        tbody.appendChild(row);
      });
      table.appendChild(tbody);
      resultsDiv.appendChild(table);
    })
    .catch(function (err) {
      clear(resultsDiv);
      resultsDiv.appendChild(el("p", "dpmtf-error", escapeHtml(err.message)));
    });
}

/* ── 9. Prompt Template Manager ────────────────────── */
function loadTemplateManager() {
  var container = document.getElementById("template-manager-content");
  if (!container) return;
  clear(container);

  // Template list
  var listCard = el("div", "dpmtf-card");
  listCard.appendChild(el("h4", null, lbl("lbl_tpl_templates", "Templates")));
  var table = el("table", "dpmtf-table");
  var thead = el("thead", null);
  var thr = el("tr", null);
  [
    lbl("lbl_tpl_key", "Key"),
    lbl("lbl_tpl_name", "Name"),
    lbl("lbl_tpl_tier", "Tier"),
    lbl("lbl_tpl_suitable_for", "Suitable For"),
    lbl("lbl_tpl_capture", "Capture"),
    lbl("lbl_tpl_local_sr", "Local SR"),
    lbl("lbl_tpl_cloud_sr", "Cloud SR"),
    lbl("lbl_tpl_tokens", "Tokens (in/out)"),
    lbl("lbl_tpl_preview", "Preview")
  ].forEach(function (h) {
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
        var cell = el("td", null, lbl("lbl_status_no_data", "No templates."));
        cell.colSpan = 9;
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

        // Complexity tier badge
        var tierCell = el("td", null);
        var tierBadge = complexityBadge(t.complexity_tier);
        tierCell.appendChild(tierBadge);
        row.appendChild(tierCell);

        // Suitable for badge
        var suitableCell = el("td", null);
        var badge = el("span", t.suitable_for === "local" ? "model-badge-local" :
                              t.suitable_for === "cloud" ? "model-badge-cloud" : "dpmtf-badge dpmtf-badge-info");
        badge.textContent = t.suitable_for;
        suitableCell.appendChild(badge);
        row.appendChild(suitableCell);

        // Capture source badge
        var captureCell = el("td", null);
        var captureBadge = el("span", "capture-" + (t.capture_source || "designed"));
        captureBadge.textContent = t.capture_source || "designed";
        captureCell.appendChild(captureBadge);
        row.appendChild(captureCell);

        // Local success rate
        row.appendChild(td(formatRate(t.local_success_rate)));

        // Cloud success rate
        row.appendChild(td(formatRate(t.cloud_success_rate)));

        row.appendChild(td((t.avg_token_count_input || "-") + " / " + (t.avg_token_count_output || "-")));
        row.appendChild(td(lbl("lbl_tpl_click_to_view", "Click to view")));
        tbody.appendChild(row);
      });
    })
    .catch(function (err) {
      clear(tbody);
      var row = el("tr", null);
      var cell = el("td", null, lbl("lbl_status_error_prefix", "Error: ") + escapeHtml(err.message));
      cell.colSpan = 9;
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

      // Badge row: complexity + suitable_for + capture_source
      var badgeRow = el("p", null);
      badgeRow.appendChild(complexityBadge(t.complexity_tier));
      badgeRow.appendChild(el("span", null, " "));
      var suitableBadge = el("span", t.suitable_for === "local" ? "model-badge-local" :
                                t.suitable_for === "cloud" ? "model-badge-cloud" : "dpmtf-badge dpmtf-badge-info");
      suitableBadge.textContent = t.suitable_for;
      badgeRow.appendChild(suitableBadge);
      badgeRow.appendChild(el("span", null, " "));
      var captureBadge = el("span", "capture-" + (t.capture_source || "designed"));
      captureBadge.textContent = t.capture_source || "designed";
      badgeRow.appendChild(captureBadge);
      card.appendChild(badgeRow);

      // Success rates
      var rateRow = el("p", "dpmtf-small");
      rateRow.textContent = lbl("lbl_tpl_local_sr_label", "Local SR:") + " " + formatRate(t.local_success_rate) +
        " (" + (t.total_local_runs || 0) + " " + lbl("lbl_tpl_runs_count", "runs") + ") | " +
        lbl("lbl_tpl_cloud_sr_label", "Cloud SR:") + " " +
        formatRate(t.cloud_success_rate) + " (" + (t.total_cloud_runs || 0) + " " + lbl("lbl_tpl_runs_count", "runs") + ")";
      card.appendChild(rateRow);

      // Token estimates
      card.appendChild(el("p", "dpmtf-small", lbl("lbl_tpl_estimated_tokens", "Estimated tokens:") + " " +
        (t.avg_token_count_input || "?") + " in / " +
        (t.avg_token_count_output || "?") + " out"));

      // ── Per-model hitrate (2H redesign) ─────────────────
      fetch("/api/prompt-templates/" + encodeURIComponent(templateKey) + "/hitrate")
        .then(function (res) { return res.json(); })
        .then(function (hitData) {
          if (hitData.model_hitrates && hitData.model_hitrates.length) {
            card.appendChild(el("h4", null, lbl("lbl_tpl_model_hitrates", "Model Hitrates")));
            var hitTable = el("table", "dpmtf-table dpmtf-compact");
            var hitThead = el("thead", null);
            var hitThr = el("tr", null);
            [
              lbl("lbl_col_model", "Model"),
              lbl("lbl_col_runs", "Runs"),
              lbl("lbl_col_success_rate", "Success Rate"),
              lbl("lbl_col_avg_duration", "Avg Duration")
            ].forEach(function (h) {
              hitThr.appendChild(el("th", null, h));
            });
            hitThead.appendChild(hitThr);
            hitTable.appendChild(hitThead);
            var hitTbody = el("tbody", null);
            hitData.model_hitrates.forEach(function (mh) {
              var hitRow = el("tr", null);
              hitRow.appendChild(td(mh.model_used));
              hitRow.appendChild(td(mh.successful_runs + " / " + mh.total_runs));
              var srCell = el("td", null);
              srCell.textContent = formatRate(mh.rolling_success_rate);
              srCell.className = rateClass(mh.rolling_success_rate);
              hitRow.appendChild(srCell);
              hitRow.appendChild(td(mh.avg_duration_seconds ? mh.avg_duration_seconds + "s" : "-"));
              hitTbody.appendChild(hitRow);
            });
            hitTable.appendChild(hitTbody);
            card.appendChild(hitTable);
          }
        })
        .catch(function () { /* hitrate fetch optional — don't block detail view */ });

      // Preview
      if (t.preview) {
        card.appendChild(el("h4", null, lbl("lbl_tpl_preview", "Preview")));
        var pre = el("pre", null);
        pre.style.whiteSpace = "pre-wrap";
        pre.style.fontSize = "0.85em";
        pre.style.background = "#0d1117";
        pre.style.padding = "12px";
        pre.style.borderRadius = "4px";
        pre.textContent = t.preview;
        card.appendChild(pre);
      }

      // ── Compile form (2I-v2: database-driven) ──────────────
      card.appendChild(el("h4", null, lbl("lbl_tpl_compile_prompt", "Compile Prompt")));
      var compileContainer = el("div", null);
      compileContainer.id = "compile-form-container";
      card.appendChild(compileContainer);

      // Compiled output
      var outputDiv = el("div", null);
      outputDiv.id = "compile-output";
      outputDiv.style.display = "none";
      outputDiv.style.marginTop = "12px";
      card.appendChild(outputDiv);

      // Load dynamic form from database
      loadCompileForm(templateKey);
    })
    .catch(function (err) {
      clear(card);
      card.appendChild(closeBtn);
      card.appendChild(el("p", "dpmtf-error", lbl("lbl_status_error_prefix", "Error: ") + escapeHtml(err.message)));
    });
}

function compilePrompt(templateKey) {
  var outputDiv = document.getElementById("compile-output");
  if (!outputDiv) return;
  outputDiv.style.display = "block";
  clear(outputDiv);
  outputDiv.appendChild(el("p", "dpmtf-muted", lbl("lbl_status_loading", "Compiling...")));

  var body = {
    project_path: document.getElementById("compile-project-path").value.trim(),
    phase_id: document.getElementById("compile-phase-id").value.trim(),
    goal: document.getElementById("compile-goal").value.trim(),
    constraints: document.getElementById("compile-constraints").value.trim().split("\n").filter(Boolean),
    allowed_files: document.getElementById("compile-files").value.trim().split("\n").filter(Boolean),
    validation_commands: document.getElementById("compile-validation").value.trim().split("\n").filter(Boolean),
  };

  fetch("/api/prompt-templates/" + encodeURIComponent(templateKey) + "/compile", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  })
    .then(function (res) { return res.json(); })
    .then(function (data) {
      clear(outputDiv);
      outputDiv.appendChild(el("h4", null, "Compiled Prompt"));
      var pre = el("pre", null);
      pre.style.whiteSpace = "pre-wrap";
      pre.style.fontSize = "0.85em";
      pre.style.background = "#0d1117";
      pre.style.padding = "12px";
      pre.style.borderRadius = "4px";
      pre.textContent = data.prompt;
      outputDiv.appendChild(pre);

      var copyBtn = el("button", "dpmtf-btn");
      copyBtn.textContent = lbl("lbl_btn_copy_prompt", "Copy Prompt");
      copyBtn.onclick = function () {
        var ta = el("textarea", null);
        ta.value = data.prompt;
        ta.style.position = "fixed";
        ta.style.left = "-9999px";
        document.body.appendChild(ta);
        ta.select();
        document.execCommand("copy");
        document.body.removeChild(ta);
        copyBtn.textContent = "Copied!";
        setTimeout(function () { copyBtn.textContent = lbl("lbl_btn_copy_prompt", "Copy Prompt"); }, 2000);
      };
      outputDiv.appendChild(copyBtn);
    })
    .catch(function (err) {
      clear(outputDiv);
      outputDiv.appendChild(el("p", "dpmtf-error", lbl("lbl_status_error_prefix", "Error: ") + escapeHtml(err.message)));
    });
}

/* ── 2I-v2: Dynamic Compile Form ─────────────────── */
function loadCompileForm(templateKey) {
  var container = document.getElementById("compile-form-container");
  if (!container) return;
  clear(container);
  container.appendChild(el("p", "dpmtf-muted", lbl("lbl_status_loading", "Loading form...")));

  fetch("/api/prompt-compiler-fields")
    .then(function (res) { return res.json(); })
    .then(function (data) {
      clear(container);
      var sections = data.sections || {};
      var sectionOrder = [
        "human_responsibility", "project", "scope",
        "migration", "validation"
      ];
      var sectionLabels = {
        "human_responsibility": lbl("lbl_section_human_resp", "Human Responsibility"),
        "project": lbl("lbl_section_project", "Project"),
        "scope": lbl("lbl_section_scope", "Scope"),
        "migration": lbl("lbl_section_migration", "Migration"),
        "validation": lbl("lbl_section_validation", "Validation")
      };

      sectionOrder.forEach(function (sectionKey) {
        var fields = sections[sectionKey];
        if (!fields || !fields.length) return;

        // Migration section — only visible when is_migration is checked
        var sectionDiv = el("div", "dpmtf-compile-section");
        sectionDiv.id = "compile-section-" + sectionKey;
        if (sectionKey === "migration") {
          sectionDiv.style.display = "none";
        }

        var sectionHeader = el("h5", null, sectionLabels[sectionKey] || sectionKey);
        sectionDiv.appendChild(sectionHeader);

        fields.forEach(function (f) {
          var fieldRow = el("div", "dpmtf-field-row");
          fieldRow.id = "field-row-" + f.field_key;

          var label = el("label", "dpmtf-label", f.field_label);
          if (f.is_required) {
            var reqMark = el("span", null, " *");
            reqMark.style.color = "#f85149";
            label.appendChild(reqMark);
          }
          fieldRow.appendChild(label);

          if (f.help_text) {
            var help = el("span", "dpmtf-help-text", f.help_text);
            help.style.fontSize = "0.8em";
            help.style.color = "#8b949e";
            help.style.marginLeft = "8px";
            fieldRow.appendChild(help);
          }

          var input;
          if (f.field_type === "checkbox") {
            input = el("input", null);
            input.type = "checkbox";
            input.id = "compile-" + f.field_key;
            if (f.default_value === "1" || f.default_value === "true") {
              input.checked = true;
            }
            // Special: is_migration toggles migration section visibility
            if (f.field_key === "is_migration") {
              input.onchange = function () {
                var migSec = document.getElementById("compile-section-migration");
                if (migSec) {
                  migSec.style.display = this.checked ? "block" : "none";
                }
              };
            }
          } else if (f.field_type === "textarea") {
            input = el("textarea", "dpmtf-textarea");
            input.id = "compile-" + f.field_key;
            input.placeholder = f.placeholder || "";
            input.style.minHeight = "60px";
            if (f.default_value) input.value = f.default_value;
          } else if (f.field_type === "select") {
            input = el("select", "dpmtf-select");
            input.id = "compile-" + f.field_key;
            // Database-driven options from API (handoff 015)
            if (f.options && f.options.length) {
              f.options.forEach(function (opt) {
                var option = el("option", null);
                option.textContent = opt.label;
                option.value = opt.value;
                if (opt.default) option.selected = true;
                input.appendChild(option);
              });
            }
          } else {
            // text, path — default to text input
            input = el("input", "dpmtf-input");
            input.type = "text";
            input.id = "compile-" + f.field_key;
            input.placeholder = f.placeholder || "";
            if (f.default_value) input.value = f.default_value;
          }

          fieldRow.appendChild(input);
          sectionDiv.appendChild(fieldRow);
        });

        container.appendChild(sectionDiv);
      });

      // Compile button
      var btnRow = el("div", "dpmtf-field-row");
      var compileBtn = el("button", "dpmtf-btn dpmtf-btn-primary");
      compileBtn.textContent = lbl("lbl_tpl_compile_prompt", "Compile Prompt");
      compileBtn.onclick = function () { compilePromptV2(templateKey); };
      btnRow.appendChild(compileBtn);
      container.appendChild(btnRow);

      // Warning banner area
      var warningDiv = el("div", null);
      warningDiv.id = "compile-warning";
      warningDiv.style.display = "none";
      container.appendChild(warningDiv);
    })
    .catch(function (err) {
      clear(container);
      container.appendChild(
        el("p", "dpmtf-error",
           lbl("lbl_status_error_prefix", "Error: ") + escapeHtml(err.message))
      );
    });
}

function compilePromptV2(templateKey) {
  var outputDiv = document.getElementById("compile-output");
  if (!outputDiv) return;
  outputDiv.style.display = "block";
  clear(outputDiv);
  outputDiv.appendChild(
    el("p", "dpmtf-muted", lbl("lbl_status_compiling", "Compiling..."))
  );

  var warningDiv = document.getElementById("compile-warning");
  if (warningDiv) { warningDiv.style.display = "none"; clear(warningDiv); }

  // Clear previous error highlights
  document.querySelectorAll(".dpmtf-field-error").forEach(function (errEl) {
    errEl.style.borderColor = "";
    errEl.classList.remove("dpmtf-field-error");
  });
  document.querySelectorAll(".dpmtf-error-text").forEach(function (msgEl) {
    msgEl.remove();
  });

  // Collect all field values from the dynamic form
  var body = { handoff_id: "???" };

  document.querySelectorAll("[id^='compile-']").forEach(function (input) {
    var fieldKey = input.id.replace("compile-", "");
    if (input.type === "checkbox") {
      body[fieldKey] = input.checked;
    } else if (input.tagName === "TEXTAREA" || input.tagName === "SELECT") {
      body[fieldKey] = input.value;
    } else {
      body[fieldKey] = input.value;
    }
  });

  fetch("/api/prompt-templates/" + encodeURIComponent(templateKey) + "/compile", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  })
    .then(function (res) {
      if (!res.ok) {
        return res.json().then(function (errData) {
          var detail = errData.detail;
          if (typeof detail === "string") {
            try { detail = JSON.parse(detail); } catch (e) {}
          }
          throw { status: res.status, errors: detail.errors || [], warning: detail.warning || null };
        });
      }
      return res.json();
    })
    .then(function (data) {
      clear(outputDiv);

      // Show warning if present
      if (data.warning && warningDiv) {
        warningDiv.style.display = "block";
        var warnP = el("p", "dpmtf-warning");
        warnP.textContent = "⚠ " + data.warning;
        warningDiv.appendChild(warnP);
      }

      outputDiv.appendChild(
        el("h4", null, lbl("lbl_tpl_compiled_prompt", "Compiled Prompt"))
      );

      // Format badge
      var badgeRow = el("p", null);
      var formatBadge = el("span", "dpmtf-badge dpmtf-badge-info");
      formatBadge.textContent = "governance-v2 XML";
      badgeRow.appendChild(formatBadge);
      if (data.gates_answered && data.gates_answered.length) {
        badgeRow.appendChild(el("span", null, " "));
        var gateBadge = el("span", "dpmtf-badge dpmtf-badge-success");
        gateBadge.textContent = "Gates: " + data.gates_answered.join(", ");
        badgeRow.appendChild(gateBadge);
      }
      outputDiv.appendChild(badgeRow);

      var pre = el("pre", null);
      pre.style.whiteSpace = "pre-wrap";
      pre.style.fontSize = "0.85em";
      pre.style.background = "#0d1117";
      pre.style.padding = "12px";
      pre.style.borderRadius = "4px";
      pre.style.maxHeight = "500px";
      pre.style.overflowY = "auto";
      pre.textContent = data.prompt;
      outputDiv.appendChild(pre);

      // Copy button using clipboard API with fallback
      var copyBtn = el("button", "dpmtf-btn dpmtf-small");
      copyBtn.textContent = lbl("lbl_btn_copy_prompt", "Copy Prompt");
      copyBtn.onclick = function () {
        if (navigator.clipboard) {
          navigator.clipboard.writeText(data.prompt).then(function () {
            copyBtn.textContent = lbl("lbl_btn_copied", "Copied!");
            setTimeout(function () {
              copyBtn.textContent = lbl("lbl_btn_copy_prompt", "Copy Prompt");
            }, 2000);
          });
        } else {
          // Fallback for older browsers
          var ta = el("textarea", null);
          ta.value = data.prompt;
          ta.style.position = "fixed";
          ta.style.left = "-9999px";
          document.body.appendChild(ta);
          ta.select();
          document.execCommand("copy");
          document.body.removeChild(ta);
          copyBtn.textContent = lbl("lbl_btn_copied", "Copied!");
          setTimeout(function () {
            copyBtn.textContent = lbl("lbl_btn_copy_prompt", "Copy Prompt");
          }, 2000);
        }
      };
      outputDiv.appendChild(copyBtn);

      // ── Assign Handoff ID button (handoff 017) ─────────────────
      var assignBtn = el("button", "dpmtf-btn dpmtf-btn-primary");
      assignBtn.textContent = lbl("lbl_btn_assign_handoff_id", "Assign Handoff ID");
      assignBtn.style.marginLeft = "8px";
      assignBtn.onclick = function () {
        assignHandoffId(data.prompt, data);
      };
      outputDiv.appendChild(assignBtn);

      // Dispatch info area (hidden until ID assigned)
      var dispatchDiv = el("div", null);
      dispatchDiv.id = "dispatch-info";
      dispatchDiv.style.display = "none";
      dispatchDiv.style.marginTop = "12px";
      outputDiv.appendChild(dispatchDiv);
    })
    .catch(function (err) {
      clear(outputDiv);

      if (err.errors && err.errors.length) {
        // Field-specific validation errors
        outputDiv.appendChild(
          el("h4", "dpmtf-error",
             lbl("lbl_compile_validation_errors", "Validation Errors"))
        );

        err.errors.forEach(function (fieldErr) {
          var errMsg = el("p", "dpmtf-error-text");
          errMsg.textContent = "❌ " + fieldErr.error;
          errMsg.style.color = "#f85149";
          errMsg.style.margin = "4px 0";
          outputDiv.appendChild(errMsg);

          // Highlight the field in red
          var inputEl = document.getElementById("compile-" + fieldErr.field_key);
          if (inputEl) {
            inputEl.style.borderColor = "#f85149";
            inputEl.classList.add("dpmtf-field-error");
          }
        });

        if (err.warning) {
          var warnMsg = el("p", "dpmtf-warning");
          warnMsg.textContent = "⚠ " + err.warning;
          warnMsg.style.color = "#d29922";
          outputDiv.appendChild(warnMsg);
        }
      } else {
        outputDiv.appendChild(
          el("p", "dpmtf-error",
             lbl("lbl_status_error_prefix", "Error: ") +
             escapeHtml(err.message || "Compilation failed"))
        );
      }
    });
}

/* ── Prompt Compiler: Assign Handoff ID (handoff 017) ── */
function assignHandoffId(promptText, compileData) {
  var dispatchDiv = document.getElementById("dispatch-info");
  if (!dispatchDiv) return;
  dispatchDiv.style.display = "block";
  clear(dispatchDiv);
  dispatchDiv.appendChild(
    el("p", "dpmtf-muted", lbl("lbl_status_assigning_id", "Assigning handoff ID..."))
  );

  var body = {
    prompt_text: promptText,
    target_project: compileData.params_used ? compileData.target_project : null
  };
  // Also pass target_project from the form if available
  var targetInput = document.getElementById("compile-target_project");
  if (targetInput) {
    body.target_project = targetInput.value;
  }

  fetch("/api/prompt-compiler/assign-handoff-id", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  })
    .then(function (res) {
      if (!res.ok) return res.json().then(function (e) { throw e; });
      return res.json();
    })
    .then(function (result) {
      clear(dispatchDiv);

      // Success badge
      var successP = el("p", null);
      var successBadge = el("span", "dpmtf-badge dpmtf-badge-success");
      successBadge.textContent = "✅ " + lbl("lbl_handoff_ready", "Handoff {ID} ready").replace("{ID}", result.handoff_id);
      successP.appendChild(successBadge);
      dispatchDiv.appendChild(successP);

      // File path info
      dispatchDiv.appendChild(el("p", "dpmtf-small",
        lbl("lbl_handoff_file_written", "File written:") + " " + result.handoff_path));

      // Dispatch command with copy button
      var cmdRow = el("div", null);
      cmdRow.style.marginTop = "8px";
      var cmdLabel = el("span", "dpmtf-label", lbl("lbl_dispatch_command", "Dispatch command:"));
      cmdRow.appendChild(cmdLabel);

      var cmdPre = el("pre", null);
      cmdPre.style.whiteSpace = "pre-wrap";
      cmdPre.style.fontSize = "0.85em";
      cmdPre.style.background = "#0d1117";
      cmdPre.style.padding = "8px";
      cmdPre.style.borderRadius = "4px";
      cmdPre.style.marginTop = "4px";
      cmdPre.textContent = result.dispatch_command;
      cmdRow.appendChild(cmdPre);
      dispatchDiv.appendChild(cmdRow);

      // Copy dispatch command button
      var copyCmdBtn = el("button", "dpmtf-btn dpmtf-small");
      copyCmdBtn.textContent = lbl("lbl_btn_copy_command", "Copy Command");
      copyCmdBtn.onclick = function () {
        navigator.clipboard.writeText(result.dispatch_command).then(function () {
          copyCmdBtn.textContent = lbl("lbl_btn_copied", "Copied!");
          setTimeout(function () {
            copyCmdBtn.textContent = lbl("lbl_btn_copy_command", "Copy Command");
          }, 2000);
        });
      };
      dispatchDiv.appendChild(copyCmdBtn);

      // Update the displayed prompt with the real ID
      var outputDiv = document.getElementById("compile-output");
      var preElement = outputDiv ? outputDiv.querySelector("pre") : null;
      if (preElement && result.prompt) {
        preElement.textContent = result.prompt;
      }
    })
    .catch(function (err) {
      clear(dispatchDiv);
      dispatchDiv.appendChild(el("p", "dpmtf-error",
        lbl("lbl_status_error_prefix", "Error: ") + escapeHtml(err.detail || err.message || "Failed to assign handoff ID")));
    });
}

/* ── 10. Init ──────────────────────────────────────── */
function onReady() {
  loadLabels();
  // Language dropdown handler
  var langDropdown = document.getElementById("lang-dropdown");
  if (langDropdown) {
    langDropdown.addEventListener("change", function () {
      switchLanguage(this.value);
    });
  }
  loadPanelStructure();
  initPanelGroupToggles();
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
