"""Calibration config loading for the forecast model."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Union


@dataclass(frozen=True)
class CalibrationBundle:
    """Loaded manual calibration constants for the fast forecast engine."""

    version: str
    model_name: str
    polling_weights: Dict[str, float]
    race_models: Dict[str, Dict[str, float]]


def default_calibration_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "calibration"


def _load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Calibration file must contain an object: {path}")
    return data


def load_calibration_bundle(
    calibration_dir: Optional[Union[str, Path]] = None,
) -> CalibrationBundle:
    """Load the manual calibration bundle from JSON files."""

    directory = Path(calibration_dir) if calibration_dir else default_calibration_dir()
    base = _load_json(directory / "base.json")
    polling = _load_json(directory / "polling.json")
    race_models = _load_json(directory / "race_models.json")

    version = base.get("calibration_version")
    if not isinstance(version, str) or not version.startswith("manual-"):
        raise ValueError("Calibration version must use the manual-* format.")

    model_name = base.get("model_name", "arbiter_forecast_v2")
    if not isinstance(model_name, str) or not model_name:
        raise ValueError("Calibration model_name must be a non-empty string.")

    return CalibrationBundle(
        version=version,
        model_name=model_name,
        polling_weights={str(key): float(value) for key, value in polling.items()},
        race_models={
            str(race_type): {str(key): float(value) for key, value in params.items()}
            for race_type, params in race_models.items()
            if isinstance(params, dict)
        },
    )
