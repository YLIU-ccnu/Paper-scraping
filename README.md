# AI for Science arXiv Crawler

一个面向 `AI for Science` 与高价值 `AI methodology` 论文的 arXiv 抓取工具。

它支持：

- 首次运行自动全量初始化
- 后续运行自动增量更新
- 关键词 + 学科分类粗筛
- 可选 AI 二次筛选
- 按主题分类、排序、拆分导出
- 运行摘要与结构化 manifest
- 本地缓存与运行状态管理


## 项目目标

这个项目的目标不是做一个“通用全网论文爬虫”，而是为持续跟踪 `AI for Science` 相关 arXiv 论文建立一个可维护、可扩展、可增量更新的小型工作流。

当前关注的论文范围包括：

- AI/ML 用于科学问题的论文
- 与高能物理、核物理、天文、材料、化学、生物等科学场景相关的 AI 论文
- 具有较强研究价值的 AI 方法论文，即使不直接限定在某一个具体科学领域


## 核心特性

### 1. 自动区分首次全量与后续增量

默认 `crawl mode` 为 `auto`：

- 如果没有历史缓存：执行全量初始化
- 如果已经有历史缓存：执行增量更新

默认策略：

- 首次全量：抓取 `1000` 条
- 后续增量：抓取最近更新窗口内的 `300` 条

增量更新不仅支持 `days_back` 时间窗，也会优先使用“上次成功运行时间”作为水位线，并自动回退几个小时，降低漏抓风险。


### 2. 多层筛选机制

当前筛选分为两层：

- 第一层：基于 arXiv 分类 + 关键词进行高召回粗筛
- 第二层：可选 AI 筛选，对边界样本进一步判断

AI 筛选支持成本控制：

- `all`：所有论文都调用模型
- `borderline`：只对边界样本调用模型
- `none`：不调用模型

默认使用 `borderline`，用于减少模型调用成本。


### 3. 主题分类与导出

每篇论文会被标记为一个 `theme`，当前包括：

- `hybrid`
- `ai_for_science`
- `ai_methodology`
- `science_application`
- `uncategorized`

输出时会：

- 统一排序
- `json` 保留完整详细字段
- `csv` 只保留适合人工浏览的关键字段
- 按主题拆分文件
- 保留总文件


### 4. 运行可追踪

每次运行会生成：

- 主输出文件
- 人工审查专用 `review csv`
- 按主题拆分的输出文件
- 纯文本运行摘要
- 结构化 `manifest`
- 内部缓存和运行状态文件

这样可以清楚知道：

- 本次抓取模式
- 实际抓到多少新论文
- 当前总库大小
- 各主题分布
- 当前审查状态分布
- AI 决策情况
- 本次生成了哪些文件


## 目录结构

```text
.
├── README.md
├── paper_scraping.py
├── library/
│   └── pdfs/
│       └── ...
├── ml_physics_crawler/
│   ├── __init__.py
│   ├── ai_filter.py
│   ├── arxiv.py
│   ├── bibtex.py
│   ├── cli.py
│   ├── constants.py
│   ├── filtering.py
│   ├── inspire.py
│   ├── models.py
│   ├── output.py
│   ├── pdf.py
│   ├── review.py
│   ├── state.py
│   ├── strategy.py
│   ├── text_utils.py
│   ├── zotero.py
│   └── config/
│       └── default_strategy.json
└── tests/
    ├── test_arxiv_parsing.py
    ├── test_core.py
    └── test_inspire.py
```

### 关键模块说明

- `paper_scraping.py`
  项目入口，保持为一个很薄的启动脚本

- `ml_physics_crawler/cli.py`
  命令行参数解析、运行计划决策、摘要与 manifest 生成

- `ml_physics_crawler/arxiv.py`
  arXiv 查询构建、请求、XML 解析、时间窗口过滤

- `ml_physics_crawler/inspire.py`
  INSPIRE 高能方向经典高引初始化抓取与解析

- `ml_physics_crawler/filtering.py`
  粗筛逻辑、主题判定、标签生成、去重

- `ml_physics_crawler/ai_filter.py`
  AI 二次筛选与调用范围控制

- `ml_physics_crawler/output.py`
  导出总文件、主题拆分文件、轻量人工审查 CSV、统一排序

- `ml_physics_crawler/review.py`
  读取和应用人工审查表中的 `approved / rejected / pending` 状态

- `ml_physics_crawler/pdf.py`
  只处理 `approved` 论文的 PDF 下载与按主题分类保存

- `ml_physics_crawler/bibtex.py`
  导出 `approved` 论文的 BibTeX，便于手动导入 Zotero

- `ml_physics_crawler/zotero.py`
  只同步 `approved` 条目的 Zotero 元数据入库与 collection 管理

- `ml_physics_crawler/state.py`
  内部状态目录、缓存文件、运行状态文件管理

