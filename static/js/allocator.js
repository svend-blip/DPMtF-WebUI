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

/* renderAllocatorDetail is completed in Task 6 (alias) and Task 7 (role). */
function renderAllocatorDetail() {
  const detail = document.getElementById("allocator-detail");
  if (!detail) return;
  clear(detail);
  detail.appendChild(el("div", "dpmtf-muted", lbl("lbl_alloc_select_hint", "Select an alias or role to edit")));
}

function initAllocator() {
  if (!document.getElementById("allocator-dashboard")) return;
  reloadAllocatorConfig();
}
window.initAllocator = initAllocator;
