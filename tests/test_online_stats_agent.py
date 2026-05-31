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
            "week": "19",
            "season": "2025",
            "season_type": "POST",
            "opponent_team": "NO",
            "carries": "30",
            "rushing_yards": "250",
            "rushing_tds": "4",
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
    assert players[0].games_played == 2
    assert players[0].fantasy_points_per_game > 0
    assert players[0].rest_of_season_strength_of_schedule > 0


def test_online_market_values_are_position_aware():
    rows = []
    for week in range(1, 6):
        rows.append(
            {
                "player_id": "qb-1",
                "player_name": "High Scoring QB",
                "position": "QB",
                "recent_team": "BUF",
                "week": str(week),
                "season": "2025",
                "passing_yards": "300",
                "passing_tds": "3",
                "interceptions": "0",
                "rushing_yards": "30",
            }
        )
        rows.append(
            {
                "player_id": "wr-1",
                "player_name": "Elite Receiver",
                "position": "WR",
                "recent_team": "CIN",
                "week": str(week),
                "season": "2025",
                "targets": "11",
                "receptions": "8",
                "receiving_yards": "105",
                "receiving_tds": "1",
            }
        )

    players = build_player_stats(rows, {}, [], season=2025, limit=10)
    values = {player.player_id: player.market_value for player in players}

    assert values["wr-1"] > values["qb-1"]
