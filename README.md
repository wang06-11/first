# NewsPulse · 每日高质量多领域新闻脉搏

> 一个可在手机上使用的**每日定时新闻推送工具**：覆盖多个领域、保证质量与深度、
> 避免信息来源单一浅薄；支持移动端阅读、可配置推送时间与内容偏好、稳定的定时任务。

借鉴自对 GitHub 上优秀开源项目的调研（详见文末「架构借鉴」）：
Miniflux / FreshRSS（RSS 阅读器管线）、RSSHub（路由式多源 + 缓存）、
Huginn（可调度 Agent + 多通道推送）、rss_daily / NewsDiet / newsletter_daily / News-Worthy（每日摘要 + GitHub Actions 定时）。

---

## ✨ 核心特性（对应用户诉求）

| 诉求 | 实现 |
|------|------|
| 高质量、有深度 | 质量打分 = 新鲜度 + 来源权威度 + 内容长度(深度) + 用户关键词偏好；可选 AI 摘要提取要点与点评 |
| 多领域、避免单一浅薄 | 6 大领域（科技/财经/国际/科学/文化/社会），「每领域上限 + 跨领域轮转」精选，强制覆盖 `min_categories` |
| 移动端可用 | 单文件 `frontend/index.html`，内联 CSS/JS/SVG，零外链，可「添加到主屏幕」当 App |
| 可配置推送时间 | `config.yaml` → `schedule.hour/minute/timezone`；本地 APScheduler 或 GitHub Actions 二选一 |
| 可配置内容偏好 | 领域开关、每领域条数、关键词加权/屏蔽、`translate_to_zh` 均可在 `config.yaml` 调整 |
| 稳定定时机制 | GitHub Actions 无服务器 cron（推荐，免费稳定）+ 本地 APScheduler 常驻（备选） |
| 多渠道推送 | ntfy（手机 App 零账号）/ Telegram / 自定义 Webhook，全部可选、失败不中断 |

---

## 📁 项目结构

```
news-pulse/
├── config.yaml              # ← 主配置：推送时间、内容偏好、领域与 RSS 源
├── requirements.txt
├── .env.example             # ← 复制为 .env 填密钥（AI key / 推送 token）
├── run.py                   # 便捷入口：python run.py --once
├── README.md
├── .github/workflows/
│   └── daily.yml            # GitHub Actions 每日定时（无服务器）
├── src/
│   ├── config.py            # 配置加载（yaml + 环境变量覆盖）
│   ├── fetcher.py           # 多源 RSS/Atom 抓取（重试/超时/友好UA）★借鉴 RSSHub 缓存反限流
│   ├── dedup.py             # 跨日去重（精确 + 相似度，保留 7 天）★借鉴 NewsDiet
│   ├── scorer.py            # 质量+多样性打分与精选（领域均衡轮转）
│   ├── summarizer.py        # AI 摘要（OpenRouter），无 key 优雅降级 ★借鉴 rss_daily 降级
│   ├── generator.py         # 生成 latest.json + 自包含 latest.html
│   ├── notifier.py          # ntfy / Telegram / Webhook 推送 ★借鉴 Huginn 多通道
│   ├── scheduler.py         # APScheduler 本地定时 ★借鉴 News-Worthy
│   └── main.py              # 编排：抓取→去重→打分→精选→摘要→生成→推送
├── frontend/
│   └── index.html           # 移动端阅读器（数据内联，离线可用）
├── data/
│   ├── latest.json          # 当日结构化数据
│   ├── latest.html          # 当日移动端页面（直接打开/托管）
│   └── history/seen.json    # 去重历史（自动生成）
└── tests/
    └── test_basic.py        # 离线单测：配置/打分/去重
```

---

## 🚀 快速开始

