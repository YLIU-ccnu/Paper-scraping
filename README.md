# Paper Scraping

一个面向高能物理与神经网络/深度学习交叉方向的论文抓取工具。

它现在支持：

- `INSPIRE` 初始化经典高引论文
- `arXiv` 增量追踪最新论文
- 关键词 + 分类粗筛
- 可选 AI 二次筛选
- `json / csv / txt` 导出
- 人工审查工作流
- Approved PDF 下载
- Approved BibTeX 导出
- Approved Zotero 同步
- 邮件提醒
- 本地定时检查与自动运行


## 这个项目适合做什么

推荐把它当成一个“论文工作流”而不是单纯爬虫：

1. 先初始化一批值得读的论文
2. 后续定期追踪新论文
3. 人工审核
4. 决定是否下载 PDF / 导出 Zotero

当前最适合的主线是：

- `INSPIRE`：抓高能方向经典高引论文
- `arXiv`：抓后续新增更新


## 5 分钟上手

### 1. 安装依赖

最少依赖：

- Python 3.11+
- `requests`

```bash
pip install requests
```

如果要启用 AI 审查，还需要：

- `OPENAI_API_KEY`
- 可用的 OpenAI 兼容接口


### 2. 首次初始化

用 `INSPIRE` 抓一批高能 + 神经网络相关的经典论文：

```bash
mkdir -p results

python paper_scraping.py \
  --source inspire \
  --crawl-mode full \
  --total-results 50 \
  --inspire-profile classic_seed \
  --output-format csv \
  --output-file results/papers.csv
```


### 3. 后续增量更新

用 `arXiv` 继续追踪新增论文：

```bash
python paper_scraping.py \
  --source arxiv \
  --crawl-mode incremental \
  --output-format csv \
  --output-file results/papers.csv
```


### 4. 人工审核

打开：

- [results/papers.review.csv](/Users/yliu/爬虫文献/results/papers.review.csv)

只改这三列：

- `review_status`
- `review_notes`
- `reviewed_at`

其中最重要的是：

- `review_status = pending / approved / rejected`


## 常用工作流

### 工作流 A：初始化经典论文

```bash
python paper_scraping.py \
  --source inspire \
  --crawl-mode full \
  --total-results 50 \
  --inspire-profile classic_seed \
  --output-format csv \
  --output-file results/papers.csv
```

适合：

- 第一次建库
- 抓高能 + 神经网络方向的代表性工作


### 工作流 B：增量追新

```bash
python paper_scraping.py \
  --source arxiv \
  --crawl-mode incremental \
  --output-format csv \
  --output-file results/papers.csv
```

默认会优先根据上次成功运行时间继续补抓，而不是简单固定回看最近几天。


### 工作流 C：按时间窗抓取，且不设条数上限

如果你想补抓某个时间窗里的全部相关结果，而不想被固定条数截断：

```bash
python paper_scraping.py \
  --source arxiv \
  --crawl-mode incremental \
  --no-total-limit \
  --output-format csv \
  --output-file results/papers.csv
```

注意：

- `--no-total-limit` 只在 `arXiv` 的时间窗抓取里生效
- 不会影响 full 初始化的默认上限


### 工作流 D：启用 AI 审查

`INSPIRE` 和 `arXiv` 都支持 AI 二次筛选。

```bash
python paper_scraping.py \
  --source inspire \
  --crawl-mode full \
  --total-results 50 \
  --inspire-profile classic_seed \
  --enable-ai-filter \
  --ai-filter-scope borderline \
  --output-format csv \
  --output-file results/papers.csv
```

AI 审查范围：

- `all`
- `borderline`
- `none`


### 工作流 E：邮件提醒

先配置 SMTP 环境变量：

```bash
export SMTP_HOST=smtp.example.com
export SMTP_USER=your_email@example.com
export SMTP_PASSWORD=your_app_password
export MAIL_FROM=your_email@example.com
export MAIL_TO=your_email@example.com
```

然后运行：

```bash
python paper_scraping.py \
  --source arxiv \
  --crawl-mode incremental \
  --output-format csv \
  --output-file results/papers.csv \
  --enable-email-notification
```

邮件正文会逐篇列出本次新增论文的：

- `theme`
- `title`
- `authors`
- `abstract`
- `pdf_url`


## 输出文件

假设输出文件是：

```text
results/papers.csv
```

一次运行后通常会得到：

- `results/papers.csv`
  总表，适合快速浏览

- `results/papers.review.csv`
  审查表，适合人工修改 `review_status`

- `results/papers.<theme>.csv`
  按主题拆分的文件

- `results/papers.manifest.json`
  结构化运行记录

- `results/papers.summary.csv.txt`
  文本运行摘要

内部状态保存在：

- `.ml_physics_crawler_state/<stem>/records.json`
- `.ml_physics_crawler_state/<stem>/run_state.json`


## 人工审查后处理

### 下载 Approved PDF

```bash
python paper_scraping.py \
  --process-approved \
  --output-format csv \
  --output-file results/papers.csv \
  --download-approved-pdfs \
  --pdf-dir library/pdfs
```

### 导出 Approved BibTeX

```bash
python paper_scraping.py \
  --process-approved \
  --output-format csv \
  --output-file results/papers.csv \
  --export-approved-bibtex
```

### 同步 Approved 到 Zotero

