from pathlib import Path

from fantasy_value.agents.article_sources import ArticleSourceConfig
from fantasy_value.agents.pipeline import InternetAgentPipeline


def test_agent_pipeline_skips_without_sources(tmp_path: Path):
    pipeline = InternetAgentPipeline(
        players_path=Path("data/sample_players.json"),
        mentions_output_path=tmp_path / "mentions.json",
        source_config=ArticleSourceConfig(),
    )

    result = pipeline.run()

    assert result.status == "skipped"
    assert result.players_seen > 0
    assert result.mentions_found == 0
