# Making FantasyFootballCalc Real

## What You Have Now

The current app is a working prototype:

- Rankings page
- League setting controls
- Trade analyzer with up to 5 players per side
- Package metrics for average points, projected rest-of-season points, schedule, expert favorability, and risk
- Daily agent scheduler hooks
- Sample player data
- Sample expert sentiment data
- Scoring engine
- GitHub Actions test run
- Docker/Codespaces/Render deployment support

GitHub Actions proves the code runs. It is the test machine, not the public website.

## How To Use It Today

Use Codespaces if your computer does not have Python installed:

```bash
uvicorn fantasy_value.api:app --host 0.0.0.0 --port 8000
```

Then open the forwarded `8000` port.

Use Docker if you have Docker Desktop:

```bash
docker compose up --build
```

Then open `http://127.0.0.1:8000`.

## How To Make It A Public Website

Deploy the repo to Render, Railway, Fly.io, Azure, AWS, or another host that can run a Python web server. This repo includes `render.yaml`, so Render is the easiest starting point.

After deployment, the host gives you a public URL. That is the real website link.

## Adding Real Data

Use automatic online stats first:

```text
STATS_PROVIDER=online
ENABLE_ONLINE_STATS=true
RUN_AGENTS_ON_START=true
ENABLE_DAILY_AGENTS=true
ONLINE_PLAYER_LIMIT=250
```

This pulls player metadata from Sleeper and weekly production from nflverse, then writes `data/runtime/latest_players.json`.

It also pulls prior nflverse seasons to create `data/runtime/calibration.json`. That calibration file sets position-specific replacement levels, starter baselines, elite thresholds, and QB scarcity multipliers from historical data.

The public website should not expose a button that runs agents. Agents are background jobs: they run on startup/deploy and then on the daily scheduler while the service is awake.

For a quick prototype on Render, use secret files:

```text
players.json
mentions.json
```

Render mounts those files at `/etc/secrets/players.json` and `/etc/secrets/mentions.json`, and the app automatically uses them when present. The files must match the sample JSON structure in `data/sample_players.json` and `data/sample_mentions.json`.

For production, do not maintain all stats by hand in Render secret files. Use a database plus scheduled ingestion from approved APIs or public/licensed feeds.

## How To Make It More Like FantasyCalc

The next product milestones are:

1. Replace sample data with real provider data.
2. Store daily value snapshots in a database.
3. Add pages for player profiles and value history.
4. Add league import from Sleeper first because it has a friendly public API.
5. Configure expert sentiment ingestion from allowed RSS feeds and licensed/public article sources.
6. Add user accounts and saved leagues.
7. Add market values from real trades if you have a lawful source for that data.

Avoid scraping websites that prohibit it. Use public APIs, licensed providers, RSS metadata, and user-authorized league exports.
