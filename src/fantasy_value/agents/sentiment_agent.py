from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from html.parser import HTMLParser
from urllib.request import Request, urlopen

from fantasy_value.models import ExpertMention, PlayerStats

POSITIVE_TERMS = {
    "breakout": 0.9,
    "buy": 0.7,
    "ascending": 0.65,
    "undervalued": 0.65,
    "target": 0.55,
    "elite": 0.9,
    "workhorse": 0.8,
    "locked": 0.55,
    "upside": 0.55,
    "efficient": 0.45,
    "volume": 0.45,
}

NEGATIVE_TERMS = {
    "sell": -0.75,
    "avoid": -0.8,
    "overvalued": -0.7,
    "committee": -0.5,
    "injury": -0.45,
    "volatile": -0.4,
    "decline": -0.65,
    "risk": -0.45,
    "limited": -0.5,
    "fade": -0.75,
}


@dataclass(frozen=True)
class Article:
    source: str
    title: str
    body: str
    url: str | None = None
    published_on: date | None = None


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript"}:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            clean = " ".join(data.split())
            if clean:
                self._chunks.append(clean)

    @property
    def text(self) -> str:
        return " ".join(self._chunks)


def fetch_article_text(url: str, timeout: float = 10.0) -> str:
    request = Request(url, headers={"User-Agent": "FantasyEdgeAI/0.1 research prototype"})
    with urlopen(request, timeout=timeout) as response:
        html = response.read().decode("utf-8", errors="replace")
    parser = TextExtractor()
    parser.feed(html)
    return parser.text


@dataclass
class ExpertSentimentAgent:
    players: list[PlayerStats]

    def analyze_article(self, article: Article) -> list[ExpertMention]:
        text = f"{article.title}. {article.body}"
        mentions: list[ExpertMention] = []
        for player in self.players:
            windows = self._windows_for_player(text, player.name)
            if not windows:
                continue
            sentiment, magnitude, reason = self._score_windows(windows)
            mentions.append(
                ExpertMention(
                    player_id=player.player_id,
                    player_name=player.name,
                    source=article.source,
                    url=article.url,
                    published_on=article.published_on,
                    sentiment=sentiment,
                    magnitude=magnitude,
                    confidence=min(0.95, 0.45 + len(windows) * 0.12),
                    context=self._infer_context(text),
                    reason=reason,
                )
            )
        return mentions

    def aggregate(self, articles: list[Article]) -> list[ExpertMention]:
        output: list[ExpertMention] = []
        for article in articles:
            output.extend(self.analyze_article(article))
        return output

    @staticmethod
    def _windows_for_player(text: str, player_name: str) -> list[str]:
        pattern = re.compile(rf"\b{re.escape(player_name)}\b", re.IGNORECASE)
        windows: list[str] = []
        for match in pattern.finditer(text):
            start = max(0, match.start() - 180)
            end = min(len(text), match.end() + 180)
            windows.append(text[start:end].lower())
        return windows

    @staticmethod
    def _score_windows(windows: list[str]) -> tuple[float, float, str]:
        signals: list[float] = []
        matched_terms: list[str] = []
        for window in windows:
            for term, value in POSITIVE_TERMS.items():
                if term in window:
                    signals.append(value)
                    matched_terms.append(term)
            for term, value in NEGATIVE_TERMS.items():
                if term in window:
                    signals.append(value)
                    matched_terms.append(term)
        if not signals:
            return 0.0, 0.25, "Mentioned without strong directional language."
        sentiment = max(-1.0, min(1.0, sum(signals) / max(1, len(signals))))
        magnitude = min(1.0, 0.25 + abs(sum(signals)) / 3.0 + min(0.25, len(windows) * 0.05))
        reason = "Signals: " + ", ".join(sorted(set(matched_terms))[:6])
        return sentiment, magnitude, reason

    @staticmethod
    def _infer_context(text: str) -> str:
        lowered = text.lower()
        if "dynasty" in lowered:
            return "dynasty"
        if "waiver" in lowered:
            return "waiver"
        if "start" in lowered or "sit" in lowered:
            return "weekly"
        if "draft" in lowered:
            return "draft"
        return "general"
