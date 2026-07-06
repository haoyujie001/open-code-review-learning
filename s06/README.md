# 从 0 学习 Alibaba Open Code Review（六）：JSON 输出结构与 Markdown 报告设计
## 一、前言

前面几篇已经把 OpenCodeReview 的几个核心点串起来了：

- 第一篇：跑通最小 Demo，知道 `ocr review` 能审查 Git diff。
- 第二篇：从 CLI 入口追踪 `ocr review` 的执行流程。
- 第三篇：理解 Git diff 如何决定审查范围。
- 第四篇：理解 `.opencodereview/rule.json` 如何影响规则加载。
- 第五篇：分析 Agent 工具调用，理解 `file_read`、`file_find`、`file_read_diff`、`code_search`、`code_comment` 的作用。

这一篇继续往后看：OpenCodeReview 审查完成后，结果是如何以 JSON 形式输出的？JSON 里有哪些字段？这些字段又怎样支撑后续的 Markdown 报告、GitHub Actions、PR 评论和自己的 Code Review Agent MVP？

这篇文章的目标不是只会执行一条命令，而是把 `ocr review --format json` 背后的数据结构看懂。

## 二、本篇学习目标

本篇主要解决 5 个问题：

1. `ocr review --format json` 输出了什么？
2. `summary`、`tool_calls`、`comments` 分别表示什么？
3. 评论里的 `start_line`、`end_line` 是怎么来的？
4. JSON 输出和普通终端输出有什么区别？
5. 为什么 JSON 输出是后续 Agent 项目的基础？



## 三、先确认当前 Demo 的 Review 输入

进入练习仓库：

```powershell
cd D:\agent\open-code-review-main\ocr-practice-demo
```

先执行 preview，看当前 Git diff 会审查哪些文件：

```powershell
ocr review --preview
```

输出的关键信息是：

```text
Preview: 2 file(s) changed  |  +45  -1

Will review (2):
  [M]  s01/src/user.js            +4   -1
  [A]  outputs-review-result.json +41  -0
```

这里有一个小细节：`outputs-review-result.json` 也被纳入了本次 diff。

原因是它本身是新增文件，并且还没有被 Git 忽略或提交。也就是说，OpenCodeReview 是基于 Git diff 判断审查范围的，只要文件出现在 diff 里，就有可能进入审查范围。

所以后面真正做工程化项目时，生成物最好放到 `outputs/` 目录，并通过 `.gitignore` 或规则 exclude 排除掉，否则下一次 Review 可能会把上一次生成的 JSON 报告也当作代码变更来审查。

## 四、生成 JSON 审查结果

OpenCodeReview 支持用 `--format json` 输出结构化结果：

```powershell
ocr review --format json > ocr-review-result.json
```

也可以把输出保存到自己的结果文件里：

```powershell
ocr review --format json > outputs-review-result.json
```

本文使用本地已有的两份结果样例进行分析：

```text
D:\agent\open-code-review-main\ocr-practice-demo\ocr-review-result.json
D:\agent\open-code-review-main\ocr-practice-demo\outputs-review-result.json
```

其中一份 JSON 的整体结构如下：

```json
{
  "status": "success",
  "summary": {
    "files_reviewed": 2,
    "comments": 2,
    "total_tokens": 65929,
    "input_tokens": 61803,
    "output_tokens": 4126,
    "cache_read_tokens": 35328,
    "elapsed": "1m33s"
  },
  "tool_calls": {
    "total": 14,
    "by_tool": {
      "code_comment": 2,
      "code_search": 3,
      "file_find": 1,
      "file_read": 6,
      "file_read_diff": 2
    }
  },
  "comments": [
    {
      "path": "s01/src/user.js",
      "content": "**SQL Injection Vulnerability**: ...",
      "suggestion_code": "db.query('UPDATE users SET email = $1 WHERE id = $2', [email, userId]);",
      "existing_code": "db.query(\"UPDATE users SET email = '\" + email + \"' WHERE id = \" + userId);",
      "start_line": 37,
      "end_line": 37
    }
  ]
}
```

