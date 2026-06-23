# src/anomaly_writer.py

import json
import hashlib
import csv
import tempfile
import os
from pathlib import Path
from typing import Dict, Any
from datetime import datetime, timezone

# -------------------------------------------------------------------
# Time helper (FIXED → consistent with API)
# -------------------------------------------------------------------

def now_utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

# -------------------------------------------------------------------
# Paths & limits
# -------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ANOMALIES_CSV = PROJECT_ROOT / "logs" / "anomalies_log.csv"
SEEN_KEYS_FILE = PROJECT_ROOT / ".seen_keys.json"
MAX_SEEN_KEYS = 20_000

# -------------------------------------------------------------------
# CANONICAL CSV SCHEMA (LOCKED)
# -------------------------------------------------------------------

CANONICAL_FIELDS = [
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

    "matched_rule",
    "active_event_count",
    "correlation_triggered",
    "escalation_reason",
]

# -------------------------------------------------------------------
# Deduplication key
# -------------------------------------------------------------------

def make_row_key(row: Dict[str, Any]) -> str:
    host = (row.get("host") or "").strip()
    svc  = (row.get("service") or "").strip()
    msg  = (row.get("message") or "").strip()
    pid  = str(row.get("pid") or "")

    raw = "|".join([host, svc, pid, msg])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

# -------------------------------------------------------------------
# Seen-keys persistence
# -------------------------------------------------------------------

def load_seen_keys() -> Dict[str, int]:
    if SEEN_KEYS_FILE.exists():
        try:
            return json.loads(SEEN_KEYS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}

def save_seen_keys(seen: Dict[str, int]) -> None:
    try:
        tmp = SEEN_KEYS_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(seen), encoding="utf-8")
        tmp.replace(SEEN_KEYS_FILE)
    except Exception:
        pass

# -------------------------------------------------------------------
# Normalize row (STRICT + SAFE)
# -------------------------------------------------------------------

def normalize_row(row: Dict[str, Any]) -> Dict[str, Any]:
    clean = {}

    for field in CANONICAL_FIELDS:
        val = row.get(field, "")

        try:
            if field == "prob_anomaly":
                val = float(val) if val != "" else 0.0

            elif field == "is_anomaly_pred":
                val = int(val) if val != "" else 0

            elif field == "pid":
                val = int(val) if val != "" else 0

            elif field == "severity":
                val = str(val).upper() if val else "LOW"

            else:
                val = str(val)

        except Exception:
            # Hard fallback safety
            if field in ["prob_anomaly"]:
                val = 0.0
            elif field in ["is_anomaly_pred", "pid"]:
                val = 0
            elif field == "severity":
                val = "LOW"
            else:
                val = ""

        clean[field] = val

    return clean

# -------------------------------------------------------------------
# Atomic append (SAFE + HEADER-PROTECTED)
# -------------------------------------------------------------------

def append_row_atomic(row: Dict[str, Any]) -> bool:
    try:
        ANOMALIES_CSV.parent.mkdir(parents=True, exist_ok=True)

        clean_row = normalize_row(row)

        file_exists = ANOMALIES_CSV.exists()
        needs_header = not file_exists or ANOMALIES_CSV.stat().st_size == 0

        # Write ONLY the new row to temp
        with tempfile.NamedTemporaryFile(
            mode="w",
            delete=False,
            dir=str(ANOMALIES_CSV.parent),
            newline="",
            encoding="utf-8"
        ) as tf:
            writer = csv.DictWriter(tf, fieldnames=CANONICAL_FIELDS)

            if needs_header:
                writer.writeheader()

            writer.writerow(clean_row)
            tf.flush()
            os.fsync(tf.fileno())

            tmp_path = Path(tf.name)

        # Append safely
        with open(ANOMALIES_CSV, "ab") as dst, open(tmp_path, "rb") as src:
            dst.write(src.read())
            dst.flush()
            os.fsync(dst.fileno())

        tmp_path.unlink(missing_ok=True)

        return True

    except Exception as e:
        print("append_row_atomic error:", e)
        return False

# -------------------------------------------------------------------
# Anomaly Writer
# -------------------------------------------------------------------

class AnomalyWriter:

    def __init__(self):
        self.seen = load_seen_keys()
        self._counter = max(self.seen.values(), default=0) + 1

    def append_anomaly(self, row: Dict[str, Any]) -> bool:

        # --- Ensure timestamps ---
        if not row.get("timestamp"):
            row["timestamp"] = now_utc_iso()

        if not row.get("detected_at"):
            row["detected_at"] = row["timestamp"]

        # --- Ensure severity ---
        if not row.get("severity"):
            row["severity"] = "LOW"

        key = make_row_key(row)

        if key in self.seen:
            return False

        if not append_row_atomic(row):
            return False

        self.seen[key] = self._counter
        self._counter += 1

        # Trim memory
        if len(self.seen) > MAX_SEEN_KEYS:
            self.seen = dict(
                sorted(self.seen.items(), key=lambda kv: kv[1])[-MAX_SEEN_KEYS:]
            )

        # Periodic persistence
        if self._counter % 50 == 0:
            save_seen_keys(self.seen)

        return True

    def persist(self):
        save_seen_keys(self.seen)