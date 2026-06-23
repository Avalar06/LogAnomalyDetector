// ----- Timezone handling -----
let activeTimezone = "UTC"; // "UTC" | "IST"
 // "live" | "upload" | "all"
window.activeSeverity = "ALL";
let refreshInterval = null;
let currentMode =
  localStorage.getItem("dashboard_mode") || "live";

function setTimezone(tz) {
  if (tz !== "UTC" && tz !== "IST") return;

  activeTimezone = tz;

  const tzUTC = document.getElementById("tzUTC");
  const tzIST = document.getElementById("tzIST");
  const switchEl = document.getElementById("timezoneSwitch");

  tzUTC?.classList.toggle("active", tz === "UTC");
  tzIST?.classList.toggle("active", tz === "IST");

  switchEl?.classList.toggle("ist-active", tz === "IST");

  if (Array.isArray(latestAnomalies)) {
    updateChart(latestAnomalies);
  }
}

try {
  window.activeSeverity = localStorage.getItem("severityFilter") || "ALL";
} catch (e) {
  window.activeSeverity = "ALL";
}



function startAutoRefresh() {

    stopAutoRefresh();

    refresh();

    refreshInterval = setInterval(async () => {

        if (currentMode === "live") {
            await refresh();
        }

    }, 3000);
}

function stopAutoRefresh() {

    if (refreshInterval) {

        clearInterval(refreshInterval);

        refreshInterval = null;
    }
}


// static/js/dashboard.js  (defensive + verbose)
// console.log("dashboard.js (defensive) loaded at", new Date().toISOString());




// Latest anomalies collapse state
let anomaliesExpanded = false;
const COLLAPSED_LIMIT = 5; // show only 5 anomalies initially

// ===== HARD BASELINE (authoritative) =====
// ===== HARD PAGE-LOAD BASELINE =====
const PAGE_LOAD_TIME = new Date();


// Dedup set (should already exist, but confirm)



console.log(
  "[toast] PAGE_LOAD_TIME initialized at:",
  PAGE_LOAD_TIME.toString()
);

console.log(
  "[toast] PAGE_LOAD_TIME initialized at:",
  PAGE_LOAD_TIME.toString()
);


// Safely extract a usable Date from anomaly rows
function extractAnomalyDate(a) {
  const raw =
    a?.detected_at ||
    a?.timestamp ||
    a?.time ||
    a?.datetime ||
    "";

  const d = new Date(raw);
  if (!isNaN(d.getTime())) return d;

  // fallback for live anomalies with missing / bad timestamps
  return new Date();
}





/* ========= GLOBAL STATE ========= */

// Toast / anomaly tracking state
let initialAnomaliesLoadDone = false;  // first fetch vs subsequent polls
let lastSeenDetectedAt = null;         // Date object of latest anomaly we've already notified about
const pageLoadTime = new Date();       // safety baseline (when page loaded)
// filter state
let activeServiceFilter = null;      
const STORAGE_ACTIVE_FILTER_KEY = "anomaly_active_service_filter";
// chart + data caches
let anomalyChart = null;
let serviceChart = null;
let latestAnomalies = []; 
// Toast deduplication
const notifiedAnomalyKeys = new Set(
  JSON.parse(localStorage.getItem("notifiedAnomalyKeys") || "[]")
);
let actionsMap = {};


/*------------------------------------*/


function setSeverityFilter(level) {
  window.activeSeverity = level;

  // save in localStorage
  try {
    localStorage.setItem("severityFilter", level);
  } catch (e) {}

  // highlight active button
  document.querySelectorAll('[data-sev]').forEach(btn => {
    btn.classList.remove('active');
    if (btn.getAttribute('data-sev') === level) {
      btn.classList.add('active');
    }
  });

  if (typeof refresh === "function") refresh();
}


function applyServiceFilter(serviceName) {
  if (!serviceName) return;
  activeServiceFilter = String(serviceName);
  try { localStorage.setItem(STORAGE_ACTIVE_FILTER_KEY, activeServiceFilter); } catch(e){}

  // update UI banner & clear button
  showFilterBanner(activeServiceFilter);
  const clearBtn = document.getElementById("clearFilterBtn");
  if (clearBtn) clearBtn.style.display = "inline-block";

  // render filtered view from cached anomalies
  if (Array.isArray(latestAnomalies)) {
    const filtered = latestAnomalies.filter(a => ((a.service || a.svc || "") + "") === activeServiceFilter);
    renderTable(filtered);
    updateChart(filtered);
    // leave donut showing global counts (helps context)
    // console.log("Applied filter:", activeServiceFilter, "=>", filtered.length, "rows");
  }
}

// clear the active service filter and restore full view
function clearServiceFilter() {
  activeServiceFilter = null;
  try { localStorage.removeItem(STORAGE_ACTIVE_FILTER_KEY); } catch(e){}
  hideFilterBanner();
  const clearBtn = document.getElementById("clearFilterBtn");
  if (clearBtn) clearBtn.style.display = "none";

  if (Array.isArray(latestAnomalies)) {
    renderTable(latestAnomalies);
    updateChart(latestAnomalies);
    updateServiceDonut(latestAnomalies);


  }
}

// small banner helpers
function showFilterBanner(service) {
  const el = document.getElementById("filterBanner");
  if (!el) return;
  el.textContent = `Filter applied — showing only service: ${service}`;
  el.style.display = "inline-block";
}

function hideFilterBanner() {
  const el = document.getElementById("filterBanner");
  if (!el) return;
  el.style.display = "none";
}


// console.log("dashboard.js (defensive) loaded at", new Date().toISOString());
// chart globals (declare before any init functions)

//---------------------------------hash assignent to anomalies ------------------------
function generateAnomalyId(a) {
  const ts   = safeGet(a, "detected_at", safeGet(a, "timestamp", ""));
  const host = safeGet(a, "host", "");
  const svc  = safeGet(a, "service", safeGet(a, "svc", ""));
  const sev  = safeGet(a, "severity", "LOW");
  const src  = safeGet(a, "source", "live");
  const msg  = (safeGet(a, "message", "") || "").trim();

  return `${ts}|${host}|${svc}|${sev}|${src}|${msg}`;
}
//-----------------------------------------------


async function loadActionsMap() {
  try {
    const res = await fetch("/api/anomalies/actions");
    if (!res.ok) throw new Error("Failed to fetch actions");

    actionsMap = await res.json();
    // console.log("actionsMap loaded:", actionsMap);

  } catch (e) {
    console.error("Could not load actions map:", e);
    actionsMap = {};
  }
}



/*---------------*/ 

function getMessageFromRow(anomalyId) {
  const row = document.querySelector(`tr[data-id="${anomalyId}"]`);
  if (!row) return "";

  const messageCell = row.querySelector(".col-message");
  return messageCell ? messageCell.innerText.trim() : "";
}

/* utility */
function safeGet(o, k, fallback="") {
  try { return (o && o[k] !== undefined) ? o[k] : fallback; } catch { return fallback; }
}
// ----- Toast helpers & state -----
let lastSeenTimestamp = null; // ISO string of last anomaly we've acknowledged


function createToastContainer() {
  if (document.getElementById('toastContainer')) return;
  const c = document.createElement('div');
  c.id = 'toastContainer';
  c.style.position = 'fixed';
  c.style.top = '18px';
  c.style.right = '18px';
  c.style.zIndex = 99999;
  c.style.display = 'flex';
  c.style.flexDirection = 'column';
  c.style.gap = '10px';
  document.body.appendChild(c);
}

function showToast(title, text, tone = 'info', timeout = 9000) {
  createToastContainer();
  const container = document.getElementById('toastContainer');
  const toast = document.createElement('div');

  toast.className = 'toast';
  toast.style.minWidth = '260px';
  toast.style.maxWidth = '420px';
  toast.style.padding = '12px 14px';
  toast.style.borderRadius = '10px';
  toast.style.boxShadow = '0 8px 30px rgba(0,0,0,0.45)';
  toast.style.background =
    tone === 'error'
      ? 'linear-gradient(90deg,#ff7b7b,#ffb3b3)'
      : 'linear-gradient(90deg,#f4b03a,#f6d06e)';
  toast.style.color = '#062';
  toast.style.fontWeight = 700;

  // animation state
  toast.style.opacity = 0;
  toast.style.transform = 'translateY(-6px)';
  toast.style.transition = 'opacity .35s ease, transform .35s ease';

  toast.innerHTML = `
    <div style="font-size:14px;font-weight:800;margin-bottom:4px">
      ${escapeHtml(title)}
    </div>
    <div style="font-size:13px;font-weight:600;color:#062">
      ${escapeHtml(text)}
    </div>
  `;

  container.prepend(toast);
  // fade-in
  requestAnimationFrame(() => {
    toast.style.opacity = 1;
    toast.style.transform = 'translateY(0)';
  });

  // console.log("Toast shown:", title, text);
  // stay longer + smooth fade-out
  setTimeout(() => {
    toast.style.opacity = 0;
    toast.style.transform = 'translateY(-6px)';
    // smoother removal
    setTimeout(() => toast.remove(), 1200);
  }, timeout);
}



/* --------- UI helpers: count-up + pulse highlight --------- */
function animateCount(el, target, duration=800) {
  if (!el) return;
  const start = parseInt(el.textContent || "0", 10) || 0;
  const end = parseInt(target || 0, 10);
  if (start === end) return;
  const startTime = performance.now();
  function step(t) {
    const p = Math.min(1, (t - startTime) / duration);
    const eased = Math.round(start + (end - start) * (1 - Math.pow(1 - p, 3)));
    el.textContent = eased;
    if (p < 1) requestAnimationFrame(step);
    else {
      // pulse highlight briefly
      el.closest('.stat-tile')?.classList.add('pulse');
      setTimeout(()=> el.closest('.stat-tile')?.classList.remove('pulse'), 900);
    }
  }
  requestAnimationFrame(step);
}

/* small helper to update counts using animateCount */
function setCountsSafely(counts) {
  try {
    animateCount(document.getElementById("totalAnomalies"), counts.total ?? counts.total_anomalies ?? 0);
    animateCount(document.getElementById("last10m"), counts.last_10_minutes ?? counts.last10m ?? 0);
    animateCount(document.getElementById("last1h"), counts.last_1_hour ?? counts.last1h ?? 0);
    animateCount(document.getElementById("last24h"), counts.last_24_hours ?? counts.last24h ?? 0);
    // big number
    animateCount(document.getElementById("bigNumber"), counts.total ?? counts.total_anomalies ?? 0);
  } catch (e) { console.warn("count update failed", e); }
}

