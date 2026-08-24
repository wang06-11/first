"""本地定时调度（APScheduler）。

与 GitHub Actions 二选一：本地常驻用本模块；无服务器用 Actions。
借鉴 News-Worthy 的 APScheduler 与 newsletter_daily 的每日定时任务。
"""
import logging

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

try:
    from tzlocal import get_localzone
except Exception:  # noqa: BLE001
    from datetime import timezone as _tz
    def get_localzone():
        return _tz.utc


def run_loop(job, hour: int, minute: int, timezone: str):
    logging.info("本地调度启动：每天 %02d:%02d (%s) 执行一次", hour, minute, timezone)
    sched = BlockingScheduler(timezone=timezone)
    sched.add_job(job, CronTrigger(hour=hour, minute=minute), id="daily_news")
    try:
        sched.start()
    except (KeyboardInterrupt, SystemExit):
        sched.shutdown()
