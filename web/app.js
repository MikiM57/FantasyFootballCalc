const state = {
  players: [],
  playerById: new Map(),
  rankings: [],
  sleepers: [],
  lastTrade: null,
  activeRankingMode: "overall",
  activePosition: "ALL",
};

const elements = {
  rankings: document.querySelector("#rankings"),
  rankingModeTabs: document.querySelector("#rankingModeTabs"),
  positionTabs: document.querySelector("#positionTabs"),
  status: document.querySelector("#status"),
  rankingCount: document.querySelector("#rankingCount"),
  scoring: document.querySelector("#scoring"),
  dynasty: document.querySelector("#dynasty"),
  superflex: document.querySelector("#superflex"),
  tePremium: document.querySelector("#tePremium"),
  window: document.querySelector("#window"),
  giveSlots: document.querySelector("#giveSlots"),
  receiveSlots: document.querySelector("#receiveSlots"),
  giveSummary: document.querySelector("#giveSummary"),
  receiveSummary: document.querySelector("#receiveSummary"),
  tradeVerdict: document.querySelector("#tradeVerdict"),
  giveValue: document.querySelector("#giveValue"),
  receiveValue: document.querySelector("#receiveValue"),
  netValue: document.querySelector("#netValue"),
  tradeNotes: document.querySelector("#tradeNotes"),
  agentState: document.querySelector("#agentState"),
  agentMetrics: document.querySelector("#agentMetrics"),
};

let tradeTimer = null;

const metricTooltips = {
  Value:
    "0-100 player value score combining production, opportunity, efficiency, team context, age, market, schedule, expert favorability, and risk.",
  Avg: "Average fantasy points per game from available weekly production.",
  ROS: "Rest-of-season projected fantasy points based on average points and remaining games.",
  Sched:
    "0-100 rest-of-season matchup score. Around 50 is neutral, 65+ is favorable, below 40 is difficult.",
  Expert:
    "0-100 favorability from configured fantasy article and RSS sources. Around 50 is neutral, 65+ is positive, below 40 is cautious.",
  Package:
    "Total trade-side value after depth, consolidation, format, and roster-context adjustments.",
  "Avg PPG": "Average fantasy points per game for players in this package.",
  "ROS Pts": "Combined rest-of-season projected fantasy points for this package.",
  Schedule:
    "Average 0-100 rest-of-season schedule score for players in this package. Higher means easier matchups.",
  Risk:
    "0-100 injury and role uncertainty penalty. Lower is safer; higher means more downside.",
  Feeds: "Number of RSS feeds configured for expert sentiment ingestion.",
  URLs: "Number of direct article URLs configured for expert sentiment ingestion.",
  Stats: "Online player-stat ingestion status from the background agent.",
  Sources: "Whether expert article/RSS sources are configured or the app is using sample sentiment.",
  Last: "Most recent background agent run status.",
  Train:
    "Season used for the latest model calibration. The app uses the newest nflverse season it can load.",
  Sleeper:
    "0-100 next-year breakout score based on youth, role growth, efficiency, trend, value gap, and risk.",
  Gap:
    "Model value minus market score. A positive gap means the model thinks the player is undervalued.",
  Trend: "0-100 recent production momentum score. Higher means the player's recent output is improving.",
  Opp: "0-100 opportunity score from touches, targets, routes, snaps, and high-value usage.",
};

function leaguePayload() {
  const positional_needs = {};
  document.querySelectorAll("[data-need]").forEach((input) => {
    positional_needs[input.dataset.need] = Number(input.value);
  });
  return {
    scoring: elements.scoring.value,
    dynasty: elements.dynasty.checked,
    superflex: elements.superflex.checked,
    tight_end_premium: Number(elements.tePremium.value),
    competitive_window: elements.window.value,
    positional_needs,
  };
}

