// Interactive Application Logic for Composio Take-Home Case Study

let allRecords = [];
let summaryData = {};
let activeCategory = "all";
let activeVerdict = "all";
let searchQuery = "";

function escapeHTML(value) {
  return String(value ?? "").replace(/[&<>"']/g, char => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;"
  })[char]);
}

function safeEvidenceUrl(value) {
  try {
    const url = new URL(value);
    return ["http:", "https:"].includes(url.protocol) ? url.href : "";
  } catch {
    return "";
  }
}

function renderVerdictBadge(app) {
  const labels = {
    buildable_now: "Buildable Now",
    conditional: "Conditional",
    outreach_needed: "Outreach Needed",
    unknown: "Unknown"
  };
  const colors = {
    buildable_now: "badge-green",
    conditional: "badge-amber",
    outreach_needed: "badge-purple",
    unknown: "badge-gray"
  };
  const verdict = labels[app.buildability] ? app.buildability : "unknown";
  const draft = summaryData.dataset_status !== "verified" || app.research_status !== "complete";
  const color = draft ? "badge-gray" : colors[verdict];
  return '<span class="badge ' + color + '">' +
    (draft ? "Draft · " : "") + labels[verdict] + '</span>';
}

document.addEventListener("DOMContentLoaded", () => {
  initData();
  setupEventListeners();
});

function initData() {
  if (window.CASE_STUDY_DATA) {
    allRecords = window.CASE_STUDY_DATA.records || [];
    summaryData = window.CASE_STUDY_DATA.summary || {};
    renderAll();
  } else {
    // Fallback fetch if opened over HTTP
    Promise.all([
      fetch("data/records.json").then(r => r.json()),
      fetch("data/summary.json").then(r => r.json())
    ]).then(([records, summary]) => {
      allRecords = records;
      summaryData = summary;
      renderAll();
    }).catch(err => {
      console.error("Failed to load local datasets:", err);
    });
  }
}

function renderAll() {
  renderMetrics();
  renderPatternBars();
  renderCategoryMatrix();
  renderAuditSection();
  renderTable();
}

function renderMetrics() {
  const coverage = summaryData.coverage || {};
  const breakdown = summaryData.buildability_breakdown || {};
  const supplied = Number(coverage.supplied_input_count || 0);
  const records = Number(coverage.records_present || 0);

  document.getElementById("metric-total").textContent = `${supplied} supplied`;
  document.getElementById("metric-buildable").textContent = formatDraftMetric(breakdown.buildable_now);
  document.getElementById("metric-conditional").textContent = formatDraftMetric(breakdown.conditional);
  document.getElementById("metric-outreach").textContent = formatDraftMetric(breakdown.outreach_needed);

  const isVerified = summaryData.dataset_status === "verified";
  const count = document.getElementById("metric-record-status");
  if (count) count.textContent = isVerified ? `${records} source-checked records` : `${records} draft records; source review pending`;
  const statusNote = document.getElementById("dataset-status-note");
  if (statusNote) statusNote.textContent = summaryData.quality_notice || "Classification status unavailable.";
}

function formatDraftMetric(metric) {
  if (!metric) return "Pending";
  return `${metric.count} (${metric.percentage}%)`;
}

function renderPatternBars() {
  const container = document.getElementById("auth-distribution-bars");
  if (!container || !summaryData.auth_breakdown) return;

  const ab = summaryData.auth_breakdown;
  const items = [
    { label: "OAuth 2.0 (Dominant standard)", key: "oauth2", color: "var(--accent-green)" },
    { label: "API Key / Personal Tokens", key: "api_key", color: "var(--accent-blue)" },
    { label: "Bearer & Internal Tokens", key: "token", color: "var(--accent-purple)" },
    { label: "HTTP Basic Authentication", key: "basic", color: "var(--accent-amber)" },
  ];

  container.innerHTML = items.map(it => {
    const data = ab[it.key] || { count: 0, percentage: 0 };
    return `
      <div class="pattern-bar-item">
        <div class="pattern-bar-header">
          <span>${it.label}</span>
          <span class="mono">${data.count} apps (${data.percentage}%)</span>
        </div>
        <div class="pattern-bar-bg">
          <div class="pattern-bar-fill" style="width: ${data.percentage}%; background: ${it.color};"></div>
        </div>
      </div>
    `;
  }).join("");
}

