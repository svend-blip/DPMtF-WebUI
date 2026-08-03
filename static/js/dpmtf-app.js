/* ── 1. i18n loader ─────────────────────────────────── */
var labelMap = {};
var currentLocale = "en-US";  // fallback indtil API svarer

function loadLabels() {
  // Hent brugerens gemte sprog fra API
  return fetch("/api/user-language")
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
  var groupNames = ["daily", "journals", "reports", "periodic", "setup", "job-queue"];
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

/**
 * Copy text to the clipboard, reporting success to the caller.
 *
 * navigator.clipboard is undefined outside a secure context, and this app
 * listens on 0.0.0.0 — reached over http from another machine, the modern
 * API is simply not there. The textarea + execCommand path is the fallback
 * that still works there. The callback receives false when neither
 * succeeds, so the caller can tell the user to copy manually rather than
 * silently doing nothing.
 */
function copyTextToClipboard(text, done) {
  var report = typeof done === "function" ? done : function () {};

  if (navigator.clipboard && window.isSecureContext) {
    navigator.clipboard.writeText(text).then(
      function () { report(true); },
      function () { report(legacyCopy(text)); }
    );
    return;
  }
  report(legacyCopy(text));
}

function legacyCopy(text) {
  var ta = document.createElement("textarea");
  ta.value = text;
  ta.setAttribute("readonly", "");
  ta.style.position = "fixed";
  ta.style.left = "-9999px";
  document.body.appendChild(ta);
  ta.select();
  var ok = false;
  try {
    ok = document.execCommand("copy");
  } catch (e) {
    ok = false;
  }
  document.body.removeChild(ta);
  return ok;
}

/**
 * Factory for a model_source + model_alias control pair.
 * Simplified: model_source is fixed (model_allocator or python_runtime),
 * model_alias is a text field with a "Test OK" button, and a link to
 * the allocator UI for full model management.
 */
function createModelSourceControl(prefix, sourceValue, aliasValue, clientValue, labels, sourceOptions) {
  var container = el("div", "dpmtf-form-group");

  // model_source dropdown (simplified — only model_allocator or python_runtime)
  var srcDiv = el("div", "dpmtf-form-group");
  var srcLabel = el("label", "dpmtf-label", lbl(labels.source, "Model Source"));
  srcLabel.htmlFor = prefix + "-model-source";
  var srcSelect = el("select", null);
  srcSelect.id = prefix + "-model-source";
  sourceOptions.forEach(function (pair) {
    var opt = document.createElement("option");
    opt.value = pair[0];
    opt.textContent = pair[1];
    if (pair[0] === (sourceValue || "")) opt.selected = true;
    srcSelect.appendChild(opt);
  });
  srcDiv.appendChild(srcLabel);
  srcDiv.appendChild(srcSelect);
  container.appendChild(srcDiv);

  // model_alias text input (no datalist — just type the alias name)
  var aliasDiv = el("div", "dpmtf-form-group");
  var aliasLabel = el("label", "dpmtf-label", lbl(labels.alias, "Model Alias"));
  aliasLabel.htmlFor = prefix + "-model-alias";
  var aliasInput = el("input", null);
  aliasInput.type = "text";
  aliasInput.id = prefix + "-model-alias";
  aliasInput.value = aliasValue || "";
  aliasInput.placeholder = "e.g. archi-local";
  aliasInput.disabled = srcSelect.value !== "model_allocator";
  aliasDiv.appendChild(aliasLabel);
  aliasDiv.appendChild(aliasInput);
  container.appendChild(aliasDiv);

  // "Test OK" button — calls allocator CLI validate via a thin DPMtF proxy endpoint
  var testBtn = el("button", "dpmtf-btn");
  testBtn.type = "button";
  testBtn.textContent = "Test OK";
  testBtn.disabled = srcSelect.value !== "model_allocator";
  container.appendChild(testBtn);

  // Link to allocator UI
  var linkDiv = el("div", "dpmtf-form-group");
  var link = document.createElement("a");
  link.href = "http://localhost:9140";
  link.target = "_blank";
  link.rel = "noopener";
  link.textContent = "Manage allocation models →";
  link.style.fontSize = "0.8rem";
  linkDiv.appendChild(link);
  container.appendChild(linkDiv);

  // Result area
  var resultDiv = el("div", "dpmtf-form-group");
  resultDiv.id = prefix + "-model-validation-result";
  container.appendChild(resultDiv);

  function updateState() {
    var isAllocator = srcSelect.value === "model_allocator";
    aliasInput.disabled = !isAllocator;
    testBtn.disabled = !isAllocator;
    if (!isAllocator) {
      aliasInput.value = "";
      clear(resultDiv);
    }
  }
  srcSelect.onchange = updateState;

  // Test OK: call DPMtF proxy endpoint that shells out to allocator CLI validate
  testBtn.onclick = function () {
    clear(resultDiv);
    var alias = aliasInput.value.trim();
    if (!alias) return;
    resultDiv.appendChild(el("div", "dpmtf-muted", "Testing..."));

    // Use the allocator CLI directly via a thin proxy endpoint
    var cmd = "/api/bridge-v2/allocator-test?alias=" + encodeURIComponent(alias) + "&client=opencode";
    fetch(cmd)
      .then(function (res) {
        if (!res.ok) throw new Error("HTTP " + res.status);
        return res.json();
      })
      .then(function (result) {
        clear(resultDiv);
        var status = (result.validation_status || "UNKNOWN").toUpperCase();
        var statusClass = status === "OK" ? "dpmtf-text-success" :
                          status === "WARNING" ? "dpmtf-text-warning" : "dpmtf-text-danger";
        var msg = status;
        if (result.resolved_real_model) {
          msg += " — " + (result.resolved_backend || "") + "/" + result.resolved_real_model;
        }
        resultDiv.appendChild(el("div", statusClass, msg));
        (result.errors || []).forEach(function (e) {
          resultDiv.appendChild(el("div", "dpmtf-text-danger dpmtf-small", e));
        });
      })
      .catch(function (err) {
        clear(resultDiv);
        resultDiv.appendChild(el("div", "dpmtf-text-danger",
          lbl("lbl_status_error_prefix", "Error") + ": " + escapeHtml(err.message)));
      });
  };

  return {
    container: container,
    getSource: function () { return srcSelect.value || null; },
    getAlias: function () {
      return srcSelect.value === "model_allocator" ? (aliasInput.value.trim() || null) : null;
    },
    setClient: function (c) { clientValue = c; }
  };
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
  closeBtn.textContent = "×";
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
      thr.appendChild(el("th", null, lbl("lbl_bridge_th_panel", "Panel")));
      thr.appendChild(el("th", null, lbl("lbl_bridge_th_slot", "Slot")));
      thr.appendChild(el("th", null, lbl("lbl_bridge_th_type", "Type")));
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
      thr.appendChild(el("th", null, lbl("lbl_bridge_th_label_key", "Key")));
      thr.appendChild(el("th", null, lbl("lbl_bridge_th_label_text", "Text")));
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
      thr.appendChild(el("th", null, lbl("lbl_bridge_th_method", "Method")));
      thr.appendChild(el("th", null, lbl("lbl_bridge_th_path", "Path")));
      thr.appendChild(el("th", null, lbl("lbl_bridge_th_purpose", "Purpose")));
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
      thr.appendChild(el("th", null, lbl("lbl_bridge_th_dataset", "Dataset")));
      thr.appendChild(el("th", null, lbl("lbl_bridge_th_table", "Table")));
      thr.appendChild(el("th", null, lbl("lbl_bridge_th_script", "Script")));
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
  valCard.appendChild(el("h4", null, lbl("lbl_system_h4_validation", "Validation")));
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
      runBtn.textContent = lbl("lbl_btn_run_validation", "Run Validation");
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
  platCard.appendChild(el("h4", null, lbl("lbl_system_h4_platform", "Platform")));
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
  sessCard.appendChild(el("h4", null, lbl("lbl_system_h4_claude_sessions", "Claude Code Sessions")));
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
        statusBadge.textContent = lbl("lbl_bridge_active", "Active");
        sessBody.appendChild(statusBadge);
        sessBody.appendChild(el("div", "dpmtf-small", null));
        var info = [];
        info.push("Model: " + (s.model_used || "unknown"));
        info.push("Project: " + (s.project_context || "unknown"));
        info.push("Started: " + (s.started_at ? new Date(s.started_at).toLocaleString() : "?"));
        sessBody.appendChild(el("div", "dpmtf-small", info.join(" | ")));
      } else {
        var inactiveBadge = el("span", "dpmtf-badge dpmtf-badge-info");
        inactiveBadge.textContent = lbl("lbl_bridge_inactive", "No active session");
        sessBody.appendChild(inactiveBadge);
      }
    })
    .catch(function (err) {
      clear(sessBody);
      sessBody.appendChild(el("p", "dpmtf-error", escapeHtml(err.message)));
    });

  // ── Workflow (P→I→V loop) ────────────────────────────
  var wfCard = el("div", "dpmtf-card");
  wfCard.appendChild(el("h4", null, lbl("lbl_system_h4_workflow_loop", "Workflow — P→I→V Loop")));
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
        wfBody.appendChild(el("p", "dpmtf-muted", lbl("lbl_no_workflow_runs", "No workflow runs yet.")));
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
      target_project: "",
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

  // ── Prompt Templates buttonrow (handoff 193, moved to top by handoff 204) ──
  // Holds: Compile Prompt (always), Assign Handoff ID + Copy Prompt (after compile success).
  var compileButtonsRow = el("div", null);
  compileButtonsRow.id = "compile-buttons-row";
  compileButtonsRow.style.marginTop = "8px";
  container.appendChild(compileButtonsRow);

  // ── Compile Prompt button (hidden when accelerated) ──
  var compileBtn = el("button", "dpmtf-btn dpmtf-btn-primary");
  compileBtn.id = "compile-btn-submit";
  compileBtn.textContent = lbl("lbl_tpl_compile_prompt", "Compile Prompt");
  compileBtn.onclick = compilePromptV2;
  compileButtonsRow.appendChild(compileBtn);

  // ── Dispatch buttons row (handoff 204) ──
  // Under the compile-buttons-row. Holds: Copy Command, Deliver to Bridge
  // (populated by assignHandoffId after a successful assign).
  var dispatchButtonsRow = el("div", null);
  dispatchButtonsRow.id = "dispatch-buttons-row";
  dispatchButtonsRow.style.marginTop = "8px";
  container.appendChild(dispatchButtonsRow);

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
  // Default to "standard" so flow/step dropdowns are visible on page load
  depSelect.value = "standard";
  depDiv.appendChild(depSelect);
  container.appendChild(depDiv);

  // ── 1.5. Flow Key (BridgeV002 — visible for standard) ──
  var flowDiv = el("div", "dpmtf-form-group");
  flowDiv.id = "compile-group-flowkey";
  flowDiv.appendChild(el("label", "dpmtf-label", lbl("lbl_compiler_flow_key", "Flow Key")));
  var flowSelect = el("select", null);
  flowSelect.id = "compile-flow_key";
  var flowEmptyOpt = document.createElement("option");
  flowEmptyOpt.value = "";
  flowEmptyOpt.textContent = lbl("lbl_compiler_no_flow", "(optional — select for BridgeV002 dispatch)");
  flowSelect.appendChild(flowEmptyOpt);
  // Populate from /api/bridge-v2/flows (only active flows)
  fetch("/api/bridge-v2/flows")
    .then(function (res) { return res.json(); })
    .then(function (data) {
      var flows = data.flows || [];
      flows.forEach(function (f) {
        var opt = document.createElement("option");
        opt.value = f.flow_key;
        opt.textContent = f.name || f.flow_key;
        flowSelect.appendChild(opt);
      });
      // Auto-select first flow if available
      if (flows.length > 0) {
        flowSelect.value = flows[0].flow_key;
        populateStepDropdown(flows[0].flow_key);
      }
      // Cascade: populate steps when flow changes
      flowSelect.onchange = function () {
        var fk = flowSelect.value;
        populateStepDropdown(fk);
      };
    })
    .catch(function (err) {
      console.error("Failed to load bridge flows for compiler:", err);
    });
  flowDiv.appendChild(flowSelect);
  container.appendChild(flowDiv);

  // ── 1.6. Step Key (BridgeV002 — populated from selected flow) ──
  var stepDiv = el("div", "dpmtf-form-group");
  stepDiv.id = "compile-group-stepkey";
  stepDiv.appendChild(el("label", "dpmtf-label", lbl("lbl_compiler_step_key", "Step Key")));
  var stepSelect = el("select", null);
  stepSelect.id = "compile-step_key";
  var stepEmptyOpt = document.createElement("option");
  stepEmptyOpt.value = "";
  stepEmptyOpt.textContent = lbl("lbl_compiler_no_step", "(select a flow first)");
  stepSelect.appendChild(stepEmptyOpt);
  stepDiv.appendChild(stepSelect);
  container.appendChild(stepDiv);

  // Helper: populate step dropdown from a given flow key
  function populateStepDropdown(flowKey) {
    var current = document.getElementById("compile-step_key");
    if (!current) return;
    clear(current);
    var emptyOpt2 = document.createElement("option");
    emptyOpt2.value = "";
    emptyOpt2.textContent = lbl("lbl_optional_select_for_bridgev002", "(optional — select for BridgeV002 dispatch)");
    current.appendChild(emptyOpt2);
    if (!flowKey) {
      _updateAutoSession(null, null);
      return;
    }
    fetch("/api/bridge-v2/steps/" + encodeURIComponent(flowKey))
      .then(function (res) { return res.json(); })
      .then(function (data) {
        var steps = data.steps || [];
        steps.forEach(function (s) {
          var opt2 = document.createElement("option");
          opt2.value = s.step_key;
          opt2.textContent = s.step_key + " (" + (s.from_role || "?") + " -> " + (s.to_role || "?") + ")";
          current.appendChild(opt2);
        });
        // Cascade: when step changes, update auto-resolved session
        current.onchange = function () {
          var sk = current.value;
          var step = null;
          steps.forEach(function (s) { if (s.step_key === sk) step = s; });
          _updateAutoSession(flowKey, step);
        };
      })
      .catch(function (err) {
        console.error("Failed to load steps for flow:", flowKey, err);
      });
  }

  // Update the auto-resolved target session display
  function _updateAutoSession(flowKey, step) {
    var div = document.getElementById("compile-group-auto-session");
    var info = document.getElementById("compile-auto-session-info");
    if (!div || !info) return;
    if (flowKey && step && step.to_role) {
      // Fetch the to_role to get its tmux_session
      fetch("/api/bridge-v2/roles/" + encodeURIComponent(step.to_role))
        .then(function (res) { return res.json(); })
        .then(function (data) {
          var role = data.role;
          if (role) {
            info.textContent = role.tmux_session + " (" + step.to_role + " — " + (role.governance_file || "no gov file") + ")";
            div.style.display = "";
          }
        })
        .catch(function () {
          info.textContent = step.to_role + " (" + lbl("lbl_session_info_unavailable", "session info unavailable") + ")";
          div.style.display = "";
        });
    } else {
      div.style.display = "none";
    }
  }

  // ── 1.7. Auto-resolved Target Session (read-only, shown when flow+step selected) ──
  var autoSessionDiv = el("div", "dpmtf-form-group");
  autoSessionDiv.id = "compile-group-auto-session";
  autoSessionDiv.style.display = "none";
  autoSessionDiv.appendChild(el("label", "dpmtf-label", lbl("lbl_compiler_target_session", "Target Session")));
  var autoSessionInfo = el("span", "dpmtf-small");
  autoSessionInfo.id = "compile-auto-session-info";
  autoSessionInfo.textContent = lbl("lbl_auto_resolved_flow_step", "(auto-resolved from flow step)");
  autoSessionDiv.appendChild(autoSessionInfo);
  container.appendChild(autoSessionDiv);

  // ── 2. Target Project ──
  var projDiv = el("div", "dpmtf-form-group");
  projDiv.id = "compile-group-project";
  projDiv.appendChild(el("label", "dpmtf-label", lbl("lbl_compiler_target_project", "Target Project")));
  var projInput = el("input", null);
  projInput.type = "text";
  projInput.id = "compile-target_project";
  projInput.placeholder = lbl("lbl_compiler_project_placeholder", "DPMtF-WebUI");
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
  nameInput.maxLength = 20;
  nameInput.placeholder = lbl("lbl_placeholder_new_webui_name", "mywebui");
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
  portInput.placeholder = lbl("lbl_placeholder_new_webui_port", "9136");
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
  titleInput.placeholder = lbl("lbl_placeholder_new_webui_title", "My Project");
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

  // (compile-buttons-row and compileBtn moved to TOP of form by handoff 204)

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
    var isStandard = depSelect.value === "standard";

    // Standard fields: hide when accelerated, some also hidden in standard (auto-resolved)
    var standardIds = [
      "compile-group-phase",
      "compile-group-allowed", "compile-group-forbidden"
    ];
    standardIds.forEach(function (id) {
      var stEl = document.getElementById(id);
      if (stEl) stEl.style.display = (isAccelerated || isStandard) ? "none" : "";
    });

    // Goal and scope gate: always visible in standard, hidden in accelerated
    var goalEl = document.getElementById("compile-group-goal");
    if (goalEl) goalEl.style.display = isAccelerated ? "none" : "";
    var scopeEl = document.getElementById("compile-group-scope");
    if (scopeEl) scopeEl.style.display = isAccelerated ? "none" : "";

    // Flow/Step: visible in standard, hidden in accelerated
    var flowEl = document.getElementById("compile-group-flowkey");
    if (flowEl) flowEl.style.display = isStandard ? "" : "none";
    var stepEl = document.getElementById("compile-group-stepkey");
    if (stepEl) stepEl.style.display = isStandard ? "" : "none";

    // Auto-resolved session: visible in standard, hidden otherwise
    var autoSessEl = document.getElementById("compile-group-auto-session");
    if (autoSessEl) autoSessEl.style.display = isStandard ? "" : "none";

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
    var deliverBtnEl = document.getElementById("compile-btn-deliver-to-bridge");
    if (compileBtnEl) compileBtnEl.style.display = isAccelerated ? "none" : "";
    if (createBtnEl) createBtnEl.style.display = isAccelerated ? "" : "none";
    if (startBtnEl) startBtnEl.style.display = "none";
    if (deliverBtnEl) deliverBtnEl.style.display = "none";

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
      var phaseEl = document.getElementById("compile-phase_key");
      if (phaseEl) phaseEl.value = "";
      var goalEl2 = document.getElementById("compile-goal");
      if (goalEl2) goalEl2.value = "";
      var scopeGateEl = document.getElementById("compile-scope_gate_confirmed");
      if (scopeGateEl) scopeGateEl.checked = false;
      var allowedEl = document.getElementById("compile-allowed_files");
      if (allowedEl) allowedEl.value = "";
      var forbiddenEl = document.getElementById("compile-forbidden_files");
      if (forbiddenEl) forbiddenEl.value = "";
      var flowSel = document.getElementById("compile-flow_key");
      if (flowSel) flowSel.value = "";
      var stepSel = document.getElementById("compile-step_key");
      if (stepSel) { clear(stepSel); stepSel.appendChild(document.createElement("option")); }
    } else if (isStandard) {
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

  // Fire onchange on page load to set initial field visibility (default: standard)
  depSelect.onchange();
}

