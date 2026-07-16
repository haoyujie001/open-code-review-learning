# 从 0 学 OpenCodeReview：引入 LangGraph 管理 Code Review Agent 工作流

## 一、前言

前面几篇已经完成了两个阶段：

第一阶段是学习 OpenCodeReview 本身：

```text
安装 OpenCodeReview
运行 ocr review
理解 Git Diff
理解 rule.json
理解 Agent 工具调用
理解 JSON 输出和 Markdown 报告
```

第二阶段是基于 OpenCodeReview 做自己的 Agent MVP：

```text
Git diff
  ↓
Run OCR
  ↓
Parse JSON
  ↓
Classify Risk
  ↓
Generate Markdown Report
```

第九篇我们已经给审查结果增加了风险分级：

```text
Critical
Warning
Suggestion
```

并且在 JSON 和 Markdown 报告中都展示了风险统计。

但是第九篇还有一个明显问题：它本质上仍然是一个顺序脚本。

也就是说，代码大概还是这种形式：

```text
run_workflow()
  -> get_changed_files()
  -> run_ocr_review()
  -> classify_review_risks()
  -> generate_markdown_report()
```

这种写法能跑，但是流程能力还比较弱，本质上仍然是一个顺序式 workflow。

本篇开始引入 LangGraph，把顺序脚本升级成有状态、有节点、有条件分支、有运行轨迹、有历史归档的 Code Review Agent 工作流。

一句话概括：本篇不是为了让 LLM 本身更聪明，而是把 Code Review Agent 的工程结构搭起来。LangGraph 负责编排节点和条件路由，OpenCodeReview 负责实际代码审查，风险分级、报告生成、历史归档作为确定性节点挂在工作流中。

## 二、本篇目标

本篇要完成的目标：

```text
1. 在 s10 中新建一个 LangGraph 版本项目。
2. 定义统一的 AgentState。
3. 把原来的顺序流程拆成多个节点。
4. 使用 StateGraph 连接节点。
5. 增加条件分支：有变更才审查，没有变更则跳过。
6. 保留 --use-existing-json，方便不调用 LLM 也能调试流程。
7. 继续复用第九篇的风险分级能力。
8. 生成 review-result.json 和 review-report.md。
9. 增加 outputs/history 历史归档。
10. 记录 workflow trace，方便解释 Agent 执行过程。
```

本篇对应代码目录：

```text
D:\agent\open-code-review-main\ocr-practice-demo\s10\open-code-review-agent-langgraph
```

博客文件：

```text
D:\agent\open-code-review-main\ocr-practice-demo\s10\s10.md
```

## 三、为什么要引入 LangGraph

第九篇的顺序脚本已经能完成任务，但它的流程是写死的。

如果后续我要继续增加这些能力：

```text
人工确认
按风险等级决定是否中断
失败重试
保存审查历史
多 Agent 协作
PR 自动评论
Evaluator 评估审查质量
```

单纯的顺序脚本会越来越难维护。

例如将来可能出现这样的逻辑：

```text
如果没有 Git 变更：
  直接结束

如果有 Git 变更：
  调用 OpenCodeReview

如果发现 Critical 问题：
  进入人工确认节点

如果只有 Suggestion：
  直接生成报告
```

这类流程更适合用图来表达。

LangGraph 的核心价值就在这里：

```text
State：统一保存流程状态
Node：把每一步封装成节点
Edge：定义节点之间的流转关系
Conditional Edge：定义条件分支
```

另外，本项目还在 `AgentState` 中自己维护了一份 `trace`，用来记录每个节点的执行情况。也就是说，LangGraph 负责状态图编排，`trace` 是我们为了可观测性额外加上的工程能力。

这也是为什么很多主流 Agent 工程都会从“一个脚本”演进到“状态图工作流”。

## 四、本篇最终架构

第十篇的流程是：

```text
START
  ↓
check_git_changes
  ↓
route_after_git_check
  ├── 有变更或传入已有 JSON -> run_ocr_review
  └── 没有变更 -> build_skipped_review
  ↓
classify_risk
  ↓
generate_report
  ↓
save_history
  ↓
END
```

这里有一个命名细节：节点名叫 `run_ocr_review`，但它内部有两条路径。如果传入 `--use-existing-json`，它会读取已有 OCR JSON；否则才会真实调用 OpenCodeReview CLI。

和第九篇相比，核心区别是：

```text
第九篇：
  一个 run_workflow 函数顺序调用多个工具函数

第十篇：
  使用 LangGraph 把流程拆成多个节点，并通过 AgentState 传递数据
```

更具体地看：

| 能力 | 第九篇 | 第十篇 |
|---|---|---|
| 流程表达 | 函数顺序调用 | 图节点 |
| 状态管理 | dataclass | AgentState |
| 条件分支 | if 写在 workflow 中 | conditional edge |
| 节点拆分 | 不明显 | git / ocr / risk / report / history |
| trace | 无完整流程 trace | 自定义节点执行轨迹 |
| 历史归档 | 无 | outputs/history |
| 后续扩展 | 容易堆代码 | 可以继续加节点 |

