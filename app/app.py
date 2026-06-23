import os
import pandas as pd
import csv
import sys
from datetime import datetime
from pathlib import Path    
from flask import Flask, jsonify, render_template, request, send_from_directory
import joblib
import io
import json
import tempfile
import time
import threading, time, re
import  os, tempfile
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

#-----------------------------------



#----------------------------------------
def read_json_safe(filepath):
    if not os.path.exists(filepath):
        return {}

    try:
        with open(filepath, "r") as f:
            content = f.read().strip()
            if not content:
                return {}  # handles empty file
            return json.loads(content)
    except Exception as e:
        print("ERROR READING FILE:", e)
        return {}
    

    #--------------------------------------

def extract_feedback_dataset():
    feedback_file = "logs/feedback_log.json"
    dataset_rows = []

    feedback_data = read_json_safe(feedback_file)

    for entry in feedback_data:
        status = entry.get("action")
        message = entry.get("message", "").strip()

        if status == "closed":
            label = 1
        elif status == "false_positive":
            label = 0
        else:
            continue

        if message:
            dataset_rows.append({
                "message": message,
                "true_label": label
            })

    return dataset_rows


    #----------------------------------------


def write_feedback_dataset_to_csv():
    import csv
    import os

    dataset_rows = extract_feedback_dataset()

    if not dataset_rows:
        print("No valid feedback data to write.")
        return

    csv_path = os.path.join("data", "feedback_dataset_clean.csv")

    try:
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["message", "true_label"])
            writer.writeheader()
            writer.writerows(dataset_rows)

        print(f"[SUCCESS] Clean dataset written → {csv_path}")

    except Exception as e:
        print("CSV WRITE ERROR:", e)
    
#----------------------------------
def write_json_safe(filepath, data):
    temp_file = filepath + ".tmp"

    with open(temp_file, "w") as f:
        json.dump(data, f, indent=4)

    os.replace(temp_file, filepath)  # atomic replace
#---------------------------------------------------

# create the Flask app BEFORE defining routes
app = Flask(__name__)

@app.route("/api/anomalies/actions", methods=["GET"])
def get_anomaly_actions():
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(BASE_DIR, "logs", "anomaly_actions.json")

    actions = read_json_safe(file_path)
    return jsonify(actions)
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


from scipy.sparse import hstack
import numpy as np

def extract_structured_features(text):
    text = text.lower()  # ✅ ensure consistency
    return [
        len(text),
        sum(c.isdigit() for c in text),
        sum(not c.isalnum() for c in text),
        sum(c.isupper() for c in text),
        len(text.split()),
        int(bool(re.search(r'\b\d{1,3}(\.\d{1,3}){3}\b', text))),
        int("error" in text),
        int("warning" in text),
        int(bool(re.search(r'\b\d{3}\b', text)))
    ]