function compilePromptV2() {
  var outputDiv = document.getElementById("compile-output");
  if (!outputDiv) return;
  outputDiv.style.display = "block";
  clear(outputDiv);
  outputDiv.appendChild(
    el("p", "dpmtf-muted", lbl("lbl_status_compiling", "Compiling..."))
  );

  // Reset Deliver to Bridge state for new compile
  _lastAssignedHandoff = null;
  var resetDeliverBtn = document.getElementById("compile-btn-deliver-to-bridge");
  if (resetDeliverBtn) resetDeliverBtn.style.display = "none";

  // Reset Prompt Templates buttonrow: remove stale Assign/Copy from previous compile
  if (_assignBtnInRow && _assignBtnInRow.parentNode) {
    _assignBtnInRow.parentNode.removeChild(_assignBtnInRow);
  }
  _assignBtnInRow = null;
  if (_copyBtnInRow && _copyBtnInRow.parentNode) {
    _copyBtnInRow.parentNode.removeChild(_copyBtnInRow);
  }
  _copyBtnInRow = null;

  // Reset dispatch buttons row: remove stale Copy Command / Deliver to Bridge
  // from a previous assign so the user does not click a stale button.
  if (_copyCmdBtnInRow && _copyCmdBtnInRow.parentNode) {
    _copyCmdBtnInRow.parentNode.removeChild(_copyCmdBtnInRow);
  }
  _copyCmdBtnInRow = null;
  if (_deliverBtnInRow && _deliverBtnInRow.parentNode) {
    _deliverBtnInRow.parentNode.removeChild(_deliverBtnInRow);
  }
  _deliverBtnInRow = null;

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

  // Collect fields (target_session auto-resolved by backend when flow_key set)
  var body = {};

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

  // BridgeV002: collect flow_key + step_key for DB-driven dispatch (B4)
  var el_flow_key = document.getElementById("compile-flow_key");
  if (el_flow_key) body.flow_key = el_flow_key.value;

  var el_step_key = document.getElementById("compile-step_key");
  if (el_step_key) body.step_key = el_step_key.value;

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

      // Defensive cleanup: remove any stale Assign/Copy buttons that survived
      // (e.g. if a prior compile succeeded and the row wasn't reset for some reason)
      if (_assignBtnInRow && _assignBtnInRow.parentNode) {
        _assignBtnInRow.parentNode.removeChild(_assignBtnInRow);
      }
      if (_copyBtnInRow && _copyBtnInRow.parentNode) {
        _copyBtnInRow.parentNode.removeChild(_copyBtnInRow);
      }

      var compileButtonsRow = document.getElementById("compile-buttons-row");

      // Assign Handoff ID button — appended to the Prompt Templates buttonrow
      var assignBtn = el("button", "dpmtf-btn dpmtf-btn-primary");
      assignBtn.style.marginLeft = "8px";
      assignBtn.textContent = lbl("lbl_btn_assign_handoff_id", "Assign Handoff ID");
      assignBtn.onclick = function () { assignHandoffId(data.prompt, data); };
      if (compileButtonsRow) compileButtonsRow.appendChild(assignBtn);
      _assignBtnInRow = assignBtn;

      // Copy button — appended to the Prompt Templates buttonrow (last)
      var copyBtn = el("button", "dpmtf-btn dpmtf-small");
      copyBtn.style.marginLeft = "8px";
      copyBtn.textContent = lbl("lbl_btn_copy_prompt", "Copy Prompt");
      copyBtn.onclick = function () {
        navigator.clipboard.writeText(data.prompt).then(function () {
          copyBtn.textContent = lbl("lbl_btn_copied", "Copied!");
          setTimeout(function () { copyBtn.textContent = lbl("lbl_btn_copy_prompt", "Copy Prompt"); }, 2000);
        });
      };
      if (compileButtonsRow) compileButtonsRow.appendChild(copyBtn);
      _copyBtnInRow = copyBtn;

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

  // BridgeV002: pass resolved flow_key, step_key, deliverable_dir from compile response (B4)
  if (compileData.bridge_flow_key) body.flow_key = compileData.bridge_flow_key;
  if (compileData.bridge_step_key) body.step_key = compileData.bridge_step_key;
  if (compileData.deliverable_dir) body.deliverable_dir = compileData.deliverable_dir;

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

      // Defensive cleanup: remove stale Copy Command / Deliver to Bridge from
      // a previous assign, in case the dispatch-buttons-row was not reset.
      if (_copyCmdBtnInRow && _copyCmdBtnInRow.parentNode) {
        _copyCmdBtnInRow.parentNode.removeChild(_copyCmdBtnInRow);
      }
      if (_deliverBtnInRow && _deliverBtnInRow.parentNode) {
        _deliverBtnInRow.parentNode.removeChild(_deliverBtnInRow);
      }

      // Deliver to Bridge button (FIRST in dispatch-buttons-row, handoff 208)
      var deliverBtn = el("button", "dpmtf-btn dpmtf-btn-primary");
      deliverBtn.id = "compile-btn-deliver-to-bridge";
      deliverBtn.textContent = lbl("lbl_btn_deliver_to_bridge", "Deliver to Bridge");
      deliverBtn.onclick = deliverToBridge;
      var dispatchButtonsRow = document.getElementById("dispatch-buttons-row");
      if (dispatchButtonsRow) dispatchButtonsRow.appendChild(deliverBtn);
      _deliverBtnInRow = deliverBtn;

      // Copy dispatch command button (SECOND in dispatch-buttons-row, handoff 208)
      var copyCmdBtn = el("button", "dpmtf-btn dpmtf-small");
      copyCmdBtn.style.marginLeft = "8px";
      copyCmdBtn.textContent = lbl("lbl_btn_copy_command", "Copy Command");
      copyCmdBtn.onclick = function () {
        navigator.clipboard.writeText(result.dispatch_command).then(function () {
          copyCmdBtn.textContent = lbl("lbl_btn_copied", "Copied!");
          setTimeout(function () {
            copyCmdBtn.textContent = lbl("lbl_btn_copy_command", "Copy Command");
          }, 2000);
        });
      };
      if (dispatchButtonsRow) dispatchButtonsRow.appendChild(copyCmdBtn);
      _copyCmdBtnInRow = copyCmdBtn;

      // Update the displayed prompt with the real ID
      var outputDiv = document.getElementById("compile-output");
      var preElement = outputDiv ? outputDiv.querySelector("pre") : null;
      if (preElement && result.prompt) {
        preElement.textContent = result.prompt;
      }

      // Store context for Deliver to Bridge button
      _lastAssignedHandoff = {
        handoff_id: result.handoff_id,
        flow_key: result.flow_key,
        from_role: result.from_role,
        to_role: result.to_role,
      };
    })
    .catch(function (err) {
      clear(dispatchDiv);
      dispatchDiv.appendChild(el("p", "dpmtf-error",
        lbl("lbl_status_error_prefix", "Error: ") + escapeHtml(err.detail || err.message || "Failed to assign handoff ID")));
    });
}

