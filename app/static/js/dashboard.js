// ----- Timezone handling -----
let activeTimezone = "UTC"; // "UTC" | "IST"

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






// static/js/dashboard.js  (defensive + verbose)
console.log("dashboard.js (defensive) loaded at", new Date().toISOString());




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
const notifiedAnomalyKeys = new Set();


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
    console.log("Applied filter:", activeServiceFilter, "=>", filtered.length, "rows");
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
    console.log("Cleared service filter — restored full view");
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


console.log("dashboard.js (defensive) loaded at", new Date().toISOString());
// chart globals (declare before any init functions)





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

  console.log("Toast shown:", title, text);
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
    const res = await fetch(buildUrl("/api/stats"));
    if (!res.ok) {
      throw new Error(`stats fetch failed: ${res.status}`);
    }

    const stats = await res.json();
    console.log("stats JSON:", stats);

    // Expect canonical shape: { counts: {...}, by_service: {...} }
    const counts = stats.counts || {};

    // Update tiles
    const elTotal = document.getElementById("totalAnomalies");
    const el10m   = document.getElementById("last10m");
    const el1h    = document.getElementById("last1h");
    const el24h   = document.getElementById("last24h");

    if (elTotal) elTotal.innerText = counts.total ?? 0;
    if (el10m)   el10m.innerText   = counts.last_10_minutes ?? 0;
    if (el1h)    el1h.innerText    = counts.last_1_hour ?? 0;
    if (el24h)   el24h.innerText   = counts.last_24_hours ?? 0;

    // Big number tile
    const big = document.getElementById("bigNumber");
    if (big) big.innerText = counts.total ?? 0;

    // Donut chart update (guarded)
    if (window.serviceDonutChart && stats.by_service) {
      window.serviceDonutChart.data.labels = Object.keys(stats.by_service);
      window.serviceDonutChart.data.datasets[0].data = Object.values(stats.by_service);
      window.serviceDonutChart.update();
    }

  } catch (err) {
    console.error("fetchStats error:", err);
  }
}



/* fetch anomalies (final corrected version) */
async function fetchAnomalies() {
  try {
    const res = await fetch(buildUrl("/api/anomalies?limit=50"));
    if (!res.ok) throw new Error(`anomalies fetch failed: ${res.status}`);
    const data = await res.json();

    // ---------- Normalize ----------
    let anomalies = [];
    if (Array.isArray(data)) anomalies = data;
    else if (Array.isArray(data.anomalies)) anomalies = data.anomalies;
    else if (Array.isArray(data.results)) anomalies = data.results;
    else if (Array.isArray(data.data)) anomalies = data.data;
    else {
      for (const k of Object.keys(data || {})) {
        if (Array.isArray(data[k])) {
          anomalies = data[k];
          break;
        }
      }
    }

    // ---------- Sort: newest first (SAFE) ----------
    anomalies.sort((a, b) => {
      return extractAnomalyDate(b) - extractAnomalyDate(a);
    });

    latestAnomalies = anomalies;

    // ---------- TOAST LOGIC (CORRECTED) ----------
// ---------- TOAST LOGIC ----------
// ---------- TOAST LOGIC ----------
for (const row of anomalies) {
  const anomalyTime = extractAnomalyDate(row);
  if (!anomalyTime) continue;

  // First successful fetch: lock baseline silently, but DO NOT stop the loop
  if (!initialAnomaliesLoadDone) {
    lastSeenDetectedAt = PAGE_LOAD_TIME;
    initialAnomaliesLoadDone = true;
    console.log("[toast] baseline locked to PAGE_LOAD_TIME");
    continue;   // 🔒 CRITICAL FIX: was 'break'
  }

  // Ignore anomalies that occurred before page load
  if (anomalyTime <= PAGE_LOAD_TIME) continue;

  // Ignore already processed anomalies
  if (lastSeenDetectedAt && anomalyTime <= lastSeenDetectedAt) continue;

  // Build stable anomaly fingerprint
  const key = [
    safeGet(row, "detected_at", safeGet(row, "timestamp", "")),
    safeGet(row, "host", ""),
    safeGet(row, "service", safeGet(row, "svc", "system")),
    safeGet(row, "message", "")
  ].join("|");

  // Skip duplicates
  if (notifiedAnomalyKeys.has(key)) continue;

  const svc = safeGet(row, "service", safeGet(row, "svc", "system"));
  const msg = (safeGet(row, "message", "") || "").slice(0, 140);

  //  REAL NEW ANOMALY
  showToast(`New anomaly: ${svc}`, msg, "info", 7000);

  // Mark as notified
  notifiedAnomalyKeys.add(key);

  // Advance baseline safely
  lastSeenDetectedAt = anomalyTime;
}



    // ---------- UI updates ----------
    renderTable(anomalies);
    updateChart(anomalies);
    updateServiceDonut(anomalies);

    // ---------- Big number ----------
    try {
      const statsRes = await fetch(buildUrl("/api/stats"));
      const big = document.getElementById("bigNumber");
      if (statsRes.ok) {
        const statsJson = await statsRes.json();
        big.textContent =
          statsJson?.counts?.total ??
          statsJson?.count ??
          anomalies.length;
      } else {
        big.textContent = anomalies.length;
      }
    } catch {
      const big = document.getElementById("bigNumber");
      if (big) big.textContent = anomalies.length;
    }

  } catch (err) {
    console.error("Anomalies fetch error:", err);
    try { renderTable([]); } catch {}
  }
}




