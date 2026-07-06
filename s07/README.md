
# 从 0 学习 Alibaba Open Code Review（七）：设计一个 Code Review Agent MVP
## 一、前言

前面六篇已经把 OpenCodeReview 的核心链路基本走了一遍。

前六篇主要做了这些事：

1. 跑通最小 Demo，知道 `ocr review` 可以审查 Git diff。
2. 从源码入口理解 `ocr review` 命令如何执行。
3. 学习 Git diff，理解 OpenCodeReview 如何确定审查范围。
4. 学习 `.opencodereview/rule.json`，理解自定义规则如何影响审查重点。
5. 学习 Agent 工具调用，理解 `file_read`、`file_find`、`file_read_diff`、`code_search`、`code_comment` 的作用。
6. 学习 JSON 输出结构，理解 `summary`、`tool_calls`、`comments` 如何支撑后续工程化。

到这里，已经可以从“学习 OpenCodeReview”进入下一步：基于 OpenCodeReview 做一个自己的 Agent 项目。

这一篇的目标，就是设计并搭建一个最小可运行的 Code Review Agent MVP。
## 二、本篇要解决的问题

这一篇主要解决 5 个问题：

1. 为什么要在 OpenCodeReview 之上再做一个 Agent 项目？
2. 这个项目和 OpenCodeReview 是什么关系？
3. MVP 第一版应该做什么，不应该做什么？
4. 代码目录应该怎么拆分？
5. 如何把 `Git diff -> OCR JSON -> Markdown Report` 跑成一个完整工作流？

这篇不是要重新实现 OpenCodeReview。

OpenCodeReview 本身已经完成了最复杂的部分：

- Git diff 解析
- 规则加载
- Agent 工具调用
- LLM Code Review
- JSON 结构化输出

我自己的项目要做的是：把 OpenCodeReview 封装成一个更工程化的 Agent Workflow。

## 三、项目和 OpenCodeReview 的关系



这个 MVP 不是 OpenCodeReview 的源码改造，也不是仿写 OpenCodeReview。

更准确的关系是：

```text
OpenCodeReview
  = 底层 AI Code Review 引擎 / Review Backend

open-code-review-agent-mvp
  = 上层 Agent Workflow 封装
```

也就是说：

```text
OpenCodeReview 负责真正的 AI 审查
本 Agent 项目负责编排审查流程、保存结果、生成报告、为后续 CI 和 PR 评论做准备
```

可以画成这样：

```text
Git Repository
  ↓
open-code-review-agent-mvp
  ↓ 调用
OpenCodeReview CLI
  ↓ 输出
review-result.json
  ↓ 解析
review-report.md
```

所以这个项目不是脱离 OpenCodeReview 的第一版，而是先依赖 OpenCodeReview 做出工程闭环。

后面如果要进一步升级，可以把 OpenCodeReview 抽象成一个可替换的 Review Backend。

## 四、为什么不直接改 OpenCodeReview 源码

如果直接改 OpenCodeReview 源码，问题会比较多：

1. OpenCodeReview 是 Go 项目，改动成本高。
2. 它本身已经有清晰的 CLI、Agent、Tool、Output 结构。
3. 目标不是贡献 OCR 内核功能，而是做一个可展示的 Agent 工程项目。


所以更合理的方式是：

```text
不改 OCR 内核
只调用 OCR CLI
基于 JSON 输出做上层工作流
```

这样做有几个好处：

- 项目边界清楚。
- 代码量可控。
- 后续容易接 LangGraph、GitHub Actions、PR 评论和多 Agent。

## 五、MVP 第一版目标

第一版 MVP 不追求复杂，只追求跑通一个闭环。

目标流程是：

```text
Git diff
  ↓
Run OpenCodeReview
  ↓
Parse JSON
  ↓
Generate Markdown Report
```

对应到代码，就是：

```text
检查 Git 变更
  ↓
调用 ocr review --format json
  ↓
保存 outputs/review-result.json
  ↓
解析 JSON 字段
  ↓
生成 outputs/review-report.md
```

第一版只要做到这几件事，就已经是一个完整的 Agent Workflow MVP。

## 六、MVP 第一版暂时不做什么

这一点也很重要。

第一版暂时不做：

- 不引入 LangGraph。
- 不做多 Agent。
- 不做 MCP Server。
- 不做 RAG 规则库。
- 不自动发布 GitHub PR 评论。
- 不做复杂历史记录系统。
- 不重新实现 OpenCodeReview 的 diff parser 和 tool calling。

