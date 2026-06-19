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

      // Initialize language dropdown from database
      initLanguageDropdown(currentLocale);

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
      if (typeof loadProjectPlans === "function") loadProjectPlans();
      if (typeof loadBridgeSetup === "function") loadBridgeSetup();
    })
    .catch(function (err) {
      console.warn("Failed to switch language:", err.message);
    });
}

function initLanguageDropdown(userLocale) {
  var dropdown = document.getElementById("lang-dropdown");
  if (!dropdown) return;

  // Set meta locale dynamically
  var metaLocale = document.querySelector('meta[name="locale"]');
  if (metaLocale) metaLocale.content = userLocale;

  fetch("/api/available-languages")
    .then(function (res) {
      if (!res.ok) throw new Error("HTTP " + res.status);
      return res.json();
    })
    .then(function (data) {
      clear(dropdown);
      (data.languages || []).forEach(function (lang) {
        var option = el("option", null);
        option.value = lang.locale;
        option.textContent = lang.display_name;
        if (lang.locale === userLocale) option.selected = true;
        dropdown.appendChild(option);
      });
      // Set onchange handler
      dropdown.onchange = function () { switchLanguage(this.value); };
    })
    .catch(function (err) {
      console.warn("Failed to load language list:", err.message);
      // Dropdown keeps existing options as fallback
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



/* ── Compiler Form with Deployment Strategy first & conditional visibility ── */
function buildCompilerForm() {
  var container = document.getElementById("template-manager-content");
  if (!container) return;
  clear(container);

  // ── 1. Deployment Strategy (first — controls visibility) ──
  var depDiv = el("div", "dpmtf-form-group");
  depDiv.id = "compile-group-deployment";
  depDiv.appendChild(el("label", "dpmtf-label", lbl("lbl_compiler_deployment_strategy", "Deployment Strategy")));
  var depSelect = el("select", null);
  depSelect.id = "compile-deployment_strategy";
  var emptyOpt = document.createElement("option");
  emptyOpt.value = "";
  emptyOpt.textContent = lbl("lbl_compiler_no_deployment", "(none)");
  depSelect.appendChild(emptyOpt);
  ["standard", "accelerated"].forEach(function (val) {
    var opt = document.createElement("option");
    opt.value = val;
    opt.textContent = val;
    depSelect.appendChild(opt);
  });
  depDiv.appendChild(depSelect);
  container.appendChild(depDiv);

  // ── 2. Target Session (hidden when accelerated) ──
  var sessionDiv = el("div", "dpmtf-form-group");
  sessionDiv.id = "compile-group-session";
  sessionDiv.appendChild(el("label", "dpmtf-label", lbl("lbl_compiler_target_session", "Target Session")));
  var sessionSelect = el("select", null);
  sessionSelect.id = "compile-target_session";
  [
    ["claude_implementer", lbl("lbl_session_implementer", "Implementer")],
    ["claude_review", lbl("lbl_session_review", "Review")],
    ["claude_architect", lbl("lbl_session_architect", "Architect")]
  ].forEach(function (pair) {
    var opt = document.createElement("option");
    opt.value = pair[0];
    opt.textContent = pair[1];
    sessionSelect.appendChild(opt);
  });
  sessionDiv.appendChild(sessionSelect);
  container.appendChild(sessionDiv);

  // ── 3. Target Project (auto-set when accelerated) ──
  var projDiv = el("div", "dpmtf-form-group");
  projDiv.id = "compile-group-project";
  projDiv.appendChild(el("label", "dpmtf-label", lbl("lbl_compiler_target_project", "Target Project")));
  var projInput = el("input", null);
  projInput.type = "text";
  projInput.id = "compile-target_project";
  projInput.placeholder = lbl("lbl_compiler_project_placeholder", "/home/svend/DPMtF-WebUI");
  projDiv.appendChild(projInput);
  container.appendChild(projDiv);

  // ── 4. Phase Key (hidden when accelerated) ──
  var phaseDiv = el("div", "dpmtf-form-group");
  phaseDiv.id = "compile-group-phase";
  phaseDiv.appendChild(el("label", "dpmtf-label", lbl("lbl_compiler_phase_key", "Phase Key")));
  var phaseInput = el("input", null);
  phaseInput.type = "text";
  phaseInput.id = "compile-phase_key";
  phaseInput.placeholder = lbl("lbl_compiler_phase_placeholder", "spor-g-test");
  phaseDiv.appendChild(phaseInput);
  container.appendChild(phaseDiv);

  // ── 5. Goal (hidden when accelerated) ──
  var goalDiv = el("div", "dpmtf-form-group");
  goalDiv.id = "compile-group-goal";
  goalDiv.appendChild(el("label", "dpmtf-label", lbl("lbl_compiler_goal", "Goal")));
  var goalTextarea = el("textarea", null);
  goalTextarea.id = "compile-goal";
  goalTextarea.rows = 4;
  goalTextarea.placeholder = lbl("lbl_compiler_goal_placeholder", "Describe the implementation task...");
  goalDiv.appendChild(goalTextarea);
  container.appendChild(goalDiv);

  // ── 6. Accelerated fields (visible only when accelerated) ──
  // New webui name
  var nameDiv = el("div", "dpmtf-form-group");
  nameDiv.id = "compile-group-accel-name";
  nameDiv.style.display = "none";
  nameDiv.appendChild(el("label", "dpmtf-label", lbl("lbl_compiler_new_webui_name", "New webui")));
  var nameInput = el("input", null);
  nameInput.type = "text";
  nameInput.id = "compile-accel-name";
  nameInput.maxLength = 10;
  nameInput.placeholder = "mywebui";
  nameDiv.appendChild(nameInput);
  container.appendChild(nameDiv);

  // Port
  var portDiv = el("div", "dpmtf-form-group");
  portDiv.id = "compile-group-accel-port";
  portDiv.style.display = "none";
  portDiv.appendChild(el("label", "dpmtf-label", lbl("lbl_compiler_new_webui_port", "Port")));
  var portInput = el("input", null);
  portInput.type = "number";
  portInput.id = "compile-accel-port";
  portInput.min = 9132;
  portInput.max = 9199;
  portInput.placeholder = "9136";
  portDiv.appendChild(portInput);
  container.appendChild(portDiv);

  // Title
  var titleDiv = el("div", "dpmtf-form-group");
  titleDiv.id = "compile-group-accel-title";
  titleDiv.style.display = "none";
  titleDiv.appendChild(el("label", "dpmtf-label", lbl("lbl_compiler_new_webui_title", "Title")));
  var titleInput = el("input", null);
  titleInput.type = "text";
  titleInput.id = "compile-accel-title";
  titleInput.placeholder = "My Project";
  titleDiv.appendChild(titleInput);
  container.appendChild(titleDiv);

  // ── 7. Scope & Gate confirmation (hidden when accelerated) ──
  var scopeDiv = el("div", "dpmtf-form-group");
  scopeDiv.id = "compile-group-scope";
  var scopeLabel = el("label", "dpmtf-label", null);
  var scopeCheckbox = el("input", null);
  scopeCheckbox.type = "checkbox";
  scopeCheckbox.id = "compile-scope_gate_confirmed";
  scopeLabel.appendChild(scopeCheckbox);
  scopeLabel.appendChild(document.createTextNode(lbl("lbl_compiler_scope_gate", " Have you considered scope and gate scope?")));
  scopeDiv.appendChild(scopeLabel);
  container.appendChild(scopeDiv);

  // ── 8. Allowed files (hidden when accelerated) ──
  var allowedDiv = el("div", "dpmtf-form-group");
  allowedDiv.id = "compile-group-allowed";
  allowedDiv.appendChild(el("label", "dpmtf-label", lbl("lbl_compiler_allowed_files", "Allowed files (optional, one per line)")));
  var allowedTextarea = el("textarea", null);
  allowedTextarea.id = "compile-allowed_files";
  allowedTextarea.rows = 3;
  allowedTextarea.placeholder = lbl("lbl_compiler_allowed_placeholder", "(blank = Review verifies)");
  allowedDiv.appendChild(allowedTextarea);
  container.appendChild(allowedDiv);

  // ── 9. Forbidden files (hidden when accelerated) ──
  var forbiddenDiv = el("div", "dpmtf-form-group");
  forbiddenDiv.id = "compile-group-forbidden";
  forbiddenDiv.appendChild(el("label", "dpmtf-label", lbl("lbl_compiler_forbidden_files", "Forbidden files (optional, one per line)")));
  var forbiddenTextarea = el("textarea", null);
  forbiddenTextarea.id = "compile-forbidden_files";
  forbiddenTextarea.rows = 3;
  forbiddenTextarea.placeholder = lbl("lbl_compiler_forbidden_placeholder", "(blank = none specified)");
  forbiddenDiv.appendChild(forbiddenTextarea);
  container.appendChild(forbiddenDiv);

  // ── Output area (shared for compile and accelerated) ──
  var outputDiv = el("div", null);
  outputDiv.id = "compile-output";
  outputDiv.style.display = "none";
  container.appendChild(outputDiv);

  // ── Warning area ──
  var warningDiv = el("div", null);
  warningDiv.id = "compile-warning";
  warningDiv.style.display = "none";
  container.appendChild(warningDiv);

  // ── Compile Prompt button (hidden when accelerated) ──
  var compileBtn = el("button", "dpmtf-btn dpmtf-btn-primary");
  compileBtn.id = "compile-btn-submit";
  compileBtn.textContent = lbl("lbl_tpl_compile_prompt", "Compile Prompt");
  compileBtn.onclick = compilePromptV2;
  container.appendChild(compileBtn);

  // ── Create New WebUI button (visible only when accelerated) ──
  var createBtn = el("button", "dpmtf-btn dpmtf-btn-primary");
  createBtn.id = "compile-btn-create-webui";
  createBtn.style.display = "none";
  createBtn.textContent = lbl("lbl_compiler_create_webui_btn", "Create New WebUI");
  createBtn.onclick = createNewWebUI;
  container.appendChild(createBtn);

  // ── Start WebUI Server button (replaces Create after success) ──
  var startBtn = el("button", "dpmtf-btn dpmtf-btn-primary");
  startBtn.id = "compile-btn-start-server";
  startBtn.style.display = "none";
  startBtn.textContent = lbl("lbl_compiler_start_server_btn", "Start WebUI Server");
  container.appendChild(startBtn);

  // ── Deployment Strategy onchange handler ──
  depSelect.onchange = function () {
    var isAccelerated = depSelect.value === "accelerated";

    // Standard fields: hide when accelerated
    var standardIds = [
      "compile-group-session", "compile-group-phase", "compile-group-goal",
      "compile-group-scope", "compile-group-allowed", "compile-group-forbidden"
    ];
    standardIds.forEach(function (id) {
      var stEl = document.getElementById(id);
      if (stEl) stEl.style.display = isAccelerated ? "none" : "";
    });

    // Accelerated fields: show only when accelerated
    var accelIds = [
      "compile-group-accel-name", "compile-group-accel-port", "compile-group-accel-title"
    ];
    accelIds.forEach(function (id) {
      var acEl = document.getElementById(id);
      if (acEl) acEl.style.display = isAccelerated ? "" : "none";
    });

    // Buttons
    var compileBtnEl = document.getElementById("compile-btn-submit");
    var createBtnEl = document.getElementById("compile-btn-create-webui");
    var startBtnEl = document.getElementById("compile-btn-start-server");
    if (compileBtnEl) compileBtnEl.style.display = isAccelerated ? "none" : "";
    if (createBtnEl) createBtnEl.style.display = isAccelerated ? "" : "none";
    if (startBtnEl) startBtnEl.style.display = "none"; // always hide on switch

    // Target Project: auto-set to Father project when accelerated
    var projEl = document.getElementById("compile-target_project");
    if (isAccelerated && projEl) {
      projEl.value = projEl.placeholder || lbl("lbl_compiler_project_placeholder", "");
      projEl.readOnly = true;
    } else if (projEl) {
      projEl.readOnly = false;
    }

    // Reset hidden fields
    if (isAccelerated) {
      // Reset standard fields
      var sessionEl = document.getElementById("compile-target_session");
      if (sessionEl) sessionEl.value = "claude_implementer";
      var phaseEl = document.getElementById("compile-phase_key");
      if (phaseEl) phaseEl.value = "";
      var goalEl = document.getElementById("compile-goal");
      if (goalEl) goalEl.value = "";
      var scopeEl = document.getElementById("compile-scope_gate_confirmed");
      if (scopeEl) scopeEl.checked = false;
      var allowedEl = document.getElementById("compile-allowed_files");
      if (allowedEl) allowedEl.value = "";
      var forbiddenEl = document.getElementById("compile-forbidden_files");
      if (forbiddenEl) forbiddenEl.value = "";
    } else {
      // Reset accelerated fields
      var nameEl = document.getElementById("compile-accel-name");
      if (nameEl) nameEl.value = "";
      var portEl = document.getElementById("compile-accel-port");
      if (portEl) portEl.value = "";
      var titleEl = document.getElementById("compile-accel-title");
      if (titleEl) titleEl.value = "";
    }

    // Hide output/warning on switch
    var outEl = document.getElementById("compile-output");
    if (outEl) { outEl.style.display = "none"; clear(outEl); }
    var warnEl = document.getElementById("compile-warning");
    if (warnEl) { warnEl.style.display = "none"; clear(warnEl); }
  };
}

function compilePromptV2() {
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

  // Collect only the 8 simplified fields
  var body = {};
  var el_target_session = document.getElementById("compile-target_session");
  if (el_target_session) body.target_session = el_target_session.value;

  var el_target_project = document.getElementById("compile-target_project");
  if (el_target_project) body.target_project = el_target_project.value;

  var el_phase_key = document.getElementById("compile-phase_key");
  if (el_phase_key) body.phase_key = el_phase_key.value;

  var el_goal = document.getElementById("compile-goal");
  if (el_goal) body.goal = el_goal.value;

  var el_deployment = document.getElementById("compile-deployment_strategy");
  if (el_deployment) body.deployment_strategy = el_deployment.value;

  var el_scope_gate = document.getElementById("compile-scope_gate_confirmed");
  if (el_scope_gate) body.scope_gate_confirmed = el_scope_gate.checked;

  var el_allowed = document.getElementById("compile-allowed_files");
  if (el_allowed) body.allowed_files = el_allowed.value;

  var el_forbidden = document.getElementById("compile-forbidden_files");
  if (el_forbidden) body.forbidden_files = el_forbidden.value;

  fetch("/api/prompt-compiler/compile", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  })
    .then(function (res) {
      if (!res.ok) {
        return res.json().then(function (errData) {
          throw { status: res.status, errors: errData.errors || [] };
        });
      }
      return res.json();
    })
    .then(function (data) {
      clear(outputDiv);
      outputDiv.appendChild(
        el("h4", null, lbl("lbl_tpl_compiled_prompt", "Compiled Prompt"))
      );
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

      // Copy button
      var copyBtn = el("button", "dpmtf-btn dpmtf-small");
      copyBtn.textContent = lbl("lbl_btn_copy_prompt", "Copy Prompt");
      copyBtn.onclick = function () {
        navigator.clipboard.writeText(data.prompt).then(function () {
          copyBtn.textContent = lbl("lbl_btn_copied", "Copied!");
          setTimeout(function () { copyBtn.textContent = lbl("lbl_btn_copy_prompt", "Copy Prompt"); }, 2000);
        });
      };
      outputDiv.appendChild(copyBtn);

      // Assign Handoff ID button
      var assignBtn = el("button", "dpmtf-btn dpmtf-btn-primary");
      assignBtn.textContent = lbl("lbl_btn_assign_handoff_id", "Assign Handoff ID");
      assignBtn.style.marginLeft = "8px";
      assignBtn.onclick = function () { assignHandoffId(data.prompt, data); };
      outputDiv.appendChild(assignBtn);

      var dispatchDiv = el("div", null);
      dispatchDiv.id = "dispatch-info";
      dispatchDiv.style.display = "none";
      dispatchDiv.style.marginTop = "12px";
      outputDiv.appendChild(dispatchDiv);
    })
    .catch(function (err) {
      clear(outputDiv);
      if (err.errors && err.errors.length) {
        outputDiv.appendChild(
          el("h4", "dpmtf-error", lbl("lbl_compile_validation_errors", "Validation Errors"))
        );
        err.errors.forEach(function (fieldErr) {
          var errMsg = el("p", "dpmtf-error-text");
          errMsg.textContent = "\u274C " + fieldErr.error;
          errMsg.style.color = "#f85149";
          errMsg.style.margin = "4px 0";
          outputDiv.appendChild(errMsg);
          var inputEl = document.getElementById("compile-" + fieldErr.field_key);
          if (inputEl) {
            inputEl.style.borderColor = "#f85149";
            inputEl.classList.add("dpmtf-field-error");
          }
        });
      } else {
        outputDiv.appendChild(
          el("p", "dpmtf-error", lbl("lbl_status_error_prefix", "Error: ") + (err.message || "Compilation failed"))
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

/* ── Accelerated WebUI Factory: Create New WebUI ── */
function createNewWebUI() {
  var outputDiv = document.getElementById("compile-output");
  if (!outputDiv) return;
  outputDiv.style.display = "block";
  clear(outputDiv);
  outputDiv.appendChild(
    el("p", "dpmtf-muted", lbl("lbl_status_compiling", "Compiling..."))
  );

  var nameEl = document.getElementById("compile-accel-name");
  var portEl = document.getElementById("compile-accel-port");
  var titleEl = document.getElementById("compile-accel-title");

  document.querySelectorAll(".dpmtf-field-error").forEach(function (errEl) {
    errEl.style.borderColor = "";
    errEl.classList.remove("dpmtf-field-error");
  });
  document.querySelectorAll(".dpmtf-error-text").forEach(function (msgEl) {
    msgEl.remove();
  });

  var hasError = false;
  if (!nameEl || !nameEl.value.trim()) {
    highlightField(nameEl, lbl("lbl_compiler_field_required", "This field is required"));
    hasError = true;
  }
  if (!portEl || !portEl.value) {
    highlightField(portEl, lbl("lbl_compiler_field_required", "This field is required"));
    hasError = true;
  }
  if (!titleEl || !titleEl.value.trim()) {
    highlightField(titleEl, lbl("lbl_compiler_field_required", "This field is required"));
    hasError = true;
  }
  if (hasError) return;

  var portNum = parseInt(portEl.value, 10);

  fetch("/api/create-webui/initialize", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name: nameEl.value.trim(),
      port: portNum,
      title: titleEl.value.trim()
    })
  })
    .then(function (res) {
      return res.json().then(function (data) {
        if (!res.ok) throw data;
        return data;
      });
    })
    .then(function (data) {
      clear(outputDiv);

      var pre = el("pre", null);
      pre.style.whiteSpace = "pre-wrap";
      pre.style.fontSize = "0.85em";
      pre.style.background = "#0d1117";
      pre.style.padding = "12px";
      pre.style.borderRadius = "4px";
      pre.style.maxHeight = "500px";
      pre.style.overflowY = "auto";
      if (data.success) {
        pre.textContent = data.output;
        outputDiv.appendChild(pre);

        var successP = el("p", null);
        var badge = el("span", "dpmtf-badge dpmtf-badge-success");
        badge.textContent = lbl("lbl_compiler_webui_created", "WebUI project created successfully");
        successP.appendChild(badge);
        outputDiv.appendChild(successP);

        // Hide Create button, show Start Server button
        var createBtnEl = document.getElementById("compile-btn-create-webui");
        var startBtnEl = document.getElementById("compile-btn-start-server");
        if (createBtnEl) createBtnEl.style.display = "none";
        if (startBtnEl) {
          startBtnEl.style.display = "";
          var pDir = data.project_dir;
          var pPort = data.port;
          startBtnEl.onclick = function () { startWebUIServer(pDir, pPort); };
        }

        // Governance reminder
        var govP = el("p", "dpmtf-muted");
        govP.textContent = lbl("lbl_compiler_governance_reminder", "Governance files to create in docs/dpmtf/:");
        outputDiv.appendChild(govP);

      } else {
        pre.textContent = data.error || (data.detail || "Unknown error");
        pre.classList.add("dpmtf-error");
        outputDiv.appendChild(pre);
      }
    })
    .catch(function (err) {
      clear(outputDiv);
      if (err.errors && err.errors.length) {
        outputDiv.appendChild(
          el("h4", "dpmtf-error", lbl("lbl_compile_validation_errors", "Validation Errors"))
        );
        err.errors.forEach(function (fieldErr) {
          var errMsg = el("p", "dpmtf-error-text");
          errMsg.textContent = "\u274C " + fieldErr.error;
          errMsg.style.color = "#f85149";
          errMsg.style.margin = "4px 0";
          outputDiv.appendChild(errMsg);
        });
      } else {
        var errP = el("p", "dpmtf-error");
        errP.textContent = lbl("lbl_compiler_script_error", "Script error: ") + escapeHtml(err.detail || err.message || "Initialization failed");
        outputDiv.appendChild(errP);
      }
    });
}

function highlightField(inputEl, message) {
  if (!inputEl) return;
  inputEl.style.borderColor = "#f85149";
  inputEl.classList.add("dpmtf-field-error");
  var errDiv = document.createElement("span");
  errDiv.className = "dpmtf-error-text";
  errDiv.textContent = message;
  errDiv.style.color = "#f85149";
  errDiv.style.fontSize = "0.8em";
  errDiv.style.display = "block";
  errDiv.style.marginTop = "2px";
  inputEl.parentNode.appendChild(errDiv);
}

/* ── Accelerated WebUI Factory: Start Server ── */
function startWebUIServer(projectDir, port) {
  var outputDiv = document.getElementById("compile-output");
  if (!outputDiv) return;
  clear(outputDiv);
  outputDiv.appendChild(
    el("p", "dpmtf-muted", lbl("lbl_status_starting_server", "Starting server..."))
  );

  fetch("/api/create-webui/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      project_dir: projectDir,
      port: port
    })
  })
    .then(function (res) {
      return res.json().then(function (data) {
        if (!res.ok) throw data;
        return data;
      });
    })
    .then(function (data) {
      clear(outputDiv);

      var successP = el("p", null);
      var badge = el("span", "dpmtf-badge dpmtf-badge-success");
      badge.textContent = "✅ " + (data.message || lbl("lbl_status_server_started", "Server started"));
      successP.appendChild(badge);
      outputDiv.appendChild(successP);

      var link = document.createElement("a");
      link.href = data.url;
      link.target = "_blank";
      link.textContent = lbl("lbl_compiler_open_webui", "Open WebUI") + " (" + data.url + ")";
      link.style.marginTop = "8px";
      link.style.display = "inline-block";
      outputDiv.appendChild(link);

      var govP = el("p", "dpmtf-muted");
      govP.textContent = lbl("lbl_compiler_governance_reminder", "Governance files to create in docs/dpmtf/:");
      govP.style.marginTop = "12px";
      outputDiv.appendChild(govP);
    })
    .catch(function (err) {
      clear(outputDiv);
      var errP = el("p", "dpmtf-error");
      errP.textContent = lbl("lbl_status_error_prefix", "Error: ") + escapeHtml(err.detail || err.message || "Failed to start server");
      outputDiv.appendChild(errP);
    });
}

/* ── 11. Bridge Setup Panel ────────────────────────── */
function loadBridgeStatus() {
  var container = document.getElementById("bridge-status-content");
  if (!container) return;
  clear(container);

  fetch("/api/bridge-v2/status")
    .then(function (res) { return res.json(); })
    .then(function (data) {
      var badge = el("span", "dpmtf-badge " +
        (data.available ? "dpmtf-badge-success" : "dpmtf-badge-danger"));
      badge.textContent = data.available
        ? lbl("lbl_bridge_status_available", "Bridge configuration available")
        : lbl("lbl_bridge_inactive", "Inactive");
      container.appendChild(badge);
      if (data.tables && data.tables.length) {
        var info = el("div", "dpmtf-small", null);
        info.textContent = data.tables.join(", ");
        container.appendChild(info);
      }
    })
    .catch(function (err) {
      var errP = el("p", "dpmtf-error");
      errP.textContent = lbl("lbl_status_error_prefix", "Error: ") + escapeHtml(err.message);
      container.appendChild(errP);
    });
}

function loadBridgeRoles() {
  var container = document.getElementById("bridge-roles-list-container");
  if (!container) return;
  clear(container);

  fetch("/api/bridge-v2/roles")
    .then(function (res) { return res.json(); })
    .then(function (data) {
      var roles = data.roles || [];
      if (!roles.length) {
        container.appendChild(el("p", "dpmtf-muted", lbl("lbl_bridge_no_roles", "No roles configured")));
        return;
      }
      roles.forEach(function (role) {
        container.appendChild(renderRoleCard(role));
      });
    })
    .catch(function (err) {
      var errP = el("p", "dpmtf-error");
      errP.textContent = lbl("lbl_status_error_prefix", "Error: ") + escapeHtml(err.message);
      container.appendChild(errP);
    });
}

function renderRoleCard(role) {
  var card = el("div", "dpmtf-card");

  // Header: role key + status badge
  var header = el("div", null);
  header.style.display = "flex";
  header.style.justifyContent = "space-between";
  header.style.alignItems = "center";
  var h4 = el("h4", null, escapeHtml(role.role_key));
  header.appendChild(h4);

  var badge = el("span", "dpmtf-badge " +
    (role.is_active ? "dpmtf-badge-success" : "dpmtf-badge-danger"));
  badge.textContent = role.is_active
    ? lbl("lbl_bridge_active", "Active")
    : lbl("lbl_bridge_inactive", "Inactive");
  header.appendChild(badge);
  card.appendChild(header);

  // Role details as key-value pairs
  var fields = [
    [lbl("lbl_bridge_tmux_session", "Tmux Session"), role.tmux_session],
    [lbl("lbl_bridge_start_cmd", "Start Command"), role.start_cmd],
    [lbl("lbl_bridge_model_type", "Model Type"), role.model_type],
    [lbl("lbl_bridge_cloud_model", "Cloud Model"), role.cloud_model],
    [lbl("lbl_bridge_ollama_model", "Ollama Model"), role.ollama_model],
  ];
  fields.forEach(function (pair) {
    if (!pair[1]) return;
    var row = el("div", null);
    row.appendChild(el("span", "dpmtf-small", escapeHtml(pair[0]) + ": "));
    row.appendChild(el("span", null, escapeHtml(String(pair[1]))));
    card.appendChild(row);
  });

  // Action buttons: Edit and Delete
  var actions = el("div", null);
  actions.style.marginTop = "8px";

  var editBtn = el("button", "dpmtf-btn");
  editBtn.textContent = lbl("lbl_bridge_edit", "Edit");
  editBtn.onclick = function () { editBridgeRole(role.role_key); };
  actions.appendChild(editBtn);

  var delBtn = el("button", "dpmtf-btn dpmtf-btn-danger");
  delBtn.textContent = lbl("lbl_bridge_delete", "Delete");
  delBtn.onclick = function () { deleteBridgeRole(role.role_key); };
  actions.appendChild(delBtn);

  card.appendChild(actions);
  return card;
}

function loadBridgeFlows() {
  var container = document.getElementById("bridge-flows-list-container");
  if (!container) return;
  clear(container);

  fetch("/api/bridge-v2/flows")
    .then(function (res) { return res.json(); })
    .then(function (data) {
      var flows = data.flows || [];
      if (!flows.length) {
        container.appendChild(el("p", "dpmtf-muted", lbl("lbl_bridge_no_flows", "No flows configured")));
        return;
      }
      flows.forEach(function (flow) {
        fetch("/api/bridge-v2/flows/" + encodeURIComponent(flow.flow_key))
          .then(function (res) { return res.json(); })
          .then(function (fd) {
            container.appendChild(renderFlowCard(fd.flow, fd.steps || []));
          })
          .catch(function () {
            container.appendChild(renderFlowCard(flow, []));
          });
      });
    })
    .catch(function (err) {
      var errP = el("p", "dpmtf-error");
      errP.textContent = lbl("lbl_status_error_prefix", "Error: ") + escapeHtml(err.message);
      container.appendChild(errP);
    });
}

function renderFlowCard(flow, steps) {
  var card = el("div", "dpmtf-card");

  // Header: flow name + badges
  var header = el("div", null);
  header.style.display = "flex";
  header.style.justifyContent = "space-between";
  header.style.alignItems = "center";
  var h4 = el("h4", null, escapeHtml(flow.name || flow.flow_key));
  header.appendChild(h4);

  var badges = el("span", null);
  if (flow.is_default) {
    var defBadge = el("span", "dpmtf-badge dpmtf-badge-warning");
    defBadge.textContent = lbl("lbl_bridge_flow_is_default", "Default");
    badges.appendChild(defBadge);
  }
  var statusBadge = el("span", "dpmtf-badge " +
    (flow.is_active ? "dpmtf-badge-success" : "dpmtf-badge-danger"));
  statusBadge.textContent = flow.is_active
    ? lbl("lbl_bridge_active", "Active")
    : lbl("lbl_bridge_inactive", "Inactive");
  badges.appendChild(statusBadge);
  header.appendChild(badges);
  card.appendChild(header);

  // Flow details
  var details = [
    escapeHtml(flow.flow_key),
    flow.description ? escapeHtml(flow.description) : null,
  ].filter(Boolean).join(" — ");
  card.appendChild(el("p", "dpmtf-small", details));

  // Steps table if any
  if (steps && steps.length) {
    var stepTitle = el("h5", null, lbl("lbl_bridge_steps_title", "Steps"));
    card.appendChild(stepTitle);

    var table = el("table", "dpmtf-table");
    var thead = el("thead", null);
    var thrRow = el("tr", null);
    [
      lbl("lbl_bridge_step_sort_order", "#"),
      lbl("lbl_bridge_step_key", "Key"),
      lbl("lbl_bridge_step_from_role", "From"),
      lbl("lbl_bridge_step_to_role", "To")
    ].forEach(function (h) {
      thrRow.appendChild(el("th", null, h));
    });
    thead.appendChild(thrRow);
    table.appendChild(thead);

    var tbody = el("tbody", null);
    steps.forEach(function (step) {
      var row = el("tr", null);
      row.appendChild(td(String(step.sort_order)));
      row.appendChild(td(escapeHtml(step.step_key)));
      row.appendChild(td(escapeHtml(step.from_role)));
      row.appendChild(td(escapeHtml(step.to_role)));
      tbody.appendChild(row);
    });
    table.appendChild(tbody);
    card.appendChild(table);
  }

  // Action buttons
  var actions = el("div", null);
  actions.style.marginTop = "8px";

  var editBtn = el("button", "dpmtf-btn");
  editBtn.textContent = lbl("lbl_bridge_edit", "Edit");
  editBtn.onclick = function () { editBridgeFlow(flow.flow_key); };
  actions.appendChild(editBtn);

  var delBtn = el("button", "dpmtf-btn dpmtf-btn-danger");
  delBtn.textContent = lbl("lbl_bridge_delete", "Delete");
  delBtn.onclick = function () { deleteBridgeFlow(flow.flow_key); };
  actions.appendChild(delBtn);

  card.appendChild(actions);
  return card;
}

function addBridgeRole() {
  var container = document.getElementById("bridge-roles-list-container");
  if (!container) return;

  var existing = document.getElementById("bridge-role-form");
  if (existing) { existing.remove(); return; }

  var form = el("div", "dpmtf-card");
  form.id = "bridge-role-form";

  var cancelBtn = el("button", "dpmtf-btn");
  cancelBtn.textContent = lbl("lbl_bridge_cancel", "Cancel");
  cancelBtn.onclick = function () { form.remove(); };

  var saveBtn = el("button", "dpmtf-btn dpmtf-btn-primary");
  saveBtn.textContent = lbl("lbl_bridge_save", "Save");
  saveBtn.onclick = function () {
    var rk = document.getElementById("bridge-input-role_key").value.trim();
    var ts = document.getElementById("bridge-input-tmux_session").value.trim();
    if (!rk || !ts) { alert(lbl("lbl_bridge_role_key", "Role Key") + " and " + lbl("lbl_bridge_tmux_session", "Tmux Session") + " are required."); return; }

    var body = { role_key: rk, tmux_session: ts };
    var mt = document.getElementById("bridge-input-model_type");
    if (mt) body.model_type = mt.value;
    var cm = document.getElementById("bridge-input-cloud_model");
    if (cm && cm.value.trim()) body.cloud_model = cm.value.trim();
    var om = document.getElementById("bridge-input-ollama_model");
    if (om && om.value.trim()) body.ollama_model = om.value.trim();

    fetch("/api/bridge-v2/roles", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    })
      .then(function (res) {
        if (!res.ok) throw new Error("HTTP " + res.status);
        return res.json();
      })
      .then(function (data) {
        alert(lbl("lbl_bridge_created", "Successfully created") + ": " + data.role_key);
        loadBridgeRoles();
      })
      .catch(function (err) {
        alert(lbl("lbl_status_error_prefix", "Error: ") + escapeHtml(err.message));
      });
  };

  form.appendChild(el("h4", null, lbl("lbl_bridge_role_add", "Add Role")));

  var fields = [
    ["bridge-input-role_key", "text", lbl("lbl_bridge_role_key", "Role Key"), "role_key"],
    ["bridge-input-tmux_session", "text", lbl("lbl_bridge_tmux_session", "Tmux Session"), "claude_..."],
    ["bridge-input-start_cmd", "text", lbl("lbl_bridge_start_cmd", "Start Command"), ""],
  ];
  fields.forEach(function (f) {
    var div = el("div", "dpmtf-form-group");
    div.appendChild(el("label", "dpmtf-label", f[2]));
    var input = el("input", null);
    input.id = f[0];
    input.type = f[1];
    input.placeholder = f[3];
    div.appendChild(input);
    form.appendChild(div);
  });

  // Model type select
  var mtDiv = el("div", "dpmtf-form-group");
  mtDiv.appendChild(el("label", "dpmtf-label", lbl("lbl_bridge_model_type", "Model Type")));
  var mtSelect = el("select", null);
  mtSelect.id = "bridge-input-model_type";
  [["ollama", lbl("lbl_bridge_ollama_option", "Ollama")], ["cloud", lbl("lbl_bridge_cloud_option", "Cloud")]].forEach(function (pair) {
    var opt = document.createElement("option");
    opt.value = pair[0];
    opt.textContent = pair[1];
    mtSelect.appendChild(opt);
  });
  mtDiv.appendChild(mtSelect);
  form.appendChild(mtDiv);

  // Model name inputs
  [["bridge-input-cloud_model", lbl("lbl_bridge_cloud_model", "Cloud Model"), ""],
   ["bridge-input-ollama_model", lbl("lbl_bridge_ollama_model", "Ollama Model"), ""]].forEach(function (f) {
    var div = el("div", "dpmtf-form-group");
    div.appendChild(el("label", "dpmtf-label", f[1]));
    var input = el("input", null);
    input.id = f[0];
    input.type = "text";
    input.placeholder = f[2];
    div.appendChild(input);
    form.appendChild(div);
  });

  var btnRow = el("div", null);
  btnRow.appendChild(saveBtn);
  btnRow.appendChild(cancelBtn);
  form.appendChild(btnRow);

  container.insertBefore(form, container.firstChild);
}