- `ml_physics_crawler/config/default_strategy.json`
  外置策略配置，包含关键词、分类、来源过滤规则、查询项、AI prompt、主题顺序


## 安装与依赖

当前最少依赖：

- Python 3.11+
- `requests`

如果使用 AI 筛选，还需要：

- 可用的 OpenAI 兼容接口
- `OPENAI_API_KEY`

示例：

```bash
pip install requests
```


## 运行方式

### 基本运行

```bash
python paper_scraping.py --output-format json --output-file papers.json
```

默认行为：

- 首次运行：自动全量初始化
- 后续运行：自动增量更新


### 常用参数

```bash
python paper_scraping.py --help
```

常用参数包括：

- `--crawl-mode {auto,full,incremental}`
- `--process-approved`
- `--source {arxiv,inspire}`
- `--bootstrap-total-results`
- `--incremental-total-results`
- `--days-back`
- `--incremental-days-back`
- `--output-format {txt,json,csv}`
- `--output-file`
- `--enable-ai-filter`
- `--ai-filter-scope {all,borderline,none}`
- `--ai-model`
- `--ai-base-url`
- `--ai-min-score`
- `--download-approved-pdfs`
- `--pdf-dir`
- `--export-approved-bibtex`
- `--bibtex-file`
- `--sync-zotero`
- `--zotero-library-type {users,groups}`
- `--zotero-library-id`
- `--zotero-api-key`
- `--zotero-collection`
- `--inspire-profile`
- `--inspire-query`
- `--inspire-topcite`
- `--recall-mode {strict,balanced,broad}`


### 示例 1：默认自动模式

```bash
python paper_scraping.py --output-format json --output-file papers.json
```


### 示例 2：强制全量抓取

```bash
python paper_scraping.py \
  --crawl-mode full \
  --bootstrap-total-results 2000 \
  --output-format json \
  --output-file papers.json
```


### 示例 3：强制增量抓取最近 14 天

```bash
python paper_scraping.py \
  --crawl-mode incremental \
  --days-back 14 \
  --incremental-total-results 500 \
  --output-format json \
  --output-file papers.json
```


### 示例 4：启用 AI 二次筛选

```bash
export OPENAI_API_KEY=your_key

python paper_scraping.py \
  --enable-ai-filter \
  --ai-filter-scope borderline \
  --ai-model gpt-4o-mini \
  --ai-min-score 70 \
  --output-format json \
  --output-file papers.json
```


## 输出文件说明

假设输出文件为：

```text
papers.json
```

一次运行后通常会生成：

- `papers.json`
  总输出文件

- `papers.review.csv`
  人工审查工作表，默认包含 `review_status=pending`

- `papers.hybrid.json`
- `papers.ai_for_science.json`
- `papers.ai_methodology.json`
- `papers.science_application.json`
  按主题拆分的输出文件

- `papers.summary.json.txt`
  纯文本运行摘要

- `papers.manifest.json`
  结构化运行记录

内部状态会保存在：

```text
.ml_physics_crawler_state/papers/
```

其中通常包括：

- `records.json`
  内部完整缓存库

- `run_state.json`
  运行状态，包含上次成功抓取时间等信息


## 人工审查工作流

推荐把这个项目接入 Zotero 或 PDF 下载前，先走一轮人工审查：

1. 运行抓取脚本，得到总文件和 `papers.review.csv`
2. 用 Excel、Numbers 或表格工具打开 `papers.review.csv`
3. 只修改这几列：
   - `review_status`：`pending` / `approved` / `rejected`
   - `review_notes`
   - `reviewed_at`
4. 后续增量抓取时，历史记录里的审查状态会被保留，不会因为同一篇论文再次抓到而丢失

这层人工审查的目的，是把“自动抓取结果”与“最终要进入 Zotero 或下载 PDF 的精选文献”分开。


## Approved PDF 下载

当你把 `papers.review.csv` 里的部分论文标记为 `approved` 后，可以在下一次运行时只下载这些论文的 PDF：

```bash
python paper_scraping.py \
  --output-format csv \
  --output-file papers.csv \
  --download-approved-pdfs \
  --pdf-dir library/pdfs
```

如果你不想重新抓 arXiv，只想基于已经抓到的缓存和你改过的审查表做后处理，可以直接运行：

```bash
python paper_scraping.py \
  --process-approved \
  --output-format csv \
  --output-file papers.csv \
  --download-approved-pdfs \
  --pdf-dir library/pdfs
```

这个模式会：

- 读取本地缓存
- 读取 `papers.review.csv`
- 找出 `review_status=approved` 的论文
- 只下载这些 PDF
- 不重新联网抓取新论文

默认会按 `theme` 分类保存到：

```text
library/pdfs/
  hybrid/
  ai_for_science/
  ai_methodology/
  science_application/
```

这样后面不管是继续人工阅读，还是接入 Zotero collection，都可以直接基于这些目录继续做。


## Approved BibTeX 导出

