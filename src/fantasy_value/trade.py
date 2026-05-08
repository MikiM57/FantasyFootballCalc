from __future__ import annotations

from dataclasses import dataclass

from fantasy_value.models import ExpertMention, LeagueSettings, PlayerStats, RosterContext
from fantasy_value.scoring import PlayerValuation, ValuationEngine


@dataclass(frozen=True)
class TradeSide:
    label: str
    player_ids: tuple[str, ...]


@dataclass(frozen=True)
class TradeResult:
    side_a: str
    side_b: str
    side_a_value: float
    side_b_value: float
    net_for_a: float
    verdict: str
    side_a_players: list[PlayerValuation]
    side_b_players: list[PlayerValuation]
    explanation: list[str]


class TradeAnalyzer:
    def __init__(self, engine: ValuationEngine | None = None) -> None:
        self.engine = engine or ValuationEngine()

    def analyze(
        self,
        players: list[PlayerStats],
        mentions: list[ExpertMention],
        side_a: TradeSide,
        side_b: TradeSide,
        league: LeagueSettings,
        roster: RosterContext | None = None,
    ) -> TradeResult:
        roster = roster or RosterContext()
        player_map = {player.player_id: player for player in players}
        mention_map: dict[str, list[ExpertMention]] = {}
        for mention in mentions:
            mention_map.setdefault(mention.player_id, []).append(mention)

        side_a_values = [
            self.engine.value_player(player_map[player_id], mention_map.get(player_id, []), league, roster)
            for player_id in side_a.player_ids
            if player_id in player_map
        ]
        side_b_values = [
            self.engine.value_player(player_map[player_id], mention_map.get(player_id, []), league, roster)
            for player_id in side_b.player_ids
            if player_id in player_map
        ]

        value_a = self._package_value(side_a_values, league)
        value_b = self._package_value(side_b_values, league)
        net = round(value_b - value_a, 2)
        verdict = self._verdict(net)
        explanation = self._explain(side_a_values, side_b_values, net, league)

        return TradeResult(
            side_a=side_a.label,
            side_b=side_b.label,
            side_a_value=round(value_a, 2),
            side_b_value=round(value_b, 2),
            net_for_a=net,
            verdict=verdict,
            side_a_players=side_a_values,
            side_b_players=side_b_values,
            explanation=explanation,
        )

    @staticmethod
    def _package_value(players: list[PlayerValuation], league: LeagueSettings) -> float:
        if not players:
            return 0.0
        values = sorted((player.value for player in players), reverse=True)
        total = 0.0
        for index, value in enumerate(values):
            if index == 0:
                total += value
            else:
                depth_discount = 0.82 if league.starters.get("WR", 2) + league.flex_spots <= 5 else 0.90
                total += value * depth_discount
        if len(values) == 1 and values[0] >= 75:
            total *= 1.05
        return total

    @staticmethod
    def _verdict(net_for_a: float) -> str:
        if net_for_a >= 8:
            return "accept"
        if net_for_a >= 2:
            return "lean_accept"
        if net_for_a > -2:
            return "fair"
        if net_for_a > -8:
            return "lean_decline"
        return "decline"

    @staticmethod
    def _explain(
        side_a_players: list[PlayerValuation],
        side_b_players: list[PlayerValuation],
        net: float,
        league: LeagueSettings,
    ) -> list[str]:
        notes: list[str] = []
        if len(side_a_players) > len(side_b_players):
            notes.append("You are consolidating assets, which can be valuable in shallower starter formats.")
        if len(side_a_players) < len(side_b_players):
            notes.append("You are adding depth, which matters more in deeper starter formats.")
        if any(player.position == "QB" for player in side_a_players + side_b_players) and league.superflex:
            notes.append("Superflex settings increase the importance of quarterback value.")
        if net >= 2:
            notes.append("Incoming value is ahead after roster and package adjustments.")
        elif net <= -2:
            notes.append("Outgoing value is ahead after roster and package adjustments.")
        else:
            notes.append("The deal is close enough that team direction should decide it.")
        return notes