## 五、项目目录结构

本篇项目目录如下：

```text
s10
└── open-code-review-agent-langgraph
    ├── agent_graph.py
    ├── state.py
    ├── requirements.txt
    ├── README.md
    ├── nodes
    │   ├── __init__.py
    │   ├── git_node.py
    │   ├── ocr_node.py
    │   ├── risk_node.py
    │   ├── report_node.py
    │   └── history_node.py
    ├── tools
    │   ├── __init__.py
    │   ├── git_tools.py
    │   ├── ocr_tools.py
    │   ├── risk_tools.py
    │   └── report_tools.py
    └── outputs
        ├── review-result.json
        ├── review-report.md
        └── history
```

这里我刻意把代码分成两层：

```text
nodes：LangGraph 节点层
tools：确定性工具层
```

这点很重要。

Agent 项目不是把所有逻辑都塞进大模型，也不是把所有代码都塞进一个 `agent_graph.py`。

更合理的结构是：

```text
LangGraph 负责流程编排
工具函数负责确定性执行
LLM / OCR 负责代码审查
风险分级和报告生成负责后处理
```

这样后续要替换 OCR、增加 MCP、增加人工确认节点，都不会影响整个项目结构。

## 六、安装 LangGraph

本篇使用的依赖文件很简单：

```text
langgraph>=0.2.0
```

通用安装方式：

```powershell
cd open-code-review-agent-langgraph
python -m pip install -r requirements.txt
```

如果使用的是 Anaconda，也可以指定自己的环境安装。比如我本地使用的是 `agent` 环境：

```powershell
conda run -n agent python -m pip install -r requirements.txt
```

安装后确认 Python 版本：

```powershell
python -c "import sys; print(sys.executable); print(sys.version)"
```

我本地的实际输出：

```text
D:\anaconda\envs\agent\python.exe
3.11.15 | packaged by conda-forge
```

这里使用 Python 3.11，所以代码里可以正常使用：

```python
str | None
list[str]
dict[str, int]
```

这类类型注解。

## 七、state.py：定义 AgentState

LangGraph 的核心是状态。

本项目中，所有节点之间传递的数据都放在 `AgentState` 里。

文件：

```text
state.py
```

核心代码：

```python
from __future__ import annotations

from datetime import datetime
from typing import Any, TypedDict


DEFAULT_EXCLUDES = [
    "outputs/**",
    "*.review.json",
    "*.review.md",
    "outputs-review-result.json",
    "s09/**",
    "s10/**",
]

SEVERITY_ORDER = ["Critical", "Warning", "Suggestion"]


class AgentState(TypedDict, total=False):
    repo_dir: str
    output_dir: str
    review_json_path: str
    review_report_path: str
    history_dir: str
    ocr_bin: str
    excludes: list[str]
    timeout_seconds: int
    use_existing_json: str | None
    raw_changed_files: list[str]
    changed_files: list[str]
    has_changes: bool
    review_data: dict[str, Any]
    risk_summary: dict[str, int]
    report_markdown: str
    history_files: dict[str, str]
    trace: list[dict[str, Any]]
```

这里的字段可以分成几类。

第一类是输入配置：

```text
repo_dir
output_dir
ocr_bin
excludes
timeout_seconds
use_existing_json
```

第二类是 Git 变更信息：

```text
raw_changed_files
changed_files
has_changes
```

第三类是审查结果：

```text
review_data
risk_summary
report_markdown
```

第四类是输出文件路径：

```text
review_json_path
review_report_path
history_dir
history_files
```

第五类是工作流轨迹：

```text
trace
```

这个 `trace` 很关键。

它能记录每个节点什么时候执行、执行了什么、产生了什么关键数据。

## 八、add_trace：记录节点执行轨迹

同样在 `state.py` 中，我定义了一个 `add_trace` 函数：

```python
def add_trace(
    state: AgentState,
    node: str,
    message: str,
    **data: Any,
) -> list[dict[str, Any]]:
    trace = list(state.get("trace") or [])
    event: dict[str, Any] = {
        "node": node,
        "message": message,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    if data:
        event["data"] = data
    trace.append(event)
    return trace
```

这个函数的作用是：

```text
读取旧 trace
追加当前节点事件
返回新的 trace
```

为什么不直接在原列表上 append？

因为在工作流状态管理里，更推荐让每个节点返回新的状态片段，而不是在原对象上做隐式修改。

这样后续调试更清晰。

每个 trace event 大概长这样：

```json
{
  "node": "classify_risk",
  "message": "Classified review comments by risk.",
  "time": "2026-07-08 13:22:57",
  "data": {
    "risk_summary": {
      "Critical": 1,
      "Warning": 1,
      "Suggestion": 0
    }
  }
}
```

这就是后面做 Tracing、Evaluator、Dashboard 的基础。

## 九、agent_graph.py：构建 LangGraph

文件：

```text
agent_graph.py
```

这是本篇最核心的文件。

它负责：

