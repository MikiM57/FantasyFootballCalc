from __future__ import annotations

import json
from dataclasses import asdict, dataclass
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
class Calibration:
    seasons: list[int]
    positions: dict[Position, PositionCalibration]


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
    return Calibration(seasons=raw.get("seasons", []), positions=merged)  # type: ignore[arg-type]


def save_calibration(path: str | Path, calibration: Calibration) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "seasons": calibration.seasons,
        "positions": {
            position: asdict(values) for position, values in calibration.positions.items()
        },
    }
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
