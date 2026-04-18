# test_model.py
# Script 3/3: TESTING / DEMO ONLY
#
# Usage (from project root):
#   python -m src.test_model
# From:

#cd E:\LogAnomalyDetector
#python -m src.test_model


#IT WILL BE SHOWING OUTPUT LIKE :

#[1] ANOMALY (1) | prob=0.8765
 #    LOG: sshd[1234]: Failed password for root from 192.168.0.10 port 54321 ssh2
#----------------------------------------------------------------------
#[2] NORMAL (0) | prob=0.0321
 #    LOG: systemd[1]: Started Daily apt download.
#----------------------------------------------------------------------
# This will:
#   - Load the trained models/best_model.joblib
#   - Read a few sample lines from logs/sample.log
#   - Run them through the full pipeline
#   - Print predictions in a viva-friendly format
#------------------------------------------------------------------------



from pathlib import Path
from typing import List

import pandas as pd

from .model_utils import load_model
from .preprocessing import prepare_dataframe


# =========================================================
# 1. CONFIG
# =========================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

LOGS_DIR = PROJECT_ROOT / "logs"
MODELS_DIR = PROJECT_ROOT / "models"

LOG_FILE = LOGS_DIR / "sample.log"
MODEL_PATH = MODELS_DIR / "best_model.joblib"

# How many recent lines to test from sample.log
N_LINES = 10


# =========================================================
# 2. HELPERS
# =========================================================

def read_last_lines(path: Path, n: int) -> List[str]:
    """Read the last n non-empty lines from a text file."""
    if not path.exists():
        raise FileNotFoundError(
            f"Log file not found at: {path}\n"
            f"Please ensure 'sample.log' exists in logs/."
        )

    with path.open("r", encoding="utf-8", errors="ignore") as f:
        lines = [line.rstrip("\n") for line in f.readlines()]

    # Filter out empty lines and take the last n
    lines = [ln for ln in lines if ln.strip()]
    return lines[-n:] if len(lines) >= n else lines


def build_test_dataframe(lines: List[str]) -> pd.DataFrame:
    """
    Build a simple DataFrame from raw log lines.

    For demonstration, we:
    - Put the full line into 'message'
    - Use a dummy host and service
    - Use a synthetic timestamp (now)
    """
    if not lines:
        raise ValueError("No non-empty lines found in the log file.")

    now = pd.Timestamp.now()

    data = {
        "timestamp": [now] * len(lines),
        "host": ["demo_host"] * len(lines),
        "service": ["demo_service"] * len(lines),
        "message": lines,
    }

    df = pd.DataFrame(data)
    return df


# =========================================================
# 3. MAIN TESTING LOGIC
# =========================================================

def main():
    print("=" * 70)
    print("LOG ANOMALY DETECTOR – TESTING / DEMO SCRIPT")
    print("=" * 70)
    print(f"Project root : {PROJECT_ROOT}")
    print(f"Log file     : {LOG_FILE}")
    print(f"Model path   : {MODEL_PATH}")
    print()

    # ---------- Load sample lines ----------
    print("[1] Reading sample log lines...")
    lines = read_last_lines(LOG_FILE, N_LINES)
    print(f"    Loaded {len(lines)} log lines for testing.")
    print()

    # ---------- Load model ----------
    print("[2] Loading trained model pipeline...")
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Trained model not found at: {MODEL_PATH}\n"
            f"Please run 'python -m src.train_model' first to create best_model.joblib."
        )

    model = load_model(str(MODEL_PATH))
    print("    Model loaded successfully.")
    print()

    # ---------- Build DataFrame ----------
    print("[3] Building test DataFrame...")
    df_test = build_test_dataframe(lines)
    df_prepared = prepare_dataframe(df_test)
    print("    DataFrame prepared.")
    print()

    # ---------- Predict ----------
    print("[4] Running predictions...")
    y_pred = model.predict(df_prepared)

    # Try to get probability or decision score for anomaly class
    score_type = None
    scores = None

    if hasattr(model, "predict_proba"):
        proba = model.predict_proba(df_prepared)
        # assume anomaly class = 1
        scores = proba[:, 1]
        score_type = "probability"
    elif hasattr(model, "decision_function"):
        scores = model.decision_function(df_prepared)
        score_type = "decision_score"

    print("    Predictions completed.")
    print()

    # ---------- Pretty print ----------
    print("[5] Results")
    print("-" * 70)

    for i, (line, pred) in enumerate(zip(lines, y_pred)):
        label_str = "ANOMALY (1)" if pred == 1 else "NORMAL (0)"

        if scores is not None:
            score_val = scores[i]
            if score_type == "probability":
                score_str = f"{score_val:.4f}"
                print(f"[{i+1}] {label_str} | prob={score_str}")
            else:
                score_str = f"{score_val:.4f}"
                print(f"[{i+1}] {label_str} | score={score_str}")
        else:
            print(f"[{i+1}] {label_str}")

        print(f"     LOG: {line}")
        print("-" * 70)

    print()
    print("Testing / demo run completed.")
    print("=" * 70)


if __name__ == "__main__":
    main()
