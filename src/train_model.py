# train_model.py
# Script 1/3: TRAINING ONLY
#
# Usage (from project root):
#   python -m src.train_model
#
# This will:
#   - Load labeled training logs from data/
#   - Run Stratified K-Fold model comparison
#   - Train the final model on full data
#   - Save it as models/best_model.joblib

from pathlib import Path
from typing import Tuple

import pandas as pd

from .model_utils import (
    evaluate_models_cv,
    train_final_model,
    save_model,
)


# =========================================================
# 1. CONFIG
# =========================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATA_DIR = PROJECT_ROOT / "data"
MODELS_DIR = PROJECT_ROOT / "models"
REPORTS_DIR = PROJECT_ROOT / "reports"

# Main training file (you can change this if needed)
TRAIN_FILE = DATA_DIR / "labeled_logs.csv"

# Output paths
CV_RESULTS_FILE = REPORTS_DIR / "train_cv_results.csv"
FINAL_MODEL_PATH = MODELS_DIR / "best_model.joblib"


# =========================================================
# 2. HELPERS
# =========================================================

def load_training_data(path: Path) -> Tuple[pd.DataFrame, pd.Series]:
    """
    Load the training dataset and return (df, y),
    where y is the anomaly label column.

    Supports either:
    - 'label' column (0/1)
    - 'is_anomaly' column (0/1)
    """
    if not path.exists():
        raise FileNotFoundError(
            f"Training file not found at: {path}\n"
            f"Please ensure 'labeled_logs.csv' (or adjust TRAIN_FILE) exists in data/."
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
            "Training labels contain only one class. "
            "Need both normal (0) and anomaly (1) samples."
        )

    return df, y


# =========================================================
# 3. MAIN TRAINING LOGIC
# =========================================================

def main():
    print("=" * 70)
    print("LOG ANOMALY DETECTOR – TRAINING SCRIPT")
    print("=" * 70)
    print(f"Project root : {PROJECT_ROOT}")
    print(f"Training file: {TRAIN_FILE}")
    print()

    # Ensure output dirs exist
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # ---------- Load data ----------
    print("[1] Loading training data...")
    df, y = load_training_data(TRAIN_FILE)
    print(f"    Loaded {len(df)} rows.")
    print(f"    Label distribution:\n{y.value_counts()}")
    print()

    # ---------- Cross-validation comparison ----------
    print("[2] Running Stratified K-Fold model comparison...")
    cv_results = evaluate_models_cv(df, y, requested_splits=5)
    print()
    print("Cross-validation results (sorted by F1 on anomaly class):")
    print(cv_results.to_string(index=False))
    print()

    # Save CV results to reports
    cv_results.to_csv(CV_RESULTS_FILE, index=False)
    print(f"[+] Saved CV results to: {CV_RESULTS_FILE}")
    print()

    # ---------- Train final model ----------
    # By default, choose the best model from CV table:
    best_model_name = cv_results.iloc[0]["model"]
    print(f"[3] Training final model on full data using: {best_model_name!r}")
    final_pipeline = train_final_model(df, y, model_type=best_model_name)

    # Save final pipeline
    save_model(final_pipeline, str(FINAL_MODEL_PATH))
    print(f"[+] Saved final model pipeline to: {FINAL_MODEL_PATH}")
    print()

    print("Training completed successfully.")
    print("=" * 70)


if __name__ == "__main__":
    main()