function escapeHtml(unsafe) {
  if (unsafe === null || unsafe === undefined) return "";
  return String(unsafe)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

/* fetch stats (with animated update) */
async function fetchStats() {
  try {

    const res = await fetch(
      buildUrl("/api/stats")
    );

    if (!res.ok) {
      throw new Error(`stats fetch failed: ${res.status}`);
    }

    const stats = await res.json();

    // -------------------------------
    // Mode-aware counts
    // -------------------------------
    let counts = stats.counts || {};

    console.log("FETCH STATS MODE:", currentMode);
    console.log("RAW STATS:", stats);
    console.log("COUNTS:", counts);

    // -------------------------------
    // Update tiles
    // -------------------------------
    const elTotal = document.getElementById("totalAnomalies");
    const el10m   = document.getElementById("last10m");
    const el1h    = document.getElementById("last1h");
    const el24h   = document.getElementById("last24h");

    if (elTotal) elTotal.innerText = counts.total ?? 0;
    if (el10m)   el10m.innerText = counts.last_10_minutes ?? 0;
    if (el1h)    el1h.innerText = counts.last_1_hour ?? 0;
    if (el24h)   el24h.innerText = counts.last_24_hours ?? 0;

    // -------------------------------
    // Big number tile
    // -------------------------------
    const big = document.getElementById("bigNumber");

    if (big) {
      big.innerText = counts.total ?? 0;
    }

    // -------------------------------
    // Donut chart update
    // -------------------------------
    if (window.serviceDonutChart && stats.by_service) {

      window.serviceDonutChart.data.labels =
        Object.keys(stats.by_service);

      window.serviceDonutChart.data.datasets[0].data =
        Object.values(stats.by_service);

      window.serviceDonutChart.update();
    }

    // -------------------------------
    // Model Status / Retraining Cards
    // -------------------------------
    const historyRes = await fetch(
      buildUrl("/api/retraining-history")
    );

    if (historyRes.ok) {

      const history = await historyRes.json();

      if (history && history.length > 0) {

        const latest = history[history.length - 1];

        const retrainEl =
          document.getElementById("lastRetrain");

        const feedbackEl =
          document.getElementById("feedbackRows");

        const outcomeEl =
          document.getElementById("retrainOutcome");

        const precisionEl =
          document.getElementById("retrainPrecision");

        const recallEl =
          document.getElementById("retrainRecall");

        const f1El =
          document.getElementById("retrainF1");

        const thresholdEl =
          document.getElementById("retrainThreshold");

        // -------------------------------
        // Last Retrain Time
        // -------------------------------
        if (retrainEl) {

          let formattedTime = "--";

          if (latest.timestamp) {

            const ts = String(latest.timestamp);

            if (ts.length >= 15) {

              formattedTime =
                `${ts.slice(0,4)}-${ts.slice(4,6)}-${ts.slice(6,8)} `
                + `${ts.slice(9,11)}:${ts.slice(11,13)}`;
            }
          }

          retrainEl.innerText =
            `Last Retrain: ${formattedTime}`;
        }

        // -------------------------------
        // Feedback Samples
        // -------------------------------
        if (feedbackEl) {

          feedbackEl.innerText =
            `Feedback Samples: ${latest.feedback_samples ?? 0}`;
        }

        // -------------------------------
        // Precision
        // -------------------------------
        if (precisionEl) {

          precisionEl.innerText =
            `Precision: ${((latest.precision ?? 0) * 100).toFixed(2)}%`;
        }

        // -------------------------------
        // Recall
        // -------------------------------
        if (recallEl) {

          recallEl.innerText =
            `Recall: ${((latest.recall ?? 0) * 100).toFixed(2)}%`;
        }

        // -------------------------------
        // F1 Score
        // -------------------------------
        if (f1El) {

          f1El.innerText =
            `F1 Score: ${((latest.f1_score ?? 0) * 100).toFixed(2)}%`;
        }

        // -------------------------------
        // Best Threshold
        // -------------------------------
        if (thresholdEl) {

          thresholdEl.innerText =
            `Best Threshold: ${
              latest.best_threshold !== undefined
              ? Number(latest.best_threshold).toFixed(2)
              : "--"
            }`;
        }

        // -------------------------------
        // Deployment Outcome
        // -------------------------------


        const status =
        latest.deployment_status ?? "UNKNOWN";
        
        outcomeEl.innerText = status;

        outcomeEl.classList.remove(
          "status-deployed",
          "status-failed"
        );
        
        if (status === "DEPLOYED") {
          outcomeEl.classList.add("status-deployed");
        }
        else if (status === "FAILED") {
          outcomeEl.classList.add("status-failed");
        }
        
      }
    }

  } catch (err) {

    console.error("fetchStats error:", err);

  }
}

function normalizeAnomaliesResponse(data) {

  if (Array.isArray(data)) return data;

  if (Array.isArray(data.anomalies)) return data.anomalies;

  if (Array.isArray(data.results)) return data.results;

  if (Array.isArray(data.data)) return data.data;

  for (const k of Object.keys(data || {})) {
    if (Array.isArray(data[k])) {
      return data[k];
    }
  }

  return [];
}

function deriveSeverity(prob) {

  const value = Number(prob || 0);

  if (value >= 0.8) return "HIGH";

  if (value >= 0.6) return "MEDIUM";

  return "LOW";
}

/* fetch anomalies (final corrected version) */
async function fetchAnomalies() {
  try {
    const res = await fetch(
      buildUrl("/api/anomalies?limit=1000")
    );

    if (!res.ok) {
      throw new Error(`anomalies fetch failed: ${res.status}`);
    }

    const data = await res.json();

    // ---------- Normalize ----------
  const anomalies = normalizeAnomaliesResponse(data);

    // ---------- Sort ----------

    const severityOrder = {
      HIGH: 3,
      MEDIUM: 2,
      LOW: 1,
    };

    anomalies.sort((a, b) => {
      const sevDiff =
        (severityOrder[(b.severity || "LOW").toUpperCase()] || 0) -
        (severityOrder[(a.severity || "LOW").toUpperCase()] || 0);

      if (sevDiff !== 0) return sevDiff;

      return extractAnomalyDate(b) - extractAnomalyDate(a);
    });

    latestAnomalies = anomalies;

    // ---------- Export Support ----------
    window.currentAnomalies = anomalies;

    // ---------- Toast Logic ----------
    let newAnomaliesBatch = [];
    let highestSeverity = "LOW";

    for (const row of anomalies) {
      const anomalyTime = extractAnomalyDate(row);

      if (!anomalyTime) continue;

      // Initial page load protection
      if (!initialAnomaliesLoadDone) {
        initialAnomaliesLoadDone = true;
        lastSeenDetectedAt = new Date();
        continue;
      }

      // Live-mode toast protection
      if (currentMode === "live") {
        if (anomalyTime <= PAGE_LOAD_TIME) continue;

        if (
          lastSeenDetectedAt &&
          anomalyTime <= lastSeenDetectedAt
        ) {
          continue;
        }
      }

      // Unique anomaly key
      const key =
        row.anomaly_id ||
        [
          safeGet(
            row,
            "detected_at",
            safeGet(row, "timestamp", "")
          ),
          safeGet(row, "host", ""),
          safeGet(
            row,
            "service",
            safeGet(row, "svc", "system")
          ),
          safeGet(row, "message", ""),
        ].join("|");

      // Skip already notified anomalies
      if (notifiedAnomalyKeys.has(key)) continue;

      const svc = safeGet(
        row,
        "service",
        safeGet(row, "svc", "system")
      );

      const msg = (
        safeGet(row, "message", "") || ""
      ).slice(0, 140);

      // Severity tracking
      const sev = safeGet(row, "severity", "LOW");

      if (sev === "HIGH") {
        highestSeverity = "HIGH";
      } else if (
        sev === "MEDIUM" &&
        highestSeverity !== "HIGH"
      ) {
        highestSeverity = "MEDIUM";
      }

      newAnomaliesBatch.push({
        svc,
        msg,
      });

      notifiedAnomalyKeys.add(key);

      lastSeenDetectedAt = anomalyTime;
    }

    // ---------- Persist notified keys ONCE ----------
    localStorage.setItem(
      "notifiedAnomalyKeys",
      JSON.stringify([...notifiedAnomalyKeys])
    );

    // ---------- Show Toast ----------
    if (newAnomaliesBatch.length > 0) {
      const count = newAnomaliesBatch.length;
      const sample = newAnomaliesBatch[0];

      showToast(
        `${count} new anomalies detected`,
        `${sample.svc}: ${sample.msg}`,
        highestSeverity === "HIGH"
          ? "error"
          : highestSeverity === "MEDIUM"
          ? "warning"
          : "info",
        7000
      );
    }

    // ---------- UI ----------
    renderTable(anomalies);
    updateChart(anomalies);
    updateServiceDonut(anomalies);

  } catch (err) {
    console.error("Anomalies fetch FULL error:", err);

    // Reset UI safely
    renderTable([]);
    updateChart([]);
    updateServiceDonut([]);

    const big = document.getElementById("bigNumber");

    if (big) {
      big.textContent = "0";
    }
  }
}



/* render table */
/* render table */
function renderTable(anomalies) {
  const tbody = document.querySelector("#anomaliesTable tbody");
  if (!tbody) {
    console.warn("No #anomaliesTable tbody found in DOM");
    return;
  }

  tbody.innerHTML = "";
  // -------------------------------
  // Defensive filtering
  // -------------------------------
const rows = Array.isArray(anomalies)
  ? anomalies.filter(r => r && typeof r === "object")
  : [];


  // ===============================
// SOC THREAT-BASED SORTING
// ===============================
rows.sort((a, b) => {

  const threatDiff =
    Number(b.threat_score || 0) -
    Number(a.threat_score || 0);

  // Higher threat first
  if (threatDiff !== 0) {
    return threatDiff;
  }

  // Newest timestamp first
  return new Date(b.timestamp) - new Date(a.timestamp);
});

updateDecisionAssistant(rows);

  // -------------------------------
  // Severity Counters (UPDATED)
  // -------------------------------
  let high = 0, medium = 0, low = 0;

  for (const a of rows) {
    let sev = (a.severity || "LOW").toUpperCase();

    let prob = parseFloat(
      safeGet(
        a,
        "prob_anomaly",
        safeGet(a, "probability", safeGet(a, "score", ""))
      )
    );

    if (!Number.isNaN(prob)) {
      severity = deriveSeverity(prob);
    }

    if (sev === "HIGH") high++;
    else if (sev === "MEDIUM") medium++;
    else low++;
  }

  document.getElementById("countHigh").textContent = high;
  document.getElementById("countMedium").textContent = medium;
  document.getElementById("countLow").textContent = low;

  // ===============================
  // THREAT LEVEL
  // ===============================
// ===============================
// THREAT LEVEL (Threat Score Based)
// ===============================
const threatEl = document.getElementById("threatLevel");

if (threatEl) {

const maxThreat = Math.max(
  ...rows.map(a => {

    const prob = Number(
      a.prob_anomaly ||
      a.probability ||
      a.score ||
      0
    );

    return prob * 100;
  }),
  0
);

  let level = "NORMAL";
  let className = "threat-normal";

if (high >= 30 && maxThreat >= 98){

    level = "CRITICAL";
    className = "threat-critical";

} else if (high >= 5 || maxThreat >= 85) {

    level = "HIGH";
    className = "threat-high";

} else if (medium >= 3 || maxThreat >= 60) {

    level = "ELEVATED";
    className = "threat-elevated";
}

  threatEl.textContent = level;
  threatEl.className = "stat-number " + className;
  // ===============================
// CRITICAL THREAT BANNER
// ===============================
const criticalBanner =
  document.getElementById("criticalThreatBanner");

if (criticalBanner) {

  if (maxThreat >= 100) {
    criticalBanner.classList.remove("hidden");

  } else {
    criticalBanner.classList.add("hidden");
  }
}
}

  // -------------------------------
  const toggleBtn = document.getElementById("toggleAnomaliesBtn");
  const countText = document.getElementById("anomalyCountText");

  if (rows.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="6" style="text-align:center;opacity:.7">
          No anomalies
        </td>
      </tr>`;

    if (toggleBtn) toggleBtn.style.display = "none";
    if (countText) countText.textContent = "";

    if (threatEl) {
      threatEl.textContent = "NORMAL";
      threatEl.className = "stat-number threat-normal";
    }

    return;
  }

  const rowsToRender = anomaliesExpanded
    ? rows
    : rows.slice(0, COLLAPSED_LIMIT);

  if (toggleBtn) {
    toggleBtn.style.display =
      rows.length > COLLAPSED_LIMIT ? "inline-flex" : "none";
  }

  if (countText) {
    countText.textContent =
      `Showing ${rowsToRender.length} of ${rows.length} anomalies`;
  }

  // -------------------------------
  // Render rows
  // -------------------------------
for (const a of rowsToRender) {

  const tr = document.createElement("tr");

  let anomalyId = "unknown";

  try {

    anomalyId = generateAnomalyId(a);


  } catch (err) {

    console.error("generateAnomalyId FAILED:", err, a);

    continue;
  }

  tr.setAttribute("data-id", anomalyId);  // ✅ THEN use

    // -------------------------------
    // Probability (MOVE UP)
    // -------------------------------
    let prob = parseFloat(
      safeGet(
        a,
        "prob_anomaly",
        safeGet(a, "probability", safeGet(a, "score", ""))
      )
    );

    if (Number.isNaN(prob)) prob = null;

    // -------------------------------
    // Severity (UPDATED)
    // -------------------------------
    let severity = (a.severity || "LOW").toUpperCase();

    if (prob !== null) {
      severity = deriveSeverity(prob);
    }

    // -------------------------------
    // Row highlight
    // -------------------------------
if (severity === "CRITICAL") {
  tr.classList.add("sev-critical-row");

} else if (severity === "HIGH") {
  tr.classList.add("sev-high-row");

} else if (severity === "MEDIUM") {
  tr.classList.add("sev-medium-row");

} else {
  tr.classList.add("sev-low-row");
}

    // -------------------------------
    const severityBadge = `
      <span class="severity-badge sev-${severity.toLowerCase()}">
        ${severity}
      </span>
    `;

    // ===============================
    // STATUS LOGIC
    // ===============================
    let status = "NEW";

    if (actionsMap && actionsMap[anomalyId]) {
      status = actionsMap[anomalyId].status.toUpperCase();
    }

    const statusBadge = `
      <span class="status-badge status-${status.toLowerCase()}">
        ${status}
      </span>
    `;

    // -------------------------------
    // Actions
    // -------------------------------
    let actionHtml = "";

    const currentStatus = actionsMap?.[anomalyId]?.status;
    const currentComment = actionsMap?.[anomalyId]?.comment || "";

    if (currentStatus === "closed") {
      tr.classList.add("row-closed");

      actionHtml = `
        <div class="action-group">
          <div class="comment-text" title="${currentComment}">
            ${currentComment || "—"}
          </div>
          <button class="ack-btn done" disabled>Closed</button>
        </div>
      `;
    }
    else if (currentStatus === "acknowledged") {
      tr.classList.add("row-ack");

      actionHtml = `
        <div class="action-group">
          <div class="comment-text" title="${currentComment}">
            ${currentComment || "—"}
          </div>
          <button class="ack-btn done" disabled>Acknowledged</button>
          <button class="close-btn"
            onclick="closeAnomaly('${anomalyId}', this); logFeedback('${anomalyId}', 'closed')">
            Close
          </button>
        </div>
      `;
    }
    else {
      tr.classList.add("row-new");

      actionHtml = `
        <div class="action-group">
          <input 
            type="text"
            class="comment-input"
            placeholder="Add note..."
            id="comment-${anomalyId}"
          />
          
          <button type="button" class="ack-btn"
            onclick="acknowledgeAnomaly('${anomalyId}', this, this.previousElementSibling.value); logFeedback('${anomalyId}', 'acknowledged')">
            Acknowledge
          </button>
          
          <button type="button" class="fp-btn"
            onclick="markFalsePositive('${anomalyId}', this); logFeedback('${anomalyId}', 'false_positive')">
            False Positive
          </button>
        </div>
      `;
    }

    // -------------------------------
    // Probability badge
    // -------------------------------
    let probBadge = `<span class="badge-prob badge-low">-</span>`;

    if (prob !== null) {
      const percent = (prob * 100).toFixed(1) + "%";

      if (prob >= 0.8) {
        probBadge = `<span class="badge-prob badge-high">${percent}</span>`;
      } else if (prob >= 0.6) {
        probBadge = `<span class="badge-prob badge-mid">${percent}</span>`;
      } else {
        probBadge = `<span class="badge-prob badge-low">${percent}</span>`;
      }
    }

    // -------------------------------
    const ts   = safeGet(a, "detected_at", safeGet(a, "timestamp", ""));
    const host = safeGet(a, "host", "");
    const svc  = safeGet(a, "service", safeGet(a, "svc", ""));
    const msg  = (safeGet(a, "message", "") || "").replace(/\n/g, " ");

    // -------------------------------
    tr.innerHTML = `
      <td>${escapeHtml(ts)}</td>
      <td>${escapeHtml(host)}</td>
      <td class="col-service">${escapeHtml(svc)}</td>
      <td>${severityBadge}</td>
      <td class="col-message" style="max-width:600px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;"
          title="${escapeHtml(msg)}">
        ${escapeHtml(msg)}
      </td>
      <td class="col-prob">${probBadge}</td>
      <td>${statusBadge}</td>
      <td>${actionHtml}</td>
    `;

    tbody.appendChild(tr);


tr.addEventListener("click", () => {

  try {

    // Remove previous selected row
    document.querySelectorAll(".selected-anomaly-row")
      .forEach(r => {
        r.classList.remove("selected-anomaly-row");
      });

    // Highlight current row
    tr.classList.add("selected-anomaly-row");

    // ----------------------------
    // Extract rendered status text
    // ----------------------------
    const tempStatus = document.createElement("div");
    tempStatus.innerHTML = statusBadge || "";

    const extractedStatus =
      (tempStatus.textContent || "").trim() || "NEW";

    // ----------------------------
    // Extract rendered action text
    // ----------------------------
    const tempAction = document.createElement("div");
    tempAction.innerHTML = actionHtml || "";

    const extractedAction =
      (tempAction.textContent || "").trim() || "-";

    // ----------------------------
    // Final panel object
    // ----------------------------
    const panelData = {
      ...a,

      status: extractedStatus,
      analyst_action: extractedAction
    };

    // ----------------------------
    // Open investigation panel
    // ----------------------------
    if (typeof showAnalystPanel === "function") {
      showAnalystPanel(panelData);
    } else {
      console.error("showAnalystPanel function not found");
    }

  } catch (err) {

    console.error("ROW CLICK ERROR:", err);

  }

});
  }
}


function addDetectionFactor(factorsMap, text, priority = 50, category = "general") {
  const existing = factorsMap.get(category);

  if (!existing || priority > existing.priority) {
    factorsMap.set(category, {
      text,
      priority,
      category
    });
  }
}

function generateDetectionFactors(a) {

  const factorsMap = new Map();

  const msg =
    (
      a.message ||
      ""
    ).toLowerCase();


  

  const prob =
    Number(
      a.prob_anomaly ||
      a.probability ||
      a.score ||
      0
    );

    const severity =
(a.severity || "LOW").toUpperCase();

//
// CENTRAL THREAT CONTEXT
//

const threatContext = {

  authentication: (
    msg.includes("failed password") ||
    msg.includes("authentication failed") ||
    msg.includes("invalid user")
  ),

  privilege: (
    msg.includes("sudo") ||
    msg.includes("root") ||
    msg.includes("privilege escalation")
  ),

  reconnaissance: (
    msg.includes("scan") ||
    msg.includes("nmap") ||
    msg.includes("recon")
  ),

  persistence: (
    msg.includes("cron") ||
    msg.includes("scheduled")
  ),

  execution: (
    msg.includes("bash") ||
    msg.includes("powershell") ||
    msg.includes("cmd") ||
    msg.includes("script")
  ),

  correlated:
    a.correlation_triggered === true,

  critical:
    severity === "CRITICAL",

  highSeverity:
  severity === "HIGH" ||
  severity === "CRITICAL",

accessPhase: (
  msg.includes("failed password") ||
  msg.includes("authentication failed") ||
  msg.includes("invalid user")
),

escalationPhase: (
  msg.includes("sudo") ||
  msg.includes("privilege escalation") ||
  msg.includes("root")
),

persistencePhase: (
  msg.includes("cron") ||
  msg.includes("scheduled")
),

reconPhase: (
  msg.includes("scan") ||
  msg.includes("recon") ||
  msg.includes("nmap")
)

};

  // ======================================
  // PROBABILITY BASED
  // ======================================

  if (prob >= 0.90) {

    addDetectionFactor(
  factorsMap,
  "Extremely high anomaly probability detected",
  100,
  "critical_confidence"
);

  }
  else if (prob >= 0.75) {

    addDetectionFactor(
  factorsMap,
  "High anomaly confidence score",
  90,
  "confidence"
);

  }


  //
// SSH / AUTHENTICATION INTELLIGENCE
//

if (
  threatContext.authentication ||
  msg.includes("brute force") ||
  a.service?.toLowerCase().includes("ssh")
) {

  addDetectionFactor(
    factorsMap,
    "Authentication-related activity deviates from expected behavioral patterns",
    88,
    "authentication_behavior"
  );

  addDetectionFactor(
    factorsMap,
    "Observed indicators align with potential credential-access or brute-force activity",
    92,
    "credential_access"
  );

  if (a.prob_anomaly >= 0.8) {

    addDetectionFactor(
      factorsMap,
      "High-confidence authentication anomaly suggests elevated compromise risk",
      97,
      "authentication_risk"
    );

  }

  if (threatContext.correlated) {

    addDetectionFactor(
      factorsMap,
      "Repeated authentication anomalies triggered behavioral correlation escalation",
      99,
      "behavioral_correlation"
    );

  }

}

//
// MITRE-AWARE RECONNAISSANCE INTELLIGENCE
//

if (
  threatContext.reconnaissance ||
  msg.includes("port sweep")
) {

  addDetectionFactor(
    factorsMap,
    "Observed behavior aligns with MITRE ATT&CK Active Scanning reconnaissance patterns",
    93,
    "mitre_reconnaissance"
  );

  addDetectionFactor(
    factorsMap,
    "Network probing activity suggests hostile reconnaissance or attack surface enumeration",
    88,
    "recon_behavior"
  );

}

//
// MITRE-AWARE PRIVILEGE ESCALATION
//

if (
  threatContext.privilege ||
  msg.includes("root access")
) {

  addDetectionFactor(
    factorsMap,
    "Behavior aligns with privilege escalation activity associated with ATT&CK T1548 techniques",
    95,
    "mitre_privilege_escalation"
  );

  addDetectionFactor(
    factorsMap,
    "Elevated privilege activity deviates from expected operational patterns",
    84,
    "privilege_behavior"
  );

}

//
// MITRE-AWARE EXECUTION INTELLIGENCE
//

if (
  msg.includes("bash") ||
  msg.includes("powershell") ||
  msg.includes("cmd") ||
  msg.includes("script")
) {

  addDetectionFactor(
    factorsMap,
    "Command execution behavior aligns with ATT&CK scripting interpreter techniques",
    90,
    "mitre_execution"
  );

  addDetectionFactor(
    factorsMap,
    "Observed execution patterns may indicate unauthorized scripted activity",
    82,
    "execution_behavior"
  );

}


//
// BEHAVIORAL CORRELATION INTELLIGENCE
//

if (a.correlation_triggered) {

  const activeCount =
    Number(a.active_event_count || 0);

  addDetectionFactor(
    factorsMap,
    "Behavioral correlation engine identified repeated suspicious activity within the configured observation window",
    98,
    "behavioral_detection"
  );

  if (activeCount >= 3) {

    addDetectionFactor(
      factorsMap,
      `Multiple correlated suspicious events detected (${activeCount} related events observed)`,
      96,
      "multi_event_activity"
    );

  }

  if (activeCount >= 5) {

    addDetectionFactor(
      factorsMap,
      "Sustained hostile behavioral patterns indicate elevated likelihood of active compromise progression",
      100,
      "critical_attack_progression"
    );

  }

  if (a.escalation_reason) {

    addDetectionFactor(
      factorsMap,
      `Escalation rationale: ${a.escalation_reason}`,
      94,
      "escalation_reasoning"
    );

  }

}


  // ======================================
  // AUTHENTICATION ATTACKS
  // ======================================

  if (
    msg.includes("failed") ||
    msg.includes("login") ||
    msg.includes("password")
  ) {

    addDetectionFactor(
  factorsMap,
  "Suspicious authentication activity detected",
  85,
  "authentication"
);

  }

  // ======================================
  // SERVICE ANOMALIES
  // ======================================

  if (
    msg.includes("error") ||
    msg.includes("exception") ||
    msg.includes("crash")
  ) {

    addDetectionFactor(
  factorsMap,
  "Abnormal service behavior observed",
  70,
  "service_behavior"
);

  }

  // ======================================
  // NETWORK ANOMALIES
  // ======================================

  if (
    msg.includes("arp") ||
    msg.includes("scan") ||
    msg.includes("flood")
  ) {

    addDetectionFactor(
  factorsMap,
  "Potential network reconnaissance activity",
  80,
  "reconnaissance"
);

  }


//
// SEVERITY-AWARE NARRATIVE INTELLIGENCE


if (severity === "LOW") {

  addDetectionFactor(
    factorsMap,
    "Observed anomaly currently reflects low-confidence deviation from established behavioral baseline",
    40,
    "severity_narrative"
  );

}

else if (severity === "MEDIUM") {

  addDetectionFactor(
    factorsMap,
    "Anomalous behavior demonstrates moderate deviation requiring additional contextual validation",
    65,
    "severity_narrative"
  );

}

else if (severity === "HIGH") {

  addDetectionFactor(
    factorsMap,
    "Elevated anomaly severity indicates increased likelihood of malicious or unauthorized operational activity",
    90,
    "severity_narrative"
  );

}

else if (severity === "CRITICAL") {

  addDetectionFactor(
    factorsMap,
    "Critical threat conditions suggest sustained hostile activity requiring immediate incident-response escalation",
    100,
    "severity_narrative"
  );

}


//
// CONTEXTUAL THREAT NARRATIVE
//

if (
  a.correlation_triggered &&
  severity === "HIGH"
) {

  addDetectionFactor(
    factorsMap,
    "Correlated high-severity activity suggests coordinated attack progression rather than isolated anomalous behavior",
    97,
    "attack_progression"
  );

}

if (
  a.correlation_triggered &&
  severity === "CRITICAL"
) {

  addDetectionFactor(
    factorsMap,
    "Sustained correlated threat activity indicates possible active compromise lifecycle progression within the monitored environment",
    100,
    "critical_attack_lifecycle"
  );

}

if (
  msg.includes("failed password") &&
  msg.includes("root")
) {

  addDetectionFactor(
    factorsMap,
    "Privileged account targeting behavior suggests elevated adversarial intent against critical authentication assets",
    96,
    "privileged_targeting"
  );

}

if (
  msg.includes("sudo") &&
  severity === "HIGH"
) {

  addDetectionFactor(
    factorsMap,
    "Elevated privilege operations combined with anomalous execution patterns may indicate attempted privilege abuse",
    94,
    "privilege_abuse"
  );

}

if (
  msg.includes("scan") &&
  severity !== "LOW"
) {

  addDetectionFactor(
    factorsMap,
    "Reconnaissance behavior observed prior to elevated anomaly escalation may indicate attack staging activity",
    91,
    "recon_attack_staging"
  );

}

//
// OPERATIONAL THREAT CONTEXT INTELLIGENCE
//

if (
  msg.includes("root") ||
  msg.includes("administrator")
) {

  addDetectionFactor(
    factorsMap,
    "Activity targeting privileged authentication assets increases potential operational impact severity",
    95,
    "privileged_asset_risk"
  );

}

if (
  msg.includes("ssh") &&
  a.correlation_triggered
) {

  addDetectionFactor(
    factorsMap,
    "Repeated remote authentication anomalies may indicate active external access attempts against exposed services",
    97,
    "remote_access_threat"
  );

}

if (
  msg.includes("cron") ||
  msg.includes("scheduled")
) {

  addDetectionFactor(
    factorsMap,
    "Unexpected scheduled-task behavior may indicate persistence establishment attempts",
    90,
    "persistence_risk"
  );

}

if (
  msg.includes("sudo") ||
  msg.includes("privilege escalation")
) {

  addDetectionFactor(
    factorsMap,
    "Privilege-related anomalous behavior may enable expanded attacker control across affected systems",
    94,
    "operational_privilege_risk"
  );

}

if (
  msg.includes("scan") ||
  msg.includes("nmap")
) {

  addDetectionFactor(
    factorsMap,
    "Reconnaissance activity may represent pre-exploitation mapping of accessible network resources",
    88,
    "pre_attack_recon"
  );

}

if (
  severity === "CRITICAL"
) {

  addDetectionFactor(
    factorsMap,
    "Critical threat severity combined with correlated behavioral indicators warrants immediate containment assessment",
    100,
    "incident_response_context"
  );

}


//
// TEMPORAL ESCALATION INTELLIGENCE
//

const activeEvents =
  Number(a.active_event_count || 0);

if (activeEvents >= 2) {

  addDetectionFactor(
    factorsMap,
    `Repeated suspicious activity observed across ${activeEvents} correlated events within the active monitoring window`,
    92,
    "temporal_activity"
  );

}

if (activeEvents >= 4) {

  addDetectionFactor(
    factorsMap,
    "Escalating anomaly frequency suggests sustained adversarial interaction with monitored services",
    96,
    "temporal_escalation"
  );

}

if (activeEvents >= 6) {

  addDetectionFactor(
    factorsMap,
    "Extended sequence of correlated hostile events indicates persistent attack lifecycle progression",
    100,
    "persistent_attack_activity"
  );

}

if (
  activeEvents >= 3 &&
  threatContext.highSeverity
) {

  addDetectionFactor(
    factorsMap,
    "High-severity anomalies persisting across multiple behavioral observations increase confidence in malicious intent",
    97,
    "high_confidence_persistence"
  );

}

if (
  activeEvents >= 5 &&
  threatContext.critical
){

  addDetectionFactor(
    factorsMap,
    "Critical anomaly persistence suggests active compromise conditions requiring immediate containment validation",
    100,
    "critical_persistence"
  );

}



//
// CONFIDENCE-AWARE NARRATIVE CALIBRATION
//

if (prob >= 0.95) {

  addDetectionFactor(
    factorsMap,
    "Anomaly confidence exceeds critical detection threshold, significantly increasing likelihood of genuine malicious activity",
    100,
    "confidence_calibration"
  );

}

else if (prob >= 0.85) {

  addDetectionFactor(
    factorsMap,
    "Elevated anomaly confidence indicates strong deviation from established behavioral baselines",
    92,
    "confidence_calibration"
  );

}

else if (prob >= 0.70) {

  addDetectionFactor(
    factorsMap,
    "Observed activity demonstrates moderate statistical deviation requiring contextual investigation",
    72,
    "confidence_calibration"
  );

}

else if (prob >= 0.50) {

  addDetectionFactor(
    factorsMap,
    "Low-confidence anomaly indicators suggest possible early-stage or weakly correlated abnormal behavior",
    55,
    "confidence_calibration"
  );

}

//
// INVESTIGATION GUIDANCE INTELLIGENCE
//

if (
  threatContext.highSeverity
) {

  addDetectionFactor(
    factorsMap,
    "Observed threat characteristics warrant prioritized analyst investigation due to elevated operational risk",
    94,
    "investigation_priority"
  );

}

if (
  threatContext.correlated
){

  addDetectionFactor(
    factorsMap,
    "Correlated behavioral indicators increase importance of timeline-based forensic review",
    95,
    "forensic_guidance"
  );

}

if (
  msg.includes("failed password") ||
  msg.includes("invalid user")
) {

  addDetectionFactor(
    factorsMap,
    "Authentication anomaly patterns warrant focused review of remote access telemetry and account activity",
    90,
    "authentication_review"
  );

}

if (
  msg.includes("sudo") ||
  msg.includes("root")
) {

  addDetectionFactor(
    factorsMap,
    "Privilege-related anomaly indicators justify validation of authorization boundaries and elevated session activity",
    92,
    "privilege_review"
  );

}

if (
  msg.includes("scan") ||
  msg.includes("nmap")
) {

  addDetectionFactor(
    factorsMap,
    "Reconnaissance indicators suggest value in reviewing adjacent network telemetry for lateral probing activity",
    88,
    "network_review"
  );

}

//
// MULTI-SIGNAL THREAT FUSION
//

// const authIndicators =
//threatContext.authentication;

// const privilegeIndicators =
//   threatContext.privilege;

// const reconIndicators =
//   threatContext.reconnaissance;

// const persistenceIndicators =
//   threatContext.persistence;

//
// AUTH + PRIVILEGE
//

if (
  threatContext.accessPhase &&
  threatContext.escalationPhase
) {

  addDetectionFactor(
    factorsMap,
    "Authentication anomalies combined with privilege-related activity may indicate attempted post-compromise escalation behavior",
    99,
    "fusion_auth_privilege"
  );

}

//
// RECON + PERSISTENCE
//

if (
  threatContext.reconPhase &&
  threatContext.persistencePhase
) {

  addDetectionFactor(
    factorsMap,
    "Reconnaissance behavior combined with persistence-oriented activity suggests structured attack lifecycle progression",
    97,
    "fusion_recon_persistence"
  );

}

//
// CORRELATION + CRITICAL
//

if (
  threatContext.correlated &&
  threatContext.critical
) {

  addDetectionFactor(
    factorsMap,
    "Critical correlated threat indicators strongly suggest coordinated hostile activity rather than isolated anomalous events",
    100,
    "fusion_critical_correlation"
  );

}

//
// EXECUTION + PRIVILEGE
//

if (
  (
    msg.includes("bash") ||
    msg.includes("powershell") ||
    msg.includes("cmd")
  ) &&
  threatContext.escalationPhase
) {

  addDetectionFactor(
    factorsMap,
    "Privileged execution activity combined with anomalous scripting behavior may indicate active attacker operations",
    98,
    "fusion_execution_privilege"
  );

}


//
// ADVERSARIAL INTENT INFERENCE
//

//
// CREDENTIAL ACCESS INTENT
//

if (
  threatContext.accessPhase &&
  (
    severity === "HIGH" ||
    severity === "CRITICAL"
  )
) {

  addDetectionFactor(
    factorsMap,
    "Behavioral indicators suggest probable credential-access objectives targeting authentication infrastructure",
    96,
    "intent_credential_access"
  );

}

//
// PRIVILEGE CONTROL INTENT
//

if (
  threatContext.escalationPhase &&
  threatContext.correlated
) {

  addDetectionFactor(
    factorsMap,
    "Correlated privilege-related anomalies may indicate attempted expansion of attacker control within the environment",
    98,
    "intent_privilege_control"
  );

}

//
// RECONNAISSANCE INTENT
//

if (
  threatContext.reconPhase &&
  activeEvents >= 3
) {

  addDetectionFactor(
    factorsMap,
    "Sustained reconnaissance-oriented behavior suggests active environmental discovery or attack surface mapping objectives",
    94,
    "intent_reconnaissance"
  );

}

//
// PERSISTENCE INTENT
//

if (
  threatContext.persistencePhase &&
  severity !== "LOW"
) {

  addDetectionFactor(
    factorsMap,
    "Persistence-oriented anomalous behavior may indicate attempts to maintain long-term unauthorized system access",
    95,
    "intent_persistence"
  );

}

//
// ACTIVE OPERATIONAL STAGING
//

if (
  threatContext.accessPhase &&
  threatContext.escalationPhase &&
  threatContext.correlated
) {

  addDetectionFactor(
    factorsMap,
    "Combined authentication, privilege, and behavioral escalation indicators suggest coordinated adversarial operational staging activity",
    100,
    "intent_operational_staging"
  );

}


//
// EVIDENTIARY LANGUAGE CALIBRATION
//

if (
  severity === "LOW" &&
  prob < 0.60
) {

  addDetectionFactor(
    factorsMap,
    "Current anomaly indicators remain weakly correlated and should be interpreted as preliminary behavioral deviations pending additional telemetry",
    45,
    "evidentiary_low_confidence"
  );

}

if (
  severity === "MEDIUM"
) {

  addDetectionFactor(
    factorsMap,
    "Observed anomaly characteristics demonstrate sufficient behavioral deviation to justify contextual investigation, though direct malicious intent remains unconfirmed",
    70,
    "evidentiary_moderate_confidence"
  );

}

if (
  severity === "HIGH" &&
  prob >= 0.85
) {

  addDetectionFactor(
    factorsMap,
    "Multiple converging anomaly indicators substantially increase confidence that the observed behavior reflects genuine hostile or unauthorized operational activity",
    96,
    "evidentiary_high_confidence"
  );

}

if (
  severity === "CRITICAL" &&
  a.correlation_triggered
) {

  addDetectionFactor(
    factorsMap,
    "Correlated critical-severity telemetry provides strong evidentiary support for active compromise assessment and immediate containment validation",
    100,
    "evidentiary_critical_compromise"
  );

}

//
// ATTACK LIFECYCLE SEQUENCING
//

//
// RECON → ACCESS
//

if (
  threatContext.reconPhase &&
  threatContext.accessPhase
) {

  addDetectionFactor(
    factorsMap,
    "Reconnaissance-oriented activity followed by authentication anomalies may indicate transition from discovery into active access attempts",
    97,
    "lifecycle_recon_to_access"
  );

}

//
// ACCESS → PRIVILEGE
//

if (
  threatContext.accessPhase &&
  threatContext.escalationPhase
) {

  addDetectionFactor(
    factorsMap,
    "Authentication-related anomalies combined with privilege-focused activity suggest potential post-access escalation progression",
    98,
    "lifecycle_access_to_privilege"
  );

}

//
// PRIVILEGE → PERSISTENCE
//

if (
  threatContext.escalationPhase &&
  threatContext.persistencePhase
) {

  addDetectionFactor(
    factorsMap,
    "Privilege-oriented activity followed by persistence-related behavior may indicate attempts to establish durable unauthorized access",
    99,
    "lifecycle_privilege_to_persistence"
  );

}

//
// CORRELATED MULTI-STAGE ACTIVITY
//

if (
  threatContext.correlated &&
  activeEvents >= 5
) {

  addDetectionFactor(
    factorsMap,
    "Sustained correlated anomalies across multiple behavioral domains suggest progression through multiple attack lifecycle stages",
    100,
    "lifecycle_multi_stage_attack"
  );

}

//
// CRITICAL ACTIVE COMPROMISE
//

if (
  threatContext.critical &&
  (
    threatContext.accessPhase ||
    threatContext.escalationPhase
  ) &&
  threatContext.correlated
){

  addDetectionFactor(
    factorsMap,
    "Critical correlated access and privilege indicators may reflect active compromise progression requiring immediate containment assessment",
    100,
    "lifecycle_active_compromise"
  );

}

//
// CENTRALIZED THREAT CONTEXT ESCALATION
//

if (
  threatContext.accessPhase &&
  threatContext.escalationPhase &&
  threatContext.correlated
) {

  addDetectionFactor(
    factorsMap,
    "Centralized threat analysis identified converging authentication, privilege, and correlation indicators consistent with escalating adversarial activity",
    100,
    "contextual_attack_escalation"
  );

}

if (
  threatContext.reconnaissance &&
  threatContext.authentication
) {

  addDetectionFactor(
    factorsMap,
    "Threat-context correlation suggests reconnaissance behavior transitioned into active authentication targeting activity",
    98,
    "contextual_recon_to_access"
  );

}

if (
  threatContext.persistence &&
  threatContext.privilege
) {

  addDetectionFactor(
    factorsMap,
    "Persistence-oriented activity combined with elevated privilege indicators may reflect attempts to maintain durable unauthorized control",
    99,
    "contextual_persistence_control"
  );

}


  // ======================================
  // FALLBACK
  // ======================================

 if (factorsMap.size === 0)  {

    addDetectionFactor(
  factorsMap,
  "Behavior deviated from learned normal baseline",
  60,
  "baseline_deviation"
);

  }

const prioritizedFactors =
  [...factorsMap.values()]
    .sort((a, b) => b.priority - a.priority);

const criticalCategories = [
  "critical_attack_progression",
  "critical_attack_lifecycle",
  "behavioral_detection",
  "attack_progression",
  "credential_access",
  "privileged_targeting"
];



const semanticGroups = {

  authentication: [
    "authentication",
    "credential",
    "remote_access"
  ],

  escalation: [
    "privilege",
    "critical_attack",
    "attack_progression"
  ],

  reconnaissance: [
    "recon",
    "network_review",
    "pre_attack"
  ],

  persistence: [
    "persistence",
    "scheduled",
    "temporal"
  ]

};

function belongsToSemanticGroup(category, group) {

  return semanticGroups[group]
    .some(keyword =>
      category.includes(keyword)
    );

}

const selectedFactors = [];

// Always preserve critical intelligence first
for (const factor of prioritizedFactors) {

  if (
    criticalCategories.includes(factor.category)
  ) {
    selectedFactors.push(factor);
  }

}

// Fill remaining slots
for (const factor of prioritizedFactors) {

  if (
    selectedFactors.length >= 6
  ) break;

const alreadyCovered =
  selectedFactors.some(existing => {

    if (
      existing.category === factor.category
    ) {
      return true;
    }

    return Object.keys(semanticGroups)
      .some(group => {

        return (
          belongsToSemanticGroup(existing.category, group) &&
          belongsToSemanticGroup(factor.category, group)
        );

      });

  });

if (!alreadyCovered){
    selectedFactors.push(factor);
  }

}

return selectedFactors
  .slice(0, 6)
  .map(f => {

    let factorClass = "factor-item";

    if (
      f.priority >= 100
    ) {
      factorClass += " factor-critical";
    }

    else if (
      f.priority >= 95
    ) {
      factorClass += " factor-high";
    }

    else if (
      f.priority >= 85
    ) {
      factorClass += " factor-medium";
    }

    if (
      f.category.includes("mitre")
    ) {
      factorClass += " factor-mitre";
    }

    if (
      f.category.includes("behavioral") ||
      f.category.includes("correlation")
    ) {
      factorClass += " factor-correlation";
    }

    return `
      <div class="${factorClass}">
        ⚠ ${escapeHtml(f.text)}
      </div>
    `;

  })
  .join("");

}

//=================================

function generateMitreMapping(a) {

  const msg =
    (
      a.message ||
      ""
    ).toLowerCase();

  const mappings = [];

  // ======================================
  // SSH / BRUTE FORCE
  // ======================================

  if (
    msg.includes("failed password") ||
    msg.includes("authentication failed") ||
    msg.includes("brute force")
  ) {

    mappings.push({
      tactic: "Credential Access",
      technique: "Brute Force",
      technique_id: "T1110"
    });

  }

  // ======================================
  // NETWORK SCANNING
  // ======================================

  if (
    msg.includes("scan") ||
    msg.includes("recon") ||
    msg.includes("arp")
  ) {

    mappings.push({
      tactic: "Reconnaissance",
      technique: "Active Scanning",
      technique_id: "T1595"
    });

  }

  // ======================================
  // PRIVILEGE ESCALATION
  // ======================================

  if (
    msg.includes("sudo") ||
    msg.includes("root") ||
    msg.includes("privilege")
  ) {

    mappings.push({
      tactic: "Privilege Escalation",
      technique: "Abuse Elevation Control Mechanism",
      technique_id: "T1548"
    });

  }

  // ======================================
  // EXECUTION
  // ======================================

  if (
    msg.includes("process") ||
    msg.includes("execution") ||
    msg.includes("binary")
  ) {

    mappings.push({
      tactic: "Execution",
      technique: "Command and Scripting Interpreter",
      technique_id: "T1059"
    });

  }

  return mappings;

}






//--------------------------------------------

//==========================================
 function generateRecommendations(a) {
  
  const recommendations = [];

function addRecommendation(
  text,
  priority = 50,
  category = "general"
) {

  recommendations.push({
    text,
    priority,
    category
  });

}

  const msg =
    (
      a.message ||
      ""
    ).toLowerCase();

  const severity =
    (
      a.severity ||
      "LOW"
    ).toUpperCase();

  const service =
    (
      a.service ||
      a.svc ||
      ""
    ).toLowerCase();

  const status =
    (
      a.status ||
      ""
    ).toUpperCase();

  const prob =
    Number(
      a.prob_anomaly ||
      a.probability ||
      a.score ||
      0
    );

  const recommendationContext = {

  critical:
    severity === "CRITICAL",

  highSeverity:
    severity === "HIGH" ||
    severity === "CRITICAL",

  correlated:
  a.correlation_triggered === true ||
  a.correlation_triggered === "true",

  accessPhase: (
    msg.includes("failed password") ||
    msg.includes("authentication failed") ||
    msg.includes("invalid user")
  ),

  escalationPhase: (
    msg.includes("sudo") ||
    msg.includes("privilege escalation") ||
    msg.includes("root")
  ),

  persistencePhase: (
    msg.includes("cron") ||
    msg.includes("scheduled")
  ),

  reconPhase: (
    msg.includes("scan") ||
    msg.includes("recon") ||
    msg.includes("nmap")
  )

};

  // ======================================
  // CLOSED CASES
  // ======================================

  if (status === "CLOSED") {

    addRecommendation(
      "Incident already resolved by analyst workflow"
    );

    addRecommendation(
      "Maintain monitoring for anomaly recurrence"
    );

  }

  // ======================================
  // HIGH SEVERITY
  // ======================================

if (recommendationContext.highSeverity) {
  
addRecommendation(
  "Prioritize investigation due to elevated threat severity and validate whether the activity indicates active compromise behavior",
  95,
  "severity_escalation"
);

addRecommendation(
  "Correlate related anomalies, affected hosts, and recent behavioral activity to determine potential attack scope",
  90,
  "correlation"
);

}
if (recommendationContext.critical){

addRecommendation(
  "Immediate incident response escalation recommended due to sustained or highly correlated malicious activity",
  100,
  "incident_response"
);

addRecommendation(
  "Investigate potential active compromise, lateral movement, or coordinated attack behavior across affected systems",
  98,
  "compromise_analysis"
);

addRecommendation(
  "Consider containment actions, endpoint isolation, and rapid forensic validation to limit potential impact",
  96,
  "containment"
);

}


  // ======================================
  // SSH / AUTHENTICATION
  // ======================================

if (
  recommendationContext.accessPhase
){

addRecommendation(
  "Investigate repeated authentication failures and correlate source IP activity for potential brute-force behavior",
  92,
  "authentication"
);

addRecommendation(
  "Review impacted accounts and validate whether credential compromise indicators are present",
  88,
  "credential_compromise"
);

addRecommendation(
  "Validate authentication logs, session anomalies, and privilege escalation attempts associated with the affected system",
  84,
  "session_analysis"
);

  }

  // ======================================
  // DATABASE RELATED
  // ======================================

  if (
    service.includes("db") ||
    service.includes("mysql") ||
    service.includes("postgres")
  ) {

addRecommendation(
  "Investigate abnormal database access patterns and review privileged query activity for potential misuse or unauthorized access",
  90,
  "database_access"
);

addRecommendation(
  "Validate database service integrity, uptime stability, and recent configuration or permission changes",
  82,
  "database_integrity"
);

  }

  // ======================================
  // WEB / HTTP SERVICES
  // ======================================

  if (
    service.includes("http") ||
    service.includes("apache") ||
    service.includes("nginx")
  ) {

addRecommendation(
  "Investigate abnormal web application behavior and review HTTP/server logs for suspicious request patterns or attack indicators",
  88,
  "web_threat_analysis"
);

addRecommendation(
  "Validate recent deployments, configuration changes, and traffic anomalies that may have contributed to service instability",
  80,
  "deployment_validation"
);

  }

  // ======================================
  // HDFS / DISTRIBUTED SYSTEMS
  // ======================================

  if (
    service.includes("hdfs")
  ) {

    addRecommendation(
      "Monitor distributed node synchronization behavior"
    );

    addRecommendation(
      "Validate cluster communication consistency"
    );

    addRecommendation(
      "Observe anomaly recurrence across nodes"
    );

  }

  // ======================================
// CRON / SCHEDULED TASKS
// ======================================

if (
  recommendationContext.persistencePhase
) {

addRecommendation(
  "Investigate unusual scheduled task behavior and review recent cron activity for unauthorized persistence or execution patterns",
  87,
  "persistence"
);

addRecommendation(
  "Validate recently modified scheduled jobs, execution frequency anomalies, and privilege context associated with recurring tasks",
  82,
  "scheduled_task_validation"
);

}

// ======================================
// SENDMAIL / MAIL SERVICES
// ======================================

if (
  service.includes("sendmail") ||
  service.includes("smtp") ||
  service.includes("mail")
) {

addRecommendation(
  "Review outbound mail activity and inspect for abnormal relay behavior, phishing distribution patterns, or spam-related anomalies",
  88,
  "mail_abuse"
);

addRecommendation(
  "Validate mail service configuration integrity and investigate unusual message delivery spikes or authentication failures",
  80,
  "mail_configuration"
);

}

// ======================================
// SUDO / PRIVILEGE ESCALATION
// ======================================

if (
  recommendationContext.escalationPhase
){

addRecommendation(
  "Investigate potential privilege escalation behavior and review elevated command execution activity across affected systems",
  95,
  "privilege_escalation"
);

addRecommendation(
  "Validate administrative access patterns, account authorization scope, and suspicious privileged operations",
  90,
  "privileged_access_review"
);

}

// ======================================
// PROCESS / EXECUTION ANOMALIES
// ======================================

if (
  msg.includes("execution") ||
  msg.includes("process") ||
  msg.includes("binary") ||
  msg.includes("spawn")
) {

addRecommendation(
  "Review suspicious process execution behavior and investigate unexpected binary launches or abnormal parent-child process relationships",
  92,
  "execution_analysis"
);

addRecommendation(
  "Correlate execution activity with recent authentication events, privilege escalation attempts, or persistence indicators",
  88,
  "execution_correlation"
);

}

// ======================================
// FILE / INTEGRITY ANOMALIES
// ======================================

if (
  msg.includes("file") ||
  msg.includes("integrity") ||
  msg.includes("modified") ||
  msg.includes("deleted")
) {

addRecommendation(
  "Investigate unexpected file modification activity and validate integrity changes across monitored assets or sensitive directories",
  90,
  "file_integrity"
);

addRecommendation(
  "Review recent user actions, permission changes, and potential tampering indicators associated with affected files",
  86,
  "tampering_analysis"
);

}

// ======================================
// MEMORY / RESOURCE ABUSE
// ======================================

if (
  msg.includes("memory") ||
  msg.includes("cpu") ||
  msg.includes("resource") ||
  msg.includes("exhaustion")
) {

addRecommendation(
  "Review abnormal resource utilization patterns and investigate potential exhaustion attacks, runaway processes, or malicious workload activity",
  88,
  "resource_abuse"
);

addRecommendation(
  "Validate system stability metrics, process consumption behavior, and infrastructure performance degradation indicators",
  82,
  "system_stability"
);

}

// ======================================
// NETWORK CONNECTION INTELLIGENCE
// ======================================

if (
  msg.includes("connection") ||
  msg.includes("traffic") ||
  msg.includes("port")
) {

addRecommendation(
  "Investigate suspicious network connection behavior and correlate unusual communication patterns across hosts, ports, and external endpoints",
  91,
  "network_connections"
);

addRecommendation(
  "Review connection frequency anomalies, failed communication attempts, and unexpected outbound traffic behavior",
  86,
  "traffic_analysis"
);

}

// ======================================
// CORRELATION-AWARE INTELLIGENCE
// ======================================

if (
  recommendationContext.correlated
){

addRecommendation(
  "Investigate repeated behavioral activity associated with this anomaly and correlate related events across the active monitoring window",
  97,
  "behavioral_correlation"
);

addRecommendation(
  "Review attack progression indicators, recurring source activity, and multi-event escalation behavior for signs of sustained compromise attempts",
  95,
  "attack_progression"
);

}

// ======================================
// THREAT SCORE INTELLIGENCE
// ======================================

const threatScore =
  Number(
    a.threat_score || 0
  );

if (threatScore >= 100) {

  addRecommendation(
    "Treat this activity as a potentially active security incident requiring immediate containment and accelerated investigation workflow",
    100,
    "critical_incident"
  );

  addRecommendation(
    "Prioritize forensic validation, attack-scope assessment, and rapid analyst escalation due to critical threat scoring",
    98,
    "forensic_escalation"
  );

}
else if (threatScore >= 75) {

  addRecommendation(
    "Prioritize this anomaly for investigation due to elevated threat scoring and increased likelihood of malicious activity",
    92,
    "threat_prioritization"
  );

}

  // ======================================
  // NETWORK ANOMALIES
  // ======================================

 if (
  recommendationContext.reconPhase
) {

addRecommendation(
  "Investigate potential reconnaissance or scanning behavior and correlate network activity across related hosts and source IP addresses",
  94,
  "reconnaissance"
);

addRecommendation(
  "Review lateral movement indicators, unusual traffic patterns, and endpoint communication anomalies for possible attack propagation",
  90,
  "lateral_movement"
);

addRecommendation(
  "Consider containment or network isolation if sustained suspicious activity is confirmed",
  96,
  "containment"
);

  }

  // ======================================
  // SERVICE FAILURES
  // ======================================

  if (
    msg.includes("error") ||
    msg.includes("exception") ||
    msg.includes("crash")
  ) {
    
    
addRecommendation(
  "Investigate abnormal service behavior and review application logs for crashes, execution failures, or instability indicators",
  86,
  "service_instability"
);

addRecommendation(
  "Validate recent deployments, configuration modifications, and dependency changes that may have triggered service disruption",
  78,
  "configuration_validation"
);

addRecommendation(
  "Review system resource utilization and failure patterns for potential exhaustion, cascading failures, or malicious impact",
  84,
  "resource_analysis"
);

  }

  // ======================================
  // VERY HIGH CONFIDENCE
  // ======================================

  if (prob >= 0.90) {
    
    
    addRecommendation(
  "Treat anomaly activity as potentially high-risk until investigation and validation are completed",
  89,
  "high_confidence"
);

  }

  // ======================================
// BASELINE HIGH-RISK INVESTIGATION
// ======================================

if (
  recommendationContext.highSeverity ||
  prob >= 0.80
) {

addRecommendation(
  "Review related system activity, authentication behavior, and recent operational events surrounding the anomaly timeframe",
  76,
  "contextual_review"
);

addRecommendation(
  "Correlate anomaly indicators with additional telemetry sources to determine whether the activity reflects isolated failure or broader malicious behavior",
  82,
  "telemetry_correlation"
);

}

  // ======================================
  // FALLBACK
  // ======================================

  if (recommendations.length === 0) {

addRecommendation(
  "Continue monitoring anomaly behavior and validate whether additional related indicators emerge over time",
  30,
  "monitoring"
);

addRecommendation(
  "Correlate this anomaly with additional telemetry sources and surrounding operational activity for further investigation context",
  45,
  "general_correlation"
);

  }

  // ======================================
  // RENDER
  // ======================================

const categoryMap = {};

for (const rec of recommendations) {

  const existing =
    categoryMap[rec.category];

  if (
    !existing ||
    rec.priority > existing.priority
  ) {

    categoryMap[rec.category] = rec;

  }

}

const prioritizedRecommendations =
  Object.values(categoryMap)
    .sort((a, b) => b.priority - a.priority)
    .slice(0, 5);

return prioritizedRecommendations.map(r => `

  <div class="recommendation-item">
    🛡 ${escapeHtml(r.text)}
  </div>

`).join("");

}
/* Chart */

// ---------- Dataset Upload (CSV) ----------
function wireUpload() {
  const btn = document.getElementById("uploadBtn");
  const input = document.getElementById("uploadInput");

  if (!btn || !input) {
    console.warn("wireUpload: missing uploadBtn or uploadInput; skipping initialization.");
    return;
  }

  btn.addEventListener("click", () => {
    try {
      input.click();
    } catch (err) {
      console.error("Upload button click failed:", err);
    }
  });

  input.addEventListener("change", async () => {
    const file = input.files && input.files[0];
    if (!file) return;

    if (!file.name.toLowerCase().endsWith(".csv")) {
      notify("Upload failed", "Please select a .csv file", true);
      input.value = "";
      return;
    }

    try {
      const fd = new FormData();
      fd.append("file", file);

      const res = await fetch("/api/datasets/upload", {
        method: "POST",
        body: fd
      });

      let data = {};
      try { data = await res.json(); } catch (_) {}

      if (!res.ok || !(data.ok || data.status === "ok")) {
        const msg = (data && (data.error || data.message)) || `HTTP ${res.status}`;
        notify("Upload failed", String(msg), true);
      } else {
        const rows = data.rows_added != null ? data.rows_added : "N/A";
        notify("Dataset uploaded", `Added ${rows} rows from ${file.name}`);

        // 🔥 Switch to upload mode
      if (typeof currentMode !== "undefined") {
        currentMode = "upload";
        localStorage.setItem("dashboard_mode", currentMode);}

        // 🔥 Update UI buttons
        const uploadBtnUI = document.getElementById("uploadsBtn");
        const liveBtnUI = document.getElementById("liveBtn");

        if (uploadBtnUI && liveBtnUI) {
          uploadBtnUI.classList.add("active");
          liveBtnUI.classList.remove("active");
        }

        // 🔥 CRITICAL FIX: Fetch real anomalies and override stats
        if (typeof fetchAnomalies === "function") {
          const anomalies = await fetchAnomalies();

          if (typeof filterBySource === "function") {
            const filtered = filterBySource(anomalies, currentMode);
            const severityFilter = window.activeSeverity || "ALL";

const finalFiltered = severityFilter === "ALL"
  ? filtered
  : filtered.filter(a => (a.severity || "").toUpperCase() === severityFilter);

            const total = finalFiltered.length;

            // 🔥 Override counters (ignore backend stats)
            const elTotal = document.getElementById("totalAnomalies");
            const el10m   = document.getElementById("last10m");
            const el1h    = document.getElementById("last1h");
            const el24h   = document.getElementById("last24h");
            const big     = document.getElementById("bigNumber");

            const now = new Date();

const last10m = finalFiltered.filter(a => {
  const t = new Date(a.detected_at);
  return t && !isNaN(t) && (now - t) <= 10 * 60 * 1000;
}).length;

const last1h = finalFiltered.filter(a => {
  const t = new Date(a.detected_at);
  return t && !isNaN(t) && (now - t) <= 60 * 60 * 1000;
}).length;

const last24h = finalFiltered.filter(a => {
  const t = new Date(a.detected_at);
  return t && !isNaN(t) && (now - t) <= 24 * 60 * 60 * 1000;
}).length;

if (elTotal) elTotal.innerText = total;
if (el10m)   el10m.innerText   = last10m;
if (el1h)    el1h.innerText    = last1h;
if (el24h)   el24h.innerText   = last24h;
if (big)     big.innerText     = total;

            // 🔥 Update UI components consistently
            if (typeof renderTable === "function")renderTable(finalFiltered);
            if (currentMode === "live" && typeof updateChart === "function") {
              updateChart(filtered);
            }
            if (typeof updateServiceDonut === "function") updateServiceDonut(finalFiltered);
          }
        }

      }

    } catch (err) {
      console.error("Upload error:", err);
      notify("Upload error", String(err), true);
    } finally {
      input.value = "";
    }
  });
}


// ---------- Notification Helper ----------
function notify(title, message, isError = false) {
  if (typeof showToast === "function") {
    showToast(title, message, isError ? "error" : "info", 6000);
  } else {
    console[(isError ? "error" : "log")](title + ": " + message);
    if (isError) alert(title + ": " + message);
  }
}




function updateChart(anomalies = []) {

  // Ensure the canvas + chart exist
  const canvas = document.getElementById("anomalyChart");
  if (!canvas) return;

  // Get existing chart instance
  const ch = window.anomalyChart || (Chart.getChart ? Chart.getChart(canvas) : null);
  if (!ch) return;

  // ---------- CONFIG ----------
  const WINDOW_MINUTES = 1440;

  // Base "now" in UTC (authoritative)
  const now = new Date();

  const nowUTC = new Date(Date.UTC(
    now.getUTCFullYear(),
    now.getUTCMonth(),
    now.getUTCDate(),
    now.getUTCHours(),
    now.getUTCMinutes(),
    0,
    0
  ));

  // Timezone offset (UI only)
  const OFFSET_MS =
    (typeof activeTimezone !== "undefined" &&
     activeTimezone === "IST")
      ? (5.5 * 60 * 60 * 1000)
      : 0;

  // Display time (UTC or IST)
  const displayNow = new Date(nowUTC.getTime() + OFFSET_MS);

// ---------- BUILD EMPTY HOURLY BUCKETS ----------
const buckets = {};
const labels = [];

for (let i = 23; i >= 0; i--) {

    const d = new Date(
      displayNow.getTime() - i * 60 * 60 * 1000
    );

    const label =
      `${String(d.getHours()).padStart(2, "0")}:00`;

    buckets[label] = 0;
    labels.push(label);
}

  // Rolling window start (UTC authoritative)
  const windowStartUTC = new Date(
    nowUTC.getTime() - WINDOW_MINUTES * 60 * 1000
  );

  // ---------- FILL BUCKETS FROM REAL DATA ----------
  for (const a of anomalies) {

    const ts = a?.detected_at;
    if (!ts) continue;

    // Force UTC parsing
    const dUTC = new Date(
      ts.endsWith("Z") ? ts : ts + "Z"
    );

    if (Number.isNaN(dUTC.getTime())) continue;



    // Ignore outside rolling window
    if (dUTC < windowStartUTC || dUTC > nowUTC) continue;

    // Convert to display timezone
    const dDisplay = new Date(
      dUTC.getTime() + OFFSET_MS
    );

    const label =
     `${String(dDisplay.getHours()).padStart(2, "0")}:00`;

    // ===============================
    // THREAT SCORE AGGREGATION
    // ===============================
    const threat = 1;

    if (label in buckets) {
      buckets[label] += 1;
    }
  }

  // ---------- UPDATE CHART ----------
  if (!ch.data) {
    ch.data = {
      labels: [],
      datasets: []
    };
  }

  if (!Array.isArray(ch.data.datasets)) {
    ch.data.datasets = [];
  }

  if (!ch.data.datasets[0]) {
    ch.data.datasets[0] = {
      label: "Threat Activity",
      data: []
    };
  }

  ch.data.labels = labels;

  ch.data.datasets[0].data =
    labels.map(l => buckets[l]);

  ch.data.datasets[0].label =
    "Threat Activity (Last 30 min)";

  if (typeof ch.update === "function") {
    ch.update();
  }
}

/* -------------------- Donut: Anomalies by Service -------------------- */




/* update donut with anomalies array */
/* ---------- Drill-down: service summary + filtered table (Option 1) ---------- */

// holds last fetched anomalies (updated inside fetchAnomalies)


/* 
   (I'll include exact placement below in case you want to copy it)
*/

/* applyServiceFilter(serviceName)
   Renders table with only that service's anomalies and shows a summary banner.
*/
function applyServiceFilter(serviceName) {
  // defensive
  if (!serviceName) return;

  // use latestAnomalies to compute stats (falls back to table DOM if empty)
  const source = filterBySource(anomalies, currentMode);
  const filtered = source.filter(a => {
    const svc = (a && (a.service || a.svc || "")).toString();
    return svc === serviceName;
  });

  // compute stats
  const count = filtered.length;
  const avgProb = count ? (filtered.reduce((s,a) => s + (parseFloat(a.prob_anomaly) || 0), 0) / count) : 0;
  // latest timestamp (prefer detected_at then timestamp), iso string or empty
  let latestTs = "";
  for (const a of filtered) {
    const t = a.detected_at || a.timestamp || "";
    if (!t) continue;
    if (!latestTs || (new Date(t).getTime() > new Date(latestTs).getTime())) latestTs = t;
  }

  // render filtered table
renderTable(finalFiltered);

  // show summary banner
  renderServiceSummary(serviceName, count, avgProb, latestTs);

  // small toast
  showToast("Filter applied", `Showing only service: ${serviceName}`, "info", 3000);
}

/* renderServiceSummary: inserts a small summary card above the anomalies table */
function renderServiceSummary(serviceName, count, avgProb, latestTs) {
  // remove prior summary if present
  const existing = document.getElementById("serviceSummary");
  if (existing) existing.remove();

  // find table-card container
  const container = document.querySelector(".table-card");
  if (!container) return;

  const summary = document.createElement("div");
  summary.id = "serviceSummary";
  summary.style.display = "flex";
  summary.style.alignItems = "center";
  summary.style.justifyContent = "space-between";
  summary.style.gap = "12px";
  summary.style.padding = "12px 16px";
  summary.style.borderRadius = "10px";
  summary.style.marginBottom = "12px";
  summary.style.background = "linear-gradient(180deg, rgba(255,255,255,0.02), rgba(0,0,0,0.02))";
  summary.style.border = "1px solid rgba(255,255,255,0.02)";
  summary.style.color = "#cfe9ff";

  // left: details
  const left = document.createElement("div");
  left.innerHTML = `<div style="font-weight:800;font-size:14px;margin-bottom:6px">Service: ${escapeHtml(serviceName)}</div>
                    <div style="font-size:13px;color:#9db6c8">Count: <strong>${count}</strong> &nbsp; • &nbsp; Avg prob: <strong>${isFinite(avgProb) ? 
                      avgProb.toFixed(2) : "0.00"}</strong> &nbsp; • &nbsp; Latest: <strong>${escapeHtml(latestTs || "N/A")}</strong></div>`;

  // right: Back button
  const right = document.createElement("div");
  const btn = document.createElement("button");
  btn.textContent = "Back to all";
  btn.style.background = "#2ca874";
  btn.style.color = "#fff";
  btn.style.border = "none";
  btn.style.padding = "6px 10px";
  btn.style.borderRadius = "8px";
  btn.style.cursor = "pointer";
  btn.onclick = function() {
    clearServiceFilter();
    summary.remove();
  };
  right.appendChild(btn);

  summary.appendChild(left);
  summary.appendChild(right);

  // insert summary at top of container (before table)
  container.insertBefore(summary, container.firstChild);
}

/* clearServiceFilter: restores full table (and removes summary if present) */
async function clearServiceFilter() {
  // remove summary if present
  const existing = document.getElementById("serviceSummary");
  if (existing) existing.remove();

  // render full table from latestAnomalies
  if (Array.isArray(latestAnomalies)) {
    renderTable(latestAnomalies);
  } else {
    // ✅ Load actions first
    await loadActionsMap();

    // fallback: try to re-fetch anomalies if we don't have them
    fetchAnomalies();
  }
}

/* show a hint/button to clear filter (non-destructive)
   Creates a small floating button near table header if not present. */




async function refresh() {

    if (typeof currentMode === "undefined") return;

    // ==========================================
    // LOAD ANALYST ACTIONS FIRST
    // ==========================================
    await loadActionsMap();

    // ==========================================
    // REFRESH DASHBOARD STATS
    // ==========================================
    if (typeof fetchStats === "function") {
        fetchStats();
    }

    // ==========================================
    // REFRESH ANOMALIES TABLE
    // ==========================================
    if (typeof fetchAnomalies === "function") {
        fetchAnomalies();
    }

    // ==========================================
    // LIVE EVENT MONITOR
    // ONLY ACTIVE IN LIVE MODE
    // ==========================================
    const consoleBox =
        document.getElementById("liveMonitorConsole");

    if (!consoleBox) return;

    // Upload Mode -> Disable Live Feed
    if (currentMode === "upload") {

        consoleBox.innerHTML = `
            <div class="live-placeholder">
                Live Event Stream available only in LIVE mode
            </div>
        `;

        return;
    }

    // LIVE / ALL MODE
    try {

        const response =
            await fetch("/api/live-stream");

        if (response.ok) {

            const events =
                await response.json();

            consoleBox.innerHTML = events
                .slice(-25)
                .reverse()
                .map(line =>
                    `<div class="live-line">${line}</div>`
                )
                .join("");

            consoleBox.scrollTop =
                consoleBox.scrollHeight;
        }

    } catch (err) {

        console.error(
            "Live monitor refresh failed:",
            err
        );

    }
}
/*Default = Live (no change in current behaviour
Switch to All or Uploads when needed.*/
 // default keeps your live view pure
 // -------------------------
// Source filtering + fetch glue
// -------------------------

// Default keeps your live view pure. (Change to "uploads" once if you want to
// quickly verify the Uploads view without adding live lines.)




/** Build query string from current filters (we'll extend later with host/time). */
function getQueryParams() {
  const p = new URLSearchParams();

  if (currentMode === "live") {
    p.set("source", "live");
  } else if (currentMode === "upload") {
    p.set("source", "upload");
  }

  return p.toString();
}

/** Small helper to append the query string safely. */
function buildUrl(pathAndQuery) {
  const [pathOnly, existingQS] = pathAndQuery.split("?", 2);

  // Build query params from current filters
  const params = new URLSearchParams(getQueryParams() || "");

  // If source is "all", remove it completely (canonical behavior)
  if (params.get("source") === "all") {
    params.delete("source");
  }

  const finalQS = params.toString();

  if (existingQS && finalQS) return `${pathOnly}?${existingQS}&${finalQS}`;
  if (existingQS)           return `${pathOnly}?${existingQS}`;
  if (finalQS)             return `${pathOnly}?${finalQS}`;
  return pathOnly;
}




/*

*/
// ------- Chart initializers (create empty charts so updates never crash) -------
function initCharts() {
  try {
    // -------- Anomalies Over Time (bar) --------
    const ac = document.getElementById("anomalyChart");
    if (ac) {
      // destroy any existing chart bound to this canvas
      const existingBar = (Chart.getChart ? Chart.getChart(ac) : window.anomalyChart);
      if (existingBar && typeof existingBar.destroy === "function") existingBar.destroy();

      window.anomalyChart = new Chart(ac.getContext("2d"), {
        type: "bar",
        data: {
          labels: [],
          datasets: [{
            label: "Anomalies",
            data: [],
            borderWidth: 0,
            barPercentage: 1.0,
            categoryPercentage: 1.0,
            maxBarThickness: 25,
            backgroundColor: "rgba(246, 189, 96, 0.9)"
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            x: { grid: { display: false } },
            y: { beginAtZero: true, grid: { color: "rgba(255,255,255,0.08)" } }
          },
          plugins: { legend: { display: false } }
        }
      });
    }
  } catch (e) {
    console.error("initCharts error:", e);
  }
}

//-----service donut---//
function initServiceDonut() {
  const sd = document.getElementById("serviceDonut");
  if (!sd) return;

  const existingDonut = (Chart.getChart ? Chart.getChart(sd) : window.serviceDonutChart);
  if (existingDonut && typeof existingDonut.destroy === "function") {
    existingDonut.destroy();
  }

  window.serviceDonutChart = new Chart(sd.getContext("2d"), {
    type: "doughnut",
    data: {
      labels: [],
      datasets: [{
        data: [],
        backgroundColor: [
          "rgba(59,130,246,0.9)",
          "rgba(251,191,36,0.9)",
          "rgba(34,197,94,0.9)",
          "rgba(244,63,94,0.9)",
          "rgba(99,102,241,0.9)"
        ]
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      cutout: "60%",
      plugins: { legend: { display: false } }
    }
  });
}
/*  updateServiceDonut */

function updateServiceDonut(anomalies) {
  if (!window.serviceDonutChart) return;

  const counts = {};
  (anomalies || []).forEach(a => {
    const svc = (a && (a.service || a.svc || "").toString().trim()) || "unknown";
    counts[svc] = (counts[svc] || 0) + 1;
  });

  const labels = Object.keys(counts);
  const data = Object.values(counts);

  const baseColors = [
    "#f4b03a", "#2ca874", "#1e90ff",
    "#e67e22", "#9b59b6", "#e74c3c",
    "#16a085", "#34495e"
  ];

  const colors = labels.map((lbl, i) =>
    (activeServiceFilter && lbl === activeServiceFilter)
      ? "#ffd27a"
      : baseColors[i % baseColors.length]
  );

  window.serviceDonutChart.data.labels = labels;
  window.serviceDonutChart.data.datasets[0].data = data;
  window.serviceDonutChart.data.datasets[0].backgroundColor = colors;
  window.serviceDonutChart.update();
}



function filterBySource(anomalies = [], mode = "all") {
  if (!Array.isArray(anomalies)) return [];

  // Normalize mode
  mode = (mode || "all").toLowerCase();

  // If backend already tags source → use it
  return anomalies.filter(a => {
    const src = (a.source || a.dataset_source || "live").toLowerCase();

    if (mode === "live") return src === "live";
    if (mode === "upload") return src === "upload";
    return true; // "all"
  });
}

/** Fetch stats and update tiles + big number + donut (uses your existing DOM ids). */

// Lightweight refresher used after uploads (table + big number only)
// here the async function fecthanomelis was there 


/** Wire the segmented control (Live | All | Uploads). */
function wireSourceSwitch() {
  const el = document.getElementById("sourceSwitch");
  if (!el) return;

  el.querySelectorAll(".seg-btn").forEach(btn => {
    btn.addEventListener("click", async () => {

      // UI toggle
      el.querySelectorAll(".seg-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");

      // Set source
      currentMode = btn.dataset.src || "all";

      const monitorCard =
    document.getElementById("eventMonitorCard");
    
    if (monitorCard) {
      monitorCard.style.display =
        currentMode === "upload"
            ? "none"
            : "block";
}

      // 🔥 AUTO-REFRESH CONTROL
      if (currentMode=== "live") {
        startAutoRefresh();
      } else {
        stopAutoRefresh();
      }

      // ✅ Load actions first
      await loadActionsMap();

      // Fetch anomalies
// Fetch stats first
    if (typeof fetchStats === "function") {
      await fetchStats();
    }

// Then anomalies
    if (typeof fetchAnomalies === "function") {
      await fetchAnomalies();
}
    });
  });
}
// Kick things off








// Unified, defensive startup 
document.addEventListener("DOMContentLoaded", async () => {
  try {
    // wire upload control (safe if not present)
    try { if (typeof wireUpload === "function") wireUpload(); } catch (e) {
      console.error("wireUpload failed:", e);
    }

    // init charts (support both initCharts() and legacy initChart())
    try {
      if (typeof initCharts === "function") initCharts();
      else if (typeof initChart === "function") initChart();

      // init service donut AFTER charts and AFTER DOM is ready
      if (typeof initServiceDonut === "function") initServiceDonut();

    } catch (e) {
      console.error("initCharts/initChart/initServiceDonut failed:", e);
    }

    // wire segmented source buttons (Live / All / Uploads)
    try { if (typeof wireSourceSwitch === "function") wireSourceSwitch(); } catch (e) {
      console.error("wireSourceSwitch failed:", e);
    }

  const level = window.activeSeverity || "ALL";

  document.querySelectorAll('[data-sev]').forEach(btn => {
    btn.classList.remove('active');
    if (btn.getAttribute('data-sev') === level) {
      btn.classList.add('active');
    }
  }); 

    // initial data fetches (stats first, then anomalies)
    try { if (typeof fetchStats === "function") await fetchStats(); } catch (e) {
      console.error("fetchStats failed:", e);
    }

    // ✅ CRITICAL FIX — Load actions BEFORE anomalies
    try { await loadActionsMap(); } catch (e) {
      console.error("loadActionsMap failed:", e);
    }

    try { if (typeof fetchAnomalies === "function") await fetchAnomalies(); } catch (e) {
      console.error("fetchAnomalies failed:", e);
    }

    const exportCSVBtn = document.getElementById("exportCSV");
const exportJSONBtn = document.getElementById("exportJSON");

if (exportCSVBtn) {
  exportCSVBtn.addEventListener("click", () => {
    const dataToExport = filterBySource(window.currentAnomalies || [], currentMode);
    exportToCSV(dataToExport);
  });
}

if (exportJSONBtn) {
  exportJSONBtn.addEventListener("click", () => {
    const dataToExport = filterBySource(window.currentAnomalies || [], currentMode);
    exportToJSON(dataToExport);
  });
}

    // optional periodic refresh ( can be enabled later once stability test has been done )
    // setInterval(refresh, 5000); // disabled for debugging

  } catch (e) {
    console.error("startup error:", e);
  }

  startAutoRefresh();
});

if (window.serviceDonutChart && stats.by_service) {
  window.serviceDonutChart.data.labels = Object.keys(stats.by_service);
  window.serviceDonutChart.data.datasets[0].data = Object.values(stats.by_service);
  window.serviceDonutChart.update();
}

// Toggle Latest Anomalies (Show more / Show less)
const toggleBtn = document.getElementById("toggleAnomaliesBtn");

if (toggleBtn) {
  toggleBtn.addEventListener("click", async () => {
    anomaliesExpanded = !anomaliesExpanded;
    toggleBtn.innerText = anomaliesExpanded ? "Show less" : "Show more";

    // ✅ Load actions before re-render
    await loadActionsMap();

    // Re-render anomalies table
    fetchAnomalies();
  });
}

function acknowledgeAnomaly(anomalyId, btn, comment) {

  fetch("/api/anomalies/action", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      anomaly_id: anomalyId,
      status: "acknowledged",
      comment: comment || ""
    })
  })
  .then(res => res.json())
  .then(async (data) => {
    console.log("ACK RESPONSE:", data);

    // ✅ Reload actions + refresh table (CRITICAL)
    if (typeof loadActionsMap === "function") {
      await loadActionsMap();
    }

    if (typeof fetchAnomalies === "function") {
      await fetchAnomalies();
    }

    // Optional fallback UI update (safe)
    if (btn) {
      btn.textContent = "Acknowledged";
      btn.classList.add("done");
      btn.disabled = true;
    }
  })
  .catch(err => {
    console.error("ACK ERROR:", err);
    alert("Failed to acknowledge");
  });
}

/* ---------------------------*/ 
function markFalsePositive(anomalyId, btn) {

  const comment = document.getElementById(`comment-${anomalyId}`)?.value || "";

  fetch("/api/anomalies/action", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      anomaly_id: anomalyId,
      status: "false_positive",
      comment: comment
    })
  })
  .then(res => res.json())
  .then(data => {
    console.log("FP RESPONSE:", data);

    if (btn) {
      btn.textContent = "False Positive";
      btn.classList.add("done");
      btn.disabled = true;
    }

    // Optional: refresh table
    if (typeof fetchAnomalies === "function") {
      fetchAnomalies();
    }
  })
  .catch(err => {
    console.error("FP ERROR:", err);
    alert("Failed to mark false positive");
  });
}

function closeAnomaly(anomalyId, btn) {

  const comment = prompt("Closing note (optional):");

  fetch("/api/anomalies/action", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      anomaly_id: anomalyId,
      status: "closed",
      comment: comment || ""
    })
  })
  .then(res => res.json())
  .then(data => {
    // console.log("CLOSE RESPONSE:", data);

    // 🔥 Force UI refresh (important)
    fetchAnomalies();
  })
  .catch(err => {
    console.error("CLOSE ERROR:", err);
    alert("Failed to close anomaly");
  });
}

function exportToCSV(data) {
  if (!data || !data.length) return;

  const headers = Object.keys(data[0]);

  const rows = data.map(row =>
    headers.map(h => `"${(row[h] ?? "").toString().replace(/"/g, '""')}"`).join(",")
  );

  const csvContent = [headers.join(","), ...rows].join("\n");

  const blob = new Blob([csvContent], { type: "text/csv" });
  const url = URL.createObjectURL(blob);

  const a = document.createElement("a");
  a.href = url;
  const now = new Date().toISOString().slice(0,19).replace(/[:T]/g, "-");
  a.download = `anomalies_${now}.csv`;
  a.click();

  URL.revokeObjectURL(url);

  // ✅ DELAYED TOAST
  setTimeout(() => {
    if (typeof showToast === "function") {
      showToast("Export Complete", "CSV downloaded successfully", "success", 3000);
    }
  }, 300);
}

