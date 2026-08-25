"""NewsPulse 主流程编排。

流水线（借鉴 rss_daily / NewsDiet / newsletter_daily）：
  抓取(fetcher) → 跨日去重(dedup) → 质量+多样性打分(scorer) →
  精选(select) → 仅对精选做 AI 摘要(summarizer, 省 token) →
  生成(generator) → 多渠道推送(notifier)

CLI:
  python -m src.main --once          跑一次（GitHub Actions 也用这个）
  python -m src.main --serve         本地常驻定时（APScheduler）
  python -m src.main --web [--port]  启动静态服务，手机同网段访问
  python -m src.main --schedule-now  立即跑一次并退出（调试）
"""
import argparse
import logging
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from .config import NewsPulseConfig
from . import fetcher, dedup, scorer, summarizer, generator, notifier, scheduler

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def collect(cfg: NewsPulseConfig) -> list[dict]:
    # 先组装所有待抓任务，再并行抓取，显著缩短多源聚合时间
    tasks = []
    for cat in cfg.categories:
        cid = cat["id"]
        cname = cat.get("name", cid)
        auth = float(cat.get("authority", 1.0))
        for src in cat.get("sources", []):
            tasks.append((src, cid, cname, auth))

    all_items: list[dict] = []
    max_workers = min(10, max(1, len(tasks)))
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        future_to_meta = {
            ex.submit(fetcher.fetch_feed, src["url"]): (src, cid, cname, auth)
            for src, cid, cname, auth in tasks
        }
        for fut in as_completed(future_to_meta):
            src, cid, cname, auth = future_to_meta[fut]
            raw = fut.result()
            w = float(src.get("weight", 1.0))
            for it in raw:
                it["_category"] = cid
                it["_cat_name"] = cname
                it["_source_name"] = src.get("name", src["url"])
                it["_cat_authority"] = auth
                it["_source_weight"] = w
                all_items.append(it)
    logging.info("[collect] 共抓取 %d 条原始条目（%d 个启用领域，%d 个源）",
                 len(all_items), len(cfg.categories), len(tasks))
    return all_items


def run_once(cfg: NewsPulseConfig, page_url: str = "") -> dict:
    items = collect(cfg)
    items = dedup.deduplicate(items)
    for it in items:
        it["_score"] = scorer.score_item(
            it, it["_cat_authority"], it["_source_weight"], cfg.preferences
        )
    selected = scorer.select(items, cfg.preferences)

    ai_key = cfg.openrouter_key
    model = cfg.openrouter_model
    translate = bool(cfg.preferences.get("translate_to_zh"))
    if ai_key and selected:
        logging.info("[summary] 对精选的 %d 条做 AI 摘要", len(selected))
    for it in selected:
        sm = summarizer.summarize(it["title"], it.get("summary", ""), ai_key, model, translate)
        it.update(sm)

    digest = generator.build_digest(selected)
    digest["page_url"] = page_url
    generator.write(digest)
    notifier.notify_all(cfg.notify, digest)
    return digest


def _job():
    cfg = NewsPulseConfig.load()
    page = os.environ.get("PAGE_URL", "")
    d = run_once(cfg, page_url=page)
    logging.info("完成：%d 条，覆盖 %d 领域", d["total"], len(d["categories"]))


def serve_scheduler(cfg: NewsPulseConfig):
    s = cfg.schedule
    scheduler.run_loop(_job, int(s.get("hour", 8)), int(s.get("minute", 0)),
                       s.get("timezone", "Asia/Shanghai"))


def serve_web(port: int = 8080):
    os.chdir(ROOT)
    httpd = ThreadingHTTPServer(("0.0.0.0", port), SimpleHTTPRequestHandler)
    logging.info("静态服务已启动：http://<本机IP>:%d  （手机同网段访问 data/latest.html）", port)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.shutdown()


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description="NewsPulse 每日新闻聚合推送")
    ap.add_argument("--once", action="store_true", help="立即跑一次并退出")
    ap.add_argument("--serve", action="store_true", help="本地常驻定时调度")
    ap.add_argument("--web", action="store_true", help="启动静态服务供手机访问")
    ap.add_argument("--port", type=int, default=8080, help="--web 端口")
    ap.add_argument("--schedule-now", action="store_true", help="同 --once（调试别名）")
    args = ap.parse_args()

    cfg = NewsPulseConfig.load()
    if args.once or args.schedule_now:
        page = os.environ.get("PAGE_URL", "")
        d = run_once(cfg, page_url=page)
        print(f"✅ 生成完成：{d['total']} 条，覆盖 {len(d['categories'])} 个领域")
        for c in d["categories"]:
            print(f"   - {c['name']}: {c['count']} 条")
        return
    if args.web:
        serve_web(args.port)
        return
    if args.serve:
        serve_scheduler(cfg)
        return
    # 默认：跑一次
    _job()


if __name__ == "__main__":
    main()