function addBridgeFlow() {
  var container = document.getElementById("bridge-flows-list-container");
  if (!container) return;

  var existing = document.getElementById("bridge-flow-form");
  if (existing) { existing.remove(); return; }

  var form = el("div", "dpmtf-card");
  form.id = "bridge-flow-form";

  var cancelBtn = el("button", "dpmtf-btn");
  cancelBtn.textContent = lbl("lbl_bridge_cancel", "Cancel");
  cancelBtn.onclick = function () { form.remove(); };

  var saveBtn = el("button", "dpmtf-btn dpmtf-btn-primary");
  saveBtn.textContent = lbl("lbl_bridge_save", "Save");
  saveBtn.onclick = function () {
    var fk = document.getElementById("bridge-input-flow_key").value.trim();
    var nm = document.getElementById("bridge-input-name").value.trim();
    if (!fk || !nm) { alert(lbl("lbl_bridge_flow_key", "Flow Key") + " and " + lbl("lbl_bridge_flow_name", "Name") + " are required."); return; }

    var body = { flow_key: fk, name: nm };
    var desc = document.getElementById("bridge-input-description");
    if (desc && desc.value.trim()) body.description = desc.value.trim();
    body.steps = [];

    fetch("/api/bridge-v2/flows", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    })
      .then(function (res) {
        if (!res.ok) throw new Error("HTTP " + res.status);
        return res.json();
      })
      .then(function (data) {
        alert(lbl("lbl_bridge_created", "Successfully created") + ": " + data.flow_key);
        loadBridgeFlows();
      })
      .catch(function (err) {
        alert(lbl("lbl_status_error_prefix", "Error: ") + escapeHtml(err.message));
      });
  };

  form.appendChild(el("h4", null, lbl("lbl_bridge_flow_add", "Add Flow")));

  [["bridge-input-flow_key", lbl("lbl_bridge_flow_key", "Flow Key"), ""],
   ["bridge-input-name", lbl("lbl_bridge_flow_name", "Name"), ""],
   ["bridge-input-description", lbl("lbl_bridge_flow_description", "Description"), ""]].forEach(function (f) {
    var div = el("div", "dpmtf-form-group");
    div.appendChild(el("label", "dpmtf-label", f[1]));
    var input = el("input", null);
    input.id = f[0];
    input.type = "text";
    input.placeholder = f[2];
    div.appendChild(input);
    form.appendChild(div);
  });

  var btnRow = el("div", null);
  btnRow.appendChild(saveBtn);
  btnRow.appendChild(cancelBtn);
  form.appendChild(btnRow);

  container.insertBefore(form, container.firstChild);
}