/* ── Prompt Compiler: Deliver to Bridge (handoff 178) ── */
function deliverToBridge() {
  var dispatchDiv = document.getElementById("dispatch-info");
  var deliverBtn = document.getElementById("compile-btn-deliver-to-bridge");
  if (!_lastAssignedHandoff) {
    if (dispatchDiv) {
      dispatchDiv.style.display = "block";
      clear(dispatchDiv);
      dispatchDiv.appendChild(el("p", "dpmtf-error",
        lbl("lbl_status_error_prefix", "Error: ") + lbl("lbl_deliver_no_handoff", "No handoff ready. Assign a handoff ID first.")));
    }
    return;
  }

  var origLabel = deliverBtn ? deliverBtn.textContent : "";
  if (deliverBtn) {
    deliverBtn.disabled = true;
    deliverBtn.textContent = lbl("lbl_deliver_in_progress", "Delivering...");
  }

  fetch("/api/prompt-compiler/dispatch", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      flow_key: _lastAssignedHandoff.flow_key,
      from_role: _lastAssignedHandoff.from_role,
      to_role: _lastAssignedHandoff.to_role,
      handoff_id: _lastAssignedHandoff.handoff_id,
    })
  })
    .then(function (res) {
      return res.json().then(function (data) { return { ok: res.ok, data: data }; });
    })
    .then(function (resp) {
      if (dispatchDiv) {
        dispatchDiv.style.display = "block";
        clear(dispatchDiv);
      }
      var data = resp.data || {};
      if (resp.ok && data.success) {
        var successP = el("p", null);
        var successBadge = el("span", "dpmtf-badge dpmtf-badge-success");
        successBadge.textContent = "✅ " + lbl("lbl_deliver_success", "Handoff {ID} delivered to {TO}").replace("{ID}", data.handoff_id).replace("{TO}", data.to_role);
        successP.appendChild(successBadge);
        if (dispatchDiv) dispatchDiv.appendChild(successP);
        if (data.output) {
          var outPre = el("pre", null);
          outPre.style.whiteSpace = "pre-wrap";
          outPre.style.fontSize = "0.8em";
          outPre.style.background = "#0d1117";
          outPre.style.padding = "8px";
          outPre.style.borderRadius = "4px";
          outPre.style.maxHeight = "300px";
          outPre.style.overflowY = "auto";
          outPre.textContent = data.output;
          if (dispatchDiv) dispatchDiv.appendChild(outPre);
        }
      } else {
        if (dispatchDiv) {
          dispatchDiv.appendChild(el("p", "dpmtf-error",
            lbl("lbl_status_error_prefix", "Error: ") + escapeHtml(data.error || data.detail || data.output || "Dispatch failed")));
        }
      }
    })
    .catch(function (err) {
      if (dispatchDiv) {
        dispatchDiv.style.display = "block";
        clear(dispatchDiv);
        dispatchDiv.appendChild(el("p", "dpmtf-error",
          lbl("lbl_status_error_prefix", "Error: ") + escapeHtml(err.message || "Dispatch request failed")));
      }
    })
    .then(function () {
      if (deliverBtn) {
        deliverBtn.disabled = false;
        deliverBtn.textContent = origLabel || lbl("lbl_btn_deliver_to_bridge", "Deliver to Bridge");
      }
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

function getTargetProject() {
  // Read from the compile form's target_project input (most current value)
  var input = document.getElementById("compile-target_project");
  if (input && input.value.trim()) {
    return input.value.trim();
  }
  // Fallback: DPMTF_PROJECT_ROOT from page context
  var meta = document.querySelector("meta[name='project-root']");
  if (meta) return meta.getAttribute("content");
  return "";
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

  // Fields in aggregated order (top-down = how the command is built)
  var targetProject = getTargetProject();
  var fields = [
    // 1. tmux_session — first part of aggregated command
    [lbl("lbl_bridge_tmux_session", "Tmux Session"), role.tmux_session],
    // 2. target_project — read-only, from Prompt Compiler
    [lbl("lbl_compiler_target_project", "Target Project"), targetProject || "(not set)"],
    // Model Allocator info
    [lbl("lbl_bridge_default_model_source", "Model Source"), role.default_model_source],
    [lbl("lbl_bridge_default_model_alias", "Model Alias"), role.default_model_alias],
    // Remaining fields
    [lbl("lbl_bridge_governance_file", "Governance File"), role.governance_file],
    [lbl("lbl_bridge_role_type", "Role Type"), role.role_type && role.role_type !== "agent" ? role.role_type : null],
    [lbl("lbl_bridge_enter_command", "Enter Command"), role.enter_command || "default"],
  ];
  fields.forEach(function (pair) {
    if (!pair[1]) return;
    var row = el("div", null);
    var label = pair[0];
    row.appendChild(el("span", "dpmtf-small", escapeHtml(label) + ": "));
    var valSpan = el("span", null, escapeHtml(String(pair[1])));
    row.appendChild(valSpan);
    card.appendChild(row);
  });

  // Action buttons: Rename, Edit and Delete
  var actions = el("div", null);
  actions.style.marginTop = "8px";

  // Rename button (was the old "Edit")
  var renameBtn = el("button", "dpmtf-btn");
  renameBtn.textContent = lbl("lbl_bridge_rename", "Rename");
  renameBtn.onclick = function () { renameBridgeRole(role.role_key); };
  actions.appendChild(renameBtn);

  // Edit button (new full edit)
  var editBtn = el("button", "dpmtf-btn");
  editBtn.textContent = lbl("lbl_bridge_edit", "Edit");
  editBtn.onclick = function () { editBridgeRoleFull(role.role_key); };
  actions.appendChild(editBtn);

  // Delete button (unchanged)
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

  // Target project — shown on the card itself so an unset path is visible
  // before dispatching. Reuses the edit form's labels (migration 018).
  var tpLine = el("p", "dpmtf-small");
  tpLine.appendChild(el("span", "dpmtf-muted",
    lbl("lbl_bridge_flow_target_project", "Target Project Path") + ": "));
  if (flow.target_project_path) {
    var tpValue = el("span", null, flow.target_project_path);
    tpValue.style.fontFamily = "monospace";
    tpLine.appendChild(tpValue);
  } else {
    tpLine.appendChild(el("span", "dpmtf-muted",
      lbl("lbl_bridge_flow_target_project_placeholder", "Empty = this project")));
  }
  card.appendChild(tpLine);

  // Step count badge
  if (steps && steps.length) {
    card.appendChild(el("p", "dpmtf-badge dpmtf-badge-info", String(steps.length) + " step(s)"));
  } else {
    card.appendChild(el("p", "dpmtf-muted", lbl("lbl_bridge_no_steps", "No steps configured")));
  }

  if (flow.auto_complete_enabled) {
    var acBadge = el("span", "dpmtf-badge dpmtf-badge-warning");
    acBadge.textContent = lbl("lbl_bridge_flow_auto_complete", "Auto-complete enabled");
    card.appendChild(acBadge);
  }

  // Action buttons
  var actions = el("div", null);
  actions.style.marginTop = "8px";

  var manageBtn = el("button", "dpmtf-btn dpmtf-btn-primary");
  manageBtn.textContent = lbl("lbl_bridge_manage_steps", "Manage Steps");
  manageBtn.onclick = function () {
    _bridgeStepsFlowKey = flow.flow_key;
    var sel = document.getElementById("bridge-steps-flow-select");
    if (sel) sel.value = flow.flow_key;
    _fetchBridgeSteps(flow.flow_key);
    var stepsSection = document.getElementById("bridge-steps-section");
    if (stepsSection) stepsSection.scrollIntoView({ behavior: "smooth" });
  };
  actions.appendChild(manageBtn);

  var renameBtn = el("button", "dpmtf-btn");
  renameBtn.textContent = lbl("lbl_bridge_rename", "Rename");
  renameBtn.onclick = function () { editBridgeFlow(flow.flow_key); };
  actions.appendChild(renameBtn);

  var editBtn = el("button", "dpmtf-btn");
  editBtn.textContent = lbl("lbl_bridge_edit", "Edit");
  editBtn.onclick = function () { editBridgeFlowFull(flow.flow_key); };
  actions.appendChild(editBtn);

  // --- START TMUX button (new for BridgeV002) ---
  var startTmuxBtn = el("button", "dpmtf-btn dpmtf-btn-success");
  startTmuxBtn.textContent = lbl("lbl_bridge_start_tmux", "Start tmux");
  startTmuxBtn.onclick = function () { startTmuxForFlow(flow.flow_key); };
  actions.appendChild(startTmuxBtn);

  // --- START CODING button (new for BridgeV002) ---
  var startCodingBtn = el("button", "dpmtf-btn dpmtf-btn-info");
  startCodingBtn.textContent = lbl("lbl_bridge_start_coding", "Start code interface");
  startCodingBtn.onclick = function () { startCodingForFlow(flow.flow_key); };
  actions.appendChild(startCodingBtn);

  // --- ATTACH TMUX button (new for BridgeV002) ---
  var attachTmuxBtn = el("button", "dpmtf-btn dpmtf-btn-info");
  attachTmuxBtn.textContent = lbl("lbl_bridge_attach_tmux", "Attach tmux");
  attachTmuxBtn.onclick = function () { attachTmuxForFlow(flow.flow_key); };
  actions.appendChild(attachTmuxBtn);

  // --- STOP TMUX button (new for BridgeV002) ---
  var stopTmuxBtn = el("button", "dpmtf-btn dpmtf-btn-danger");
  stopTmuxBtn.textContent = lbl("lbl_bridge_stop_tmux", "Stop tmux");
  stopTmuxBtn.onclick = function () { stopTmuxForFlow(flow.flow_key); };
  actions.appendChild(stopTmuxBtn);

  // --- STOP SERVERS button ---
  var stopServersBtn = el("button", "dpmtf-btn dpmtf-btn-warning");
  stopServersBtn.textContent = lbl("lbl_bridge_stop_servers", "Stop servers");
  stopServersBtn.onclick = function () { stopServersForFlow(flow.flow_key); };
  actions.appendChild(stopServersBtn);

  // --- DELETE button (moved to end of row by handoff 002) ---
  var delBtn = el("button", "dpmtf-btn dpmtf-btn-danger");
  delBtn.textContent = lbl("lbl_bridge_delete", "Delete");
  delBtn.onclick = function () { deleteBridgeFlow(flow.flow_key); };
  actions.appendChild(delBtn);

  card.appendChild(actions);

  // Attach command — the viewer session built by "Attach tmux" groups this
  // flow's role windows, so one command reconnects to all of them. The
  // session name comes from the API (derived from attach_tmux.py's prefix),
  // never spelled out here. Kept at the bottom of the card, below the
  // action buttons.
  var viewerSession = flow.viewer_session || "";
  if (viewerSession) {
    var attachCmd = "tmux attach -t " + viewerSession;

    var attachDiv = el("div", "dpmtf-form-group");
    attachDiv.style.marginTop = "8px";
    attachDiv.appendChild(el("label", "dpmtf-label",
      lbl("lbl_bridge_flow_attach_command", "Attach command")));

    var attachRow = el("div", null);
    attachRow.style.display = "flex";
    attachRow.style.gap = "8px";
    attachRow.style.alignItems = "center";

    var attachInput = el("input", null);
    attachInput.type = "text";
    attachInput.value = attachCmd;
    attachInput.readOnly = true;
    attachInput.style.flex = "1";
    attachInput.style.fontFamily = "monospace";
    attachInput.onclick = function () { attachInput.select(); };
    attachRow.appendChild(attachInput);

    var attachCopyBtn = el("button", "dpmtf-btn dpmtf-small");
    attachCopyBtn.textContent = lbl("lbl_btn_copy_command", "Copy Command");
    attachCopyBtn.onclick = function () {
      copyTextToClipboard(attachCmd, function (ok) {
        attachCopyBtn.textContent = ok
          ? lbl("lbl_btn_copied", "Copied!")
          : lbl("lbl_btn_copy_failed", "Copy failed — select and copy manually");
        setTimeout(function () {
          attachCopyBtn.textContent = lbl("lbl_btn_copy_command", "Copy Command");
        }, 2000);
      });
    };
    attachRow.appendChild(attachCopyBtn);

    attachDiv.appendChild(attachRow);
    attachDiv.appendChild(el("p", "dpmtf-muted",
      lbl("lbl_bridge_flow_attach_hint",
        "Run \"Attach tmux\" first to build this session, then paste the command in a terminal.")));
    card.appendChild(attachDiv);
  }

  return card;
}

// ---- START TMUX FOR FLOW (BridgeV002) ----
function startTmuxForFlow(flowKey) {
  fetch("/api/bridge-v2/flows/" + flowKey + "/start-tmux", { method: "POST" })
    .then(function(res) { return res.json(); })
    .then(function(data) {
      if (data.status === "ok") {
        alert("✅ " + data.message);
      } else {
        alert("❌ " + lbl("lbl_error_prefix", "Error: ") + (data.detail || lbl("lbl_unknown_error", "Unknown error")));
      }
    })
    .catch(function(err) {
      alert(lbl("lbl_network_error_prefix", "Network error: ") + err.message);
    });
}

// ---- START CODING FOR FLOW (BridgeV002) ----
function startCodingForFlow(flowKey) {
  fetch("/api/bridge-v2/flows/" + flowKey + "/start-coding", { method: "POST" })
    .then(function(res) { return res.json(); })
    .then(function(data) {
      if (data.status === "ok") {
        alert("✅ " + data.message);
      } else {
        alert("❌ " + lbl("lbl_error_prefix", "Error: ") + (data.detail || lbl("lbl_unknown_error", "Unknown error")));
      }
    })
    .catch(function(err) {
      alert(lbl("lbl_network_error_prefix", "Network error: ") + err.message);
    });
}

// ---- STOP TMUX FOR FLOW (BridgeV002) ----
function stopTmuxForFlow(flowKey) {
  if (!confirm(lbl("lbl_confirm_stop_tmux_sessions", "Stop all tmux sessions for '{flowKey}'?").replace("{flowKey}", flowKey))) return;
  fetch("/api/bridge-v2/flows/" + flowKey + "/stop-tmux", { method: "POST" })
    .then(function(res) { return res.json(); })
    .then(function(data) {
      if (data.status === "ok") {
        alert("✅ " + data.message);
      } else {
        alert("❌ " + lbl("lbl_error_prefix", "Error: ") + (data.detail || lbl("lbl_unknown_error", "Unknown error")));
      }
    })
    .catch(function(err) {
      alert(lbl("lbl_network_error_prefix", "Network error: ") + err.message);
    });
}

// ---- STOP SERVERS FOR FLOW ----
function stopServersForFlow(flowKey) {
  if (!confirm(lbl("lbl_confirm_stop_servers", "Stop all model servers (llama.cpp, SGLang) for '{flowKey}'?").replace("{flowKey}", flowKey))) return;
  fetch("/api/bridge-v2/flows/" + flowKey + "/stop-servers", { method: "POST" })
    .then(function(res) { return res.json(); })
    .then(function(data) {
      if (data.status === "ok") {
        alert("✅ " + data.message);
      } else if (data.status === "partial") {
        alert("⚠️ " + data.message);
      } else {
        alert("❌ " + lbl("lbl_error_prefix", "Error: ") + (data.detail || lbl("lbl_unknown_error", "Unknown error")));
      }
    })
    .catch(function(err) {
      alert(lbl("lbl_network_error_prefix", "Network error: ") + err.message);
    });
}

// ---- ATTACH TMUX FOR FLOW (BridgeV002) ----
function attachTmuxForFlow(flowKey) {
  fetch("/api/bridge-v2/flows/" + flowKey + "/attach-tmux", { method: "POST" })
    .then(function(res) { return res.json(); })
    .then(function(data) {
      if (data.status === "ok") {
        alert("✅ " + data.message);
      } else {
        alert("❌ " + lbl("lbl_error_prefix", "Error: ") + (data.detail || lbl("lbl_unknown_error", "Unknown error")));
      }
    })
    .catch(function(err) {
      alert(lbl("lbl_network_error_prefix", "Network error: ") + err.message);
    });
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
    var ec = document.getElementById("bridge-input-enter_command");
    if (ec) body.enter_command = ec.value;

    // Runtime config
    var pmEl = document.getElementById("bridge-input-trade-mcp-push-mode");
    var moEl = document.getElementById("bridge-input-max-output-tokens");
    if (pmEl) body.trade_mcp_push_mode = pmEl.value || null;
    if (moEl) body.max_output_tokens = moEl.value ? parseInt(moEl.value, 10) : null;

    // V3A: Model Allocator source / alias
    var msEl = document.getElementById("bridge-role-model-source");
    var maEl = document.getElementById("bridge-role-model-alias");
    if (msEl) body.default_model_source = msEl.value || null;
    if (maEl && !maEl.disabled) body.default_model_alias = maEl.value.trim() || null;

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

  // H150: Enter command select
  var ecDiv = el("div", "dpmtf-form-group");
  ecDiv.appendChild(el("label", "dpmtf-label", lbl("lbl_bridge_enter_command", "Enter Command")));
  var ecSelect = el("select", null);
  ecSelect.id = "bridge-input-enter_command";
  [["default", "Default (Enter)"], ["c-m", "C-m (Freebuff two-step)"], ["c-j", "C-j (Ctrl+J)"], ["c-d", "C-d (Ctrl+D)"]].forEach(function (pair) {
    var opt = document.createElement("option");
    opt.value = pair[0];
    opt.textContent = pair[1];
    ecSelect.appendChild(opt);
  });
  ecDiv.appendChild(ecSelect);
  form.appendChild(ecDiv);

  // Runtime config: trade-mcp push mode + max output tokens
  var rcDiv = el("div", "dpmtf-form-group");
  rcDiv.appendChild(el("label", "dpmtf-label", lbl("lbl_bridge_trade_mcp_push_mode", "Trade-MCP Push Mode")));
  var pmSelect = el("select", null);
  pmSelect.id = "bridge-input-trade-mcp-push-mode";
  ["", "watchlist", "market", "risk"].forEach(function (m) {
    var opt = el("option", null);
    opt.value = m;
    opt.textContent = m || lbl("lbl_bridge_model_source_default", "Default / inherit");
    pmSelect.appendChild(opt);
  });
  pmSelect.value = "";
  rcDiv.appendChild(pmSelect);
  form.appendChild(rcDiv);

  var moDiv = el("div", "dpmtf-form-group");
  moDiv.appendChild(el("label", "dpmtf-label", lbl("lbl_bridge_max_output_tokens", "Max Output Tokens")));
  var moInput = el("input", null);
  moInput.type = "number";
  moInput.min = "1024";
  moInput.step = "1024";
  moInput.id = "bridge-input-max-output-tokens";
  moInput.value = "";
  moDiv.appendChild(moInput);
  form.appendChild(moDiv);

  // V3A: Model Allocator source / alias
  var allocatorControl = createModelSourceControl(
    "bridge-role",
    null,
    null,
    function () { return "opencode"; },
    {
      source: "lbl_bridge_default_model_source",
      alias: "lbl_bridge_default_model_alias",
      validate: "lbl_bridge_validate_allocator"
    },
    [
      ["", lbl("lbl_bridge_model_source_default", "Default / inherit")],
      ["model_allocator", "model_allocator"]
    ]
  );
  form.appendChild(allocatorControl.container);

  var btnRow = el("div", null);
  btnRow.appendChild(saveBtn);
  btnRow.appendChild(cancelBtn);
  form.appendChild(btnRow);

  container.insertBefore(form, container.firstChild);
}

// Update role save to include allocator fields
var _origAddBridgeRoleSave = null;

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
    var acInput = document.getElementById("bridge-input-auto_complete_enabled");
    if (acInput) body.auto_complete_enabled = acInput.checked ? 1 : 0;
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

  var acDiv = el("div", null);
  var acLabel = el("label", null);
  var acInput = el("input", null);
  acInput.type = "checkbox";
  acInput.id = "bridge-input-auto_complete_enabled";
  acLabel.appendChild(acInput);
  acLabel.appendChild(document.createTextNode(" " + lbl("lbl_bridge_flow_auto_complete", "Auto-complete enabled")));
  acDiv.appendChild(acLabel);
  form.appendChild(acDiv);

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
    .then(function (res) {
      if (!res.ok) return res.text().then(function (txt) { throw new Error(txt); });
      return res.json();
    })
    .then(function () {
      alert(lbl("lbl_bridge_deleted", "Successfully deleted") + ": " + flowKey);
      loadBridgeFlows();
    })
    .catch(function (err) {
      alert(lbl("lbl_status_error_prefix", "Error: ") + escapeHtml(err.message));
    });
}

function renameBridgeRole(oldRoleKey) {
  var newKey = prompt(lbl("lbl_bridge_rename", "Rename") + " (" + escapeHtml(oldRoleKey) + "):");
  if (newKey === null) return;
  newKey = newKey.trim();
  if (!newKey || newKey === oldRoleKey) {
    alert(lbl("lbl_status_error_prefix", "Error: ") + lbl("lbl_bridge_rename_invalid", "No change made"));
    return;
  }

  fetch("/api/bridge-v2/roles/" + encodeURIComponent(oldRoleKey) + "/rename", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ new_role_key: newKey })
  })
    .then(function (res) { return res.json(); })
    .then(function (data) {
      if (data.dependents && data.dependents > 0) {
        var msg = lbl("lbl_bridge_renamed", "Successfully renamed") + ": " + oldRoleKey + " → " + escapeHtml(newKey);
        msg += "\n\n" + escapeHtml(String(data.dependents)) + " flow step(s) reference this role.";
        alert(msg);
      } else {
        alert(lbl("lbl_bridge_renamed", "Successfully renamed") + ": " + oldRoleKey + " → " + escapeHtml(newKey));
      }
      loadBridgeRoles();
    })
    .catch(function (err) {
      alert(lbl("lbl_status_error_prefix", "Error: ") + escapeHtml(err.message));
    });
}

