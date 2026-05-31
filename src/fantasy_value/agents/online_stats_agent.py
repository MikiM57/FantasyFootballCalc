from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path
from statistics import mean
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fantasy_value.calibration import (
    Calibration,
    ModelTrainingProfile,
    PositionCalibration,
    save_calibration,
)
from fantasy_value.models import PlayerStats, Position
from fantasy_value.repository import save_players

SLEEPER_PLAYERS_URL = "https://api.sleeper.app/v1/players/nfl"
NFLVERSE_STATS_TEMPLATE = (
    "https://github.com/nflverse/nflverse-data/releases/download/"
    "player_stats/stats_player_week_{season}.csv"
)
NFLVERSE_SCHEDULES_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/schedules/schedules.csv"
)
FANTASY_POSITIONS = {"QB", "RB", "WR", "TE"}


@dataclass(frozen=True)
class OnlineStatsConfig:
    season: int | None = None
    fallback_seasons: int = 2
    limit: int = 250
    sleeper_players_url: str = SLEEPER_PLAYERS_URL
    nflverse_stats_template: str = NFLVERSE_STATS_TEMPLATE
    nflverse_schedules_url: str = NFLVERSE_SCHEDULES_URL
    include_schedule: bool = True
    calibration_seasons: int = 5


@dataclass(frozen=True)
class OnlineStatsRunSummary:
    status: str
    season_used: int | None
    players_written: int
    calibration_seasons: list[int]
    calibration_output_path: str | None
    output_path: str | None
    message: str


@dataclass(frozen=True)
class OnlineNflStatsAgent:
    output_path: Path
    config: OnlineStatsConfig
    calibration_output_path: Path | None = None

    def run(self) -> OnlineStatsRunSummary:
        try:
            sleeper_players = fetch_sleeper_players(self.config.sleeper_players_url)
            season, rows = fetch_latest_weekly_stats(self.config)
            schedules = fetch_schedules(self.config.nflverse_schedules_url) if self.config.include_schedule else []
            players = build_player_stats(
                weekly_rows=rows,
                sleeper_players=sleeper_players,
                schedules=schedules,
                season=season,
                limit=self.config.limit,
            )
            save_players(self.output_path, players)
            calibration = build_historical_calibration(
                self.config,
                current_season=season,
                current_rows=rows,
            )
            if self.calibration_output_path:
                save_calibration(self.calibration_output_path, calibration)
            return OnlineStatsRunSummary(
                status="complete",
                season_used=season,
                players_written=len(players),
                calibration_seasons=calibration.seasons,
                calibration_output_path=(
                    str(self.calibration_output_path) if self.calibration_output_path else None
                ),
                output_path=str(self.output_path),
                message="Online NFL player data refreshed.",
            )
        except Exception as exc:  # noqa: BLE001
            return OnlineStatsRunSummary(
                status="failed",
                season_used=None,
                players_written=0,
                calibration_seasons=[],
                calibration_output_path=None,
                output_path=None,
                message=f"Online stats refresh failed: {exc}",
            )


def config_from_env(env: dict[str, str]) -> OnlineStatsConfig:
    raw_season = env.get("NFLVERSE_SEASON", "").strip()
    raw_limit = env.get("ONLINE_PLAYER_LIMIT", "").strip()
    raw_fallback = env.get("NFLVERSE_FALLBACK_SEASONS", "").strip()
    raw_calibration_seasons = env.get("HISTORICAL_CALIBRATION_SEASONS", "").strip()
    return OnlineStatsConfig(
        season=int(raw_season) if raw_season else None,
        fallback_seasons=int(raw_fallback) if raw_fallback else 2,
        limit=int(raw_limit) if raw_limit else 250,
        sleeper_players_url=env.get("SLEEPER_PLAYERS_URL", SLEEPER_PLAYERS_URL),
        nflverse_stats_template=env.get("NFLVERSE_STATS_TEMPLATE", NFLVERSE_STATS_TEMPLATE),
        nflverse_schedules_url=env.get("NFLVERSE_SCHEDULES_URL", NFLVERSE_SCHEDULES_URL),
        include_schedule=env.get("ENABLE_SCHEDULE_STRENGTH", "true").lower() == "true",
        calibration_seasons=int(raw_calibration_seasons) if raw_calibration_seasons else 5,
    )