```text
1. 导入所有节点
2. 创建 StateGraph
3. 注册节点
4. 连接节点
5. 定义条件分支
6. 编译图
7. 提供命令行入口
```

核心代码：

```python
from nodes.git_node import check_git_changes, route_after_git_check
from nodes.history_node import save_history_node
from nodes.ocr_node import build_skipped_review_node, run_ocr_review_node
from nodes.report_node import generate_report_node
from nodes.risk_node import classify_risk_node
from state import AgentState, DEFAULT_EXCLUDES

try:
    from langgraph.graph import END, START, StateGraph
except ImportError as exc:
    END = START = StateGraph = None
    LANGGRAPH_IMPORT_ERROR = exc
else:
    LANGGRAPH_IMPORT_ERROR = None
```

这里做了一个 `try except`。

原因是如果用户没有安装 LangGraph，直接运行脚本时可以得到明确提示，而不是看到一堆底层报错。

## 十、build_graph：注册节点

`build_graph` 是图构建函数。

核心代码：

```python
def build_graph():
    if StateGraph is None:
        raise RuntimeError(
            "LangGraph is not installed. Run `pip install -r requirements.txt` "
            "inside the S10 project directory."
        ) from LANGGRAPH_IMPORT_ERROR

    graph = StateGraph(AgentState)
    graph.add_node("check_git_changes", check_git_changes)
    graph.add_node("run_ocr_review", run_ocr_review_node)
    graph.add_node("build_skipped_review", build_skipped_review_node)
    graph.add_node("classify_risk", classify_risk_node)
    graph.add_node("generate_report", generate_report_node)
    graph.add_node("save_history", save_history_node)
```

这段代码把普通 Python 函数注册成 LangGraph 节点。

每个节点的统一形式是：

```python
def node_name(state: AgentState) -> AgentState:
    ...
```

也就是说：

```text
输入是 AgentState
输出也是 AgentState 的一部分
```

LangGraph 会把每个节点返回的状态合并到整体状态里。

## 十一、build_graph：连接节点

注册节点后，需要连接节点。

核心代码：

```python
graph.add_edge(START, "check_git_changes")
graph.add_conditional_edges(
    "check_git_changes",
    route_after_git_check,
    {
        "review": "run_ocr_review",
        "skip": "build_skipped_review",
    },
)
graph.add_edge("run_ocr_review", "classify_risk")
graph.add_edge("build_skipped_review", "classify_risk")
graph.add_edge("classify_risk", "generate_report")
graph.add_edge("generate_report", "save_history")
graph.add_edge("save_history", END)
return graph.compile()
```

这里最重要的是：

```python
graph.add_conditional_edges(...)
```

它让工作流不再是固定直线，而是可以根据状态进行分支。

本项目中的分支逻辑是：

```text
check_git_changes
  ↓
如果 use_existing_json 存在：
  进入 run_ocr_review

如果有 changed_files：
  进入 run_ocr_review

否则：
  进入 build_skipped_review
```

虽然这个分支现在还比较简单，但它是后续扩展的基础。

例如后面可以继续加：

```text
如果 Critical > 0：
  进入 human_approval

如果 OCR 执行失败：
  进入 retry_or_fallback

如果是文档变更：
  进入 lightweight_review
```

## 十二、run_workflow：初始化状态并运行图

`run_workflow` 用来初始化状态，然后调用编译后的 LangGraph。

核心代码：

```python
def run_workflow(
    repo_dir: str | Path,
    output_dir: str | Path = "outputs",
    ocr_bin: str = "ocr",
    excludes: list[str] | None = None,
    timeout_seconds: int = 900,
    use_existing_json: str | Path | None = None,
) -> AgentState:
    initial_state: AgentState = {
        "repo_dir": str(repo_dir),
        "output_dir": str(output_dir),
        "ocr_bin": ocr_bin,
        "excludes": excludes or list(DEFAULT_EXCLUDES),
        "timeout_seconds": timeout_seconds,
        "use_existing_json": str(use_existing_json) if use_existing_json else None,
        "trace": [],
    }
    app = build_graph()
    return app.invoke(initial_state)
```

这里有两个重点。

第一，工作流不是靠全局变量传递数据，而是靠 `initial_state`。

第二，真正触发执行的是：

```python
app.invoke(initial_state)
```

这行代码会按照图的边依次执行节点。

## 十三、git_node.py：检测 Git 变更

文件：

```text
nodes/git_node.py
```

它有两个职责：

```text
1. 检测 Git 变更文件。
2. 根据变更决定下一步走 review 还是 skip。
```

核心代码：

