# GitHub Trending 每日精选系统设计

> 扩展 `ai-wechat-digest` 项目，新增 GitHub 高星仓库监控 → 主题过滤 → Claude 中文摘要 → HTML 图文报告 → 飞书推送 pipeline。

## 整体架构

```
[采集器] → [过滤/排序器] → [摘要生成器] → [HTML 渲染器] → [分发器]
   ↓            ↓              ↓              ↓             ↓
trending.json  ranked.json   summaries.json  report.html   飞书通知
```

模块间通过 JSON 文件传递数据，存储在 `data/YYYY-MM-DD/` 目录下。入口脚本 `main_github.py` 按顺序调用各模块，支持 `--step collector` 单独运行某一步。本地 launchd 定时触发（复用现有 launchd 配置模式）。

## 模块一：采集器 (Collector)

两路并行采集，合并去重。

### GitHub Trending 爬取

- HTTP 抓取 `github.com/trending` 页面，解析 HTML
- 支持按语言、时间范围（daily/weekly）过滤
- 提取字段：仓库名、描述、星标数、今日新增星标、主要语言

### GitHub Search API

- `GET /search/repositories`
- 查询条件：`created:>={7天前}` + `stars:>=50` + 关键词
- 按 stars 降序，使用 Personal Access Token 提高 rate limit（30次/分钟）

### 数据差异处理

- Trending 页面直接提供 `stars_today` 字段
- Search API 不提供每日增星数，`stars_today` 置为 0（排序时仅依赖总星标和创建时间）

### 去重与输出

- 两路数据按 `owner/repo` 去重（若重复，优先保留 Trending 数据，因为有 `stars_today`）
- 与 SQLite 已推送记录对比，排除已推送过的仓库
- 输出 `data/YYYY-MM-DD/trending.json`

```json
[
  {
    "full_name": "owner/repo",
    "description": "...",
    "stars": 1234,
    "stars_today": 89,
    "language": "Python",
    "url": "https://github.com/owner/repo",
    "source": "trending|search",
    "created_at": "2026-06-08"
  }
]
```

### 错误处理

- Trending 页面结构变化 → 解析失败时 log 警告，降级为只用 Search API
- API rate limit → 退避重试，最多 3 次

## 模块二：过滤/排序器 (Ranker)

### 关键词配置

```json
{
  "topics": {
    "ai_llm": ["llm", "agent", "rag", "prompt", "fine-tune", "inference", "transformer"],
    "dev_tools": ["cli", "plugin", "skill", "neovim", "vscode", "devtools", "copilot", "claude code", "codex"]
  }
}
```

匹配范围：仓库名、description、topics 标签。

### 相关性打分

- 关键词命中数 × 权重
- 今日新增星标数（归一化）
- 仓库创建时间越新加分越多（偏好新项目）

### 异常检测

今日新增星标 > 200 或 24 小时内创建且星标 > 100 → 标记 `highlight: true`，后续做深度分析。

### 输出

按综合分降序取 top-5（K 值可配置），输出 `data/YYYY-MM-DD/ranked.json`：

```json
[
  {
    "full_name": "owner/repo",
    "score": 0.87,
    "matched_topics": ["ai_llm"],
    "matched_keywords": ["agent", "rag"],
    "highlight": false,
    "stars": 1234,
    "stars_today": 89
  }
]
```

## 模块三：摘要生成器 (Summarizer)

### 处理流程

对每个仓库：

1. GitHub API 获取 README（`GET /repos/{owner}/{repo}/readme`，Base64 解码）
2. 根据 `highlight` 标记选择 prompt 深度：
   - 普通：翻译 README 核心内容，提取项目定位、功能亮点、技术栈，200-300 字中文摘要
   - highlight：额外分析仓库结构（tree API），给出"为什么值得关注"的点评，400-500 字
3. 让 Claude 额外输出 Mermaid 图表代码（系统架构图/数据流图），用于 HTML 渲染

### LLM 配置

```json
{
  "llm": {
    "provider": "openai_compatible",
    "model": "claude-opus-4-7",
    "base_url": "https://ai.t8star.org",
    "api_key": "从配置或环境变量读取"
  }
}
```

使用 OpenAI 兼容接口格式调用。provider 抽象为统一的 `generate(prompt, content)` 函数，切换 provider 只需改配置。

API key 优先级：环境变量 `LLM_API_KEY` > config.json 中的 `llm.api_key` 字段。

