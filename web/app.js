const state = {
  players: [],
  playerById: new Map(),
  rankings: [],
  lastTrade: null,
};

const elements = {
  rankings: document.querySelector("#rankings"),
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
  agentRunButton: document.querySelector("#agentRunButton"),
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
  select.addEventListener("change", analyzeTrade);
  wrapper.append(select);
  return wrapper;
}

async function loadRankings() {
  elements.status.textContent = "Refreshing";
  state.rankings = await postJson("/api/rankings", leaguePayload());
  renderRankings();
  elements.status.textContent = "Ready";
  elements.rankingCount.textContent = `${state.rankings.length} players`;
}

function renderRankings() {
  elements.rankings.innerHTML = "";
  state.rankings.forEach((player, index) => {
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
        <div class="explain">${player.explanation[0]}</div>
      </div>
      ${metric("Value", player.value)}
      ${metric("Avg", player.average_points)}
      ${metric("ROS", player.rest_of_season_points)}
      ${metric("Sched", player.strength_of_schedule)}
      ${metric("Expert", player.expert_favorability)}
    `;
    elements.rankings.append(row);
  });
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
  const result = await postJson("/api/trade", {
    ...leaguePayload(),
    give,
    receive,
  });
  state.lastTrade = result;
  renderTrade(result);
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
  return `<div class="metric"><span>${label}</span><strong>${display}</strong></div>`;
}

async function loadAgentStatus() {
  const status = await fetch("/api/agent/status").then((response) => response.json());
  elements.agentState.textContent = status.is_running
    ? "Running"
    : status.daily_enabled
      ? "Scheduled"
      : "Manual";
  const lastRun = status.last_run;
  elements.agentMetrics.innerHTML = `
    ${metric("Feeds", status.rss_feeds)}
    ${metric("URLs", status.article_urls)}
    ${metric("Sources", status.sources_configured ? "Ready" : "Sample")}
    ${metric("Last", lastRun ? lastRun.status : "None")}
  `;
}

async function runAgents() {
  elements.agentState.textContent = "Queued";
  await postJson("/api/agent/run", {});
  setTimeout(loadAgentStatus, 1200);
}

async function refreshAll() {
  await Promise.all([loadRankings(), loadAgentStatus()]);
  await analyzeTrade();
}

document.querySelector("#refreshButton").addEventListener("click", refreshAll);
document.querySelector("#tradeButton").addEventListener("click", analyzeTrade);
elements.agentRunButton.addEventListener("click", runAgents);
document.querySelectorAll(".controls input, .controls select").forEach((field) => {
  field.addEventListener("change", refreshAll);
});

loadPlayers()
  .then(refreshAll)
  .catch((error) => {
    elements.status.textContent = error.message;
  });