def transform_log_to_features(msg):
    msg = (msg or "").lower()  # ✅ normalize once
    X_tfidf = vectorizer.transform([msg])
    structured = np.array([extract_structured_features(msg)])
    return hstack([X_tfidf, structured])


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

            if prob_anomaly >= 0.85:
                severity = "HIGH"
            elif prob_anomaly >= 0.65:
                severity = "MEDIUM"
            else:
                severity = "LOW"

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
                    "severity": severity,
                })

                print(f"[process_log_line] added JSON anomaly: {host} | {service} | {prob_anomaly}")
            else:
                print(f"[process_log_line] JSON line below threshold: {prob_anomaly}")
            return

        except Exception as e:
            print(f"[process_log_line] JSON parse error: {e}")
            # fallback to syslog

    # --- Step 2: Handle regular syslog/plaintext lines ---
    svc = ("sshd" if ("sshd" in msg or "ssh" in msg)
           else "httpd" if any(x in msg for x in ["httpd", "nginx", "apache"])
           else "system")

    host = "host"
    ts = parse_syslog_time(msg)

    # ML-based probability (with safe fallback)
    try:
        start_time = time.perf_counter()
        X = transform_log_to_features(msg)
        prob = model.predict_proba(X)[0][1]
        end_time = time.perf_counter()
        latency_ms = (end_time - start_time) * 1000
        print(f"[LATENCY] {latency_ms:.4f} ms")
    except Exception as e:
        print(f"[ML ERROR] {e}")
        prob = quick_score(msg)
        

    is_anom = (
    1 if prob >= BEST_RF_THRESHOLD
    else 0
)
    if prob >= 0.85:
        severity = "HIGH"
    elif prob >= 0.65:
         severity = "MEDIUM"
    else:
        severity = "LOW"

    
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
            "source": source,
            "severity": severity,
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
@app.route("/api/feedback", methods=["POST"])
def api_feedback():
    from datetime import datetime
    import json
    import os
    import csv

    data = request.get_json()
    message = data.get("message", "")

    anomaly_id = data.get("anomaly_id")
    action = data.get("action")

    # -------------------------------
    # 🔹 Analyst label (from action)
    # -------------------------------
    label = 1  # default anomaly
    if action == "false_positive":
        label = 0

    # -------------------------------
    # 🔹 Suggested label (from frontend)
    # -------------------------------
    suggested_label = data.get("suggested_label")

    # normalize (safety)
    if suggested_label not in [0, 1]:
        suggested_label = None

    # -------------------------------
    # 🔹 Agreement logic
    # -------------------------------
    if suggested_label is None:
        agreement = None
    else:
        agreement = (label == suggested_label)

    # -------------------------------
    # 🔹 JSON ENTRY (existing system)
    # -------------------------------
    entry = {
        "anomaly_id": anomaly_id,
        "action": action,
        "message": message,
        "label": label,
        "suggested_label": suggested_label,
        "agreement": agreement,
        "timestamp": datetime.utcnow().isoformat()
    }

    log_path = os.path.join("logs", "feedback_log.json")

    # read existing
    if os.path.exists(log_path):
        try:
            with open(log_path, "r") as f:
                logs = json.load(f)
        except:
            logs = []
    else:
        logs = []

    logs.append(entry)

    # write JSON
    with open(log_path, "w") as f:
        json.dump(logs, f, indent=2)

    # ======================================================
    # 🔥 NEW: CSV DATASET (FOR TRAINING / FEEDBACK LOOP)
    # ======================================================

    csv_path = os.path.join("data", "feedback_dataset.csv")

    csv_row = {
        "anomaly_id": anomaly_id,
        "timestamp": entry["timestamp"],
        "action": action,
        "predicted_label": suggested_label,
        "analyst_label": label,
        "agreement": agreement
    }

    file_exists = os.path.isfile(csv_path)

    try:
        with open(csv_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=csv_row.keys())

            # write header only once
            if not file_exists:
                writer.writeheader()

            writer.writerow(csv_row)

    except Exception as e:
        print("CSV WRITE ERROR:", e)

    # ======================================================

    return jsonify({
        "status": "ok",
        "agreement": agreement
    })

#---------------------------


#----------------------------
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
VECTORIZER_PATH = str(PROJECT_ROOT / "models" / "tfidf_vectorizer.joblib")
THRESHOLD_PATH = str(
    PROJECT_ROOT / "models" / "best_rf_threshold.joblib"
)

print("Loading ML assets...")

model = joblib.load(MODEL_PATH)

vectorizer = joblib.load(VECTORIZER_PATH)

BEST_RF_THRESHOLD = joblib.load(
    THRESHOLD_PATH
)

