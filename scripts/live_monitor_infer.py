#!/usr/bin/env python3
# scripts/live_monitor_infer.py
# Canonical real-time inference runner for live pipeline

import os
import time
import joblib
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from pathlib import Path
import sys

# -------------------------------------------------------------------
# Project setup
# -------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(PROJECT_ROOT))

from src.anomaly_writer import AnomalyWriter

MODEL_PATH = PROJECT_ROOT / "models" / "best_model.joblib"
VECTORIZER_PATH = PROJECT_ROOT / "models" / "tfidf_vectorizer.joblib"

PARSED_CSV = PROJECT_ROOT / "data" / "parsed_live_logs.csv"

POLL_INTERVAL = 2.0
PROB_THRESHOLD = 0.7   # production-safe default

_writer = AnomalyWriter()

# -------------------------------------------------------------------
# Utility
# -------------------------------------------------------------------

def terminal_alert(rec):
    RED = "\033[91m"
    RESET = "\033[0m"
    try:
        print(
            RED
            + "[ALERT] Anomaly detected: time={ts} host={h} service={s} prob={p:.3f}\n  msg: {m}".format(
                ts=rec.get("detected_at", ""),
                h=rec.get("host", ""),
                s=rec.get("service", ""),
                p=float(rec.get("prob_anomaly", 0.0)),
                m=str(rec.get("message", ""))[:200],
            )
            + RESET
        )
    except Exception:
        print(RED + "[ALERT] Anomaly detected (details unavailable)" + RESET)

# -------------------------------------------------------------------
# Main
# -------------------------------------------------------------------

def main():
    # --- Load model and vectorizer ---

    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Model not found at {MODEL_PATH}")
    if not VECTORIZER_PATH.exists():
        raise FileNotFoundError(f"Vectorizer not found at {VECTORIZER_PATH}")

    print("Loading model from:", MODEL_PATH)
    model = joblib.load(MODEL_PATH)

    print("Loading vectorizer from:", VECTORIZER_PATH)
    vectorizer = joblib.load(VECTORIZER_PATH)

    print("Model and vectorizer loaded.")
    print("Monitoring parsed logs:", PARSED_CSV)

    last_mtime = None
    last_row_count = 0   # process only new rows

    while True:
        try:
            if not PARSED_CSV.exists():
                time.sleep(POLL_INTERVAL)
                continue

            mtime = PARSED_CSV.stat().st_mtime
            if last_mtime is not None and mtime == last_mtime:
                time.sleep(POLL_INTERVAL)
                continue

            last_mtime = mtime

            try:
                df_all = pd.read_csv(PARSED_CSV, dtype=str, keep_default_na=False)
            except Exception as e:
                print("Failed reading parsed CSV:", e)
                time.sleep(POLL_INTERVAL)
                continue

            if df_all.empty:
                time.sleep(POLL_INTERVAL)
                continue

            # Only process newly appended rows
            if last_row_count > 0 and len(df_all) <= last_row_count:
                time.sleep(POLL_INTERVAL)
                continue

            df_new = df_all.iloc[last_row_count:].copy()
            last_row_count = len(df_all)

            print(f"Found {len(df_new)} new rows; running inference...")

            appended_count = 0

            for _, row in df_new.iterrows():
                # ------------------------------------------------------------------
                # Canonical preprocessing (must match 02_preprocessing.ipynb)
                # ------------------------------------------------------------------
                msg = row.get("message", "")
                msg = str(msg).strip().lower()

                try:
                    X = vectorizer.transform([msg])
                    prob = float(model.predict_proba(X)[0][1])
                except Exception as e:
                    print("Prediction failed for one record:", e)
                    prob = 0.0

                is_anom = int(prob >= PROB_THRESHOLD)

                if is_anom == 1:
                    detected_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

                    output = {
                        "timestamp": row.get("timestamp", "") or "",
                        "detected_at": detected_at,
                        "host": row.get("host", "") or "",
                        "service": row.get("service", "") or "",
                        "message": row.get("message", "") or "",
                        "prob_anomaly": prob,
                        "is_anomaly_pred": 1,
                        "pid": int(row.get("pid", -1)) if row.get("pid", "") != "" else -1,
                        "model": os.path.basename(MODEL_PATH),
                        "source": "live",
                    }

                    try:
                        ok = _writer.append_anomaly(output)
                    except Exception as e:
                        ok = False
                        print("AnomalyWriter append error:", e)

                    if ok:
                        appended_count += 1
                        terminal_alert(output)
                    else:
                        print(
                            "Skipped duplicate or failed write for anomaly:",
                            output.get("service"),
                            output.get("host"),
                        )

            print(f"Inference completed. Appended {appended_count} new anomalies (if any).")
            time.sleep(POLL_INTERVAL)

        except KeyboardInterrupt:
            print("Stopping monitor.")
            break

        except Exception as e:
            print("Monitor error:", str(e))
            time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
