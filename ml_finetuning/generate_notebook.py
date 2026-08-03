import nbformat as nbf

nb = nbf.v4.new_notebook()

text_intro = """\
# Traditional ML Baseline (Member 2)
**Research Objective:** Establish the baseline accuracy and latency ceiling for the triage classification task using classical ML and TF-IDF.
**Targets:** `category`, `priority`, `sentiment`
**Approach:** 
- Feature Engineering: Combine text features, clean text, TF-IDF vectorization.
- Hyperparameter Tuning: Optuna optimization for Random Forest / LinearSVC.
- Evaluation: Custom classification report matching the exact requested format.
"""

code_setup = """\
!pip install optuna pandas scikit-learn numpy

import pandas as pd
import numpy as np
import optuna
import time
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, accuracy_score, f1_score, precision_score, recall_score
import warnings
warnings.filterwarnings('ignore')
"""

code_data = """\
# Load dataset
# Make sure to upload the dataset to Colab or mount Google Drive
df = pd.read_csv('curated_lms_tickets.csv')

# Drop unneeded columns as requested
cols_to_drop = ['channel', 'platform', 'source', 'ticket_id']
df = df.drop(columns=[col for col in cols_to_drop if col in df.columns])

# We only need the text to predict the labels (Category, Priority, Sentiment)
# Feature Engineering: Combine issue_description and product to enrich the TF-IDF context
df['text_feature'] = df['product'].astype(str) + " - " + df['issue_description'].astype(str)

# Clean text (lowercasing)
df['text_feature'] = df['text_feature'].str.lower()

# Define targets
targets = ['category', 'priority', 'sentiment']

# Stratified Train/Test Split (70/30)
# Note: For multi-label stratification, we stratify on Category as it's the primary label
X_train, X_test, y_train, y_test = train_test_split(
    df['text_feature'], 
    df[targets], 
    test_size=0.3, 
    random_state=42, 
    stratify=df['category']
)

print(f"Training samples: {len(X_train)}")
print(f"Testing samples: {len(X_test)}")
"""

code_tfidf = """\
# TF-IDF Vectorization
# We can tune max_features, ngram_range in Optuna, but for now we set a strong baseline.
vectorizer = TfidfVectorizer(max_features=5000, ngram_range=(1, 2), stop_words='english')

X_train_vec = vectorizer.fit_transform(X_train)
X_test_vec = vectorizer.transform(X_test)
"""

code_optuna = """\
# Optuna Hyperparameter Tuning for each Target
# We will use LinearSVC as it handles high-dimensional sparse TF-IDF data very fast and effectively.

best_models = {}

def optimize_target(target_name):
    print(f"--- Tuning for {target_name.upper()} ---")
    
    def objective(trial):
        # Hyperparameters to tune
        c_param = trial.suggest_float('C', 0.01, 10.0, log=True)
        # We could also test Random Forest, but SVM is vastly superior for TF-IDF.
        
        clf = LinearSVC(C=c_param, random_state=42, class_weight='balanced')
        clf.fit(X_train_vec, y_train[target_name])
        
        preds = clf.predict(X_test_vec)
        # Optimize for Macro F1
        f1 = f1_score(y_test[target_name], preds, average='macro')
        return f1
    
    study = optuna.create_study(direction='maximize')
    study.optimize(objective, n_trials=10) # Set to higher (e.g., 50) for better optimization
    
    print(f"Best trial for {target_name}: {study.best_value}")
    print(f"Best params for {target_name}: {study.best_params}")
    
    # Train best model
    best_clf = LinearSVC(C=study.best_params['C'], random_state=42, class_weight='balanced')
    best_clf.fit(X_train_vec, y_train[target_name])
    best_models[target_name] = best_clf

for target in targets:
    optimize_target(target)
"""

code_eval = """\
# Custom Evaluation Output exactly matching the requested format

def print_custom_report(y_true, y_pred, target_name):
    acc = accuracy_score(y_true, y_pred)
    macro_f1 = f1_score(y_true, y_pred, average='macro')
    macro_prec = precision_score(y_true, y_pred, average='macro')
    macro_rec = recall_score(y_true, y_pred, average='macro')
    
    print("================================================================================")
    print(f"*** {target_name.upper()}")
    print("================================================================================")
    print(f"Accuracy: {acc:.4f}")
    print(f"Macro F1: {macro_f1:.4f}")
    print(f"Macro Precision: {macro_prec:.4f}")
    print(f"Macro Recall: {macro_rec:.4f}")
    print("")
    
    # Classification report
    rep = classification_report(y_true, y_pred, digits=2)
    print(rep)

for target in targets:
    preds = best_models[target].predict(X_test_vec)
    print_custom_report(y_test[target], preds, target)
"""

code_optimization_tips = """\
# HOW TO OPTIMIZE THIS FURTHER:
# 1. Change TF-IDF 'max_features' to 10000 or None (all features).
# 2. Change TF-IDF 'ngram_range' to (1, 3) to capture 3-word phrases.
# 3. In the Optuna objective, add Random Forest as an alternative choice for the trial:
#    classifier_name = trial.suggest_categorical("classifier", ["LinearSVC", "RandomForest"])
# 4. Increase `n_trials=50` in Optuna to let it search longer.
"""

nb['cells'] = [
    nbf.v4.new_markdown_cell(text_intro),
    nbf.v4.new_code_cell(code_setup),
    nbf.v4.new_code_cell(code_data),
    nbf.v4.new_code_cell(code_tfidf),
    nbf.v4.new_code_cell(code_optuna),
    nbf.v4.new_code_cell(code_eval),
    nbf.v4.new_code_cell(code_optimization_tips)
]

with open('c:/Users/ranug/Clario/clario/ml_finetuning/Traditional_ML_Baseline.ipynb', 'w') as f:
    nbf.write(nb, f)
print("Notebook created successfully.")
