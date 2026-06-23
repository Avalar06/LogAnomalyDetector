import pandas as pd
import json
import os
import re
import joblib
import numpy as np
import shutil
from datetime import datetime

from sklearn.model_selection import GridSearchCV
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    precision_score,
    recall_score,
    f1_score
)
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer

# ===============================
# PATH SETUP
# ===============================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

original_data_path = os.path.join(
    BASE_DIR,
    "data",
    "labeled_logs_large.csv"
)

feedback_data_path = os.path.join(
    BASE_DIR,
    "app",
    "data",
    "feedback_dataset_clean.csv"
)

vectorizer_path = os.path.join(
    BASE_DIR,
    "models",
    "tfidf_vectorizer.joblib"
)

retraining_history_path = os.path.join(
    BASE_DIR,
    "logs",
    "retraining_history.json"
)

# ===============================
# LOAD DATASETS (SAFE)
# ===============================
if not os.path.exists(original_data_path):
    raise FileNotFoundError(
        f"Original dataset not found: {original_data_path}"
    )

if not os.path.exists(feedback_data_path):
    raise FileNotFoundError(
        f"Feedback dataset not found: {feedback_data_path}"
    )

df_original = pd.read_csv(original_data_path)
df_feedback = pd.read_csv(feedback_data_path)

# ===============================
# FEEDBACK DATA CLEANING
# ===============================
initial_feedback_size = len(df_feedback)

# Remove duplicate rows
df_feedback = df_feedback.drop_duplicates()

# ===============================
# RESOLVE CONFLICTING LABELS
# ===============================
initial_conflict_size = len(df_feedback)

# Keep latest label occurrence
df_feedback = df_feedback.drop_duplicates(
    subset=["message"],
    keep="last"
)

final_conflict_size = len(df_feedback)

print(
    f"Resolved "
    f"{initial_conflict_size - final_conflict_size} "
    f"conflicting feedback entries"
)

# Keep only valid labels
df_feedback = df_feedback[
    df_feedback["true_label"].isin([0, 1])
]

final_feedback_size = len(df_feedback)

print(
    f"\nFeedback cleaning completed:"
)

print(
    f"Removed "
    f"{initial_feedback_size - final_feedback_size} "
    f"duplicate/invalid rows"
)

print(
    f"Clean feedback samples: "
    f"{final_feedback_size}"
)

print("Original dataset shape:", df_original.shape)
print("Feedback dataset shape:", df_feedback.shape)

# ===============================
# VALIDATION
# ===============================
REQUIRED_COLS = ["message", "true_label"]

for col in REQUIRED_COLS:

    if col not in df_original.columns:
        raise ValueError(
            f"Missing column '{col}' in original dataset"
        )

    if col not in df_feedback.columns:
        raise ValueError(
            f"Missing column '{col}' in feedback dataset"
        )

# ===============================
# CLEAN FEEDBACK DATA
# ===============================
df_feedback = df_feedback.dropna(
    subset=["message", "true_label"]
)

df_feedback["message"] = (
    df_feedback["message"]
    .astype(str)
    .str.strip()
)

def extract_structured_features(df):

    messages = df["message"].fillna("").astype(str)

    features = pd.DataFrame()

    # 1. Message Length
    features["message_length"] = messages.apply(len)

    # 2. Digit Ratio
    features["digit_ratio"] = messages.apply(
        lambda x: (
            sum(c.isdigit() for c in x)
            / max(len(x), 1)
        )
    )

    # 3. Uppercase Ratio
    features["uppercase_ratio"] = messages.apply(
        lambda x: (
            sum(c.isupper() for c in x)
            / max(len(x), 1)
        )
    )

    # 4. Special Character Count
    features["special_char_count"] = messages.apply(
        lambda x: len(
            re.findall(r'[^a-zA-Z0-9\s]', x)
        )
    )

    # 5. Contains IP
    features["contains_ip"] = messages.apply(
        lambda x: int(bool(
            re.search(
                r'\b(?:\d{1,3}\.){3}\d{1,3}\b',
                x
            )
        ))
    )

    # 6. Contains Failed
    features["contains_failed"] = messages.str.contains(
        "failed",
        case=False,
        na=False
    ).astype(int)

    # 7. Contains Error
    features["contains_error"] = messages.str.contains(
        "error",
        case=False,
        na=False
    ).astype(int)

    # 8. Contains Warning
    features["contains_warning"] = messages.str.contains(
        "warning",
        case=False,
        na=False
    ).astype(int)

    # 9. Contains Admin
    features["contains_admin"] = messages.str.contains(
        "admin",
        case=False,
        na=False
    ).astype(int)

    # 10. Contains Login
    features["contains_login"] = messages.str.contains(
        "login",
        case=False,
        na=False
    ).astype(int)

    return features

