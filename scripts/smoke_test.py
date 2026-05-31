from __future__ import annotations

import argparse
import json
import time
from urllib.error import URLError
from urllib.request import Request, urlopen


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    wait_for_server(base_url)

    health = get_json(f"{base_url}/api/health")
    assert health["status"] == "ok"
    assert health["web_dir_exists"] is True
    assert health["data_dir_exists"] is True

    players = get_json(f"{base_url}/api/players")
    assert players, "Expected /api/players to return sample players."

    rankings = post_json(
        f"{base_url}/api/rankings",
        {
            "scoring": "half_ppr",
            "dynasty": True,
            "superflex": True,
            "tight_end_premium": 0.5,
            "competitive_window": "balanced",
            "positional_needs": {"QB": 0.5, "RB": 0.0, "WR": 0.25, "TE": 0.0},
        },
    )
    assert rankings, "Expected /api/rankings to return ranked players."
    assert "value" in rankings[0], "Expected rankings to include player values."
    assert "explanation" in rankings[0], "Expected rankings to include explanations."

    sleepers = post_json(
        f"{base_url}/api/sleepers",
        {
            "scoring": "half_ppr",
            "dynasty": True,
            "superflex": False,
            "tight_end_premium": 0.0,
            "competitive_window": "balanced",
            "positional_needs": {},
        },
    )
    assert sleepers, "Expected /api/sleepers to return next-year sleeper candidates."
    assert "sleeper_score" in sleepers[0]

    trade = post_json(
        f"{base_url}/api/trade",
        {
            "scoring": "half_ppr",
            "dynasty": True,
            "superflex": False,
            "tight_end_premium": 0.0,
            "competitive_window": "rebuilder",
            "positional_needs": {"WR": 0.5},
            "give": ["derrick-henry"],
            "receive": ["drake-london"],
        },
    )
    assert trade["verdict"] in {
        "accept",
        "lean_accept",
        "fair",
        "lean_decline",
        "decline",
    }
    assert "net_for_a" in trade
    assert "side_a_summary" in trade
    assert "expert_favorability" in trade["side_b_summary"]

    agent_status = get_json(f"{base_url}/api/agent/status")
    assert "daily_enabled" in agent_status

    html = get_text(f"{base_url}/")
    assert "FantasyFootballCalc" in html

    print("Full program smoke test passed.")


def wait_for_server(base_url: str, timeout_seconds: float = 15.0) -> None:
    deadline = time.time() + timeout_seconds
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            get_json(f"{base_url}/api/players")
            return
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            time.sleep(0.5)
    raise RuntimeError(f"Server did not become ready: {last_error}")


def get_json(url: str):
    with urlopen(url, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def get_text(url: str) -> str:
    with urlopen(url, timeout=5) as response:
        return response.read().decode("utf-8")


def post_json(url: str, payload: dict):
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))
    except URLError as exc:
        raise RuntimeError(f"POST failed for {url}: {exc}") from exc


if __name__ == "__main__":
    main()
