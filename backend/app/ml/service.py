"""
ML prediction service for SmartCare AI.

Provides duration and no-show predictions from trained scikit-learn models
(falling back to fixed heuristics if a model isn't available), plus a
DETERMINISTIC waiting-time estimate — there is no trained waiting-time model
(see app/ml/train_models.py for why) and this module is explicit about that:
`estimate_waiting_time_minutes` is documented as an estimate, not a
prediction, and its output is never presented to the user as "the model
predicted X".
"""

import json
import os
from datetime import datetime
from typing import Dict, Any, Optional
import logging

import joblib
import numpy as np
import pandas as pd
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Appointment, Doctor, Patient
from app.models.enums import AppointmentStatus
from app.ml.categorical_maps import encode_appointment_type, encode_booking_source
from app.scheduling.slots import ACTIVE_APPOINTMENT_STATUSES

logger = logging.getLogger(__name__)

DURATION_MODEL_FILE = 'duration_model.joblib'
NOSHOW_MODEL_FILE = 'noshow_model.joblib'
FEATURE_NAMES_FILE = 'feature_names.json'
MODEL_VERSION = 'rf-v3-dataframe-input'

_duration_model = None
_noshow_model = None
_feature_names = None
_loaded_model_dir = None

FALLBACK_DURATION = 30.0  # minutes
FALLBACK_NOSHOW_PROB = 0.1  # 10%
FALLBACK_WAITING_TIME = 5.0  # minutes


def _default_model_dir() -> str:
    """
    Resolve settings.ML_MODEL_DIR. If it's a relative path (the common case,
    e.g. "app/ml/models"), resolve it relative to the backend project root
    (two levels up from this file: app/ml/service.py -> app/ml -> app -> root),
    not the current working directory, so it works the same whether uvicorn
    is started from the repo root or from inside backend/.
    """
    configured = settings.ML_MODEL_DIR
    if os.path.isabs(configured):
        return configured
    backend_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    return os.path.join(backend_root, configured)


def _load_models(model_dir: Optional[str] = None):
    global _duration_model, _noshow_model, _feature_names, _loaded_model_dir

    model_dir = model_dir or _default_model_dir()
    feature_names_path = os.path.join(model_dir, FEATURE_NAMES_FILE)

    if not os.path.exists(feature_names_path):
        logger.warning(f"Feature names file not found at {feature_names_path}; using fallback predictions.")
        _duration_model = _noshow_model = None
        _feature_names = None
        _loaded_model_dir = model_dir
        return

    try:
        with open(feature_names_path, 'r') as f:
            _feature_names = json.load(f)

        duration_path = os.path.join(model_dir, DURATION_MODEL_FILE)
        noshow_path = os.path.join(model_dir, NOSHOW_MODEL_FILE)
        _duration_model = joblib.load(duration_path) if os.path.exists(duration_path) else None
        _noshow_model = joblib.load(noshow_path) if os.path.exists(noshow_path) else None
        _loaded_model_dir = model_dir
    except Exception as e:
        logger.error(f"Error loading ML models from {model_dir}: {e}")
        _duration_model = _noshow_model = None
        _feature_names = None


def _get_models_and_features(model_dir: Optional[str] = None):
    global _duration_model, _noshow_model, _feature_names, _loaded_model_dir
    resolved_dir = model_dir or _default_model_dir()
    if _feature_names is None or _loaded_model_dir != resolved_dir:
        _load_models(model_dir)
    return _duration_model, _noshow_model, _feature_names


def _features_to_array(features: Dict[str, Any], feature_names: list) -> pd.DataFrame:
    """
    Build a single-row pandas DataFrame with columns named EXACTLY like
    feature_names (the same names train_models.py used to fit the
    ColumnTransformer). The trained pipelines select columns by string
    name, so a plain numpy ndarray will not work here — sklearn raises
    "Specifying the columns using strings is only supported for
    dataframes." A DataFrame keeps the column order/naming exactly in
    sync with what the model was fit on, regardless of dict key order.
    """
    row = {}
    for fname in feature_names:
        try:
            row[fname] = float(features.get(fname, 0.0))
        except (ValueError, TypeError):
            row[fname] = 0.0
    return pd.DataFrame([row], columns=feature_names)