function deleteBridgeRole(roleKey) {
  if (!confirm(escapeHtml(roleKey) + "?")) return;
  fetch("/api/bridge-v2/roles/" + encodeURIComponent(roleKey), { method: "DELETE" })
    .then(function (res) { return res.json(); })
    .then(function () {
      alert(lbl("lbl_bridge_deleted", "Successfully deleted") + ": " + roleKey);
      loadBridgeRoles();
    })
    .catch(function (err) {
      alert(lbl("lbl_status_error_prefix", "Error: ") + escapeHtml(err.message));
    });
}

function deleteBridgeFlow(flowKey) {
  if (!confirm(escapeHtml(flowKey) + "?")) return;
  fetch("/api/bridge-v2/flows/" + encodeURIComponent(flowKey), { method: "DELETE" })
    .then(function (res) { return res.json(); })
    .then(function () {
      alert(lbl("lbl_bridge_deleted", "Successfully deleted") + ": " + flowKey);
      loadBridgeFlows();
    })
    .catch(function (err) {
      alert(lbl("lbl_status_error_prefix", "Error: ") + escapeHtml(err.message));
    });
}

function editBridgeRole(roleKey) {
  fetch("/api/bridge-v2/roles/" + encodeURIComponent(roleKey))
    .then(function (res) { return res.json(); })
    .then(function (data) {
      var role = data.role;
      var newSession = prompt(lbl("lbl_bridge_tmux_session", "Tmux Session") + ":", role.tmux_session);
      if (newSession === null) return;

      var body = {};
      if (newSession !== role.tmux_session) body.tmux_session = newSession;
      if (!Object.keys(body).length) return;

      fetch("/api/bridge-v2/roles/" + encodeURIComponent(roleKey), {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
      })
        .then(function (res) { return res.json(); })
        .then(function () {
          alert(lbl("lbl_bridge_updated", "Successfully updated") + ": " + roleKey);
          loadBridgeRoles();
        })
        .catch(function (err) {
          alert(lbl("lbl_status_error_prefix", "Error: ") + escapeHtml(err.message));
        });
    })
    .catch(function (err) {
      alert(lbl("lbl_status_error_prefix", "Error: ") + escapeHtml(err.message));
    });
}

