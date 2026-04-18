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
# Time helper
# -------------------------------------------------------------------

def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

# -------------------------------------------------------------------
# Paths & limits
# -------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ANOMALIES_CSV = PROJECT_ROOT / "logs" / "anomalies_log.csv"
SEEN_KEYS_FILE = PROJECT_ROOT / ".seen_keys.json"
MAX_SEEN_KEYS = 20_000

# -------------------------------------------------------------------
# CANONICAL CSV SCHEMA (MUST MATCH app.py + dashboard)
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
]

# -------------------------------------------------------------------
# Deduplication key (STABLE, BUT NOT OVER-AGGRESSIVE)
# -------------------------------------------------------------------

def make_row_key(row: Dict[str, Any]) -> str:
    """
    Dedup key based on:
      - host
      - service
      - message
      - pid

    NOTE:
    - detected_at is NOT included
    - timestamp is NOT included (same event can reappear later)
    """

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
# Atomic CSV append with FIXED HEADER
# -------------------------------------------------------------------

def append_row_atomic(row: Dict[str, Any]) -> bool:
    try:
        ANOMALIES_CSV.parent.mkdir(parents=True, exist_ok=True)
        file_exists = ANOMALIES_CSV.exists()

        # Enforce canonical schema and ordering
        clean_row = {field: row.get(field, "") for field in CANONICAL_FIELDS}

        with tempfile.NamedTemporaryFile(
            mode="w",
            delete=False,
            dir=str(ANOMALIES_CSV.parent),
            newline="",
            encoding="utf-8"
        ) as tf:
            writer = csv.DictWriter(tf, fieldnames=CANONICAL_FIELDS)

            if not file_exists:
                writer.writeheader()

            writer.writerow(clean_row)
            tf.flush()
            os.fsync(tf.fileno())
            tmp_path = Path(tf.name)

        if file_exists:
            with open(ANOMALIES_CSV, "ab") as dst, open(tmp_path, "rb") as src:
                dst.write(src.read())
                dst.flush()
                os.fsync(dst.fileno())
            tmp_path.unlink(missing_ok=True)
        else:
            tmp_path.replace(ANOMALIES_CSV)

        return True

    except Exception as e:
        print("append_row_atomic error:", e)
        return False

# -------------------------------------------------------------------
# Anomaly Writer (RECTIFIED, PRODUCTION-SAFE)
# -------------------------------------------------------------------

class AnomalyWriter:
    """
    Central writer for live and uploaded anomalies.

    Guarantees:
    - Fixed CSV schema
    - Stable dedup
    - No header corruption
    - detected_at preserved if already set
    """

    def __init__(self):
        self.seen = load_seen_keys()
        self._counter = max(self.seen.values(), default=0) + 1

    def append_anomaly(self, row: Dict[str, Any]) -> bool:
        """
        Append anomaly if new.
        Returns True only if actually written.
        """

        # Only set detected_at if not already provided
        if not row.get("detected_at"):
            row["detected_at"] = now_utc_iso()

        # Enforce required fields (never let them be missing)
        for field in CANONICAL_FIELDS:
            if field not in row:
                row[field] = ""

        key = make_row_key(row)

        if key in self.seen:
            return False

        if not append_row_atomic(row):
            return False

        self.seen[key] = self._counter
        self._counter += 1

        # Trim seen-keys
        if len(self.seen) > MAX_SEEN_KEYS:
            self.seen = dict(
                sorted(self.seen.items(), key=lambda kv: kv[1])[-MAX_SEEN_KEYS:]
            )

        # Persist periodically
        if self._counter % 50 == 0:
            save_seen_keys(self.seen)

        return True

    def persist(self):
        save_seen_keys(self.seen)