# =====================================
# DETECT VECTOR-LIKE ROWS
# =====================================
def is_vector_like(message):

    message = str(message)

    if len(message) == 0:
        return False

    comma_ratio = (
        message.count(",")
        / max(len(message), 1)
    )

    digit_ratio = (
        sum(c.isdigit() for c in message)
        / max(len(message), 1)
    )

    return (
        comma_ratio > 0.30
        and digit_ratio > 0.50
    )

# ===============================
# MERGE DATASETS
# ===============================
df_combined = pd.concat(
    [df_original, df_feedback],
    ignore_index=True
)

print("Combined dataset shape:", df_combined.shape)

# ===============================
# TEST STRUCTURED FEATURES
# ===============================
structured_features = extract_structured_features(
    df_combined
)

# ===============================
# INSPECT EXTREME MESSAGE LENGTHS
# ===============================

largest_messages = df_combined.copy()

largest_messages["message_length"] = (
    structured_features["message_length"]
)

largest_messages = largest_messages.sort_values(
    by="message_length",
    ascending=False
)

print("\n=== TOP 5 LARGEST MESSAGES ===")

for i, row in largest_messages.head(5).iterrows():

    print("\n----------------------------")
    print(f"Row Index : {i}")
    print(f"Length    : {row['message_length']}")

    print("\nMessage Preview:")

    print(str(row["message"])[:1000])



# ===============================
# DETECT VECTOR-LIKE ROWS
# ===============================

vector_like_mask = df_combined["message"].apply(
    is_vector_like
)

vector_like_rows = df_combined[
    vector_like_mask
]

# Remove vector-like corrupted rows
df_combined = df_combined[
    ~vector_like_mask
]

print(
    f"\nDataset shape after filtering: "
    f"{df_combined.shape}"
)

# Rebuild structured features after filtering
structured_features = extract_structured_features(
    df_combined
)

print("\nStructured Features Sample:")
print(structured_features.head())

print("\nStructured Feature Info:")
print(structured_features.info())

print("\nStructured Feature Statistics:")
print(structured_features.describe())

print("\nMissing Values:")
print(structured_features.isnull().sum())

print("\n=== VECTOR-LIKE ROW DETECTION ===")

print(
    f"Detected vector-like rows: "
    f"{len(vector_like_rows)}"
)

print("\nSample vector-like rows:")

for i, row in vector_like_rows.head(3).iterrows():

    print("\n----------------------------")
    print(f"Row Index : {i}")

    print("\nPreview:")

    print(str(row["message"])[:500])

# ===============================
# LABEL DISTRIBUTION
# ===============================
print("\nLabel distribution:")
print(df_combined["true_label"].value_counts())

# ===============================
# SPLIT FEATURES AND LABELS
# ===============================
X = df_combined["message"]
y = df_combined["true_label"]

# ===============================
# ARCHIVE / VERSIONING SETUP
# ===============================
archive_dir = os.path.join(
    BASE_DIR,
    "models",
    "archive"
)

os.makedirs(archive_dir, exist_ok=True)

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

# ===============================
# TF-IDF VECTORIZER
# ===============================
vectorizer = TfidfVectorizer(
    max_features=3000,
    ngram_range=(1, 2),
    min_df=2,
    max_df=0.95,
    sublinear_tf=True
)

X_features = vectorizer.fit_transform(X)

# ===============================
# SAVE VECTORIZER
# ===============================
# ===============================
# BACKUP EXISTING VECTORIZER
# ===============================
if os.path.exists(vectorizer_path):
    
    archived_vectorizer_path = os.path.join(
        archive_dir,
        f"tfidf_vectorizer_{timestamp}.joblib"
    )

    shutil.copy2(
        vectorizer_path,
        archived_vectorizer_path
    )

    print(
        f"\nExisting vectorizer backed up to:\n"
        f"{archived_vectorizer_path}"
    )

