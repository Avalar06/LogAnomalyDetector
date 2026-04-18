#This file is needed because,
#Without this file, Python doesn’t treat src as a proper package, and commands like:

#python -m src.train_model
#python -m src.validate_model
#python -m src.test_model
#python -m src.log_tailer_windows
#may fail or behave inconsistently.
#-----------------------------
#With __init__.py present:

#src becomes a package

#python -m src.something works cleanly

#The whole “3-script structure” looks more professional
#----------------------------------------------

"""
src package

This package contains all core modules for the
Adaptive ML-Based Log Anomaly Detection System:

- preprocessing.py      : cleaning + feature engineering
- model_utils.py        : model building, CV, train/save/load
- train_model.py        : training-only script
- validate_model.py     : validation-only script
- test_model.py         : testing/demo script
- log_tailer_windows.py : Windows log simulator for demo

The presence of this file allows commands like:
    python -m src.train_model
to work correctly from the project root.
"""