function exportToJSON(data) {
  if (!data || !data.length) return;

  const blob = new Blob([JSON.stringify(data, null, 2)], {
    type: "application/json"
  });

  const url = URL.createObjectURL(blob);

  const a = document.createElement("a");
  a.href = url;
  const now = new Date().toISOString().slice(0,19).replace(/[:T]/g, "-");
  a.download = `anomalies_${now}.json`;
  a.click();

  URL.revokeObjectURL(url);

  // ✅ DELAYED TOAST
  setTimeout(() => {
    if (typeof showToast === "function") {
      showToast("Export Complete", "JSON downloaded successfully", "success", 3000);
    }
  }, 300);
}


  const level = window.activeSeverity || "ALL";

  document.querySelectorAll('[data-sev]').forEach(btn => {
    btn.classList.remove('active');
    if (btn.getAttribute('data-sev') === level) {
      btn.classList.add('active');
    }
  });



/*feedbaack */

function logFeedback(anomalyId, action) {

  // 🔥 Extract row context
  const row = document.querySelector(`[data-id='${anomalyId}']`);

  let message = null;
  let service = null;
  let probability = null;

  if (row) {
    // message column
    message = row.querySelector(".col-message")?.innerText || null;

    // service column
    service = row.querySelector(".col-service")?.innerText || null;

    // probability badge
    const probText = row.querySelector(".badge-prob")?.innerText || "";
    const prob = parseFloat(probText.replace("%", "")) / 100;

    if (!isNaN(prob)) {
      probability = prob;
    }
  }

  fetch("/api/feedback", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      anomaly_id: anomalyId,
      action: action,
      message: getMessageFromRow(anomalyId),
      suggested_label: getSuggestedLabel(anomalyId),

      // 🔥 NEW FIELDS (CRITICAL)
      message: message,
      service: service,
      probability: probability
    })
  })
  .then(res => res.json())
  .then(data => {
    // console.log("FEEDBACK LOGGED:", data);
  })
  .catch(err => {
    console.error("FEEDBACK ERROR:", err);
  });
}