print(
    f"✅ Model + Vectorizer + Threshold loaded "
    f"(Threshold={BEST_RF_THRESHOLD})"
)


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
    df["host"] = df["host"].fillna("").astype(str).str.strip()
    df["source"] = df["source"].fillna("").astype(str).str.strip()

    # -------------------------------------------------
    # Ensure we have a proper datetime column to filter on
    # -------------------------------------------------
    if pd.api.types.is_datetime64_any_dtype(df.get("detected_at")):
        ts_col = "detected_at"
    else:
        # Try parsing detected_at first, then fallback to timestamp
        df["detected_at"] = pd.to_datetime(
            df.get("detected_at"),
            errors="coerce",
            utc=True
        )

        if df["detected_at"].isna().all() and "timestamp" in df.columns:
            df["detected_at"] = pd.to_datetime(
                df["timestamp"],
                errors="coerce",
                utc=True
            )

        ts_col = "detected_at"

    # -------------------------------------------------
    # Apply filters (ONLY ONCE, CLEAN PASS)
    # -------------------------------------------------

    # --- Source filter ---
    source = (args.get("source") or "").lower().strip()

    if source and source != "all":
        
        normalized = source.lower().strip()
        df["source"] = (
        df["source"]
        .astype(str)
        .str.lower()
        .str.strip()
    )

