/* Model Allocator config dashboard (V4). Depends on el/clear/lbl from dpmtf-app.js. */
"use strict";

window.allocatorState = { config: { aliases: {}, roles: {}, profiles: {} }, selected: { type: null, name: null } };

function reloadAllocatorConfig() {
  return fetch("/api/bridge-v2/allocator/config")
    .then(function (res) { if (!res.ok) throw new Error("HTTP " + res.status); return res.json(); })
    .then(function (cfg) {
      window.allocatorState.config = {
        aliases: cfg.aliases || {},
        roles: cfg.roles || {},
        profiles: cfg.profiles || {}
      };
      renderAllocatorDashboard();
    })
    .catch(function (err) {
      const mount = document.getElementById("allocator-dashboard");
      if (mount) { clear(mount); mount.appendChild(el("div", "dpmtf-text-danger", lbl("lbl_alloc_load_error", "Failed to load allocator config") + ": " + err.message)); }
    });
}

function _allocatorListColumn(titleKey, titleFallback, newKey, newFallback, listId, onNew) {
  const col = el("div", "allocator-col");
  col.appendChild(el("h4", null, lbl(titleKey, titleFallback)));
  const list = el("div", null);
  list.id = listId;
  col.appendChild(list);
  const newBtn = el("button", "dpmtf-btn", lbl(newKey, newFallback));
  newBtn.style.marginTop = "8px";
  newBtn.onclick = onNew;
  col.appendChild(newBtn);
  return col;
}

function _renderList(listId, names, type) {
  const list = document.getElementById(listId);
  if (!list) return;
  clear(list);
  const sel = window.allocatorState.selected;
  names.sort().forEach(function (name) {
    const item = el("div", "allocator-list-item", name);
    if (sel.type === type && sel.name === name) item.className += " selected";
    item.onclick = function () { selectAllocatorItem(type, name); };
    list.appendChild(item);
  });
}

function _renderProfiles() {
  const box = document.getElementById("allocator-profiles");
  if (!box) return;
  clear(box);
  box.appendChild(el("div", "dpmtf-muted", lbl("lbl_alloc_profiles", "Runtime profiles (read-only)")));
  const profiles = window.allocatorState.config.profiles;
  Object.keys(profiles).sort().forEach(function (pname) {
    const backend = (profiles[pname] && profiles[pname].backend) || "?";
    box.appendChild(el("div", null, pname + " — " + backend));
  });
}

function renderAllocatorDashboard() {
  const mount = document.getElementById("allocator-dashboard");
  if (!mount) return;
  clear(mount);

  const grid = el("div", "allocator-grid");
  grid.appendChild(_allocatorListColumn("lbl_alloc_aliases", "Aliases", "lbl_alloc_new_alias", "+ New alias",
    "allocator-aliases-list", function () { selectAllocatorItem("alias", null); }));
  grid.appendChild(_allocatorListColumn("lbl_alloc_roles", "Roles", "lbl_alloc_new_role", "+ New role",
    "allocator-roles-list", function () { selectAllocatorItem("role", null); }));

  const detailCol = el("div", "allocator-col");
  detailCol.appendChild(el("h4", null, lbl("lbl_alloc_detail", "Detail")));
  const detail = el("div", null);
  detail.id = "allocator-detail";
  detailCol.appendChild(detail);
  grid.appendChild(detailCol);

  mount.appendChild(grid);

  const profiles = el("div", "allocator-profiles");
  profiles.id = "allocator-profiles";
  mount.appendChild(profiles);

  _renderList("allocator-aliases-list", Object.keys(window.allocatorState.config.aliases), "alias");
  _renderList("allocator-roles-list", Object.keys(window.allocatorState.config.roles), "role");
  _renderProfiles();
  renderAllocatorDetail();
}

function selectAllocatorItem(type, name) {
  window.allocatorState.selected = { type: type, name: name };
  _renderList("allocator-aliases-list", Object.keys(window.allocatorState.config.aliases), "alias");
  _renderList("allocator-roles-list", Object.keys(window.allocatorState.config.roles), "role");
  renderAllocatorDetail();
}

function _field(parent, labelKey, labelFallback, inputEl) {
  const row = el("div", null);
  row.style.marginTop = "8px";
  const lab = el("label", "dpmtf-small dpmtf-muted", lbl(labelKey, labelFallback));
  lab.style.display = "block";
  row.appendChild(lab);
  row.appendChild(inputEl);
  parent.appendChild(row);
  return inputEl;
}