def fetch_sleeper_players(url: str) -> dict[str, dict[str, object]]:
    request = Request(url, headers={"User-Agent": "FantasyFootballCalc/0.1"})
    with urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Sleeper players response was not a JSON object.")
    return payload


def fetch_latest_weekly_stats(config: OnlineStatsConfig) -> tuple[int, list[dict[str, str]]]:
    start_year = config.season or date.today().year
    seasons = [start_year - offset for offset in range(config.fallback_seasons + 1)]
    last_error: Exception | None = None
    for season in seasons:
        url = config.nflverse_stats_template.format(season=season)
        try:
            return season, fetch_csv(url)
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            last_error = exc
    raise RuntimeError(f"No nflverse player stats CSV could be loaded: {last_error}")


def fetch_historical_weekly_stats(
    config: OnlineStatsConfig,
    current_season: int,
) -> dict[int, list[dict[str, str]]]:
    output: dict[int, list[dict[str, str]]] = {}
    for season in range(current_season - 1, current_season - config.calibration_seasons - 1, -1):
        url = config.nflverse_stats_template.format(season=season)
        try:
            output[season] = fetch_csv(url)
        except (HTTPError, URLError, TimeoutError, ValueError):
            continue
    return output


def build_historical_calibration(
    config: OnlineStatsConfig,
    current_season: int,
    current_rows: list[dict[str, str]] | None = None,
) -> Calibration:
    seasons = fetch_historical_weekly_stats(config, current_season)
    if current_rows:
        seasons[current_season] = current_rows
    return calibration_from_weekly_stats(seasons, training_season=current_season)


def calibration_from_weekly_stats(
    seasons: dict[int, list[dict[str, str]]],
    training_season: int | None = None,
) -> Calibration:
    ppg_by_position: dict[Position, list[float]] = {"QB": [], "RB": [], "WR": [], "TE": []}
    for rows in (_regular_season_rows(rows) for rows in seasons.values()):
        grouped: dict[str, list[dict[str, str]]] = {}
        for row in rows:
            position = _position(row)
            if position not in FANTASY_POSITIONS:
                continue
            player_id = row.get("player_id") or row.get("player_gsis_id") or _slug(row.get("player_name", ""))
            grouped.setdefault(player_id, []).append(row)
        for player_rows in grouped.values():
            games = [_fantasy_points(row) for row in player_rows]
            active_games = [points for points in games if points > 0]
            if len(active_games) < 4:
                continue
            position = _position(player_rows[-1])
            ppg_by_position[position].append(mean(active_games))

    positions = {
        position: _position_calibration_from_ppg(position, values)
        for position, values in ppg_by_position.items()
    }
    seasons_used = sorted(season for season, rows in seasons.items() if rows)
    training_rows = seasons.get(training_season or 0)
    if training_rows is None and seasons_used:
        training_rows = seasons[seasons_used[-1]]
        training_season = seasons_used[-1]
    model = model_training_from_weekly_stats(training_rows or [], training_season)
    return Calibration(seasons=seasons_used, positions=positions, model=model)


def model_training_from_weekly_stats(
    rows: list[dict[str, str]],
    season: int | None,
) -> ModelTrainingProfile:
    rows = _regular_season_rows(rows)
    if not rows or season is None:
        return ModelTrainingProfile(trained_seasons=[], market_anchor=0.0)
    player_count = _qualified_player_count(rows)
    market_anchor = 0.30 if player_count >= 80 else 0.24
    return ModelTrainingProfile(
        trained_seasons=[season],
        market_anchor=market_anchor,
        component_weights={
            "production": 0.31,
            "opportunity": 0.20,
            "efficiency": 0.08,
            "environment": 0.06,
            "sentiment": 0.06,
            "market": 0.20,
            "schedule": 0.03,
            "age": 0.08,
            "risk": 0.12,
        },
    )