原因很简单：MVP 的重点是先跑通闭环。



正确路线应该是：

```text
V1：线性 Workflow，跑通 Git diff -> OCR -> JSON -> Markdown
V2：引入 LangGraph，增加状态管理和风险分级
V3：接入 GitHub Actions、审查历史、人工确认
V4：抽象 ReviewBackend，支持 OCR / 自研 Reviewer / 静态扫描器
```

## 七、项目目录结构

项目放在：

```text
D:\agent\open-code-review-agent-mvp
```

当前目录结构是：

```text
open-code-review-agent-mvp
├── agent_graph.py
├── tools
│   ├── __init__.py
│   ├── git_tools.py
│   ├── ocr_tools.py
│   └── report_tools.py
├── README.md
├── requirements.txt
└── .gitignore
```

运行后会生成：

```text
outputs
├── review-result.json
└── review-report.md
```

每个文件的职责如下：

| 文件 | 职责 |
|---|---|
| `agent_graph.py` | 工作流入口，串联 Git、OCR、Report |
| `tools/git_tools.py` | 封装 Git 命令，检测仓库和变更文件 |
| `tools/ocr_tools.py` | 调用 OpenCodeReview CLI，保存并解析 JSON |
| `tools/report_tools.py` | 把 OCR JSON 转成 Markdown 报告 |
| `.gitignore` | 排除输出文件和 Python 缓存 |
| `README.md` | 说明项目定位、运行方式和后续规划 |

### 7.1 每个代码文件的职责总览

如果只看目录结构，还不够清楚每个文件为什么存在。

这个项目不是把所有逻辑都写到 `agent_graph.py` 里，而是拆成了四层：

```text
Git 输入层：tools/git_tools.py
OCR 执行层：tools/ocr_tools.py
报告输出层：tools/report_tools.py
流程编排层：agent_graph.py
```

更完整的职责表如下：

| 文件 | 核心作用 | 为什么这样写 |
|---|---|---|
| `agent_graph.py` | 串联整个 Agent Workflow | 把流程编排和具体工具实现分离，后续方便升级 LangGraph |
| `tools/git_tools.py` | 负责 Git 仓库检测和变更文件获取 | Git 输入是 Review 的起点，单独封装方便测试和复用 |
| `tools/ocr_tools.py` | 负责调用 `ocr review --format json` | 把 OpenCodeReview 当作 Review Backend，不侵入 OCR 源码 |
| `tools/report_tools.py` | 负责 JSON 到 Markdown 报告 | 报告生成是纯本地逻辑，应该和 OCR 调用解耦 |
| `tools/__init__.py` | 标记 `tools` 为 Python 包 | 让 `agent_graph.py` 可以清晰导入工具模块 |
| `.gitignore` | 排除缓存、环境文件和输出文件 | 避免生成的 JSON/Markdown 再进入下一次 diff |
| `README.md` | 项目说明文档 | 用于 GitHub 展示和简历项目入口 |
| `requirements.txt` | 记录依赖 | 当前只用标准库，但保留依赖入口，后续接 LangGraph 时方便扩展 |

这样拆分之后，项目结构会比较清楚：

```text
agent_graph.py 只负责“流程怎么走”
git_tools.py 只负责“Git 输入从哪里来”
ocr_tools.py 只负责“怎么调用 OCR”
report_tools.py 只负责“怎么生成报告”
```

不是简单写一个脚本，而是把输入、执行、输出和编排拆开。

### 7.2 agent_graph.py：流程编排层

`agent_graph.py` 是整个项目的入口。

它最核心的代码有两块：

第一块是 `AgentState`：

```python
@dataclass
class AgentState:
    repo_dir: Path
    output_dir: Path
    review_json_path: Path
    review_report_path: Path
    changed_files: list[str] = field(default_factory=list)
    review_data: dict[str, Any] = field(default_factory=dict)
```

它负责保存整个工作流的状态。

第二块是 `run_workflow`：

```python
def run_workflow(...):
    repo_root = ensure_git_repo(repo_dir)
    state.changed_files = get_changed_files(repo_root)

    if use_existing_json:
        state.review_data = load_review_json(use_existing_json)
    elif not state.changed_files:
        state.review_data = skipped_result
    else:
        state.review_data = run_ocr_review(...)

    markdown = generate_markdown_report(state.review_data, changed_files=state.changed_files)
    save_markdown_report(markdown, state.review_report_path)
    return state
```