可以看到，JSON 输出不是一段自然语言总结，而是分成了三个核心部分：

- `summary`：本次审查的统计信息。
- `tool_calls`：Agent 工具调用统计。
- `comments`：具体代码审查意见。

这三个部分正好对应一个 Code Review Agent 最关心的三类数据：运行成本、执行过程、审查结论。

## 五、从源码定位 JSON 输出入口

前面第二篇已经追过 `ocr review` 的 CLI 入口，这一篇继续往输出方向追。

和最终输出相关的核心文件是：

```text
cmd/opencodereview/shared.go
cmd/opencodereview/output.go
internal/model/review.go
internal/diff/resolver.go
```

其中 `shared.go` 里有一个关键函数：

```go
func emitRunResult(
    ctx context.Context,
    ag ResultProvider,
    comments []model.LlmComment,
    startTime time.Time,
    outputFormat, audience string,
    q *quietHandle,
) error {
    comments = diff.ResolveLineNumbers(comments, ag.Diffs())

    duration := time.Since(startTime)

    if outputFormat == "json" && len(comments) == 0 && ag.FilesReviewed() == 0 {
        return outputJSONNoFiles()
    }

    if outputFormat == "json" {
        return outputJSONWithWarnings(comments, ag.Warnings(), ag.FilesReviewed(),
            ag.TotalInputTokens(), ag.TotalOutputTokens(), ag.TotalTokensUsed(),
            ag.TotalCacheReadTokens(), ag.TotalCacheWriteTokens(), duration,
            ag.ProjectSummary(), ag.ToolCalls())
    }

    outputTextWithWarnings(comments, ag.Warnings())
    return nil
}
```

这段逻辑说明了三件事：

1. 最终输出前会先调用 `diff.ResolveLineNumbers` 补齐评论行号。
2. 如果 `--format json`，最终会走 `outputJSONWithWarnings`。
3. 如果不是 JSON，则走普通的文本输出 `outputTextWithWarnings`。

所以可以画出一条简化链路：

```text
ocr review
  ↓
Agent Run
  ↓
生成 comments
  ↓
ResolveLineNumbers 补齐行号
  ↓
outputJSONWithWarnings
  ↓
stdout 输出 JSON
```

## 六、JSON 顶层结构 jsonOutput

在 `cmd/opencodereview/output.go` 里，JSON 输出对应的结构体是 `jsonOutput`：

```go
type jsonOutput struct {
    Status         string               `json:"status"`
    Message        string               `json:"message,omitempty"`
    Summary        *jsonSummary         `json:"summary,omitempty"`
    ToolCalls      *jsonToolCalls       `json:"tool_calls"`
    Comments       []model.LlmComment   `json:"comments"`
    Warnings       []agent.AgentWarning `json:"warnings,omitempty"`
    ProjectSummary string               `json:"project_summary,omitempty"`
}
```

字段含义可以这样理解：

| 字段 | 含义 |
|---|---|
| `status` | 本次运行状态，例如 `success` 或 `skipped` |
| `message` | 补充提示信息，没有时省略 |
| `summary` | 本次审查的统计数据 |
| `tool_calls` | Agent 工具调用统计 |
| `comments` | 具体审查评论列表 |
| `warnings` | 非致命警告 |
| `project_summary` | 项目级总结，`review` 模式下一般为空，`scan` 场景更常见 |

这里有一个细节：很多字段带了 `omitempty`。

这意味着字段为空时不会出现在 JSON 里。例如没有 warning 时不会输出 `warnings`，没有项目总结时不会输出 `project_summary`。

## 七、summary：本次审查的运行统计

`summary` 对应源码里的 `jsonSummary`：

