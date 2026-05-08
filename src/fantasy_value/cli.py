from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from fantasy_value.models import LeagueSettings, RosterContext
from fantasy_value.repository import load_mentions, load_players
from fantasy_value.scoring import ValuationEngine
from fantasy_value.trade import TradeAnalyzer, TradeSide


def main() -> None:
    parser = argparse.ArgumentParser(prog="fantasy-edge")
    subparsers = parser.add_subparsers(dest="command", required=True)

    rank_parser = subparsers.add_parser("rank", help="Rank players from JSON inputs.")
    rank_parser.add_argument("--players", required=True)
    rank_parser.add_argument("--mentions", required=True)
    rank_parser.add_argument("--superflex", action="store_true")
    rank_parser.add_argument("--redraft", action="store_true")

    trade_parser = subparsers.add_parser("trade", help="Analyze a player trade.")
    trade_parser.add_argument("--players", required=True)
    trade_parser.add_argument("--mentions", required=True)
    trade_parser.add_argument("--give", required=True, help="Comma-separated player ids.")
    trade_parser.add_argument("--get", required=True, help="Comma-separated player ids.")
    trade_parser.add_argument("--superflex", action="store_true")
    trade_parser.add_argument("--redraft", action="store_true")

    args = parser.parse_args()
    if args.command == "rank":
        _rank(args)
    elif args.command == "trade":
        _trade(args)


def _league_from_args(args: argparse.Namespace) -> LeagueSettings:
    return LeagueSettings(superflex=args.superflex, dynasty=not args.redraft)


def _rank(args: argparse.Namespace) -> None:
    players = load_players(args.players)
    mentions = load_mentions(args.mentions)
    rankings = ValuationEngine().rank_players(players, mentions, _league_from_args(args), RosterContext())
    print(json.dumps([asdict(item) for item in rankings], indent=2))


def _trade(args: argparse.Namespace) -> None:
    players = load_players(args.players)
    mentions = load_mentions(args.mentions)
    result = TradeAnalyzer().analyze(
        players=players,
        mentions=mentions,
        side_a=TradeSide("give", tuple(item.strip() for item in args.give.split(",") if item.strip())),
        side_b=TradeSide("get", tuple(item.strip() for item in args.get.split(",") if item.strip())),
        league=_league_from_args(args),
        roster=RosterContext(),
    )
    print(json.dumps(asdict(result), indent=2))


if __name__ == "__main__":
    main()