为什么这样写？

因为 `agent_graph.py` 不应该关心 Git 命令怎么执行，也不应该关心 OCR JSON 怎么解析，更不应该关心 Markdown 每一行怎么拼。

它只需要回答一个问题：

```text
这个 Agent Workflow 应该按什么顺序执行？
```

所以它只负责编排：

```text
检查仓库
  ↓
获取变更
  ↓
运行 OCR 或读取已有 JSON
  ↓
生成 Markdown 报告
```

后续如果引入 LangGraph，`run_workflow` 可以自然拆成多个节点：

```text
check_git_node
run_ocr_node
parse_json_node
generate_report_node
```

### 7.3 tools/git_tools.py：Git 输入层

`git_tools.py` 负责和 Git 交互。

核心函数之一是 `run_git`：

```python
def run_git(repo_dir: str | Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    repo_path = Path(repo_dir).resolve()
    command = ["git", "-C", str(repo_path), *args]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise GitCommandError(command, result.returncode, result.stdout, result.stderr)
    return result
```

这里统一封装 Git 命令，有两个好处：

1. 所有 Git 命令都通过同一个入口执行。
2. Git 失败时可以统一抛出 `GitCommandError`。

另一个核心函数是 `ensure_git_repo`：

```python
def ensure_git_repo(repo_dir: str | Path) -> Path:
    repo_path = Path(repo_dir).resolve()
    result = run_git(repo_path, ["rev-parse", "--is-inside-work-tree"])
    if result.stdout.strip() != "true":
        raise RuntimeError(f"{repo_path} is not inside a Git work tree")
    root = run_git(repo_path, ["rev-parse", "--show-toplevel"]).stdout.strip()
    return Path(root).resolve()
```

它用来确认目标目录是不是 Git 仓库，并且拿到仓库根目录。

获取变更文件使用：

```python
def get_changed_files(repo_dir: str | Path) -> list[str]:
    result = run_git(repo_dir, ["status", "--porcelain"])
```

这里选择 `git status --porcelain`，而不是普通的 `git status`。

原因是：

```text
普通 git status 是给人看的
--porcelain 是给程序解析的
```

这就是为什么 Git 逻辑要单独放到 `git_tools.py`：Git 是整个 Review 的输入层，输入层越稳定，后面的 OCR 和报告生成越可靠。

### 7.4 tools/ocr_tools.py：OCR 执行层

`ocr_tools.py` 是这个项目和 OpenCodeReview 连接的地方。

它的核心不是重写 OCR，而是构造并执行 OCR 命令。

命令构造函数是：

```python
def build_ocr_review_command(
    ocr_bin: str = "ocr",
    excludes: list[str] | None = None,
    extra_args: list[str] | None = None,
) -> list[str]:
    command = [ocr_bin, "review", "--format", "json"]

    normalized_excludes = [item for item in (excludes or []) if item]
    if normalized_excludes:
        command.extend(["--exclude", ",".join(normalized_excludes)])

    if extra_args:
        command.extend(extra_args)

    return command
```

默认命令是：

```powershell
ocr review --format json
```

如果加上排除目录，就会变成：

```powershell
ocr review --format json --exclude outputs/**
```

真正执行命令的是 `run_ocr_review`：

```python
result = subprocess.run(
    command,
    cwd=repo_path,
    capture_output=True,
    text=True,
    timeout=timeout_seconds,
)
```

这里必须处理三件事：

1. `stdout`：OCR 成功时的 JSON 输出。
2. `stderr`：OCR 失败时的错误信息。
3. `returncode`：判断命令是否成功。

所以代码里有：

```python
if result.returncode != 0:
    error_file = output_file.with_suffix(".stderr.txt")
    error_file.write_text(result.stderr, encoding="utf-8")
    raise OcrCommandError(command, result.returncode, result.stdout, result.stderr)
```

为什么这样写？

因为 OCR 是一个外部命令，不是普通函数调用。外部命令可能失败，可能超时，可能输出不是合法 JSON。

所以 `ocr_tools.py` 的职责就是把这个不稳定边界包起来，让上层 `agent_graph.py` 拿到稳定的结构化结果。

### 7.5 tools/report_tools.py：报告输出层

`report_tools.py` 是纯本地逻辑。

它不调用 Git，也不调用 OCR，只做一件事：

```text
把 OCR JSON 转成 Markdown 报告
```

核心函数是：

