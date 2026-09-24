"""appointment duration_minutes, check-in fields, and integrity constraints

Adds the fields the ML/recommendation code actually needs on Appointment:
  - duration_minutes: the real (ground-truth) duration, used as the training
    target for the duration model. No-show is NOT a new boolean column here —
    it is represented by the existing AppointmentStatus.no_show status value.
  - checked_in_at / seen_at: optional timestamps that let us compute a
    deterministic waiting-time *estimate* later (queue length based), without
    pretending there is a trained waiting-time model.

Also adds database-level integrity constraints (Phase 19):
  - end_datetime > start_datetime
  - duration_minutes > 0 (or NULL)
  - day_of_week between 0 and 6 on doctor_availability

Revision ID: 9a1f3c7e2b44
Revises: 2761fb48110b
Create Date: 2026-09-16 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '9a1f3c7e2b44'
down_revision: Union[str, None] = '2761fb48110b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('appointments', sa.Column('duration_minutes', sa.Integer(), nullable=True))
    op.add_column('appointments', sa.Column('checked_in_at', sa.DateTime(), nullable=True))
    op.add_column('appointments', sa.Column('seen_at', sa.DateTime(), nullable=True))

    # Backfill duration_minutes for any existing rows from start/end so historical
    # data has a meaningful, non-NULL value (MySQL: TIMESTAMPDIFF in minutes).
    op.execute(
        "UPDATE appointments SET duration_minutes = TIMESTAMPDIFF(MINUTE, start_datetime, end_datetime) "
        "WHERE duration_minutes IS NULL"
    )

    op.create_check_constraint(
        'ck_appointment_end_after_start', 'appointments', 'end_datetime > start_datetime'
    )
    op.create_check_constraint(
        'ck_appointment_duration_positive',
        'appointments',
        'duration_minutes IS NULL OR duration_minutes > 0',
    )
    op.create_check_constraint(
        'ck_doctor_availability_day_of_week',
        'doctor_availability',
        'day_of_week >= 0 AND day_of_week <= 6',
    )
    op.create_check_constraint(
        'ck_doctor_availability_end_after_start', 'doctor_availability', 'end_time > start_time'
    )
    op.create_check_constraint(
        'ck_doctor_leave_end_after_start', 'doctor_leaves', 'end_datetime > start_datetime'
    )


def downgrade() -> None:
    op.drop_constraint('ck_doctor_leave_end_after_start', 'doctor_leaves', type_='check')
    op.drop_constraint('ck_doctor_availability_end_after_start', 'doctor_availability', type_='check')
    op.drop_constraint('ck_doctor_availability_day_of_week', 'doctor_availability', type_='check')
    op.drop_constraint('ck_appointment_duration_positive', 'appointments', type_='check')
    op.drop_constraint('ck_appointment_end_after_start', 'appointments', type_='check')
    op.drop_column('appointments', 'seen_at')
    op.drop_column('appointments', 'checked_in_at')
    op.drop_column('appointments', 'duration_minutes')