function editBridgeRoleFull(roleKey) {
  fetch("/api/bridge-v2/roles/" + encodeURIComponent(roleKey))
    .then(function (res) { return res.json(); })
    .then(function (data) {
      var role = data.role;

      var existing = document.getElementById("bridge-role-edit-form");
      if (existing) { existing.remove(); }

      var form = el("div", "dpmtf-card");
      form.id = "bridge-role-edit-form";

      var cancelBtn = el("button", "dpmtf-btn");
      cancelBtn.textContent = lbl("lbl_bridge_cancel", "Cancel");
      cancelBtn.onclick = function () { form.remove(); };

      var saveBtn = el("button", "dpmtf-btn dpmtf-btn-primary");
      saveBtn.textContent = lbl("lbl_bridge_save", "Save");
      saveBtn.onclick = function () {
        var body = {};

        var ts = document.getElementById("bridge-edit-input-tmux_session").value.trim();
        if (!ts) { alert(lbl("lbl_bridge_tmux_session", "Tmux Session") + " is required."); return; }
        body.tmux_session = ts;

        var gf = document.getElementById("bridge-edit-input-governance_file");
        if (gf && gf.value) {
          body.governance_file = gf.value;
        } else if (gf && gf.value === "") {
          body.governance_file = null;
        }

        // G1: role_type select — agent (default) or human
        var rt = document.getElementById("bridge-edit-input-role_type");
        if (rt && rt.value) {
          body.role_type = rt.value;
        }

        // H150: enter_command select
        var ec = document.getElementById("bridge-edit-input-enter_command");
        if (ec) {
          body.enter_command = ec.value;
        }

        // Migration 023: workdir_mode select
        var wm = document.getElementById("bridge-edit-input-workdir_mode");
        if (wm && wm.value) {
          body.workdir_mode = wm.value;
        }

        // Runtime config
        var pmEl = document.getElementById("bridge-edit-input-trade-mcp-push-mode");
        var moEl = document.getElementById("bridge-edit-input-max-output-tokens");
        if (pmEl) body.trade_mcp_push_mode = pmEl.value || null;
        if (moEl) body.max_output_tokens = moEl.value ? parseInt(moEl.value, 10) : null;

        // V3A: Model Allocator source / alias
        var msEl = document.getElementById("bridge-edit-role-model-source");
        var maEl = document.getElementById("bridge-edit-role-model-alias");
        if (msEl) body.default_model_source = msEl.value || null;
        if (maEl && !maEl.disabled) body.default_model_alias = maEl.value.trim() || null;

        fetch("/api/bridge-v2/roles/" + encodeURIComponent(roleKey), {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body)
        })
          .then(function (res) { return res.json(); })
          .then(function () {
            alert(lbl("lbl_bridge_updated", "Successfully updated") + ": " + escapeHtml(roleKey));
            loadBridgeRoles();
          })
          .catch(function (err) {
            alert(lbl("lbl_status_error_prefix", "Error: ") + escapeHtml(err.message));
          });
      };

      form.appendChild(el("h4", null, lbl("lbl_bridge_edit_role", "Edit Role") + ": " + escapeHtml(roleKey)));
      form.appendChild(cancelBtn);
      form.appendChild(saveBtn);
      form.style.display = "flex";
      form.style.flexDirection = "column";
      form.style.gap = "8px";

      // role_key (readonly)
      var rkDiv = el("div", "dpmtf-form-group");
      rkDiv.appendChild(el("label", "dpmtf-label", lbl("lbl_bridge_role_key", "Role Key") + " " + el("span", "dpmtf-badge dpmtf-badge-danger", "(locked)")));
      var rkInput = el("input", null);
      rkInput.id = "bridge-edit-input-role_key";
      rkInput.type = "text";
      rkInput.value = role.role_key;
      rkInput.disabled = true;
      rkInput.style.background = "#161b22";
      rkInput.style.color = "#8b949e";
      rkDiv.appendChild(rkInput);
      form.appendChild(rkDiv);

      // tmux_session
      var tsDiv = el("div", "dpmtf-form-group");
      tsDiv.appendChild(el("label", "dpmtf-label", lbl("lbl_bridge_tmux_session", "Tmux Session")));
      var tsInput = el("input", null);
      tsInput.id = "bridge-edit-input-tmux_session";
      tsInput.type = "text";
      tsInput.value = role.tmux_session || "";
      tsDiv.appendChild(tsInput);
      form.appendChild(tsDiv);

      // governance_file select — loaded dynamically from disk
      var gfDiv = el("div", "dpmtf-form-group");
      gfDiv.appendChild(el("label", "dpmtf-label", lbl("lbl_bridge_governance_file", "Governance File")));
      var gfSelect = el("select", null);
      gfSelect.id = "bridge-edit-input-governance_file";

      // None option (always first)
      var noneOpt = document.createElement("option");
      noneOpt.value = "";
      noneOpt.textContent = lbl("lbl_bridge_none_option", "(None)");
      if (!role.governance_file) noneOpt.selected = true;
      gfSelect.appendChild(noneOpt);

      fetch("/api/bridge-v2/governance-files")
        .then(function (res) { return res.json(); })
        .then(function (data) {
          var files = data.files || [];
          files.forEach(function (f) {
            var opt = document.createElement("option");
            opt.value = f;
            opt.textContent = f;
            if (role.governance_file === f) opt.selected = true;
            gfSelect.appendChild(opt);
          });
        })
        .catch(function () {
          // Silently OK — dropdown stays with (None) only
        });

      gfDiv.appendChild(gfSelect);
      form.appendChild(gfDiv);

      // G1: role_type select — agent (default) or human
      var rtDiv = el("div", "dpmtf-form-group");
      rtDiv.appendChild(el("label", "dpmtf-label", lbl("lbl_bridge_role_type", "Role Type")));
      var rtSelect = el("select", null);
      rtSelect.id = "bridge-edit-input-role_type";
      ["agent", "human"].forEach(function (val) {
        var opt = document.createElement("option");
        opt.value = val;
        opt.textContent = val.charAt(0).toUpperCase() + val.slice(1);
        if ((role.role_type || "agent") === val) opt.selected = true;
        rtSelect.appendChild(opt);
      });
      rtDiv.appendChild(rtSelect);
      form.appendChild(rtDiv);

      // Migration 023: workdir_mode select — which directory the role's
      // coding session starts in. Prompts stay cwd-independent (dispatch
      // injects absolute governance paths), so this only moves the shell.
      var wmDiv = el("div", "dpmtf-form-group");
      wmDiv.appendChild(el("label", "dpmtf-label",
        lbl("lbl_bridge_workdir_mode", "Working Directory")));
      var wmSelect = el("select", null);
      wmSelect.id = "bridge-edit-input-workdir_mode";
      [
        ["target_project", lbl("lbl_bridge_workdir_target", "Flow's target project")],
        ["father", lbl("lbl_bridge_workdir_father", "This project (Father)")]
      ].forEach(function (pair) {
        var opt = document.createElement("option");
        opt.value = pair[0];
        opt.textContent = pair[1];
        if ((role.workdir_mode || "target_project") === pair[0]) opt.selected = true;
        wmSelect.appendChild(opt);
      });
      wmDiv.appendChild(wmSelect);
      wmDiv.appendChild(el("p", "dpmtf-muted",
        lbl("lbl_bridge_workdir_help",
          "Where this role's coding session starts. Chain workers follow the flow's Target Project Path; supervisors and architects stay in this project.")));
      form.appendChild(wmDiv);

      // H150: enter_command select
      var ecDiv2 = el("div", "dpmtf-form-group");
      ecDiv2.appendChild(el("label", "dpmtf-label", lbl("lbl_bridge_enter_command", "Enter Command")));
      var ecSelect2 = el("select", null);
      ecSelect2.id = "bridge-edit-input-enter_command";
      [["default", "Default (Enter)"], ["c-m", "C-m (Freebuff two-step)"], ["c-j", "C-j (Ctrl+J)"], ["c-d", "C-d (Ctrl+D)"]].forEach(function (pair) {
        var opt = document.createElement("option");
        opt.value = pair[0];
        opt.textContent = pair[1];
        if ((role.enter_command || "default") === pair[0]) opt.selected = true;
        ecSelect2.appendChild(opt);
      });
      ecDiv2.appendChild(ecSelect2);
      form.appendChild(ecDiv2);

      // Runtime config: trade-mcp push mode + max output tokens
      var pmDiv = el("div", "dpmtf-form-group");
      pmDiv.appendChild(el("label", "dpmtf-label", lbl("lbl_bridge_trade_mcp_push_mode", "Trade-MCP Push Mode")));
      var pmSelect = el("select", null);
      pmSelect.id = "bridge-edit-input-trade-mcp-push-mode";
      ["", "watchlist", "market", "risk"].forEach(function (m) {
        var opt = el("option", null);
        opt.value = m;
        opt.textContent = m || lbl("lbl_bridge_model_source_default", "Default / inherit");
        pmSelect.appendChild(opt);
      });
      pmSelect.value = role.trade_mcp_push_mode || "";
      pmDiv.appendChild(pmSelect);
      form.appendChild(pmDiv);

      var moDiv = el("div", "dpmtf-form-group");
      moDiv.appendChild(el("label", "dpmtf-label", lbl("lbl_bridge_max_output_tokens", "Max Output Tokens")));
      var moInput = el("input", null);
      moInput.type = "number";
      moInput.min = "1024";
      moInput.step = "1024";
      moInput.id = "bridge-edit-input-max-output-tokens";
      moInput.value = role.max_output_tokens != null ? String(role.max_output_tokens) : "";
      moDiv.appendChild(moInput);
      form.appendChild(moDiv);

      // V3A: Model Allocator source / alias
      var allocatorControl = createModelSourceControl(
        "bridge-edit-role",
        role.default_model_source,
        role.default_model_alias,
        function () { return "opencode"; },
        {
          source: "lbl_bridge_default_model_source",
          alias: "lbl_bridge_default_model_alias",
          validate: "lbl_bridge_validate_allocator"
        },
        [
          ["", lbl("lbl_bridge_model_source_default", "Default / inherit")],
          ["model_allocator", "model_allocator"]
        ]
      );
      form.appendChild(allocatorControl.container);

      // H160: Target Project (read-only, from Prompt Compiler)
      var tpDiv = el("div", "dpmtf-form-group");
      tpDiv.appendChild(el("label", "dpmtf-label", lbl("lbl_compiler_target_project", "Target Project")));
      var tpDisplay = el("div", null);
      tpDisplay.style.padding = "8px";
      tpDisplay.style.background = "#161b22";
      tpDisplay.style.borderRadius = "4px";
      tpDisplay.style.fontFamily = "monospace";
      tpDisplay.style.fontSize = "12px";
      tpDisplay.textContent = getTargetProject() || "(not set)";
      tpDiv.appendChild(tpDisplay);
      form.appendChild(tpDiv);

      var container = document.getElementById("bridge-roles-list-container");
      if (container) {
        container.insertBefore(form, container.firstChild);
      }
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

function editBridgeFlowFull(flowKey) {
  fetch("/api/bridge-v2/flows/" + encodeURIComponent(flowKey))
    .then(function (res) { return res.json(); })
    .then(function (data) {
      var flow = data.flow;

      var existing = document.getElementById("bridge-flow-edit-form");
      if (existing) { existing.remove(); }

      var form = el("div", "dpmtf-card");
      form.id = "bridge-flow-edit-form";

      var cancelBtn = el("button", "dpmtf-btn");
      cancelBtn.textContent = lbl("lbl_bridge_cancel", "Cancel");
      cancelBtn.onclick = function () { form.remove(); };

      var saveBtn = el("button", "dpmtf-btn dpmtf-btn-primary");
      saveBtn.textContent = lbl("lbl_bridge_save", "Save");
      saveBtn.onclick = function () {
        var body = {};
        var nm = document.getElementById("bridge-edit-input-name").value.trim();
        if (!nm) { alert(lbl("lbl_bridge_flow_name", "Name") + " is required."); return; }
        body.name = nm;

        var desc = document.getElementById("bridge-edit-input-description");
        if (desc) body.description = desc.value.trim();

        var acInput = document.getElementById("bridge-edit-input-auto_complete_enabled");
        if (acInput) body.auto_complete_enabled = acInput.checked ? 1 : 0;

        var tpInput = document.getElementById("bridge-edit-input-target_project_path");
        if (tpInput) body.target_project_path = tpInput.value.trim();

        fetch("/api/bridge-v2/flows/" + encodeURIComponent(flowKey), {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body)
        })
          .then(function (res) {
            // A rejected target path returns 400 — surface it instead of
            // reporting success for a change the server refused to store.
            return res.json().then(function (payload) {
              if (!res.ok) {
                throw new Error(payload.detail || res.status);
              }
              return payload;
            });
          })
          .then(function () {
            alert(lbl("lbl_bridge_updated", "Successfully updated") + ": " + flowKey);
            loadBridgeFlows();
          })
          .catch(function (err) {
            alert(lbl("lbl_status_error_prefix", "Fejl: ") + (err.message || ""));
          });
      };

      form.appendChild(el("h4", null, lbl("lbl_bridge_edit_flow", "Edit Flow") + ": " + escapeHtml(flowKey)));

      // flow_key (readonly)
      var fkDiv = el("div", "dpmtf-form-group");
      fkDiv.appendChild(el("label", "dpmtf-label", lbl("lbl_bridge_flow_key", "Flow Key") + " (locked)"));
      var fkInput = el("input", null);
      fkInput.type = "text";
      fkInput.value = flow.flow_key;
      fkInput.disabled = true;
      fkInput.style.background = "#161b22";
      fkInput.style.color = "#8b949e";
      fkDiv.appendChild(fkInput);
      form.appendChild(fkDiv);

      // name
      var nmDiv = el("div", "dpmtf-form-group");
      nmDiv.appendChild(el("label", "dpmtf-label", lbl("lbl_bridge_flow_name", "Name")));
      var nmInput = el("input", null);
      nmInput.id = "bridge-edit-input-name";
      nmInput.type = "text";
      nmInput.value = flow.name || "";
      nmDiv.appendChild(nmInput);
      form.appendChild(nmDiv);

      // description
      var descDiv = el("div", "dpmtf-form-group");
      descDiv.appendChild(el("label", "dpmtf-label", lbl("lbl_bridge_flow_description", "Description")));
      var descInput = el("input", null);
      descInput.id = "bridge-edit-input-description";
      descInput.type = "text";
      descInput.value = flow.description || "";
      descDiv.appendChild(descInput);
      form.appendChild(descDiv);

      // target_project_path — the repository this flow's roles operate in.
      // Empty means this project (Father). Dispatch states the resolved path
      // in a Target Project block at the top of every injected prompt.
      var tpDiv = el("div", "dpmtf-form-group");
      tpDiv.appendChild(el("label", "dpmtf-label",
        lbl("lbl_bridge_flow_target_project", "Target Project Path")));
      var tpInput = el("input", null);
      tpInput.id = "bridge-edit-input-target_project_path";
      tpInput.type = "text";
      tpInput.value = flow.target_project_path || "";
      tpInput.placeholder = lbl("lbl_bridge_flow_target_project_placeholder",
        "Empty = this project");
      tpDiv.appendChild(tpInput);
      tpDiv.appendChild(el("p", "dpmtf-muted",
        lbl("lbl_bridge_flow_target_project_help",
          "Absolute path to the repository this flow's roles work in. Must exist. Leave empty for flows that operate on this project.")));
      form.appendChild(tpDiv);

      // auto_complete_enabled checkbox
      var acDiv = el("div", null);
      var acLabel = el("label", null);
      var acInput = el("input", null);
      acInput.type = "checkbox";
      acInput.id = "bridge-edit-input-auto_complete_enabled";
      if (flow.auto_complete_enabled) acInput.checked = true;
      acLabel.appendChild(acInput);
      acLabel.appendChild(document.createTextNode(" " + lbl("lbl_bridge_flow_auto_complete", "Auto-complete enabled")));
      acDiv.appendChild(acLabel);
      form.appendChild(acDiv);

      var btnRow = el("div", null);
      btnRow.appendChild(saveBtn);
      btnRow.appendChild(cancelBtn);
      form.appendChild(btnRow);

      var container = document.getElementById("bridge-flows-list-container");
      if (container) container.insertBefore(form, container.firstChild);
    })
    .catch(function (err) {
      alert(lbl("lbl_status_error_prefix", "Fejl: ") + (err.message || ""));
    });
}

function buildBridgeExport() {
  var container = document.getElementById("bridge-export-content");
  if (!container) return;
  clear(container);

  [
    ["all", lbl("lbl_bridge_export_all", "View All")],
    ["roles", lbl("lbl_bridge_export_roles", "View Roles")],
    ["flows", lbl("lbl_bridge_export_flows", "View Flows")],
    ["all_steps", lbl("lbl_bridge_view_all_steps", "View All Steps")],
    ["all_data", lbl("lbl_bridge_export_all_data", "Export all data")]
  ].forEach(function (pair) {
    var btn = el("button", "dpmtf-btn");
    btn.textContent = pair[1];
    if (pair[0] === "all_data") {
      btn.onclick = function () { exportAllData(); };
    } else {
      btn.onclick = function () { exportBridge(pair[0]); };
    }
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

  var requestType = type === "all_steps" ? "all" : type;

  fetch("/api/bridge-v2/export", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ type: requestType })
  })
    .then(function (res) { return res.json(); })
    .then(function (data) {
      var payload = data.data || data;
      if (type === "all_steps" && payload.all_steps) {
        outputDiv.textContent = JSON.stringify(payload.all_steps, null, 2);
      } else {
        outputDiv.textContent = JSON.stringify(payload, null, 2);
      }
    })
    .catch(function (err) {
      outputDiv.textContent = lbl("lbl_status_error_prefix", "Error: ") + escapeHtml(err.message);
    });
}

