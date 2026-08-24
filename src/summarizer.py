"""摘要模块：有 AI key 时调用 OpenRouter 生成「要点 + 一句点评」；
无 key 时优雅降级为原文摘要截取（借鉴 rss_daily 的 AI 降级机制）。
"""
import logging
import os
import re

import requests

_SENT_SPLIT = re.compile(r"(?<=[。.!?！？；;\n])\s*")


def _fallback(summary: str, n: int = 240) -> dict:
    """无 AI：清洗后截取前 n 字作为摘要。"""
    text = re.sub(r"\s+", " ", summary or "").strip()
    if len(text) > n:
        text = text[:n].rstrip() + "…"
    return {"points": [text] if text else ["（暂无摘要）"], "takeaway": "", "ai": False}


def _truncate(text: str, n: int) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text[:n].rstrip() + ("…" if len(text) > n else "")


def summarize(title: str, summary: str, api_key: str, model: str, translate: bool = False) -> dict:
    if not api_key:
        return _fallback(summary)

    prompt = (
        "你是新闻编辑。请基于给定标题与摘要，产出中文结构化摘要：\n"
        "1) 2-3 个要点（每条≤40字，抓住事实与影响）\n"
        "2) 一句点评（≤30字，点明为什么值得关注）\n"
    )
    if translate:
        prompt += "注意：原文可能为外文，请翻译成中文。\n"
    prompt += f"\n标题：{title}\n摘要：{_truncate(summary, 600)}"

    try:
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 300,
            },
            timeout=30,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        points, takeaway = _parse_ai(content)
        return {"points": points, "takeaway": takeaway, "ai": True}
    except Exception as exc:  # noqa: BLE001
        logging.warning("[summarize] AI 摘要失败，降级: %s", exc)
        return _fallback(summary)


def _parse_ai(content: str) -> tuple[list[str], str]:
    lines = [l.strip(" -•·\t") for l in content.splitlines() if l.strip()]
    points, takeaway = [], ""
    for l in lines:
        if l.startswith("点评") or l.startswith("一句话") or "值得关注" in l:
            takeaway = re.sub(r"^.*?[:：]", "", l).strip()
        elif l:
            points.append(l)
    if not points:
        # 退路：按句切分
        parts = [p.strip() for p in _SENT_SPLIT.split(content) if p.strip()]
        points = parts[:3]
    return points[:4], takeaway
