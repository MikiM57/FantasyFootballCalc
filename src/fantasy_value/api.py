from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

try:
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.staticfiles import StaticFiles
    from pydantic import BaseModel, Field
except ImportError as exc:  # pragma: no cover - exercised only without API extras installed
    raise RuntimeError(
        "Install API dependencies with: pip install -e \".[api]\""
    ) from exc

from fantasy_value.models import LeagueSettings, RosterContext
from fantasy_value.repository import load_mentions, load_players
from fantasy_value.scoring import ValuationEngine
from fantasy_value.trade import TradeAnalyzer, TradeSide

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
WEB_DIR = ROOT / "web"

app = FastAPI(title="Fantasy Edge AI", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class LeaguePayload(BaseModel):
    scoring: str = "half_ppr"
    dynasty: bool = True
    superflex: bool = False
    tight_end_premium: float = 0.0
    positional_needs: dict[str, float] = Field(default_factory=dict)
    competitive_window: str = "balanced"


class TradePayload(LeaguePayload):
    give: list[str]
    receive: list[str]


def _settings(payload: LeaguePayload) -> LeagueSettings:
    return LeagueSettings(
        scoring=payload.scoring,  # type: ignore[arg-type]
        dynasty=payload.dynasty,
        superflex=payload.superflex,
        tight_end_premium=payload.tight_end_premium,
    )


def _roster(payload: LeaguePayload) -> RosterContext:
    return RosterContext(
        competitive_window=payload.competitive_window,  # type: ignore[arg-type]
        positional_needs=payload.positional_needs,  # type: ignore[arg-type]
    )


def _sample_data():
    return load_players(DATA_DIR / "sample_players.json"), load_mentions(DATA_DIR / "sample_mentions.json")


@app.get("/api/players")
def players():
    sample_players, _ = _sample_data()
    return [asdict(player) for player in sample_players]


@app.post("/api/rankings")
def rankings(payload: LeaguePayload):
    sample_players, mentions = _sample_data()
    values = ValuationEngine().rank_players(
        sample_players,
        mentions,
        _settings(payload),
        _roster(payload),
    )
    return [asdict(value) for value in values]


@app.post("/api/trade")
def trade(payload: TradePayload):
    sample_players, mentions = _sample_data()
    result = TradeAnalyzer().analyze(
        sample_players,
        mentions,
        TradeSide("give", tuple(payload.give)),
        TradeSide("receive", tuple(payload.receive)),
        _settings(payload),
        _roster(payload),
    )
    return asdict(result)


if WEB_DIR.exists():
    app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
