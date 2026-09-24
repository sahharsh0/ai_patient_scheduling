"""
Generate a dataset for ML model training from the SmartCare AI database.

This script queries the database for historical appointments and related entities,
engineers features, and outputs a CSV file suitable for training duration,
no-show, and waiting-time prediction models.

Usage:
    python generate_dataset.py --output dataset.csv
"""

import argparse
import os
import sys
from datetime import datetime
from typing import Tuple

import pandas as pd
from sqlalchemy import and_, func, select

# Add the parent directory to sys.path so we can import app modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app.core.database import SessionLocal
from app.models import Appointment, Doctor, Patient, User, DoctorAvailability, DoctorLeave
from app.models.enums import AppointmentStatus, BookingSource
from app.ml.categorical_maps import encode_appointment_type, encode_booking_source


def get_db_session():
    """Get a new database session."""
    return SessionLocal()


def load_appointments(session) -> pd.DataFrame:
    """
    Load appointments with relevant joined data.
    Returns a DataFrame with one row per appointment.
    """
    # Query appointments with joins to get necessary related data
    query = session.query(
        Appointment.id.label('appointment_id'),
        Appointment.patient_id,
        Appointment.doctor_id,
        Appointment.specialization_id,
        Appointment.start_datetime,
        Appointment.end_datetime,
        Appointment.appointment_type,
        Appointment.status,
        Appointment.booking_source,
        Appointment.duration_minutes,
        Appointment.predicted_duration,
        Appointment.predicted_no_show_probability,
        Appointment.predicted_waiting_time,
        # Patient details
        Patient.date_of_birth.label('patient_dob'),
        # Doctor details
        Doctor.experience_years,
        Doctor.consultation_fee,
        Doctor.rating,
        Doctor.specialization_id.label('doctor_specialization_id'),  # redundant but explicit
        # User details for patient and doctor (names, etc. if needed)
    ).join(
        Patient, Appointment.patient_id == Patient.id
    ).join(
        Doctor, Appointment.doctor_id == Doctor.id
    ).filter(
        # We'll use all appointments for now; could filter by status if needed
        Appointment.status.in_([
            AppointmentStatus.scheduled,
            AppointmentStatus.completed,
            AppointmentStatus.cancelled,
            AppointmentStatus.no_show,
            AppointmentStatus.rescheduled
        ])
    )

    # Execute query and load into DataFrame
    df = pd.read_sql(query.statement, session.bind)
    return df


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Engineer features from the raw data.
    Returns a DataFrame with features and targets.
    """
    # Make a copy to avoid warnings
    df = df.copy()

    # Convert datetime columns
    df['start_datetime'] = pd.to_datetime(df['start_datetime'])
    df['end_datetime'] = pd.to_datetime(df['end_datetime'])

    # Target variables
    # Duration in minutes: the REAL ground-truth duration_minutes column
    # (falls back to the start/end span only for legacy rows that predate it).
    if 'duration_minutes' in df.columns:
        df['duration_minutes'] = df['duration_minutes'].fillna(
            (df['end_datetime'] - df['start_datetime']).dt.total_seconds() / 60.0
        )
    else:
        df['duration_minutes'] = (df['end_datetime'] - df['start_datetime']).dt.total_seconds() / 60.0
    # No-show binary (1 if the appointment's actual status is no_show, else 0).
    df['no_show'] = (df['status'] == 'no_show').astype(int)
    # NOTE: there is intentionally no 'waiting_time_minutes' target here.
    # Training against `predicted_waiting_time` would be circular (that
    # column is itself a prior model/heuristic output, not ground truth), and
    # we don't have real check-in/seen timestamps in the seed data to derive
    # an honest one. Waiting time is estimated deterministically at inference
    # time instead — see app/ml/service.py:estimate_waiting_time_minutes.

    # Features from datetime
    df['start_hour'] = df['start_datetime'].dt.hour
    df['start_day_of_week'] = df['start_datetime'].dt.weekday  # Monday=0, Sunday=6
    df['start_month'] = df['start_datetime'].dt.month
    df['is_weekend'] = df['start_day_of_week'].isin([5, 6]).astype(int)

    # Patient age at appointment
    df['patient_age'] = (df['start_datetime'] - pd.to_datetime(df['patient_dob'])).dt.days / 365.25

    # Doctor features (already have)
    # We'll also compute historical stats for doctor and patient

    # For each doctor, compute historical average duration, no-show rate, etc.
    # We'll do this by grouping on doctor_id using appointments that are in the past
    # relative to each appointment? This is tricky because we might leak future data.
    # For simplicity, we'll compute global averages per doctor and patient using all data,
    # but note that this could lead to data leakage in a time-series scenario.
    # Since this is a synthetic dataset and we're not doing temporal validation, we'll proceed.

    # Historical features for doctor
    doctor_stats = df.groupby('doctor_id').agg(
        doctor_avg_duration=('duration_minutes', 'mean'),
        doctor_no_show_rate=('no_show', 'mean'),
        doctor_total_appointments=('appointment_id', 'count')
    ).reset_index()

    # Historical features for patient
    patient_stats = df.groupby('patient_id').agg(
        patient_avg_duration=('duration_minutes', 'mean'),
        patient_no_show_rate=('no_show', 'mean'),
        patient_total_appointments=('appointment_id', 'count')
    ).reset_index()

    # Merge stats back to the main DataFrame
    df = df.merge(doctor_stats, on='doctor_id', how='left')
    df = df.merge(patient_stats, on='patient_id', how='left')

    # Appointment type / booking source: encode with the FIXED vocabulary in
    # app.ml.categorical_maps, not a mapping derived from whatever values
    # happen to appear in this particular dataset. A per-run unique()-based
    # mapping (the previous approach) assigns different codes to the same
    # category across different training runs, and doesn't match whatever
    # code inference uses for a category that's rare/absent in this sample.
    df['appointment_type_code'] = df['appointment_type'].map(
        lambda v: encode_appointment_type(v.value if hasattr(v, 'value') else v)
    )
    df['booking_source_code'] = df['booking_source'].map(
        lambda v: encode_booking_source(v.value if hasattr(v, 'value') else v)
    )

    # Features for availability and leave: we could compute the number of available slots,
    # but for simplicity, we'll skip for now and maybe add later.

    # Select features for modeling
    feature_columns = [
        # Doctor features
        'experience_years', 'consultation_fee', 'rating',
        'doctor_avg_duration', 'doctor_no_show_rate', 'doctor_total_appointments',
        # Patient features
        'patient_age', 'patient_avg_duration', 'patient_no_show_rate', 'patient_total_appointments',
        # Appointment features
        'start_hour', 'start_day_of_week', 'start_month', 'is_weekend',
        'appointment_type_code', 'booking_source_code',
        # Specialization ID (as categorical, we'll one-hot or leave as integer for now)
        'specialization_id',
    ]

    # Ensure all features exist and fill NaNs with 0 (or appropriate values)
    for col in feature_columns:
        if col not in df.columns:
            df[col] = 0
        df[col] = df[col].fillna(0)

    # Targets: duration (regression) and no-show (classification) only.
    # There is deliberately no waiting-time target — see the note above.
    target_columns = ['duration_minutes', 'no_show']

    # Return features and targets
    features = df[feature_columns]
    targets = df[target_columns]

    return features, targets, feature_columns, target_columns


def main():
    parser = argparse.ArgumentParser(description='Generate dataset for ML training.')
    parser.add_argument('--output', type=str, default='dataset.csv',
                        help='Output CSV file path')
    parser.add_argument('--max-rows', type=int, default=None,
                        help='Maximum number of rows to load (for testing)')
    args = parser.parse_args()

    print("Loading database session...")
    session = get_db_session()
    try:
        print("Loading appointments from database...")
        df = load_appointments(session)
        if args.max_rows:
            df = df.head(args.max_rows)
        print(f"Loaded {len(df)} appointments.")

        print("Engineering features...")
        features, targets, feature_names, target_names = engineer_features(df)

        # Combine features and targets for saving
        dataset = pd.concat([features, targets], axis=1)

        # Save to CSV
        dataset.to_csv(args.output, index=False)
        print(f"Dataset saved to {args.output}")
        print(f"Features: {list(feature_names)}")
        print(f"Targets: {list(target_names)}")
        print(f"Shape: {dataset.shape}")

    finally:
        session.close()


if __name__ == '__main__':
    main()