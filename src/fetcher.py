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

# 部分中文站点（含 CDN 防护）会拒绝非浏览器 UA，统一使用浏览器 UA 更稳。
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
# 注意：\S+ 会贪婪吞掉 URL 后的 ")"（如 "(https://...)"），导致残留 "("；
# 故在 ")" 处停止，配合下方 .replace("()","") 清理豆瓣头部遗留的空括号。
_URL_RE = re.compile(r"https?://[^\s)]+")
# 豆瓣书评/影评标题会带 " (评论: 影片名)" 后缀，属冗余
_DOUBAN_SUFFIX_RE = re.compile(r"\s*[（(]\s*评论\s*[:：].*?[)）]\s*$")
# 豆瓣摘要开头形如 "某用户评论: 片名 ( 评价: 力荐"（可能含换行，故用 [\s\S]）
_DOUBAN_HEAD_RE = re.compile(r"^[\s\S]{0,24}?评论\s*[:：][\s\S]{0,80}?评价\s*[:：]\s*\S+\s*")
_DOUBAN_HEAD2_RE = re.compile(r"^[\s\S]{0,24}?评论\s*[:：]\s*")
# 豆瓣把 Draft.js 富文本 JSON 直接塞进 RSS 摘要，需抽出其中正文。
# 注意：JSON 既可能以 {"blocks":... 也可能以 {"entityMap":... 开头（blocks 在后）。
_DRAFTJS_RE = re.compile(r'\{\s*"(?:blocks|entityMap)"\s*:')
_BLOCK_TEXT_RE = re.compile(r'"text"\s*:\s*"((?:[^"\\]|\\.)*)"')


def _unescape(s: str) -> str:
    try:
        return s.encode("utf-8").decode("unicode_escape").encode("latin-1", "ignore").decode("utf-8", "ignore")
    except Exception:  # noqa: BLE001
        return s.replace("\\n", " ").replace('\\"', '"')


def _clean(text: str) -> str:
    if not text:
        return ""
    text = _TAG_RE.sub(" ", text)
    text = _WS_RE.sub(" ", text).strip()
    return text


def _clean_title(text: str) -> str:
    return _DOUBAN_SUFFIX_RE.sub("", _clean(text)).strip()


def _clean_summary(text: str) -> str:
    """清理摘要中的 URL 噪音、平台前缀与富文本 JSON，让手机端阅读更干净。

    豆瓣 RSS 摘要形如：
        {用户}评论: {影片} ({url})\\n评价: {评分}\\n\\n{"entityMap":{...},"blocks":[...]}
    其中可读正文在 Draft.js 的 blocks[].text，其余都是噪音，应尽量剔除。
    """
    text = _clean(text)

    # 富文本 JSON（Draft.js）：从整个 JSON 对象中抽出所有 block 正文
    m = _DRAFTJS_RE.search(text)
    if m:
        blocks = _BLOCK_TEXT_RE.findall(text[m.start():])
        body = " ".join(_unescape(b).strip() for b in blocks if b.strip())
        if body:
            # 有正文：直接用正文，丢弃前面的「用户评论/影片/评分」噪声头部
            text = body
        else:
            # blocks 为空（少数豆瓣条目 RSS 只放了封面图，无正文）：
            # 退而保留头部里的「影片名 + 评价」，避免手机端出现空白卡片
            head = _URL_RE.sub("", text[: m.start()])
            head = _DOUBAN_HEAD2_RE.sub("", head, count=1)  # 去掉 "用户评论: "
            text = _WS_RE.sub(" ", head).strip()

    text = _URL_RE.sub("", text)
    text = _DOUBAN_HEAD_RE.sub("", text, count=1)
    text = _DOUBAN_HEAD2_RE.sub("", text, count=1)
    text = _WS_RE.sub(" ", text).replace("( )", "").replace("()", "")
    return text.strip(" ()（）*")


def _parse_date(entry) -> tuple[datetime, bool]:
    """返回 (发布时间, 是否来自源本身)。

    第二个返回值很关键：源没给时间时只能回落为「当前时间」，
    这类条目会伪装成最新，需要在打分阶段降权（见 scorer._no_date）。
    """
    for key in ("published_parsed", "updated_parsed", "created_parsed"):
        val = entry.get(key)
        if val:
            try:
                return datetime(*val[:6], tzinfo=timezone.utc), True
            except Exception:  # noqa: BLE001
                pass
    # 退路：交给 feedparser 的日期解析器处理非标准格式
    for key in ("published", "updated", "created", "dc:date", "pubDate"):
        raw = entry.get(key)
        if not raw:
            continue
        try:
            parsed = feedparser._parse_date(raw)  # noqa: SLF001
            if parsed:
                return datetime(*parsed[:6], tzinfo=timezone.utc), True
        except Exception:  # noqa: BLE001
            pass
    return datetime.now(timezone.utc), False


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
                title = _clean_title(e.get("title", ""))
                summary = _clean_summary(e.get("summary", e.get("description", "")))
                link = e.get("link", "")
                if not title or not link:
                    continue
                dt, has_date = _parse_date(e)
                items.append(
                    {
                        "title": title,
                        "summary": summary,
                        "link": link,
                        "published": dt.isoformat(),
                        "_no_date": not has_date,
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
