"""多源 RSS/Atom 抓取：带重试、超时、友好 UA，单源失败不影响整体。

借鉴：
- RSSHub 的「缓存/反限流」思路 => 统一 UA + 重试退避
- FreshRSS/Miniflux 的「抓取层」 => 归一化为统一 NewsItem
"""
import logging
import time
import random
import re
from datetime import datetime, timezone

import feedparser
import requests

HEADERS = {
    "User-Agent": "NewsPulse/1.0 (+https://github.com/your/news-pulse; RSS reader)",
    "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
}

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _clean(text: str) -> str:
    if not text:
        return ""
    text = _TAG_RE.sub(" ", text)
    text = _WS_RE.sub(" ", text).strip()
    return text


def _parse_date(entry) -> datetime:
    for key in ("published_parsed", "updated_parsed", "created_parsed"):
        val = entry.get(key)
        if val:
            try:
                return datetime(*val[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    for key in ("published", "updated", "created"):
        val = entry.get(key)
        if val:
            try:
                return feedparser.parse(val).get("updated_parsed") and datetime(
                    *feedparser.parse(val)["updated_parsed"][:6], tzinfo=timezone.utc
                )
            except Exception:
                pass
    return datetime.now(timezone.utc)


def fetch_feed(url: str, timeout: int = 15, retries: int = 2) -> list[dict]:
    """抓取一个 feed，返回归一化条目列表（失败返回空列表）。"""
    for attempt in range(retries + 1):
        try:
            r = requests.get(url, headers=HEADERS, timeout=timeout)
            r.raise_for_status()
            parsed = feedparser.parse(r.content)
            if parsed.bozo and not parsed.entries:
                raise ValueError(str(parsed.get("bozo_exception", "parse error")))
            items = []
            for e in parsed.entries:
                title = _clean(e.get("title", ""))
                summary = _clean(e.get("summary", e.get("description", "")))
                link = e.get("link", "")
                if not title or not link:
                    continue
                items.append(
                    {
                        "title": title,
                        "summary": summary,
                        "link": link,
                        "published": _parse_date(e).isoformat(),
                        "source_url": url,
                    }
                )
            return items
        except Exception as exc:  # noqa: BLE001
            logging.warning("[fetch] %s 第%d次失败: %s", url, attempt + 1, exc)
            if attempt == retries:
                return []
            time.sleep(1 + random.random() * 2)
    return []