function editBridgeFlow(flowKey) {
  fetch("/api/bridge-v2/flows/" + encodeURIComponent(flowKey))
    .then(function (res) { return res.json(); })
    .then(function (data) {
      var flow = data.flow;
      var newName = prompt(lbl("lbl_bridge_flow_name", "Name") + ":", flow.name);
      if (newName === null) return;

      var body = {};
      if (newName !== flow.name) body.name = newName;
      if (!Object.keys(body).length) return;

      fetch("/api/bridge-v2/flows/" + encodeURIComponent(flowKey), {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
      })
        .then(function (res) { return res.json(); })
        .then(function () {
          alert(lbl("lbl_bridge_updated", "Successfully updated") + ": " + flowKey);
          loadBridgeFlows();
        })
        .catch(function (err) {
          alert(lbl("lbl_status_error_prefix", "Error: ") + escapeHtml(err.message));
        });
    })
    .catch(function (err) {
      alert(lbl("lbl_status_error_prefix", "Error: ") + escapeHtml(err.message));
    });
}

function buildBridgeExport() {
  var container = document.getElementById("bridge-export-content");
  if (!container) return;
  clear(container);

  [
    ["all", lbl("lbl_bridge_export_all", "Export All")],
    ["roles", lbl("lbl_bridge_export_roles", "Export Roles")],
    ["flows", lbl("lbl_bridge_export_flows", "Export Flows")]
  ].forEach(function (pair) {
    var btn = el("button", "dpmtf-btn");
    btn.textContent = pair[1];
    btn.onclick = function () { exportBridge(pair[0]); };
    container.appendChild(btn);
  });

  var outputDiv = el("pre", null);
  outputDiv.id = "bridge-export-output";
  outputDiv.style.whiteSpace = "pre-wrap";
  outputDiv.style.fontSize = "0.85em";
  outputDiv.style.background = "#0d1117";
  outputDiv.style.padding = "8px";
  outputDiv.style.borderRadius = "4px";
  outputDiv.style.marginTop = "8px";
  outputDiv.style.maxHeight = "300px";
  outputDiv.style.overflowY = "auto";
  container.appendChild(outputDiv);
}

