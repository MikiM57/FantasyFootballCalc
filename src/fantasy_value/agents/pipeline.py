from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from fantasy_value.agents.online_stats_agent import OnlineNflStatsAgent, OnlineStatsRunSummary
from fantasy_value.agents.article_sources import ArticleSourceConfig, load_articles
from fantasy_value.agents.sentiment_agent import ExpertSentimentAgent
from fantasy_value.repository import load_players, save_mentions


@dataclass(frozen=True)
class AgentRunSummary:
    status: str
    started_at: str
    finished_at: str | None
    players_seen: int
    articles_seen: int
    mentions_found: int
    stats_status: str | None
    stats_players_written: int
    output_path: str | None
    message: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class InternetAgentPipeline:
    players_path: Path
    mentions_output_path: Path
    source_config: ArticleSourceConfig
    stats_agent: OnlineNflStatsAgent | None = None
    fallback_players_path: Path | None = None

    def run(self) -> AgentRunSummary:
        started_at = _now()
        stats_summary = self._refresh_stats()
        players_path = self.players_path if self.players_path.exists() else self.fallback_players_path
        if not players_path:
            players_path = self.players_path
        players = load_players(players_path)
        if not self.source_config.rss_feeds and not self.source_config.article_urls:
            return AgentRunSummary(
                status="skipped",
                started_at=started_at,
                finished_at=_now(),
                players_seen=len(players),
                articles_seen=0,
                mentions_found=0,
                stats_status=stats_summary.status if stats_summary else None,
                stats_players_written=stats_summary.players_written if stats_summary else 0,
                output_path=None,
                message=(
                    "No ARTICLE_FEEDS or ARTICLE_URLS are configured. "
                    "The site will keep using bundled sample sentiment."
                ),
            )

        try:
            articles = load_articles(self.source_config)
            mentions = ExpertSentimentAgent(players).aggregate(articles)
            save_mentions(self.mentions_output_path, mentions)
            return AgentRunSummary(
                status="complete",
                started_at=started_at,
                finished_at=_now(),
                players_seen=len(players),
                articles_seen=len(articles),
                mentions_found=len(mentions),
                stats_status=stats_summary.status if stats_summary else None,
                stats_players_written=stats_summary.players_written if stats_summary else 0,
                output_path=str(self.mentions_output_path),
                message="Expert sentiment refreshed from configured sources.",
            )
        except Exception as exc:  # noqa: BLE001
            return AgentRunSummary(
                status="failed",
                started_at=started_at,
                finished_at=_now(),
                players_seen=len(players),
                articles_seen=0,
                mentions_found=0,
                stats_status=stats_summary.status if stats_summary else None,
                stats_players_written=stats_summary.players_written if stats_summary else 0,
                output_path=None,
                message=f"Agent refresh failed: {exc}",
            )

    def _refresh_stats(self) -> OnlineStatsRunSummary | None:
        if not self.stats_agent:
            return None
        return self.stats_agent.run()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
