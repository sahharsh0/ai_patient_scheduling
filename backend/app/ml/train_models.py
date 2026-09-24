"""
Train ML models for duration and no-show prediction.

There is intentionally NO waiting-time model here. The original version
trained one against `predicted_waiting_time`, which is circular (that column
is itself a prior prediction, not an observed value), and the seed data has
no real check-in/seen timestamps to derive an honest target from. Waiting
time is estimated deterministically at inference time instead (queue length
x historical average duration) — see app/ml/service.py.

Usage:
    python train_models.py --input dataset.csv --model-dir app/ml/models
"""

import argparse
import json
import os
import sys
from typing import Tuple

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, accuracy_score, roc_auc_score
from sklearn.preprocessing import StandardScaler
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app.ml.data.generate_dataset import load_appointments, engineer_features
from app.ml.categorical_maps import write_categorical_maps_json
from app.core.database import SessionLocal


def load_or_generate_data(input_csv: str = None) -> Tuple[pd.DataFrame, pd.DataFrame, list, list]:
    if input_csv and os.path.exists(input_csv):
        print(f"Loading dataset from {input_csv}")
        dataset = pd.read_csv(input_csv)
        target_columns = ['duration_minutes', 'no_show']
        if not all(col in dataset.columns for col in target_columns):
            raise ValueError(f"CSV must contain target columns: {target_columns}")
        features = dataset.drop(columns=[c for c in target_columns if c in dataset.columns])
        targets = dataset[target_columns]
        feature_names = list(features.columns)
        return features, targets, feature_names, target_columns
    else:
        print("Generating dataset from database...")
        session = SessionLocal()
        try:
            df = load_appointments(session)
            features, targets, feature_names, target_names = engineer_features(df)
            return features, targets, feature_names, target_names
        finally:
            session.close()


def train_models(features: pd.DataFrame, targets: pd.DataFrame, model_dir: str):
    os.makedirs(model_dir, exist_ok=True)

    if len(features) < 20:
        raise ValueError(
            f"Only {len(features)} training rows available — too few for a meaningful model. "
            "Seed the database with more historical appointments first (see seed.py)."
        )

    X_train, X_test, y_duration_train, y_duration_test = train_test_split(
        features, targets['duration_minutes'], test_size=0.2, random_state=42
    )
    # Only stratify on no_show if both classes are present.
    stratify = targets['no_show'] if targets['no_show'].nunique() > 1 else None
    X_train_ns, X_test_ns, y_no_show_train, y_no_show_test = train_test_split(
        features, targets['no_show'], test_size=0.2, random_state=42, stratify=stratify
    )

    numeric_features = features.columns.tolist()
    preprocessor = ColumnTransformer(
        transformers=[('num', Pipeline(steps=[('scaler', StandardScaler())]), numeric_features)]
    )

    print("Training duration prediction model...")
    duration_model = Pipeline(
        steps=[('preprocessor', preprocessor), ('regressor', RandomForestRegressor(n_estimators=200, random_state=42))]
    )
    duration_model.fit(X_train, y_duration_train)
    duration_mae = mean_absolute_error(y_duration_test, duration_model.predict(X_test))
    print(f"Duration MAE: {duration_mae:.2f} minutes")
    joblib.dump(duration_model, os.path.join(model_dir, 'duration_model.joblib'))

    print("Training no-show prediction model...")
    noshow_model = Pipeline(
        steps=[('preprocessor', preprocessor), ('classifier', RandomForestClassifier(n_estimators=200, random_state=42))]
    )
    noshow_model.fit(X_train_ns, y_no_show_train)
    noshow_pred = noshow_model.predict(X_test_ns)
    noshow_accuracy = accuracy_score(y_no_show_test, noshow_pred)
    if targets['no_show'].nunique() > 1:
        noshow_proba = noshow_model.predict_proba(X_test_ns)[:, 1]
        noshow_auc = roc_auc_score(y_no_show_test, noshow_proba)
        print(f"No-show Accuracy: {noshow_accuracy:.3f}, AUC: {noshow_auc:.3f}")
    else:
        print(f"No-show Accuracy: {noshow_accuracy:.3f} (AUC undefined — only one class present in training data)")
    joblib.dump(noshow_model, os.path.join(model_dir, 'noshow_model.joblib'))

    feature_names_path = os.path.join(model_dir, 'feature_names.json')
    with open(feature_names_path, 'w') as f:
        json.dump(list(features.columns), f)
    print(f"Feature names saved to {feature_names_path}")

    maps_path = write_categorical_maps_json(model_dir)
    print(f"Categorical maps saved to {maps_path}")

    # Remove any stale waiting_model.joblib from a previous version of this
    # script so a leftover file doesn't get mistaken for a live model.
    stale_waiting_model = os.path.join(model_dir, 'waiting_model.joblib')
    if os.path.exists(stale_waiting_model):
        os.remove(stale_waiting_model)
        print(f"Removed stale {stale_waiting_model} (waiting-time is now a deterministic estimate, not a trained model)")

    print(f"All models saved to {model_dir}")


def main():
    parser = argparse.ArgumentParser(description='Train ML models for SmartCare AI.')
    parser.add_argument('--input', type=str, default=None, help='Input CSV dataset (if omitted, generated from the DB)')
    parser.add_argument('--model-dir', type=str, default='app/ml/models', help='Directory to save trained models')
    args = parser.parse_args()

    features, targets, feature_names, target_names = load_or_generate_data(args.input)
    print(f"Features shape: {features.shape}")
    print(f"Targets shape: {targets.shape}")

    train_models(features, targets, args.model_dir)


if __name__ == '__main__':
    main()
