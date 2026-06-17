/* ── {PROJECT_NAME} — Core Frontend Infrastructure ────
 *
 * Provides the database-driven panel system that every
 * DPMtF-governed WebUI needs:
 *   - lbl() i18n helper (4-layer architecture)
 *   - el() safe DOM creation (no innerHTML)
 *   - Panel structure: visibility, expand/collapse, subgroups
 *   - Language switcher
 *
 * Domain-specific panel loading functions are added by
 * the implementer for each project.
 */

/* ── 1. Utilities ──────────────────────────────────── */

function el(tag, className, text) {
  const e = document.createElement(tag);
  if (className) e.className = className;
  if (text !== undefined) e.textContent = text;
  return e;
}

function escapeHtml(str) {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

/* ── 2. i18n ────────────────────────────────────────── */

let currentLocale = "en-US";
let labelMap = {};

function lbl(key, fallback) {
  if (labelMap[key]) return labelMap[key];
  return fallback || key;
}

function loadLabels(locale) {
  return fetch("/api/ui-labels/main?locale=" + encodeURIComponent(locale))
    .then(function (res) {
      if (!res.ok) throw new Error("HTTP " + res.status);
      return res.json();
    })
    .then(function (data) {
      labelMap = data.labels || {};
      // Update all data-slot elements
      document.querySelectorAll("[data-slot]").forEach(function (el) {
        const key = el.getAttribute("data-slot");
        if (labelMap[key]) el.textContent = labelMap[key];
      });
    });
}

function switchLanguage(locale) {
  currentLocale = locale;
  document.querySelector("meta[name='locale']").setAttribute("content", locale);
  loadLabels(locale)
    .then(function () {
      // Re-render panel structure with new locale
      loadPanelStructure();
    })
    .catch(function (err) {
      console.warn("Failed to switch language:", err.message);
    });
}

function loadLanguageDropdown() {
  fetch("/api/available-languages")
    .then(function (res) { return res.json(); })
    .then(function (data) {
      const select = document.getElementById("lang-dropdown");
      if (!select) return;
      select.replaceChildren();
      (data.languages || []).forEach(function (lang) {
        const opt = document.createElement("option");
        opt.value = lang.locale;
        opt.textContent = lang.label;
        if (lang.locale === currentLocale) opt.selected = true;
        select.appendChild(opt);
      });
      select.addEventListener("change", function () {
        switchLanguage(this.value);
      });
    })
    .catch(function (err) {
      console.warn("Failed to load languages:", err.message);
    });
}

/* ── 3. Panel Structure ────────────────────────────── */

let panelStructure = {};

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
      // Fallback: render with defaults if API unavailable
      buildPanelStructure();
    });
}

function buildPanelStructure() {
  const groupNames = ["daily", "journals", "reports", "periodic", "setup"];
  for (let i = 0; i < groupNames.length; i++) {
    const gn = groupNames[i];
    const pg = document.getElementById("pg-" + gn);
    if (!pg) continue;
    const info = panelStructure[gn] || { is_visible: true, state: "expanded", subgroups: [] };

    // Hide invisible groups
    if (!info.is_visible) {
      pg.classList.add("dpmtf-hidden");
      continue;
    }
    pg.classList.remove("dpmtf-hidden");

    // Set group collapse state
    const toggle = pg.querySelector(".panel-group-toggle");
    const body = pg.querySelector(".panel-group-body");
    if (info.state === "collapsed") {
      pg.classList.add("collapsed");
      if (body) body.style.display = "none";
      if (toggle) toggle.textContent = "▶";
    } else {
      pg.classList.remove("collapsed");
      if (body) body.style.display = "";
      if (toggle) toggle.textContent = "▼";
    }

    // Build subgroups inside body
    if (body) buildSubgroups(body, gn, info.subgroups);
  }
}

function buildSubgroups(body, groupName, subgroups) {
  // Move panels back to body before removing subgroups (don't delete panels)
  const existing = body.querySelectorAll(".panel-subgroup");
  for (let i = 0; i < existing.length; i++) {
    const sgBody = existing[i].querySelector(".panel-subgroup-body");
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

  for (let s = 0; s < subgroups.length; s++) {
    const sg = subgroups[s];
    if (!sg.is_visible) continue;

    const sgEl = document.createElement("section");
    sgEl.className = "panel-subgroup";
    if (sg.key && sg.key.endsWith("_all")) {
      sgEl.classList.add("panel-subgroup-all");
    }
    sgEl.setAttribute("data-subgroup", sg.key);

    // Header
    const header = document.createElement("div");
    header.className = "panel-subgroup-header";
    const title = document.createElement("h3");
    title.textContent = sg.title || "";
    header.appendChild(title);
    const sgToggle = document.createElement("span");
    sgToggle.className = "panel-subgroup-toggle";
    sgToggle.textContent = sg.state === "collapsed" ? "▶" : "▼";
    header.appendChild(sgToggle);
    sgEl.appendChild(header);

    // Body
    const sgBody = document.createElement("div");
    sgBody.className = "panel-subgroup-body";
    if (sg.state === "collapsed") {
      sgEl.classList.add("collapsed");
      sgBody.style.display = "none";
    }

    // Move panels into subgroup based on slot mapping
    if (sg.slots && sg.slots.length) {
      for (let k = 0; k < sg.slots.length; k++) {
        const slotKey = sg.slots[k];
        const panel = body.querySelector('[data-slot="' + slotKey + '"]');
        if (panel) {
          const section = panel.closest("section") || panel.parentElement;
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
        const isCollapsed = el.classList.contains("collapsed");
        const newState = isCollapsed ? "expanded" : "collapsed";
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
  const headers = document.querySelectorAll(".panel-group-header");
  for (let i = 0; i < headers.length; i++) {
    headers[i].addEventListener("click", function () {
      const groupName = this.getAttribute("data-group");
      const pg = document.getElementById("pg-" + groupName);
      if (!pg) return;
      const isCollapsed = pg.classList.contains("collapsed");
      const newState = isCollapsed ? "expanded" : "collapsed";

      if (panelStructure[groupName]) {
        panelStructure[groupName].state = newState;
      }
      buildPanelStructure();

      // Persist group state
      fetch("/api/panel-structure/group-state", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ group_name: groupName, state: newState }),
      }).catch(function (err) {
        console.warn("Failed to save group state:", err.message);
      });
    });
  }
}

/* ── 4. Init ────────────────────────────────────────── */

function init() {
  loadLabels(currentLocale)
    .then(function () {
      return loadPanelStructure();
    })
    .then(function () {
      initPanelGroupToggles();
      loadLanguageDropdown();
    })
    .catch(function (err) {
      console.warn("Init error:", err.message);
      // Still try to render with defaults
      buildPanelStructure();
      initPanelGroupToggles();
      loadLanguageDropdown();
    });
}

document.addEventListener("DOMContentLoaded", init);
