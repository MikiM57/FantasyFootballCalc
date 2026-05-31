from __future__ import annotations

import os
from dataclasses import asdict
from pathlib import Path

try:
    from fastapi import BackgroundTasks, FastAPI, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.staticfiles import StaticFiles
    from pydantic import BaseModel, Field
except ImportError as exc:  # pragma: no cover - exercised only without API extras installed
    raise RuntimeError(
        "Install API dependencies with: pip install -e \".[api]\""
    ) from exc

from fantasy_value.models import LeagueSettings, RosterContext
from fantasy_value.agents.article_sources import source_config_from_env
from fantasy_value.agents.pipeline import InternetAgentPipeline
from fantasy_value.agents.scheduler import DailyAgentScheduler
from fantasy_value.repository import load_mentions, load_players
from fantasy_value.scoring import ValuationEngine
from fantasy_value.trade import TradeAnalyzer, TradeSide

def _find_project_root() -> Path:
    candidates = [
        Path(os.environ["PROJECT_ROOT"]).resolve() if os.environ.get("PROJECT_ROOT") else None,
        Path.cwd().resolve(),
        Path(__file__).resolve().parents[2],
    ]
    for candidate in candidates:
        if candidate and (candidate / "web").exists() and (candidate / "data").exists():
            return candidate
    return Path.cwd().resolve()


ROOT = _find_project_root()
DATA_DIR = ROOT / "data"
WEB_DIR = ROOT / "web"
RUNTIME_DIR = DATA_DIR / "runtime"
RUNTIME_MENTIONS_PATH = RUNTIME_DIR / "latest_mentions.json"
SAMPLE_PLAYERS_PATH = DATA_DIR / "sample_players.json"
SAMPLE_MENTIONS_PATH = DATA_DIR / "sample_mentions.json"

app = FastAPI(title="FantasyFootballCalc", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_source_config = source_config_from_env(dict(os.environ))
_agent_pipeline = InternetAgentPipeline(
    players_path=SAMPLE_PLAYERS_PATH,
    mentions_output_path=RUNTIME_MENTIONS_PATH,
    source_config=_source_config,
)
_scheduler = DailyAgentScheduler(
    pipeline=_agent_pipeline,
    interval_seconds=int(os.environ.get("AGENT_INTERVAL_SECONDS", "86400")),
    run_on_start=os.environ.get("RUN_AGENTS_ON_START", "").lower() == "true",
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


def _current_data():
    mentions_path = RUNTIME_MENTIONS_PATH if RUNTIME_MENTIONS_PATH.exists() else SAMPLE_MENTIONS_PATH
    return load_players(SAMPLE_PLAYERS_PATH), load_mentions(mentions_path)


@app.on_event("startup")
def start_daily_agents() -> None:
    if os.environ.get("ENABLE_DAILY_AGENTS", "").lower() == "true":
        _scheduler.start()


@app.on_event("shutdown")
def stop_daily_agents() -> None:
    _scheduler.stop()


@app.get("/api/players")
def players():
    sample_players, _ = _current_data()
    return [asdict(player) for player in sample_players]


@app.post("/api/rankings")
def rankings(payload: LeaguePayload):
    sample_players, mentions = _current_data()
    values = ValuationEngine().rank_players(
        sample_players,
        mentions,
        _settings(payload),
        _roster(payload),
    )
    return [asdict(value) for value in values]


@app.post("/api/trade")
def trade(payload: TradePayload):
    if len(payload.give) > 5 or len(payload.receive) > 5:
        raise HTTPException(status_code=400, detail="Trades support up to 5 players on each side.")
    sample_players, mentions = _current_data()
    result = TradeAnalyzer().analyze(
        sample_players,
        mentions,
        TradeSide("give", tuple(payload.give)),
        TradeSide("receive", tuple(payload.receive)),
        _settings(payload),
        _roster(payload),
    )
    return asdict(result)


@app.get("/api/agent/status")
def agent_status():
    return {
        **_scheduler.status(),
        "daily_enabled": os.environ.get("ENABLE_DAILY_AGENTS", "").lower() == "true",
        "manual_run_enabled": os.environ.get("ALLOW_AGENT_MANUAL_RUN", "true").lower() == "true",
        "sources_configured": bool(_source_config.rss_feeds or _source_config.article_urls),
        "rss_feeds": len(_source_config.rss_feeds),
        "article_urls": len(_source_config.article_urls),
    }


@app.post("/api/agent/run")
def run_agent(background_tasks: BackgroundTasks):
    if os.environ.get("ALLOW_AGENT_MANUAL_RUN", "true").lower() != "true":
        raise HTTPException(status_code=403, detail="Manual agent runs are disabled.")
    background_tasks.add_task(_scheduler.run_once)
    return {"status": "queued", "message": "Agent refresh queued."}


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "root": str(ROOT),
        "web_dir_exists": WEB_DIR.exists(),
        "data_dir_exists": DATA_DIR.exists(),
    }


app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
