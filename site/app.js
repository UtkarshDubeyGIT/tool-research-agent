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
  const checked = app.research_status === "complete";
  const color = checked ? colors[verdict] : "badge-gray";
  return '<span class="badge ' + color + '">' +
    (checked ? "Source checked · " : "Needs review · ") + labels[verdict] + '</span>';
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
  const supplied = Number(coverage.supplied_input_count || 0);
  const records = Number(coverage.records_present || 0);

  document.getElementById("metric-total").textContent = String(supplied);
  document.getElementById("metric-buildable").textContent = String(Number(coverage.complete_records || 0));
  document.getElementById("metric-conditional").textContent = String(Number(coverage.needs_review_records || 0) + Number(coverage.blocked_records || 0));
  document.getElementById("metric-outreach").textContent = String((summaryData.planned_sample_ids || []).length);

  const count = document.getElementById("metric-record-status");
  if (count) count.textContent = `${records} records; ${Number(coverage.complete_records || 0)} source checked`;
  const statusNote = document.getElementById("dataset-status-note");
  if (statusNote) statusNote.textContent = summaryData.quality_notice || "Classification status unavailable.";
}

function renderPatternBars() {
  const container = document.getElementById("auth-distribution-bars");
  if (!container || !summaryData.auth_breakdown) return;

  const ab = summaryData.auth_breakdown;
  const items = [
    { label: "OAuth 2.0", key: "oauth2", color: "var(--accent-green)" },
    { label: "API keys", key: "api_key", color: "var(--accent-blue)" },
    { label: "Bearer or internal tokens", key: "token", color: "var(--accent-purple)" },
    { label: "HTTP Basic", key: "basic", color: "var(--accent-amber)" },
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

  const quality = summaryData.evidence_quality || {};
  const quoteRate = document.getElementById("quote-check-rate");
  if (quoteRate && quality.first_pass && quality.final_pass) {
    const first = quality.first_pass;
    const final = quality.final_pass;
    quoteRate.textContent = `${first.exact}/${first.total} (${first.percentage}%) first pass → ${final.exact}/${final.total} (${final.percentage}%) final pass`;
  }
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

  // Keep unknown distinct from a verified no.
  const ca = app.credential_access || {};
  const credentialLabels = [
    ["Self-serve signup", "self_serve_signup"],
    ["Free or trial credentials", "free_or_trial_credentials"],
    ["Paid plan required", "paid_plan_required"],
    ["Admin approval", "admin_approval_required"],
    ["Partner approval", "partner_approval_required"]
  ];
  document.getElementById("drawer-credentials-list").innerHTML = credentialLabels.map(([label, key]) => {
    const value = ["yes", "no"].includes(ca[key]) ? ca[key] : "unknown";
    return `<div class="credential-row"><span>${label}</span><strong class="credential-value credential-${value}">${value}</strong></div>`;
  }).join("");

  const evContainer = document.getElementById("drawer-evidence-container");
  const supported = (app.evidence || []).filter(ev => ev.verification === "supported" && safeEvidenceUrl(ev.url));
  const unresolved = (app.evidence || []).filter(ev => ev.verification !== "supported" && safeEvidenceUrl(ev.url));
  const cards = supported.map(ev => {
    const url = safeEvidenceUrl(ev.url);
    return `<article class="evidence-card">
      <div class="badge badge-blue mono">Source checked · ${escapeHTML(ev.field)}</div>
      <p class="evidence-claim">${escapeHTML(ev.claim)}</p>
      <blockquote class="evidence-quote-box">“${escapeHTML(ev.quote)}”</blockquote>
      <a href="${escapeHTML(url)}" target="_blank" rel="noopener noreferrer" class="evidence-url mono">Open source ↗</a>
    </article>`;
  }).join("");
  const pendingUrls = [...new Set(unresolved.map(ev => safeEvidenceUrl(ev.url)))];
  const pending = pendingUrls.length
    ? `<div class="evidence-pending"><strong>Unresolved source checks</strong><p>These candidate claims are excluded from the checked evidence above.</p>${pendingUrls.map(url => `<a href="${escapeHTML(url)}" target="_blank" rel="noopener noreferrer" class="evidence-url mono">${escapeHTML(url)} ↗</a>`).join("")}</div>`
    : "";
  evContainer.innerHTML = cards + pending || '<p class="empty-evidence">No source-backed evidence is available for this record yet.</p>';

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
