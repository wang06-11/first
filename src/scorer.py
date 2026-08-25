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


_CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def _is_chinese(text: str) -> bool:
    """粗判是否中文文本（CJK 字符占比 > 20%）。"""
    if not text:
        return False
    cjk = len(_CJK_RE.findall(text))
    return cjk >= 8 or (cjk / max(1, len(text))) > 0.2


def _depth_score(summary: str, title: str) -> float:
    """深度分：按语言自适应阈值。

    中文单字信息量远高于英文单字符：一条 160 字的中文摘要
    ≈ 一条 400 字符的英文摘要。若统一用 400 阈值，中文条目
    会被系统性误判为「没深度」。
    """
    length = len(summary or "")
    threshold = 160.0 if _is_chinese(summary or title) else 400.0
    return min(1.0, length / threshold)


def score_item(item: dict, cat_authority: float, source_weight: float, prefs: dict) -> float:
    """返回 0-100 的单项质量分。"""
    # 新鲜度：72h 内线性衰减
    age = _hours_ago(item.get("published", ""))
    fresh = max(0.0, 1.0 - age / 72.0)
    # 源未提供发布时间时，抓取层回落为「当前时间」，会伪装成最新。
    # 这里打对折，避免无时间戳的源霸占榜首。
    if item.get("_no_date"):
        fresh *= 0.5

    title = item.get("title", "")
    depth = _depth_score(item.get("summary", ""), title)

    # 用户偏好关键词加权
    boost = 0.0
    text = (title + " " + item.get("summary", "")).lower()
    for kw in prefs.get("keywords_boost", []) or []:
        if kw.lower() in text:
            boost += 0.15
    block = 0.0
    for kw in prefs.get("keywords_block", []) or []:
        if kw.lower() in text:
            block += 0.5

    # 标题过短通常是图集/短视频/快讯占位，信息量低
    short_title_penalty = 3.0 if len(title.strip()) < 8 else 0.0

    s = (
        45 * fresh
        + 20 * cat_authority
        + 15 * source_weight
        + 15 * depth
        + boost
        - block
        - short_title_penalty
    )
    return max(0.0, min(100.0, s))


def filter_fresh(items: list[dict], max_age_hours: float) -> list[dict]:
    """硬过滤：剔除超过 max_age_hours 的条目。

    部分中文门户 RSS 会返回上百条历史条目，若不过滤，
    「每日新闻」会混入几个月前的旧闻。
    """
    if not max_age_hours or max_age_hours <= 0:
        return items
    kept = [it for it in items if _hours_ago(it.get("published", "")) <= max_age_hours]
    dropped = len(items) - len(kept)
    if dropped:
        logging.info("[filter] 剔除 %d 条超过 %.0f 小时的旧闻，保留 %d 条",
                     dropped, max_age_hours, len(kept))
    return kept


def _cap_per_source(sorted_items: list[dict], per_cat: int) -> list[dict]:
    """限制单个来源在同一领域内的条目数，保证来源多样性。

    配额 = max(2, ceil(per_category / 该领域源数))：
    源多的领域每源少取（科技 8 源 -> 每源 2 条），
    源少的领域适度放宽（国际 2 源 -> 每源 3 条），避免凑不满。
    超额条目排到列表末尾作为备用，而非直接丢弃。
    """
    n_src = len({it.get("_source_name", "") for it in sorted_items}) or 1
    quota = max(2, math.ceil(per_cat / n_src))
    used: dict[str, int] = {}
    primary, overflow = [], []
    for it in sorted_items:
        src = it.get("_source_name", "")
        if used.get(src, 0) < quota:
            used[src] = used.get(src, 0) + 1
            primary.append(it)
        else:
            overflow.append(it)
    return primary + overflow


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

    # 同源配额：防止单一媒体霸占整个领域（如豆瓣影评占满「文化」）。
    # 配额随领域内源数量动态调整，源多则每源少取，源少则放宽。
    by_cat = {cat: _cap_per_source(lst, per_cat) for cat, lst in by_cat.items()}

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
