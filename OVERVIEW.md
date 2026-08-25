# NewsPulse 项目概览

> 在 GitHub 调研开源新闻聚合/推送项目后，落地的「每日高质量、多领域、有深度」新闻推送工具。

## 调研借鉴（4 类代表项目）
- **Miniflux / FreshRSS**（RSS 阅读器）：分层管线 `抓取→过滤/全文→阅读`；核心教训是「信息过载必须去重+过滤」。
- **RSSHub**（路由式多源生成）：模块化来源注册 + 中间件缓存/反限流 → 保证多领域覆盖。
- **Huginn**（自动化 Agent）：可调度 + 多通道推送（邮件/Slack/webhook）+ 摘要 Agent。
- **rss_daily / NewsDiet / newsletter_daily / News-Worthy**（每日摘要）：AI 摘要带降级、GitHub Actions 无服务器定时、`sources.yaml` 配置驱动、跨日去重、Telegram/飞书/网页推送、APScheduler 可设推送时间。

## 已实现（对齐用户诉求）
- **高质量+深度**：质量分 = 新鲜度 + 来源权威度 + 内容长度(深度) + 用户关键词偏好；可选 OpenRouter AI 摘要（要点+点评，无 key 自动降级）。
- **多领域防浅薄**：6 大领域（科技与 AI / 财经与商业 / 时事与国际 / 科学与健康 / 文化与思想 / 社会与深度），全部为**已实测可访问的中文 RSS 源**（Solidot、量子位、IT之家、华尔街见闻、财新、澎湃、果壳、豆瓣等 25 个）；「每领域上限 + 跨领域轮转 + 单源配额」精选，强制覆盖 `min_categories`，避免单一媒体霸屏。
- **移动端**：`frontend/index.html` 单文件、内联 CSS/JS/SVG、零外链、可加到主屏；底部分类胶囊导航 + 日期回看。
- **底部导航（全部+分类） + 回看往日**：底部为横向滚动胶囊导航——「全部」+ 6 个具体分类区块（带配色圆点，拇指可达）；顶部日期药丸唤起日期选择器，可加载 `data/archive/<日期>.json` 回看任意一天。生成器每日归档并随 GitHub Pages 的 `data/` 目录发布。
- **可配置**：`config.yaml` 调推送时间、领域开关、每领域条数、关键词加权/屏蔽、外文翻译。
- **稳定定时**：GitHub Actions cron（推荐，免费）+ 本地 APScheduler（`--serve`）二选一。
- **多渠道推送**：ntfy / Telegram / 自定义 Webhook，全部可选、失败不中断。
- **去重**：跨源同标题 + 相似度 + 7 天历史，避免重复推送同一事件。

## 验证
- 离线单测通过（`tests/test_basic.py`：配置加载、打分、跨源去重）。
- 桩抓取驱动完整管线跑通（19 条 / 6 领域全覆盖；生成 `data/latest.html`）。
- `data/latest.html` 已用贴近真实的示例数据填充，可直接在手机/浏览器预览。
- 说明：所有源已切为**中文 RSS**（`config.yaml` 中 25 个源均经本地探测：可访问、带时间戳、72h 内有新内容；已剔除新华网/人民网等无时间戳或超旧源）。中文摘要用自适应深度阈值打分（160 字≈英文 400 字符），并对豆瓣 Draft.js 富文本 JSON 做抽取清洗。部分 RSSHub 代理源偶发超时，已在抓取层加重试；生产环境（GitHub Actions 云端）访问更稳定。

## 快速使用
```bash
pip install -r requirements.txt
python run.py --once            # 生成 data/latest.html
python run.py --web --port 8080 # 手机同网段访问
# 或推到 GitHub 启用 .github/workflows/daily.yml 每日自动运行
```
