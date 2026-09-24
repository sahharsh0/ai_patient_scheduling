"""
Single source of truth for categorical -> numeric encoding used by both
training (generate_dataset.py / train_models.py) and inference (ml/service.py,
recommendation_service.py).

Replaces the old `hash(value) % 1000` approach, which was wrong for two
reasons: (1) training used a *different*, dynamically-generated mapping than
inference, and (2) Python's hash() is randomized per-process (PYTHONHASHSEED),
so it isn't even stable across two runs of the same code.

The vocabulary here matches app.models.enums exactly. Unknown values (e.g. a
legacy value no longer in the enum) fall back to -1 rather than crashing.
"""
import json
import os
from typing import Dict

APPOINTMENT_TYPE_MAP: Dict[str, int] = {
    "consultation": 0,
    "follow_up": 1,
    "check_up": 2,
    "procedure": 3,
}

BOOKING_SOURCE_MAP: Dict[str, int] = {
    "normal": 0,
    "ai": 1,
}

UNKNOWN_CATEGORY_CODE = -1


def encode_appointment_type(value: str) -> int:
    return APPOINTMENT_TYPE_MAP.get(value, UNKNOWN_CATEGORY_CODE)


def encode_booking_source(value: str) -> int:
    return BOOKING_SOURCE_MAP.get(value, UNKNOWN_CATEGORY_CODE)


def write_categorical_maps_json(model_dir: str) -> str:
    """Persist the mapping alongside the trained model artifacts so a future
    reader can see exactly what encoding a given model version was trained
    with, even if this module later changes."""
    os.makedirs(model_dir, exist_ok=True)
    path = os.path.join(model_dir, "categorical_maps.json")
    with open(path, "w") as f:
        json.dump({"appointment_type": APPOINTMENT_TYPE_MAP, "booking_source": BOOKING_SOURCE_MAP}, f, indent=2)
    return path
