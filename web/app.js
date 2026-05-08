const state = {
  players: [],
  rankings: [],
};

const elements = {
  rankings: document.querySelector("#rankings"),
  status: document.querySelector("#status"),
  scoring: document.querySelector("#scoring"),
  dynasty: document.querySelector("#dynasty"),
  superflex: document.querySelector("#superflex"),
  tePremium: document.querySelector("#tePremium"),
  window: document.querySelector("#window"),
  giveSelect: document.querySelector("#giveSelect"),
  receiveSelect: document.querySelector("#receiveSelect"),
  tradeResult: document.querySelector("#tradeResult"),
};

function payload() {
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
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json();
}

async function loadPlayers() {
  state.players = await fetch("/api/players").then((response) => response.json());
  for (const select of [elements.giveSelect, elements.receiveSelect]) {
    select.innerHTML = "";
    state.players.forEach((player) => {
      const option = document.createElement("option");
      option.value = player.player_id;
      option.textContent = `${player.name} (${player.position})`;
      select.append(option);
    });
  }
}

async function loadRankings() {
  elements.status.textContent = "Loading";
  state.rankings = await postJson("/api/rankings", payload());
  renderRankings();
  elements.status.textContent = `${state.rankings.length} players`;
}

function renderRankings() {
  elements.rankings.innerHTML = "";
  state.rankings.forEach((player, index) => {
    const row = document.createElement("article");
    row.className = "player-row";
    row.innerHTML = `
      <div class="rank">${index + 1}</div>
      <div>
        <div class="player-name">${player.name} <span class="badge">${player.position}</span></div>
        <div class="explain">${player.explanation[0]}</div>
      </div>
      <div class="metric"><span>Value</span><strong>${player.value}</strong></div>
      <div class="metric"><span>Opp</span><strong>${player.opportunity_score}</strong></div>
    `;
    elements.rankings.append(row);
  });
}

function selectedValues(select) {
  return Array.from(select.selectedOptions).map((option) => option.value);
}

async function analyzeTrade() {
  const result = await postJson("/api/trade", {
    ...payload(),
    give: selectedValues(elements.giveSelect),
    receive: selectedValues(elements.receiveSelect),
  });
  elements.tradeResult.innerHTML = `
    <div class="verdict ${result.verdict}">${result.verdict.replace("_", " ")}</div>
    <div>Give value: <strong>${result.side_a_value}</strong></div>
    <div>Receive value: <strong>${result.side_b_value}</strong></div>
    <div>Net: <strong>${result.net_for_a}</strong></div>
    <div>${result.explanation.join(" ")}</div>
  `;
}

document.querySelector("#refreshButton").addEventListener("click", loadRankings);
document.querySelector("#tradeButton").addEventListener("click", analyzeTrade);
document.querySelectorAll("input, select").forEach((field) => {
  field.addEventListener("change", () => {
    if (!field.closest(".trade")) {
      loadRankings();
    }
  });
});

loadPlayers().then(loadRankings).catch((error) => {
  elements.status.textContent = error.message;
});
