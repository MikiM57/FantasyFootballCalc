from fantasy_value.agents.online_stats_agent import calibration_from_weekly_stats
from fantasy_value.calibration import Calibration, PositionCalibration
from fantasy_value.models import LeagueSettings
from fantasy_value.repository import load_mentions, load_players
from fantasy_value.scoring import ValuationEngine


def test_calibration_from_weekly_stats_builds_position_baselines():
    rows = []
    for index in range(1, 9):
        for week in range(1, 6):
            rows.append(
                {
                    "player_id": f"qb-{index}",
                    "player_name": f"Quarterback {index}",
                    "position": "QB",
                    "passing_yards": str(180 + index * 10),
                    "passing_tds": str(index % 3),
                    "interceptions": "0",
                    "week": str(week),
                }
            )
            rows.append(
                {
                    "player_id": f"wr-{index}",
                    "player_name": f"Receiver {index}",
                    "position": "WR",
                    "receptions": str(2 + index),
                    "receiving_yards": str(35 + index * 9),
                    "receiving_tds": str(index % 2),
                    "week": str(week),
                }
            )

    calibration = calibration_from_weekly_stats({2023: rows}, training_season=2023)

    assert calibration.seasons == [2023]
    assert calibration.model.trained_seasons == [2023]
    assert calibration.model.market_anchor > 0
    assert calibration.positions["QB"].elite_ppg >= calibration.positions["QB"].starter_ppg
    assert calibration.positions["WR"].replacement_ppg > 0


def test_custom_calibration_changes_qb_discount():
    players = load_players("data/sample_players.json")
    mentions = load_mentions("data/sample_mentions.json")

    conservative = Calibration(
        seasons=[2021, 2022, 2023],
        positions={
            "QB": PositionCalibration(14, 18, 24, 16, 0.6, 1.25),
            "RB": PositionCalibration(7, 11, 20, 8, 1.0, 1.0),
            "WR": PositionCalibration(8, 12, 21, 9, 1.05, 1.0),
            "TE": PositionCalibration(5, 8, 16, 6, 1.0, 1.0),
        },
    )

    default_values = {
        value.player_id: value
        for value in ValuationEngine().rank_players(players, mentions, LeagueSettings())
    }
    calibrated_values = {
        value.player_id: value
        for value in ValuationEngine(conservative).rank_players(players, mentions, LeagueSettings())
    }

    assert calibrated_values["josh-allen"].value < default_values["josh-allen"].value
