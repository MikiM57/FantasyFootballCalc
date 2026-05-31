from pathlib import Path

from fantasy_value import api


def test_current_data_falls_back_when_runtime_players_are_empty(tmp_path: Path, monkeypatch):
    runtime_players = tmp_path / "latest_players.json"
    runtime_players.write_text("[]", encoding="utf-8")

    monkeypatch.setattr(api, "ONLINE_STATS_ENABLED", True)
    monkeypatch.setattr(api, "RUNTIME_PLAYERS_PATH", runtime_players)
    monkeypatch.setattr(api, "CONFIGURED_PLAYERS_PATH", Path("data/sample_players.json").resolve())
    monkeypatch.setattr(api, "RUNTIME_MENTIONS_PATH", tmp_path / "missing_mentions.json")
    monkeypatch.setattr(api, "MENTIONS_PATH", Path("data/sample_mentions.json").resolve())

    players, mentions = api._current_data()

    assert players
    assert mentions