/* render table */
function renderTable(anomalies) {
  const tbody = document.querySelector("#anomaliesTable tbody");
  if (!tbody) {
    console.warn("No #anomaliesTable tbody found in DOM");
    return;
  }

  tbody.innerHTML = "";

  // Defensive filtering
  const rows = Array.isArray(anomalies)
    ? anomalies.filter(r =>
        r &&
        (
          (r.message && String(r.message).trim() !== "") ||
          (r.host && String(r.host).trim() !== "")
        )
      )
    : [];

  // References (safe even if elements do not exist)
  const toggleBtn = document.getElementById("toggleAnomaliesBtn");
  const countText = document.getElementById("anomalyCountText");

  // No anomalies case
  if (rows.length === 0) {
    tbody.innerHTML =
      `<tr>
        <td colspan="5" style="text-align:center;opacity:.7">
          No anomalies
        </td>
      </tr>`;

    if (toggleBtn) toggleBtn.style.display = "none";
    if (countText) countText.textContent = "";
    return;
  }

  // Decide visible rows
  const rowsToRender = anomaliesExpanded
    ? rows
    : rows.slice(0, COLLAPSED_LIMIT);

  // Show / hide toggle button
  if (toggleBtn) {
    toggleBtn.style.display =
      rows.length > COLLAPSED_LIMIT ? "inline-flex" : "none";
  }

  // Update count text
  if (countText) {
    countText.textContent =
      `Showing ${rowsToRender.length} of ${rows.length} anomalies`;
  }

  // Render rows
  for (const a of rowsToRender) {
    const tr = document.createElement("tr");

    // Probability handling (robust)
    let prob = parseFloat(
      safeGet(
        a,
        "prob_anomaly",
        safeGet(a, "probability", safeGet(a, "score", ""))
      )
    );
    if (Number.isNaN(prob)) prob = null;

    let probBadge = `<span class="badge-prob badge-low">-</span>`;
    if (prob !== null) {
      if (prob >= 0.8) {
        probBadge = `<span class="badge-prob badge-high">${prob.toFixed(2)}</span>`;
      } else if (prob >= 0.7) {
        probBadge = `<span class="badge-prob badge-mid">${prob.toFixed(2)}</span>`;
      } else {
        probBadge = `<span class="badge-prob badge-low">${prob.toFixed(2)}</span>`;
      }
    }

    const ts   = safeGet(a, "detected_at", safeGet(a, "timestamp", ""));
    const host = safeGet(a, "host", "");
    const svc  = safeGet(a, "service", safeGet(a, "svc", ""));
    const msg  = (safeGet(a, "message", "") || "").replace(/\n/g, " ");

    tr.innerHTML = `
      <td>${escapeHtml(ts)}</td>
      <td>${escapeHtml(host)}</td>
      <td>${escapeHtml(svc)}</td>
      <td style="max-width:600px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;"
          title="${escapeHtml(msg)}">
        ${escapeHtml(msg)}
      </td>
      <td>${probBadge}</td>
    `;

    tbody.appendChild(tr);
  }
}