# ===============================
# SAVE NEW VECTORIZER
# ===============================
joblib.dump(vectorizer, vectorizer_path)

print("\nNew vectorizer trained successfully")
print("\nFeature matrix shape:", X_features.shape)

# ===============================
# TRAIN TEST SPLIT
# ===============================
X_train, X_test, y_train, y_test = train_test_split(
    X_features,
    y,
    test_size=0.3,
    stratify=y,
    random_state=42
)

print("\nTrain shape:", X_train.shape)
print("Test shape:", X_test.shape)

# ===============================
# PARAM GRID
# ===============================
param_grid = {
    "n_estimators": [100, 200],
    "max_depth": [None, 20, 40],
    "min_samples_split": [2, 5],
    "min_samples_leaf": [1, 2]
}

# ===============================
# GRID SEARCH
# ===============================
grid_search = GridSearchCV(
    estimator=RandomForestClassifier(
        class_weight="balanced",
        random_state=42,
        n_jobs=-1
    ),
    param_grid=param_grid,
    scoring="f1",
    cv=3,
    verbose=1,
    n_jobs=-1
)

grid_search.fit(X_train, y_train)

print("\nBest Parameters:")
print(grid_search.best_params_)

best_model = grid_search.best_estimator_

# ===============================
# CALIBRATION
# ===============================
model = CalibratedClassifierCV(
    estimator=best_model,
    method="sigmoid",
    cv=3
)

model.fit(X_train, y_train)

print("\nTuned + Calibrated model trained successfully")

# ===============================
# SAVE MODEL
# ===============================
model_path = os.path.join(
    BASE_DIR,
    "models",
    "best_model.joblib"
)

# ===============================
# BACKUP EXISTING MODEL
# ===============================

# Backup old model
if os.path.exists(model_path):

    archived_model_path = os.path.join(
        archive_dir,
        f"best_model_{timestamp}.joblib"
    )

    shutil.copy2(model_path, archived_model_path)

    print(
        f"\nExisting model backed up to:\n"
        f"{archived_model_path}"
    )

# ===============================
# SAVE NEW MODEL
# ===============================
# Model deployment temporarily delayed
# until validation gate passes

# ===============================
# PREDICT PROBABILITIES
# ===============================
y_proba = model.predict_proba(X_test)[:, 1]

# ===============================
# SEVERITY LOGIC
# ===============================
def get_severity(prob):

    if prob >= 0.75:
        return "HIGH"

    elif prob >= 0.55:
        return "MEDIUM"

    else:
        return "LOW"

print("\nSample severity mapping:")

for i in range(min(10, len(y_proba))):
    print(y_proba[i], "->", get_severity(y_proba[i]))

# ===============================
# DEFAULT THRESHOLD EVALUATION
# ===============================
threshold = 0.55

y_pred = (y_proba >= threshold).astype(int)

print(f"\n=== Threshold ({threshold}) ===")

print("\nConfusion Matrix:")
print(confusion_matrix(y_test, y_pred))

print("\nClassification Report:")
print(classification_report(y_test, y_pred))

# ===============================
# SAMPLE PROBABILITIES
# ===============================
print("\nSample probabilities:")
print(y_proba[:10])

MIN_PRECISION = 0.88
MIN_RECALL = 0.80
MIN_F1 = 0.85
F1_TOLERANCE = 0.01

# ===============================
# AUTOMATED THRESHOLD EVALUATION
# ===============================
print("\n=== Automated Threshold Evaluation ===")

thresholds = np.arange(0.10, 0.96, 0.05)
best_threshold = None
best_f1 = 0
best_precision = 0
best_recall = 0

for t in thresholds:

    y_pred_auto = (y_proba >= t).astype(int)

    precision = precision_score(
        y_test,
        y_pred_auto
    )

    recall = recall_score(
        y_test,
        y_pred_auto
    )

    f1 = f1_score(
        y_test,
        y_pred_auto
    )

    # Only consider thresholds that satisfy deployment requirements
    if (
        precision >= MIN_PRECISION
        and recall >= MIN_RECALL
        and f1 >= (MIN_F1 - F1_TOLERANCE)
    ):

        if f1 > best_f1:
            best_f1 = f1
            best_threshold = t
            best_precision = precision
            best_recall = recall

    print(
        f"Threshold={t:.2f} | "
        f"Precision={precision:.3f} | "
        f"Recall={recall:.3f} | "
        f"F1={f1:.3f}"
    )