```go
type jsonSummary struct {
    FilesReviewed    int64  `json:"files_reviewed"`
    Comments         int64  `json:"comments"`
    TotalTokens      int64  `json:"total_tokens"`
    InputTokens      int64  `json:"input_tokens"`
    OutputTokens     int64  `json:"output_tokens"`
    CacheReadTokens  int64  `json:"cache_read_tokens,omitempty"`
    CacheWriteTokens int64  `json:"cache_write_tokens,omitempty"`
    Elapsed          string `json:"elapsed"`
}
```

本地样例：

```json
"summary": {
  "files_reviewed": 2,
  "comments": 2,
  "total_tokens": 65929,
  "input_tokens": 61803,
  "output_tokens": 4126,
  "cache_read_tokens": 35328,
  "elapsed": "1m33s"
}
```

这些字段对工程化很有价值：

| 字段 | 说明 | 可以用来做什么 |
|---|---|---|
| `files_reviewed` | 实际审查的文件数量 | 判断本次 Review 范围大小 |
| `comments` | 生成的评论数量 | 判断是否发现问题 |
| `total_tokens` | 总 token 消耗 | 估算成本 |
| `input_tokens` | 输入 token | 判断上下文是否过大 |
| `output_tokens` | 输出 token | 判断模型生成量 |
| `cache_read_tokens` | 命中缓存读取的 token | 判断缓存收益 |
| `cache_write_tokens` | 写入缓存的 token | 判断缓存写入情况 |
| `elapsed` | 审查耗时 | 用于 CI 耗时统计 |

如果后面要做自己的 Agent 项目，这些字段可以直接进入运行报告，例如：

```markdown
## Review Summary

- Files reviewed: 2
- Comments: 2
- Total tokens: 65929
- Elapsed: 1m33s
```

## 八、tool_calls：Agent 工具调用统计

第五篇已经分析过 OpenCodeReview 的工具调用机制。第六篇要关注的是：这些工具调用最后也会进入 JSON 输出。

源码中的结构是：

```go
type jsonToolCalls struct {
    Total  int64            `json:"total"`
    ByTool map[string]int64 `json:"by_tool"`
}
```

本地样例：

```json
"tool_calls": {
  "total": 14,
  "by_tool": {
    "code_comment": 2,
    "code_search": 3,
    "file_find": 1,
    "file_read": 6,
    "file_read_diff": 2
  }
}
```

这说明本次审查过程中，Agent 一共调用了 14 次工具：

- `file_read` 调用 6 次，说明模型多次读取文件上下文。
- `file_read_diff` 调用 2 次，说明模型读取了 diff 内容。
- `code_search` 调用 3 次，说明模型主动搜索了相关代码。
- `file_find` 调用 1 次，说明模型查找过文件。
- `code_comment` 调用 2 次，说明最终产出了 2 条评论。

这也是 OpenCodeReview 和“把 diff 直接丢给大模型”的核心区别之一：它不是单轮 Prompt，而是带工具调用轨迹的 Agent 审查流程。

对自己的项目来说，`tool_calls` 可以用于生成执行过程摘要：

```markdown
## Tool Calls

| Tool | Count |
|---|---:|
| file_read | 6 |
| file_read_diff | 2 |
| code_search | 3 |
| file_find | 1 |
| code_comment | 2 |
```

## 九、comments：真正的审查结果

`comments` 是最重要的部分，因为它包含了真正需要开发者处理的问题。

本地样例中，一条评论大概长这样：

```json
{
  "path": "s01/src/user.js",
  "content": "**SQL Injection Vulnerability**: The `email` and `userId` parameters are directly concatenated into the SQL query string...",
  "suggestion_code": "db.query('UPDATE users SET email = $1 WHERE id = $2', [email, userId]);",
  "existing_code": "db.query(\"UPDATE users SET email = '\" + email + \"' WHERE id = \" + userId);",
  "start_line": 37,
  "end_line": 37
}
```