def _qualified_player_count(rows: list[dict[str, str]]) -> int:
    grouped: dict[str, list[float]] = {}
    for row in rows:
        position = _position(row)
        if position not in FANTASY_POSITIONS:
            continue
        player_id = row.get("player_id") or row.get("player_gsis_id") or _slug(row.get("player_name", ""))
        grouped.setdefault(player_id, []).append(_fantasy_points(row))
    return sum(1 for points in grouped.values() if len([point for point in points if point > 0]) >= 4)


def _position_calibration_from_ppg(
    position: Position,
    values: list[float],
) -> PositionCalibration:
    if not values:
        fallback = {
            "QB": (14.0, 18.0, 24.0, 15.5),
            "RB": (7.5, 11.5, 20.0, 8.5),
            "WR": (8.0, 12.0, 21.0, 8.8),
            "TE": (5.5, 8.0, 16.0, 5.8),
        }[position]
        baseline, starter, elite, replacement = fallback
    else:
        ordered = sorted(values, reverse=True)
        baseline = _percentile(ordered, 0.72)
        starter = _rank_value(ordered, {"QB": 12, "RB": 24, "WR": 30, "TE": 12}[position])
        elite = _rank_value(ordered, {"QB": 3, "RB": 6, "WR": 8, "TE": 3}[position])
        replacement = _rank_value(ordered, {"QB": 18, "RB": 36, "WR": 42, "TE": 18}[position])
    one_qb_multiplier = _one_qb_multiplier(position, elite, replacement)
    superflex_multiplier = 1.0
    if position == "QB":
        superflex_multiplier = 1.16 + min(0.12, max(0.0, (elite - replacement) / 100))
    return PositionCalibration(
        baseline_ppg=round(baseline, 2),
        starter_ppg=round(starter, 2),
        elite_ppg=round(max(elite, starter + 1.0), 2),
        replacement_ppg=round(replacement, 2),
        one_qb_multiplier=round(one_qb_multiplier, 3),
        superflex_multiplier=round(superflex_multiplier, 3),
    )


def _rank_value(values: list[float], rank: int) -> float:
    if not values:
        return 0.0
    index = max(0, min(len(values) - 1, rank - 1))
    return values[index]


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    index = int(max(0, min(len(values) - 1, round((len(values) - 1) * percentile))))
    return values[index]


def _one_qb_multiplier(position: Position, elite: float, replacement: float) -> float:
    if position != "QB":
        return 1.05 if position == "WR" else 1.0
    spread = max(1.0, elite - replacement)
    return _clip(0.64 + spread / 50, 0.64, 0.78)


def fetch_schedules(url: str) -> list[dict[str, str]]:
    try:
        return fetch_csv(url)
    except Exception:
        return []


def fetch_csv(url: str) -> list[dict[str, str]]:
    request = Request(url, headers={"User-Agent": "FantasyFootballCalc/0.1"})
    with urlopen(request, timeout=45) as response:
        text = response.read().decode("utf-8", errors="replace")
    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows:
        raise ValueError(f"No rows returned from {url}")
    return rows


def _regular_season_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    output = []
    for row in rows:
        season_type = str(row.get("season_type") or row.get("game_type") or "REG").upper()
        if season_type in {"REG", "REGULAR"}:
            output.append(row)
    return output


def build_player_stats(
    weekly_rows: list[dict[str, str]],
    sleeper_players: dict[str, dict[str, object]],
    schedules: list[dict[str, str]],
    season: int,
    limit: int,
) -> list[PlayerStats]:
    weekly_rows = _regular_season_rows(weekly_rows)
    sleeper_by_name = _sleeper_by_name(sleeper_players)
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in weekly_rows:
        position = _position(row)
        if position not in FANTASY_POSITIONS:
            continue
        player_id = row.get("player_id") or row.get("player_gsis_id") or _slug(row.get("player_name", ""))
        if not player_id:
            continue
        grouped.setdefault(player_id, []).append(row)

    defense_allowed = _defense_allowed_by_position(weekly_rows)
    schedule_by_team = _remaining_opponents_by_team(schedules, season)
    players = [
        _to_player_stats(player_id, rows, sleeper_by_name, defense_allowed, schedule_by_team)
        for player_id, rows in grouped.items()
    ]
    players = [player for player in players if player.fantasy_points_per_game > 0]
    players = _apply_consensus_market_values(players)
    return sorted(players, key=lambda player: player.projected_points, reverse=True)[:limit]


