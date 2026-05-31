from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from fantasy_value.agents.article_sources import ArticleSourceConfig
from fantasy_value.agents.online_stats_agent import OnlineNflStatsAgent, OnlineStatsConfig
from fantasy_value.agents.pipeline import InternetAgentPipeline
from fantasy_value.models import LeagueSettings, RosterContext
from fantasy_value.repository import load_mentions, load_players
from fantasy_value.scoring import ValuationEngine
from fantasy_value.trade import TradeAnalyzer, TradeSide


def main() -> None:
    parser = argparse.ArgumentParser(prog="fantasy-football-calc")
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

    agents_parser = subparsers.add_parser("agents", help="Run expert sentiment agents once.")
    agents_parser.add_argument("--players", default="data/sample_players.json")
    agents_parser.add_argument("--output", default="data/runtime/latest_mentions.json")
    agents_parser.add_argument("--feed", action="append", default=[])
    agents_parser.add_argument("--url", action="append", default=[])
    agents_parser.add_argument("--fetch-bodies", action="store_true")
    agents_parser.add_argument("--online-stats", action="store_true")
    agents_parser.add_argument("--stats-output", default="data/runtime/latest_players.json")

    stats_parser = subparsers.add_parser("online-stats", help="Fetch online NFL player stats once.")
    stats_parser.add_argument("--output", default="data/runtime/latest_players.json")
    stats_parser.add_argument("--season", type=int)
    stats_parser.add_argument("--limit", type=int, default=250)
    stats_parser.add_argument("--fallback-seasons", type=int, default=2)
    stats_parser.add_argument("--no-schedule", action="store_true")

    args = parser.parse_args()
    if args.command == "rank":
        _rank(args)
    elif args.command == "trade":
        _trade(args)
    elif args.command == "agents":
        _agents(args)
    elif args.command == "online-stats":
        _online_stats(args)


def _league_from_args(args: argparse.Namespace) -> LeagueSettings:
    return LeagueSettings(superflex=args.superflex, dynasty=not args.redraft)


def _rank(args: argparse.Namespace) -> None:
    players = load_players(args.players)
    mentions = load_mentions(args.mentions)
    rankings = ValuationEngine().rank_players(
        players,
        mentions,
        _league_from_args(args),
        RosterContext(),
    )
    print(json.dumps([asdict(item) for item in rankings], indent=2))


def _trade(args: argparse.Namespace) -> None:
    players = load_players(args.players)
    mentions = load_mentions(args.mentions)
    result = TradeAnalyzer().analyze(
        players=players,
        mentions=mentions,
        side_a=TradeSide(
            "give",
            tuple(item.strip() for item in args.give.split(",") if item.strip()),
        ),
        side_b=TradeSide(
            "get",
            tuple(item.strip() for item in args.get.split(",") if item.strip()),
        ),
        league=_league_from_args(args),
        roster=RosterContext(),
    )
    print(json.dumps(asdict(result), indent=2))


def _agents(args: argparse.Namespace) -> None:
    stats_agent = (
        OnlineNflStatsAgent(
            output_path=Path(args.stats_output),
            config=OnlineStatsConfig(),
        )
        if args.online_stats
        else None
    )
    result = InternetAgentPipeline(
        players_path=Path(args.stats_output) if args.online_stats else Path(args.players),
        mentions_output_path=Path(args.output),
        source_config=ArticleSourceConfig(
            rss_feeds=tuple(args.feed),
            article_urls=tuple(args.url),
            fetch_article_bodies=args.fetch_bodies,
        ),
        stats_agent=stats_agent,
        fallback_players_path=Path(args.players),
    ).run()
    print(json.dumps(result.to_dict(), indent=2))


def _online_stats(args: argparse.Namespace) -> None:
    result = OnlineNflStatsAgent(
        output_path=Path(args.output),
        config=OnlineStatsConfig(
            season=args.season,
            fallback_seasons=args.fallback_seasons,
            limit=args.limit,
            include_schedule=not args.no_schedule,
        ),
    ).run()
    print(json.dumps(asdict(result), indent=2))


if __name__ == "__main__":
    main()
