"""推送模块：多渠道，全部可选，任一失败不影响生成。

借鉴 Huginn 的「多通道通知 Agent」与 rss_daily / News-Worthy 的飞书/Telegram 推送。
- ntfy.sh：手机装 ntfy App 订阅 topic 即可收推送，零账号
- Telegram：Bot + Chat ID
- Webhook：企业微信/飞书/IFTTT 等自定义
"""
import json
import logging

import requests


def _safe_post(url: str, **kw) -> bool:
    try:
        r = requests.post(url, timeout=15, **kw)
        r.raise_for_status()
        return True
    except Exception as exc:  # noqa: BLE001
        logging.warning("[notify] 推送失败 %s: %s", url[:60], exc)
        return False


def send_ntfy(topic: str, digest: dict) -> bool:
    if not topic:
        return False
    top_items = digest["items"][:5]
    lines = [f"📰 NewsPulse 今日 {digest['total']} 条（{digest['date']}）"]
    for it in top_items:
        lines.append(f"• [{it['category_name']}] {it['title']}")
    lines.append(f"打开阅读页查看全部：{digest.get('page_url', '')}")
    return _safe_post(
        f"https://ntfy.sh/{topic}",
        data="\n".join(lines).encode("utf-8"),
        headers={"Title": "NewsPulse 每日资讯", "Priority": "default"},
    )


def send_telegram(token: str, chat_id: str, digest: dict) -> bool:
    if not token or not chat_id:
        return False
    top = digest["items"][:8]
    msg = f"*📰 NewsPulse 每日资讯*{digest['date']}（共 {digest['total']} 条）\n\n"
    for it in top:
        msg += f"• *[{it['category_name']}]* {it['title']}\n  {it['link']}\n"
    if digest.get("page_url"):
        msg += f"\n🌐 完整版：{digest['page_url']}"
    return _safe_post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown", "disable_web_page_preview": False},
    )


def send_webhook(url: str, digest: dict) -> bool:
    if not url:
        return False
    return _safe_post(url, json={"type": "newspulse.daily", "digest": digest})


def notify_all(cfg_notify: dict, digest: dict) -> dict:
    result = {
        "ntfy": send_ntfy(cfg_notify.get("ntfy_topic", ""), digest),
        "telegram": send_telegram(cfg_notify.get("telegram_token", ""),
                                  cfg_notify.get("telegram_chat_id", ""), digest),
        "webhook": send_webhook(cfg_notify.get("webhook_url", ""), digest),
    }
    logging.info("[notify] 结果：%s", result)
    return result
