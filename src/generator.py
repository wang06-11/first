"""生成器：构建当日 digest，写出 latest.json 与自包含 latest.html。

- latest.json：结构化的程序化数据（供 API / 前端 fetch）
- latest.html：移动端阅读页，数据内联，离线/直接打开均可用
模板来源 frontend/index.html（单一模板，注入 __DIGEST_JSON__ 占位符）
"""
import json
import logging
import os
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
TEMPLATE = os.path.join(ROOT, "frontend", "index.html")
PLACEHOLDER = "/*__DIGEST_JSON__*/null"


def build_digest(items: list[dict]) -> dict:
    cats: dict[str, dict] = {}
    out = []
    for it in items:
        cats.setdefault(it["_category"], {"id": it["_category"], "name": it["_cat_name"], "count": 0})
        cats[it["_category"]]["count"] += 1
        out.append(
            {
                "title": it.get("title", ""),
                "summary": it.get("summary", "")[:400],
                "points": it.get("points", []),
                "takeaway": it.get("takeaway", ""),
                "link": it.get("link", ""),
                "source": it.get("_source_name", ""),
                "category": it.get("_category", ""),
                "category_name": it.get("_cat_name", ""),
                "score": round(it.get("_score", 0), 1),
                "published": it.get("published", ""),
                "ai": it.get("ai", False),
            }
        )
    return {
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total": len(out),
        "categories": sorted(cats.values(), key=lambda c: -c["count"]),
        "items": out,
    }


def render(digest: dict) -> str:
    with open(TEMPLATE, "r", encoding="utf-8") as f:
        tpl = f.read()
    payload = json.dumps(digest, ensure_ascii=False)
    if PLACEHOLDER not in tpl:
        raise RuntimeError("模板缺少占位符 " + PLACEHOLDER)
    return tpl.replace(PLACEHOLDER, payload)


def write(digest: dict) -> tuple[str, str]:
    os.makedirs(DATA_DIR, exist_ok=True)
    json_path = os.path.join(DATA_DIR, "latest.json")
    html_path = os.path.join(DATA_DIR, "latest.html")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(digest, f, ensure_ascii=False, indent=2)
    html = render(digest)
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    logging.info("[generate] 写出 latest.json / latest.html（%d 条）", digest["total"])
    _write_archive(digest)
    return json_path, html_path


def _write_archive(digest: dict):
    """把每日 digest 落盘到 data/archive/<日期>.json，并维护 index.json。

    前端日期选择器据此回看任意一天；归档随 GitHub Pages 的 data/ 目录一起发布。
    """
    date = digest.get("date")
    if not date:
        return
    arch_dir = os.path.join(DATA_DIR, "archive")
    os.makedirs(arch_dir, exist_ok=True)
    arc_path = os.path.join(arch_dir, f"{date}.json")
    with open(arc_path, "w", encoding="utf-8") as f:
        json.dump(digest, f, ensure_ascii=False, indent=2)
    # 维护升序去重的日期索引
    idx_path = os.path.join(arch_dir, "index.json")
    dates: list[str] = []
    if os.path.exists(idx_path):
        try:
            dates = json.load(open(idx_path, encoding="utf-8"))
        except Exception:
            dates = []
    if date not in dates:
        dates.append(date)
    dates = sorted(set(dates))
    with open(idx_path, "w", encoding="utf-8") as f:
        json.dump(dates, f, ensure_ascii=False, indent=2)
    logging.info("[generate] 归档 %s.json（共 %d 个归档日）", date, len(dates))