function renderCategoryMatrix() {
  const container = document.getElementById("category-matrix-body");
  if (!container || !summaryData.category_matrix) return;

  container.innerHTML = Object.entries(summaryData.category_matrix).map(([cat, data]) => `
    <tr>
      <td style="font-weight: 500;">${escapeHTML(cat)}</td>
      <td class="mono">${Number(data.total) || 0}</td>
      <td><span class="badge badge-green">${Number(data.buildable_now) || 0}</span></td>
      <td><span class="badge badge-amber">${Number(data.conditional) || 0}</span></td>
      <td><span class="badge badge-purple">${Number(data.outreach_needed) || 0}</span></td>
      <td><span class="badge badge-gray">${Number(data.unknown) || 0}</span></td>
      <td class="mono">${Number(data.self_serve_pct) || 0}%</td>
      <td><span class="badge badge-gray mono">${escapeHTML(data.dominant_auth || "unknown")}</span></td>
    </tr>
  `).join("");
}

function renderAuditSection() {
  const status = document.getElementById("audit-status");
  const detail = document.getElementById("audit-status-detail");
  const sample = document.getElementById("audit-sample-ids");
  const metricsContainer = document.getElementById("audit-metrics");
  const missesContainer = document.getElementById("audit-misses-container");
  if (!status) return;

  const complete = summaryData.audit_status === "complete";
  status.textContent = complete ? "Human audit complete" : "Pending independent review";
  if (detail) {
    detail.textContent = complete
      ? "Scores below use the recorded human checks and list unverifiable fields outside the denominator."
      : "No accuracy score is available. The prior synthetic baseline and static expected values were removed.";
  }

  const ids = summaryData.planned_sample_ids || [];
  if (sample) sample.textContent = ids.length ? `Planned sample IDs: ${ids.join(", ")}` : "Sample IDs will be frozen before manual verification.";

  const audit = summaryData.audit_metrics || {};
  const first = audit.first_pass || {};
  const final = audit.final_pass || {};
  const fieldScores = document.getElementById("audit-field-scores");
  const appScores = document.getElementById("audit-app-scores");
  if (metricsContainer) {
    metricsContainer.hidden = !complete;
    metricsContainer.style.display = complete ? "grid" : "none";
  }
  if (complete && fieldScores && appScores) {
    fieldScores.textContent = `${first.field_numerator}/${first.field_denominator} (${first.field_level_accuracy_pct}%) → ${final.field_numerator}/${final.field_denominator} (${final.field_level_accuracy_pct}%)`;
    appScores.textContent = `${first.app_numerator}/${first.app_denominator} (${first.app_level_accuracy_pct}%) → ${final.app_numerator}/${final.app_denominator} (${final.app_level_accuracy_pct}%)`;
  }

  if (missesContainer) {
    const misses = complete ? (summaryData.concrete_misses || []) : [];
    missesContainer.textContent = misses.length
      ? misses.map(item => `#${item.app_id} ${item.field}: ${JSON.stringify(item.first_pass_value)} → ${JSON.stringify(item.checked_value)} → ${JSON.stringify(item.final_pass_value)} (${item.source_url})`).join("\n")
      : "";
  }
}

