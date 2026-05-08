from __future__ import annotations

from dataclasses import dataclass
from statistics import mean

from fantasy_value.models import ExpertMention, LeagueSettings, PlayerStats, Position, RosterContext


@dataclass(frozen=True)
class PlayerValuation:
    player_id: str
    name: str
    position: Position
    team: str
    value: float
    standalone_value: float
    roster_adjusted_value: float
    production_score: float
    opportunity_score: float
    efficiency_score: float
    environment_score: float
    sentiment_score: float
    market_score: float
    risk_penalty: float
    explanation: list[str]


class ValuationEngine:
    """Transparent first-pass valuation model.

    The model deliberately avoids hiding behind a black box. Each component is
    visible so rankings can be debugged before adding trained models.
    """

    def rank_players(
        self,
        players: list[PlayerStats],
        mentions: list[ExpertMention],
        league: LeagueSettings,
        roster: RosterContext | None = None,
    ) -> list[PlayerValuation]:
        roster = roster or RosterContext()
        mention_map = self._mentions_by_player(mentions)
        valuations = [
            self.value_player(player, mention_map.get(player.player_id, []), league, roster)
            for player in players
        ]
        return sorted(valuations, key=lambda item: item.value, reverse=True)

    def value_player(
        self,
        player: PlayerStats,
        mentions: list[ExpertMention],
        league: LeagueSettings,
        roster: RosterContext | None = None,
    ) -> PlayerValuation:
        roster = roster or RosterContext()

        production = self._production_score(player)
        opportunity = self._opportunity_score(player)
        efficiency = self._efficiency_score(player)
        environment = self._environment_score(player)
        sentiment = self._sentiment_score(mentions)
        market = self._market_score(player)
        age = self._age_score(player, league)
        scarcity = self._scarcity_multiplier(player, league)
        risk = self._risk_penalty(player)

        weights = self._weights(league)
        standalone = (
            production * weights["production"]
            + opportunity * weights["opportunity"]
            + efficiency * weights["efficiency"]
            + environment * weights["environment"]
            + sentiment * weights["sentiment"]
            + market * weights["market"]
            + age * weights["age"]
            - risk * weights["risk"]
        )
        standalone *= scarcity

        roster_adjusted = standalone + self._context_adjustment(player, roster, league)
        explanation = self._explain(
            player=player,
            production=production,
            opportunity=opportunity,
            sentiment=sentiment,
            risk=risk,
            roster=roster,
        )

        return PlayerValuation(
            player_id=player.player_id,
            name=player.name,
            position=player.position,
            team=player.team,
            value=round(roster_adjusted, 2),
            standalone_value=round(standalone, 2),
            roster_adjusted_value=round(roster_adjusted, 2),
            production_score=round(production, 2),
            opportunity_score=round(opportunity, 2),
            efficiency_score=round(efficiency, 2),
            environment_score=round(environment, 2),
            sentiment_score=round(sentiment, 2),
            market_score=round(market, 2),
            risk_penalty=round(risk, 2),
            explanation=explanation,
        )

    @staticmethod
    def _mentions_by_player(mentions: list[ExpertMention]) -> dict[str, list[ExpertMention]]:
        grouped: dict[str, list[ExpertMention]] = {}
        for mention in mentions:
            grouped.setdefault(mention.player_id, []).append(mention)
        return grouped

    @staticmethod
    def _clip(value: float, low: float = 0.0, high: float = 100.0) -> float:
        return max(low, min(high, value))

    def _production_score(self, player: PlayerStats) -> float:
        projected = player.projected_points / 3.2
        per_game = player.fantasy_points_per_game * 4.0
        durability = min(100.0, player.games_played / 17 * 100)
        return self._clip(projected * 0.45 + per_game * 0.45 + durability * 0.10)

    def _opportunity_score(self, player: PlayerStats) -> float:
        route_role = player.route_participation * 100
        target_role = player.target_share * 220
        rushing_role = player.carries_per_game * 4.2
        high_value = player.high_value_touch_rate * 7.5
        snaps = player.snap_share * 100
        if player.position == "QB":
            return self._clip(player.projected_points / 3.0 + player.offensive_environment * 15)
        if player.position in {"WR", "TE"}:
            return self._clip(route_role * 0.35 + target_role * 0.35 + high_value * 0.20 + snaps * 0.10)
        if player.position == "RB":
            return self._clip(rushing_role * 0.45 + high_value * 0.35 + snaps * 0.20)
        return self._clip(snaps)

    def _efficiency_score(self, player: PlayerStats) -> float:
        receiving = player.yards_per_route_run * 24
        rushing = player.yards_after_contact_per_attempt * 20
        explosive = player.explosive_play_rate * 300
        if player.position in {"WR", "TE"}:
            return self._clip(receiving * 0.70 + explosive * 0.30)
        if player.position == "RB":
            return self._clip(rushing * 0.55 + explosive * 0.25 + receiving * 0.20)
        if player.position == "QB":
            return self._clip(player.fantasy_points_per_game * 4.0 + explosive * 0.20)
        return self._clip(explosive)

    def _environment_score(self, player: PlayerStats) -> float:
        implied = player.team_implied_points * 3.0
        offense = player.offensive_environment * 50
        return self._clip(implied * 0.55 + offense * 0.45)

    def _sentiment_score(self, mentions: list[ExpertMention]) -> float:
        if not mentions:
            return 50.0
        weighted = [
            (mention.sentiment * 50 + 50) * mention.magnitude * mention.confidence
            for mention in mentions
        ]
        weights = [max(0.05, mention.magnitude * mention.confidence) for mention in mentions]
        return self._clip(sum(weighted) / sum(weights))

    def _market_score(self, player: PlayerStats) -> float:
        if player.market_value > 0:
            return self._clip(player.market_value)
        if player.average_draft_position:
            return self._clip(100 - player.average_draft_position / 3)
        return 50.0

    def _age_score(self, player: PlayerStats, league: LeagueSettings) -> float:
        if not league.dynasty:
            return 50.0
        peak = {"QB": 29.0, "RB": 24.5, "WR": 26.5, "TE": 27.5}.get(player.position, 26.0)
        distance = abs(player.age - peak)
        return self._clip(100 - distance * 11)

    def _risk_penalty(self, player: PlayerStats) -> float:
        injury = player.injury_risk * 100
        role = player.role_uncertainty * 100
        return self._clip(injury * 0.55 + role * 0.45)

    @staticmethod
    def _weights(league: LeagueSettings) -> dict[str, float]:
        weights = {
            "production": 0.25,
            "opportunity": 0.22,
            "efficiency": 0.12,
            "environment": 0.10,
            "sentiment": 0.10,
            "market": 0.12,
            "age": 0.09,
            "risk": 0.12,
        }
        if league.dynasty:
            weights["age"] += 0.06
            weights["market"] += 0.03
            weights["production"] -= 0.05
            weights["environment"] -= 0.04
        else:
            weights["production"] += 0.07
            weights["opportunity"] += 0.04
            weights["age"] -= 0.06
            weights["market"] -= 0.03
        return weights

    @staticmethod
    def _scarcity_multiplier(player: PlayerStats, league: LeagueSettings) -> float:
        if player.position == "QB" and league.superflex:
            return 1.18
        if player.position == "TE":
            premium_boost = min(0.16, league.tight_end_premium * 0.12)
            starter_boost = 0.04 if league.starters.get("TE", 1) > 1 else 0.0
            return 1.0 + premium_boost + starter_boost
        if player.position == "WR" and league.starters.get("WR", 2) >= 3:
            return 1.05
        return 1.0

    @staticmethod
    def _context_adjustment(
        player: PlayerStats,
        roster: RosterContext,
        league: LeagueSettings,
    ) -> float:
        need_bonus = roster.need_for(player.position) * 8.0
        window_bonus = 0.0
        if roster.competitive_window == "contender":
            window_bonus += player.fantasy_points_per_game * 0.35
            window_bonus -= player.role_uncertainty * 4.0
        elif roster.competitive_window == "rebuilder":
            if league.dynasty:
                if player.position == "RB" and player.age > 25.5:
                    window_bonus -= 5.0
                if player.position in {"WR", "TE", "QB"} and player.age < 26.0:
                    window_bonus += 4.0
            window_bonus -= player.injury_risk * 3.0
        return need_bonus + window_bonus

    @staticmethod
    def _explain(
        player: PlayerStats,
        production: float,
        opportunity: float,
        sentiment: float,
        risk: float,
        roster: RosterContext,
    ) -> list[str]:
        reasons: list[str] = []
        if production >= 75:
            reasons.append("Strong fantasy production profile.")
        if opportunity >= 75:
            reasons.append("Role and high-value touches are carrying the projection.")
        if sentiment >= 65:
            reasons.append("Expert/article sentiment is positive.")
        if sentiment <= 40:
            reasons.append("Expert/article sentiment is cautious.")
        if risk >= 55:
            reasons.append("Injury or role uncertainty is a meaningful drag.")
        need = roster.need_for(player.position)
        if need >= 0.35:
            reasons.append(f"Roster context boosts {player.position} because it is a need.")
        if need <= -0.35:
            reasons.append(f"Roster context discounts {player.position} because it is already deep.")
        if not reasons:
            reasons.append("Balanced profile with no single extreme signal.")
        return reasons


def average_value(values: list[PlayerValuation]) -> float:
    if not values:
        return 0.0
    return round(mean(item.value for item in values), 2)