```python
def generate_markdown_report(review_data: dict[str, Any], changed_files: list[str] | None = None) -> str:
    status = review_data.get("status", "unknown")
    message = review_data.get("message", "")
    summary = review_data.get("summary") or {}
    tool_calls = review_data.get("tool_calls") or {}
    comments = review_data.get("comments") or []
    warnings = review_data.get("warnings") or []
```

这几个字段正好来自第六篇分析过的 OCR JSON：

```text
status
message
summary
tool_calls
comments
warnings
```

每条评论由 `render_comment` 负责渲染：

```python
def render_comment(index: int, comment: dict[str, Any]) -> list[str]:
    path = comment.get("path", "unknown")
    start_line = comment.get("start_line", 0)
    end_line = comment.get("end_line", start_line)
    content = comment.get("content", "").strip() or "(empty comment)"
    existing_code = comment.get("existing_code", "")
    suggestion_code = comment.get("suggestion_code", "")
```

它把一条 OCR comment 转成 Markdown 的一条 Finding：

```text
文件路径 + 行号
问题说明
原始代码
建议代码
```

为什么报告生成要单独拆出来？

因为报告生成不依赖 OCR 执行。

只要有一份合法的 OCR JSON，就可以反复生成 Markdown 报告。这样调试报告格式时，不需要反复调用 LLM。

这就是 `--use-existing-json` 能成立的原因。

### 7.6 .gitignore：为什么要排除 outputs

`.gitignore` 里最关键的是：

```text
outputs/
*.review.json
*.review.md
```

为什么要这样写？

因为前面第六篇已经发现：如果生成的 JSON 文件没有被忽略，它会进入下一次 Git diff。

也就是说，本来只想审查业务代码，结果 OCR 可能会把上一次生成的报告文件也纳入审查范围。

所以 MVP 一开始就要排除输出文件。

这不是可有可无的小细节，而是 AI Code Review 工程化时必须处理的问题。

### 7.7 README.md 和 requirements.txt 的作用

`README.md` 是 GitHub 项目的入口。

它需要讲清楚：

```text
这个项目是什么
依赖什么
怎么运行
输出什么
后续怎么扩展
```

`requirements.txt` 当前只有一行说明：

```text
# MVP uses only Python standard library modules.
```

因为当前版本只使用 Python 标准库，不需要安装第三方依赖。

但后面如果加入 LangGraph、Pydantic、Rich、OpenTelemetry，就可以直接在这里维护依赖。

### 7.8 为什么要这样拆模块

这套拆分背后的思路是：

```text
输入、执行、输出、编排分离
```

对应关系是：

```text
Git 输入层       -> git_tools.py
OCR 执行层       -> ocr_tools.py
报告输出层      -> report_tools.py
Agent 编排层    -> agent_graph.py
```

如果把所有代码都写在 `agent_graph.py` 里，第一版可能也能跑，但是后面会很难扩展。

例如：

- 想换 Git 检测方式，会影响 OCR 和报告逻辑。
- 想替换 OCR 后端，会影响主流程。
- 想修改 Markdown 格式，可能误伤 Git 或 OCR 调用。
- 想引入 LangGraph，需要重新拆代码。

现在这样拆开之后，每个模块只负责自己的边界：

```text
git_tools.py 只管 Git
ocr_tools.py 只管 OCR
report_tools.py 只管报告
agent_graph.py 只管编排
```

这也是这个 MVP 比普通脚本更像工程项目的地方。

虽然现在还没有使用 LangGraph，但我仍然把入口文件命名为 `agent_graph.py`。

原因是后面升级到 LangGraph 时，这个文件可以自然演进成真正的 graph workflow。

## 八、整体流程设计

从用户视角看，只需要执行：

```powershell
python agent_graph.py --repo D:\agent\open-code-review-main\ocr-practice-demo
```

内部执行流程是：

```text
run_workflow
  ↓
ensure_git_repo
  ↓
get_changed_files
  ↓
run_ocr_review
  ↓
load / parse review JSON
  ↓
generate_markdown_report
  ↓
save_markdown_report
```

这个流程对应的模块关系是：

```text
agent_graph.py
  ├── git_tools.py
  │     ├── ensure_git_repo
  │     └── get_changed_files
  │
  ├── ocr_tools.py
  │     ├── run_ocr_review
  │     ├── load_review_json
  │     └── parse_review_json_text
  │
  └── report_tools.py
        ├── generate_markdown_report
        └── save_markdown_report
```

