"""
Writes to the prediction_logs table (Phase 13). Every ML/LLM prediction the
system makes when generating recommendations is logged here: type, model
version, a safe subset of the input, the prediction itself, and a timestamp.

Logging failures must never break booking or recommendations — callers should
wrap calls to `log_prediction` the same way this module does internally, but
as a second line of defense every exception here is caught and swallowed
(after being logged to the standard logger).
"""
import logging
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models.prediction_log import PredictionLog

logger = logging.getLogger(__name__)

# Keys we never want to persist even if a caller accidentally includes them
# in input_features (defense in depth against logging secrets).
_SENSITIVE_KEYS = {"api_key", "password", "password_hash", "token", "authorization"}

def _sanitize(d: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not d:
        return {}
    return {k: v for k, v in d.items() if k.lower() not in _SENSITIVE_KEYS}


def log_prediction(
    db: Session,
    prediction_type: str,
    input_features: Dict[str, Any],
    prediction: Dict[str, Any],
    model_version: str,
) -> None:
    try:
        entry = PredictionLog(
            prediction_type=prediction_type,
            input_features=_sanitize(input_features),
            prediction=_sanitize(prediction),
            model_version=model_version,
        )
        db.add(entry)
        db.commit()
    except Exception:
        logger.exception("Failed to write prediction log (type=%s) — continuing without it.", prediction_type)
        db.rollback()