def _apply_consensus_market_values(players: list[PlayerStats]) -> list[PlayerStats]:
    output: list[PlayerStats] = []
    grouped: dict[Position, list[PlayerStats]] = {"QB": [], "RB": [], "WR": [], "TE": []}
    for player in players:
        if player.position in grouped:
            grouped[player.position].append(player)
    for position, position_players in grouped.items():
        ordered = sorted(position_players, key=_market_sort_key, reverse=True)
        ppg_values = [player.fantasy_points_per_game for player in ordered]
        replacement = _rank_value(ppg_values, {"QB": 18, "RB": 36, "WR": 42, "TE": 18}[position])
        elite = _rank_value(ppg_values, {"QB": 3, "RB": 6, "WR": 8, "TE": 3}[position])
        for rank, player in enumerate(ordered, start=1):
            market = _consensus_market_score(position, rank, player, replacement, elite)
            output.append(replace(player, market_value=market))
    return output


def _market_sort_key(player: PlayerStats) -> float:
    return (
        player.fantasy_points_per_game * 0.70
        + (player.projected_points / max(1, player.remaining_games)) * 0.15
        + player.trend_score * 0.08
        + player.high_value_touch_rate * 0.35
    )


def _consensus_market_score(
    position: Position,
    rank: int,
    player: PlayerStats,
    replacement: float,
    elite: float,
) -> float:
    tier_score = _interpolated_rank_score(position, rank)
    edge = (player.fantasy_points_per_game - replacement) / max(1.0, elite - replacement)
    ppg_adjustment = (edge - 0.45) * 7.0
    trend_adjustment = (player.trend_score - 50.0) * 0.045
    risk_adjustment = player.role_uncertainty * 6.0 + player.injury_risk * 5.0
    high = 84.0 if position == "QB" else 96.0
    return round(_clip(tier_score + ppg_adjustment + trend_adjustment - risk_adjustment, 10, high), 2)


def _interpolated_rank_score(position: Position, rank: int) -> float:
    tiers = {
        "QB": [(1, 82.0), (3, 78.0), (6, 72.0), (12, 61.0), (18, 44.0), (30, 22.0)],
        "RB": [(1, 96.0), (6, 88.0), (12, 78.0), (24, 62.0), (36, 44.0), (60, 22.0)],
        "WR": [(1, 96.0), (8, 88.0), (12, 82.0), (24, 68.0), (36, 54.0), (60, 32.0)],
        "TE": [(1, 88.0), (3, 78.0), (6, 68.0), (12, 54.0), (18, 39.0), (30, 22.0)],
    }[position]
    if rank <= tiers[0][0]:
        return tiers[0][1]
    for (left_rank, left_score), (right_rank, right_score) in zip(tiers, tiers[1:]):
        if rank <= right_rank:
            distance = (rank - left_rank) / max(1, right_rank - left_rank)
            return left_score + (right_score - left_score) * distance
    return tiers[-1][1]