```python
def check_git_changes(state: AgentState) -> AgentState:
    repo_root = ensure_git_repo(state.get("repo_dir", "."))
    excludes = state.get("excludes") or list(DEFAULT_EXCLUDES)

    output_dir = Path(state.get("output_dir", "outputs"))
    if not output_dir.is_absolute():
        output_dir = repo_root / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    raw_changed_files = get_changed_files(repo_root)
    changed_files = filter_paths(raw_changed_files, excludes)

    next_state: AgentState = {
        "repo_dir": str(repo_root),
        "output_dir": str(output_dir),
        "review_json_path": str(output_dir / "review-result.json"),
        "review_report_path": str(output_dir / "review-report.md"),
        "history_dir": str(output_dir / "history"),
        "raw_changed_files": raw_changed_files,
        "changed_files": changed_files,
        "has_changes": bool(changed_files),
        "trace": add_trace(
            state,
            "check_git_changes",
            "Collected Git changed files.",
            raw_count=len(raw_changed_files),
            reviewed_count=len(changed_files),
        ),
    }
    return next_state
```

这里有一个细节：我同时保留了两个字段。

```text
raw_changed_files
changed_files
```

`raw_changed_files` 是 Git 原始检测到的变更。

`changed_files` 是经过 exclude 过滤之后真正参与审查的文件。

实际运行时，metadata 中记录的是：

```json
"raw_changed_files": [
  "outputs-review-result.json",
  "s01/src/user.js",
  "s09/",
  "s10/"
],
"changed_files": [
  "s01/src/user.js"
]
```

这说明 `outputs-review-result.json`、`s09/`、`s10/` 这些文件被排除了，真正参与审查的只有：

```text
s01/src/user.js
```

## 十四、route_after_git_check：条件分支

条件分支函数如下：

```python
def route_after_git_check(state: AgentState) -> str:
    if state.get("use_existing_json"):
        return "review"
    if state.get("has_changes"):
        return "review"
    return "skip"
```

这个函数返回的不是下一个节点函数，而是一个字符串：

```text
review
skip
```

然后在 `agent_graph.py` 里映射到具体节点：

```python
{
    "review": "run_ocr_review",
    "skip": "build_skipped_review",
}
```

这种写法的好处是流程图很清晰。

以后要加更多分支，也可以继续扩展成：

```text
security_review
doc_review
skip
manual_approval
```

## 十五、ocr_node.py：调用 OCR 或读取已有 JSON

文件：

```text
nodes/ocr_node.py
```

这个节点有两个路径。

第一种是读取已有 OCR JSON：

```python
use_existing_json = state.get("use_existing_json")
if use_existing_json:
    review_data = load_review_json(use_existing_json)
    message = "Loaded existing OCR JSON."
```

第二种是真实调用 OpenCodeReview：

```python
review_data = run_ocr_review(
    repo_dir=state["repo_dir"],
    output_path=state["review_json_path"],
    ocr_bin=state.get("ocr_bin", "ocr"),
    excludes=state.get("excludes"),
    timeout_seconds=int(state.get("timeout_seconds", 900)),
)
message = "Ran OpenCodeReview CLI."
```

为什么要保留 `--use-existing-json`？

因为真实调用 LLM 成本更高，而且调试 LangGraph 时没必要每次都重新审查。

本篇验证时使用的是：

```text
D:\agent\open-code-review-main\ocr-practice-demo\outputs-review-result.json
```

这份 JSON 是之前真实调用 OpenCodeReview 得到的结果。

所以本篇运行 LangGraph 时没有再次调用 LLM，而是复用了已有 OCR 输出。

这也是 Agent 工程里很常见的做法：

```text
真实调用模型生成一次结果
后续开发流程编排、报告生成、风险分级时复用 fixture / existing json
```

## 十六、build_skipped_review_node：没有变更时也生成结构化结果

如果没有 Git 变更，工作流不会直接崩掉，而是生成一个 skipped 结果：

```python
def build_skipped_review_node(state: AgentState) -> AgentState:
    review_data = {
        "status": "skipped",
        "message": "No Git changes detected by the LangGraph wrapper.",
        "summary": {
            "files_reviewed": 0,
            "comments": 0,
            "total_tokens": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_read_tokens": 0,
            "cache_write_tokens": 0,
            "elapsed": "0s",
        },
        "tool_calls": {"total": 0, "by_tool": {}},
        "comments": [],
    }
    return {
        "review_data": review_data,
        "trace": add_trace(state, "build_skipped_review", "Built skipped review result."),
    }
```

这个设计很重要。

因为即使没有代码变更，后面的节点仍然可以继续运行：

```text
classify_risk
generate_report
save_history
```

最终仍然会得到一份结构一致的报告。

这比直接 `return` 更利于自动化。

## 十七、risk_node.py：风险分级节点

文件：

```text
nodes/risk_node.py
```

核心代码：

```python
def classify_risk_node(state: AgentState) -> AgentState:
    review_data = classify_review_risks(state.get("review_data") or {})
    risk_summary = review_data.get("risk_summary") or {}

    review_json_path = Path(state["review_json_path"])
    review_json_path.parent.mkdir(parents=True, exist_ok=True)
    review_json_path.write_text(
        json.dumps(review_data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    return {
        "review_data": review_data,
        "risk_summary": risk_summary,
        "trace": add_trace(
            state,
            "classify_risk",
            "Classified review comments by risk.",
            risk_summary=risk_summary,
        ),
    }
```

这里复用了第九篇的工具函数：

```python
classify_review_risks(...)
```