/* Chart */

// ---------- Dataset Upload (CSV) ----------
function wireUpload() {
  // --- Grab elements ---
  const btn = document.getElementById("uploadBtn");
  const input = document.getElementById("uploadInput");

  // --- Hard guard for missing elements ---
  if (!btn || !input) {
    console.warn("wireUpload: missing uploadBtn or uploadInput; skipping initialization.");
    return;
  }

  // --- Button click triggers file picker ---
  btn.addEventListener("click", () => {
    try {
      input.click();
    } catch (err) {
      console.error("Upload button click failed:", err);
    }
  });

  // --- File change handler ---
  input.addEventListener("change", async () => {
    const file = input.files && input.files[0];
    if (!file) return;

    // --- Validate extension ---
    if (!file.name.toLowerCase().endsWith(".csv")) {
      notify("Upload failed", "Please select a .csv file", true);
      input.value = "";
      return;
    }

    try {
      const fd = new FormData();
      fd.append("file", file);

      const res = await fetch("/api/datasets/upload", { method: "POST", body: fd });
      let data = {};
      try { data = await res.json(); } catch (_) {}

      if (!res.ok || !(data.ok || data.status === "ok")) {
        const msg = (data && (data.error || data.message)) || `HTTP ${res.status}`;
        notify("Upload failed", String(msg), true);
      } else {
        const rows = data.rows_added != null ? data.rows_added : "N/A";
        notify("Dataset uploaded", `Added ${rows} rows from ${file.name}`);

        // --- Refresh dashboard cleanly ---
        if (typeof refresh === "function") {
          refresh();
        } else {
          // fallback calls if refresh() is missing
          if (typeof fetchStats === "function") await fetchStats();
          if (typeof fetchAnomalies === "function") await fetchAnomalies();
          if (typeof fetchAnomaliesTable === "function") await fetchAnomaliesTable();
        }
      }
    } catch (err) {
      console.error("Upload error:", err);
      notify("Upload error", String(err), true);
    } finally {
      input.value = ""; // allow reupload of same file later
    }
  });
}


// Minimal notification helper (uses your toast if available, else alert)
function notify(title, message, isError = false) {
  if (typeof showToast === "function") {
    showToast(title, message, isError ? "error" : "info", 6000);
  } else {
    // very simple fallback; replace with your UI toast later if you wish
    console[(isError ? "error" : "log")](title + ": " + message);
    if (isError) alert(title + ": " + message);
  }
}

// Ensure this runs on page load