function _textInput(value) {
  const i = el("input");
  i.type = "text";
  i.className = "dpmtf-input";
  if (value !== undefined && value !== null) i.value = String(value);
  return i;
}

function _profileSelect(value) {
  const s = el("select");
  s.className = "dpmtf-input";
  Object.keys(window.allocatorState.config.profiles).sort().forEach(function (p) {
    const o = el("option", null, p);
    o.value = p;
    if (p === value) o.selected = true;
    s.appendChild(o);
  });
  return s;
}

function _checkbox(checked) {
  const c = el("input");
  c.type = "checkbox";
  c.checked = !!checked;
  return c;
}

function renderAliasForm(name) {
  const detail = document.getElementById("allocator-detail");
  clear(detail);
  const existing = name ? (window.allocatorState.config.aliases[name] || {}) : {};

  const nameInput = _textInput(name || "");
  nameInput.disabled = !!name; // renaming = delete+create; keep key stable while editing
  _field(detail, "lbl_alloc_field_name", "Name", nameInput);

  const profileSel = _profileSelect(existing.runtime_profile);
  _field(detail, "lbl_alloc_field_profile", "Runtime profile", profileSel);

  const modelInput = _textInput(existing.real_model || "");
  _field(detail, "lbl_alloc_field_model", "Real model", modelInput);

  const modelPathInput = _textInput(existing.model_path || "");
  _field(detail, "lbl_alloc_field_model_path", "Model path", modelPathInput);

  const contextInput = _textInput(existing.context !== undefined ? existing.context : "");
  _field(detail, "lbl_alloc_field_context", "Context", contextInput);

  const lifecycleInput = _textInput(existing.lifecycle_policy || "");
  _field(detail, "lbl_alloc_field_lifecycle", "Lifecycle policy", lifecycleInput);

  const clientsWrap = el("div", null);
  const clients = existing.clients || {};
  const ocCb = _checkbox(clients.opencode);
  const ccCb = _checkbox(clients["claude-code"]);
  clientsWrap.appendChild(ocCb); clientsWrap.appendChild(el("span", null, " opencode  "));
  clientsWrap.appendChild(ccCb); clientsWrap.appendChild(el("span", null, " claude-code"));
  _field(detail, "lbl_alloc_field_clients", "Clients", clientsWrap);

  const msg = el("div", "dpmtf-small");
  msg.style.marginTop = "8px";

  const saveBtn = el("button", "dpmtf-btn", lbl("lbl_alloc_save", "Save"));
  saveBtn.onclick = function () {
    const key = (name || nameInput.value).trim();
    if (!key) { msg.className = "dpmtf-small dpmtf-text-danger"; msg.textContent = lbl("lbl_alloc_name_required", "Name required"); return; }
    const definition = {};
    if (profileSel.value) definition.runtime_profile = profileSel.value;
    if (modelInput.value.trim()) definition.real_model = modelInput.value.trim();
    if (modelPathInput.value.trim()) definition.model_path = modelPathInput.value.trim();
    if (contextInput.value.trim()) {
      const n = parseInt(contextInput.value.trim(), 10);
      definition.context = isNaN(n) ? contextInput.value.trim() : n;
    }
    if (lifecycleInput.value.trim()) definition.lifecycle_policy = lifecycleInput.value.trim();
    definition.clients = { opencode: ocCb.checked, "claude-code": ccCb.checked };
    saveBtn.disabled = true;
    fetch("/api/bridge-v2/allocator/config/alias", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: key, definition: definition })
    })
      .then(function (res) { return res.json().then(function (b) { return { ok: res.ok, body: b }; }); })
      .then(function (r) {
        saveBtn.disabled = false;
        if (!r.ok) { msg.className = "dpmtf-small dpmtf-text-danger"; msg.textContent = r.body.detail || lbl("lbl_alloc_error", "Error"); return; }
        reloadAllocatorConfig().then(function () { selectAllocatorItem("alias", key); });
      })
      .catch(function (e) { saveBtn.disabled = false; msg.className = "dpmtf-small dpmtf-text-danger"; msg.textContent = e.message; });
  };
  detail.appendChild(saveBtn);

  if (name) {
    const delBtn = el("button", "dpmtf-btn", lbl("lbl_alloc_delete", "Delete"));
    delBtn.style.marginLeft = "8px";
    delBtn.onclick = function () {
      if (!confirm(lbl("lbl_alloc_confirm_delete", "Delete '{name}'?").replace("{name}", name))) return;
      fetch("/api/bridge-v2/allocator/config/alias/" + encodeURIComponent(name), { method: "DELETE" })
        .then(function (res) { return res.json().then(function (b) { return { ok: res.ok, body: b }; }); })
        .then(function (r) {
          if (!r.ok) { msg.className = "dpmtf-small dpmtf-text-danger"; msg.textContent = r.body.detail || lbl("lbl_alloc_error", "Error"); return; }
          selectAllocatorItem(null, null);
          reloadAllocatorConfig();
        });
    };
    detail.appendChild(delBtn);
  }
  detail.appendChild(msg);

  if (name) {
    const statusBox = el("div", "dpmtf-card");
    statusBox.style.marginTop = "12px";
    detail.appendChild(statusBox);
    const client = (existing.clients && existing.clients.opencode) ? "opencode" : "claude-code";
    renderAllocatorStatus(statusBox, name, client);
  }
}