function exportAllData() {
  var outputDiv = document.getElementById("bridge-export-output");
  if (outputDiv) {
    outputDiv.textContent = lbl("lbl_status_loading", "Loading...");
  }

  var suggestedName = "dpmtf-webui_" +
    new Date().toISOString().replace(/[-:T]/g, "").slice(0, 15) + ".db.bak";

  var useFilePicker = typeof window.showSaveFilePicker === "function";

  fetch("/api/bridge-v2/db-backup", { method: "POST" })
    .then(function (res) {
      if (!res.ok) {
        return res.text().then(function (txt) {
          throw new Error(txt || ("HTTP " + res.status));
        });
      }
      var cd = res.headers.get("Content-Disposition") || "";
      var match = cd.match(/filename="?([^";]+)"?/);
      var filename = (match && match[1]) ? match[1] : suggestedName;
      return res.blob().then(function (blob) { return { blob: blob, filename: filename }; });
    })
    .then(function (data) {
      if (useFilePicker) {
        return window.showSaveFilePicker({
          suggestedName: data.filename,
          types: [{
            description: "SQLite database backup",
            accept: { "application/octet-stream": [".db.bak", ".db", ".bak"] }
          }]
        })
          .then(function (fileHandle) {
            return fileHandle.createWritable().then(function (writable) {
              return writable.write(data.blob).then(function () { return writable.close(); });
            });
          })
          .then(function () {
            if (outputDiv) {
              outputDiv.textContent = lbl("lbl_bridge_export_all_data", "Export all data")
                + ": " + data.filename;
            }
          });
      }
      var url = URL.createObjectURL(data.blob);
      var a = document.createElement("a");
      a.href = url;
      a.download = data.filename;
      a.rel = "noopener";
      a.style.display = "none";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
      if (outputDiv) {
        outputDiv.textContent = lbl("lbl_bridge_export_all_data", "Export all data")
          + ": " + data.filename;
      }
    })
    .catch(function (err) {
      if (outputDiv) {
        outputDiv.textContent = lbl("lbl_status_error_prefix", "Error: ") + escapeHtml(err.message);
      } else {
        alert(lbl("lbl_status_error_prefix", "Error: ") + escapeHtml(err.message));
      }
    });
}