### 输出

`data/YYYY-MM-DD/summaries.json`：

```json
[
  {
    "full_name": "owner/repo",
    "title": "项目中文名/简称",
    "one_liner": "一句话概括",
    "summary": "详细中文摘要...",
    "highlights": ["亮点1", "亮点2"],
    "tech_stack": ["Python", "FastAPI"],
    "why_notable": "仅 highlight 项目有此字段",
    "stars": 1234,
    "stars_today": 89,
    "url": "https://github.com/owner/repo",
    "diagrams": [
      {
        "title": "系统架构",
        "mermaid": "graph TD\n  A[用户] --> B[API]..."
      }
    ]
  }
]
```

### 错误处理

- README 为空或获取失败 → 用 description 作为降级输入
- API 调用失败 → 重试 2 次，仍失败则跳过并 log 警告
- README 超长 → 截取前 8000 字符

## 模块四：HTML 渲染器 (Renderer)

### 页面结构

- 顶部：日期标题 + 今日精选概览
- 主体：每个仓库一张卡片
  - 项目名 + GitHub 链接
  - 星标数 + 今日增长（趋势图标）
  - 技术栈标签
  - 中文摘要
  - Mermaid 架构图（1-2 张）
  - highlight 项目有特殊样式（金色边框 + "值得关注"角标）
- 底部：历史报告导航

### 视觉风格

- 单文件 HTML（CSS 内联），Mermaid.js 为唯一外部 CDN 依赖
- 暗色/亮色双主题（prefers-color-scheme 自适应）
- 卡片式布局，圆角 + 阴影
- 移动端响应式

### 技术实现

- Jinja2 模板引擎，模板文件 `templates/report.html`
- Mermaid.js CDN 引入，`<div class="mermaid">` 客户端渲染 SVG
- 输出到 `docs/reports/YYYY-MM-DD.html`
- 同时更新 `docs/reports/index.html` 目录页

## 模块五：分发器 (Distributor)

### GitHub Pages 部署

1. 将 HTML 写入 `docs/reports/YYYY-MM-DD.html`
2. 更新 `docs/reports/index.html`（追加今日链接）
3. `git add → commit → push` 到 main 分支
4. Pages 自动部署，URL：`https://{user}.github.io/{repo}/reports/YYYY-MM-DD.html`

### 飞书机器人推送

使用飞书自定义机器人 webhook，发送 Interactive Card：

```json
{
  "msg_type": "interactive",
  "card": {
    "header": {
      "title": "GitHub 每日精选 | 2026-06-10",
      "template": "blue"
    },
    "elements": [
      {
        "tag": "markdown",
        "content": "今日发现 5 个值得关注的项目：\n\n**1. owner/repo** - 一句话摘要\n⭐ 1234 (+89 today)\n\n..."
      },
      {
        "tag": "action",
        "actions": [
          {
            "tag": "button",
            "text": "查看完整报告",
            "url": "https://...github.io/.../2026-06-10.html"
          }
        ]
      }
    ]
  }
}
```

### 配置

```json
{
  "feishu_webhook": "https://open.feishu.cn/open-apis/bot/v2/hook/xxx",
  "github_pages_base_url": "https://user.github.io/repo/reports"
}
```

### 错误处理

- push 失败 → 重试一次，仍失败则发送降级内容到飞书
- 飞书 webhook 失败 → 重试 2 次，log 告警

## 配置文件结构

`config.json` 完整结构：

```json
{
  "github_token": "ghp_xxx",
  "topics": {
    "ai_llm": ["llm", "agent", "rag", "prompt", "fine-tune", "inference", "transformer"],
    "dev_tools": ["cli", "plugin", "skill", "neovim", "vscode", "devtools", "copilot", "claude code", "codex"]
  },
  "top_k": 5,
  "llm": {
    "provider": "openai_compatible",
    "model": "claude-opus-4-7",
    "base_url": "https://ai.t8star.org",
    "api_key": "sk-xxx"
  },
  "feishu_webhook": "https://open.feishu.cn/open-apis/bot/v2/hook/xxx",
  "github_pages_base_url": "https://user.github.io/ai-wechat-digest/reports",
  "schedule": "daily"
}
```

## 定时调度

复用现有 launchd plist 模式，新增一个 plist 文件 `launchd/com.user.github-digest.plist`，每天早上 9:00 触发 `python3 main_github.py`。