function renderAllocatorStatus(container, alias, client) {
  clear(container);
  container.appendChild(el("h5", null, lbl("lbl_bridge_runtime_status", "Runtime Status")));
  const info = el("div", "dpmtf-small");
  container.appendChild(info);

  function setInfo(text, cls) { clear(info); info.appendChild(el("span", cls || null, text)); }

  const btns = el("div", null);
  btns.style.marginTop = "8px";
  const valBtn = el("button", "dpmtf-btn", lbl("lbl_bridge_validate_allocator", "Validate"));
  const startBtn = el("button", "dpmtf-btn", lbl("lbl_bridge_start", "Start"));
  const stopBtn = el("button", "dpmtf-btn", lbl("lbl_bridge_stop", "Stop"));
  startBtn.style.marginLeft = "6px"; stopBtn.style.marginLeft = "6px";
  btns.appendChild(valBtn); btns.appendChild(startBtn); btns.appendChild(stopBtn);
  container.appendChild(btns);

  function post(path) {
    return fetch(path, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ alias: alias, client: client })
    }).then(function (res) { if (!res.ok) throw new Error("HTTP " + res.status); return res.json(); });
  }

  valBtn.onclick = function () {
    setInfo("…");
    post("/api/bridge-v2/allocator/validate")
      .then(function (r) { setInfo(lbl("lbl_bridge_validation_status", "Validation") + ": " + (r.validation_status || "?"),
        r.validation_status === "OK" ? "dpmtf-text-success" : "dpmtf-text-warning"); })
      .catch(function (e) { setInfo(e.message, "dpmtf-text-danger"); });
  };
  startBtn.onclick = function () { setInfo("…"); post("/api/bridge-v2/allocator/start").then(function () { refresh(); }).catch(function (e) { setInfo(e.message, "dpmtf-text-danger"); }); };
  stopBtn.onclick = function () {
    if (!confirm(lbl("lbl_bridge_confirm_stop", "Stop the allocator runtime for '{alias}'?").replace("{alias}", alias))) return;
    setInfo("…"); post("/api/bridge-v2/allocator/stop").then(function () { refresh(); }).catch(function (e) { setInfo(e.message, "dpmtf-text-danger"); });
  };

  function refresh() {
    post("/api/bridge-v2/allocator/status")
      .then(function (d) {
        const running = d && d.running;
        setInfo((running ? lbl("lbl_bridge_running", "Running") : lbl("lbl_bridge_not_running", "Not running")) +
          (d && d.pid ? "  pid " + d.pid : "") + (d && d.port ? "  :" + d.port : ""),
          running ? "dpmtf-text-success" : "dpmtf-text-muted");
      })
      .catch(function (e) { setInfo(e.message, "dpmtf-text-danger"); });
  }
  refresh();
}

function _aliasSelect(value, includeBlank) {
  const s = el("select");
  s.className = "dpmtf-input";
  if (includeBlank) { const o = el("option", null, "—"); o.value = ""; s.appendChild(o); }
  Object.keys(window.allocatorState.config.aliases).sort().forEach(function (a) {
    const o = el("option", null, a);
    o.value = a;
    if (a === value) o.selected = true;
    s.appendChild(o);
  });
  return s;
}

