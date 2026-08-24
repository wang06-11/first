"""质量 + 多样性打分与精选。

设计目标（对应用户诉求）：
- 高质量：新鲜度、来源权威度、内容长度(深度)、用户关键词偏好
- 多领域/有深度：保证覆盖 min_categories，且每领域均衡取Top
- 避免单一浅薄：per_category 上限 + 跨领域轮转补足
"""
import logging
import math
import re
from datetime import datetime, timezone


def _hours_ago(iso: str) -> float:
    try:
        dt = datetime.fromisoformat(iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0.0, (datetime.now(timezone.utc) - dt).total_seconds() / 3600)
    except Exception:  # noqa: BLE001
        return 24.0


def score_item(item: dict, cat_authority: float, source_weight: float, prefs: dict) -> float:
    """返回 0-100 的单项质量分。"""
    # 新鲜度：48h 内线性衰减
    age = _hours_ago(item.get("published", ""))
    fresh = max(0.0, 1.0 - age / 72.0)

    # 深度：正文长度信号（RSS 常只给摘要，越长通常越有料）
    length = len(item.get("summary", ""))
    depth = min(1.0, length / 400.0)

    # 用户偏好关键词加权
    boost = 0.0
    text = (item.get("title", "") + " " + item.get("summary", "")).lower()
    for kw in prefs.get("keywords_boost", []) or []:
        if kw.lower() in text:
            boost += 0.15
    block = 0.0
    for kw in prefs.get("keywords_block", []) or []:
        if kw.lower() in text:
            block += 0.5

    s = (
        45 * fresh
        + 20 * cat_authority
        + 15 * source_weight
        + 15 * depth
        + boost
        - block
    )
    return max(0.0, min(100.0, s))


def select(items_with_meta: list[dict], prefs: dict) -> list[dict]:
    """items_with_meta: 每条含 _score, _category, _cat_name, _source。

    策略：
    1) 每领域按分数取 Top per_category
    2) 若覆盖领域 < min_categories，放宽阈值补满领域
    3) 跨领域轮转取 Top，直至 max_total，保证均衡
    """
    per_cat = int(prefs.get("per_category", 7))
    min_cats = int(prefs.get("min_categories", 5))
    max_total = int(prefs.get("max_total", 36))

    by_cat: dict[str, list[dict]] = {}
    for it in items_with_meta:
        by_cat.setdefault(it["_category"], []).append(it)

    for cat in by_cat:
        by_cat[cat].sort(key=lambda x: x["_score"], reverse=True)

    # 先每领域取 Top per_cat
    chosen: list[dict] = []
    for cat, lst in by_cat.items():
        chosen.extend(lst[:per_cat])

    # 领域覆盖保护：未达 min_categories 时，从有余量的领域补
    if len(chosen) == 0:
        return []
    chosen_cats = {c["_category"] for c in chosen}
    if len(chosen_cats) < min_cats:
        for cat, lst in by_cat.items():
            if cat in chosen_cats or not lst:
                continue
            chosen.append(lst[0])
            chosen_cats.add(cat)

    # 跨领域均衡轮转取 Top 至 max_total
    chosen.sort(key=lambda x: x["_score"], reverse=True)
    final: list[dict] = []
    ptr = {c: 0 for c in by_cat}
    # 多轮：每轮从仍有余量的领域各取当前最高分者
    while len(final) < max_total:
        progressed = False
        round_pick = []
        for cat in sorted(by_cat, key=lambda c: -max((i["_score"] for i in by_cat[c]), default=0)):
            lst = by_cat[cat]
            i = ptr[cat]
            if i < len(lst) and lst[i] not in final and lst[i] not in round_pick:
                round_pick.append(lst[i])
                ptr[cat] = i + 1
                progressed = True
        if not progressed:
            break
        # 本轮按分数再排序取最优若干，避免单次塞满
        round_pick.sort(key=lambda x: x["_score"], reverse=True)
        for it in round_pick:
            if len(final) >= max_total:
                break
            if it not in final:
                final.append(it)
    final.sort(key=lambda x: x["_score"], reverse=True)
    logging.info("[select] 精选 %d 条，覆盖 %d 个领域",
                 len(final), len({c['_category'] for c in final}))
    return final
