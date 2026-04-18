# model_utils.py
# Shared ML utilities: model definitions, CV training, final training, save/load helpers.

from typing import Dict, Tuple, Any, List

import joblib
import numpy as np
import pandas as pd

from sklearn.linear_model import LogisticRegression
from sklearn.svm import LinearSVC
from sklearn.ensemble import RandomForestClassifier, IsolationForest
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import precision_recall_fscore_support

from sklearn.pipeline import Pipeline

from .preprocessing import build_preprocessor, prepare_dataframe


# =========================================================
# 1. BUILD BASE MODELS
# =========================================================

def build_base_models() -> Dict[str, Any]:
    """
    Define the base estimators we want to compare.
    Note: IsolationForest is unsupervised; we will treat it separately if needed.
    """
    models = {
        "logreg": LogisticRegression(
            max_iter=500,
            class_weight="balanced",
            n_jobs=-1
        ),
        "linear_svm": LinearSVC(
            class_weight="balanced"
        ),
        "random_forest": RandomForestClassifier(
            n_estimators=200,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1
        )
        # If you want to experiment with IsolationForest later,
        # you can add it as a separate pipeline.
    }
    return models


# =========================================================
# 2. PIPELINE BUILDER
# =========================================================

def build_pipeline(estimator: Any) -> Pipeline:
    """
    Build the full pipeline:
    - Preprocessor (TF-IDF + OHE + numeric)
    - Classifier (LogReg / LinearSVM / RandomForest)
    """
    preprocessor = build_preprocessor()
    pipeline = Pipeline(steps=[
        ('preprocessor', preprocessor),
        ('classifier', estimator)
    ])
    return pipeline


# =========================================================
# 3. ADAPTIVE STRATIFIED K-FOLD
# =========================================================

def _get_valid_n_splits(y: np.ndarray, requested_splits: int = 5) -> int:
    """
    Ensure that the number of splits does not exceed the count
    of the minority class, otherwise StratifiedKFold will fail.
    """
    unique, counts = np.unique(y, return_counts=True)
    class_counts = dict(zip(unique, counts))

    # minority class count
    min_count = min(class_counts.values())

    if min_count < requested_splits:
        # at least 2 splits to still have some sort of validation
        n_splits = max(2, min_count)
    else:
        n_splits = requested_splits

    return n_splits


# =========================================================
# 4. K-FOLD MODEL COMPARISON
# =========================================================

def evaluate_models_cv(
    df: pd.DataFrame,
    y: pd.Series,
    requested_splits: int = 5,
    random_state: int = 42
) -> pd.DataFrame:
    """
    Run Stratified K-Fold cross-validation on all base models.
    Focus on the anomaly (1) class: precision, recall, F1.
    """
    X = prepare_dataframe(df)
    y = y.values

    n_splits = _get_valid_n_splits(y, requested_splits=requested_splits)
    skf = StratifiedKFold(
        n_splits=n_splits,
        shuffle=True,
        random_state=random_state
    )

    base_models = build_base_models()

    rows: List[Dict[str, Any]] = []

    for model_name, estimator in base_models.items():
        pipeline = build_pipeline(estimator)

        precisions: List[float] = []
        recalls: List[float] = []
        f1s: List[float] = []

        for train_idx, test_idx in skf.split(X, y):
            X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
            y_train, y_test = y[train_idx], y[test_idx]

            pipeline.fit(X_train, y_train)
            y_pred = pipeline.predict(X_test)

            # focus on anomaly class (assumed label 1)
            p, r, f1, _ = precision_recall_fscore_support(
                y_test,
                y_pred,
                pos_label=1,
                average='binary',
                zero_division=0
            )

            precisions.append(p)
            recalls.append(r)
            f1s.append(f1)

        rows.append({
            "model": model_name,
            "n_splits": n_splits,
            "precision_mean": np.mean(precisions),
            "precision_std": np.std(precisions),
            "recall_mean": np.mean(recalls),
            "recall_std": np.std(recalls),
            "f1_mean": np.mean(f1s),
            "f1_std": np.std(f1s),
        })

    results_df = pd.DataFrame(rows).sort_values(by="f1_mean", ascending=False)
    return results_df


# =========================================================
# 5. TRAIN THE FINAL MODEL ON FULL DATA
# =========================================================

def train_final_model(
    df: pd.DataFrame,
    y: pd.Series,
    model_type: str = "random_forest"
) -> Pipeline:
    """
    Train the final pipeline on the full dataset using the chosen model.
    Default: RandomForest (based on your earlier experiments).
    """
    X = prepare_dataframe(df)
    base_models = build_base_models()

    if model_type not in base_models:
        raise ValueError(f"Unknown model_type '{model_type}'. "
                         f"Available: {list(base_models.keys())}")

    estimator = base_models[model_type]
    pipeline = build_pipeline(estimator)
    pipeline.fit(X, y.values)

    return pipeline


# =========================================================
# 6. SAVE / LOAD HELPERS
# =========================================================

def save_model(model: Pipeline, path: str) -> None:
    """Save the full pipeline (preprocessor + classifier) to disk."""
    joblib.dump(model, path)


def load_model(path: str) -> Pipeline:
    """Load a previously saved pipeline."""
    model = joblib.load(path)
    return model
