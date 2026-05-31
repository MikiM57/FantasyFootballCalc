from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from fantasy_value.models import Position


@dataclass(frozen=True)
class PositionCalibration:
    baseline_ppg: float
    starter_ppg: float
    elite_ppg: float
    replacement_ppg: float
    one_qb_multiplier: float
    superflex_multiplier: float


@dataclass(frozen=True)
class ModelTrainingProfile:
    trained_seasons: list[int]
    market_anchor: float
    component_weights: dict[str, float] = field(default_factory=dict)


DEFAULT_MODEL_TRAINING = ModelTrainingProfile(
    trained_seasons=[],
    market_anchor=0.0,
    component_weights={},
)


@dataclass(frozen=True)
class Calibration:
    seasons: list[int]
    positions: dict[Position, PositionCalibration]
    model: ModelTrainingProfile = field(default_factory=lambda: DEFAULT_MODEL_TRAINING)


DEFAULT_CALIBRATION = Calibration(
    seasons=[],
    positions={
        "QB": PositionCalibration(
            baseline_ppg=14.0,
            starter_ppg=18.0,
            elite_ppg=24.0,
            replacement_ppg=15.5,
            one_qb_multiplier=0.76,
            superflex_multiplier=1.22,
        ),
        "RB": PositionCalibration(
            baseline_ppg=7.5,
            starter_ppg=11.5,
            elite_ppg=20.0,
            replacement_ppg=8.5,
            one_qb_multiplier=1.0,
            superflex_multiplier=1.0,
        ),
        "WR": PositionCalibration(
            baseline_ppg=8.0,
            starter_ppg=12.0,
            elite_ppg=21.0,
            replacement_ppg=8.8,
            one_qb_multiplier=1.05,
            superflex_multiplier=1.0,
        ),
        "TE": PositionCalibration(
            baseline_ppg=5.5,
            starter_ppg=8.0,
            elite_ppg=16.0,
            replacement_ppg=5.8,
            one_qb_multiplier=1.0,
            superflex_multiplier=1.0,
        ),
    },
    model=DEFAULT_MODEL_TRAINING,
)


def load_calibration(path: str | Path | None) -> Calibration:
    if not path:
        return DEFAULT_CALIBRATION
    calibration_path = Path(path)
    if not calibration_path.exists():
        return DEFAULT_CALIBRATION
    with calibration_path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    positions = {
        position: PositionCalibration(**values)
        for position, values in raw.get("positions", {}).items()
        if position in DEFAULT_CALIBRATION.positions
    }
    merged = {**DEFAULT_CALIBRATION.positions, **positions}
    model = _load_model_profile(raw.get("model", {}))
    return Calibration(  # type: ignore[arg-type]
        seasons=raw.get("seasons", []),
        positions=merged,
        model=model,
    )


def save_calibration(path: str | Path, calibration: Calibration) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "seasons": calibration.seasons,
        "positions": {
            position: asdict(values) for position, values in calibration.positions.items()
        },
        "model": asdict(calibration.model),
    }
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


def _load_model_profile(raw: object) -> ModelTrainingProfile:
    if not isinstance(raw, dict):
        return DEFAULT_MODEL_TRAINING
    weights = raw.get("component_weights", {})
    if not isinstance(weights, dict):
        weights = {}
    return ModelTrainingProfile(
        trained_seasons=list(raw.get("trained_seasons", [])),
        market_anchor=float(raw.get("market_anchor", DEFAULT_MODEL_TRAINING.market_anchor)),
        component_weights={str(key): float(value) for key, value in weights.items()},
    )
