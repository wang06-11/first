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
- **列表 → 详情阅读**：列表页展示精简摘要（summary 截断 400 字），点击卡片进入详情页展示**完整原文内容**（`content` 字段不截断）+ 要点速览 + AI 点评 + 「阅读原文」外链。数据传递：每条新闻由生成器写入稳定唯一 `id`（来源+标题 MD5 前 12 位），列表卡片仅携带 `data-id`，详情视图按 id 从当前数据源（内联 today / archive JSON）查找完整对象——不把完整数据塞进 DOM/URL，防注入、无冗余。hash 路由 `#/item/<id>` 支持前进/后退/刷新恢复；id 不存在、archive 404、fetch 失败均有空态提示。
- **底部导航（Modal Bottom Sheet）**：底栏为单胶囊切换器（当前分类 + chevron），点击展开**标准底部抽屉**（圆角顶部 18px + grab handle + 阴影 + 遮罩 + 滑入动画 translateY 100%→0），抽屉内为标题 + 2 列 cat-grid（全部 + 6 分类，含配色点/名称/数量/选中态）。借鉴 GitHub 上 react-native-bottom-action-sheet、Material BottomSheetDialogFragment、Flutter showModalBottomSheet 等开源项目共识——移动端"更多"展开的标准模式。响应式：移动端贴底上滑；桌面端（≥860px）抽屉居中浮起（圆角四周），底栏收束为居中浮条。
- **可配置**：`config.yaml` 调推送时间、领域开关、每领域条数、关键词加权/屏蔽、外文翻译。
- **稳定定时**：GitHub Actions cron（推荐，免费）+ 本地 APScheduler（`--serve`）二选一。
- **多渠道推送**：ntfy / Telegram / 自定义 Webhook，全部可选、失败不中断。
- **去重**：跨源同标题 + 相似度 + 7 天历史，避免重复推送同一事件。关键设计：历史只记录「已推送条目」（`data/history/pushed.json`），而非抓取过的全部条目——否则更新慢的分类（时事/科学/文化）次日会被整体误判为已见、标签没有内容（实测修复前第二天 3 个分类归零）。

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
