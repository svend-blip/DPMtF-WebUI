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



/* ── Static Compile Form (8 fields) ─────────── */
function buildCompilerForm() {
  var container = document.getElementById("template-manager-content");
  if (!container) return;
  clear(container);

  // Target Session (role-based, tool-independent)
  var sessionDiv = el("div", "dpmtf-form-group");
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

  // Target Project
  var projDiv = el("div", "dpmtf-form-group");
  projDiv.appendChild(el("label", "dpmtf-label", lbl("lbl_compiler_target_project", "Target Project")));
  var projInput = el("input", null);
  projInput.type = "text";
  projInput.id = "compile-target_project";
  projInput.placeholder = lbl("lbl_compiler_project_placeholder", "/home/svend/DPMtF-WebUI");
  projDiv.appendChild(projInput);
  container.appendChild(projDiv);

  // Phase Key
  var phaseDiv = el("div", "dpmtf-form-group");
  phaseDiv.appendChild(el("label", "dpmtf-label", lbl("lbl_compiler_phase_key", "Phase Key")));
  var phaseInput = el("input", null);
  phaseInput.type = "text";
  phaseInput.id = "compile-phase_key";
  phaseInput.placeholder = lbl("lbl_compiler_phase_placeholder", "spor-g-test");
  phaseDiv.appendChild(phaseInput);
  container.appendChild(phaseDiv);

  // Goal
  var goalDiv = el("div", "dpmtf-form-group");
  goalDiv.appendChild(el("label", "dpmtf-label", lbl("lbl_compiler_goal", "Goal")));
  var goalTextarea = el("textarea", null);
  goalTextarea.id = "compile-goal";
  goalTextarea.rows = 4;
  goalTextarea.placeholder = lbl("lbl_compiler_goal_placeholder", "Describe the implementation task...");
  goalDiv.appendChild(goalTextarea);
  container.appendChild(goalDiv);

  // Deployment Strategy (optional)
  var depDiv = el("div", "dpmtf-form-group");
  depDiv.appendChild(el("label", "dpmtf-label", lbl("lbl_compiler_deployment_strategy", "Deployment Strategy (optional)")));
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

  // Scope & Gate confirmation
  var scopeDiv = el("div", "dpmtf-form-group");
  var scopeLabel = el("label", "dpmtf-label", null);
  var scopeCheckbox = el("input", null);
  scopeCheckbox.type = "checkbox";
  scopeCheckbox.id = "compile-scope_gate_confirmed";
  scopeLabel.appendChild(scopeCheckbox);
  scopeLabel.appendChild(document.createTextNode(lbl("lbl_compiler_scope_gate", " Have you considered scope and gate scope?")));
  scopeDiv.appendChild(scopeLabel);
  container.appendChild(scopeDiv);

  // Allowed files (optional)
  var allowedDiv = el("div", "dpmtf-form-group");
  allowedDiv.appendChild(el("label", "dpmtf-label", lbl("lbl_compiler_allowed_files", "Allowed files (optional, one per line)")));
  var allowedTextarea = el("textarea", null);
  allowedTextarea.id = "compile-allowed_files";
  allowedTextarea.rows = 3;
  allowedTextarea.placeholder = lbl("lbl_compiler_allowed_placeholder", "(blank = Review verifies)");
  allowedDiv.appendChild(allowedTextarea);
  container.appendChild(allowedDiv);

  // Forbidden files (optional)
  var forbiddenDiv = el("div", "dpmtf-form-group");
  forbiddenDiv.appendChild(el("label", "dpmtf-label", lbl("lbl_compiler_forbidden_files", "Forbidden files (optional, one per line)")));
  var forbiddenTextarea = el("textarea", null);
  forbiddenTextarea.id = "compile-forbidden_files";
  forbiddenTextarea.rows = 3;
  forbiddenTextarea.placeholder = lbl("lbl_compiler_forbidden_placeholder", "(blank = none specified)");
  forbiddenDiv.appendChild(forbiddenTextarea);
  container.appendChild(forbiddenDiv);

  // Compile button
  var compileBtn = el("button", "dpmtf-btn dpmtf-btn-primary");
  compileBtn.textContent = lbl("lbl_tpl_compile_prompt", "Compile Prompt");
  compileBtn.onclick = compilePromptV2;
  container.appendChild(compileBtn);
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
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", onReady);
} else {
  onReady();
}