def _historical_stats(db: Session, filter_column, filter_value) -> Dict[str, float]:
    """Shared helper: avg real duration_minutes + no_show rate (via status ==
    no_show, NOT a nonexistent boolean column) + total count for a doctor or patient."""
    past_condition = filter_column == filter_value
    stats = (
        db.query(
            func.avg(Appointment.duration_minutes).label('avg_duration'),
            func.avg(func.if_(Appointment.status == AppointmentStatus.no_show, 1, 0)).label('no_show_rate'),
            func.count(Appointment.id).label('total_appointments'),
        )
        .filter(past_condition)
        .first()
    )
    if not stats or stats.total_appointments == 0:
        return {'avg_duration': 0.0, 'no_show_rate': 0.0, 'total_appointments': 0}
    return {
        'avg_duration': float(stats.avg_duration or 0.0),
        'no_show_rate': float(stats.no_show_rate or 0.0),
        'total_appointments': stats.total_appointments or 0,
    }


def get_doctor_historical_stats(db: Session, doctor_id: int) -> Dict[str, float]:
    return _historical_stats(db, Appointment.doctor_id, doctor_id)


def get_patient_historical_stats(db: Session, patient_id: int) -> Dict[str, float]:
    return _historical_stats(db, Appointment.patient_id, patient_id)


