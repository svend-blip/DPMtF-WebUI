/* Job Queue dashboard — operations UI.
 * Shows active jobs, allows create/approve/cancel, scheduler tick.
 * Depends on: el(), clear(), lbl() from dpmtf-app.js.
 */
"use strict";

window.jobQueueState = { jobs: [], filter: "active", selectedJob: null, autoRefresh: true };

function reloadJobQueue() {
  var url = "/api/bridge-v2/jobs";
  if (window.jobQueueState.filter && window.jobQueueState.filter !== "all") {
    if (window.jobQueueState.filter === "active") {
      url += "?status=APPROVED";
    } else {
      url += "?status=" + window.jobQueueState.filter;
    }
  }
  return fetch(url)
    .then(function(res) { if (!res.ok) throw new Error("HTTP " + res.status); return res.json(); })
    .then(function(data) {
      // For "active" filter, also fetch RUNNING and QUEUED
      if (window.jobQueueState.filter === "active") {
        return fetch("/api/bridge-v2/jobs?status=RUNNING")
          .then(function(r) { return r.json(); })
          .then(function(running) {
            return fetch("/api/bridge-v2/jobs?status=QUEUED")
              .then(function(r2) { return r2.json(); })
              .then(function(queued) {
                return fetch("/api/bridge-v2/jobs?status=AWAITING_APPROVAL")
                  .then(function(r3) { return r3.json(); })
                  .then(function(awaiting) {
                    return fetch("/api/bridge-v2/jobs?status=DRAFT")
                      .then(function(r4) { return r4.json(); })
                      .then(function(drafts) {
                        return fetch("/api/bridge-v2/jobs?status=BLOCKED")
                          .then(function(r5) { return r5.json(); })
                          .then(function(blocked) {
                            return fetch("/api/bridge-v2/jobs?status=VERIFYING")
                              .then(function(r6) { return r6.json(); })
                              .then(function(verifying) {
                                window.jobQueueState.jobs = [].concat(
                                  (drafts.jobs || []),
                                  (awaiting.jobs || []),
                                  (data.jobs || []),
                                  (queued.jobs || []),
                                  (running.jobs || []),
                                  (verifying.jobs || []),
                                  (blocked.jobs || [])
                                );
                                renderJobQueue();
                              });
                          });
                      });
                  });
              });
          });
      }
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

  // ── Summary bar ──
  var summary = el("div", "dpmtf-job-summary");
  summary.style.cssText = "display:flex;gap:12px;margin-bottom:12px;flex-wrap:wrap;";

  var counts = {};
  jobs.forEach(function(j) { counts[j.status] = (counts[j.status] || 0) + 1; });

  var statuses = ["DRAFT", "AWAITING_APPROVAL", "APPROVED", "QUEUED", "RUNNING", "VERIFYING", "BLOCKED"];
  statuses.forEach(function(st) {
    var count = counts[st] || 0;
    var badge = el("span", null);
    badge.style.cssText = "font-size:0.85em;padding:2px 8px;border-radius:4px;";
    if (count > 0) {
      badge.style.fontWeight = "bold";
      if (st === "RUNNING") badge.style.background = "#d4edda";
      else if (st === "BLOCKED") badge.style.background = "#f8d7da";
      else if (st === "AWAITING_APPROVAL") badge.style.background = "#fff3cd";
      else badge.style.background = "#e9ecef";
    } else {
      badge.style.color = "#999";
    }
    badge.textContent = st + ": " + count;
    summary.appendChild(badge);
  });

  // Auto-refresh toggle
  var autoBtn = el("button", "dpmtf-btn dpmtf-btn-sm");
  autoBtn.textContent = window.jobQueueState.autoRefresh ? "⏸ Auto-refresh ON" : "▶ Auto-refresh OFF";
  autoBtn.style.marginLeft = "auto";
  autoBtn.onclick = function() {
    window.jobQueueState.autoRefresh = !window.jobQueueState.autoRefresh;
    renderJobQueue();
  };
  summary.appendChild(autoBtn);

  mount.appendChild(summary);

  // ── Filter buttons ──
  var filters = el("div", null);
  filters.style.marginBottom = "12px";

  var filterOpts = [
    {key: "active", label: "Active"},
    {key: "all", label: "All"},
    {key: "DRAFT", label: "Draft"},
    {key: "AWAITING_APPROVAL", label: "Awaiting"},
    {key: "RUNNING", label: "Running"},
    {key: "COMPLETED", label: "Completed"},
    {key: "CANCELLED", label: "Cancelled"},
  ];
  filterOpts.forEach(function(opt) {
    var btn = el("button", "dpmtf-btn dpmtf-btn-sm");
    btn.textContent = opt.label;
    btn.style.marginRight = "4px";
    if (window.jobQueueState.filter === opt.key) {
      btn.style.fontWeight = "bold";
      btn.style.background = "var(--dpmtf-accent, #4a90d9)";
      btn.style.color = "#fff";
    }
    btn.onclick = function() { window.jobQueueState.filter = opt.key; reloadJobQueue(); };
    filters.appendChild(btn);
  });

  // Scheduler tick button
  var tickBtn = el("button", "dpmtf-btn dpmtf-btn-sm");
  tickBtn.textContent = "⚡ Run Scheduler Tick";
  tickBtn.style.marginLeft = "12px";
  tickBtn.onclick = function() {
    tickBtn.disabled = true;
    tickBtn.textContent = "⚡ Running...";
    fetch("/api/bridge-v2/jobs/scheduler/tick", { method: "POST" })
      .then(function(r) { return r.json(); })
      .then(function(data) {
        tickBtn.disabled = false;
        tickBtn.textContent = "⚡ Run Scheduler Tick";
        reloadJobQueue();
      })
      .catch(function(e) { tickBtn.disabled = false; tickBtn.textContent = "⚡ Run Scheduler Tick"; });
  };
  filters.appendChild(tickBtn);

  mount.appendChild(filters);

  // ── Create job form (collapsible) ──
  var createToggle = el("button", "dpmtf-btn dpmtf-btn-sm");
  createToggle.textContent = "+ Create Job";
  createToggle.style.marginBottom = "8px";
  mount.appendChild(createToggle);

  var createForm = el("div", null);
  createForm.style.display = "none";
  createForm.style.cssText = "background:var(--dpmtf-bg-alt,#f8f9fa);padding:12px;border-radius:6px;margin-bottom:12px;";

  // Flow selector
  var flowLabel = el("label", null, "Flow: ");
  flowLabel.style.cssText = "font-size:0.85em;display:block;margin-bottom:4px;";
  var flowSelect = el("select", "dpmtf-input");
  flowSelect.style.cssText = "width:100%;margin-bottom:8px;";
  // Populate flows from API
  fetch("/api/bridge-v2/flows").then(function(r) { return r.json(); }).then(function(data) {
    (data.flows || data || []).forEach(function(f) {
      var opt = el("option", null, f.flow_key + " — " + (f.name || ""));
      opt.value = f.flow_key;
      flowSelect.appendChild(opt);
    });
  }).catch(function() {});
  flowLabel.appendChild(flowSelect);
  createForm.appendChild(flowLabel);

  // Role selector
  var roleLabel = el("label", null, "Role: ");
  roleLabel.style.cssText = "font-size:0.85em;display:block;margin-bottom:4px;";
  var roleSelect = el("select", "dpmtf-input");
  roleSelect.style.cssText = "width:100%;margin-bottom:8px;";
  // Populate roles from API
  fetch("/api/bridge-v2/roles").then(function(r) { return r.json(); }).then(function(data) {
    (data.roles || data || []).forEach(function(r) {
      if (r.role_type === "human") return;
      var opt = el("option", null, r.role_key + (r.default_model_alias ? " (" + r.default_model_alias + ")" : ""));
      opt.value = r.role_key;
      if (r.default_model_alias) opt.dataset.alias = r.default_model_alias;
      roleSelect.appendChild(opt);
    });
  }).catch(function() {});
  roleLabel.appendChild(roleSelect);
  createForm.appendChild(roleLabel);

  // Goal textarea
  var goalLabel = el("label", null, "Goal: ");
  goalLabel.style.cssText = "font-size:0.85em;display:block;margin-bottom:4px;";
  var goalInput = el("textarea", "dpmtf-input");
  goalInput.style.cssText = "width:100%;min-height:60px;margin-bottom:8px;";
  goalInput.placeholder = "Describe what the agent should do...";
  goalLabel.appendChild(goalInput);
  createForm.appendChild(goalLabel);

  // Project path
  var projLabel = el("label", null, "Target project: ");
  projLabel.style.cssText = "font-size:0.85em;display:block;margin-bottom:4px;";
  var projInput = el("input", "dpmtf-input");
  projInput.type = "text";
  projInput.value = "";
  projInput.style.cssText = "width:100%;margin-bottom:8px;";
  projLabel.appendChild(projInput);
  createForm.appendChild(projLabel);

  // Buttons
  var createBtn = el("button", "dpmtf-btn");
  createBtn.textContent = "Create Job";
  createBtn.onclick = function() {
    var body = {
      flow_key: flowSelect.value,
      role_key: roleSelect.value,
      goal: goalInput.value,
      target_project: projInput.value,
      allocator_alias: roleSelect.selectedOptions[0] ? (roleSelect.selectedOptions[0].dataset.alias || "") : "",
    };
    if (!body.goal) { alert("Goal is required"); return; }
    createBtn.disabled = true;
    createBtn.textContent = "Creating...";
    fetch("/api/bridge-v2/jobs", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(body),
    })
      .then(function(r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
      .then(function(data) {
        createBtn.disabled = false;
        createBtn.textContent = "Create Job";
        goalInput.value = "";
        reloadJobQueue();
      })
      .catch(function(e) {
        createBtn.disabled = false;
        createBtn.textContent = "Create Job";
        alert("Failed: " + e.message);
      });
  };
  createForm.appendChild(createBtn);

  createToggle.onclick = function() {
    if (createForm.style.display === "none") {
      createForm.style.display = "block";
      createToggle.textContent = "− Hide Form";
    } else {
      createForm.style.display = "none";
      createToggle.textContent = "+ Create Job";
    }
  };
  mount.appendChild(createForm);

  // ── Job table ──
  if (!jobs.length) {
    mount.appendChild(el("div", "dpmtf-muted", "No jobs match filter."));
  } else {
    var table = el("table", "dpmtf-table");
    table.style.cssText = "width:100%;font-size:0.85em;";

    var thead = el("thead", null);
    var headerRow = el("tr", null);
    ["Job ID", "Flow", "Role", "Status", "Goal", "Created", "Actions"].forEach(function(h) {
      headerRow.appendChild(el("th", null, h));
    });
    thead.appendChild(headerRow);
    table.appendChild(thead);

    var tbody = el("tbody", null);
    jobs.forEach(function(job) {
      var row = el("tr", null);
      row.style.cursor = "pointer";

      var idCell = el("td", null, job.job_id.substring(4, 12));
      row.appendChild(idCell);
      row.appendChild(el("td", null, job.flow_key));
      row.appendChild(el("td", null, job.role_key));

      var statusCell = el("td", null, job.status);
      if (job.status === "RUNNING") statusCell.style.color = "#28a745";
      else if (job.status === "BLOCKED" || job.status === "FAILED") statusCell.style.color = "#dc3545";
      else if (job.status === "COMPLETED") statusCell.style.color = "#6c757d";
      else if (job.status === "AWAITING_APPROVAL" || job.status === "DRAFT") statusCell.style.color = "#ffc107";
      row.appendChild(statusCell);

      var goalCell = el("td", null, (job.goal || "").substring(0, 60) + ((job.goal || "").length > 60 ? "…" : ""));
      row.appendChild(goalCell);
      row.appendChild(el("td", "dpmtf-small", (job.created_at || "").substring(0, 19)));

      // Actions
      var actionsCell = el("td", null);
      actionsCell.style.cssText = "white-space:nowrap;";

      if (job.status === "DRAFT" || job.status === "AWAITING_APPROVAL") {
        var approveBtn = el("button", "dpmtf-btn dpmtf-btn-sm");
        approveBtn.textContent = "✓ Approve";
        approveBtn.style.cssText = "font-size:0.75em;padding:2px 6px;margin-right:4px;";
        approveBtn.onclick = function(e) {
          e.stopPropagation();
          approveBtn.disabled = true;
          fetch("/api/bridge-v2/jobs/" + job.job_id + "/approve", { method: "PUT" })
            .then(function(r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
            .then(function() { reloadJobQueue(); })
            .catch(function(e) { approveBtn.disabled = false; alert(e.message); });
        };
        actionsCell.appendChild(approveBtn);
      }

      if (job.status !== "COMPLETED" && job.status !== "CANCELLED") {
        var cancelBtn = el("button", "dpmtf-btn dpmtf-btn-sm");
        cancelBtn.textContent = "✕ Cancel";
        cancelBtn.style.cssText = "font-size:0.75em;padding:2px 6px;";
        cancelBtn.onclick = function(e) {
          e.stopPropagation();
          fetch("/api/bridge-v2/jobs/" + job.job_id + "/cancel", { method: "POST" })
            .then(function(r) { return r.json(); })
            .then(function() { reloadJobQueue(); })
            .catch(function() { reloadJobQueue(); });
        };
        actionsCell.appendChild(cancelBtn);
      }

      row.appendChild(actionsCell);

      // Click row to see events
      row.onclick = function() { showJobEvents(job.job_id); };
      tbody.appendChild(row);
    });
    table.appendChild(tbody);
    mount.appendChild(table);
  }
}

function showJobEvents(jobId) {
  fetch("/api/bridge-v2/jobs/" + jobId)
    .then(function(r) { return r.json(); })
    .then(function(data) {
      var mount = document.getElementById("job-queue-dashboard");
      if (!mount) return;
      clear(mount);

      var backBtn = el("button", "dpmtf-btn dpmtf-btn-sm", "← Back");
      backBtn.style.marginBottom = "12px";
      backBtn.onclick = function() { reloadJobQueue(); };
      mount.appendChild(backBtn);

      var job = data.job || {};
      var title = el("h3", null, "Job " + job.job_id);
      mount.appendChild(title);

      // Job details
      var details = el("div", null);
      details.style.cssText = "margin-bottom:16px;font-size:0.85em;";
      var fields = [
        ["Status", job.status],
        ["Flow", job.flow_key],
        ["Role", job.role_key],
        ["Allocator alias", job.allocator_alias || "—"],
        ["Handoff ID", job.handoff_id || "—"],
        ["Goal", job.goal],
        ["Target project", job.target_project],
        ["Checkpoint", job.checkpoint_path || "—"],
        ["Retry count", job.retry_count + "/" + job.max_retries],
        ["Created", job.created_at],
      ];
      fields.forEach(function(f) {
        var row = el("div", null);
        row.style.cssText = "display:flex;gap:8px;margin-bottom:2px;";
        row.appendChild(el("span", "dpmtf-muted", f[0] + ":"));
        row.appendChild(el("span", null, f[1]));
        details.appendChild(row);
      });
      mount.appendChild(details);

      // Events timeline
      var eventsTitle = el("h4", null, "Events");
      mount.appendChild(eventsTitle);

      var events = data.events || [];
      if (!events.length) {
        mount.appendChild(el("div", "dpmtf-muted", "No events."));
      } else {
        var table = el("table", "dpmtf-table");
        table.style.cssText = "width:100%;font-size:0.8em;";
        var thead = el("thead", null);
        var hr = el("tr", null);
        ["Time", "Type", "From", "To", "Actor", "Detail"].forEach(function(h) {
          hr.appendChild(el("th", null, h));
        });
        thead.appendChild(hr);
        table.appendChild(thead);

        var tbody = el("tbody", null);
        events.forEach(function(ev) {
          var row = el("tr", null);
          row.appendChild(el("td", null, (ev.created_at || "").substring(0, 19)));
          row.appendChild(el("td", null, ev.event_type || ""));
          row.appendChild(el("td", null, ev.from_state || "—"));
          row.appendChild(el("td", null, ev.to_state || "—"));
          row.appendChild(el("td", null, ev.actor || "—"));
          row.appendChild(el("td", null, (ev.detail || "").substring(0, 80)));
          tbody.appendChild(row);
        });
        table.appendChild(tbody);
        mount.appendChild(table);
      }
    })
    .catch(function(err) {
      // If detail fetch fails, just go back
      reloadJobQueue();
    });
}

function initJobQueue() {
  if (!document.getElementById("job-queue-dashboard")) return;
  reloadJobQueue();

  // Auto-refresh every 10 seconds
  setInterval(function() {
    if (window.jobQueueState.autoRefresh && !window.jobQueueState.selectedJob) {
      reloadJobQueue();
    }
  }, 10000);
}
window.initJobQueue = initJobQueue;