风险分级完成后，会把增强后的 JSON 写入：

```text
outputs/review-result.json
```

这份 JSON 相比原始 OCR JSON，多了这些字段：

```text
comments[].severity
comments[].risk_reason
comments[].matched_keywords
risk_summary
```

例如：

```json
"risk_summary": {
  "Critical": 1,
  "Warning": 1,
  "Suggestion": 0
}
```

## 十八、risk_tools.py：确定性风险分级规则

风险分级的具体规则仍然放在工具层：

```text
tools/risk_tools.py
```

核心等级：

```python
SEVERITY_ORDER = ["Critical", "Warning", "Suggestion"]
```

高风险关键词：

```python
CRITICAL_KEYWORDS = [
    "sql injection",
    "command injection",
    "remote code execution",
    "rce",
    "xss",
    "csrf",
    "hardcoded secret",
    "secret key",
    "api key",
    "password",
    "token",
    "authentication",
    "authorization",
    "permission",
    "privilege",
    "prepared statement",
    "parameterized",
    "drop table",
]
```

中风险关键词：

```python
WARNING_KEYWORDS = [
    "error handling",
    "exception",
    "null",
    "undefined",
    "validation",
    "not exported",
    "missing",
    "async",
    "timeout",
    "resource leak",
    "race condition",
]
```

核心分级逻辑：

```python
def match_severity(text: str) -> tuple[str, str, list[str]]:
    matched = find_keywords(text, CRITICAL_KEYWORDS)
    if matched:
        return "Critical", "Security-sensitive or data-risk keyword matched.", matched

    matched = find_keywords(text, WARNING_KEYWORDS)
    if matched:
        return "Warning", "Reliability, correctness, or maintainability keyword matched.", matched

    matched = find_keywords(text, SUGGESTION_KEYWORDS)
    if matched:
        return "Suggestion", "Code quality or readability keyword matched.", matched

    return "Suggestion", "No high-risk keyword matched; treat as a general suggestion.", []
```

这里采用的是确定性规则，而不是再调用一次 LLM。

原因是：

```text
1. 结果稳定，方便调试。
2. 成本低，不消耗额外 token。
3. 容易解释，博客和面试都能讲清楚。
4. 后续可以替换成 LLM classifier 或规则库。
```

## 十九、report_node.py：生成 Markdown 报告

文件：

```text
nodes/report_node.py
```

核心代码：

```python
def generate_report_node(state: AgentState) -> AgentState:
    markdown = generate_markdown_report(
        state.get("review_data") or {},
        changed_files=state.get("changed_files") or [],
        trace=state.get("trace") or [],
    )
    report_path = save_markdown_report(markdown, state["review_report_path"])

    return {
        "report_markdown": markdown,
        "review_report_path": str(report_path),
        "trace": add_trace(
            state,
            "generate_report",
            "Generated Markdown review report.",
            path=str(report_path),
        ),
    }
```

这里同样是节点层调用工具层：

```text
nodes/report_node.py
  ↓
tools/report_tools.py
```

`report_node` 只负责工作流状态。

具体 Markdown 怎么拼，由 `report_tools.py` 负责。

这样职责更清楚。

最终报告路径：

```text
D:\agent\open-code-review-main\ocr-practice-demo\s10\open-code-review-agent-langgraph\outputs\review-report.md
```

## 二十、history_node.py：保存审查历史

文件：

```text
nodes/history_node.py
```

这是第十篇新增的一个工程化能力。

每次运行后，把结果归档到：

```text
outputs/history/<timestamp>/
```

核心代码：

```python
def save_history_node(state: AgentState) -> AgentState:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    history_root = Path(state["history_dir"])
    run_dir = history_root / timestamp
    run_dir.mkdir(parents=True, exist_ok=True)

    review_json_path = Path(state["review_json_path"])
    review_report_path = Path(state["review_report_path"])
    history_json = run_dir / "review-result.json"
    history_report = run_dir / "review-report.md"
    metadata_path = run_dir / "run-metadata.json"

    if review_json_path.exists():
        shutil.copy2(review_json_path, history_json)
    if review_report_path.exists():
        shutil.copy2(review_report_path, history_report)
```

这里会复制两份文件：

```text
review-result.json
review-report.md
```

另外还会生成：

```text
run-metadata.json
```

metadata 中保存：

```text
generated_at
repo_dir
changed_files
raw_changed_files
risk_summary
history_files
trace
```

这一步很适合写进简历，因为它体现的是工程化能力，而不是简单调用 API。

可以这样描述：

```text
实现审查历史归档能力，自动保存每次 AI Review 的结构化结果、Markdown 报告、风险统计和节点执行轨迹，便于后续追踪、评估和审计。
```

## 二十一、tools 层为什么保留

第十篇并没有把所有逻辑都改成 LangGraph 节点。

例如这些能力仍然放在 `tools` 目录：

```text
tools/git_tools.py
tools/ocr_tools.py
tools/risk_tools.py
tools/report_tools.py
```

原因是：

```text
LangGraph 负责“流程怎么走”
tools 负责“具体事情怎么做”
```