/* ── Steps CRUD (Fase 4) ─────────────────────────────── */
var _bridgeStepsFlowKey = null;
var _bridgeStepsMetadata = null;
var _bridgeEditingStepId = null;
var _lastAssignedHandoff = null;  // result of /api/prompt-compiler/assign-handoff-id
var _assignBtnInRow = null;  // current Assign Handoff ID button in compile-buttons-row
var _copyBtnInRow = null;    // current Copy Prompt button in compile-buttons-row
var _copyCmdBtnInRow = null; // current Copy Command button in dispatch-buttons-row
var _deliverBtnInRow = null; // current Deliver to Bridge button in dispatch-buttons-row

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
    ["Auto-chain", step.auto_chain_to_next ? "Yes" : "No"],
    ["Require validation", step.validation_required ? "Yes" : "No"],
    ["Model Source", step.model_source],
    ["Model Alias", step.model_alias],
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
      if (flows.length > 0 && !select.value) {
        select.value = flows[0].flow_key;
        _fetchBridgeSteps(flows[0].flow_key);
      }
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

  var isNewStep = !_bridgeEditingStepId;

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

    var acn = document.getElementById("bridge-input-auto_chain_to_next");
    if (acn) body.auto_chain_to_next = acn.checked ? 1 : 0;
    var vreq = document.getElementById("bridge-input-validation_required");
    if (vreq) body.validation_required = vreq.checked ? 1 : 0;

    // V3A: Model Allocator step-level source / alias
    var msEl = document.getElementById("bridge-step-model-source");
    var maEl = document.getElementById("bridge-step-model-alias");
    if (msEl) body.model_source = msEl.value || null;
    if (maEl && !maEl.disabled) body.model_alias = maEl.value.trim() || null;

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

  // V3A: Model Allocator step-level source / alias
  var stepAllocatorControl = createModelSourceControl(
    "bridge-step",
    data.model_source,
    data.model_alias,
    function () { return "opencode"; },
    {
      source: "lbl_bridge_step_model_source",
      alias: "lbl_bridge_step_model_alias",
      validate: "lbl_bridge_validate_allocator"
    },
    [
      ["inherit_from_role", lbl("lbl_bridge_step_model_source_inherit", "Inherit from role")],
      ["model_allocator", "model_allocator"]
    ]
  );
  form.appendChild(stepAllocatorControl.container);

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
  rkSelect.onchange = function () { _autoFillFromConvention(this.value, form, meta.available_conventions, isNewStep); };
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

  // Auto-chain checkbox
  var acnDiv = el("div", null);
  var acnLabel = el("label", null);
  var acnInput = el("input", null);
  acnInput.type = "checkbox";
  acnInput.id = "bridge-input-auto_chain_to_next";
  if (data.auto_chain_to_next) acnInput.checked = true;
  acnLabel.appendChild(acnInput);
  acnLabel.appendChild(document.createTextNode(" " + lbl("lbl_bridge_step_auto_chain", "Auto-chain to next")));
  acnDiv.appendChild(acnLabel);
  form.appendChild(acnDiv);

  // Validation required checkbox
  var vreqDiv = el("div", null);
  var vreqLabel = el("label", null);
  var vreqInput = el("input", null);
  vreqInput.type = "checkbox";
  vreqInput.id = "bridge-input-validation_required";
  if (data.validation_required) vreqInput.checked = true;
  vreqLabel.appendChild(vreqInput);
  vreqLabel.appendChild(document.createTextNode(" " + lbl("lbl_bridge_step_validation_required", "Require validation")));
  vreqDiv.appendChild(vreqLabel);
  form.appendChild(vreqDiv);

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