这就是第一版 Agent Workflow。

## 九、AgentState 设计

`agent_graph.py` 里定义了一个 `AgentState`：

```python
@dataclass
class AgentState:
    repo_dir: Path
    output_dir: Path
    review_json_path: Path
    review_report_path: Path
    changed_files: list[str] = field(default_factory=list)
    review_data: dict[str, Any] = field(default_factory=dict)
```

这个结构很重要。

它保存了整个 Workflow 的状态：

| 字段 | 含义 |
|---|---|
| `repo_dir` | 被审查的 Git 仓库路径 |
| `output_dir` | 输出目录 |
| `review_json_path` | OCR JSON 结果路径 |
| `review_report_path` | Markdown 报告路径 |
| `changed_files` | 当前 Git 变更文件列表 |
| `review_data` | 解析后的 OCR JSON 数据 |

为什么要设计 `AgentState`？

因为一个 Agent Workflow 通常不是只有一个函数，而是多个节点共享状态。

现在的版本是线性流程：

```text
Git Node -> OCR Node -> Report Node
```

未来升级成 LangGraph 后，`AgentState` 可以直接演进成图状态：

```text
StateGraph(AgentState)
```

所以现在虽然没有引入 LangGraph，但代码已经提前保留了状态管理思路。

## 十、run_workflow：工作流主入口

`run_workflow` 是整个 MVP 的核心函数。

简化后可以理解为：

```python
def run_workflow(repo_dir, output_dir="outputs", use_existing_json=None):
    repo_root = ensure_git_repo(repo_dir)
    changed_files = get_changed_files(repo_root)

    if use_existing_json:
        review_data = load_review_json(use_existing_json)
    elif not changed_files:
        review_data = skipped_result
    else:
        review_data = run_ocr_review(repo_root)

    markdown = generate_markdown_report(review_data, changed_files)
    save_markdown_report(markdown)
```

真实代码里有三个分支：

### 1. 使用已有 JSON

```python
if use_existing_json:
    state.review_data = load_review_json(use_existing_json)
```

这个分支主要用于学习和测试。

因为每次完整执行 OCR 都会调用 LLM，可能消耗接口额度。所以开发报告生成逻辑时，可以先复用已有的 OCR JSON。

### 2. 当前没有 Git 变更

```python
elif not state.changed_files:
    state.review_data = {
        "status": "skipped",
        "message": "No Git changes detected by the wrapper.",
        "tool_calls": {"total": 0, "by_tool": {}},
        "comments": [],
    }
```

这个分支避免没有变更时还去调用 LLM。

从工程角度看，这是一个很必要的保护。

### 3. 正常调用 OCR

```python
else:
    state.review_data = run_ocr_review(
        repo_dir=repo_root,
        output_path=state.review_json_path,
        ocr_bin=ocr_bin,
        excludes=excludes or ["outputs/**"],
        timeout_seconds=timeout_seconds,
    )
```

这个分支才是真正运行 OpenCodeReview。

它会调用：

```powershell
ocr review --format json
```

然后把结果保存为：

```text
outputs/review-result.json
```

最后生成：

```text
outputs/review-report.md
```

## 十一、git_tools.py：封装 Git 输入

`git_tools.py` 的职责是处理 Git 相关能力。

它主要做三件事：

1. 判断目标目录是否是 Git 仓库。
2. 获取 Git 仓库根目录。
3. 获取当前变更文件列表。

核心函数是：

```python
def ensure_git_repo(repo_dir: str | Path) -> Path:
    repo_path = Path(repo_dir).resolve()
    result = run_git(repo_path, ["rev-parse", "--is-inside-work-tree"])
    if result.stdout.strip() != "true":
        raise RuntimeError(f"{repo_path} is not inside a Git work tree")
    root = run_git(repo_path, ["rev-parse", "--show-toplevel"]).stdout.strip()
    return Path(root).resolve()
```

这里用到的 Git 命令是：

```powershell
git rev-parse --is-inside-work-tree
```

用于判断当前目录是否在 Git 仓库中。

然后用：

```powershell
git rev-parse --show-toplevel
```

拿到仓库根目录。

获取变更文件使用：

```python
def get_changed_files(repo_dir: str | Path) -> list[str]:
    result = run_git(repo_dir, ["status", "--porcelain"])
```

这里用的是：

```powershell
git status --porcelain
```

为什么不用自然语言解析 `git status`？