function updateChart(anomalies = []) {
  // Ensure the canvas + chart exist
  const canvas = document.getElementById("anomalyChart");
  if (!canvas) return;

  // Get existing chart instance
  const ch = window.anomalyChart || (Chart.getChart ? Chart.getChart(canvas) : null);
  if (!ch) return;

  // ---------- CONFIG ----------
  const WINDOW_MINUTES = 10;

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
  const OFFSET_MS = (typeof activeTimezone !== "undefined" && activeTimezone === "IST")
    ? (5.5 * 60 * 60 * 1000)
    : 0;

  // Display time (UTC or IST)
  const displayNow = new Date(nowUTC.getTime() + OFFSET_MS);

  // ---------- BUILD EMPTY MINUTE BUCKETS ----------
  const buckets = {};
  const labels = [];

  for (let i = WINDOW_MINUTES - 1; i >= 0; i--) {
    const d = new Date(displayNow.getTime() - i * 60 * 1000);

    const label =
      `${String(d.getHours()).padStart(2, "0")}:` +
      `${String(d.getMinutes()).padStart(2, "0")} ` +
      `${activeTimezone || "UTC"}`;

    buckets[label] = 0;
    labels.push(label);
  }

  // Rolling window start (ALWAYS in UTC for correctness)
  const windowStartUTC = new Date(nowUTC.getTime() - WINDOW_MINUTES * 60 * 1000);

  // ---------- FILL BUCKETS FROM REAL DATA ----------
  for (const a of anomalies) {
    const ts = a?.detected_at || a?.timestamp || "";
    if (!ts) continue;

    const dUTC = new Date(ts);
    if (Number.isNaN(dUTC.getTime())) continue;

    // Ignore anomalies outside rolling window (UTC comparison)
    if (dUTC < windowStartUTC || dUTC > nowUTC) continue;

    // Convert to display timezone
    const dDisplay = new Date(dUTC.getTime() + OFFSET_MS);

    const label =
      `${String(dDisplay.getHours()).padStart(2, "0")}:` +
      `${String(dDisplay.getMinutes()).padStart(2, "0")} ` +
      `${activeTimezone || "UTC"}`;

    if (label in buckets) {
      buckets[label] += 1;
    }
  }

  // ---------- UPDATE CHART ----------
  if (!ch.data) ch.data = { labels: [], datasets: [] };
  if (!Array.isArray(ch.data.datasets)) ch.data.datasets = [];
  if (!ch.data.datasets[0]) {
    ch.data.datasets[0] = { label: "Anomalies", data: [] };
  }

  ch.data.labels = labels;
  ch.data.datasets[0].data = labels.map(l => buckets[l]);

  if (typeof ch.update === "function") ch.update();
}


/* -------------------- Donut: Anomalies by Service -------------------- */




/* update donut with anomalies array */
/* ---------- Drill-down: service summary + filtered table (Option 1) ---------- */

// holds last fetched anomalies (updated inside fetchAnomalies)


/* Call this in fetchAnomalies() after anomalies is normalized:
     latestAnomalies = anomalies;
   (I'll include exact placement below in case you want to copy it)
*/