# compatibility mapping
        df["source"] = df["source"].replace({
            "uploads": "upload"
        })

        df = df[df["source"] == normalized]


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
    to = args.get("to") or args.get("end")

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
    """

    global _last_mtime, _cache

    if not os.path.exists(ANOMALIES_CSV):
        return []

    try:
        mtime = os.path.getmtime(ANOMALIES_CSV)
    except Exception:
        return []

    # Cache check
# Cache temporarily disabled for debugging
# Cache check
    if _cache is not None and _last_mtime == mtime:
        return _cache or []

    # --- 1. Read CSV ---
    try:
        df = pd.read_csv(
            ANOMALIES_CSV,
        engine="python",
        dtype=str,
        keep_default_na=False,
        skip_blank_lines=True,
        on_bad_lines="skip",
        quotechar='"',
        sep=",",
        encoding="utf-8",
        index_col=False
        )
        # Force clean sequential index
        df.reset_index(drop=True, inplace=True)

    except Exception as e:
        app.logger.warning("Failed to read anomalies CSV: %s", str(e))
        return []

    if df.empty:
        _cache = []
        _last_mtime = mtime
        return []

    # --- 2. Normalize columns ---
    df.columns = [c.strip() for c in df.columns]

    # --- 3. Remove duplicate headers ---
    def is_header_like(row):
        try:
            return all(str(row[c]).strip() == c for c in df.columns)
        except Exception:
            return False

    mask = df.apply(is_header_like, axis=1)
    if mask.any():
        df = df.loc[~mask].copy()

    # --- 4. Drop empty rows ---
    df = df.replace("", pd.NA).dropna(how="all").fillna("")

    # --- 5. Ensure required columns exist ---
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
        "severity",
    ]

    for col in REQUIRED_COLS:
        if col not in df.columns:
            df[col] = ""

    # Severity default
    df["severity"] = df["severity"].replace("", "LOW").fillna("LOW")

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

    # --- 7. ✅ CRITICAL: Parse datetime safely (FIXED BLOCK) ---
    for col in ("timestamp", "detected_at"):
        df[col] = pd.to_datetime(
            df[col],
            errors="coerce",
            utc=True,

        )

    # --- 7.1 Fallback logic ---
    mask_na = df["detected_at"].isna()
    df.loc[mask_na, "detected_at"] = df.loc[mask_na, "timestamp"]

    mask_still_na = df["detected_at"].isna()
    df.loc[mask_still_na, "detected_at"] = pd.Timestamp.now(tz="UTC")

    # --- 8. Numeric conversion ---
    df["prob_anomaly"] = pd.to_numeric(df["prob_anomaly"], errors="coerce").fillna(0.0)
    df["is_anomaly_pred"] = (
        pd.to_numeric(df["is_anomaly_pred"], errors="coerce")
        .fillna(0)
        .astype(int)
    )
    df["pid"] = pd.to_numeric(df["pid"], errors="coerce").fillna(-1).astype(int)


    # --- 9. Remove garbage rows ---
    df = df[
        ~(
            (df["message"].astype(str).str.strip() == "")
            & (df["host"].astype(str).str.strip() == "")
        )
    ].copy()

    # --- 10. Sort newest first ---
    df = df.sort_values(by="detected_at", ascending=False)

    # --- 11. Convert datetime to ISO (API-safe) ---
    for col in ("timestamp", "detected_at"):
        df[col] = df[col].dt.strftime("%Y-%m-%dT%H:%M:%SZ").fillna("")

    # --- 12. Final column order ---
    df = df[REQUIRED_COLS]

    # --- 13. Convert to records ---
    records = df.to_dict(orient="records")

    _cache = records
    _last_mtime = mtime

    return _cache or []
# -----------------------
def normalize_dataframe(df_raw: pd.DataFrame, source_tag: str) -> pd.DataFrame:
    """
    Normalize uploaded CSV to the canonical schema used by the dashboard.
    Final columns (in order):
      anomaly_id, detected_at, timestamp, host, service, message,
      prob_anomaly, is_anomaly_pred, model, pid, source
    """
    df = df_raw.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]

    # Loose mappings to canonical names
    colmap = {
        "time": "timestamp", "ts": "timestamp", "datetime": "timestamp", "date": "timestamp",
        "host_name": "host", "hostname": "host",
        "svc": "service", "service_name": "service", "process": "service",
        "msg": "message", "log": "message", "text": "message", "event": "message",
        "score": "prob_anomaly", "prob": "prob_anomaly", "probability": "prob_anomaly","content": "message",
        "anomaly_prob": "prob_anomaly", "anomaly_score": "prob_anomaly"
    }
    for old, new in colmap.items():
        if old in df.columns and new not in df.columns:
            df.rename(columns={old: new}, inplace=True)

    # Ensure required text columns
    for required in ["detected_at", "timestamp", "host", "service", "message"]:
        if required not in df.columns:
            df[required] = ""
    df["source"] = str(source_tag).strip().lower()

    if df["source"].eq("").all():
        df["source"] = "upload"
    if "detected_at" not in df.columns:
        df["detected_at"] = df["timestamp"]
    # -------------------------------
    # 🔧 1. LABEL HANDLING
    # -------------------------------
    if "true_label" in df.columns:
        df["is_anomaly_pred"] = pd.to_numeric(df["true_label"], errors="coerce").fillna(0).astype(int)
    elif "is_anomaly_pred" in df.columns:
        df["is_anomaly_pred"] = pd.to_numeric(df["is_anomaly_pred"], errors="coerce").fillna(0).astype(int)
    else:
    # Use probability if available
        if "prob_anomaly" in df.columns:

            def infer_label(x):
                try:
                    return 1 if float(x) >= 0.65 else 0
                except Exception:
                    return 0

            df["is_anomaly_pred"] = df["prob_anomaly"].apply(infer_label)

        else:
            df["is_anomaly_pred"] = 0

    # -------------------------------
    # 🔧 2. PROBABILITY HANDLING
    # -------------------------------
    if "prob_anomaly" not in df.columns:
        df["prob_anomaly"] = df["is_anomaly_pred"].apply(lambda x: 0.95 if x == 1 else 0.0)
    else:
        def to_prob(x):
            try:
                v = float(x)
                if v > 1.0:
                    v = v / 100.0
                return max(0.0, min(1.0, v))
            except Exception:
                return 0.0
        df["prob_anomaly"] = df["prob_anomaly"].apply(to_prob)

    # -------------------------------
    # 🔧 3. TIMESTAMP HANDLING (FIXED)
    # -------------------------------
    def to_strict_utc(x):
        try:
            dt = pd.to_datetime(x, errors="coerce", utc=True)
            if pd.isna(dt):
                dt = pd.Timestamp.now(tz="UTC")
            return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        except Exception:
            return pd.Timestamp.now(tz="UTC").strftime("%Y-%m-%dT%H:%M:%SZ")

    from datetime import datetime

    if source_tag.startswith("upload"):
        current_time = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        df["timestamp"] = current_time
        df["detected_at"] = current_time
    else:
        df["timestamp"] = df["timestamp"].apply(to_strict_utc)

        if "detected_at" not in df.columns:
            df["detected_at"] = df["timestamp"]
        else:
            df["detected_at"] = df["detected_at"].apply(to_strict_utc)

    # -------------------------------
    # 🔒 REQUIRED FIELD VALIDATION
    # -------------------------------
    if "message" not in df.columns:
        raise ValueError("Missing required column: message")

    if "timestamp" not in df.columns:
        df["timestamp"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    # -------------------------------
    # 🆔 ANOMALY ID GENERATION
    # -------------------------------
    df["anomaly_id"] = df.apply(
        lambda row: f"{row['timestamp']}_{hash(str(row['message']))}",
        axis=1
    )

    # -------------------------------
    # 🔧 4. DEFAULT FIELDS
    # -------------------------------
    if "model" not in df.columns:
        df["model"] = "upload"
    if "pid" not in df.columns:
        df["pid"] = 0

    df["source"] = source_tag  

    cols = [
        "anomaly_id",
        "detected_at", "timestamp", "host", "service", "message",
        "prob_anomaly", "is_anomaly_pred", "model", "pid", "source"
    ]

    for c in cols:
        if c not in df.columns:
            df[c] = ""

    return df[cols]


# Routes
@app.post("/api/datasets/upload")
def upload_dataset():

    import json
    from datetime import datetime, UTC

    # =================================================
    # VALIDATE REQUEST
    # =================================================
    if "file" not in request.files:
        return jsonify({
            "ok": False,
            "error": "No file uploaded"
        }), 400

    f = request.files["file"]

    if not f or not f.filename:
        return jsonify({
            "ok": False,
            "error": "Invalid file"
        }), 400

    if not f.filename.lower().endswith(".csv"):
        return jsonify({
            "ok": False,
            "error": "Only CSV supported"
        }), 400

    # =================================================
    # SAVE ORIGINAL FILE
    # =================================================
    ts_tag = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")

    safe_name = f.filename.replace(" ", "_")

    saved_name = f"{ts_tag}__{safe_name}"

    os.makedirs(DATASETS_DIR, exist_ok=True)

    saved_path = os.path.join(DATASETS_DIR, saved_name)

    try:
        f.seek(0)
        f.save(saved_path)

    except Exception as e:
        return jsonify({
            "ok": False,
            "error": f"Failed saving file: {e}"
        }), 500

    # =================================================
    # READ CSV
    # =================================================
    try:

        df_raw = pd.read_csv(
            saved_path,
            encoding="utf-8",
            dtype=str,
            keep_default_na=False,
            on_bad_lines="skip"
        )

    except Exception as e:
        return jsonify({
            "ok": False,
            "error": f"CSV read failed: {e}"
        }), 400

    # =================================================
    # NORMALIZE
    # =================================================
    try:

        df_norm = normalize_dataframe(
            df_raw,
            source_tag="upload"
        )

        

    except Exception as e:
        return jsonify({
            "ok": False,
            "error": f"Normalization failed: {e}"
        }), 500

    # =================================================

    # ============================================
    # ML INFERENCE FOR UPLOADED DATASETS
    # ============================================

    try:

        if model is not None and vectorizer is not None:

            messages = (
                df_norm["message"]
                .fillna("")
                .astype(str)
            )


            X_upload = vectorizer.transform(messages)

            probs = model.predict_proba(X_upload)[:, 1]

            df_norm["prob_anomaly"] = probs

            df_norm["is_anomaly_pred"] = (
                probs >= BEST_RF_THRESHOLD
            ).astype(int)

        else:

            print("WARNING: Model or Vectorizer not loaded")

            df_norm["prob_anomaly"] = 0.0
            df_norm["is_anomaly_pred"] = 0

    except Exception as e:

        print(f"Upload inference failed: {e}")

        df_norm["prob_anomaly"] = 0.0
        df_norm["is_anomaly_pred"] = 0


        # =================================================
    # SEVERITY MAPPING
    # =================================================

    df_norm["severity"] = "LOW"

    df_norm.loc[
        df_norm["prob_anomaly"] >= 0.60,
        "severity"
    ] = "MEDIUM"

    df_norm.loc[
        df_norm["prob_anomaly"] >= 0.80,
        "severity"
    ] = "HIGH"






    # =================================================
    # CANONICAL COLUMN ORDER
    # =================================================
    CANONICAL_COLUMNS = [
        "detected_at",
        "timestamp",
        "host",
        "service",
        "message",
        "prob_anomaly",
        "is_anomaly_pred",
        "model",
        "pid",
        "source",
        "severity",
        "matched_rule",
        "active_event_count",
        "correlation_triggered",
        "escalation_reason"
    ]

    # =================================================
    # ENSURE ALL REQUIRED COLUMNS EXIST
    # =================================================
    defaults = {
        "detected_at": "",
        "timestamp": "",
        "host": "",
        "service": "",
        "message": "",
        "prob_anomaly": 0.0,
        "is_anomaly_pred": 0,
        "model": "upload",
        "pid": -1,
        "source": "upload",
        "severity": "LOW",
        "matched_rule": "",
        "active_event_count": "",
        "correlation_triggered": "",
        "escalation_reason": ""
    }

    for col in CANONICAL_COLUMNS:

        if col not in df_norm.columns:
            df_norm[col] = defaults[col]

    # =================================================
    # FORCE IMPORTANT FIELDS
    # =================================================


    df_norm["severity"] = df_norm["severity"].replace(
        "",
        "LOW"
    )

    # =================================================
    # FINAL SAFE COLUMN ORDER
    # =================================================
    df_norm = df_norm[CANONICAL_COLUMNS].copy()

    # =================================================
    # DEBUG
    # =================================================
    print("\n========== FINAL UPLOAD DEBUG ==========")

    print("TOTAL ROWS:", len(df_norm))

    print("\nSOURCE COUNTS:")
    print(df_norm["source"].value_counts(dropna=False))

    print("\nANOMALY COUNTS:")
    print(df_norm["is_anomaly_pred"].value_counts(dropna=False))

    print("\nFIRST 5 ROWS:")
    print(df_norm.head().to_string())

    print("========================================\n")

    # =================================================
    # WRITE CSV
    # =================================================
    try:

        os.makedirs(
            os.path.dirname(ANOMALIES_CSV),
            exist_ok=True
        )

        write_header = not os.path.exists(ANOMALIES_CSV)

        mode = "a"

        if write_header:
            mode = "w"

        df_norm.to_csv(
            ANOMALIES_CSV,
            index=False,
            mode=mode,
            header=write_header,
            encoding="utf-8"
        )

    except Exception as e:
        return jsonify({
            "ok": False,
            "error": f"CSV append failed: {e}"
        }), 500

    # =================================================
    # UPDATE META
    # =================================================
    datasets_count = None

    try:

        meta = {
            "datasets_analyzed": 0,
            "files": []
        }

        if os.path.exists(META_FILE):

            with open(
                META_FILE,
                "r",
                encoding="utf-8"
            ) as m:

                meta = json.load(m)

        meta["datasets_analyzed"] += 1

        meta["files"].append({
            "name": saved_name,
            "rows": int(len(df_norm)),
            "added_at": ts_tag
        })

        with open(
            META_FILE,
            "w",
            encoding="utf-8"
        ) as m:

            json.dump(meta, m, indent=2)

        datasets_count = meta["datasets_analyzed"]

    except Exception:
        pass

    # =================================================
    # SUCCESS
    # =================================================
    return jsonify({
        "ok": True,
        "file_saved": saved_name,
        "rows_added": int(len(df_norm)),
        "datasets_analyzed": datasets_count
    }), 201
# -----------------------
@app.post("/api/anomalies/action")
def handle_anomaly_action():
    data = request.get_json()
    print("RECEIVED DATA:", data)
    
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    file_path = os.path.join(BASE_DIR, "logs", "anomaly_actions.json")

    # ✅ Safe read
    actions = read_json_safe(file_path)
    print("CURRENT ACTIONS:", actions)

    # ✅ Extract fields
    anomaly_id = data.get("anomaly_id")
    status = data.get("status")

    # ===============================
    # ✅ STRICT STATUS VALIDATION (ADDED)
    # ===============================
    valid_status = ["acknowledged", "closed", "false_positive"]

    if not anomaly_id or status not in valid_status:
        return {"error": "Invalid anomaly_id or status"}, 400

    # ===============================
    # ✅ Store action (unchanged logic)
    # ===============================
    actions[anomaly_id] = {
        **actions.get(anomaly_id, {}),
        "status": status,
        "comment": data.get("comment", ""),
        "action_time": datetime.now(timezone.utc).isoformat()
    }

    # ✅ Safe write
    write_json_safe(file_path, actions)

    return {"message": "Action saved successfully"}
#-------------------------

@app.route("/")
def index():
    return render_template("index.html")

#----------------------------to accept filters--------
@app.route("/api/anomalies")
def api_anomalies():

    import pandas as pd

    try:
        rows = _read_anomalies()
    except Exception as e:
        return jsonify({"error": f"read_failed: {e}"}), 500

    df = pd.DataFrame(rows)

    if not df.empty:

        # =========================================================
        # --- 2. STRICT TYPE NORMALIZATION ---
        # =========================================================

        df["is_anomaly_pred"] = pd.to_numeric(
            df.get("is_anomaly_pred", 0), errors="coerce"
        ).fillna(0).astype(int)

        df["prob_anomaly"] = pd.to_numeric(
            df.get("prob_anomaly", 0.0), errors="coerce"
        ).fillna(0.0).astype(float)

        # ✅ FIXED (safe severity handling)
        if "severity" in df.columns:
            df["severity"] = df["severity"].fillna("LOW").astype(str)
        else:
            df["severity"] = "LOW"

        # =========================================================
        # --- 3. DATETIME ---
        # =========================================================

        df["detected_at"] = pd.to_datetime(
            df.get("detected_at"),
            errors="coerce",
            utc=True
        )

        # =========================================================
        # --- 4. FILTER TRUE ANOMALIES ---
        # =========================================================
        df = df[df["is_anomaly_pred"] == 1].copy()

        df = df.dropna(subset=["detected_at"])

        # =========================================================
        # --- 5. APPLY FILTERS ---
        # =========================================================
        df = _apply_filters(df, request.args).copy()

        # =========================================================
        # --- 6. SORT ---
        # =========================================================
        df = df.sort_values(by=["detected_at"], ascending=False)

    # =========================================================
    # --- 7. LIMIT ---
    # =========================================================
    try:
        limit = int(request.args.get("limit", 200))
        if limit > 0:
            df = df.head(limit)
    except Exception:
        pass

    # =========================================================
    # --- 8. SERIALIZER ---
    # =========================================================
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
                "prob_anomaly":    float(r.get("prob_anomaly", 0.0)),
                "severity":        _to_str(r.get("severity")),  # ✅ ensured
                "is_anomaly_pred": int(r.get("is_anomaly_pred", 0)),
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
        # --- 1. Use canonical reader ---
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

    # =========================================================
    # --- 2. EMPTY SAFETY ---
    # =========================================================
    if df.empty:
        counts.update({
            "total": 0,
            "last_10_minutes": 0,
            "last_1_hour": 0,
            "last_24_hours": 0,
        })
    else:

        # =========================================================
        # --- 3. STRICT TYPE NORMALIZATION ---
        # =========================================================

        df["is_anomaly_pred"] = pd.to_numeric(
            df.get("is_anomaly_pred", 0), errors="coerce"
        ).fillna(0).astype(int)

        df["prob_anomaly"] = pd.to_numeric(
            df.get("prob_anomaly", 0.0), errors="coerce"
        ).fillna(0.0).astype(float)

        df["severity"] = (
            df.get("severity", "LOW")
            .fillna("LOW")
            .astype(str)
        )

        # =========================================================
        # --- 4. DATETIME (already ISO from reader, but safe parse) ---
        # =========================================================

        df["detected_at"] = pd.to_datetime(
            df.get("detected_at"),
            errors="coerce",
            utc=True
        )

        print("\n===== TIME DEBUG =====")
        print("NOW UTC:", now)

        if not df.empty:
            print("MIN detected_at:", df["detected_at"].min())
            print("MAX detected_at:", df["detected_at"].max())

        print("======================\n")


        # =========================================================
        # --- 5. FILTER TRUE ANOMALIES ---
        # =========================================================
        df = df[df["is_anomaly_pred"] == 1].copy()
        # -------------------------------------------------

        # Now drop invalid timestamps
        df = df.dropna(subset=["detected_at"])

        # =========================================================
            # --- 5.1 APPLY SOURCE FILTER ---
            # =========================================================
        df = _apply_filters(df, request.args).copy()
        # ========================================

        # --- 6. COUNTERS ---
        # =========================================================

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

        # =========================================================
        # --- 7. SERVICE BREAKDOWN ---
        # =========================================================


        if "service" in df.columns:
                 by_service = (
                 df["service"]
                .fillna("unknown")
                .astype(str)
                .str.strip()
                .value_counts()
                .to_dict()
            )

    # =========================================================
    # --- 8. DATASET COUNTER ---
    # =========================================================

    try:
        datasets_analyzed = 0
        if os.path.exists(META_FILE):
            with open(META_FILE, "r", encoding="utf-8") as m:
                meta = json.load(m)
            datasets_analyzed = int(meta.get("datasets_analyzed", 0))
        counts["datasets_analyzed"] = datasets_analyzed
    except Exception:
        counts["datasets_analyzed"] = 0

    return jsonify({"counts": counts, "by_service": by_service})



@app.route("/api/live-stream")
def api_live_stream():

    try:
        log_file = PROJECT_ROOT / "logs" / "live_system.log"

        if not log_file.exists():
            return jsonify([])

        with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()

        return jsonify([
            line.strip()
            for line in lines[-20:]
            if line.strip()
        ])

    except Exception as e:
        return jsonify({
            "error": str(e)
        }), 500



@app.route("/api/retrain", methods=["POST"])
def trigger_retraining():

    import subprocess
    import sys

    try:
        script_path = PROJECT_ROOT / "retrain_with_feedback.py"

        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            timeout=600
        )

        return jsonify({
            "success": True,
            "returncode": result.returncode,
            "stdout": result.stdout[-5000:],
            "stderr": result.stderr[-5000:]
        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
    

@app.route("/api/retraining-history", methods=["GET"])
def api_retraining_history():

    try:

        history_file = PROJECT_ROOT / "logs" / "retraining_history.json"

        if not history_file.exists():
            return jsonify([])

        with open(
            history_file,
            "r",
            encoding="utf-8"
        ) as f:

            history = json.load(f)

        return jsonify(history)

    except Exception as e:

        return jsonify({
            "error": str(e)
        }), 500

if __name__ == "__main__":
    print("Starting Flask server...")
    write_feedback_dataset_to_csv()
    app.run(host="0.0.0.0", port=5000, debug=True)