function exportBridge(type) {
  var outputDiv = document.getElementById("bridge-export-output");
  if (!outputDiv) return;
  outputDiv.textContent = lbl("lbl_status_loading", "Loading...");

  fetch("/api/bridge-v2/export", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ type: type })
  })
    .then(function (res) { return res.json(); })
    .then(function (data) {
      outputDiv.textContent = JSON.stringify(data.data || data, null, 2);
    })
    .catch(function (err) {
      outputDiv.textContent = lbl("lbl_status_error_prefix", "Error: ") + escapeHtml(err.message);
    });
}

/* ── Steps CRUD (Fase 4) ─────────────────────────────── */
var _bridgeStepsFlowKey = null;
var _bridgeStepsMetadata = null;
var _bridgeEditingStepId = null;

function renderStepCard(step, meta) {
  var card = el("div", "dpmtf-card");

  // Header: step_key + status badge
  var header = el("div", null);
  header.style.display = "flex";
  header.style.justifyContent = "space-between";
  header.style.alignItems = "center";
  var h4 = el("h4", null, escapeHtml(step.step_key || step.id));
  header.appendChild(h4);

  var badge = el("span", "dpmtf-badge " +
    (step.is_active ? "dpmtf-badge-success" : "dpmtf-badge-danger"));
  badge.textContent = step.is_active
    ? lbl("lbl_bridge_active", "Active")
    : lbl("lbl_bridge_inactive", "Inactive");
  header.appendChild(badge);
  card.appendChild(header);

  // Step details
  var fields = [
    ["From/To Role", (step.from_role || "") + " -> " + (step.to_role || "")],
    ["Rule Key", step.rule_key],
    ["Dir", step.deliverable_dir],
    ["Pattern", step.deliverable_pattern],
    ["Pre-script", step.pre_dispatch_script],
    ["Post-script", step.post_dispatch_script],
    ["Sort", String(step.sort_order || 0)],
  ];
  fields.forEach(function (pair) {
    if (!pair[1]) return;
    var row = el("div", null);
    row.appendChild(el("span", "dpmtf-small", escapeHtml(pair[0]) + ": "));
    row.appendChild(el("span", null, escapeHtml(String(pair[1]))));
    card.appendChild(row);
  });

  // Action buttons
  var actions = el("div", null);
  actions.style.marginTop = "8px";

  var editBtn = el("button", "dpmtf-btn");
  editBtn.textContent = lbl("lbl_bridge_edit", "Edit");
  editBtn.onclick = function () { _editBridgeStep(step.id, step.flow_key || _bridgeStepsFlowKey); };
  actions.appendChild(editBtn);

  var delBtn = el("button", "dpmtf-btn dpmtf-btn-danger");
  delBtn.textContent = lbl("lbl_bridge_delete", "Delete");
  delBtn.onclick = function () { _deleteBridgeStep(step.id, step.flow_key || _bridgeStepsFlowKey); };
  actions.appendChild(delBtn);

  card.appendChild(actions);
  return card;
}