// ✅ KEEP THIS SAME (NO CHANGE)
function getSuggestedLabel(anomalyId) {
  const row = document.querySelector(`[data-id='${anomalyId}']`);
  if (!row) return null;

  const probEl = row.querySelector(".badge-prob");
  if (!probEl) return null;

  const prob = parseFloat(probEl.textContent.replace('%','')) / 100;

  if (isNaN(prob)) return null;

  if (prob >= 0.8) return 1;
  if (prob <= 0.3) return 0;

  return null;
}

// =========================================
// ANALYST INVESTIGATION PANEL
// =========================================
function showAnalystPanel(a) {

  const panel = document.getElementById("analystPanel");
  const content = document.getElementById("analystPanelContent");

  if (!panel || !content) return;

  panel.classList.remove("hidden");

  const prob =
    Number(
      a.prob_anomaly ||
      a.probability ||
      a.score ||
      0
    ) * 100;

const severity = deriveSeverity(prob / 100);

  const severityClass =
    severity.toLowerCase();

  content.innerHTML = `

    <div class="analyst-section">
      <div class="analyst-label">Host</div>
      <div class="analyst-value">${escapeHtml(a.host || "-")}</div>
    </div>

    <div class="analyst-section">
      <div class="analyst-label">Service</div>
      <div class="analyst-value">${escapeHtml(a.service || a.svc || "-")}</div>
    </div>

    <div class="analyst-section">
      <div class="analyst-label">Severity</div>
      <div class="analyst-value">
        <span class="analyst-severity ${severityClass}">
          ${severity}
        </span>
      </div>
    </div>

    <div class="analyst-section">
      <div class="analyst-label">Threat Score</div>
      <div class="analyst-value">
        ${prob.toFixed(2)}%
      </div>
    </div>

    <div class="analyst-section">
      <div class="analyst-label">Timestamp</div>
      <div class="analyst-value">
        ${escapeHtml(a.detected_at || a.timestamp || "-")}
      </div>
    </div>

    <div class="analyst-section">
  <div class="analyst-label">Case Status</div>
  <div class="analyst-value">
    ${escapeHtml((a.status || "NEW").toUpperCase())}
  </div>
</div>

<div class="analyst-section">
  <div class="analyst-label">Analyst Action</div>
  <div class="analyst-value">
    ${escapeHtml(a.action || a.analyst_action || "-")}
  </div>
</div>

    <div class="analyst-section">
      <div class="analyst-label">Message</div>
      <div class="analyst-value">
        ${escapeHtml(a.message || "-")}
      </div>
    </div>
    <div class="analyst-section full-width">

  <div class="analyst-label">
    Detection Factors
  </div>

  <div class="detection-factors">

    ${generateDetectionFactors(a)

    }

  </div>

  <div class="analyst-section full-width">

  <div class="analyst-label">
    MITRE ATT&CK Mapping
  </div>

  <div class="mitre-mapping-list">


  ${generateMitreMapping(a).length > 0

  ? generateMitreMapping(a).map(m => `

    <div class="mitre-item">

      <div class="mitre-tactic">
        ${escapeHtml(m.tactic)}
      </div>

      <div class="mitre-technique">
        ${escapeHtml(m.technique)}
      </div>

      <div class="mitre-id">
        ${escapeHtml(m.technique_id)}
      </div>

    </div>

  `).join("")

  : `

    <div class="mitre-empty">
      No MITRE ATT&CK mapping identified for this anomaly
    </div>

  `
}

  </div>

</div>

  <div class="analyst-section full-width">

  <div class="analyst-label">
    Recommended Response
  </div>

  <div class="recommendation-list">

    ${generateRecommendations(a)}

  </div>

</div>

</div>

  `;

  panel.scrollIntoView({
    behavior: "smooth",
    block: "start"
  });

  panel.classList.remove(
  "panel-low",
  "panel-medium",
  "panel-high"
);

panel.classList.add(
  `panel-${severity.toLowerCase()}`
);
}