function renderRoleForm(name) {
  const detail = document.getElementById("allocator-detail");
  clear(detail);
  const existing = name ? (window.allocatorState.config.roles[name] || {}) : {};
  const ca = existing.client_aliases || {};

  const nameInput = _textInput(name || "");
  nameInput.disabled = !!name;
  _field(detail, "lbl_alloc_field_name", "Name", nameInput);

  const configDirInput = _textInput(existing.config_dir || "");
  _field(detail, "lbl_alloc_field_config_dir", "Config dir", configDirInput);

  const defaultAliasSel = _aliasSelect(existing.default_alias, true);
  _field(detail, "lbl_alloc_field_default_alias", "Default alias", defaultAliasSel);

  const ocSel = _aliasSelect(ca.opencode, true);
  _field(detail, "lbl_alloc_field_client_aliases", "Client aliases (opencode)", ocSel);
  const ccSel = _aliasSelect(ca["claude-code"], true);
  _field(detail, "lbl_alloc_field_client_aliases", "Client aliases (claude-code)", ccSel);

  const msg = el("div", "dpmtf-small");
  msg.style.marginTop = "8px";

  const saveBtn = el("button", "dpmtf-btn", lbl("lbl_alloc_save", "Save"));
  saveBtn.onclick = function () {
    const key = (name || nameInput.value).trim();
    if (!key) { msg.className = "dpmtf-small dpmtf-text-danger"; msg.textContent = lbl("lbl_alloc_name_required", "Name required"); return; }
    const definition = {};
    if (defaultAliasSel.value) definition.default_alias = defaultAliasSel.value;
    if (configDirInput.value.trim()) definition.config_dir = configDirInput.value.trim();
    const clientAliases = {};
    if (ocSel.value) clientAliases.opencode = ocSel.value;
    if (ccSel.value) clientAliases["claude-code"] = ccSel.value;
    if (Object.keys(clientAliases).length) definition.client_aliases = clientAliases;
    saveBtn.disabled = true;
    fetch("/api/bridge-v2/allocator/config/role", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: key, definition: definition })
    })
      .then(function (res) { return res.json().then(function (b) { return { ok: res.ok, body: b }; }); })
      .then(function (r) {
        saveBtn.disabled = false;
        if (!r.ok) { msg.className = "dpmtf-small dpmtf-text-danger"; msg.textContent = r.body.detail || lbl("lbl_alloc_error", "Error"); return; }
        reloadAllocatorConfig().then(function () { selectAllocatorItem("role", key); });
      })
      .catch(function (e) { saveBtn.disabled = false; msg.className = "dpmtf-small dpmtf-text-danger"; msg.textContent = e.message; });
  };
  detail.appendChild(saveBtn);

  if (name) {
    const delBtn = el("button", "dpmtf-btn", lbl("lbl_alloc_delete", "Delete"));
    delBtn.style.marginLeft = "8px";
    delBtn.onclick = function () {
      if (!confirm(lbl("lbl_alloc_confirm_delete", "Delete '{name}'?").replace("{name}", name))) return;
      fetch("/api/bridge-v2/allocator/config/role/" + encodeURIComponent(name), { method: "DELETE" })
        .then(function (res) { return res.json().then(function (b) { return { ok: res.ok, body: b }; }); })
        .then(function (r) {
          if (!r.ok) { msg.className = "dpmtf-small dpmtf-text-danger"; msg.textContent = r.body.detail || lbl("lbl_alloc_error", "Error"); return; }
          selectAllocatorItem(null, null);
          reloadAllocatorConfig();
        });
    };
    detail.appendChild(delBtn);
  }
  detail.appendChild(msg);
}

function renderAllocatorDetail() {
  const detail = document.getElementById("allocator-detail");
  if (!detail) return;
  const sel = window.allocatorState.selected;
  if (sel.type === "alias") { renderAliasForm(sel.name); return; }
  if (sel.type === "role") { renderRoleForm(sel.name); return; }
  clear(detail);
  detail.appendChild(el("div", "dpmtf-muted", lbl("lbl_alloc_select_hint", "Select an alias or role to edit")));
}

function initAllocator() {
  if (!document.getElementById("allocator-dashboard")) return;
  reloadAllocatorConfig();
}
window.initAllocator = initAllocator;
