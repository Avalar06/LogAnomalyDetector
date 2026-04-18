\# Adaptive ML-Based Log Anomaly Detection System



\## 📌 Overview



This project presents a \*\*real-time log anomaly detection system\*\* powered by Machine Learning. It continuously monitors system logs, detects anomalies using trained ML models, and visualizes them through an interactive dashboard.



The system is designed to simulate \*\*SOC (Security Operations Center)-style monitoring\*\*, enabling proactive detection of suspicious activities in log streams.



\---



\## 🎯 Objectives



\* Detect anomalies in log data using ML techniques

\* Provide real-time monitoring and visualization

\* Build a scalable and modular pipeline

\* Enable future SOC-level enhancements (alerts, actions, correlation)



\---



\## 🧠 Key Features



\### 🔍 Real-Time Log Monitoring



\* Continuous log ingestion using log tailing

\* Live anomaly detection pipeline



\### 🤖 Machine Learning Detection



\* TF-IDF based feature extraction

\* Random Forest classifier

\* Probability-based anomaly scoring



\### 📊 Interactive Dashboard



\* Real-time anomaly visualization

\* Filtering by:



&#x20; \* Service

&#x20; \* Time range

&#x20; \* Dataset source

\* Summary metrics and graphs



\### 📁 Multi-Dataset Support



\* Supports both:



&#x20; \* Live system logs

&#x20; \* Uploaded datasets (e.g., HDFS, ADFA)



\### ⚙️ Modular Architecture



\* Clean separation:



&#x20; \* Data processing

&#x20; \* Feature engineering

&#x20; \* Model inference

&#x20; \* Visualization



\---



\## 🏗️ System Architecture



```

Log Source → Log Tailer → Parser → Feature Extraction → ML Model → Anomaly Writer → Flask API → Dashboard

```



\---



\## 📂 Project Structure



```

LogAnomalyDetector/

│

├── app/                # Flask dashboard (frontend + API)

├── src/                # Core ML and processing logic

├── scripts/            # Data parsing and monitoring scripts

├── notebooks/          # Training, preprocessing, evaluation

├── reports/            # Evaluation results \& graphs

├── requirements.txt    # Dependencies

├── start\_all.bat       # Run full pipeline

└── .gitignore          # Ignored files (models, logs, data)

```



\---



\## ⚙️ Tech Stack



\* \*\*Backend:\*\* Python, Flask

\* \*\*ML:\*\* Scikit-learn (Random Forest, TF-IDF)

\* \*\*Frontend:\*\* HTML, CSS, JavaScript

\* \*\*Data Processing:\*\* Pandas, NumPy

\* \*\*Visualization:\*\* Chart.js / custom dashboard



\---



\## 📊 Model Performance



Trained on ADFA-LD dataset:



\* \*\*Accuracy:\*\* 96.61%

\* \*\*Precision:\*\* 0.896

\* \*\*Recall:\*\* 0.829

\* \*\*F1 Score:\*\* 0.861



Confusion matrices and performance graphs are available in the `reports/` folder.



\---



\## 🚀 How to Run



\### 1. Clone the repository



```

git clone https://github.com/Avalar06/LogAnomalyDetector.git

cd LogAnomalyDetector

```



\### 2. Install dependencies



```

pip install -r requirements.txt

```



\### 3. Start the system



```

start\_all.bat

```



\### 4. Run dashboard



```

cd app

set FLASK\_APP=app.py

flask run

```



\---



\## 📈 Use Cases



\* Security monitoring (SOC simulation)

\* Intrusion detection systems

\* Log analytics platforms

\* ML-based anomaly detection research



\---



\## 🔮 Future Enhancements



\* Anomaly lifecycle management (acknowledge, close, false positive)

\* Severity scoring and threat classification

\* Alerting system (email/SMS)

\* Correlation rules across logs

\* Cloud deployment (AWS / Azure)



\---



\## 👨‍💻 Author



\*\*Ayush Dutta\*\*

Master’s Student (BCA Background)

Project: End-Semester Dissertation



\---



\## 📜 License



This project is for academic and research purposes.