因为普通 `git status` 是给人看的，而 `--porcelain` 是给程序解析的，格式更稳定。

这也是工程化里一个很重要的习惯：程序尽量使用机器友好的输出格式。

## 十二、ocr_tools.py：封装 OpenCodeReview CLI

`ocr_tools.py` 是这个项目和 OpenCodeReview 连接的地方。

它不重新实现 OCR 的 Agent 能力，只调用 OCR CLI。

核心命令构造函数是：

```python
def build_ocr_review_command(
    ocr_bin: str = "ocr",
    excludes: list[str] | None = None,
    extra_args: list[str] | None = None,
) -> list[str]:
    command = [ocr_bin, "review", "--format", "json"]

    normalized_excludes = [item for item in (excludes or []) if item]
    if normalized_excludes:
        command.extend(["--exclude", ",".join(normalized_excludes)])

    if extra_args:
        command.extend(extra_args)

    return command
```

默认生成的命令是：

```powershell
ocr review --format json
```

如果传入排除规则，会生成类似：

```powershell
ocr review --format json --exclude outputs/**
```

前面第六篇已经发现一个问题：生成的 `outputs-review-result.json` 可能会进入下一次 diff。

所以这个 MVP 默认排除：

```text
outputs/**
```

这就是从前面学习中提炼出来的工程化细节。

## 十三、为什么要处理 returncode、stdout、stderr

`run_ocr_review` 里使用了：

```python
result = subprocess.run(
    command,
    cwd=repo_path,
    capture_output=True,
    text=True,
    timeout=timeout_seconds,
)
```

这里有几个关键点：

| 参数 | 作用 |
|---|---|
| `cwd=repo_path` | 在目标 Git 仓库里执行 OCR |
| `capture_output=True` | 捕获 stdout 和 stderr |
| `text=True` | 按文本读取输出 |
| `timeout=timeout_seconds` | 避免命令无限卡住 |

OpenCodeReview 的 JSON 输出在 `stdout`。

如果执行失败，错误通常会出现在 `stderr`，并且进程返回码不是 0。

所以代码里必须判断：

```python
if result.returncode != 0:
    error_file = output_file.with_suffix(".stderr.txt")
    error_file.write_text(result.stderr, encoding="utf-8")
    raise OcrCommandError(command, result.returncode, result.stdout, result.stderr)
```

这样做的好处是：

1. OCR 成功时，保存 JSON。
2. OCR 失败时，保存错误信息。
3. 上层调用可以明确知道失败原因。
4. 后续接 GitHub Actions 时，失败日志可以作为 artifact 保留。

这比简单地调用一条命令更工程化。

## 十四、Windows 下 JSON 编码问题

实际测试时遇到了一个很真实的问题。

用 PowerShell 重定向保存 JSON 时：

```powershell
ocr review --format json > outputs-review-result.json
```

这个文件有可能不是 UTF-8，而是 UTF-16。

如果 Python 直接这样读：

```python
Path(path).read_text(encoding="utf-8")
```

可能会报错：

```text
UnicodeDecodeError: 'utf-8' codec can't decode byte 0xff in position 0
```

所以 `ocr_tools.py` 里加了一个编码兜底函数：

```python
def read_text_with_fallback(path: str | Path) -> str:
    data = Path(path).read_bytes()
    for encoding in ("utf-8", "utf-8-sig", "utf-16", "utf-16-le", "utf-16-be"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("unknown", data, 0, min(len(data), 1), "unsupported text encoding")
```

这个细节看起来很小，但对工程项目很重要。

因为真实项目经常不是“代码逻辑错了”，而是被编码、路径、换行、命令输出这些环境问题卡住。

这个问题也说明：写 Agent 工程不能只关注大模型，还要处理好系统边界。

## 十五、report_tools.py：把 JSON 转成 Markdown

`report_tools.py` 的职责是把 OCR JSON 变成更适合人看的 Markdown 报告。

核心函数是：

```python
def generate_markdown_report(review_data: dict[str, Any], changed_files: list[str] | None = None) -> str:
    status = review_data.get("status", "unknown")
    message = review_data.get("message", "")
    summary = review_data.get("summary") or {}
    tool_calls = review_data.get("tool_calls") or {}
    comments = review_data.get("comments") or []
    warnings = review_data.get("warnings") or []
```

这里解析的字段，正好对应第六篇学过的 JSON 结构：

