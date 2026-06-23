#!/usr/bin/env python3
# scripts/live_monitor_infer.py

import os
import time
import joblib
import pandas as pd
import numpy as np
import re
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict
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
PROB_THRESHOLD = 0.65
SERVICE_THRESHOLDS = {
    "sshd": 0.70,
    "CRON": 0.80,
    "sendmail": 0.85,
    "rtkit-daemon": 0.90,
}
CORRELATION_RULES = [
    {
        "name": "ssh_bruteforce",
        "window_seconds": 60,
        "correlation_threshold": 3,
        "dedup_seconds": 15,
        "severity": "HIGH",
        "patterns": [
            "ssh",
            "failed password",
            "authentication failed",
            "brute force",
        ]
    }
]


_writer = AnomalyWriter()

# -------------------------------------------------
# SSH Failure Correlation Tracker
# -------------------------------------------------
behavior_trackers = defaultdict(lambda: defaultdict(list))

# Recent Event Deduplication Cache

recent_event_cache = {}

# -------------------------------------------------------------------
# Terminal Alert
# -------------------------------------------------------------------

def terminal_alert(rec):

    RED = "\033[91m"
    RESET = "\033[0m"

    try:

        print(
            RED
            + "[ALERT] Anomaly detected: time={ts} host={h} service={s} prob={p:.3f} severity={sev}\n  msg: {m}".format(
                ts=rec.get("detected_at", ""),
                h=rec.get("host", ""),
                s=rec.get("service", ""),
                p=float(rec.get("prob_anomaly", 0.0)),
                sev=rec.get("severity", ""),
                m=str(rec.get("message", ""))[:200],
            )
            + RESET
        )

    except Exception:

        print(
            RED
            + "[ALERT] Anomaly detected (details unavailable)"
            + RESET
        )

# -------------------------------------------------------------------
# Severity Mapping
# -------------------------------------------------------------------

def get_severity(prob):
    if prob >= 0.75:
        return "HIGH"

    elif prob >= 0.55:
        return "MEDIUM"

    else:
        return "LOW"
    

def get_service_threshold(service_name):

    if not service_name:
        return PROB_THRESHOLD

    return SERVICE_THRESHOLDS.get(
        str(service_name).strip(),
        PROB_THRESHOLD
    )

# -------------------------------------------------------------------
# Structured Features (Future Use)
# -------------------------------------------------------------------

def extract_features(text):

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

# -------------------------------------------------------------------
# Main
# -------------------------------------------------------------------

def main():

    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Model not found at {MODEL_PATH}"
        )

    if not VECTORIZER_PATH.exists():
        raise FileNotFoundError(
            f"Vectorizer not found at {VECTORIZER_PATH}"
        )

    print("Loading model from:", MODEL_PATH)
    model = joblib.load(MODEL_PATH)

    print("Loading vectorizer from:", VECTORIZER_PATH)
    vectorizer = joblib.load(VECTORIZER_PATH)

    print("Model and vectorizer loaded.")
    print("Monitoring parsed logs:", PARSED_CSV)

    last_mtime = None
    last_row_count = 0

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

                df_all = pd.read_csv(
                    PARSED_CSV,
                    dtype=str,
                    keep_default_na=False,
                    on_bad_lines="skip",
                    encoding="utf-8"
                )

            except Exception as e:

                print("Failed reading parsed CSV:", e)
                time.sleep(POLL_INTERVAL)
                continue

            if df_all.empty:
                time.sleep(POLL_INTERVAL)
                continue

            if (
                last_row_count > 0
                and len(df_all) <= last_row_count
            ):
                time.sleep(POLL_INTERVAL)
                continue

            df_new = df_all.iloc[last_row_count:].copy()

            last_row_count = len(df_all)

            print(
                f"Found {len(df_new)} new rows; running inference..."
            )

            appended_count = 0

            for _, row in df_new.iterrows():

                # -------------------------------------------------
                # Safe message extraction
                # -------------------------------------------------

                try:

                    cols = list(df_new.columns)

                    if "message" in cols:
                        msg = str(row["message"]).strip().lower()

                    else:
                        msg = str(row.iloc[-1]).strip().lower()

                except Exception:

                    msg = ""

                # -------------------------------------------------
                # Skip empty/corrupt rows
                # -------------------------------------------------

                if not msg or msg == "nan":
                    continue

                try:

                    # -----------------------------
                    # TF-IDF ONLY
                    # -----------------------------

                    X_tfidf = vectorizer.transform([msg])

                    X = X_tfidf

                    # -----------------------------
                    # Prediction
                    # -----------------------------

                    prob = float(
                        model.predict_proba(X)[0][1]
                    )

                    print(
                        f"[DEBUG] prob={prob:.4f} | "
                        f"msg={msg[:80]}"
                    )

                    # -------------------------------------------------
                    # SSH Failure Correlation Tracking
                    # -------------------------------------------------


                    # Extract IP Address