def _to_player_stats(
    player_id: str,
    rows: list[dict[str, str]],
    sleeper_by_name: dict[str, dict[str, object]],
    defense_allowed: dict[str, dict[str, float]],
    schedule_by_team: dict[str, list[str]],
) -> PlayerStats:
    latest = rows[-1]
    name = latest.get("player_display_name") or latest.get("player_name") or player_id
    sleeper = sleeper_by_name.get(_slug(name), {})
    position = _position(latest)
    team = latest.get("recent_team") or latest.get("team") or str(sleeper.get("team") or "FA")
    fantasy_points = [_fantasy_points(row) for row in rows]
    games = len([points for points in fantasy_points if points > 0])
    average_points = mean(fantasy_points) if fantasy_points else 0.0
    remaining_games = _remaining_games(schedule_by_team.get(team, []))
    target_games = max(1, games)
    targets_per_game = _sum(rows, "targets") / target_games
    carries_per_game = _sum(rows, "carries") / target_games
    red_zone_touches = _sum(rows, "rushing_tds") + _sum(rows, "receiving_tds")
    projected_points = average_points * max(remaining_games, 17 if games else 0)
    schedule_score = _schedule_score(position, schedule_by_team.get(team, []), defense_allowed)
    trend = _trend_score(fantasy_points)
    market = _market_from_rank(position, latest, average_points, trend)
    return PlayerStats(
        player_id=player_id,
        name=name,
        position=position,
        team=team,
        age=_float(sleeper.get("age"), 27.0),
        projected_points=round(projected_points, 2),
        fantasy_points_per_game=round(average_points, 2),
        games_played=games,
        snap_share=0.72,
        route_participation=_route_proxy(position, targets_per_game),
        target_share=_target_share_proxy(position, targets_per_game),
        targets_per_game=round(targets_per_game, 2),
        carries_per_game=round(carries_per_game, 2),
        red_zone_touches_per_game=round(red_zone_touches / target_games, 2),
        yards_per_route_run=_yards_per_route_proxy(rows, targets_per_game),
        yards_after_contact_per_attempt=2.4 if position == "RB" else 0.0,
        explosive_play_rate=_explosive_proxy(rows),
        team_implied_points=22.5,
        offensive_environment=_clip(average_points / 25, 0.25, 0.95),
        injury_risk=max(_injury_risk(sleeper), _availability_risk(games)),
        role_uncertainty=_role_uncertainty(games, trend),
        market_value=round(market, 2),
        average_draft_position=None,
        rest_of_season_strength_of_schedule=round(schedule_score, 2),
        remaining_games=remaining_games or 17,
        trend_score=round(trend, 2),
        bye_week=None,
    )


def _sleeper_by_name(players: dict[str, dict[str, object]]) -> dict[str, dict[str, object]]:
    output: dict[str, dict[str, object]] = {}
    for item in players.values():
        if not isinstance(item, dict):
            continue
        name = str(item.get("full_name") or f"{item.get('first_name', '')} {item.get('last_name', '')}")
        position = str(item.get("position") or "")
        if name.strip() and position in FANTASY_POSITIONS:
            output[_slug(name)] = item
    return output


def _defense_allowed_by_position(rows: list[dict[str, str]]) -> dict[str, dict[str, float]]:
    totals: dict[str, dict[str, list[float]]] = {}
    for row in rows:
        opponent = row.get("opponent_team") or row.get("opponent")
        position = _position(row)
        if not opponent or position not in FANTASY_POSITIONS:
            continue
        totals.setdefault(opponent, {}).setdefault(position, []).append(_fantasy_points(row))
    return {
        team: {position: mean(points) for position, points in positions.items()}
        for team, positions in totals.items()
    }


def _remaining_opponents_by_team(rows: list[dict[str, str]], season: int) -> dict[str, list[str]]:
    current_week = _current_nfl_week(rows, season)
    output: dict[str, list[str]] = {}
    for row in rows:
        if int(_float(row.get("season"), 0)) != season:
            continue
        week = int(_float(row.get("week"), 0))
        if week and week <= current_week:
            continue
        home = row.get("home_team")
        away = row.get("away_team")
        if home and away:
            output.setdefault(home, []).append(away)
            output.setdefault(away, []).append(home)
    return output


def _current_nfl_week(rows: list[dict[str, str]], season: int) -> int:
    completed = []
    for row in rows:
        if int(_float(row.get("season"), 0)) != season:
            continue
        result = row.get("result") or row.get("home_score")
        if result not in {"", None}:
            completed.append(int(_float(row.get("week"), 0)))
    return max(completed, default=0)


def _schedule_score(
    position: Position,
    opponents: list[str],
    defense_allowed: dict[str, dict[str, float]],
) -> float:
    if not opponents:
        return 50.0
    values = [defense_allowed.get(opponent, {}).get(position) for opponent in opponents]
    allowed = [value for value in values if value is not None]
    if not allowed:
        return 50.0
    avg_allowed = mean(allowed)
    position_baseline = {"QB": 18.0, "RB": 10.0, "WR": 11.0, "TE": 8.0}.get(position, 10.0)
    return _clip(50 + (avg_allowed - position_baseline) * 3.2, 20, 85)


