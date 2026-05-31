from __future__ import annotations

from dataclasses import dataclass

from fantasy_value.models import ExpertMention, LeagueSettings, PlayerStats, Position, RosterContext
from fantasy_value.scoring import PlayerValuation, ValuationEngine


@dataclass(frozen=True)
class SleeperCandidate:
    player_id: str
    name: str
    position: Position
    team: str
    sleeper_score: float
    current_value: float
    market_score: float
    value_gap: float
    trend_score: float
    opportunity_score: float
    efficiency_score: float
    age: float
    average_points: float
    rest_of_season_points: float
    explanation: list[str]


class SleeperRanker:
    def __init__(self, engine: ValuationEngine | None = None) -> None:
        self.engine = engine or ValuationEngine()

    def rank(
        self,
        players: list[PlayerStats],
        mentions: list[ExpertMention],
        league: LeagueSettings,
        roster: RosterContext | None = None,
        limit: int = 60,
    ) -> list[SleeperCandidate]:
        roster = roster or RosterContext()
        mention_map: dict[str, list[ExpertMention]] = {}
        for mention in mentions:
            mention_map.setdefault(mention.player_id, []).append(mention)

        candidates = [
            self._candidate(
                player,
                self.engine.value_player(
                    player,
                    mention_map.get(player.player_id, []),
                    league,
                    roster,
                ),
                league,
            )
            for player in players
            if player.position in {"QB", "RB", "WR", "TE"}
        ]
        candidates = [candidate for candidate in candidates if candidate.sleeper_score >= 35]
        return sorted(candidates, key=lambda item: item.sleeper_score, reverse=True)[:limit]

    def _candidate(
        self,
        player: PlayerStats,
        valuation: PlayerValuation,
        league: LeagueSettings,
    ) -> SleeperCandidate:
        age_signal = self._age_signal(player)
        market = valuation.market_score
        value_gap = valuation.value - market
        undervalued = self._clip(48 + value_gap * 1.8 + (100 - market) * 0.24)
        runway = self._clip(
            valuation.opportunity_score * 0.42
            + valuation.efficiency_score * 0.24
            + player.trend_score * 0.22
            + age_signal * 0.12
        )
        score = (
            undervalued * 0.30
            + runway * 0.31
            + age_signal * 0.15
            + player.trend_score * 0.12
            + valuation.strength_of_schedule * 0.06
            + valuation.expert_favorability * 0.06
            - valuation.risk_penalty * 0.16
        )
        score = self._apply_sleeper_caps(score, player, market, league)
        return SleeperCandidate(
            player_id=player.player_id,
            name=player.name,
            position=player.position,
            team=player.team,
            sleeper_score=round(score, 2),
            current_value=valuation.value,
            market_score=market,
            value_gap=round(value_gap, 2),
            trend_score=round(player.trend_score, 2),
            opportunity_score=valuation.opportunity_score,
            efficiency_score=valuation.efficiency_score,
            age=player.age,
            average_points=valuation.average_points,
            rest_of_season_points=valuation.rest_of_season_points,
            explanation=self._explain(player, valuation, value_gap, age_signal, market),
        )

    @staticmethod
    def _age_signal(player: PlayerStats) -> float:
        peak = {"QB": 28.5, "RB": 24.0, "WR": 25.5, "TE": 26.5}.get(player.position, 25.5)
        young_bonus = max(0.0, peak - player.age) * 9.0
        near_peak = max(0.0, 100 - abs(player.age - peak) * 12.0)
        return max(young_bonus, near_peak)

    def _apply_sleeper_caps(
        self,
        score: float,
        player: PlayerStats,
        market: float,
        league: LeagueSettings,
    ) -> float:
        if market >= 92:
            score = min(score, 62.0)
        elif market >= 84:
            score = min(score, 74.0)
        if player.position == "QB" and not league.superflex:
            score = min(score, 78.0)
        if player.position == "RB" and player.age >= 27:
            score = min(score, 64.0)
        return self._clip(score)

    @staticmethod
    def _explain(
        player: PlayerStats,
        valuation: PlayerValuation,
        value_gap: float,
        age_signal: float,
        market: float,
    ) -> list[str]:
        reasons: list[str] = []
        if value_gap >= 5:
            reasons.append("Model value is ahead of market score.")
        if market <= 70:
            reasons.append("Not priced like an established star yet.")
        if valuation.opportunity_score >= 65:
            reasons.append("Usage and role indicators are already strong.")
        if valuation.efficiency_score >= 60:
            reasons.append("Efficiency profile supports a larger future role.")
        if player.trend_score >= 60:
            reasons.append("Recent production trend is improving.")
        if age_signal >= 70:
            reasons.append("Age curve leaves room for next-season growth.")
        if valuation.risk_penalty >= 50:
            reasons.append("Risk is elevated, so the upside is less stable.")
        if not reasons:
            reasons.append("Balanced upside profile with modest breakout indicators.")
        return reasons

    @staticmethod
    def _clip(value: float, low: float = 0.0, high: float = 100.0) -> float:
        return max(low, min(high, value))
