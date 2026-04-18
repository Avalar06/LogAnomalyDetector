# validate_model.py
# Script 2/3: VALIDATION ONLY
#
# Usage (from project root):
#   python -m src.validate_model
#
# This will:
#   - Load a separate labeled validation dataset from data/
#   - Load the already-trained models/best_model.joblib
#   - Evaluate precision/recall/F1 on anomaly class
#   - Save results to reports/validation_results.csv

from pathlib import Path
from typing import Tuple

import pandas as pd
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    precision_recall_fscore_support,
)

from .model_utils import load_model
from .preprocessing import prepare_dataframe


# =========================================================
# 1. CONFIG
# =========================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATA_DIR = PROJECT_ROOT / "data"
MODELS_DIR = PROJECT_ROOT / "models"
REPORTS_DIR = PROJECT_ROOT / "reports"

# Validation file – you can change this if needed
VALIDATION_FILE = DATA_DIR / "labeled_live_logs.csv"

# Model & report paths
MODEL_PATH = MODELS_DIR / "best_model.joblib"
VALIDATION_REPORT_FILE = REPORTS_DIR / "validation_results.csv"


# =========================================================
# 2. HELPERS
# =========================================================

def load_validation_data(path: Path) -> Tuple[pd.DataFrame, pd.Series]:
    """
    Load the validation dataset and return (df, y),
    where y is the anomaly label column.

    Supports either:
    - 'label' column (0/1)
    - 'is_anomaly' column (0/1)
    """
    if not path.exists():
        raise FileNotFoundError(
            f"Validation file not found at: {path}\n"
            f"Please ensure 'labeled_live_logs.csv' (or adjust VALIDATION_FILE) exists in data/."
        )

    df = pd.read_csv(path)

    # Detect label column
    if "label" in df.columns:
        label_col = "label"
    elif "is_anomaly" in df.columns:
        label_col = "is_anomaly"
    else:
        raise ValueError(
            f"No label column found in {path}.\n"
            f"Expected a 'label' or 'is_anomaly' column."
        )

    y = df[label_col].astype(int)

    # Basic sanity check
    if y.nunique() < 2:
        raise ValueError(
            "Validation labels contain only one class. "
            "Need both normal (0) and anomaly (1) samples."
        )

    return df, y


# =========================================================
# 3. MAIN VALIDATION LOGIC
# =========================================================

def main():
    print("=" * 70)
    print("LOG ANOMALY DETECTOR – VALIDATION SCRIPT")
    print("=" * 70)
    print(f"Project root    : {PROJECT_ROOT}")
    print(f"Validation file : {VALIDATION_FILE}")
    print(f"Model path      : {MODEL_PATH}")
    print()

    # Ensure reports dir exists
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # ---------- Load data ----------
    print("[1] Loading validation data...")
    df, y_true = load_validation_data(VALIDATION_FILE)
    print(f"    Loaded {len(df)} rows.")
    print(f"    Label distribution:\n{y_true.value_counts()}")
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

    # ---------- Prepare features ----------
    print("[3] Preparing features...")
    X_val = prepare_dataframe(df)
    print("    Feature preparation done.")
    print()

    # ---------- Predict ----------
    print("[4] Running predictions...")
    y_pred = model.predict(X_val)
    print("    Predictions completed.")
    print()

    # ---------- Metrics ----------
    print("[5] Calculating metrics (focus on anomaly class = 1)...")
    p, r, f1, _ = precision_recall_fscore_support(
        y_true,
        y_pred,
        pos_label=1,
        average="binary",
        zero_division=0
    )

    cm = confusion_matrix(y_true, y_pred)
    report_str = classification_report(
        y_true,
        y_pred,
        digits=4,
        zero_division=0
    )

    print()
    print("Confusion Matrix:")
    print(cm)
    print()
    print("Classification Report:")
    print(report_str)
    print()
    print(f"Anomaly class metrics: precision={p:.4f}, recall={r:.4f}, f1={f1:.4f}")
    print()

    # ---------- Save to CSV ----------
    results_df = pd.DataFrame([{
        "precision_anomaly": p,
        "recall_anomaly": r,
        "f1_anomaly": f1
    }])
    results_df.to_csv(VALIDATION_REPORT_FILE, index=False)

    print(f"[+] Saved validation metrics to: {VALIDATION_REPORT_FILE}")
    print()
    print("Validation completed successfully.")
    print("=" * 70)


if __name__ == "__main__":
    main()