print("\n=== Recommended Threshold ===")

if best_threshold is not None:

    print(
        f"Best Threshold : {best_threshold:.2f}"
    )

    print(
        f"Best F1 Score  : {best_f1:.3f}"
    )

    print(
        f"Precision      : {best_precision:.3f}"
    )

    print(
        f"Recall         : {best_recall:.3f}"
    )

else:

    print(
        "No threshold satisfied deployment requirements."
    )

    print(
        f"Required: Precision>={MIN_PRECISION}, "
        f"Recall>={MIN_RECALL}, "
        f"F1>={MIN_F1 - F1_TOLERANCE:.2f}"
    )
# ===============================
# CUSTOM THRESHOLD EVALUATION
# ===============================
if best_threshold is not None:
    threshold = best_threshold
else:
    threshold = 0.55

print(f"\nDeployment Threshold Used: {threshold:.2f}")

y_pred_custom = (y_proba >= threshold).astype(int)

print(f"\n=== Custom Threshold ({threshold}) ===")

print("\nConfusion Matrix (Custom):")
print(confusion_matrix(y_test, y_pred_custom))

print("\nClassification Report (Custom):")
print(classification_report(y_test, y_pred_custom))



#=================================================
# ===============================
# RETRAINING HISTORY LOGGING
# ===============================
history_data = []

# Load existing history safely
if os.path.exists(retraining_history_path):

    try:
        with open(
            retraining_history_path,
            "r"
        ) as f:

            content = f.read().strip()

            if content:
                history_data = json.loads(content)

    except Exception as e:
        print(
            f"\nWarning: Could not read "
            f"retraining history: {e}"
        )
# ===============================
# VALIDATION GATE
# ===============================

final_precision = precision_score(
    y_test,
    y_pred_custom
)

final_recall = recall_score(
    y_test,
    y_pred_custom
)

final_f1 = f1_score(
    y_test,
    y_pred_custom
)

print("\nValidation Gate Check:")
print(f"Precision : {final_precision:.4f}")
print(f"Recall    : {final_recall:.4f}")
print(f"F1 Score  : {final_f1:.4f}")

validation_passed = (
    final_precision >= MIN_PRECISION
    and final_recall >= MIN_RECALL
    and final_f1 >= (MIN_F1 - F1_TOLERANCE)
)

deployment_status = (
    "DEPLOYED"
    if validation_passed
    else "FAILED"
)

# ===============================
# SAFE DEPLOYMENT DECISION
# ===============================

if validation_passed:

    # Deploy validated model
    joblib.dump(model, model_path)

    print(
        "\nModel PASSED validation "
        "and was deployed successfully"
    )

else:

    print(
        "\nModel FAILED validation."
    )

    print(
        "Production model remains unchanged."
    )
# ===============================
# RETRAINING HISTORY LOGGING
# ===============================
history_entry = {
    "timestamp": timestamp,
    "dataset_size": int(len(df_combined)),
    "feedback_samples": int(len(df_feedback)),

    # Validation threshold actually used
    "threshold": float(threshold),

    # Metrics at deployed/validation threshold
    "precision": float(
        precision_score(y_test, y_pred_custom)
    ),

    "recall": float(
        recall_score(y_test, y_pred_custom)
    ),

    "f1_score": float(
        f1_score(y_test, y_pred_custom)
    ),

    # Grid Search result
    "best_params": grid_search.best_params_,

    # Automated threshold search result
    "best_threshold": float(best_threshold),

    "best_precision": float(
        best_precision
    ),

    "best_recall": float(
        best_recall
    ),

    "best_f1": float(
        best_f1
    ),

    # Deployment outcome
    "deployment_status": deployment_status
}
# Append new entry
history_data.append(history_entry)

# Save updated history
with open(
    retraining_history_path,
    "w"
) as f:

    json.dump(
        history_data,
        f,
        indent=4
    )

print(
    "\nRetraining history updated successfully"
)