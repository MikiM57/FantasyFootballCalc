from fantasy_value.models import LeagueSettings, RosterContext
from fantasy_value.repository import load_mentions, load_players
from fantasy_value.scoring import ValuationEngine
from fantasy_value.sleepers import SleeperRanker


def test_sleepers_rank_undervalued_candidates():
    players = load_players("data/sample_players.json")
    mentions = load_mentions("data/sample_mentions.json")

    sleepers = SleeperRanker(ValuationEngine()).rank(
        players,
        mentions,
        LeagueSettings(dynasty=True),
        RosterContext(),
    )

    assert sleepers
    assert sleepers[0].sleeper_score >= sleepers[-1].sleeper_score
    assert sleepers[0].position in {"QB", "RB", "WR", "TE"}


def test_expensive_elite_players_are_capped_as_sleepers():
    players = load_players("data/sample_players.json")
    mentions = load_mentions("data/sample_mentions.json")

    sleepers = {
        player.player_id: player
        for player in SleeperRanker().rank(players, mentions, LeagueSettings(dynasty=True))
    }

    if "jamarr-chase" in sleepers:
        assert sleepers["jamarr-chase"].sleeper_score <= 62
