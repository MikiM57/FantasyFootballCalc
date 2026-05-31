from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Any

from fantasy_value.models import ExpertMention, PlayerStats


def load_players(path: str | Path) -> list[PlayerStats]:
    raw = _load_json(path)
    return [PlayerStats(**item) for item in raw]


def save_players(path: str | Path, players: list[PlayerStats]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump([asdict(player) for player in players], handle, indent=2)


def load_mentions(path: str | Path) -> list[ExpertMention]:
    raw = _load_json(path)
    mentions: list[ExpertMention] = []
    for item in raw:
        item = dict(item)
        if item.get("published_on"):
            item["published_on"] = date.fromisoformat(item["published_on"])
        mentions.append(ExpertMention(**item))
    return mentions


def save_mentions(path: str | Path, mentions: list[ExpertMention]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for mention in mentions:
        item = asdict(mention)
        if mention.published_on:
            item["published_on"] = mention.published_on.isoformat()
        rows.append(item)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(rows, handle, indent=2)


def _load_json(path: str | Path) -> Any:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)