### 1. 安装
```bash
cd news-pulse
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. 立即跑一次（本地预览）
```bash
python run.py --once
```
生成 `data/latest.json` 与 `data/latest.html`。直接用浏览器打开 `data/latest.html` 即可看到今日资讯。

### 3. 在手机上看
- **方式 A（最推荐）**：用 `--web` 启动本地静态服务，手机连同一 WiFi 访问
  ```bash
  python run.py --web --port 8080
  # 手机浏览器打开 http://<电脑局域网IP>:8080/data/latest.html
  # 然后「添加到主屏幕」，像 App 一样使用
  ```
- **方式 B（公网托管）**：把 `data/latest.html` 部署到任意静态托管（GitHub Pages / Vercel / 对象存储），得到固定链接，手机随时访问。

### 4. 配置推送时间 & 内容偏好
编辑 `config.yaml`：
```yaml
schedule:
  timezone: "Asia/Shanghai"
  hour: 8          # 每天 08:00 推送
  minute: 0
preferences:
  max_total: 36
  per_category: 7
  min_categories: 5   # 至少覆盖 5 个领域
  keywords_boost: [AI, 芯片, 气候]   # 你关心的话题加权
  keywords_block: [明星八卦]          # 屏蔽词
```
**改领域/换源**：在 `categories` 下增删 `sources` 条目即可，无需改代码。

### 5. 开启推送（可选）
复制 `.env.example` 为 `.env` 并填写：
- `NTFY_TOPIC`：手机装 [ntfy](https://ntfy.sh) App，订阅同名 topic 即可收推送（零账号）
- `TELEGRAM_TOKEN` / `TELEGRAM_CHAT_ID`：Telegram Bot 推送
- `WEBHOOK_URL`：企业微信/飞书/IFTTT 等
不填则只生成网页，不推送。

### 6. 稳定定时（二选一）

**A. GitHub Actions（推荐，免费稳定）**
1. 把仓库推到 GitHub
2. `Settings → Secrets` 添加：`OPENROUTER_API_KEY`、`NTFY_TOPIC`、`TELEGRAM_TOKEN`、`TELEGRAM_CHAT_ID`、`PAGE_URL`（可选）
3. 每天 UTC 00:00（北京 08:00）自动运行并把结果提交回 `data/`
4. 若用方式 B 托管，把托管后的 `latest.html` 链接填进 `PAGE_URL`，推送文案里就会带可点链接
> 改时间：编辑 `.github/workflows/daily.yml` 里的 `cron`（UTC）。

**B. 本地常驻（有一直开着的机器/VPS 时）**
```bash
python run.py --serve     # 按 config.yaml 的 schedule 每天执行
```

---

## 🧪 测试
```bash
python tests/test_basic.py    # 离线校验配置/打分/去重逻辑
```

---

## 🏗️ 架构借鉴（来自开源调研）

1. **Miniflux / FreshRSS** — 分层管线 `抓取→过滤/全文→阅读`；核心教训是「信息过载必须去重+过滤」，本项目用 `dedup.py` + 质量打分落实。
2. **RSSHub** — 路由式多源生成 + 中间件缓存 + 声明式路由；借鉴其「模块化来源注册（config 即路由）+ 反限流 UA/重试」保证多领域覆盖。
3. **Huginn** — Agent 事件 DAG + 每 Agent 定时 + 多通道通知（邮件/Slack/webhook）；借鉴「可调度 + 多渠道推送 + 摘要」三段式。
4. **rss_daily / NewsDiet / newsletter_daily / News-Worthy** — 多分类 RSS 聚合、AI 摘要带降级、GitHub Actions 无服务器定时、`sources.yaml` 配置驱动、跨日去重、Telegram/飞书/网页推送、APScheduler 可设推送时间。本项目直接对齐「可配置时间/偏好 + 稳定定时 + 移动端」。

## ⚠️ 隐私与边界
- 部署后的阅读页若托管为公网链接，任何拿到链接的人都能打开；`data/` 不含你的密钥。
- `.env` 含密钥，**切勿提交**。AI 摘要需自备 OpenRouter key；不填则降级为原文摘要。
- `data/history/seen.json` 仅用于去重，仅存标题归一化哈希，不含正文。
