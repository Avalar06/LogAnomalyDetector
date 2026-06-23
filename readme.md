# Adaptive ML-Based Log Anomaly Detection System

## 1. Overview

This project presents an Adaptive Machine Learning-Based Log Anomaly Detection System designed for real-time cybersecurity monitoring. The system continuously ingests log data, extracts meaningful features, detects anomalous behavior using machine learning models, and visualizes security events through an interactive dashboard.

Unlike traditional static anomaly detection systems, the proposed framework incorporates a feedback-driven retraining mechanism that enables the model to adapt to changing log patterns and evolving security threats.

The architecture simulates a Security Operations Center (SOC)-style workflow, providing automated detection, visualization, analysis, and continuous model improvement.

---

## 2. Objectives

* Detect anomalous activities in system logs using machine learning techniques.
* Provide real-time monitoring and visualization of security events.
* Develop an adaptive retraining framework using analyst feedback.
* Improve detection accuracy through threshold optimization and validation.
* Build a scalable and modular cybersecurity monitoring platform.

---

## 3. System Architecture

The system follows a modular machine learning pipeline:

```text
Log Sources
      │
      ▼
Log Collection Layer
      │
      ▼
Log Parser & Preprocessing
      │
      ▼
Feature Engineering
(TF-IDF + Structured Features)
      │
      ▼
Machine Learning Model
(Random Forest Classifier)
      │
      ▼
Anomaly Detection Engine
      │
      ▼
Anomaly Writer
      │
      ▼
Flask API Layer
      │
      ▼
Interactive Dashboard
      │
      ▼
Feedback Collection
      │
      ▼
Adaptive Retraining Pipeline
```

---

## 4. Key Features

### 4.1 Real-Time Log Monitoring

* Continuous monitoring of incoming log streams.
* Live anomaly detection pipeline.
* Near real-time security event visualization.

### 4.2 Machine Learning-Based Detection

* TF-IDF text vectorization.
* Structured feature extraction.
* Random Forest-based classification.
* Probability-based anomaly confidence scoring.

### 4.3 Adaptive Retraining Framework

* Feedback-driven model improvement.
* Automated threshold optimization.
* Validation-gated deployment.
* Model version management.
* Continuous learning capability.

### 4.4 Interactive Dashboard

* Real-time anomaly monitoring.
* Historical anomaly visualization.
* Service-wise filtering.
* Host-wise filtering.
* Dataset source filtering.
* Dynamic charts and analytics.

### 4.5 Multi-Dataset Validation

The framework supports evaluation across multiple benchmark datasets:

* ADFA-LD Dataset
* HDFS Dataset
* BGL Dataset

This improves robustness and demonstrates model generalization across different log environments.

### 4.6 Modular Design

* Independent processing components.
* Extensible architecture.
* Easy integration of future machine learning models.
* Suitable for cybersecurity research and experimentation.

---

## 5. Project Structure

```text
LogAnomalyDetector/
│
├── app/                     # Flask dashboard and API
├── src/                     # Core preprocessing and ML logic
├── scripts/                 # Log monitoring and parsing scripts
├── notebooks/               # Data preparation and model development
├── reports/                 # Evaluation results and visualizations
├── retrain_with_feedback.py # Adaptive retraining module
├── requirements.txt         # Project dependencies
├── start_all.bat            # Startup automation script
└── .gitignore               # Ignored files and folders
```

---

## 6. Technology Stack

### Backend

* Python
* Flask

### Machine Learning

* Scikit-Learn
* Random Forest
* Logistic Regression
* Linear SVM
* TF-IDF Vectorization

### Data Processing

* Pandas
* NumPy

### Frontend

* HTML
* CSS
* JavaScript

### Visualization

* Chart.js
* Dashboard Analytics

### Development Tools

* Jupyter Notebook
* Git
* GitHub

---

## 7. Model Performance

The primary model was trained using the ADFA-LD dataset and validated across additional datasets.

### Final Performance Metrics

| Metric           | Value |
| ---------------- | ----- |
| Accuracy         | 96%   |
| Normal Precision | 97%   |
| Attack Precision | 88%   |
| Attack Recall    | 81%   |
| ROC-AUC          | ~0.98 |

The evaluation framework includes:

* Confusion Matrix Analysis
* ROC Curve Analysis
* Precision-Recall Analysis
* Threshold Optimization
* Feature Importance Analysis
* Calibration Analysis

Evaluation artifacts are available within the `reports/` directory.

---

## 8. Installation and Setup

### 8.1 Clone the Repository

```bash
git clone https://github.com/Avalar06/LogAnomalyDetector.git
cd LogAnomalyDetector
```

### 8.2 Install Dependencies

```bash
pip install -r requirements.txt
```

### 8.3 Start the System

```bash
start_all.bat
```

### 8.4 Run the Flask Dashboard

```bash
cd app
python app.py
```

### 8.5 Run Adaptive Retraining

```bash
python retrain_with_feedback.py
```

---

## 9. Use Cases

* Security Operations Center (SOC) Monitoring
* Intrusion Detection Systems
* Enterprise Log Analytics
* Security Research
* Machine Learning-Based Threat Detection
* Cybersecurity Education and Experimentation

---

## 10. Future Work

* Deep Learning-Based Log Analysis
* Transformer-Based Anomaly Detection
* Threat Intelligence Integration
* Automated Alerting System
* Severity and Risk Scoring
* Multi-Source Event Correlation
* Cloud Deployment
* SIEM Integration

---

## 11. Author

**Ayush Dutta**

M.Sc. IT (Cyber Security)

NSHM Knowledge Campus, Durgapur

MAKAUT University

End-Semester Dissertation Project

---

## 12. License

This project is intended for academic, educational, and research purposes.
