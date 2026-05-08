from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Literal

Position = Literal["QB", "RB", "WR", "TE", "K", "DST"]
ScoringFormat = Literal["standard", "half_ppr", "ppr"]
CompetitiveWindow = Literal["contender", "balanced", "rebuilder"]


@dataclass(frozen=True)
class PlayerStats:
    player_id: str
    name: str
    position: Position
    team: str
    age: float
    projected_points: float
    fantasy_points_per_game: float
    games_played: int
    snap_share: float
    route_participation: float
    target_share: float
    targets_per_game: float
    carries_per_game: float
    red_zone_touches_per_game: float
    yards_per_route_run: float
    yards_after_contact_per_attempt: float
    explosive_play_rate: float
    team_implied_points: float
    offensive_environment: float
    injury_risk: float
    role_uncertainty: float
    market_value: float
    average_draft_position: float | None = None

    @property
    def high_value_touch_rate(self) -> float:
        return self.targets_per_game + self.red_zone_touches_per_game


@dataclass(frozen=True)
class ExpertMention:
    player_id: str
    player_name: str
    source: str
    url: str | None
    published_on: date | None
    sentiment: float
    magnitude: float
    confidence: float
    context: str
    reason: str


@dataclass(frozen=True)
class LeagueSettings:
    scoring: ScoringFormat = "half_ppr"
    teams: int = 12
    dynasty: bool = True
    superflex: bool = False
    tight_end_premium: float = 0.0
    starters: dict[Position, int] = field(
        default_factory=lambda: {"QB": 1, "RB": 2, "WR": 2, "TE": 1, "K": 0, "DST": 0}
    )
    flex_spots: int = 2
    bench_spots: int = 8


@dataclass(frozen=True)
class RosterContext:
    competitive_window: CompetitiveWindow = "balanced"
    positional_needs: dict[Position, float] = field(default_factory=dict)
    roster_player_ids: tuple[str, ...] = ()

    def need_for(self, position: Position) -> float:
        return max(-1.0, min(1.0, self.positional_needs.get(position, 0.0)))