function _loadBridgeStepsFlow() {
  var select = document.getElementById("bridge-steps-flow-select");
  if (!select) return;

  fetch("/api/bridge-v2/flows")
    .then(function (res) { return res.json(); })
    .then(function (data) {
      var flows = data.flows || [];
      clear(select);
      var defaultOpt = document.createElement("option");
      defaultOpt.value = "";
      defaultOpt.textContent = lbl("lbl_bridge_select_flow", "Select Flow");
      select.appendChild(defaultOpt);
      flows.forEach(function (flow) {
        var opt = document.createElement("option");
        opt.value = flow.flow_key;
        opt.textContent = flow.name || flow.flow_key;
        select.appendChild(opt);
      });
      select.onchange = function () {
        if (this.value) _fetchBridgeSteps(this.value);
      };
    })
    .catch(function (err) {
      console.error("Failed to load bridge flows for steps selector:", err.message);
    });
}

function _fetchBridgeSteps(flowKey) {
  _bridgeStepsFlowKey = flowKey;
  var container = document.getElementById("bridge-steps-list-container");
  if (!container) return;
  clear(container);

  fetch("/api/bridge-v2/steps/" + encodeURIComponent(flowKey))
    .then(function (res) { return res.json(); })
    .then(function (data) {
      var steps = data.steps || [];
      _bridgeStepsMetadata = {
        available_roles: data.available_roles || [],
        available_conventions: data.available_conventions || [],
        available_scripts: data.available_scripts || []
      };
      if (!steps.length) {
        container.appendChild(el("p", "dpmtf-muted", lbl("lbl_bridge_no_flows", "No steps for this flow")));
        return;
      }
      steps.forEach(function (step) {
        step.flow_key = flowKey;
        container.appendChild(renderStepCard(step, _bridgeStepsMetadata));
      });
    })
    .catch(function (err) {
      var errP = el("p", "dpmtf-error");
      errP.textContent = lbl("lbl_status_error_prefix", "Error: ") + escapeHtml(err.message);
      container.appendChild(errP);
    });
}

