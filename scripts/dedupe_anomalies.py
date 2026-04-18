# scripts/dedupe_anomalies.py
"""
Simple robust dedupe:
- reads logs/anomalies_log.csv
- computes 16-char sha key per row from (detected_at | timestamp) + host + service + message
- drops duplicate keys, keeping FIRST occurrence (stable)
- writes deduped file to backups/anomalies_log.deduped_<ts>.csv and replaces canonical file
This version avoids timestamp parsing/sorting to be resilient to tz issues.
"""
import pandas as pd
import hashlib
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
ANOMALIES_CSV = ROOT / "logs" / "anomalies_log.csv"
BACKUP_DIR = ROOT / "backups"
OUT_COPY = BACKUP_DIR / f"anomalies_log.deduped_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"

if not ANOMALIES_CSV.exists():
    print("ERROR: anomalies_log.csv not found at", ANOMALIES_CSV)
    raise SystemExit(1)

# read everything as string to avoid dtype surprises
df = pd.read_csv(ANOMALIES_CSV, dtype=str, keep_default_na=False)
print("Rows before:", len(df))

# ensure expected columns exist (create empty if missing)
for c in ("detected_at", "timestamp", "host", "service", "message", "msg", "svc"):
    if c not in df.columns:
        df[c] = ""

# stable key function
def make_key(row):
    ts = (row.get("detected_at") or row.get("timestamp") or "").strip()
    host = (row.get("host") or "").strip()
    svc = (row.get("service") or row.get("svc") or "").strip()
    msg = (row.get("message") or row.get("msg") or "").strip()
    key = "|".join([ts, host, svc, msg])
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]

# compute keys
df["_row_key"] = df.apply(make_key, axis=1)

# drop duplicates by key (keep first appearance)
df_dedup = df.drop_duplicates(subset="_row_key", keep="first").copy()
print("Rows after dedupe:", len(df_dedup))

# write deduped to backup path first
BACKUP_DIR.mkdir(parents=True, exist_ok=True)
df_dedup.drop(columns=["_row_key"]).to_csv(OUT_COPY, index=False)
print("Wrote deduped copy to:", OUT_COPY)

# replace canonical file safely: rename original (timestamped) then move deduped into place
orig_backup = ANOMALIES_CSV.with_suffix(".csv.orig")
try:
    ANOMALIES_CSV.rename(orig_backup)
    OUT_COPY.replace(ANOMALIES_CSV)
    print("Replaced canonical anomalies_log.csv with deduped file.")
    print("Original file moved to:", orig_backup)
except Exception as e:
    print("ERROR while replacing canonical file:", e)
    print("Your deduped copy is at:", OUT_COPY)