每个字段的作用如下：

| 字段 | 含义 |
|---|---|
| `path` | 问题所在文件路径 |
| `content` | 审查意见正文 |
| `suggestion_code` | 建议修改后的代码，可能为空 |
| `existing_code` | 被审查的原始代码片段 |
| `start_line` | 问题开始行号 |
| `end_line` | 问题结束行号 |

对后续工程化来说，`comments` 是最重要的数据源。

因为 Markdown 报告、PR 评论、风险分级、人工确认、审查历史，基本都要围绕 `comments` 展开。

## 十、LlmComment：评论数据模型

`comments` 的元素类型是 `model.LlmComment`，定义在 `internal/model/review.go`：

```go
type LlmComment struct {
    Path           string `json:"path"`
    Content        string `json:"content"`
    SuggestionCode string `json:"suggestion_code,omitempty"`
    ExistingCode   string `json:"existing_code,omitempty"`
    StartLine      int    `json:"start_line"`
    EndLine        int    `json:"end_line"`
    Thinking       string `json:"thinking,omitempty"`
}
```

这里可以注意几个点：

1. `path` 和 `content` 是最基础的评论信息。
2. `suggestion_code` 和 `existing_code` 是可选字段，空时不会输出。
3. `start_line` 和 `end_line` 是定位评论位置的关键。
4. `thinking` 也是可选字段，默认不会总是出现。

如果后面要把评论发布到 GitHub PR，至少需要这几个字段：

```text
path
start_line / end_line
content
```

如果还想做自动修复建议，就需要额外使用：

```text
existing_code
suggestion_code
```

## 十一、评论行号是怎么来的

这一点非常关键。

模型生成评论时，不一定总能稳定给出准确行号。因此 OpenCodeReview 在最终输出前，会做一次行号解析：

```go
comments = diff.ResolveLineNumbers(comments, ag.Diffs())
```

`ResolveLineNumbers` 定义在 `internal/diff/resolver.go`，它的核心思路是：

1. 先根据 diff 建立文件路径到 diff 的映射。
2. 对每条评论，优先用 `existing_code` 去 diff hunk 里匹配。
3. 如果 diff hunk 里匹配不到，再回退到新文件完整内容里逐行匹配。
4. 匹配成功后，补齐 `start_line` 和 `end_line`。

源码注释里也明确说明：

```go
// ResolveLineNumbers populates StartLine/EndLine on each comment by matching
// the ExistingCode against the corresponding file's diff hunks (primary), or
// falling back to scanning the full new-file content line-by-line.
```

这说明 `existing_code` 不只是展示给用户看的字段，它还是定位行号的重要依据。

所以如果后续我们自己设计 Agent 输出格式，也应该保留 `existing_code`，否则后面做 PR 行内评论会困难很多。

## 十二、JSON 输出和普通文本输出的区别

OpenCodeReview 默认终端输出更适合人直接看，而 JSON 输出更适合程序继续处理。

| 对比项 | 普通文本输出 | JSON 输出 |
|---|---|---|
| 阅读对象 | 人 | 程序和人都可以 |
| 结构化程度 | 较弱 | 强 |
| 是否适合二次处理 | 不适合 | 适合 |
| 是否适合生成 Markdown | 需要解析文本 | 直接解析字段 |
| 是否适合 GitHub Actions | 一般 | 很适合 |
| 是否适合 Agent MVP | 不适合 | 很适合 |

后续做自己的项目时，更建议基于 JSON 输出，而不是解析终端文本。

终端文本适合学习和调试，JSON 才适合工程化。

## 十三、warnings 和 status 怎么理解

JSON 顶层还有两个容易忽略的字段：`status` 和 `warnings`。

正常审查成功时：

```json
{
  "status": "success"
}
```

如果没有可审查文件，源码里会走 `outputJSONNoFiles`：

