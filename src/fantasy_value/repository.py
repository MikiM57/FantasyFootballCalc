from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

from fantasy_value.models import ExpertMention, PlayerStats


def load_players(path: str | Path) -> list[PlayerStats]:
    raw = _load_json(path)
    return [PlayerStats(**item) for item in raw]


def load_mentions(path: str | Path) -> list[ExpertMention]:
    raw = _load_json(path)
    mentions: list[ExpertMention] = []
    for item in raw:
        item = dict(item)
        if item.get("published_on"):
            item["published_on"] = date.fromisoformat(item["published_on"])
        mentions.append(ExpertMention(**item))
    return mentions


def _load_json(path: str | Path) -> Any:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)
