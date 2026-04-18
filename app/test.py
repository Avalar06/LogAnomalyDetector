import os
import pandas as pd
import csv
import sys
from datetime import datetime
from pathlib import Path    
from flask import Flask, jsonify, render_template, request, send_from_directory
import joblib
import io
import threading, time, re
from datetime import datetime, timezone


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

#-----------------------------------------
from src.anomaly_writer import AnomalyWriter




# ================= LOG PATHS  =================
LOG_DIR = PROJECT_ROOT / "logs"
ANOMALY_LOG = LOG_DIR / "anomalies_log.csv"
LIVE_LOG = LOG_DIR / "live_system.log"
SAMPLE_LOG = LOG_DIR / "sample.log"
# ======================================================




def _to_str(v):
    """Convert pandas Timestamp/NaT/datetime to plain string for JSON."""
    if v is None:
        return ""
    if isinstance(v, pd.Timestamp):
        if pd.isna(v):
            return ""
        return v.isoformat()
    if isinstance(v, datetime):
        return v.isoformat()
    try:
        # catches NaN/NaT in non-Timestamp columns
        if pd.isna(v):
            return ""
    except Exception:
        pass
    return str(v)


# create the Flask app BEFORE defining routes
app = Flask(__name__)
# ✅ SINGLE GLOBAL anomaly writer 
anomaly_writer = AnomalyWriter()

# -------------------------------
# Canonical project base
# -------------------------------
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# -------------------------------
# Datasets directory (uploads)
# -------------------------------
DATASETS_DIR = os.path.join(BASE_DIR, "data", "datasets")

# -------------------------------
# Logs directory (root-level)
# -------------------------------
LOGS_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOGS_DIR, exist_ok=True)

# -------------------------------
# Canonical anomalies file
# -------------------------------
ANOMALIES_CSV = os.path.join(LOGS_DIR, "anomalies_log.csv")

# -------------------------------
# Meta file for uploads
# -------------------------------
META_FILE = os.path.join(DATASETS_DIR, "datasets_meta.json")

# -------------------------------
# Watched live log paths
# -------------------------------
DEFAULT_WATCH_PATHS = f"{SAMPLE_LOG},{LIVE_LOG}"
WATCH_PATHS = os.environ.get("LIVE_LOG_PATHS", DEFAULT_WATCH_PATHS).split(",")
WATCH_PATHS = [p.strip() for p in WATCH_PATHS if p.strip()]

def _read_anomalies_unified():
    rows = []
    try:
        if os.path.exists(ANOMALIES_CSV):
            df = pd.read_csv(
                ANOMALIES_CSV,
                keep_default_na=False,
                on_bad_lines="skip",
                engine="python"
            )
            rows.extend(df.to_dict(orient="records"))
    except Exception as e:
        print(f"[warn] failed reading ANOMALIES_CSV: {e}")
    return rows



