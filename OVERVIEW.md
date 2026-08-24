# NewsPulse 项目概览

> 在 GitHub 调研开源新闻聚合/推送项目后，落地的「每日高质量、多领域、有深度」新闻推送工具。

## 调研借鉴（4 类代表项目）
- **Miniflux / FreshRSS**（RSS 阅读器）：分层管线 `抓取→过滤/全文→阅读`；核心教训是「信息过载必须去重+过滤」。
- **RSSHub**（路由式多源生成）：模块化来源注册 + 中间件缓存/反限流 → 保证多领域覆盖。
- **Huginn**（自动化 Agent）：可调度 + 多通道推送（邮件/Slack/webhook）+ 摘要 Agent。
- **rss_daily / NewsDiet / newsletter_daily / News-Worthy**（每日摘要）：AI 摘要带降级、GitHub Actions 无服务器定时、`sources.yaml` 配置驱动、跨日去重、Telegram/飞书/网页推送、APScheduler 可设推送时间。

## 已实现（对齐用户诉求）
- **高质量+深度**：质量分 = 新鲜度 + 来源权威度 + 内容长度(深度) + 用户关键词偏好；可选 OpenRouter AI 摘要（要点+点评，无 key 自动降级）。
- **多领域防浅薄**：6 大领域（科技/财经/国际/科学/文化/社会），「每领域上限 + 跨领域轮转」精选，强制覆盖 `min_categories`。
- **移动端**：`frontend/index.html` 单文件、内联 CSS/JS/SVG、零外链、可加到主屏；分类筛选/搜索/本地偏好。
- **可配置**：`config.yaml` 调推送时间、领域开关、每领域条数、关键词加权/屏蔽、外文翻译。
- **稳定定时**：GitHub Actions cron（推荐，免费）+ 本地 APScheduler（`--serve`）二选一。
- **多渠道推送**：ntfy / Telegram / 自定义 Webhook，全部可选、失败不中断。
- **去重**：跨源同标题 + 相似度 + 7 天历史，避免重复推送同一事件。

## 验证
- 离线单测通过（`tests/test_basic.py`：配置加载、打分、跨源去重）。
- 桩抓取驱动完整管线跑通（19 条 / 6 领域全覆盖；生成 `data/latest.html`）。
- `data/latest.html` 已用贴近真实的示例数据填充，可直接在手机/浏览器预览。
- 说明：本沙箱到 BBC/Economist 等部分源网络不通，真实 `--once` 需在有外网环境运行（前台超时曾误报 exit 1，非代码缺陷）。

## 快速使用
```bash
pip install -r requirements.txt
python run.py --once            # 生成 data/latest.html
python run.py --web --port 8080 # 手机同网段访问
# 或推到 GitHub 启用 .github/workflows/daily.yml 每日自动运行
```