例如：

```text
git_tools.py：
  负责 Git 命令、变更文件解析、exclude 过滤

ocr_tools.py：
  负责解析 ocr 可执行文件、调用 ocr review、读取 JSON

risk_tools.py：
  负责风险分级

report_tools.py：
  负责生成 Markdown
```

这种拆分方式更适合扩展。

后续如果我要把 OpenCodeReview 换成另一个 review engine，只需要替换 `ocr_tools.py` 或新增一个工具模块。

如果我要把风险分级从关键词升级成 LLM classifier，也主要改 `risk_tools.py`。

LangGraph 节点本身不用大改。

## 二十二、运行语法检查

先对 D 盘项目做语法检查：

```powershell
python -B -c "from pathlib import Path; files=list(Path(r'D:\agent\open-code-review-main\ocr-practice-demo\s10\open-code-review-agent-langgraph').rglob('*.py')); [compile(p.read_text(encoding='utf-8'), str(p), 'exec') for p in files]; print('syntax ok:', len(files), 'files')"
```

输出：

```text
syntax ok: 13 files
```

说明所有 Python 文件都能正常编译。

## 二十三、查看命令行参数

运行：

```powershell
python -B D:\agent\open-code-review-main\ocr-practice-demo\s10\open-code-review-agent-langgraph\agent_graph.py --help
```

输出中可以看到这些参数：

```text
--repo
--output-dir
--ocr-bin
--exclude
--timeout-seconds
--use-existing-json
--print-trace
```

这些参数分别用于：

| 参数 | 作用 |
|---|---|
| `--repo` | 指定要审查的 Git 仓库 |
| `--output-dir` | 指定输出目录 |
| `--ocr-bin` | 指定 OpenCodeReview CLI 路径 |
| `--exclude` | 排除不需要审查的文件 |
| `--timeout-seconds` | 设置 OCR 命令超时时间 |
| `--use-existing-json` | 不调用 LLM，复用已有 OCR JSON |
| `--print-trace` | 在终端打印节点执行轨迹 |

## 二十四、离线运行 LangGraph 工作流

为了避免重复调用 LLM，本篇使用已有的 OCR JSON：

```text
D:\agent\open-code-review-main\ocr-practice-demo\outputs-review-result.json
```

运行命令：

```powershell
conda run -n agent python -B D:\agent\open-code-review-main\ocr-practice-demo\s10\open-code-review-agent-langgraph\agent_graph.py `
  --repo D:\agent\open-code-review-main\ocr-practice-demo `
  --output-dir D:\agent\open-code-review-main\ocr-practice-demo\s10\open-code-review-agent-langgraph\outputs `
  --use-existing-json D:\agent\open-code-review-main\ocr-practice-demo\outputs-review-result.json `
  --print-trace
```

这里的重点是：

```text
--use-existing-json
```

它会跳过真实 OCR 调用，直接读取已有审查结果。

因此这次运行验证的是：

```text
LangGraph 编排
Git 变更检测
JSON 读取
风险分级
报告生成
历史归档
trace 记录
```

不是重新调用 LLM。

## 二十五、运行结果

实际输出：

```text
Code Review Agent LangGraph workflow finished.
Repo: D:\agent\open-code-review-main\ocr-practice-demo
Changed files: 1
Risk summary: {'Critical': 1, 'Warning': 1, 'Suggestion': 0}
JSON: D:\agent\open-code-review-main\ocr-practice-demo\s10\open-code-review-agent-langgraph\outputs\review-result.json
Report: D:\agent\open-code-review-main\ocr-practice-demo\s10\open-code-review-agent-langgraph\outputs\review-report.md
History: D:\agent\open-code-review-main\ocr-practice-demo\s10\open-code-review-agent-langgraph\outputs\history\20260708-132257
- [check_git_changes] Collected Git changed files.
- [run_ocr_review] Loaded existing OCR JSON.
- [classify_risk] Classified review comments by risk.
- [generate_report] Generated Markdown review report.
- [save_history] Archived review outputs.
```

从结果可以看出，完整 LangGraph 节点都执行了：

```text
check_git_changes
run_ocr_review
classify_risk
generate_report
save_history
```

并且最终风险统计为：

```text
Critical: 1
Warning: 1
Suggestion: 0
```

## 二十六、输出文件

运行后生成了这些文件：

```text
D:\agent\open-code-review-main\ocr-practice-demo\s10\open-code-review-agent-langgraph\outputs\review-result.json
D:\agent\open-code-review-main\ocr-practice-demo\s10\open-code-review-agent-langgraph\outputs\review-report.md
D:\agent\open-code-review-main\ocr-practice-demo\s10\open-code-review-agent-langgraph\outputs\history\20260708-132257\review-result.json
D:\agent\open-code-review-main\ocr-practice-demo\s10\open-code-review-agent-langgraph\outputs\history\20260708-132257\review-report.md
D:\agent\open-code-review-main\ocr-practice-demo\s10\open-code-review-agent-langgraph\outputs\history\20260708-132257\run-metadata.json
```

