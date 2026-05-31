from fantasy_value.models import ExpertMention, LeagueSettings, RosterContext
from fantasy_value.repository import load_mentions, load_players
from fantasy_value.scoring import ValuationEngine
from fantasy_value.trade import TradeAnalyzer, TradeSide


def test_superflex_boosts_elite_quarterback_value():
    players = load_players("data/sample_players.json")
    mentions = load_mentions("data/sample_mentions.json")
    engine = ValuationEngine()

    standard = {
        value.player_id: value
        for value in engine.rank_players(players, mentions, LeagueSettings(superflex=False))
    }
    superflex = {
        value.player_id: value
        for value in engine.rank_players(players, mentions, LeagueSettings(superflex=True))
    }

    assert superflex["josh-allen"].value > standard["josh-allen"].value


def test_roster_need_changes_player_value():
    players = load_players("data/sample_players.json")
    mentions = load_mentions("data/sample_mentions.json")
    engine = ValuationEngine()

    neutral = engine.rank_players(players, mentions, LeagueSettings(), RosterContext())
    needs_wr = engine.rank_players(
        players,
        mentions,
        LeagueSettings(),
        RosterContext(positional_needs={"WR": 1.0}),
    )

    neutral_chase = next(player for player in neutral if player.player_id == "jamarr-chase")
    needed_chase = next(player for player in needs_wr if player.player_id == "jamarr-chase")

    assert needed_chase.value > neutral_chase.value


def test_negative_sentiment_lowers_value():
    player = next(item for item in load_players("data/sample_players.json") if item.player_id == "drake-london")
    base = ValuationEngine().value_player(player, [], LeagueSettings()).value
    negative = ValuationEngine().value_player(
        player,
        [
            ExpertMention(
                player_id=player.player_id,
                player_name=player.name,
                source="test",
                url=None,
                published_on=None,
                sentiment=-0.9,
                magnitude=1.0,
                confidence=1.0,
                context="draft",
                reason="Overvalued risk.",
            )
        ],
        LeagueSettings(),
    ).value

    assert negative < base


def test_trade_analyzer_returns_verdict():
    players = load_players("data/sample_players.json")
    mentions = load_mentions("data/sample_mentions.json")

    result = TradeAnalyzer().analyze(
        players,
        mentions,
        TradeSide("give", ("derrick-henry",)),
        TradeSide("receive", ("drake-london",)),
        LeagueSettings(dynasty=True),
        RosterContext(competitive_window="rebuilder"),
    )

    assert result.verdict in {"accept", "lean_accept", "fair", "lean_decline", "decline"}
    assert result.net_for_a > 0
    assert result.side_b_summary.expert_favorability > 0


def test_trade_analyzer_supports_five_player_packages():
    players = load_players("data/sample_players.json")
    mentions = load_mentions("data/sample_mentions.json")

    result = TradeAnalyzer().analyze(
        players,
        mentions,
        TradeSide("give", ("derrick-henry",)),
        TradeSide(
            "receive",
            ("drake-london", "bijan-robinson", "jamarr-chase", "josh-allen", "sam-laporta"),
        ),
        LeagueSettings(dynasty=True, superflex=True),
        RosterContext(competitive_window="balanced"),
    )

    assert result.side_b_summary.player_count == 5
    assert result.side_b_summary.rest_of_season_points > result.side_a_summary.rest_of_season_points