```go
func outputJSONNoFiles() error {
    out := jsonOutput{
        Status:   "skipped",
        Message:  "No supported files changed.",
        Comments: []model.LlmComment{},
        ToolCalls: &jsonToolCalls{
            ByTool: map[string]int64{},
        },
    }
    ...
}
```

结合 `outputJSONWithWarnings` 的源码，`status` 常见可以分成几类：

| 状态 | 出现场景 |
|---|---|
| `success` | 正常完成，没有 warning |
| `completed_with_warnings` | 审查完成，但存在非致命 warning |
| `completed_with_errors` | 审查过程中部分子任务失败，但整体仍输出了结果 |
| `skipped` | 没有可审查文件 |

`warnings` 用来记录非致命问题。例如某个文件读取失败、某些上下文无法获取、某些工具调用不完整等。它不一定导致整个 Review 失败，但应该在报告里保留下来。

如果自己生成 Markdown 报告，可以加一个 warning 区域：

```markdown
## Warnings

- xxx warning message
```

这样 CI 里即使 Review 没有完全失败，也能看到潜在问题。

## 十四、从 JSON 生成 Markdown 报告

理解 JSON 结构后，下一步就很自然：写一个脚本读取 JSON，然后生成 Markdown 报告。

最小报告结构可以这样设计：

````markdown
# AI Code Review Report

## Summary

- Status: success
- Files reviewed: 2
- Comments: 2
- Total tokens: 65929
- Elapsed: 1m33s

## Tool Calls

| Tool | Count |
|---|---:|
| file_read | 6 |
| file_read_diff | 2 |
| code_search | 3 |
| file_find | 1 |
| code_comment | 2 |

## Findings

### 1. s01/src/user.js:37-37

**Issue**

SQL Injection Vulnerability...

**Existing Code**

```js
db.query("UPDATE users SET email = '" + email + "' WHERE id = " + userId);
```

**Suggestion**

```js
db.query('UPDATE users SET email = $1 WHERE id = $2', [email, userId]);
```
````

这个 Markdown 报告就是后续 Agent 项目的第一个可交付物。

它比直接看 JSON 更适合放到 GitHub Actions artifact、README 示例、博客截图和简历项目展示里。

## 十五、Markdown 报告的字段映射

从 JSON 到 Markdown 的映射关系可以这样设计：

| JSON 字段 | Markdown 位置 |
|---|---|
| `status` | Summary 里的运行状态 |
| `summary.files_reviewed` | Summary 里的文件数量 |
| `summary.comments` | Summary 里的问题数量 |
| `summary.total_tokens` | Summary 里的 token 消耗 |
| `summary.elapsed` | Summary 里的耗时 |
| `tool_calls.by_tool` | Tool Calls 表格 |
| `comments[].path` | Findings 标题 |
| `comments[].start_line` | Findings 标题里的行号 |
| `comments[].end_line` | Findings 标题里的行号 |
| `comments[].content` | Issue 正文 |
| `comments[].existing_code` | Existing Code 代码块 |
| `comments[].suggestion_code` | Suggestion 代码块 |
| `warnings` | Warnings 区域 |

这个映射越稳定，后面的工程越容易扩展。

## 十六、为什么 JSON 输出适合做 Agent MVP

如果只看 OpenCodeReview 本身，它已经可以完成 AI Code Review。

但如果想做一个能写进简历的 Agent 项目，只调用 CLI 还不够。我们需要把它封装成一个自己的工作流：

```text
Git diff
  ↓
Run OpenCodeReview
  ↓
Parse JSON
  ↓
Normalize Findings
  ↓
Generate Markdown Report
  ↓
Save History / GitHub Actions Artifact
```

这里的关键节点就是 `Parse JSON`。

因为 JSON 把 OpenCodeReview 的运行结果变成了标准输入数据，我们可以继续做很多事情：