function updateDecisionAssistant(rows) {

  const rec =
    document.getElementById("assistantRecommendation");

  const reason =
    document.getElementById("assistantReason");

  if (!rec || !reason) return;

  if (!rows || rows.length === 0) {

    rec.textContent = "NO ACTIVE ANOMALIES";

    reason.textContent =
      "No anomaly currently requires analyst action.";

    return;
  }

  const anomaly = rows[0];
  
  const prob = Number(
    anomaly.prob ||
    anomaly.score ||
    0
);

  const severity =
    (anomaly.severity || "").toUpperCase();

  const status =
    (anomaly.status || "NEW").toUpperCase();

if (status === "ACKNOWLEDGED") {

    rec.textContent =
      "ESCALATE OR CLOSE";

    reason.textContent =
      "Analyst already acknowledged this anomaly. Further investigation required.";

}
else if (severity === "HIGH" && prob >= 0.80) {

    rec.textContent =
      "ACKNOWLEDGE & INVESTIGATE";

    reason.textContent =
      "High severity anomaly with strong ML confidence.";

}
else if (severity === "MEDIUM" || prob >= 0.60) {

    rec.textContent =
      "REVIEW";

    reason.textContent =
      "Requires analyst verification before escalation.";

}
else {

    rec.textContent =
      "FALSE POSITIVE REVIEW";

    reason.textContent =
      "Low confidence anomaly. Verify before taking action.";

}
}


document.getElementById("retrainBtn")?.addEventListener(
  "click",
  async () => {

    const btn = document.getElementById("retrainBtn");

    btn.disabled = true;
    btn.textContent = "Retraining...";

    try {

      const response = await fetch(
        "/api/retrain",
        {
          method: "POST"
        }
      );

      const result = await response.json();

      console.log(
        "Retraining result:",
         result
      );

      // Refresh cards immediately
      if (typeof refresh === "function") {
        await refresh();
      }

    } catch (err) {

      console.error(
        "Retraining failed:",
        err
      );

    } finally {

      btn.disabled = false;
      btn.textContent = "Retrain Model";

    }

  }
);