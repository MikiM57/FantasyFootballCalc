# FantasyFootballCalc

FantasyFootballCalc is a repo-ready starter for a fantasy football valuation platform. It combines statistical player signals, expert/article sentiment, league settings, and roster context to rank players and evaluate trades.

The goal is to improve on simple trade calculators by separating:

- player quality
- fantasy production
- market sentiment
- dynasty value
- roster utility
- trade context

## What is included

- A dependency-light Python valuation engine in `src/fantasy_value`
- Agent-style ingestion modules for stats and expert sentiment
- A trade analyzer that accounts for roster needs and league format
- Trade packages with up to 5 players on each side
- Player metrics for value, average points, projected points, schedule, trend, risk, and expert favorability
- A FastAPI app with static web UI
- Sample player and article-sentiment data
- Unit tests for the core scoring behavior
- GitHub Actions CI that runs tests, CLI checks, and a live API/web smoke test
- Docker and GitHub Codespaces support

## What The GitHub Run Means

When the GitHub Actions `CI` workflow is green, the app has been tested. It means GitHub successfully installed the project, ran the unit tests, ran the command-line rankings/trade checks, started the web server, called the API, and confirmed the web UI loads.

That is not the same as hosting the site. GitHub Actions runs the program temporarily and then shuts it down. To actually use it in a browser, run it locally, open it in Codespaces, or deploy it to a hosting service.

## AI Agents

The repo now has a daily agent pipeline. When live, set these environment variables on your host:

```text
ENABLE_DAILY_AGENTS=true
RUN_AGENTS_ON_START=true
ARTICLE_FEEDS=https://example.com/fantasy-football/rss
ARTICLE_URLS=
ALLOW_ARTICLE_BODY_FETCH=false
```

The agents run once per day by default. They read configured RSS feeds or article URLs, extract player mentions, score expert favorability, and save the latest generated sentiment to `data/runtime/latest_mentions.json`.

Use only approved feeds, public APIs, licensed data, RSS metadata, or sources you are allowed to access. The app is built to support internet ingestion, but it should not blindly scrape sites that prohibit automated access.

## Quick Start

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev,api]"
pytest
uvicorn fantasy_value.api:app --reload
```

Then open `http://127.0.0.1:8000`.

If the deployed site shows JSON like `{"detail":"Not Found"}`, open `/api/health` on the same URL. It should report that the `web` and `data` directories exist.

## Use It In GitHub Codespaces

This is the easiest way to test it without setting up Python on your computer:

1. Open `https://github.com/MikiM57/FantasyFootballCalc`.
2. Select **Code**.
3. Select **Codespaces**.
4. Create a codespace.
5. Wait for dependencies to install.
6. Run:

```bash
uvicorn fantasy_value.api:app --host 0.0.0.0 --port 8000
```

When Codespaces shows port `8000`, open it in the browser. You should see rankings, league controls, and the trade analyzer.

## Run From GitHub

After pushing this repo to GitHub, open the **Actions** tab and run the `CI` workflow. The workflow installs the project, runs lint/tests, checks the CLI, starts the FastAPI server, calls the API endpoints, and verifies the static web app loads.

You can also use GitHub Codespaces:

1. Open the repo on GitHub.
2. Select **Code**.
3. Select **Codespaces**.
4. Create a codespace.
5. Run:

```bash
uvicorn fantasy_value.api:app --host 0.0.0.0 --port 8000
```

Codespaces will forward port `8000` so the site can open in your browser.

For container runs:

```bash
docker compose up --build
```

## Deploy As A Public Website

The app is ready to deploy as a small FastAPI website. A simple path is Render:

1. Create a Render account.
2. Select **New**.
3. Select **Blueprint**.
4. Connect `MikiM57/FantasyFootballCalc`.
5. Render will read `render.yaml`.
6. Deploy.

After deployment, Render gives you a public URL. That URL is the actual website.

If you only want to test the core engine without installing API dependencies:

```powershell
python -m unittest discover -s tests
python -m fantasy_value.cli rank --players data/sample_players.json --mentions data/sample_mentions.json
python -m fantasy_value.cli agents --players data/sample_players.json --output data/runtime/latest_mentions.json
```

## Repo Layout

```text
.
|-- data/
|   |-- sample_mentions.json
|   `-- sample_players.json
|-- src/
|   `-- fantasy_value/
|       |-- agents/
|       |   |-- sentiment_agent.py
|       |   `-- stats_agent.py
|       |-- api.py
|       |-- cli.py
|       |-- models.py
|       |-- repository.py
|       |-- scoring.py
|       `-- trade.py
|-- scripts/
|   `-- smoke_test.py
|-- tests/
|-- web/
|-- docs/
|-- Dockerfile
|-- docker-compose.yml
|-- render.yaml
`-- pyproject.toml
```

## Data Strategy

The project is designed around provider interfaces instead of hard-coded scraping. That matters because ESPN, paid fantasy sites, and many article publishers have terms of service that restrict automated scraping. For production, prefer:

- official APIs
- licensed feeds
- public datasets such as nflverse
- RSS feeds and article metadata where allowed
- user-provided exports

The included agents show where to plug in approved sources.

## Scoring Model

The first scoring model is intentionally transparent:

```text
base value =
  production
+ opportunity
+ efficiency
+ team context
+ expert sentiment
+ market signal
+ age curve
- injury risk
- role uncertainty
```

League settings modify the weights. Dynasty leagues emphasize age and future value. Superflex boosts quarterbacks. TE premium boosts tight ends with strong target roles. Roster context then shifts values based on team need and competitive window.

This is meant to be a strong baseline before adding a trained model.

## AI Roadmap

Good next steps:

1. Add real data providers for player stats, injuries, depth charts, and projections.
2. Add an LLM sentiment extractor that returns structured evidence from approved article text.
3. Store historical snapshots in Postgres.
4. Train a model against historical fantasy outcomes and market movement.
5. Add authentication, saved leagues, and user rosters.
6. Add trade search: find likely acceptable trades based on both sides' needs.

## Environment

Copy `.env.example` to `.env` when you add real providers.

```text
OPENAI_API_KEY=
STATS_PROVIDER=
ARTICLE_FEEDS=
```

## License

MIT