- 生成 Markdown 报告。
- 根据 `comments` 做风险分级。
- 根据 `tool_calls` 生成 Agent 执行轨迹。
- 根据 `summary.total_tokens` 做成本统计。
- 根据 `path/start_line/end_line` 发布 GitHub PR 评论。
- 根据历史 JSON 做审查质量评估。

第六篇不是孤立的一篇，而是从“源码学习”进入“自研 Agent 项目”的转折点。

## 十七、后续 Agent 项目可以怎么设计

基于这一篇的 JSON 输出，第一版 MVP 可以设计成：

```text
Git diff
  ↓
Run OCR
  ↓
Parse JSON
  ↓
Generate Markdown Report
```

对应目录结构可以是：

```text
open-code-review-agent-mvp
├── agent_graph.py
├── tools
│   ├── git_tools.py
│   ├── ocr_tools.py
│   └── report_tools.py
├── outputs
│   ├── review-result.json
│   └── review-report.md
├── README.md
└── requirements.txt
```

模块职责可以先保持简单：

| 模块 | 职责 |
|---|---|
| `git_tools.py` | 检测当前 Git diff 和变更文件 |
| `ocr_tools.py` | 调用 `ocr review --format json` 并保存结果 |
| `report_tools.py` | 解析 JSON 并生成 Markdown 报告 |
| `agent_graph.py` | 串联整个流程 |

第一版不要一上来就做多 Agent、RAG、MCP、Tracing。

更合理的顺序是：先把 JSON 到 Markdown 跑通，再逐步加 LangGraph、风险分级、GitHub Actions、PR 自动评论。

## 十八、本篇用到的命令

本文实际用到的命令如下：

```powershell
cd D:\agent\open-code-review-main\ocr-practice-demo
```

```powershell
ocr review --preview
```

```powershell
Get-Content .\ocr-review-result.json
```

```powershell
Get-Content .\outputs-review-result.json
```

源码定位命令：

```powershell
Select-String -Path D:\agent\open-code-review-main\cmd\opencodereview\output.go -Pattern "type jsonSummary|type jsonToolCalls|type jsonOutput|outputJSONWithWarnings|outputJSONNoFiles" -Context 0,25
```

```powershell
Select-String -Path D:\agent\open-code-review-main\cmd\opencodereview\shared.go -Pattern "emitRunResult|ResolveLineNumbers|outputJSONWithWarnings|outputTextWithWarnings" -Context 0,18
```

```powershell
Get-Content D:\agent\open-code-review-main\internal\model\review.go
```

```powershell
Get-Content D:\agent\open-code-review-main\internal\diff\resolver.go
```

## 十九、本篇总结

这一篇主要学习了 OpenCodeReview 的 JSON 输出结构。

核心结论有 5 个：

1. `ocr review --format json` 输出的是结构化审查结果，不是普通日志文本。
2. JSON 顶层主要包含 `status`、`summary`、`tool_calls`、`comments`、`warnings`、`project_summary`。
3. `summary` 记录文件数量、评论数量、token 消耗和耗时，适合做运行统计。
4. `tool_calls` 记录 Agent 工具调用次数，适合展示 Agent 执行轨迹。
5. `comments` 是最核心的审查结果，可以直接用于 Markdown 报告、PR 评论和风险分级。

从源码看，最终输出前还有一个重要步骤：

```text
comments = diff.ResolveLineNumbers(comments, ag.Diffs())
```

也就是说，OpenCodeReview 会尽量根据 `existing_code` 和 diff 内容补齐评论行号。

这也是为什么 JSON 里的 `existing_code`、`start_line`、`end_line` 对后续工程化非常重要。

## 二十、下一篇计划

下一篇可以正式进入自己的项目：

```text
从 0 学 OpenCodeReview：设计一个 Code Review Agent MVP
```

下一篇重点不再只是读源码，而是开始设计自己的 Agent 工程：

```text
Git diff
  ↓
Run OCR
  ↓
Parse JSON
  ↓
Generate Markdown Report
```