function renderTable() {
  const tbody = document.getElementById("matrix-tbody");
  if (!tbody) return;

  const filtered = allRecords.filter(r => {
    // Category filter
    if (activeCategory !== "all" && r.category !== activeCategory) return false;
    // Verdict filter
    if (activeVerdict !== "all" && r.buildability !== activeVerdict) return false;
    // Search query
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      const matchName = r.name.toLowerCase().includes(q);
      const matchCat = r.category.toLowerCase().includes(q);
      const matchHint = (r.website_hint || "").toLowerCase().includes(q);
      const matchBlocker = (r.main_blocker || "").toLowerCase().includes(q);
      if (!matchName && !matchCat && !matchHint && !matchBlocker) return false;
    }
    return true;
  });

  document.getElementById("matrix-count-display").textContent = `Showing ${filtered.length} of ${allRecords.length} apps`;

  if (filtered.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align: center; padding: 32px; color: var(--text-dim);">No matching applications found.</td></tr>`;
    return;
  }

  tbody.innerHTML = filtered.map(r => {
    const verdictBadge = renderVerdictBadge(r);

    const authBadges = (r.auth_methods || []).map(m => `<span class="badge badge-gray" style="margin-right: 4px;">${escapeHTML(m)}</span>`).join("");
    const mcpBadge = r.existing_mcp === "official" 
      ? `<span class="badge badge-blue">Official</span>` 
      : (r.existing_mcp === "third_party" ? `<span class="badge badge-gray">Community</span>` : `<span style="color: var(--text-dim);">&mdash;</span>`);

    return `
      <tr tabindex="0" role="button" aria-label="Open ${escapeHTML(r.name)} details" onclick="openDrawer(${Number(r.id) || 0})" onkeydown="if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); openDrawer(${Number(r.id) || 0}); }">
        <td class="mono" style="color: var(--text-dim);">${Number(r.id) || 0}</td>
        <td>
          <div style="font-weight: 600;">${escapeHTML(r.name)}</div>
          <div style="font-size: 11px; color: var(--text-dim);">${escapeHTML(r.website_hint)}</div>
        </td>
        <td style="color: var(--text-muted);">${escapeHTML(r.category)}</td>
        <td>${authBadges}</td>
        <td><span class="mono" style="font-size: 12px;">${escapeHTML(r.api_breadth)}</span></td>
        <td>${mcpBadge}</td>
        <td>${verdictBadge}</td>
      </tr>
    `;
  }).join("");
}

