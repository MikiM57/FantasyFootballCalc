from __future__ import annotations

import html
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date
from urllib.request import Request, urlopen

from fantasy_value.agents.sentiment_agent import Article, fetch_article_text


@dataclass(frozen=True)
class ArticleSourceConfig:
    rss_feeds: tuple[str, ...] = ()
    article_urls: tuple[str, ...] = ()
    fetch_article_bodies: bool = False


def source_config_from_env(env: dict[str, str]) -> ArticleSourceConfig:
    return ArticleSourceConfig(
        rss_feeds=_split_urls(env.get("ARTICLE_FEEDS", "")),
        article_urls=_split_urls(env.get("ARTICLE_URLS", "")),
        fetch_article_bodies=env.get("ALLOW_ARTICLE_BODY_FETCH", "").lower() == "true",
    )


def load_articles(config: ArticleSourceConfig) -> list[Article]:
    articles: list[Article] = []
    for feed_url in config.rss_feeds:
        articles.extend(fetch_rss_articles(feed_url))
    for article_url in config.article_urls:
        articles.append(fetch_single_article(article_url, config.fetch_article_bodies))
    return articles


def fetch_rss_articles(feed_url: str, timeout: float = 10.0) -> list[Article]:
    request = Request(feed_url, headers={"User-Agent": "FantasyFootballCalc/0.1"})
    with urlopen(request, timeout=timeout) as response:
        raw = response.read()
    root = ET.fromstring(raw)
    articles: list[Article] = []
    for item in root.findall(".//item"):
        title = _text(item, "title")
        description = _text(item, "description")
        link = _text(item, "link") or None
        if title or description:
            articles.append(
                Article(
                    source=_hostname(feed_url),
                    title=html.unescape(title),
                    body=html.unescape(description),
                    url=link,
                    published_on=None,
                )
            )
    if articles:
        return articles

    namespace = {"atom": "http://www.w3.org/2005/Atom"}
    for entry in root.findall(".//atom:entry", namespace):
        title = _text(entry, "atom:title", namespace)
        summary = _text(entry, "atom:summary", namespace) or _text(entry, "atom:content", namespace)
        link = _atom_link(entry)
        if title or summary:
            articles.append(
                Article(
                    source=_hostname(feed_url),
                    title=html.unescape(title),
                    body=html.unescape(summary),
                    url=link,
                    published_on=None,
                )
            )
    return articles


def fetch_single_article(article_url: str, fetch_body: bool) -> Article:
    body = fetch_article_text(article_url) if fetch_body else ""
    return Article(
        source=_hostname(article_url),
        title=article_url,
        body=body,
        url=article_url,
        published_on=date.today(),
    )


def _split_urls(raw: str) -> tuple[str, ...]:
    urls = []
    for item in raw.replace("\n", ",").split(","):
        clean = item.strip()
        if clean:
            urls.append(clean)
    return tuple(urls)


def _text(element: ET.Element, tag: str, namespace: dict[str, str] | None = None) -> str:
    child = element.find(tag, namespace or {})
    if child is None or child.text is None:
        return ""
    return child.text.strip()


def _atom_link(entry: ET.Element) -> str | None:
    namespace = {"atom": "http://www.w3.org/2005/Atom"}
    link = entry.find("atom:link", namespace)
    if link is None:
        return None
    return link.attrib.get("href")


def _hostname(url: str) -> str:
    without_protocol = url.split("://", 1)[-1]
    return without_protocol.split("/", 1)[0]