# -------------------------------------------------
                    ip_match = re.search(
                        r'\b\d{1,3}(?:\.\d{1,3}){3}\b',
                        msg
                        )
                    
                    src_ip = ip_match.group(0) if ip_match else "unknown"
                    msg_lower = msg.lower()
                    event_signature = f"{src_ip}:{msg_lower}"

                    active_events = 0
                    correlation_triggered = False
                    matched_rule = None
                    matched_pattern = None
                    for rule in CORRELATION_RULES:
                         pattern = next(
                             (p for p in rule["patterns"] if p in msg_lower),
                             None
                             )
                         
                         if pattern:
                            matched_rule = rule
                            matched_pattern = pattern
                            rule_name = matched_rule["name"]
                            rule_tracker = behavior_trackers[rule_name]
                            break

                    if matched_pattern:
                        
                        current_time = time.time()
                        last_seen = recent_event_cache.get(event_signature)
                        if (
                            last_seen is not None
                            and current_time - last_seen <= matched_rule["dedup_seconds"]
                        ):
                            print(
                                f"[DEDUP SKIP] "
                                f"IP={src_ip} | "
                                f"Rule={matched_pattern}"
                            )
                            continue

                        rule_tracker[src_ip].append(current_time)
                        recent_event_cache[event_signature] = current_time
                        # Remove expired timestamps
                        rule_tracker[src_ip] = [
                             ts for ts in rule_tracker[src_ip]
                            if current_time - ts <= matched_rule["window_seconds"]
                        ]

                        # Remove empty trackers
                        if not rule_tracker[src_ip]:
                            del rule_tracker[src_ip]
                            continue

                        count = len(rule_tracker[src_ip])
                        active_events = count
                        correlation_triggered = (
                             active_events >= matched_rule["correlation_threshold"]
                        )
                        print(
                            f"[WINDOW DEBUG] "
                            f"IP={src_ip} | "
                            f"Rule={matched_pattern} | "
                            f"ActiveEvents={count} | "
                            f"Window={matched_rule['window_seconds']}s"
                            )

                        print(
                            f"[SSH TRACKER] "
                            f"IP={src_ip} | "
                            f"Count={count} | "
                            f"msg={msg[:80]}"
                        )

                except Exception as e:

                    print(
                        "Prediction failed for one record:",
                        e
                    )

                    prob = 0.0

                # -------------------------------------------------
                # Severity + Threshold Logic
                # ------------------------------------------------

                severity = get_severity(prob)

                # Dynamic SSH Escalation ...
                if matched_rule and correlation_triggered:
                          severity = matched_rule["severity"]
                          if active_events >= 5:
                              severity = "CRITICAL"
                          print(
                                f"[CORRELATION ALERT] "
                                f"IP={src_ip} | "
                                f"Count={active_events} | "
                                f"Severity={severity}"
                                )
                          

                service_name = str(
                    row.get("service", "")
                    ).strip()
                
                service_name = service_name.lower()
                if service_name == "ssshd":
                     service_name = "sshd"
                if service_name == "ssh":
                    service_name = "sshd"

                
                service_threshold = get_service_threshold(service_name)
                print(
                    f"[THRESHOLD DEBUG] "
                    f"service={service_name} | "
                    f"threshold={service_threshold:.2f}"
                    )

                is_anom = int(prob >= service_threshold)
                if matched_rule and correlation_triggered:
                        is_anom = 1

                        print(
                            f"[FORCED ALERT] "  
                            f"Correlation engine forced anomaly "
                            f"(count={active_events})"
                        )

                # -------------------------------------------------
                # Write anomaly
                # -------------------------------------------------

                if is_anom == 1:

                    detected_at = datetime.now(
                        timezone.utc
                    ).strftime("%Y-%m-%dT%H:%M:%SZ")

                    output = {
                        "timestamp": row.get("timestamp", "") or "",
                        "detected_at": detected_at,
                        "host": row.get("host", "") or "",
                        "service": row.get("service", "") or "",
                        "message": row.get("message", "") or "",
                        "matched_rule": matched_pattern if matched_pattern else "",
                        "active_event_count": active_events,
                            "correlation_triggered": (correlation_triggered),

                            "escalation_reason": (
                                "Repeated behavioral correlation detected"
                                if correlation_triggered 
                                else "ML semantic anomaly"
                                ),

                        "prob_anomaly": float(prob),
                        "severity": severity,
                        "threat_score": (
                            100 if severity == "CRITICAL"
                            else 75 if severity == "HIGH"
                             else 50 if severity == "MEDIUM"
                             else 25
                                ),
                        "is_anomaly_pred": 1,
                        "pid": (
                            int(row.get("pid", -1))
                            if row.get("pid", "") != ""
                            else -1
                        ),
                        "model": os.path.basename(MODEL_PATH),
                        "source": "live",
                    }

                    try:

                        ok = _writer.append_anomaly(output)

                    except Exception as e:

                        ok = False

                        print(
                            "AnomalyWriter append error:",
                            e
                        )

                    if ok:

                        appended_count += 1

                        terminal_alert(output)

            print(
                f"Inference completed. "
                f"Appended {appended_count} new anomalies."
            )

            time.sleep(POLL_INTERVAL)

        except KeyboardInterrupt:

            print("Stopping monitor.")
            break

        except Exception as e:

            print("Monitor error:", str(e))

            time.sleep(POLL_INTERVAL)

# -------------------------------------------------------------------
# Entry
# -------------------------------------------------------------------

if __name__ == "__main__":
    main()