| OCR JSON 字段 | Markdown 报告位置 |
|---|---|
| `status` | 报告顶部状态 |
| `message` | 报告提示信息 |
| `summary` | Summary 区域 |
| `tool_calls.by_tool` | Tool Calls 表格 |
| `warnings` | Warnings 区域 |
| `comments` | Findings 区域 |

生成后的报告结构大概是：

```text
# AI Code Review Report

## Summary

## Changed Files

## Tool Calls

## Warnings

## Project Summary

## Findings
```

其中 `Findings` 是最重要的部分。

每条评论会被渲染成：

````markdown
### 1. `s01/src/user.js:37-37`

**Issue**

SQL Injection Vulnerability...

**Existing Code**

```js
...
```

**Suggestion**

```js
...
```
````

为了避免代码块里本身包含反引号导致 Markdown 混乱，代码里还做了一个处理：

```python
def fenced_code(code: str, language: str = "") -> str:
    fence = "```"
    if "```" in code:
        fence = "````"
    return f"{fence}{language}\n{code.rstrip()}\n{fence}"
```

这也是工程化细节：不能假设模型输出的代码永远不会破坏 Markdown 格式。

## 十六、为什么要有 use_existing_json 模式

`agent_graph.py` 支持一个参数：

```powershell
--use-existing-json
```

例如：

```powershell
python -B D:\agent\open-code-review-agent-mvp\agent_graph.py `
  --repo D:\agent\open-code-review-main\ocr-practice-demo `
  --output-dir "C:\Users\ad\Documents\New project\mvp-test-output-final" `
  --use-existing-json D:\agent\open-code-review-main\ocr-practice-demo\outputs-review-result.json
```

这个参数的作用是：不重新调用 OCR，只读取已有 JSON，然后生成 Markdown 报告。

为什么需要这个模式？

因为完整的 OCR Review 会调用 LLM，可能消耗接口额度，也可能受网络影响。

在开发报告生成逻辑时，不应该每次都重新调用 LLM。

所以可以先用已有 JSON 做离线测试。

这也是一个成熟工程习惯：把“外部昂贵调用”和“本地纯逻辑处理”拆开。

## 十七、实际测试结果

我用已有 OCR JSON 做了一次测试。

执行命令：

```powershell
python -B D:\agent\open-code-review-agent-mvp\agent_graph.py --repo D:\agent\open-code-review-main\ocr-practice-demo --output-dir "C:\Users\ad\Documents\New project\mvp-test-output-final" --use-existing-json D:\agent\open-code-review-main\ocr-practice-demo\outputs-review-result.json
```

输出结果：

```text
Code Review Agent MVP finished.
Repo: D:\agent\open-code-review-main\ocr-practice-demo
Changed files: 2
JSON: C:\Users\ad\Documents\New project\mvp-test-output-final\review-result.json
Report: C:\Users\ad\Documents\New project\mvp-test-output-final\review-report.md
```

说明这个 MVP 的链路已经跑通：

```text
已有 OCR JSON
  ↓
解析 JSON
  ↓
生成 Markdown Report
```

如果要调用 OpenCodeReview，可以执行：

```powershell
python -B D:\agent\open-code-review-agent-mvp\agent_graph.py --repo D:\agent\open-code-review-main\ocr-practice-demo
```

这会触发：

```powershell
ocr review --format json --exclude outputs/**
```

并生成：

```text
outputs/review-result.json
outputs/review-report.md
```

## 十八、.gitignore 的设计

项目里的 `.gitignore` 包含：

```text
__pycache__/
*.py[cod]
.pytest_cache/
.mypy_cache/
.ruff_cache/
.venv/
venv/
.env
outputs/
*.review.json
*.review.md
```

这里重点是：

```text
outputs/
*.review.json
*.review.md
```

原因前面已经遇到过：生成的 JSON 和 Markdown 报告如果没有忽略，下一次 Git diff 可能会把它们纳入审查范围。

所以从第一版 MVP 开始，就应该把输出文件排除掉。

这也是第六篇学习结果在第七篇里的实际应用。

## 十九、这个项目为什么可以叫 Agent MVP

严格来说，第一版不是复杂的多 Agent 系统。

但它已经具备 Agent Workflow 的雏形：

```text
感知输入：读取 Git 变更
调用工具：调用 OpenCodeReview CLI
结构化结果：解析 OCR JSON
生成产物：输出 Markdown 报告
保留状态：AgentState
```

所以它可以叫做 Code Review Agent MVP。

它和普通脚本的区别在于：