/* applyServiceFilter(serviceName)
   Renders table with only that service's anomalies and shows a summary banner.
*/
function applyServiceFilter(serviceName) {
  // defensive
  if (!serviceName) return;

  // use latestAnomalies to compute stats (falls back to table DOM if empty)
  const source = Array.isArray(latestAnomalies) ? latestAnomalies : [];
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
  renderTable(filtered);

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
function clearServiceFilter() {
  // remove summary if present
  const existing = document.getElementById("serviceSummary");
  if (existing) existing.remove();

  // render full table from latestAnomalies
  if (Array.isArray(latestAnomalies)) {
    renderTable(latestAnomalies);
  } else {
    // fallback: try to re-fetch anomalies if we don't have them
    fetchAnomalies();
  }
}

/* show a hint/button to clear filter (non-destructive)
   Creates a small floating button near table header if not present. */
function showClearFilterHint() {
  if (document.getElementById("clearFilterBtn")) return;
  const container = document.querySelector(".table-card");
  if (!container) return;
  const btn = document.createElement("button");
  btn.id = "clearFilterBtn";
  btn.textContent = "Clear filter";
  btn.style.position = "absolute";
  btn.style.right = "22px";
  btn.style.top = "18px";
  btn.style.padding = "6px 10px";
  btn.style.borderRadius = "8px";
  btn.style.border = "none";
  btn.style.cursor = "pointer";
  btn.style.background = "#2ca874";
  btn.style.color = "#fff";
  btn.style.boxShadow = "0 8px 20px rgba(0,0,0,0.25)";
  btn.onclick = function() {
    clearServiceFilter();
    btn.remove();
  };
  container.style.position = "relative";
  container.appendChild(btn);
}



/* refresh loop */
function refresh() {
  fetchStats();
  fetchAnomalies();
}

/*Default = Live (no change in current behaviour
Switch to All or Uploads when needed.*/
 // default keeps your live view pure
 // -------------------------
// Source filtering + fetch glue
// -------------------------

// Default keeps your live view pure. (Change to "uploads" once if you want to
// quickly verify the Uploads view without adding live lines.)
let currentSource = "all";



/** Build query string from current filters (we'll extend later with host/time). */
function getQueryParams() {
  const p = new URLSearchParams();
  if (currentSource && currentSource !== "all") p.set("source", currentSource);
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





/** Fetch stats and update tiles + big number + donut (uses your existing DOM ids). */

// Lightweight refresher used after uploads (table + big number only)
async function fetchAnomaliesTable() {
  try {
    const res = await fetch(buildUrl("/api/anomalies?limit=50"));
    if (!res.ok) throw new Error(`anomalies fetch failed: ${res.status}`);
    const data = await res.json();

    // Normalize
    let anomalies = [];
    if (Array.isArray(data)) anomalies = data;
    else if (Array.isArray(data.anomalies)) anomalies = data.anomalies;
    else if (Array.isArray(data.results)) anomalies = data.results;
    else if (Array.isArray(data.data)) anomalies = data.data;
    else {
      for (const k of Object.keys(data || {})) {
        if (Array.isArray(data[k])) { anomalies = data[k]; break; }
      }
    }

    // Newest first for consistent table ordering
    anomalies.sort((a, b) => {
      const ta = Date.parse(a?.detected_at || a?.timestamp || 0) || 0;
      const tb = Date.parse(b?.detected_at || b?.timestamp || 0) || 0;
      return tb - ta;
    });

    // Table
    const tbody = document.querySelector("#anomaliesTable tbody");
    if (tbody) {
      tbody.innerHTML = "";
      for (const a of anomalies) {
        const prob = a?.prob_anomaly == null ? "" : Number(a.prob_anomaly).toFixed(2);
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td>${a?.timestamp || a?.detected_at || ""}</td>
          <td>${a?.host || ""}</td>
          <td>${a?.service || ""}</td>
          <td>${a?.message || ""}</td>
          <td>${prob}</td>
        `;
        tbody.appendChild(tr);
      }
    }

    // Big number
    const big = document.getElementById("bigNumber");
    if (big) big.textContent = anomalies.length;

  } catch (err) {
    console.error("fetchAnomaliesTable error:", err);
  }
}




/** Wire the segmented control (Live | All | Uploads). */
function wireSourceSwitch() {
  const el = document.getElementById("sourceSwitch");
  if (!el) return;
  el.querySelectorAll(".seg-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
      // toggle active UI state
      el.querySelectorAll(".seg-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");

      // set filter + refresh
      currentSource = btn.dataset.src || "all";
      await fetchStats();
      await fetchAnomalies();
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

    // initial data fetches (stats first, then anomalies)
    try { if (typeof fetchStats === "function") await fetchStats(); } catch (e) {
      console.error("fetchStats failed:", e);
    }
    try { if (typeof fetchAnomalies === "function") await fetchAnomalies(); } catch (e) {
      console.error("fetchAnomalies failed:", e);
    }

    // optional periodic refresh ( can be enabled later once stablity test has been done )
     if (typeof refresh === "function") setInterval(refresh, 5000);

  } catch (e) {
    console.error("startup error:", e);
  }
});

if (window.serviceDonutChart && stats.by_service) {
  window.serviceDonutChart.data.labels = Object.keys(stats.by_service);
  window.serviceDonutChart.data.datasets[0].data = Object.values(stats.by_service);
  window.serviceDonutChart.update();
}

 // Toggle Latest Anomalies (Show more / Show less)
const toggleBtn = document.getElementById("toggleAnomaliesBtn");

if (toggleBtn) {
  toggleBtn.addEventListener("click", () => {
    anomaliesExpanded = !anomaliesExpanded;
    toggleBtn.innerText = anomaliesExpanded ? "Show less" : "Show more";

    // Re-render anomalies table
    fetchAnomalies();
  });
}