# Ensure folders exist
os.makedirs(DATASETS_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

# --- Ensure anomalies_log.csv exists ---
if not os.path.exists(ANOMALIES_CSV):
    pd.DataFrame(columns=[
        "detected_at","timestamp","host","service","message",
        "prob_anomaly","is_anomaly_pred","model","pid","source"
    ]).to_csv(ANOMALIES_CSV, index=False, encoding="utf-8")




# --- Minimal realtime detector (keyword score) ---
KEYWORDS = [
    "failed", "error", "unauthorized", "denied", "timeout",
    "segfault", "panic", "refused", "invalid"
]

def quick_score(msg: str) -> float:
    """
    Heuristic score in [0,1].
    Base=0.40, +0.08 per matched keyword, +0.30 bonus for 'failed password'.
    """
    m = (msg or "").lower()
    score = 0.40 + 0.08 * sum(1 for kw in KEYWORDS if kw in m)
    if "failed password" in m:
        score += 0.30
    return float(min(0.99, score))


def parse_syslog_time(line: str) -> str:
    """Try 'Oct 08 12:40:01 ...' → ISO UTC; else fallback to now."""
    try:
        months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
        mon = line[0:3]; day = int(line[4:6].strip()); hh,mm,ss = map(int, line[7:15].split(":"))
        now = datetime.now(timezone.utc)
        dt = datetime(now.year, months.index(mon)+1, day, hh, mm, ss, tzinfo=timezone.utc)
        return dt.isoformat()
    except Exception:
        return datetime.now(timezone.utc).isoformat()


import json
from datetime import datetime, timezone

def process_log_line(line: str, source="live"):
    msg = (line or "").strip()
    if not msg:
        return

    # Debug: show every line picked up by the tailer
    print(f"[debug] raw tail line: {msg}")

    # --- Step 1: Try JSON logs first ---
    if msg.startswith("{") and msg.endswith("}"):
        try:
            data = json.loads(msg)
            ts = data.get("timestamp") or data.get("detected_at") or datetime.now(timezone.utc).isoformat()
            host = data.get("host", "unknown")
            service = data.get("service", "unknown")
            message = data.get("message", "")
            prob_anomaly = float(data.get("prob_anomaly", 0.0))
            source = data.get("source", "upload")

            is_anom = 1 if prob_anomaly >= 0.60 else 0

            if is_anom:
                anomaly_writer.append_anomaly({
                    "detected_at": datetime.now(timezone.utc).isoformat(),
                    "timestamp": ts,
                    "host": host,
                    "service": service,
                    "message": message,
                    "prob_anomaly": prob_anomaly,
                    "is_anomaly_pred": 1,
                    "model": "realtime",
                    "pid": 0,
                    "source": source,
                    })

                print(f"[process_log_line] added JSON anomaly: {host} | {service} | {prob_anomaly}")
            else:
                print(f"[process_log_line] JSON line below threshold: {prob_anomaly}")
            return  # stop here; no need to go to syslog parsing
        except Exception as e:
            print(f"[process_log_line] JSON parse error: {e}")
            # Fall through to syslog handling

    # --- Step 2: Handle regular syslog/plaintext lines ---
    svc = ("sshd" if ("sshd" in msg or "ssh" in msg)
           else "httpd" if any(x in msg for x in ["httpd", "nginx", "apache"])
           else "system")
    host = "host"  # You can enhance this to extract from msg later
    ts = parse_syslog_time(msg)

    prob = quick_score(msg)
    is_anom = 1 if prob >= 0.60 else 0  # your existing threshold

    if is_anom:
        now_iso = datetime.now(timezone.utc).isoformat()
        anomaly_writer.append_anomaly({
    "detected_at": now_iso,
    "timestamp": ts,
    "host": host,
    "service": svc,
    "message": msg,
    "prob_anomaly": prob,
    "is_anomaly_pred": 1,
    "model": "realtime",
    "pid": 0,
    "source": source,  # ← uses function arg
})

        print(f"[process_log_line] added syslog anomaly: {svc} | {prob}")
    else:
        print(f"[process_log_line] normal syslog line: {svc} | {prob}")



def start_log_tailer(log_path):
    """Start a background thread that tails a single log file and processes new lines."""
    def _follow():
        # wait until file exists, then tail
        while not os.path.exists(log_path):
            time.sleep(0.5)
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            f.seek(0, os.SEEK_END)  # start at end of file
            while True:
                line = f.readline()
                if not line:
                    time.sleep(0.3)
                    continue
                try:
                    process_log_line(line)
                except Exception as e:
                    print(f"[tailer] line error in {os.path.basename(log_path)}:", e)

    # start each file tailer in its own thread
    t = threading.Thread(target=_follow, daemon=True)
    t.start()
    print(f"[tailer] watching: {log_path}")


# ---------------------------------------------------------------------------
# Start tailers for multiple log files at launch (sample.log + live_system.log)





#======routes===
@app.route("/api/test/anomaly")
def test_anomaly():
    fake_line = "[2025-12-13 23:20:00] CRITICAL: LIVE TEST root compromise detected"
    process_log_line(fake_line)
    return jsonify({"status": "test anomaly injected"})



# favicon route — returns 204 No Content (no file needed)
@app.route('/favicon.ico')
def favicon():
    # If you prefer to serve an actual file, return send_from_directory(...) as discussed.
    # Returning 204 prevents browser 404 spam without needing a favicon file.
    from flask import Response
    return Response(status=204)


# --- now other globals & config ---
ANOMALY_CSV_PATH = str(ANOMALY_LOG)
MODEL_PATH = str(PROJECT_ROOT / "models" / "best_model.joblib")


@app.route('/api/simulate_anomaly', methods=['POST'])
def simulate_anomaly():
    """
    Append a simulated anomaly row to the anomalies CSV so /api/anomalies returns it.
    Accepts JSON body (optional) with keys: host, service, message, prob_anomaly, pid, model
    """
    body = request.get_json(silent=True) or {}
    now_iso = datetime.utcnow().isoformat() + "Z"
    anomaly = {
        "detected_at": now_iso,
        "timestamp": now_iso,
        "host": body.get("host", "kali"),
        "is_anomaly_pred": 1,
        "message": body.get("message", "Simulated anomaly for toast test"),
        "model": body.get("model", "rf_v1"),
        "pid": int(body.get("pid", 9999)),
        "prob_anomaly": float(body.get("prob_anomaly", 0.95)),
        "service": body.get("service", "testsvc")
    }

    # ensure logs dir exists
    os.makedirs(os.path.dirname(ANOMALY_CSV_PATH), exist_ok=True)

    # If file doesn't exist, create and write header with our chosen field order
    fieldnames = ["detected_at","timestamp","host","is_anomaly_pred","message","model","pid","prob_anomaly","service"]
    write_header = not os.path.exists(ANOMALY_CSV_PATH)
    try:
        with open(ANOMALY_CSV_PATH, "a", newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore', quoting=csv.QUOTE_MINIMAL)
            if write_header:
                writer.writeheader()
            writer.writerow(anomaly)
    except Exception as e:
        return jsonify({"status":"error","error": str(e)}), 500

    return jsonify({"status":"ok", "anomaly": anomaly}), 201

_last_mtime = None
_cache = None


# --------------------
# ---------- Filtering helpers (non-breaking) ----------
def _parse_time_utc(s: str):
    """Parse an ISO-like timestamp to tz-aware UTC; return None if invalid."""
    try:
        return pd.to_datetime(s, errors="coerce", utc=True)
    except Exception:
        return None

def _apply_filters(df: pd.DataFrame, args) -> pd.DataFrame:
    """
    Apply optional filters based on query params.
    Accepted params (all optional, non-breaking):
      - source: 'live' | 'uploads' | 'all'
      - service: exact match (case-insensitive)
      - host: exact match (case-insensitive)
      - from / start: ISO datetime (inclusive, compares to detected_at)
      - to   / end:   ISO datetime (inclusive, compares to detected_at)
    If none provided → returns df unchanged.
    """
    if df.empty:
        return df

    df = df.copy()

    # -------------------------------------------------
    # Ensure required columns exist
    # -------------------------------------------------
    for col in ["service", "host", "source", "detected_at", "timestamp"]:
        if col not in df.columns:
            df[col] = ""

    # -------------------------------------------------
    # Normalize basic string columns
    # -------------------------------------------------
    df["service"] = df["service"].fillna("").astype(str).str.strip()
    df["host"]    = df["host"].fillna("").astype(str).str.strip()
    df["source"]  = df["source"].fillna("").astype(str).str.strip()

    # -------------------------------------------------
    # Ensure we have a proper datetime column to filter on
    # -------------------------------------------------
    if pd.api.types.is_datetime64_any_dtype(df.get("detected_at")):
        ts_col = "detected_at"
    else:
        # Try parsing detected_at first, then fallback to timestamp
        df["detected_at"] = pd.to_datetime(df.get("detected_at"), errors="coerce", utc=True)
        if df["detected_at"].isna().all() and "timestamp" in df.columns:
            df["detected_at"] = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
        ts_col = "detected_at"

    # -------------------------------------------------
    # Apply filters (ONLY ONCE, CLEAN PASS)
    # -------------------------------------------------

    # --- Source filter ---
    source = (args.get("source") or "").lower().strip()
    if source == "live":
        df = df[df["source"] == "live"]
    elif source == "uploads":
        df = df[df["source"].str.startswith("upload:")]
    elif source in ("all", ""):
        pass  # no filter
    else:
        pass  # unknown selector → no filter

    # --- Service filter ---
    svc = (args.get("service") or "").strip()
    if svc:
        df = df[df["service"].str.casefold() == svc.casefold()]

    # --- Host filter ---
    host = (args.get("host") or "").strip()
    if host:
        df = df[df["host"].str.casefold() == host.casefold()]

    # --- Time window filter (inclusive) ---
    frm = args.get("from") or args.get("start")
    to  = args.get("to")   or args.get("end")

    if frm:
        t0 = _parse_time_utc(frm)
        if t0 is not None:
            df = df[df[ts_col] >= t0]

    if to:
        t1 = _parse_time_utc(to)
        if t1 is not None:
            df = df[df[ts_col] <= t1]

    return df

#---------------------------------


# -----------------------
# Robust anomaly reader
# -----------------------
def _read_anomalies():
    """
    Canonical robust reader for anomalies_log.csv

    Guarantees:
    - Never drops valid columns silently
    - Never corrupts detected_at
    - Preserves ingestion time correctly
    - Produces dashboard-compatible records
    """

    global _last_mtime, _cache

    if not os.path.exists(ANOMALY_CSV_PATH):
        return []

    try:
        mtime = os.path.getmtime(ANOMALY_CSV_PATH)
    except Exception:
        return []

    # Cache check
    if _cache is not None and _last_mtime == mtime:
        return _cache or []

    # --- 1. Read CSV robustly ---
    try:
        df = pd.read_csv(
            ANOMALY_CSV_PATH,
            engine="python",
            dtype=str,
            keep_default_na=False,
            skip_blank_lines=True,
            on_bad_lines="skip"
        )
    except Exception as e:
        app.logger.warning("Failed to read anomalies CSV: %s", str(e))
        return []

    if df.empty:
        _cache = []
        _last_mtime = mtime
        return []

    # --- 2. Normalize column names safely ---
    df.columns = [c.strip() for c in df.columns]

    # --- 3. Remove duplicate header rows ---
    def is_header_like(row):
        try:
            return all(str(row[c]).strip() == c for c in df.columns)
        except Exception:
            return False

    mask = df.apply(is_header_like, axis=1)
    if mask.any():
        df = df.loc[~mask].copy()

    # --- 4. Drop fully empty rows ---
    df = df.replace("", pd.NA).dropna(how="all").fillna("")

    # --- 5. Ensure required columns exist (DO NOT reorder yet) ---
    REQUIRED_COLS = [
        "timestamp",
        "detected_at",
        "host",
        "service",
        "message",
        "prob_anomaly",
        "is_anomaly_pred",
        "pid",
        "model",
        "source",
    ]

    for col in REQUIRED_COLS:
        if col not in df.columns:
            df[col] = ""

    # --- 6. Clean message ---
    df["message"] = (
        df["message"]
        .astype(str)
        .str.strip()
        .str.replace(r"\s+", " ", regex=True)
    )

    MAX_MSG_LEN = 8000
    df["message"] = df["message"].apply(
        lambda s: s if len(s) <= MAX_MSG_LEN else s[:MAX_MSG_LEN] + " ...[truncated]"
    )

    # --- 7. Parse datetimes correctly (NO overwriting with now blindly) ---
    for col in ("timestamp", "detected_at"):
        df[col] = pd.to_datetime(df[col], errors="coerce", utc=True)

    # If detected_at missing, fallback to timestamp per row
    mask_na = df["detected_at"].isna()
    df.loc[mask_na, "detected_at"] = df.loc[mask_na, "timestamp"]

    # Final fallback: ONLY for rows where both are NaT
    mask_still_na = df["detected_at"].isna()
    df.loc[mask_still_na, "detected_at"] = pd.Timestamp.now(tz="UTC")

    # --- 8. Convert numeric columns safely ---
    df["prob_anomaly"] = pd.to_numeric(df["prob_anomaly"], errors="coerce").fillna(0.0)
    df["is_anomaly_pred"] = pd.to_numeric(df["is_anomaly_pred"], errors="coerce").fillna(0).astype(int)
    df["pid"] = pd.to_numeric(df["pid"], errors="coerce").fillna(-1).astype(int)

    # --- 9. Drop true garbage rows ---
    df = df[
        ~(
            (df["message"].astype(str).str.strip() == "")
            & (df["host"].astype(str).str.strip() == "")
        )
    ].copy()

    # --- 10. Sort newest first ---
    df = df.sort_values(by="detected_at", ascending=False)

    # --- 11. Convert datetimes to ISO UTC strings ---
    for col in ("timestamp", "detected_at"):
        df[col] = (
            pd.to_datetime(df[col], utc=True, errors="coerce")
            .dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            .fillna("")
        )

    # --- 12. Reorder columns ONLY at the very end ---
    df = df[REQUIRED_COLS]

    # --- 13. Final output ---
    records = df.to_dict(orient="records")

    _cache = records
    _last_mtime = mtime
    return _cache or []



# -----------------------
def normalize_dataframe(df_raw: pd.DataFrame, source_tag: str) -> pd.DataFrame:
    """
    Normalize uploaded CSV to the canonical schema used by the dashboard.
    Final columns (in order):
      detected_at, timestamp, host, service, message,
      prob_anomaly, is_anomaly_pred, model, pid, source
    We are lenient with input column names.
    """
    df = df_raw.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]

    # Loose mappings to canonical names
    colmap = {
        "time": "timestamp", "ts": "timestamp", "datetime": "timestamp", "date": "timestamp",
        "host_name": "host", "hostname": "host",
        "svc": "service", "service_name": "service", "process": "service",
        "msg": "message", "log": "message", "text": "message", "event": "message",
        "score": "prob_anomaly", "prob": "prob_anomaly", "probability": "prob_anomaly",
        "anomaly_prob": "prob_anomaly", "anomaly_score": "prob_anomaly"
    }
    for old, new in colmap.items():
        if old in df.columns and new not in df.columns:
            df.rename(columns={old: new}, inplace=True)

    # Ensure required text columns
    for required in ["timestamp", "host", "service", "message"]:
        if required not in df.columns:
            df[required] = ""

    # Probability column (0..1)
    if "prob_anomaly" not in df.columns:
        df["prob_anomaly"] = 0.95

    def to_prob(x):
        try:
            v = float(x)
            if v > 1.0:  # treat 97 → 0.97
                v = v / 100.0
            return max(0.0, min(1.0, v))
        except Exception:
            return 0.95

    df["prob_anomaly"] = df["prob_anomaly"].apply(to_prob)

    # Timestamps → ISO Z
    def to_iso(x):
        try:
            return pd.to_datetime(x, errors="coerce", utc=True).isoformat()
        except Exception:
            return pd.Timestamp.now(tz="UTC").isoformat()

    df["timestamp"] = df["timestamp"].apply(to_iso)
    if "detected_at" not in df.columns:
        df["detected_at"] = df["timestamp"]

    # -------------------------------
    # 🔧 FIXED LABEL HANDLING LOGIC
    # -------------------------------
    if "true_label" in df.columns:
        # Upload is label-driven
        df["is_anomaly_pred"] = df["true_label"].astype(int)
    elif "is_anomaly_pred" in df.columns:
        # Already present, keep it but coerce to int
        df["is_anomaly_pred"] = df["is_anomaly_pred"].astype(int)
    else:
        # Default: normal
        df["is_anomaly_pred"] = 0

    # Other canonical fields with defaults
    if "model" not in df.columns:
        df["model"] = "upload"
    if "pid" not in df.columns:
        df["pid"] = 0

    df["source"] = source_tag  # e.g., "upload:filename.csv"

    cols = [
        "detected_at", "timestamp", "host", "service", "message",
        "prob_anomaly", "is_anomaly_pred", "model", "pid", "source"
    ]
    for c in cols:
        if c not in df.columns:
            df[c] = ""

    return df[cols]





# Routes
# Routes
@app.post("/api/datasets/upload")
def upload_dataset():
    """
    Accepts a CSV file, normalizes it, appends to anomalies_log.csv,
    and saves the original file under data/datasets/.
    Returns a JSON summary (rows added, filename, dataset_count).
    """
    import json

    # --- Validate request ---
    if "file" not in request.files:
        return jsonify({"ok": False, "error": "No file field named 'file' in form-data"}), 400

    f = request.files["file"]
    if not f or not f.filename:
        return jsonify({"ok": False, "error": "No file selected"}), 400

    if not f.filename.lower().endswith(".csv"):
        return jsonify({"ok": False, "error": "Only CSV files are supported"}), 400

    # --- Save original upload copy (timestamped) ---
    ts_tag = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    safe_name = f.filename.replace(" ", "_")
    saved_name = f"{ts_tag}__{safe_name}"
    os.makedirs(DATASETS_DIR, exist_ok=True)
    saved_path = os.path.join(DATASETS_DIR, saved_name)

    # Save the uploaded file to disk
    f.seek(0)
    f.save(saved_path)

    # --- Read CSV and normalize to canonical schema ---
    try:
        # tolerant read; skips bad rows instead of failing
        df_raw = pd.read_csv(saved_path, encoding="utf-8", on_bad_lines="skip")
    except Exception as e:
        return jsonify({"ok": False, "error": f"Failed to read CSV: {e}"}), 400

    try:
        df_norm = normalize_dataframe(df_raw, source_tag=f"upload:{safe_name}")
    except Exception as e:
        return jsonify({"ok": False, "error": f"Normalization failed: {e}"}), 500

    # ------------------------------------------------
    # 🔎 TEMP DEBUG: Verify label distribution ONCE
    # ------------------------------------------------
    try:
        print("UPLOAD LABEL CHECK:")
        print(df_norm["is_anomaly_pred"].value_counts())
    except Exception as e:
        print(f"[warn] label check failed: {e}")

    # --- Append to anomalies_log.csv (create with header if new/empty) ---
    try:
        write_header = True
        if os.path.exists(ANOMALIES_CSV):
            try:
                # if file exists and is non-empty, don't write header
                write_header = os.path.getsize(ANOMALIES_CSV) == 0
            except Exception:
                write_header = False  # be conservative
            mode = "a"
        else:
            os.makedirs(os.path.dirname(ANOMALIES_CSV), exist_ok=True)
            mode = "w"
            write_header = True

        df_norm.to_csv(
            ANOMALIES_CSV,
            index=False,
            mode=mode,
            header=write_header,
            encoding="utf-8"
        )
    except Exception as e:
        return jsonify({"ok": False, "error": f"Failed to append to anomalies log: {e}"}), 500

    # --- Update meta counter (datasets analyzed) ---
    datasets_count = None
    try:
        meta = {"datasets_analyzed": 0, "files": []}
        if os.path.exists(META_FILE):
            with open(META_FILE, "r", encoding="utf-8") as m:
                meta = json.load(m)
        meta["datasets_analyzed"] = int(meta.get("datasets_analyzed", 0)) + 1
        meta["files"].append({
            "name": saved_name,
            "rows": int(len(df_norm)),
            "added_at": ts_tag
        })
        with open(META_FILE, "w", encoding="utf-8") as m:
            json.dump(meta, m, indent=2)
        datasets_count = meta["datasets_analyzed"]
    except Exception:
        # do not fail upload if meta write has an issue
        pass

    return jsonify({
        "ok": True,
        "file_saved": saved_name,
        "rows_added": int(len(df_norm)),
        "datasets_analyzed": datasets_count
    }), 201



# -----------------------

@app.route("/")
def index():
    return render_template("index.html")

#----------------------------to accept filters--------
@app.route("/api/anomalies")
def api_anomalies():
    # --- 1. Read anomalies using the canonical reader ---
    rows = _read_anomalies()
    df = pd.DataFrame(rows)

    if not df.empty:

        # --- 2. Ensure is_anomaly_pred is numeric 0/1 ---
        if "is_anomaly_pred" in df.columns:
            df["is_anomaly_pred"] = pd.to_numeric(
                df["is_anomaly_pred"], errors="coerce"
            ).fillna(0).astype(int)
        else:
            df["is_anomaly_pred"] = 0

        # --- 3. Parse detected_at safely BEFORE filtering ---
        if "detected_at" in df.columns:
            df["detected_at"] = pd.to_datetime(df["detected_at"], errors="coerce", utc=True)
        elif "timestamp" in df.columns:
            df["detected_at"] = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
        else:
            df["detected_at"] = pd.NaT

        # Drop only rows where time is completely missing
        df = df.dropna(subset=["detected_at"])

        # --- 4. KEEP ONLY TRUE ANOMALIES (after normalization) ---
        df = df[df["is_anomaly_pred"] == 1].copy()

        # --- 5. Apply optional filters (host, service, source, time range) ---
        df = _apply_filters(df, request.args).copy()

        # --- 6. Sort newest first ---
        df = df.sort_values(by=["detected_at"], ascending=False)

    # --- 7. Optional limit ---
    try:
        limit = int(request.args.get("limit", 200))
        if limit > 0:
            df = df.head(limit)
    except Exception:
        pass

    # --- 8. Safe serializer ---
    def _to_str(v):
        if v is None:
            return ""
        if isinstance(v, pd.Timestamp):
            if pd.isna(v):
                return ""
            return v.strftime("%Y-%m-%dT%H:%M:%SZ")
        try:
            if pd.isna(v):
                return ""
        except Exception:
            pass
        return str(v)

    anomalies = []
    if not df.empty:
        for _, r in df.iterrows():
            anomalies.append({
                "detected_at":     _to_str(r.get("detected_at")),
                "timestamp":       _to_str(r.get("timestamp")),
                "host":            _to_str(r.get("host")),
                "service":         _to_str(r.get("service")),
                "message":         _to_str(r.get("message")),
                "prob_anomaly":    float(r.get("prob_anomaly")) if pd.notna(r.get("prob_anomaly")) else None,
                "is_anomaly_pred": int(r.get("is_anomaly_pred")) if pd.notna(r.get("is_anomaly_pred")) else 0,
                "model":           _to_str(r.get("model")),
                "pid": (
                    int(r.get("pid"))
                    if pd.notna(r.get("pid")) and str(r.get("pid")).isdigit()
                    else None
                ),
                "source":          _to_str(r.get("source")),
            })

    return jsonify({
        "anomalies": anomalies,
        "count": len(anomalies)
    })

#---------------------------------------


#--------------------------to mirror the same filters------------#

@app.route("/api/stats")
def api_stats():
    try:
        # --- 1. Use the canonical reader ---
        rows = _read_anomalies()
    except Exception as e:
        return jsonify(
            {"counts": {}, "by_service": {}, "error": f"read_failed: {e}"}
        ), 500

    import pandas as pd
    import json, os

    df = pd.DataFrame(rows)
    counts = {}
    by_service = {}

    now = pd.Timestamp.now(tz="UTC")

    if not df.empty:

        # --- 2. Normalize is_anomaly_pred safely ---
        if "is_anomaly_pred" in df.columns:
            df["is_anomaly_pred"] = pd.to_numeric(
                df["is_anomaly_pred"], errors="coerce"
            ).fillna(0).astype(int)
        else:
            df["is_anomaly_pred"] = 0

        # --- 3. Parse detected_at safely ---
        if "detected_at" in df.columns:
            df["detected_at"] = pd.to_datetime(
                df["detected_at"], errors="coerce", utc=True
            )
        elif "timestamp" in df.columns:
            df["detected_at"] = pd.to_datetime(
                df["timestamp"], errors="coerce", utc=True
            )
        else:
            df["detected_at"] = pd.NaT

        # Drop rows with invalid time
        df = df.dropna(subset=["detected_at"])

        # --- 4. KEEP ONLY TRUE ANOMALIES ---
        df = df[df["is_anomaly_pred"] == 1].copy()

        # ================= DEBUG (keep for now) =================
        print("[DEBUG stats] total TRUE anomalies:", len(df))
        if not df.empty:
            print("[DEBUG stats] newest detected_at:", df["detected_at"].max())
            print("[DEBUG stats] now (UTC):", now)
        # ========================================================

        # --- 5. Authoritative counters ---
        counts["total"] = int(len(df))

        counts["last_10_minutes"] = int(
            (df["detected_at"] >= now - pd.Timedelta(minutes=10)).sum()
        )

        counts["last_1_hour"] = int(
            (df["detected_at"] >= now - pd.Timedelta(hours=1)).sum()
        )

        counts["last_24_hours"] = int(
            (df["detected_at"] >= now - pd.Timedelta(hours=24)).sum()
        )

        # --- 6. Service breakdown (after anomaly filter) ---
        df_filtered = _apply_filters(df, request.args)

        if "service" in df_filtered.columns:
            by_service = (
                df_filtered["service"]
                .fillna("unknown")
                .astype(str)
                .str.strip()
                .value_counts()
                .to_dict()
            )

    # --- 7. Dataset counter (unchanged) ---
    try:
        datasets_analyzed = 0
        if os.path.exists(META_FILE):
            with open(META_FILE, "r", encoding="utf-8") as m:
                meta = json.load(m)
            datasets_analyzed = int(meta.get("datasets_analyzed", 0))
        counts["datasets_analyzed"] = datasets_analyzed
    except Exception:
        pass

    return jsonify({"counts": counts, "by_service": by_service})