```bash
export ZOTERO_API_KEY=your_key

python paper_scraping.py \
  --process-approved \
  --output-format csv \
  --output-file results/papers.csv \
  --sync-zotero \
  --zotero-library-type users \
  --zotero-library-id your_user_id \
  --zotero-collection "AI for Science"
```


## 本地定时方案

如果你希望“本地自动运行”，但又不想因为电脑偶尔关机而漏掉更新，项目里已经内置了一套更稳的方案：

- 系统每天检查一次
- 只有距离上次成功运行已满 `5` 天，才真正执行抓取

这样不是死板按固定日历点每 5 天触发，而是按：

- `run_state.json` 里的 `last_successful_run_at`

来判断是否该运行。

项目里提供了：

- [scripts/run_if_due.py](/Users/yliu/爬虫文献/scripts/run_if_due.py)
- [launchd/com.paper-scraping.update.plist](/Users/yliu/爬虫文献/launchd/com.paper-scraping.update.plist)

### 手动检查一次

```bash
python scripts/run_if_due.py
```

### 可配置环境变量

- `PAPER_UPDATE_INTERVAL_DAYS`
  默认 `5`

- `PAPER_OUTPUT_FILE`
  默认 `results/papers.csv`

- `PYTHON_BIN`
  默认当前 Python

- `PAPER_EXTRA_ARGS`
  会附加到抓取命令末尾  
  例如：
  - `--enable-email-notification`
  - `--enable-ai-filter --ai-filter-scope borderline`

示例：

```bash
export PAPER_UPDATE_INTERVAL_DAYS=5
export PAPER_OUTPUT_FILE=/Users/yliu/爬虫文献/results/papers.csv
export PAPER_EXTRA_ARGS="--enable-email-notification --enable-ai-filter --ai-filter-scope borderline"
python scripts/run_if_due.py
```

### macOS launchd

模板文件：

- [launchd/com.paper-scraping.update.plist](/Users/yliu/爬虫文献/launchd/com.paper-scraping.update.plist)

默认行为：

- 每天 `09:00` 检查一次
- 是否真正抓取，由 `run_if_due.py` 决定

安装示例：

```bash
mkdir -p ~/Library/LaunchAgents
cp launchd/com.paper-scraping.update.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.paper-scraping.update.plist
```

停用：

```bash
launchctl unload ~/Library/LaunchAgents/com.paper-scraping.update.plist
```


## 配置文件

配置文件统一放在：

- [ml_physics_crawler/config](/Users/yliu/爬虫文献/ml_physics_crawler/config)

当前主要有两个：

- [default_strategy.json](/Users/yliu/爬虫文献/ml_physics_crawler/config/default_strategy.json)
  负责全局规则：
  - `ml_keywords`
  - `science_keywords`
  - `ml_categories`
  - `science_categories`
  - `source_filters`
  - `arxiv_query_ml_terms`
  - `inspire_default_query`

- [inspire_profiles.json](/Users/yliu/爬虫文献/ml_physics_crawler/config/inspire_profiles.json)
  负责 `INSPIRE` 初始化模板：
  - `classic_seed`
  - `hep_default`
  - `lhc_ml`
  - `jet_reco_ml`
  - `heavy_ion_ml`
  - `hep_theory_ml`

简单理解：

- 想改“什么算神经网络/深度学习相关”：改 `default_strategy.json`
- 想改“INSPIRE 初始化用什么查询模板”：改 `inspire_profiles.json`
- 想改“某个来源必须满足什么条件才保留”：改 `default_strategy.json` 里的 `source_filters`


## 项目结构

```text
.
├── README.md
├── paper_scraping.py
├── launchd/
│   └── com.paper-scraping.update.plist
├── scripts/
│   └── run_if_due.py
├── ml_physics_crawler/
│   ├── ai_filter.py
│   ├── arxiv.py
│   ├── bibtex.py
│   ├── cli.py
│   ├── filtering.py
│   ├── inspire.py
│   ├── mailer.py
│   ├── models.py
│   ├── output.py
│   ├── pdf.py
│   ├── review.py
│   ├── scheduler.py
│   ├── state.py
│   ├── strategy.py
│   ├── text_utils.py
│   ├── zotero.py
│   └── config/
│       ├── default_strategy.json
│       └── inspire_profiles.json
└── tests/
    ├── test_arxiv_parsing.py
    ├── test_core.py
    └── test_inspire.py
```


## 常用参数

```bash
python paper_scraping.py --help
```

常用参数：

- `--source {arxiv,inspire}`
- `--crawl-mode {auto,full,incremental}`
- `--total-results`
- `--no-total-limit`
- `--days-back`
- `--incremental-days-back`
- `--output-format {txt,json,csv}`
- `--output-file`
- `--enable-ai-filter`
- `--ai-filter-scope {all,borderline,none}`
- `--enable-email-notification`
- `--download-approved-pdfs`
- `--export-approved-bibtex`
- `--sync-zotero`
- `--inspire-profile`
- `--inspire-query`
- `--inspire-topcite`
- `--recall-mode {strict,balanced,broad}`


## 测试

```bash
python -m unittest discover -s tests -v
```


## 说明

这个项目现在已经更偏“高能物理 + 神经网络/深度学习”工作流，而不是泛 AI for Science 抓取器。

如果你后面想重新放宽方向，优先改配置文件，不建议直接改主流程代码。
