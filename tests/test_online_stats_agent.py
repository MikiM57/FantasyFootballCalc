from fantasy_value.agents.online_stats_agent import build_player_stats


def test_build_player_stats_from_weekly_rows():
    rows = [
        {
            "player_id": "00-001",
            "player_name": "Test Runner",
            "position": "RB",
            "recent_team": "ATL",
            "week": "1",
            "season": "2025",
            "opponent_team": "CAR",
            "carries": "18",
            "rushing_yards": "90",
            "rushing_tds": "1",
            "targets": "4",
            "receptions": "3",
            "receiving_yards": "24",
            "receiving_tds": "0",
        },
        {
            "player_id": "00-001",
            "player_name": "Test Runner",
            "position": "RB",
            "recent_team": "ATL",
            "week": "2",
            "season": "2025",
            "opponent_team": "NO",
            "carries": "14",
            "rushing_yards": "70",
            "rushing_tds": "0",
            "targets": "5",
            "receptions": "4",
            "receiving_yards": "32",
            "receiving_tds": "1",
        },
    ]
    sleeper = {"1": {"full_name": "Test Runner", "age": 24, "position": "RB", "team": "ATL"}}
    schedules = [
        {
            "season": "2025",
            "week": "3",
            "home_team": "ATL",
            "away_team": "CAR",
            "home_score": "",
            "result": "",
        }
    ]

    players = build_player_stats(rows, sleeper, schedules, season=2025, limit=10)

    assert len(players) == 1
    assert players[0].name == "Test Runner"
    assert players[0].position == "RB"
    assert players[0].fantasy_points_per_game > 0
    assert players[0].rest_of_season_strength_of_schedule > 0
