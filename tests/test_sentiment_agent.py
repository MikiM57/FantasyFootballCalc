from fantasy_value.agents.sentiment_agent import Article, ExpertSentimentAgent
from fantasy_value.repository import load_players


def test_sentiment_agent_extracts_positive_player_mention():
    players = load_players("data/sample_players.json")
    agent = ExpertSentimentAgent(players)

    mentions = agent.analyze_article(
        Article(
            source="test",
            title="Dynasty buys",
            body="Drake London is an ascending breakout target with volume and upside.",
        )
    )

    london = next(mention for mention in mentions if mention.player_id == "drake-london")
    assert london.sentiment > 0
    assert london.magnitude > 0.25