其中：

```text
outputs/review-result.json
```

是本次最新结构化结果。

```text
outputs/review-report.md
```

是本次最新 Markdown 报告。

```text
outputs/history/20260708-132257/
```

是本次运行的历史归档。

## 二十七、查看 Markdown 报告

报告开头：

```markdown
# AI Code Review Report

- Generated at: 2026-07-08 13:22:57
- Status: success

## Summary

- Files reviewed: 2
- Comments: 2
- Total tokens: 65929
- Input tokens: 61803
- Output tokens: 4126
- Cache read tokens: 35328
- Cache write tokens: 0
- Elapsed: 1m33s
```

这里可以看到 OCR 原始结果中的 token 信息也被保留下来了。

风险统计：

```markdown
## Risk Summary

| Severity | Count |
|---|---:|
| Critical | 1 |
| Warning | 1 |
| Suggestion | 0 |
```

变更文件：

```markdown
## Changed Files

- `s01/src/user.js`
```

工具调用统计：

```markdown
## Tool Calls

| Tool | Count |
|---|---:|
| `file_read` | 6 |
| `code_search` | 3 |
| `code_comment` | 2 |
| `file_read_diff` | 2 |
| `file_find` | 1 |
```

报告中还包含 Workflow Trace：

```markdown
## Workflow Trace

| Node | Message |
|---|---|
| `check_git_changes` | Collected Git changed files. |
| `run_ocr_review` | Loaded existing OCR JSON. |
| `classify_risk` | Classified review comments by risk. |
```

这里有一个细节：

报告生成时，`generate_report` 和 `save_history` 还没有被写入报告内容，所以报告里的 trace 只展示到生成报告之前。

完整 trace 在终端输出和 `run-metadata.json` 中。

这个点后续可以优化成：

```text
额外生成 trace.json
或者在 save_history 节点中保存完整 trace
```

本篇已经在 `run-metadata.json` 中保存了完整 trace。

## 二十八、查看 Finding 结果

第一条审查结果是 Critical：

```markdown
### 1. [Critical] `s01/src/user.js:37-37`

**Risk Reason**

Security-sensitive or data-risk keyword matched.

**Matched Keywords**

`sql injection`, `prepared statement`, `parameterized`
```

问题内容是 SQL 注入：

```text
SQL Injection Vulnerability:
The email and userId parameters are directly concatenated into the SQL query string without any sanitization or parameterization.
```

原始代码：

```js
db.query("UPDATE users SET email = '" + email + "' WHERE id = " + userId);
```

建议代码：

```js
db.query('UPDATE users SET email = $1 WHERE id = $2', [email, userId]);
```

第二条审查结果是 Warning：

```markdown
### 2. [Warning] `s01/src/user.js:36-39`
```

原因是：

```text
not exported
```

也就是函数定义了，但是没有导出。

这说明第九篇实现的风险分级在 LangGraph 工作流中仍然正常工作。

## 二十九、查看 run-metadata.json

历史目录中最重要的文件是：

```text
run-metadata.json
```

它记录了本次运行的元信息。

关键内容：

```json
{
  "generated_at": "2026-07-08 13:22:57",
  "repo_dir": "D:\\agent\\open-code-review-main\\ocr-practice-demo",
  "changed_files": [
    "s01/src/user.js"
  ],
  "raw_changed_files": [
    "outputs-review-result.json",
    "s01/src/user.js",
    "s09/",
    "s10/"
  ],
  "risk_summary": {
    "Critical": 1,
    "Warning": 1,
    "Suggestion": 0
  }
}
```

这里能清楚看到：

```text
Git 原始变更有 4 项
真正参与审查的文件只有 1 个
风险分级结果是 1 个 Critical 和 1 个 Warning
```

完整 trace：

```json
[
  {
    "node": "check_git_changes",
    "message": "Collected Git changed files."
  },
  {
    "node": "run_ocr_review",
    "message": "Loaded existing OCR JSON."
  },
  {
    "node": "classify_risk",
    "message": "Classified review comments by risk."
  },
  {
    "node": "generate_report",
    "message": "Generated Markdown review report."
  },
  {
    "node": "save_history",
    "message": "Archived review outputs."
  }
]
```

这就是一个最小版本的 workflow tracing。

## 三十、如果要真实调用 OpenCodeReview

本篇为了调试 LangGraph，没有重新调用 LLM。

如果要真实调用 OpenCodeReview，可以使用：