def _fantasy_points(row: dict[str, str]) -> float:
    passing = _num(row, "passing_yards") / 25 + _num(row, "passing_tds") * 4 - _num(row, "interceptions") * 2
    rushing = _num(row, "rushing_yards") / 10 + _num(row, "rushing_tds") * 6
    receiving = _num(row, "receiving_yards") / 10 + _num(row, "receiving_tds") * 6 + _num(row, "receptions") * 0.5
    misc = _num(row, "passing_2pt_conversions") * 2 + _num(row, "rushing_2pt_conversions") * 2
    misc += _num(row, "receiving_2pt_conversions") * 2
    turnovers = (
        _num(row, "sack_fumbles_lost")
        + _num(row, "rushing_fumbles_lost")
        + _num(row, "receiving_fumbles_lost")
    ) * 2
    return round(passing + rushing + receiving + misc - turnovers, 2)


def _position(row: dict[str, str]) -> Position:
    raw = row.get("position") or row.get("position_group") or ""
    if raw in FANTASY_POSITIONS:
        return raw  # type: ignore[return-value]
    return "WR"


def _sum(rows: list[dict[str, str]], key: str) -> float:
    return sum(_num(row, key) for row in rows)


def _num(row: dict[str, str], key: str) -> float:
    return _float(row.get(key), 0.0)


def _float(value: object, default: float) -> float:
    try:
        if value is None:
            return default
        if isinstance(value, str) and not value:
            return default
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _remaining_games(opponents: list[str]) -> int:
    return len(opponents)


def _route_proxy(position: Position, targets_per_game: float) -> float:
    if position in {"WR", "TE"}:
        return _clip(0.35 + targets_per_game / 14, 0.25, 0.95)
    if position == "RB":
        return _clip(0.15 + targets_per_game / 18, 0.1, 0.65)
    return 0.0


def _target_share_proxy(position: Position, targets_per_game: float) -> float:
    if position in {"WR", "TE"}:
        return _clip(targets_per_game / 34, 0.02, 0.35)
    if position == "RB":
        return _clip(targets_per_game / 40, 0.0, 0.2)
    return 0.0


def _yards_per_route_proxy(rows: list[dict[str, str]], targets_per_game: float) -> float:
    receiving_yards = _sum(rows, "receiving_yards")
    routes = max(1.0, targets_per_game * len(rows) * 4.2)
    return round(_clip(receiving_yards / routes, 0.0, 3.2), 2)


def _explosive_proxy(rows: list[dict[str, str]]) -> float:
    total_yards = _sum(rows, "rushing_yards") + _sum(rows, "receiving_yards")
    touches = _sum(rows, "carries") + _sum(rows, "receptions")
    if touches <= 0:
        return 0.05
    return round(_clip((total_yards / touches - 4.0) / 30, 0.03, 0.18), 3)


def _trend_score(points: list[float]) -> float:
    if len(points) < 4:
        return 50.0
    recent = mean(points[-4:])
    full = mean(points)
    return _clip(50 + (recent - full) * 4, 20, 90)


def _market_from_rank(position: Position, row: dict[str, str], average_points: float, trend: float) -> float:
    position_bonus = {"QB": 8, "RB": 10, "WR": 10, "TE": 4}.get(position, 5)
    return _clip(average_points * 3.2 + trend * 0.35 + position_bonus, 15, 96)


def _injury_risk(sleeper: dict[str, object]) -> float:
    status = str(sleeper.get("injury_status") or sleeper.get("status") or "").lower()
    if any(term in status for term in ("out", "ir", "pup", "suspend")):
        return 0.75
    if any(term in status for term in ("question", "doubt")):
        return 0.45
    return 0.16


def _availability_risk(games: int) -> float:
    if games >= 15:
        return 0.12
    if games >= 12:
        return 0.22
    if games >= 8:
        return 0.34
    if games >= 4:
        return 0.46
    return 0.58


def _role_uncertainty(games: int, trend: float) -> float:
    if games <= 2:
        return 0.45
    if trend < 38:
        return 0.3
    return 0.14


def _slug(value: str) -> str:
    return "".join(character.lower() for character in value if character.isalnum())


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