function _autoFillFromConvention(ruleKey, form, conventions, isNewStep) {
  if (!ruleKey || !conventions) return;
  if (!isNewStep) return;
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
  if (!confirm(lbl("lbl_confirm_delete_step", "Delete step #{stepId}?").replace("{stepId}", stepId))) return;
  fetch("/api/bridge-v2/steps/" + encodeURIComponent(flowKey) + "/" + stepId, { method: "DELETE" })
    .then(function (res) {
      if (!res.ok) throw new Error("HTTP " + res.status);
      return res.json();
    })
    .then(function () {
      alert(lbl("lbl_bridge_deleted", "Successfully deleted") + ": #" + stepId);
      _fetchBridgeSteps(flowKey);
    })
    .catch(function (err) {
      alert(lbl("lbl_status_error_prefix", "Error: ") + escapeHtml(err.message));
    });
}

function loadConventionsAdmin() {
  var container = document.getElementById("bridge-conventions-container");
  if (!container) return;
  clear(container);

  fetch("/api/bridge-v2/conventions")
    .then(function (res) { return res.json(); })
    .then(function (data) {
      var conves = data.conventions || [];
      if (!conves.length) {
        container.appendChild(el("p", "dpmtf-muted", lbl("lbl_bridge_no_flows", "No conventions configured")));
        return;
      }
      renderConventionList(conves, container);
    })
    .catch(function (err) {
      var errP = el("p", "dpmtf-error");
      errP.textContent = lbl("lbl_status_error_prefix", "Error: ") + escapeHtml(err.message);
      container.appendChild(errP);
    });
}

