// Interactive Application Logic for Composio Take-Home Case Study

let allRecords = [];
let summaryData = {};
let activeCategory = "all";
let activeVerdict = "all";
let searchQuery = "";

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
  const bb = summaryData.buildability_breakdown || {};
  const mcp = summaryData.mcp_breakdown || {};

  document.getElementById("metric-total").textContent = summaryData.coverage ? `${summaryData.coverage.total_researched}/90` : "90/90";
  document.getElementById("metric-buildable").textContent = bb.buildable_now ? `${bb.buildable_now.count} (${bb.buildable_now.percentage}%)` : "72 (80.0%)";
  document.getElementById("metric-conditional").textContent = bb.conditional ? `${bb.conditional.count} (${bb.conditional.percentage}%)` : "14 (15.6%)";
  document.getElementById("metric-outreach").textContent = bb.outreach_needed ? `${bb.outreach_needed.count} (${bb.outreach_needed.percentage}%)` : "4 (4.4%)";
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

  const cm = summaryData.category_matrix;
  container.innerHTML = Object.entries(cm).map(([cat, data]) => {
    return `
      <tr>
        <td style="font-weight: 500;">${cat}</td>
        <td class="mono">${data.total}</td>
        <td><span class="badge badge-green">${data.buildable_now}</span></td>
        <td><span class="badge badge-amber">${data.conditional}</span></td>
        <td><span class="badge badge-purple">${data.outreach_needed}</span></td>
        <td class="mono">${data.self_serve_pct}%</td>
        <td><span class="badge badge-gray mono">${data.dominant_auth}</span></td>
      </tr>
    `;
  }).join("");
}

function renderAuditSection() {
  const m = summaryData.audit_metrics;
  if (!m) return;

  const fp = m.first_pass || {};
  const fn = m.final_pass || {};

  const fpField = document.getElementById("audit-fp-field");
  const fnField = document.getElementById("audit-fn-field");
  const fpApp = document.getElementById("audit-fp-app");
  const fnApp = document.getElementById("audit-fn-app");

  if (fpField) fpField.textContent = `${fp.field_level_accuracy_pct}% (${fp.field_numerator}/${fp.field_denominator})`;
  if (fnField) fnField.textContent = `${fn.field_level_accuracy_pct}% (${fn.field_numerator}/${fn.field_denominator})`;
  if (fpApp) fpApp.textContent = `${fp.app_level_accuracy_pct}% (${fp.app_numerator}/${fp.app_denominator})`;
  if (fnApp) fnApp.textContent = `${fn.app_level_accuracy_pct}% (${fn.app_numerator}/${fn.app_denominator})`;

  // Render concrete misses
  const missesContainer = document.getElementById("audit-misses-container");
  if (missesContainer && summaryData.concrete_misses) {
    missesContainer.innerHTML = summaryData.concrete_misses.map(miss => `
      <div style="background: rgba(255,255,255,0.02); border: 1px solid var(--border-color); border-radius: 6px; padding: 14px; margin-bottom: 12px;">
        <div style="display: flex; justify-content: space-between; margin-bottom: 6px;">
          <span style="font-weight: 600;">#${miss.app_id} ${miss.app_name} &bull; <span class="mono" style="color: var(--accent-amber);">${miss.field}</span></span>
          <span class="badge badge-purple">Baseline Miss Corrected</span>
        </div>
        <div style="font-size: 12px; margin-bottom: 4px;">
          <span style="color: var(--text-dim);">Initial Baseline:</span> <span class="mono" style="color: #ef4444;">${JSON.stringify(miss.first_pass_val)}</span>
          &rarr; <span style="color: var(--text-dim);">Verified Ground Truth:</span> <span class="mono" style="color: var(--accent-green);">${JSON.stringify(miss.ground_truth_val)}</span>
        </div>
        <div style="font-size: 12px; color: var(--text-muted);">${miss.correction_rationale}</div>
      </div>
    `).join("");
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
    let verdictBadge = "";
    if (r.buildability === "buildable_now") {
      verdictBadge = `<span class="badge badge-green">Buildable Now</span>`;
    } else if (r.buildability === "conditional") {
      verdictBadge = `<span class="badge badge-amber">Conditional</span>`;
    } else if (r.buildability === "outreach_needed") {
      verdictBadge = `<span class="badge badge-purple">Outreach Needed</span>`;
    } else {
      verdictBadge = `<span class="badge badge-gray">Unknown</span>`;
    }

    const authBadges = (r.auth_methods || []).map(m => `<span class="badge badge-gray" style="margin-right: 4px;">${m}</span>`).join("");
    const mcpBadge = r.existing_mcp === "official" 
      ? `<span class="badge badge-blue">Official</span>` 
      : (r.existing_mcp === "third_party" ? `<span class="badge badge-gray">Community</span>` : `<span style="color: var(--text-dim);">&mdash;</span>`);

    return `
      <tr onclick="openDrawer(${r.id})">
        <td class="mono" style="color: var(--text-dim);">${r.id}</td>
        <td>
          <div style="font-weight: 600;">${r.name}</div>
          <div style="font-size: 11px; color: var(--text-dim);">${r.website_hint}</div>
        </td>
        <td style="color: var(--text-muted);">${r.category}</td>
        <td>${authBadges}</td>
        <td><span class="mono" style="font-size: 12px;">${r.api_breadth}</span></td>
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
  
  let verdictBadge = "";
  if (app.buildability === "buildable_now") {
    verdictBadge = `<span class="badge badge-green">Buildable Now</span>`;
  } else if (app.buildability === "conditional") {
    verdictBadge = `<span class="badge badge-amber">Conditional</span>`;
  } else {
    verdictBadge = `<span class="badge badge-purple">Outreach Needed</span>`;
  }
  document.getElementById("drawer-verdict-badge").innerHTML = verdictBadge;

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

  // Render Evidence cards
  const evContainer = document.getElementById("drawer-evidence-container");
  if (app.evidence && app.evidence.length > 0) {
    evContainer.innerHTML = app.evidence.map(ev => `
      <div style="background: rgba(255,255,255,0.02); border: 1px solid var(--border-color); border-radius: 6px; padding: 14px; margin-bottom: 12px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
          <span class="badge badge-gray mono">${ev.field}</span>
          <span class="badge badge-green mono">Jev: ${ev.verification}</span>
        </div>
        <div style="font-size: 13px; font-weight: 500; margin-bottom: 6px;">${ev.claim}</div>
        <div class="evidence-quote-box">&ldquo;${ev.quote}&rdquo;</div>
        <a href="${ev.url}" target="_blank" rel="noopener noreferrer" class="evidence-url mono">${ev.url} &nearr;</a>
        <div style="font-size: 10px; color: var(--text-dim); margin-top: 4px;" class="mono">Retrieved: ${ev.retrieved_at}</div>
      </div>
    `).join("");
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