| 普通脚本 | Agent MVP |
|---|---|
| 只执行一条命令 | 编排多个步骤 |
| 输出文本 | 输出结构化 JSON 和 Markdown |
| 不保留状态 | 使用 `AgentState` 保存流程状态 |
| 错误处理简单 | 处理 returncode、stderr、timeout、encoding |
| 难以扩展 | 后续可以接 LangGraph、多 Agent、CI |

这个阶段最重要的不是炫技术，而是把边界划清楚：

```text
OpenCodeReview 是 Review Backend
这个项目是 Agent Workflow Wrapper
```

## 二十、后续如何升级

这个 MVP 后续可以按版本演进。

### V1：当前版本

```text
Git diff
  ↓
Run OCR
  ↓
Parse JSON
  ↓
Generate Markdown Report
```

当前已经完成。

### V2：加入风险分级

可以根据 `comments[].content` 做简单规则分类：

```text
SQL Injection -> Critical
Authorization -> Critical
Error Handling -> Warning
Style Issue -> Suggestion
```

然后在 Markdown 报告里新增：

```text
Risk Level
```

### V3：引入 LangGraph

把当前线性流程拆成节点：

```text
check_git_changes
  ↓
run_ocr_review
  ↓
parse_review_json
  ↓
classify_risk
  ↓
generate_report
```

`AgentState` 可以继续复用。

### V4：接入 GitHub Actions

在 PR 触发时自动运行：

```text
pull_request
  ↓
run agent workflow
  ↓
upload review-report.md artifact
```

### V5：PR 自动评论

使用 `comments[].path`、`comments[].start_line`、`comments[].end_line` 生成 GitHub PR 行内评论。

### V6：抽象 ReviewBackend

把 OCR 抽象成可替换后端：

```text
ReviewBackend
  ├── OpenCodeReviewBackend
  ├── LLMReviewBackend
  └── StaticScanBackend
```

到这一步，项目就不再只是 OCR wrapper，而是一个更完整的 Code Review Agent Framework。

## 二十一、本篇用到的命令

查看项目目录：

```powershell
Get-ChildItem -Recurse D:\agent\open-code-review-agent-mvp
```

查看帮助信息：

```powershell
python -B D:\agent\open-code-review-agent-mvp\agent_graph.py --help
```

使用已有 OCR JSON 生成报告：

```powershell
python -B D:\agent\open-code-review-agent-mvp\agent_graph.py --repo D:\agent\open-code-review-main\ocr-practice-demo --output-dir "C:\Users\ad\Documents\New project\mvp-test-output-final" --use-existing-json D:\agent\open-code-review-main\ocr-practice-demo\outputs-review-result.json
```

真正调用 OpenCodeReview：

```powershell
python -B D:\agent\open-code-review-agent-mvp\agent_graph.py --repo D:\agent\open-code-review-main\ocr-practice-demo
```

## 二十二、本篇总结

这一篇完成了从“学习 OpenCodeReview”到“设计自己的 Agent 项目”的第一步。

核心结论如下：

1. 这个项目不是仿写 OpenCodeReview，而是在 OpenCodeReview 之上做 Agent Workflow 封装。
2. OpenCodeReview 负责真正的 AI Code Review，我的项目负责流程编排和工程化输出。
3. MVP 第一版只做 `Git diff -> OCR -> JSON -> Markdown Report`。
4. `agent_graph.py` 负责串联流程。
5. `git_tools.py` 负责 Git 输入。
6. `ocr_tools.py` 负责调用 OCR CLI 和解析 JSON。
7. `report_tools.py` 负责生成 Markdown 报告。
8. `AgentState` 为后续升级 LangGraph 保留了状态模型。
9. `use_existing_json` 可以避免开发阶段重复调用 LLM。
10. Windows 下 JSON 编码问题也需要处理，这是实际工程里的细节。

到这里，一个最小 Code Review Agent MVP 已经有了雏形。

## 二十三、下一篇计划

下一篇：

```text
从 0 学 OpenCodeReview：实现 Git Diff 到 Markdown 报告的 Agent MVP
```

下一篇重点不再是设计，而是完整实现和运行：

```text
1. 初始化项目
2. 运行 agent_graph.py
3. 真正调用 ocr review --format json
4. 生成 outputs/review-result.json
5. 生成 outputs/review-report.md
6. 展示报告内容
7. 总结 V1 的不足
```

也就是说，第七篇讲设计和代码结构，第八篇讲完整运行和结果展示。
