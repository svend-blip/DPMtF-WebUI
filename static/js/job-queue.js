/* Job Queue dashboard — minimal operations UI.
 * Answers: What is running? What is waiting? What requires human action? What completed?
 * Depends on: el(), clear(), lbl() from dpmtf-app.js.
 */
"use strict";

window.jobQueueState = { jobs: [], filter: null };

function reloadJobQueue() {
  var url = "/api/bridge-v2/jobs";
  if (window.jobQueueState.filter) {
    url += "?status=" + window.jobQueueState.filter;
  }
  return fetch(url)
    .then(function(res) { if (!res.ok) throw new Error("HTTP " + res.status); return res.json(); })
    .then(function(data) {
      window.jobQueueState.jobs = data.jobs || [];
      renderJobQueue();
    })
    .catch(function(err) {
      var mount = document.getElementById("job-queue-dashboard");
      if (mount) { clear(mount); mount.appendChild(el("div", "dpmtf-text-danger", "Job Queue: " + err.message)); }
    });
}

function renderJobQueue() {
  var mount = document.getElementById("job-queue-dashboard");
  if (!mount) return;
  clear(mount);

  var jobs = window.jobQueueState.jobs;
  if (!jobs.length) {
    mount.appendChild(el("div", "dpmtf-muted", "No jobs. Create one via POST /api/bridge-v2/jobs"));
    return;
  }

  // Filter buttons
  var filters = el("div", null);
  filters.style.marginBottom = "12px";
  var allBtn = el("button", "dpmtf-btn", "All");
  allBtn.onclick = function() { window.jobQueueState.filter = null; reloadJobQueue(); };
  filters.appendChild(allBtn);

  var statuses = ["DRAFT", "AWAITING_APPROVAL", "APPROVED", "RUNNING", "BLOCKED", "COMPLETED"];
  for (var i = 0; i < statuses.length; i++) {
    var btn = el("button", "dpmtf-btn", statuses[i]);
    btn.style.marginLeft = "4px";
    var st = statuses[i];
    btn.onclick = function(s) { return function() { window.jobQueueState.filter = s; reloadJobQueue(); }; }(st);
    filters.appendChild(btn);
  }
  mount.appendChild(filters);

  // Job table
  var table = el("table", "dpmtf-table");
  var thead = el("thead", null);
  var headerRow = el("tr", null);
  ["Job ID", "Flow", "Role", "Status", "Goal", "Created"].forEach(function(h) {
    headerRow.appendChild(el("th", null, h));
  });
  thead.appendChild(headerRow);
  table.appendChild(thead);

  var tbody = el("tbody", null);
  jobs.forEach(function(job) {
    var row = el("tr", null);
    row.appendChild(el("td", null, job.job_id.substring(0, 16)));
    row.appendChild(el("td", null, job.flow_key));
    row.appendChild(el("td", null, job.role_key));

    var statusCell = el("td", null, job.status);
    if (job.status === "RUNNING") statusCell.className = "dpmtf-text-success";
    else if (job.status === "BLOCKED" || job.status === "FAILED") statusCell.className = "dpmtf-text-danger";
    else if (job.status === "COMPLETED") statusCell.className = "dpmtf-muted";
    row.appendChild(statusCell);

    row.appendChild(el("td", null, (job.goal || "").substring(0, 50)));
    row.appendChild(el("td", "dpmtf-small", job.created_at || ""));
    tbody.appendChild(row);
  });
  table.appendChild(tbody);
  mount.appendChild(table);

  // Scheduler tick button
  var tickBtn = el("button", "dpmtf-btn", "Run Scheduler Tick");
  tickBtn.style.marginTop = "12px";
  tickBtn.onclick = function() {
    tickBtn.disabled = true;
    fetch("/api/bridge-v2/jobs/scheduler/tick", { method: "POST" })
      .then(function(r) { return r.json(); })
      .then(function(data) {
        tickBtn.disabled = false;
        reloadJobQueue();
      })
      .catch(function(e) { tickBtn.disabled = false; });
  };
  mount.appendChild(tickBtn);
}

function initJobQueue() {
  if (!document.getElementById("job-queue-dashboard")) return;
  reloadJobQueue();
}
window.initJobQueue = initJobQueue;
