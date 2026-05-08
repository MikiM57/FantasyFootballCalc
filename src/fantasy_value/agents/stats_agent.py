from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from fantasy_value.models import PlayerStats
from fantasy_value.repository import load_players


class StatsProvider(Protocol):
    def fetch_players(self) -> list[PlayerStats]:
        """Return normalized player stats."""


@dataclass(frozen=True)
class JsonStatsProvider:
    path: str | Path

    def fetch_players(self) -> list[PlayerStats]:
        return load_players(self.path)


@dataclass(frozen=True)
class CsvStatsProvider:
    path: str | Path

    def fetch_players(self) -> list[PlayerStats]:
        with Path(self.path).open("r", encoding="utf-8", newline="") as handle:
            rows = csv.DictReader(handle)
            return [PlayerStats(**self._coerce(row)) for row in rows]

    @staticmethod
    def _coerce(row: dict[str, str]) -> dict[str, object]:
        numeric_fields = {
            "age",
            "projected_points",
            "fantasy_points_per_game",
            "snap_share",
            "route_participation",
            "target_share",
            "targets_per_game",
            "carries_per_game",
            "red_zone_touches_per_game",
            "yards_per_route_run",
            "yards_after_contact_per_attempt",
            "explosive_play_rate",
            "team_implied_points",
            "offensive_environment",
            "injury_risk",
            "role_uncertainty",
            "market_value",
            "average_draft_position",
        }
        int_fields = {"games_played"}
        output: dict[str, object] = {}
        for key, value in row.items():
            if key in numeric_fields:
                output[key] = float(value) if value else 0.0
            elif key in int_fields:
                output[key] = int(value) if value else 0
            else:
                output[key] = value
        if output.get("average_draft_position") == 0.0:
            output["average_draft_position"] = None
        return output


@dataclass
class StatsIngestionAgent:
    provider: StatsProvider

    def run(self) -> list[PlayerStats]:
        return self.provider.fetch_players()


class EspnStatsProvider:
    """Placeholder for an approved ESPN integration.

    ESPN pages and APIs may have terms that restrict automated scraping. A
    production implementation should use an approved endpoint, licensed data,
    or a user-provided export before enabling this provider.
    """

    def fetch_players(self) -> list[PlayerStats]:
        raise NotImplementedError(
            "Configure an approved ESPN data source or replace this provider with a licensed feed."
        )
