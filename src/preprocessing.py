# preprocessing.py
# All cleaning, masking, and feature engineering logic for the anomaly detector.

import re
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline


# =========================================================
# 1. BASIC TEXT CLEANING + MASKING FUNCTIONS
# =========================================================

def clean_log_message(msg: str) -> str:
    """Clean log message by applying masking patterns."""
    if pd.isna(msg):
        return ""

    msg = str(msg)

    # Mask IPv4 addresses
    msg = re.sub(r'\b\d{1,3}(?:\.\d{1,3}){3}\b', ' <IP> ', msg)

    # Mask file paths
    msg = re.sub(r'(/[A-Za-z0-9._-]+)+', ' <PATH> ', msg)

    # Mask long numbers (IDs, PIDs, ports, codes)
    msg = re.sub(r'\b\d{4,}\b', ' <NUM> ', msg)

    # Mask usernames and system accounts
    msg = re.sub(r'\buser=[A-Za-z0-9._-]+\b', ' user=<USER> ', msg)

    # Mask MAC addresses
    msg = re.sub(r'\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b', ' <MAC> ', msg)

    # Remove extra spaces
    msg = re.sub(r'\s+', ' ', msg).strip()

    return msg


# =========================================================
# 2. NUMERIC + BEHAVIORAL FEATURE EXTRACTION
# =========================================================

def extract_numeric_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add engineered numeric features:
    - hour, weekday
    - digit_count, path_count
    - msg_length
    - pid (if present)
    """

    df = df.copy()

    # Ensure timestamp parsing
    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')

    df['hour'] = df['timestamp'].dt.hour.fillna(0).astype(int)
    df['weekday'] = df['timestamp'].dt.weekday.fillna(0).astype(int)

    df['digit_count'] = df['message'].apply(lambda x: sum(c.isdigit() for c in str(x)))
    df['path_count'] = df['message'].str.count(r'/')

    df['msg_length'] = df['message'].apply(lambda x: len(str(x)))

    # Extract PID if present
    df['pid'] = df['message'].str.extract(r'pid=(\d+)')
    df['pid'] = df['pid'].fillna(0).astype(int)

    return df


# =========================================================
# 3. COLUMN TRANSFORMER BUILDER
# =========================================================

def build_preprocessor():
    """
    Build a unified ColumnTransformer:
    - TF-IDF for text (max_features=500, 1-2 grams)
    - OHE for categorical (host, service)
    - StandardScaler for numeric engineered features
    """

    text_features = 'cleaned_message'
    categorical_features = ['host', 'service']
    numeric_features = [
        'hour', 'weekday', 'digit_count',
        'path_count', 'msg_length', 'pid'
    ]

    preprocessor = ColumnTransformer(
        transformers=[
            ('tfidf', TfidfVectorizer(max_features=500,
                                     ngram_range=(1, 2)),
             text_features),

            ('ohe', OneHotEncoder(handle_unknown='ignore'),
             categorical_features),

            ('num', StandardScaler(),
             numeric_features)
        ],
        remainder='drop'
    )

    return preprocessor


# =========================================================
# 4. FINAL MASTER FUNCTION (used before training/inference)
# =========================================================

def prepare_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Clean + extract all features before model training/inference."""
    df = df.copy()

    # Apply cleaning
    df['cleaned_message'] = df['message'].apply(clean_log_message)

    # Extract numeric engineered features
    df = extract_numeric_features(df)

    # Ensure host and service exist
    if 'host' not in df.columns:
        df['host'] = 'unknown'

    if 'service' not in df.columns:
        df['service'] = 'unknown'

    return df
