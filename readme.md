# Adaptive ML-Based Log Anomaly Detection System

## 1. Overview

This project presents a real-time log anomaly detection system powered by Machine Learning. The system continuously monitors log streams, detects anomalous patterns using trained models, and visualizes the results through an interactive dashboard.

The architecture is designed to simulate a Security Operations Center (SOC)-style monitoring workflow, enabling proactive identification of suspicious behavior in system logs.

---

## 2. Objectives

* Detect anomalies in log data using machine learning techniques
* Provide real-time monitoring and visualization
* Build a scalable and modular processing pipeline
* Support future SOC-level enhancements such as alerting and response actions

---

## 3. System Architecture

The system follows a modular pipeline:

Log Source → Log Tailer → Parser → Feature Extraction → ML Model → Anomaly Writer → Flask API → Dashboard

---

## 4. Key Features

### 4.1 Real-Time Log Monitoring

* Continuous ingestion of logs using a log tailing mechanism
* Streaming-based processing pipeline for live detection

### 4.2 Machine Learning-Based Detection

* TF-IDF vectorization for text-based feature extraction
* Random Forest classifier for anomaly detection
* Probability-based scoring for anomaly confidence

### 4.3 Interactive Dashboard

* Real-time visualization of detected anomalies
* Filtering capabilities based on:

  * Service
  * Time range
  * Dataset source
* Summary statistics and graphical insights

### 4.4 Multi-Dataset Support

* Supports both live system logs and uploaded datasets
* Flexible schema normalization for different log formats

### 4.5 Modular Design

* Separation of concerns across data ingestion, processing, inference, and visualization
* Extensible architecture for future enhancements

---

## 5. Project Structure

```
LogAnomalyDetector/
│
├── app/                # Flask application (dashboard and API)
├── src/                # Core logic (preprocessing, model, inference)
├── scripts/            # Log parsing and monitoring scripts
├── notebooks/          # Data preparation, training, evaluation
├── reports/            # Model evaluation results and visualizations
├── requirements.txt    # Python dependencies
├── start_all.bat       # Script to start the pipeline
└── .gitignore          # Ignored files (models, logs, datasets)
```

---

## 6. Technology Stack

* Backend: Python, Flask
* Machine Learning: Scikit-learn (Random Forest, TF-IDF)
* Data Processing: Pandas, NumPy
* Frontend: HTML, CSS, JavaScript
* Visualization: Chart-based dashboard

---

## 7. Model Performance

The model is trained on the ADFA-LD dataset.

* Accuracy: 96.61%
* Precision: 0.8962
* Recall: 0.8297
* F1 Score: 0.8617

Evaluation artifacts such as confusion matrices and performance graphs are available in the `reports/` directory.

---

## 8. Installation and Setup

### 8.1 Clone the Repository

```
git clone https://github.com/Avalar06/LogAnomalyDetector.git
cd LogAnomalyDetector
```

### 8.2 Install Dependencies

```
pip install -r requirements.txt
```

### 8.3 Run the System

```
start_all.bat
```

### 8.4 Start the Dashboard

```
cd app
set FLASK_APP=app.py
flask run
```

---

## 9. Use Cases

* Security monitoring systems
* Intrusion detection frameworks
* Log analytics platforms
* Machine learning research in anomaly detection

---

## 10. Future Work

* Implementation of anomaly lifecycle management (acknowledge, close, false positive)
* Severity scoring and risk classification
* Alerting mechanisms (email or notification-based)
* Correlation of anomalies across multiple sources
* Deployment in cloud environments

---

## 11. Author

Ayush Dutta
Master’s Student (BCA Background)
End-Semester Dissertation Project

---

## 12. License

This project is intended for academic and research purposes.