function openDrawer(appId) {
  const app = allRecords.find(r => r.id === appId);
  if (!app) return;

  document.getElementById("drawer-title").textContent = app.name;
  document.getElementById("drawer-category").textContent = app.category;
  document.getElementById("drawer-summary").textContent = app.summary || "No summary available.";
  document.getElementById("drawer-hint").textContent = app.website_hint || "N/A";
  document.getElementById("drawer-blocker").textContent = app.main_blocker || "none";
  const apiTypes = Array.isArray(app.api_types) ? app.api_types.join(", ") : "unknown";
  document.getElementById("drawer-api-summary").textContent = `Types: ${apiTypes || "unknown"} · Breadth: ${app.api_breadth || "unknown"} · MCP: ${app.existing_mcp || "unknown"} · Review: ${app.research_status || "unknown"}`;
  
  document.getElementById("drawer-verdict-badge").innerHTML = renderVerdictBadge(app);

  // Render Credential Access Matrix
  const ca = app.credential_access || {};
  document.getElementById("drawer-credentials-list").innerHTML = `
    <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; font-size: 12px;" class="mono">
      <div>Self-Serve Signup: <strong style="color: ${ca.self_serve_signup === 'yes' ? 'var(--accent-green)' : '#ef4444'}">${ca.self_serve_signup}</strong></div>
      <div>Free/Trial: <strong style="color: ${ca.free_or_trial_credentials === 'yes' ? 'var(--accent-green)' : '#ef4444'}">${ca.free_or_trial_credentials}</strong></div>
      <div>Paid Plan Required: <strong style="color: ${ca.paid_plan_required === 'yes' ? 'var(--accent-amber)' : 'var(--text-main)'}">${ca.paid_plan_required}</strong></div>
      <div>Admin Approval: <strong style="color: ${ca.admin_approval_required === 'yes' ? 'var(--accent-amber)' : 'var(--text-main)'}">${ca.admin_approval_required}</strong></div>
      <div style="grid-column: span 2;">Partner Approval: <strong style="color: ${ca.partner_approval_required === 'yes' ? 'var(--accent-purple)' : 'var(--accent-green)'}">${ca.partner_approval_required}</strong></div>
    </div>
  `;

  // Do not display draft quotes as verified evidence before source matching passes.
  const evContainer = document.getElementById("drawer-evidence-container");
  if (summaryData.dataset_status === "provisional") {
    const urls = [...new Set((app.evidence || []).map(ev => safeEvidenceUrl(ev.url)).filter(Boolean))];
    const sourceLinks = urls.map(url =>
      '<div style="margin-top: 8px;"><a href="' + escapeHTML(url) +
      '" target="_blank" rel="noopener noreferrer" class="evidence-url mono">' +
      escapeHTML(url) + ' ↗</a></div>'
    ).join("");
    evContainer.innerHTML =
      '<div style="color: var(--text-muted); font-size: 12px;">Candidate source links. Claims and quotes remain unverified.</div>' +
      (sourceLinks || '<div style="color: var(--text-dim); font-size: 12px; margin-top: 8px;">No source link recorded.</div>');
  } else if (app.evidence && app.evidence.length > 0) {
    evContainer.innerHTML = app.evidence.map(ev => {
      const url = safeEvidenceUrl(ev.url);
      const sourceLink = url ? `<a href="${escapeHTML(url)}" target="_blank" rel="noopener noreferrer" class="evidence-url mono">${escapeHTML(url)} &nearr;</a>` : "";
      return `
        <div style="background: rgba(255,255,255,0.02); border: 1px solid var(--border-color); border-radius: 6px; padding: 14px; margin-bottom: 12px;">
          <div class="badge badge-gray mono">${escapeHTML(ev.field)}</div>
          <div style="font-size: 13px; font-weight: 500; margin: 6px 0;">${escapeHTML(ev.claim)}</div>
          <div class="evidence-quote-box">&ldquo;${escapeHTML(ev.quote)}&rdquo;</div>
          ${sourceLink}
          <div style="font-size: 10px; color: var(--text-dim); margin-top: 4px;" class="mono">Retrieved: ${escapeHTML(ev.retrieved_at)}</div>
        </div>`;
    }).join("");
  } else {
    evContainer.innerHTML = `<div style="color: var(--text-dim); font-size: 12px;">No evidence cards logged.</div>`;
  }

  document.getElementById("drawer").classList.add("open");
  document.getElementById("drawer-backdrop").classList.add("open");
}

function closeDrawer() {
  document.getElementById("drawer").classList.remove("open");
  document.getElementById("drawer-backdrop").classList.remove("open");
}

function setupEventListeners() {
  // Drawer close events
  document.getElementById("drawer-close-btn").addEventListener("click", closeDrawer);
  document.getElementById("drawer-backdrop").addEventListener("click", closeDrawer);
  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeDrawer();
  });

  // Search input
  const searchEl = document.getElementById("matrix-search");
  if (searchEl) {
    searchEl.addEventListener("input", (e) => {
      searchQuery = e.target.value;
      renderTable();
    });
  }

  // Category filters
  document.querySelectorAll(".cat-filter-btn").forEach(btn => {
    btn.addEventListener("click", (e) => {
      document.querySelectorAll(".cat-filter-btn").forEach(b => b.classList.remove("active"));
      e.target.classList.add("active");
      activeCategory = e.target.getAttribute("data-cat");
      renderTable();
    });
  });

  // Verdict filters
  document.querySelectorAll(".verdict-filter-btn").forEach(btn => {
    btn.addEventListener("click", (e) => {
      document.querySelectorAll(".verdict-filter-btn").forEach(b => b.classList.remove("active"));
      e.target.classList.add("active");
      activeVerdict = e.target.getAttribute("data-verdict");
      renderTable();
    });
  });
}