function _showStepForm(initialData) {
  var container = document.getElementById("bridge-steps-list-container");
  if (!container) return;

  // Remove any existing form
  var existing = document.getElementById("bridge-step-form");
  if (existing) existing.remove();

  var meta = initialData._meta || _bridgeStepsMetadata || {
    available_roles: [],
    available_conventions: [],
    available_scripts: []
  };
  var data = initialData.data || {};

  var form = el("div", "dpmtf-card");
  form.id = "bridge-step-form";

  var cancelBtn = el("button", "dpmtf-btn");
  cancelBtn.textContent = lbl("lbl_bridge_cancel", "Cancel");
  cancelBtn.onclick = function () { form.remove(); _bridgeEditingStepId = null; };

  var saveBtn = el("button", "dpmtf-btn dpmtf-btn-primary");
  saveBtn.textContent = lbl("lbl_bridge_save", "Save");
  saveBtn.onclick = function () {
    var sk = document.getElementById("bridge-input-step_key").value.trim();
    if (!sk) { alert(lbl("lbl_bridge_step_key", "Step Key") + " is required."); return; }

    var body = { step_key: sk };
    var fr = document.getElementById("bridge-input-from_role");
    if (fr.value) body.from_role = fr.value;
    var tr = document.getElementById("bridge-input-to_role");
    if (tr.value) body.to_role = tr.value;
    var rk = document.getElementById("bridge-input-rule_key");
    if (rk.value) body.rule_key = rk.value;
    var dd = document.getElementById("bridge-input-deliverable_dir");
    if (dd.value) body.deliverable_dir = dd.value.trim();
    var dp = document.getElementById("bridge-input-deliverable_pattern");
    if (dp.value) body.deliverable_pattern = dp.value.trim();
    var ps = document.getElementById("bridge-input-pre_dispatch_script");
    if (ps.value) body.pre_dispatch_script = ps.value;
    var pos = document.getElementById("bridge-input-post_dispatch_script");
    if (pos.value) body.post_dispatch_script = pos.value;
    var em = document.getElementById("bridge-input-error_msg");
    if (em.value) body.error_msg = em.value.trim();
    var so = document.getElementById("bridge-input-sort_order");
    if (so.value !== "") body.sort_order = parseInt(so.value, 10);

    _submitBridgeStep(_bridgeStepsFlowKey, _bridgeEditingStepId, body);
  };

  form.appendChild(el("h4", null, lbl("lbl_bridge_step_form_title", "Add/Edit Step")));

  // Helper to create a select dropdown
  var makeSelect = function (id, options, valueAttr, textAttr, selected) {
    var sel = document.createElement("select");
    sel.id = id;
    var defaultOpt = document.createElement("option");
    defaultOpt.value = "";
    defaultOpt.textContent = "--";
    sel.appendChild(defaultOpt);
    (options || []).forEach(function (item) {
      var opt = document.createElement("option");
      opt.value = item[valueAttr] || item;
      opt.textContent = item[textAttr] || item[valueAttr] || item;
      if (opt.value === selected) opt.selected = true;
      sel.appendChild(opt);
    });
    return sel;
  };

  // Text input fields
  [["bridge-input-step_key", lbl("lbl_bridge_step_key", "Step Key"), data.step_key || ""],
   ["bridge-input-deliverable_dir", lbl("lbl_bridge_deliverable_dir", "Deliverable Dir"), data.deliverable_dir || ""],
   ["bridge-input-deliverable_pattern", lbl("lbl_bridge_deliverable_pattern", "Pattern"), data.deliverable_pattern || ""],
   ["bridge-input-error_msg", lbl("lbl_bridge_deliver_error_msg", "Error Msg"), data.error_msg || ""]].forEach(function (f) {
    var div = el("div", "dpmtf-form-group");
    div.appendChild(el("label", "dpmtf-label", f[1]));
    var input = el("input", null);
    input.id = f[0];
    input.type = "text";
    input.value = f[2];
    div.appendChild(input);
    form.appendChild(div);
  });

  // From role dropdown
  var frDiv = el("div", "dpmtf-form-group");
  frDiv.appendChild(el("label", "dpmtf-label", lbl("lbl_bridge_step_from_role", "From Role")));
  frDiv.appendChild(makeSelect("bridge-input-from_role", meta.available_roles, "role_key", "name", data.from_role));
  form.appendChild(frDiv);

  // To role dropdown
  var trDiv = el("div", "dpmtf-form-group");
  trDiv.appendChild(el("label", "dpmtf-label", lbl("lbl_bridge_step_to_role", "To Role")));
  trDiv.appendChild(makeSelect("bridge-input-to_role", meta.available_roles, "role_key", "name", data.to_role));
  form.appendChild(trDiv);

  // Rule key dropdown with auto-fill on change
  var rkDiv = el("div", "dpmtf-form-group");
  rkDiv.appendChild(el("label", "dpmtf-label", lbl("lbl_bridge_rule_key", "Convention Rule")));
  var rkSelect = makeSelect("bridge-input-rule_key", meta.available_conventions, "rule_key", "step_type", data.rule_key);
  rkSelect.onchange = function () { _autoFillFromConvention(this.value, form, meta.available_conventions); };
  rkDiv.appendChild(rkSelect);
  form.appendChild(rkDiv);

  // Pre-dispatch script dropdown (pre or both only)
  var preScripts = meta.available_scripts.filter(function (s) { return s.stage === "pre" || s.stage === "both"; });
  var psDiv = el("div", "dpmtf-form-group");
  psDiv.appendChild(el("label", "dpmtf-label", lbl("lbl_bridge_script_pre", "Pre-Dispatch Script")));
  psDiv.appendChild(makeSelect("bridge-input-pre_dispatch_script", preScripts, "script_key", "name", data.pre_dispatch_script));
  form.appendChild(psDiv);

  // Post-dispatch script dropdown (post or both only)
  var postScripts = meta.available_scripts.filter(function (s) { return s.stage === "post" || s.stage === "both"; });
  var posDiv = el("div", "dpmtf-form-group");
  posDiv.appendChild(el("label", "dpmtf-label", lbl("lbl_bridge_script_post", "Post-Dispatch Script")));
  posDiv.appendChild(makeSelect("bridge-input-post_dispatch_script", postScripts, "script_key", "name", data.post_dispatch_script));
  form.appendChild(posDiv);

  // Sort order (number input)
  var soDiv = el("div", "dpmtf-form-group");
  soDiv.appendChild(el("label", "dpmtf-label", lbl("lbl_bridge_step_sort_order", "Sort Order")));
  var soInput = el("input", null);
  soInput.id = "bridge-input-sort_order";
  soInput.type = "number";
  soInput.value = data.sort_order != null ? String(data.sort_order) : "0";
  soDiv.appendChild(soInput);
  form.appendChild(soDiv);

  // Buttons
  var btnRow = el("div", null);
  btnRow.appendChild(saveBtn);
  btnRow.appendChild(cancelBtn);
  form.appendChild(btnRow);

  container.insertBefore(form, container.firstChild);
}

