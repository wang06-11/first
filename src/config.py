"""配置加载：config.yaml + 环境变量覆盖。"""
import os
import yaml
from dataclasses import dataclass, field
from typing import Any

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_env_file(path: str):
    """极简 .env 解析（不依赖 python-dotenv，避免额外依赖）。"""
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


@dataclass
class NewsPulseConfig:
    raw: dict = field(default_factory=dict)

    @classmethod
    def load(cls, path: str | None = None):
        _load_env_file(os.path.join(ROOT, ".env"))
        path = path or os.path.join(ROOT, "config.yaml")
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        return cls(raw=raw)

    # —— 便捷访问 ——
    @property
    def schedule(self) -> dict:
        return self.raw.get("schedule", {"timezone": "Asia/Shanghai", "hour": 8, "minute": 0})

    @property
    def preferences(self) -> dict:
        return self.raw.get("preferences", {})

    @property
    def notify(self) -> dict:
        n = dict(self.raw.get("notify", {}))
        # 环境变量优先（密钥不入库）
        n["ntfy_topic"] = n.get("ntfy_topic") or os.environ.get("NTFY_TOPIC", "")
        n["telegram_token"] = n.get("telegram_token") or os.environ.get("TELEGRAM_TOKEN", "")
        n["telegram_chat_id"] = n.get("telegram_chat_id") or os.environ.get("TELEGRAM_CHAT_ID", "")
        n["webhook_url"] = n.get("webhook_url") or os.environ.get("WEBHOOK_URL", "")
        return n

    @property
    def categories(self) -> list:
        return [c for c in self.raw.get("categories", []) if c.get("enabled", True)]

    # —— 密钥 ——
    @property
    def openrouter_key(self) -> str:
        return os.environ.get("OPENROUTER_API_KEY", "")

    @property
    def openrouter_model(self) -> str:
        return os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o-mini")

    def get(self, key: str, default: Any = None):
        return self.raw.get(key, default)
