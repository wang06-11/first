"""去重：运行内 + 跨日（借鉴 NewsDiet 的「5 天内去重」）。

- 标题归一化 hash：精确去重
- 词集合 Jaccard 相似度：近似去重（同一事件多源报道）
- 历史 hash 落盘：data/history/pushed.json，保留 N 天
- 关键：历史里只记录「最终推送的条目」，而非「抓取过的所有条目」。
  否则第二天绝大多数抓取条目都会因「昨天见过」被剔除，
  更新慢的分类（时事/科学/文化）会整体被掏空、标签没有内容。
"""
import json
import logging
import os
import re
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HISTORY_DIR = os.path.join(ROOT, "data", "history")
HISTORY_FILE = os.path.join(HISTORY_DIR, "pushed.json")
_KEEP_DAYS = 7

_STOP = set("的 了 和 与 在 是 对 等 a an the of to in on for and with is are be".split())


def _norm_title(t: str) -> str:
    t = re.sub(r"[^\w\u4e00-\u9fff]+", " ", t.lower())
    return re.sub(r"\s+", " ", t).strip()


def title_hash(t: str) -> str:
    return _norm_title(t)


def _tokens(t: str) -> set:
    words = re.findall(r"[\w\u4e00-\u9fff]+", t.lower())
    return {w for w in words if w not in _STOP and len(w) > 1}


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _load_history() -> dict:
    if not os.path.exists(HISTORY_FILE):
        return {}
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:  # noqa: BLE001
        return {}


def _save_history(hist: dict):
    os.makedirs(HISTORY_DIR, exist_ok=True)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(hist, f, ensure_ascii=False, indent=2)


def deduplicate(items: list[dict], keep_days: int = _KEEP_DAYS) -> list[dict]:
    """返回去重后的 items（保留首次出现），只读历史、不写历史。

    历史写入由 remember_pushed() 在「精选完成」后单独调用，
    确保历史里只有已推送条目，不会把当天全部抓取条目误记为已见。
    """
    hist = _load_history()
    now = time.time()
    # 清理过期历史
    hist = {k: v for k, v in hist.items() if now - v < keep_days * 86400}

    seen_exact: set[str] = set()
    seen_tokens: list[tuple[set, str]] = []  # (tokens, key)
    out: list[dict] = []

    for it in items:
        key = title_hash(it["title"])
        if key in seen_exact or key in hist:
            continue
        toks = _tokens(it["title"])
        dup = False
        for ot, _ in seen_tokens:
            if _jaccard(toks, ot) >= 0.6:
                dup = True
                break
        if dup:
            continue
        seen_exact.add(key)
        seen_tokens.append((toks, key))
        out.append(it)

    logging.info("[dedup] %d -> %d 条（跨 %d 天去重，仅剔除已推送）", len(items), len(out), keep_days)
    return out


def remember_pushed(items: list[dict], keep_days: int = _KEEP_DAYS) -> None:
    """把最终精选/推送的条目标题写入跨日历史（只记推送过的，防重复推送）。"""
    hist = _load_history()
    now = time.time()
    hist = {k: v for k, v in hist.items() if now - v < keep_days * 86400}
    for it in items:
        key = title_hash(it.get("title", ""))
        if key:
            hist[key] = now
    _save_history(hist)
    logging.info("[dedup] 已推送 %d 条写入跨日历史", len(items))