def _compute_features_for_appointment(
    session: Session,
    doctor_id: int,
    patient_id: Optional[int],
    appointment_datetime: datetime,
    appointment_type: str,
    booking_source: str,
    specialization_id: int,
    doctor_historical: Optional[Dict[str, Any]] = None,
    patient_historical: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    features: Dict[str, Any] = {}

    doctor = session.get(Doctor, doctor_id)
    features['experience_years'] = doctor.experience_years if doctor else 0
    features['consultation_fee'] = float(doctor.consultation_fee or 0.0) if doctor else 0.0
    features['rating'] = float(doctor.rating or 0.0) if doctor else 0.0
    features['doctor_specialization_id'] = (doctor.specialization_id if doctor else 0) or 0

    patient = session.get(Patient, patient_id) if patient_id else None
    if patient and patient.date_of_birth:
        age = (appointment_datetime.date() - patient.date_of_birth).days / 365.25
        features['patient_age'] = max(0.0, age)
    else:
        features['patient_age'] = 0.0

    features['start_hour'] = appointment_datetime.hour
    features['start_day_of_week'] = appointment_datetime.weekday()
    features['start_month'] = appointment_datetime.month
    features['is_weekend'] = 1 if features['start_day_of_week'] in (5, 6) else 0

    # Fixed vocabulary encoding (see app/ml/categorical_maps.py) — the SAME
    # mapping training used, not a per-process hash().
    features['appointment_type_code'] = encode_appointment_type(appointment_type)
    features['booking_source_code'] = encode_booking_source(booking_source)
    features['specialization_id'] = specialization_id or 0

    doctor_hist = doctor_historical or (get_doctor_historical_stats(session, doctor_id) if doctor_id else {})
    features['doctor_avg_duration'] = doctor_hist.get('avg_duration', doctor_hist.get('doctor_avg_duration', 0.0))
    features['doctor_no_show_rate'] = doctor_hist.get('no_show_rate', doctor_hist.get('doctor_no_show_rate', 0.0))
    features['doctor_total_appointments'] = doctor_hist.get('total_appointments', doctor_hist.get('doctor_total_appointments', 0))

    patient_hist = patient_historical or (get_patient_historical_stats(session, patient_id) if patient_id else {})
    features['patient_avg_duration'] = patient_hist.get('avg_duration', patient_hist.get('patient_avg_duration', 0.0))
    features['patient_no_show_rate'] = patient_hist.get('no_show_rate', patient_hist.get('patient_no_show_rate', 0.0))
    features['patient_total_appointments'] = patient_hist.get('total_appointments', patient_hist.get('patient_total_appointments', 0))

    return features


def estimate_waiting_time_minutes(
    session: Session, doctor_id: int, appointment_datetime: datetime, doctor_avg_duration: float
) -> float:
    """
    Deterministic waiting-time ESTIMATE (not a trained prediction): the
    number of the doctor's active appointments already scheduled earlier the
    same day, multiplied by their historical average duration (or a 20-minute
    default if there's no history yet). This is a queue-length heuristic,
    clearly separate from the ML models above, because we have no real
    check-in/seen-at data to train an honest waiting-time model against.
    """
    day_start = appointment_datetime.replace(hour=0, minute=0, second=0, microsecond=0)
    earlier_count = (
        session.query(func.count(Appointment.id))
        .filter(
            Appointment.doctor_id == doctor_id,
            Appointment.status.in_(ACTIVE_APPOINTMENT_STATUSES),
            Appointment.start_datetime >= day_start,
            Appointment.start_datetime < appointment_datetime,
        )
        .scalar()
        or 0
    )
    avg_duration = doctor_avg_duration if doctor_avg_duration and doctor_avg_duration > 0 else 20.0
    # Assume some overlap/parallel capacity is absorbed; use a damping factor
    # so the estimate doesn't grow unrealistically for a doctor with many
    # appointments earlier in the day.
    return round(min(earlier_count * avg_duration * 0.3, 90.0), 1)


def predict_appointment(
    session: Session,
    doctor_id: int,
    patient_id: Optional[int],
    appointment_datetime: datetime,
    appointment_type: str,
    booking_source: str,
    specialization_id: int,
    model_dir: Optional[str] = None,
    doctor_historical: Optional[Dict[str, Any]] = None,
    patient_historical: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Returns a dict with 'duration_minutes' and 'no_show_probability' from the
    trained models (or fallback heuristics), PLUS 'waiting_time_minutes'
    which is always the deterministic estimate above — never a model output.
    Also returns 'model_version' and 'used_fallback' for prediction logging.
    """
    features = _compute_features_for_appointment(
        session, doctor_id, patient_id, appointment_datetime, appointment_type, booking_source,
        specialization_id, doctor_historical, patient_historical,
    )

    duration_model, noshow_model, feature_names = _get_models_and_features(model_dir)
    used_fallback = duration_model is None or noshow_model is None or feature_names is None

    if used_fallback:
        logger.warning("ML models not available — using fallback heuristic predictions.")
        duration = FALLBACK_DURATION
        no_show_prob = FALLBACK_NOSHOW_PROB
    else:
        try:
            X = _features_to_array(features, feature_names)
            duration = max(0.0, float(duration_model.predict(X)[0]))
            proba = noshow_model.predict_proba(X)[0]
            no_show_prob = float(proba[1]) if len(proba) == 2 else float(proba[0])
            no_show_prob = max(0.0, min(1.0, no_show_prob))
        except Exception as e:
            logger.error(f"Error during ML prediction, falling back to heuristics: {e}")
            duration = FALLBACK_DURATION
            no_show_prob = FALLBACK_NOSHOW_PROB
            used_fallback = True

    waiting_time = estimate_waiting_time_minutes(
        session, doctor_id, appointment_datetime, features.get('doctor_avg_duration', 0.0)
    )

    return {
        'duration_minutes': duration,
        'no_show_probability': no_show_prob,
        'waiting_time_minutes': waiting_time,
        'model_version': MODEL_VERSION if not used_fallback else 'fallback-heuristic',
        'used_fallback': used_fallback,
        'features': features,
    }


# Warm the cache at import time (best-effort; falls back cleanly if artifacts are missing).
_load_models()