async function postJson(url, body) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed: ${response.status}`);
  }
  return response.json();
}

async function loadPlayers() {
  state.players = await fetch("/api/players").then((response) => response.json());
  state.playerById = new Map(state.players.map((player) => [player.player_id, player]));
  renderTradeSlots();
}

function renderTradeSlots() {
  elements.giveSlots.innerHTML = "";
  elements.receiveSlots.innerHTML = "";
  for (let index = 0; index < 5; index += 1) {
    elements.giveSlots.append(createPlayerSelect("give", index));
    elements.receiveSlots.append(createPlayerSelect("receive", index));
  }
}

function createPlayerSelect(side, index) {
  const wrapper = document.createElement("label");
  wrapper.className = "slot";
  wrapper.innerHTML = `<span>${side === "give" ? "Outgoing" : "Incoming"} ${index + 1}</span>`;
  const select = document.createElement("select");
  select.dataset.side = side;
  select.innerHTML = `<option value="">Empty slot</option>`;
  state.players.forEach((player) => {
    const option = document.createElement("option");
    option.value = player.player_id;
    option.textContent = `${player.name} - ${player.position} ${player.team}`;
    select.append(option);
  });
  select.addEventListener("change", scheduleTradeAnalysis);
  wrapper.append(select);
  return wrapper;
}

async function loadRankings() {
  elements.status.textContent = "Refreshing";
  const payload = leaguePayload();
  try {
    state.rankings = await postJson("/api/rankings", payload);
    renderRankings();
  } catch (error) {
    state.rankings = [];
    renderRankingError(`Could not load overall rankings: ${error.message}`);
  }
  try {
    state.sleepers = await postJson("/api/sleepers", payload);
  } catch (error) {
    state.sleepers = [];
    if (state.activeRankingMode === "sleepers") {
      renderRankingError(`Could not load sleeper rankings: ${error.message}`);
    }
  }
  renderRankings();
  elements.status.textContent = "Ready";
}

function renderRankings() {
  elements.rankings.innerHTML = "";
  const source = state.activeRankingMode === "sleepers" ? state.sleepers : state.rankings;
  const positions = state.activePosition === "ALL" ? ["QB", "RB", "WR", "TE"] : [state.activePosition];
  let shown = 0;
  positions.forEach((position) => {
    const players = source.filter((player) => player.position === position);
    if (!players.length) {
      return;
    }
    elements.rankings.append(positionHeader(position, players.length));
    players.forEach((player, index) => {
      elements.rankings.append(
        state.activeRankingMode === "sleepers" ? sleeperRow(player, index) : playerRow(player, index),
      );
      shown += 1;
    });
  });
  if (!shown) {
    const label = state.activeRankingMode === "sleepers" ? "sleeper candidates" : "ranked players";
    renderRankingError(`No ${label} available for this position yet.`);
  }
  elements.rankingCount.textContent = `${shown} players`;
}

function renderRankingError(message) {
  elements.rankings.innerHTML = `<div class="empty-state">${message}</div>`;
  elements.rankingCount.textContent = "0 players";
}

function positionHeader(position, count) {
  const header = document.createElement("div");
  header.className = "position-header";
  header.innerHTML = `<strong>${position}</strong><span>${count} ranked</span>`;
  return header;
}

function playerRow(player, index) {
  const row = document.createElement("article");
  row.className = "player-row";
  row.innerHTML = `
      <div class="rank">${index + 1}</div>
      <div class="player-main">
        <div class="player-name">
          ${player.name}
          <span class="badge">${player.position}</span>
          <span class="team">${player.team}</span>
        </div>
        <div class="value-bar" aria-hidden="true"><span style="width: ${barWidth(player.value)}%"></span></div>
        <div class="explain">${player.explanation[0]}</div>
      </div>
      ${metric("Value", player.value)}
      ${metric("Avg", player.average_points)}
      ${metric("ROS", player.rest_of_season_points)}
      ${metric("Sched", player.strength_of_schedule)}
      ${metric("Expert", player.expert_favorability)}
    `;
  return row;
}

function sleeperRow(player, index) {
  const row = document.createElement("article");
  row.className = "player-row sleeper-row";
  row.innerHTML = `
      <div class="rank">${index + 1}</div>
      <div class="player-main">
        <div class="player-name">
          ${player.name}
          <span class="badge">${player.position}</span>
          <span class="team">${player.team}</span>
        </div>
        <div class="value-bar sleeper-bar" aria-hidden="true"><span style="width: ${barWidth(player.sleeper_score)}%"></span></div>
        <div class="explain">${player.explanation[0]}</div>
      </div>
      ${metric("Sleeper", player.sleeper_score)}
      ${metric("Value", player.current_value)}
      ${metric("Gap", player.value_gap)}
      ${metric("Trend", player.trend_score)}
      ${metric("Opp", player.opportunity_score)}
    `;
  return row;
}

function barWidth(value) {
  return Math.max(4, Math.min(100, Number(value) || 0));
}

function selectedValues(side) {
  const values = Array.from(document.querySelectorAll(`select[data-side="${side}"]`))
    .map((select) => select.value)
    .filter(Boolean);
  return Array.from(new Set(values)).slice(0, 5);
}

async function analyzeTrade() {
  const give = selectedValues("give");
  const receive = selectedValues("receive");
  if (!give.length && !receive.length) {
    renderEmptyTrade();
    return;
  }
  try {
    const result = await postJson("/api/trade", {
      ...leaguePayload(),
      give,
      receive,
    });
    state.lastTrade = result;
    renderTrade(result);
  } catch (error) {
    elements.tradeNotes.innerHTML = `<p>${error.message}</p>`;
  }
}

function scheduleTradeAnalysis() {
  window.clearTimeout(tradeTimer);
  tradeTimer = window.setTimeout(analyzeTrade, 180);
}

function renderTrade(result) {
  elements.tradeVerdict.textContent = result.verdict.replace("_", " ");
  elements.tradeVerdict.className = result.verdict;
  elements.giveValue.textContent = result.side_a_value.toFixed(1);
  elements.receiveValue.textContent = result.side_b_value.toFixed(1);
  elements.netValue.textContent = result.net_for_a.toFixed(1);
  elements.tradeNotes.innerHTML = result.explanation.map((note) => `<p>${note}</p>`).join("");
  elements.giveSummary.innerHTML = renderSummary(result.side_a_summary);
  elements.receiveSummary.innerHTML = renderSummary(result.side_b_summary);
}

function renderEmptyTrade() {
  elements.tradeVerdict.textContent = "Select players";
  elements.tradeVerdict.className = "";
  elements.giveValue.textContent = "0.0";
  elements.receiveValue.textContent = "0.0";
  elements.netValue.textContent = "0.0";
  elements.tradeNotes.innerHTML = "";
  elements.giveSummary.innerHTML = "";
  elements.receiveSummary.innerHTML = "";
}

function renderSummary(summary) {
  return `
    ${metric("Package", summary.total_value)}
    ${metric("Avg PPG", summary.average_points)}
    ${metric("ROS Pts", summary.rest_of_season_points)}
    ${metric("Schedule", summary.average_strength_of_schedule)}
    ${metric("Expert", summary.expert_favorability)}
    ${metric("Risk", summary.average_risk)}
  `;
}

function metric(label, value) {
  const display = typeof value === "number" ? value.toFixed(value >= 100 ? 0 : 1) : value;
  const tooltip = metricTooltips[label] || "FantasyFootballCalc metric.";
  return `
    <div class="metric has-tooltip" tabindex="0" data-tooltip="${escapeAttr(tooltip)}">
      <span>${label}</span>
      <strong>${display}</strong>
    </div>
  `;
}

function escapeAttr(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll('"', "&quot;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

async function loadAgentStatus() {
  const status = await fetch("/api/agent/status").then((response) => response.json());
  elements.agentState.textContent = status.is_running
    ? "Running"
    : status.daily_enabled
      ? "Scheduled"
      : "Off";
  const lastRun = status.last_run;
  elements.agentMetrics.innerHTML = `
    ${metric("Feeds", status.rss_feeds)}
    ${metric("URLs", status.article_urls)}
    ${metric("Stats", lastRun?.stats_status || (status.online_stats_enabled ? "On" : "Off"))}
    ${metric("Train", status.trained_seasons?.join(", ") || "None")}
    ${metric("Sources", status.sources_configured ? "Ready" : "Sample")}
    ${metric("Last", lastRun ? lastRun.status : "None")}
  `;
}

async function refreshAll() {
  await Promise.all([loadRankings(), loadAgentStatus()]);
  await analyzeTrade();
}

document.querySelector("#refreshButton").addEventListener("click", refreshAll);
elements.rankingModeTabs.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-mode]");
  if (!button) {
    return;
  }
  state.activeRankingMode = button.dataset.mode;
  elements.rankingModeTabs.querySelectorAll("button").forEach((item) => {
    item.classList.toggle("active", item === button);
  });
  renderRankings();
});
elements.positionTabs.addEventListener("click", (event) => {
  const button = event.target.closest("button[data-position]");
  if (!button) {
    return;
  }
  state.activePosition = button.dataset.position;
  elements.positionTabs.querySelectorAll("button").forEach((item) => {
    item.classList.toggle("active", item === button);
  });
  renderRankings();
});
document.querySelectorAll(".controls input, .controls select").forEach((field) => {
  field.addEventListener("change", refreshAll);
});

loadPlayers()
  .then(refreshAll)
  .catch((error) => {
    elements.status.textContent = error.message;
  });