如果你想先把精选论文手动导入 Zotero，而不是直接走 API，同样可以基于审查表导出 `approved` 的 BibTeX：

```bash
python paper_scraping.py \
  --process-approved \
  --output-format csv \
  --output-file papers.csv \
  --export-approved-bibtex
```

默认会额外生成：

```text
papers.approved.bib
```

这个文件只包含 `review_status=approved` 的论文，可以直接在 Zotero 中通过 `File -> Import` 导入。


## Approved Zotero 同步

如果你希望把 `approved` 论文直接同步到 Zotero，而不是手动导入 BibTeX，可以使用内置的 Zotero 同步：

```bash
export ZOTERO_API_KEY=your_key

python paper_scraping.py \
  --process-approved \
  --output-format csv \
  --output-file papers.csv \
  --sync-zotero \
  --zotero-library-type users \
  --zotero-library-id your_user_id \
  --zotero-collection "AI for Science"
```

当前这一步的策略是：

- 只同步 `review_status=approved` 的论文
- 只同步元数据，不自动上传 PDF 附件
- 会按 `theme` 和已有标签写入 Zotero tags
- 如果指定的 collection 不存在，会自动创建
- 会优先用 `DOI`、其次 `arXiv ID`、最后 `title` 做去重


## 筛选与增量更新逻辑

### 首次运行

- 如果没有缓存文件，默认走全量模式
- 抓取 `bootstrap_total_results`
- 不使用最近天数限制
- 建立完整本地缓存

如果你是高能方向，也可以把首次初始化改成 `INSPIRE` 经典高引模式：

```bash
python paper_scraping.py \
  --source inspire \
  --crawl-mode full \
  --total-results 50 \
  --inspire-profile classic_seed \
  --output-format csv \
  --output-file papers.csv
```

这条路径更适合先建立“小而精”的经典文献库。

当前内置了几组 INSPIRE 模板，放在：

- `ml_physics_crawler/config/inspire_profiles.json`

这些模板现在已经偏向：

- 高能物理
- 神经网络 / 深度学习
- 尽量减少纯贝叶斯或泛统计学习噪音

常用模板包括：

- `hep_default`
- `lhc_ml`
- `jet_reco_ml`
- `heavy_ion_ml`
- `hep_theory_ml`
- `classic_seed`

例如：

```bash
python paper_scraping.py \
  --source inspire \
  --crawl-mode full \
  --total-results 50 \
  --inspire-profile lhc_ml \
  --output-format csv \
  --output-file papers.csv
```

如果你确实想手写 query，仍然可以继续使用 `--inspire-query`。

### 后续运行

- 如果检测到缓存，默认走增量模式
- 优先读取上次成功运行时间 `last_successful_run_at`
- 自动回退几个小时作为安全水位线
- 如果没有水位线，则退回到 `incremental_days_back`
- 抓到的新记录会与历史缓存合并，再统一去重

后续增量更新建议继续使用 `arXiv`：

```bash
python paper_scraping.py \
  --source arxiv \
  --crawl-mode incremental \
  --output-format csv \
  --output-file papers.csv
```

当前实现里，`INSPIRE` 主要用于 `full` 初始化，不建议用于 `incremental` 追新。


## 策略配置

项目中的大部分策略已经外置到：

- `ml_physics_crawler/config/default_strategy.json`

你可以在这个文件中调整：

- 学科分类
- ML 分类
- 科学关键词
- AI/ML 关键词
- arXiv 查询项
- AI 筛选 prompt
- 主题顺序与标题

如果你要调整方向，优先修改这个 JSON，而不是直接改 Python 主逻辑。


## 测试

当前项目已包含基础单元测试，覆盖：

- 粗筛逻辑
- 主题分类
- 输出排序与拆分
- 运行摘要与 manifest
- 自动运行计划
- arXiv XML 解析
- 时间窗口过滤
- 内部状态文件逻辑

运行方式：

```bash
python -m unittest discover -s tests -v
```


## 已实现的工程能力

当前项目已经具备这些能力：

- 模块化架构
- 外置策略配置
- 自动全量/增量抓取
- 水位线增量更新
- AI 成本控制
- 主题分类与拆分导出
- 运行摘要
- manifest 记录
- 本地缓存与状态管理
- 人工审查工作流
- 基础测试


## 后续可继续完善的方向

- 抓取失败 batch 与重试统计写入 manifest
- 更细粒度的 AI 调用策略
- 支持多数据源，而不仅限于 arXiv
- 增加日志文件而不仅是摘要
- 为解析和状态逻辑补更多边界测试
- 支持自定义外部配置文件路径


## 备注

当前这个项目默认优先服务“持续跟踪论文”的工作流，而不是一次性离线抓全量数据库。

推荐使用方式是：

1. 第一次运行，建立完整初始库
2. 之后每天或每周运行一次
3. 通过总文件、分主题文件、summary 和 manifest 持续跟踪更新