```powershell
conda run -n agent python -B D:\agent\open-code-review-main\ocr-practice-demo\s10\open-code-review-agent-langgraph\agent_graph.py `
  --repo D:\agent\open-code-review-main\ocr-practice-demo `
  --output-dir D:\agent\open-code-review-main\ocr-practice-demo\s10\open-code-review-agent-langgraph\outputs `
  --ocr-bin C:\Users\ad\AppData\Roaming\npm\ocr.cmd `
  --exclude outputs/** `
  --exclude outputs-review-result.json `
  --exclude s09/** `
  --exclude s10/** `
  --print-trace
```

这里要注意 Windows 下的 `ocr`。

之前 Python subprocess 直接找 `ocr` 可能找不到，因为 npm 安装出来的命令在 Windows 下通常有：

```text
ocr.ps1
ocr.cmd
```

对 Python subprocess 来说，显式传入：

```text
C:\Users\ad\AppData\Roaming\npm\ocr.cmd
```

更稳定。

## 三十一、这一版相比第九篇提升了什么

前面已经从架构角度对比过第九篇和第十篇。这里再从项目价值角度总结一次。

第九篇解决的是：

```text
把 OpenCodeReview 的 JSON 结果做风险分级和 Markdown 报告增强
```

第十篇解决的是：

```text
把这些能力组织成可扩展的 LangGraph 状态工作流
```

这一步很重要。

因为它把项目从：

```text
我写了一个脚本调用 OCR
```

升级成：

```text
我设计了一个基于 LangGraph 的 Code Review Agent Workflow
```

这两句话在简历和面试里的分量是不一样的。

## 三十二、当前版本的不足

当前版本还有一些不足。

第一，风险分级还是关键词规则。

例如：

```text
password
token
sql injection
not exported
```

只要命中关键词就会被归类。

这种方式简单稳定，但可能有误判。

后续可以升级成：

```text
规则库 + LLM classifier
```

第二，报告里的 Workflow Trace 不是最终完整 trace。

原因是报告生成节点执行时，后面的 `generate_report` trace 和 `save_history` trace 还没有进入报告。

当前完整 trace 保存在：

```text
run-metadata.json
```

后续可以新增：

```text
outputs/trace.json
```

或者把 `save_history` 改成最后再生成一份完整运行报告。

第三，目前还没有人工确认。

如果发现 Critical 问题，比较合理的流程应该是：

```text
classify_risk
  ↓
如果 Critical > 0
  ↓
human_approval
```

第四，目前还没有 PR 自动评论。

现在只是生成本地 Markdown 报告，后续可以接入：

```text
GitHub Actions
GitHub REST API
PR comment publisher
```

## 三十三、这一篇可以怎么写进简历

本篇完成后，简历上可以这样写：

```text
基于 LangGraph 将 AI Code Review 顺序脚本升级为状态图工作流，拆分 Git 检测、OpenCodeReview 调用、风险分级、报告生成、历史归档等节点，并通过 AgentState 在节点间传递审查上下文，实现条件分支、执行轨迹记录和审查历史归档。
```

如果压缩成一条项目经历：

```text
设计并实现基于 LangGraph 的 Code Review Agent Workflow，集成 OpenCodeReview CLI，支持 Git 变更检测、OCR JSON 解析、风险分级、Markdown 报告生成、节点 Trace 和历史归档。
```

如果面试官追问“为什么用 LangGraph”，可以回答：

```text
因为代码审查不是一次简单的 LLM 调用，而是一个多步骤流程：
Git 输入、审查执行、结果结构化、风险分级、报告生成、历史归档、后续还可能有人审和 PR 评论。
LangGraph 可以把这些步骤抽象成状态节点和条件边，比顺序脚本更适合扩展。
```

## 三十四、下一篇计划

下一篇可以继续做：

```text
从 0 学 OpenCodeReview：接入 GitHub Actions 实现 PR 自动代码审查
```

下一篇建议实现：

```text
.github/workflows/ai-code-review.yml
```

目标是：

```text
pull_request 触发
安装 OpenCodeReview
安装 Python 依赖
运行 LangGraph Agent Workflow
生成 review-result.json
生成 review-report.md
上传 artifact
```

这样项目就从本地工具升级为 CI 自动化工具。

再往后可以继续扩展：

```text
PR 自动评论
Human Approval
MCP Server
RAG 规则库
多 Agent 审查
Evaluator
```

## 三十五、本篇总结

本篇完成了 Code Review Agent 的一次关键升级。

从第九篇到第十篇，项目变化是：

```text
顺序脚本
  ↓
LangGraph Workflow
```

本篇新增了：

```text
1. AgentState 状态定义。
2. LangGraph StateGraph。
3. check_git_changes 节点。
4. run_ocr_review / build_skipped_review 节点。
5. classify_risk 节点。
6. generate_report 节点。
7. save_history 节点。
8. 条件分支 route_after_git_check。
9. workflow trace。
10. outputs/history 历史归档。
```

最终运行结果：

```text
Changed files: 1
Risk summary: {'Critical': 1, 'Warning': 1, 'Suggestion': 0}
History: outputs/history/20260708-132257
```

这一篇的重点不是“多调用了一个库”，而是把 Code Review Agent 的工程结构搭起来了。

现在这个项目已经具备了继续扩展的基础：

```text
可以接 GitHub Actions
可以做 PR 自动评论
可以加人工确认
可以加多 Agent
可以加 MCP
可以加评估和追踪
```

到这里，这个项目已经不只是 OpenCodeReview 的简单使用 Demo，而是一个围绕 OpenCodeReview 构建的 Code Review Agent Workflow。