function renderConventionList(conves, container) {
  conves.forEach(function (conv) {
    var card = el("div", "dpmtf-card");

    var header = el("div", null);
    header.style.display = "flex";
    header.style.justifyContent = "space-between";
    header.style.alignItems = "center";
    var h4 = el("h4", null, escapeHtml(conv.rule_key));
    header.appendChild(h4);
    var badgeText = conv.step_type || conv.type || "";
    if (badgeText) {
      var typeBadge = el("span", "dpmtf-badge dpmtf-badge-info");
      typeBadge.textContent = escapeHtml(badgeText);
      header.appendChild(typeBadge);
    }
    card.appendChild(header);

    if (conv.description) {
      card.appendChild(el("p", "dpmtf-small", escapeHtml(conv.description)));
    }

    var ctLabel = el("label", "dpmtf-label");
    ctLabel.textContent = lbl("lbl_bridge_content_template", "Content Template");
    card.appendChild(ctLabel);
    var ctTa = el("textarea", null);
    ctTa.id = "conv-ct-" + escapeHtml(conv.rule_key);
    ctTa.rows = "4";
    ctTa.style.width = "100%";
    ctTa.style.background = "#0d1117";
    ctTa.style.color = "#c9d1d9";
    ctTa.style.padding = "6px";
    ctTa.textContent = conv.content_template || "";
    card.appendChild(ctTa);

    var vsLabel = el("label", "dpmtf-label");
    vsLabel.textContent = lbl("lbl_bridge_validation_schema", "Validation Schema (JSON array)");
    card.appendChild(vsLabel);
    var vsTa = el("textarea", null);
    vsTa.id = "conv-vs-" + escapeHtml(conv.rule_key);
    vsTa.rows = "2";
    vsTa.style.width = "100%";
    vsTa.style.background = "#0d1117";
    vsTa.style.color = "#c9d1d9";
    vsTa.style.padding = "6px";
    vsTa.textContent = conv.validation_schema || "";
    card.appendChild(vsTa);

    var saveBtn = el("button", "dpmtf-btn dpmtf-btn-primary");
    saveBtn.textContent = lbl("lbl_bridge_save", "Save");
    saveBtn.style.marginTop = "4px";
    (function (rk, ta1, ta2) {
      saveBtn.onclick = function () {
        fetch("/api/bridge-v2/conventions/" + encodeURIComponent(rk), {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            content_template: ta1.textContent || null,
            validation_schema: ta2.textContent || null
          })
        })
          .then(function (res) { return res.json(); })
          .then(function () {
            alert(lbl("lbl_bridge_updated", "Successfully updated") + ": " + rk);
          })
          .catch(function (err) {
            alert(lbl("lbl_status_error_prefix", "Error: ") + escapeHtml(err.message));
          });
      };
    })(conv.rule_key, ctTa, vsTa);
    card.appendChild(saveBtn);

    container.appendChild(card);
  });
}

function loadBridgeSetup() {
  loadBridgeStatus();
  loadBridgeRoles();
  loadBridgeFlows();
  _loadBridgeStepsFlow();
  buildBridgeExport();
  loadConventionsAdmin();

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

/* ── User Preferences (database-driven compiler defaults) ── */
function loadUserPreferences() {
  fetch("/api/user-preferences")
    .then(function (r) { return r.json(); })
    .then(function (data) {
      var prefs = data.preferences || {};
      // Restore target_project
      if (prefs.target_project) {
        var projInput = document.getElementById("compile-target_project");
        if (projInput) projInput.value = prefs.target_project;
      }
    })
    .catch(function () { /* silent — defaults stay */ });

  // Save target_project on change (debounced via blur)
  var projInput = document.getElementById("compile-target_project");
  if (projInput) {
    projInput.addEventListener("blur", function () {
      var val = this.value.trim();
      if (!val) return;
      fetch("/api/user-preferences", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pref_key: "target_project", pref_value: val }),
      }).catch(function () { /* silent */ });
    });
  }
}

/* ── 10. Init ──────────────────────────────────────── */
function onReady() {
  loadLabels().then(function () {
    if (window.initAllocator) window.initAllocator();
    if (window.initJobQueue) window.initJobQueue();
  });
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
  loadUserPreferences();
  initDrawer();
  loadBridgeSetup();
  if (typeof loadSystemSetup === "function") loadSystemSetup();
}

/* ── 12. System Setup Panel (Machine Profile) ────────── */

var _systemSetupSections = [
  "profile", "paths", "binaries", "ports",
  "secrets", "tmux", "ollama", "providers"
];

function loadSystemSetup() {
  var container = document.getElementById("system-setup-content");
  if (!container) return;
  clear(container);

  var loadingP = el("p", "dpmtf-muted");
  loadingP.textContent = "Indlæser...";
  container.appendChild(loadingP);

  fetch("/api/system/machine-profile")
    .then(function (res) {
      if (!res.ok) throw new Error("HTTP " + res.status);
      return res.json();
    })
    .then(function (meta) {
      clear(container);
      renderSystemSetupHeader(container, meta);
      renderSystemSetupButtons(container);
      renderSystemSetupCheckContainer(container);
    })
    .catch(function (err) {
      clear(container);
      var errP = el("p", "dpmtf-error");
      errP.textContent = "Fejl: " + (err.message || "Kunne ikke hente Machine Profile");
      container.appendChild(errP);
    });
}

function renderSystemSetupHeader(container, meta) {
  var headerDiv = el("div", "dpmtf-system-setup-header");

  if (!meta.exists) {
    var noProfile = el("p", "dpmtf-warning");
    noProfile.textContent = lbl("system_setup_no_profile",
      "Ingen maskinprofil konfigureret. " +
      "Opret profiles/machine.local.json eller sæt DPMTF_MACHINE_PROFILE i .env. " +
      "Eksisterende DPMtF-funktionalitet er uændret.");
    headerDiv.appendChild(noProfile);
    container.appendChild(headerDiv);
    return;
  }

  if (meta.parse_error) {
    var parseErr = el("p", "dpmtf-error");
    parseErr.textContent = lbl("system_setup_parse_error", "JSON-fejl i profil") +
      ": " + (meta.parse_error || "");
    headerDiv.appendChild(parseErr);
  }

  var infoLines = [
    lbl("system_setup_machine", "Maskine") + ": " + (meta.name || "ukendt"),
    lbl("system_setup_profile", "Profil") + ": " + (meta.active_profile || ""),
    lbl("system_setup_schema", "Schema") + ": v" + (meta.schema_version || "?"),
  ];

  infoLines.forEach(function (line) {
    var p = el("p", "dpmtf-small");
    p.textContent = line;
    headerDiv.appendChild(p);
  });

  container.appendChild(headerDiv);
}

function renderSystemSetupButtons(container) {
  var btnDiv = el("div", "dpmtf-btn-group");

  var allBtn = el("button", "dpmtf-btn dpmtf-btn-primary");
  allBtn.textContent = lbl("system_setup_run_all_checks", "Kør alle checks");
  allBtn.onclick = function () { runSystemCheck(null); };
  btnDiv.appendChild(allBtn);

  _systemSetupSections.forEach(function (sec) {
    var btn = el("button", "dpmtf-btn dpmtf-btn-secondary");
    btn.textContent = lbl("system_setup_run_" + sec, "Kør " + sec);
    btn.onclick = function () { runSystemCheck(sec); };
    btnDiv.appendChild(btn);
  });

  container.appendChild(btnDiv);
}

function renderSystemSetupCheckContainer(container) {
  var checkDiv = el("div", "dpmtf-system-setup-checks");
  checkDiv.id = "system-setup-checks";

  var summaryP = el("p", "dpmtf-small dpmtf-muted");
  summaryP.id = "system-setup-summary";
  summaryP.textContent = lbl("system_setup_ready", "Klar. Klik på en check-knap for at køre.");
  checkDiv.appendChild(summaryP);

  var listDiv = el("div", "dpmtf-check-list");
  listDiv.id = "system-setup-check-list";
  checkDiv.appendChild(listDiv);

  container.appendChild(checkDiv);
}

function runSystemCheck(section) {
  var listDiv = document.getElementById("system-setup-check-list");
  var summaryP = document.getElementById("system-setup-summary");
  if (!listDiv || !summaryP) return;

  clear(listDiv);
  summaryP.textContent = lbl("system_setup_running", "Kører checks...");

  var url = "/api/system/healthcheck";
  if (section) {
    url += "/" + encodeURIComponent(section);
  }

  fetch(url)
    .then(function (res) {
      if (!res.ok) {
        return res.json().then(function (err) {
          throw new Error(err.detail || "Healthcheck failed");
        });
      }
      return res.json();
    })
    .then(function (data) {
      renderSystemCheckResults(listDiv, summaryP, data);
    })
    .catch(function (err) {
      summaryP.textContent = lbl("lbl_status_error_prefix", "Fejl: ") + (err.message || "");
    });
}

function renderSystemCheckResults(listDiv, summaryP, data) {
  var summary = data.summary || {};
  summaryP.textContent =
    lbl("system_setup_status", "Status") + ": " +
    (summary.passed || 0) + " bestået / " +
    (summary.warnings || 0) + " advarsler / " +
    (summary.failed || 0) + " fejlet";

  var checks = data.checks || [];
  if (!checks.length) {
    var emptyP = el("p", "dpmtf-muted");
    emptyP.textContent = lbl("system_setup_no_checks", "Ingen checks returneret");
    listDiv.appendChild(emptyP);
    return;
  }

  checks.forEach(function (check) {
    var row = el("div", "dpmtf-check-row");

    var icon = el("span", "dpmtf-check-icon");
    if (check.status === "pass") {
      icon.textContent = "✅";
      icon.className += " dpmtf-check-pass";
    } else if (check.status === "warning") {
      icon.textContent = "⚠️";
      icon.className += " dpmtf-check-warning";
    } else if (check.status === "fail") {
      icon.textContent = "❌";
      icon.className += " dpmtf-check-fail";
    } else {
      icon.textContent = "⏭️";
      icon.className += " dpmtf-check-skip";
    }
    row.appendChild(icon);

    var nameSpan = el("span", "dpmtf-check-name");
    nameSpan.textContent = check.name;
    row.appendChild(nameSpan);

    var msgSpan = el("span", "dpmtf-check-message");
    msgSpan.textContent = check.message;
    row.appendChild(msgSpan);

    listDiv.appendChild(row);
  });
}


if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", onReady);
} else {
  onReady();
}