function _autoFillFromConvention(ruleKey, form, conventions) {
  if (!ruleKey || !conventions) return;
  var conv = (conventions || []).filter(function (c) { return c.rule_key === ruleKey; })[0];
  if (!conv) return;

  var dirInput = document.getElementById("bridge-input-deliverable_dir");
  if (dirInput && conv.dir_template) dirInput.value = conv.dir_template;

  var patInput = document.getElementById("bridge-input-deliverable_pattern");
  if (patInput && conv.pattern_template) patInput.value = conv.pattern_template;

  var errInput = document.getElementById("bridge-input-error_msg");
  if (errInput && conv.error_template) errInput.value = conv.error_template;
}

function _submitBridgeStep(flowKey, stepId, body) {
  var method = stepId ? "PUT" : "POST";
  var url = stepId
    ? "/api/bridge-v2/steps/" + encodeURIComponent(flowKey) + "/" + stepId
    : "/api/bridge-v2/steps/" + encodeURIComponent(flowKey);

  fetch(url, {
    method: method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  })
    .then(function (res) {
      if (!res.ok) throw new Error("HTTP " + res.status);
      return res.json();
    })
    .then(function (data) {
      var msg = stepId ? lbl("lbl_bridge_updated", "Successfully updated") : lbl("lbl_bridge_created", "Successfully created");
      alert(msg + ": " + (data.step ? data.step.step_key : body.step_key));
      var form = document.getElementById("bridge-step-form");
      if (form) form.remove();
      _bridgeEditingStepId = null;
      _fetchBridgeSteps(flowKey);
    })
    .catch(function (err) {
      alert(lbl("lbl_status_error_prefix", "Error: ") + escapeHtml(err.message));
    });
}

function _editBridgeStep(stepId, flowKey) {
  fetch("/api/bridge-v2/steps/" + encodeURIComponent(flowKey))
    .then(function (res) { return res.json(); })
    .then(function (data) {
      var step = (data.steps || []).filter(function (s) { return s.id === stepId; })[0];
      if (!step) throw new Error("Step not found: " + stepId);
      _bridgeEditingStepId = stepId;
      _showStepForm({ data: step, _meta: {
        available_roles: data.available_roles || [],
        available_conventions: data.available_conventions || [],
        available_scripts: data.available_scripts || []
      }});
    })
    .catch(function (err) {
      alert(lbl("lbl_status_error_prefix", "Error: ") + escapeHtml(err.message));
    });
}

function _deleteBridgeStep(stepId, flowKey) {
  if (!confirm("Delete step #" + stepId + "?")) return;
  fetch("/api/bridge-v2/steps/" + encodeURIComponent(flowKey) + "/" + stepId, { method: "DELETE" })
    .then(function (res) { return res.json(); })
    .then(function () {
      alert(lbl("lbl_bridge_deleted", "Successfully deleted") + ": #" + stepId);
      _fetchBridgeSteps(flowKey);
    })
    .catch(function (err) {
      alert(lbl("lbl_status_error_prefix", "Error: ") + escapeHtml(err.message));
    });
}

function loadBridgeSetup() {
  loadBridgeStatus();
  loadBridgeRoles();
  loadBridgeFlows();
  _loadBridgeStepsFlow();
  buildBridgeExport();

  var addRoleBtn = document.getElementById("bridge-add-role-btn");
  if (addRoleBtn) addRoleBtn.onclick = function () { addBridgeRole(); };

  var expRolesBtn = document.getElementById("bridge-export-roles-btn");
  if (expRolesBtn) expRolesBtn.onclick = function () { exportBridge("roles"); };

  var addFlowBtn = document.getElementById("bridge-add-flow-btn");
  if (addFlowBtn) addFlowBtn.onclick = function () { addBridgeFlow(); };

  var expFlowsBtn = document.getElementById("bridge-export-flows-btn");
  if (expFlowsBtn) expFlowsBtn.onclick = function () { exportBridge("flows"); };

  var addStepBtn = document.getElementById("bridge-add-step-btn");
  if (addStepBtn) addStepBtn.onclick = function () { _showStepForm({ data: {}, _meta: _bridgeStepsMetadata }); };
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
  buildCompilerForm();
  initDrawer();
  loadBridgeSetup();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", onReady);
} else {
  onReady();
}
