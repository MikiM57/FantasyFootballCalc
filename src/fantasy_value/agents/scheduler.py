from __future__ import annotations

import threading
from dataclasses import dataclass

from fantasy_value.agents.pipeline import AgentRunSummary, InternetAgentPipeline


@dataclass
class DailyAgentScheduler:
    pipeline: InternetAgentPipeline
    interval_seconds: int = 86_400
    run_on_start: bool = True

    def __post_init__(self) -> None:
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self.last_run: AgentRunSummary | None = None
        self.is_running = False

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._loop, name="daily-agent-scheduler", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def run_once(self) -> AgentRunSummary:
        with self._lock:
            self.is_running = True
            try:
                self.last_run = self.pipeline.run()
                return self.last_run
            finally:
                self.is_running = False

    def status(self) -> dict[str, object]:
        return {
            "enabled": self._thread is not None,
            "is_running": self.is_running,
            "interval_seconds": self.interval_seconds,
            "last_run": self.last_run.to_dict() if self.last_run else None,
        }

    def _loop(self) -> None:
        if self.run_on_start:
            self.run_once()
        while not self._stop.wait(self.interval_seconds):
            self.run_once()
