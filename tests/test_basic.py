"""基础测试：配置加载 + 打分/精选/去重逻辑（离线，无需网络）。"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from src.config import NewsPulseConfig
from src import scorer, dedup


def test_config_load():
    cfg = NewsPulseConfig.load()
    assert cfg.categories, "应至少加载一个领域"
    assert cfg.schedule["hour"] in range(0, 24)
    print("OK config:", len(cfg.categories), "categories")


def test_score_and_select():
    # 清空去重历史，保证测试确定性（避免跨运行的持久化哈希干扰）
    hist = os.path.join(ROOT, "data", "history", "seen.json")
    if os.path.exists(hist):
        os.remove(hist)

    items = [
        {"title": "AI 芯片重大突破", "summary": "x" * 500, "link": "https://a", "published": "",
         "_category": "tech_ai", "_cat_name": "科技与AI", "_source_name": "Hacker News",
         "_cat_authority": 1.0, "_source_weight": 1.0},
        {"title": "AI 芯片重大突破", "summary": "y" * 100, "link": "https://b", "published": "",
         "_category": "tech_ai", "_cat_name": "科技与AI", "_source_name": "The Verge",
         "_cat_authority": 1.0, "_source_weight": 0.9},  # 重复（同标题）
        {"title": "全球气候峰会达成新协议", "summary": "z" * 300, "link": "https://c", "published": "",
         "_category": "world", "_cat_name": "国际", "_source_name": "BBC",
         "_cat_authority": 0.95, "_source_weight": 0.9},
    ]
    for it in items:
        it["_score"] = scorer.score_item(it, it["_cat_authority"], it["_source_weight"], {})
    deduped = dedup.deduplicate(items)
    assert len(deduped) == 2, f"跨源同标题应去重，实际 {len(deduped)}"
    selected = scorer.select(items, {"per_category": 7, "min_categories": 5, "max_total": 36})
    assert selected, "应选出条目"
    print("OK dedup+select:", len(deduped), "->", len(selected))


if __name__ == "__main__":
    test_config_load()
    test_score_and_select()
    print("ALL TESTS PASSED")
