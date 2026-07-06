#从 0 学习 Alibaba Open Code Review（五）：Agent 工具调用源码分析


## 前言

前面几篇文章中，从不同角度学习了 OpenCodeReview 的核心流程。

第一篇从使用者角度跑通了最小 Demo，观察到了 `ocr review` 在审查过程中会调用一些工具，例如：

```text
file_read
file_find
code_search
code_comment
```

当时更多是从现象上理解：

```text
file_read 用来读取文件；
code_search 用来搜索代码；
code_comment 用来生成评论。
```

第二篇分析了 `ocr review` 命令入口，知道了命令会从 `main.go` 分发到：

```go
runReview(args[1:])
```

第三篇分析了 Git Diff，理解了：

```text
Git diff 决定本次审查哪些文件。
```

第四篇分析了 `.opencodereview/rule.json`，理解了：

```text
rule.json 决定这些文件按照什么规则审查。
```

这一篇继续往下看，不过不再只是停留在“工具调用日志长什么样”，而是从源码角度分析：

```text
这些工具是在哪里注册的？
工具名称在哪里定义？
每个工具对应哪个实现文件？
Agent 是怎么执行工具调用的？
工具调用日志为什么会出现在终端？
JSON 中 tool_calls 是怎么统计出来的？
```

也就是说，第一篇是观察工具调用现象，而第五篇要开始理解工具调用背后的源码结构。

---

## 一、本篇学习目标

本文主要解决下面几个问题：

```text
1. runReview 中哪里注册了 Agent 工具？
2. buildToolRegistry 做了什么？
3. file_read、file_find、file_read_diff、code_search、code_comment 的名称在哪里定义？
4. Tool、Provider、Registry 分别是什么？
5. 每个工具对应哪个源码文件？
6. LLM 返回 tool_calls 后，OpenCodeReview 如何执行工具？
7. 工具调用日志是从哪里打印出来的？
8. JSON 中 tool_calls 为什么能统计每个工具的调用次数？
9. Review filter removed comment 是什么意思？
```


---

## 二、先回顾一次运行日志

在练习项目中，执行：

```powershell
cd D:\agent\open-code-review-main\ocr-practice-demo

git status --short

ocr review --preview

ocr review
```

当前 Git 状态是：

```text
 M s01/src/user.js
```

说明 `s01/src/user.js` 文件发生了修改。

执行：

```powershell
ocr review --preview
```

输出：

```text
Preview: 1 file(s) changed  |  +4  -1

Will review (1):
  [M]  s01/src/user.js      +4    -1
```

说明本次 Review 会审查 1 个文件，新增 4 行，删除 1 行。

然后执行正式审查：

```powershell
ocr review
```

终端中出现了下面这些工具调用日志：

```text
[ocr] 1 file(s) changed, reviewing 1 in D:\agent\open-code-review-main\ocr-practice-demo
[ocr] Skipping plan phase for s01/src/user.js (5 lines < threshold 50)
[ocr]   ▶ file_read file_path=s01/src/user.js
[ocr]   ✔ file_read (2ms)
[ocr]   ▶ file_read end_line=60 file_path=s01/src/user.js start_line=1
[ocr]   ✔ file_read (1ms)
[ocr]   ▶ code_comment "s01/src/user.js"
[ocr]   ✔ code_comment (0s)
[ocr]   ▶ code_comment "s01/src/user.js"
[ocr]   ✔ code_comment (0s)
[ocr] Review filter removed 1 comment(s) for s01/src/user.js
[ocr] Summary: 1 file(s) reviewed, 2 comment(s), ~21544 token(s) used (input: ~19356, output: ~2188), 51s elapsed
```

从日志上看，本次终端执行中主要调用了：

```text
file_read
code_comment
```

同时，在 JSON 输出中，还能看到更多工具调用统计：

```json
{
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
}
```

需要注意的是：

```text
ocr review
```

和：

```text
ocr review --format json
```

是两次独立执行，所以终端日志和 JSON 中的工具调用次数不一定完全一致。

但它们共同说明了一点：

```text
OpenCodeReview 的审查过程不是一次简单的大模型问答，而是包含工具调用的 Agent 流程。
```

接下来就从源码里追这些工具是怎么来的。

---

## 三、从 runReview 找到工具注册入口

第二篇中已经分析过，`ocr review` 的核心入口是：

```go
runReview(args []string)
```

为了找到工具注册位置，在源码目录执行：

```powershell
Select-String -Path .\cmd\opencodereview\review_cmd.go -Pattern "buildToolRegistry"
```

输出结果：

```text
cmd\opencodereview\review_cmd.go:62:    tools := buildToolRegistry(rt.Collector, fileReader)
cmd\opencodereview\review_cmd.go:183:func buildToolRegistry(collector *tool.CommentCollector, fr *tool.FileReader) *tool.Registry {
```

这说明在 `review_cmd.go` 中，`runReview` 会调用：

```go
tools := buildToolRegistry(rt.Collector, fileReader)
```

也就是说，正式创建 Agent 之前，OpenCodeReview 会先构建一个工具注册表。

可以先画出当前调用链：

```text
runReview
  ↓
创建 FileReader
  ↓
buildToolRegistry
  ↓
得到 tools
  ↓
agent.New(...)
  ↓
ag.Run(...)
```

其中 `tools` 就是后面 Agent 可以调用的工具集合。

---

## 四、分析 buildToolRegistry

继续查看 `buildToolRegistry` 的源码：

```powershell
Get-Content .\cmd\opencodereview\review_cmd.go | Select-Object -Skip 180 -First 40
```

源码如下：

```go
func buildToolRegistry(collector *tool.CommentCollector, fr *tool.FileReader) *tool.Registry {
        reg := tool.NewRegistry()
        reg.Register(tool.NewFileRead(fr))
        reg.Register(tool.NewFileFind(fr))
        reg.Register(tool.NewFileReadDiff(tool.DiffMap{}))
        reg.Register(tool.NewCodeSearch(fr))
        reg.Register(&tool.CodeCommentProvider{Collector: collector})
        return reg
}
```

这段代码非常关键。

它说明 `ocr review` 注册了 5 个核心工具：

```text
file_read
file_find
file_read_diff
code_search
code_comment
```

对应的注册代码是：

| 注册代码                                             | 对应工具             |
| ------------------------------------------------ | ---------------- |
| `tool.NewFileRead(fr)`                           | `file_read`      |
| `tool.NewFileFind(fr)`                           | `file_find`      |
| `tool.NewFileReadDiff(tool.DiffMap{})`           | `file_read_diff` |
| `tool.NewCodeSearch(fr)`                         | `code_search`    |
| `tool.CodeCommentProvider{Collector: collector}` | `code_comment`   |

需要注意：`buildToolRegistry` 只是注册工具的 Go 实现，让程序知道“这个工具被调用时应该执行哪段代码”。

但 LLM 能不能看到这些工具、每个工具有哪些参数、工具在哪个阶段可用，并不是由 `buildToolRegistry` 决定的，而是由 `tools.json` 中的 tool schema 决定。

---

## 五、工具注册表 Registry 是什么

从 `buildToolRegistry` 可以看到，工具注册表是这样创建的：

```go
reg := tool.NewRegistry()
```

然后通过：

```go
reg.Register(...)
```

把一个个工具注册进去。

这说明 OpenCodeReview 内部有一个类似“工具容器”的结构：

```text
Registry
  ↓
保存工具名和工具实现的映射关系
```

Agent 后面如果要调用：

```text
file_read
```

就可以从这个 Registry 中找到对应的工具实现。

可以简单理解为：

```text
Registry = Agent 的工具箱
```

工具箱里放了：

```text
file_read
file_find
file_read_diff
code_search
code_comment
```

Agent 并不是随便调用系统函数，而是只能调用注册表中提供的工具。

这也是 Agent 工程化中很重要的一点：

```text
LLM 不能无限制操作系统；
它只能调用工程代码明确暴露出来的工具。
```

---

## 六、工具注册和 `tools.json` 不是一回事

这里有一个容易混淆的点：

```text
Registry 决定工具能不能被执行；
tools.json 决定 LLM 能看到哪些工具，以及工具参数 schema 是什么。
```

从源码看，工具 schema 定义在：

```text
internal/config/toolsconfig/tools.json
```

里面会定义每个工具的：

```text
name
plan_task
main_task
description
parameters
required
```

例如：

```text
file_read 的参数是 file_path / start_line / end_line；
code_search 的参数是 search_text / file_patterns / case_sensitive / use_perl_regexp；
file_read_diff 的参数是 path_array；
code_comment 的参数是 comments。
```

加载链路可以简化为：

```text
loadLLMRuntime
  ↓
toolsconfig.Load
  ↓
读取 embedded tools.json 或 --tools 指定的 JSON
  ↓
ToolDefsByPhase
  ↓
生成 PlanToolDefs / MainToolDefs
  ↓
LLM 请求中携带 Tools
```

所以完整理解应该分成两层：

```text
工具实现层：buildToolRegistry -> Registry -> Provider.Execute
工具描述层：tools.json -> ToolDef -> LLM tool schema
```

只有这两层都存在，Agent 工具调用才能真正工作：

```text
LLM 先根据 tools.json 知道有哪些工具可以调用；
当 LLM 返回 tool_calls 后，llmloop 再通过 Registry 找到 Go 代码实现并执行。
```

---

## 七、工具名称定义在哪里

接下来查看工具名称定义文件：

```powershell
Get-Content .\internal\tool\definitions.go
```

可以看到：

```go
var (
        Unknown      = Tool{name: "unknown"}
        TaskDone     = Tool{name: "task_done"}
        CodeComment  = Tool{name: "code_comment"}
        FileRead     = Tool{name: "file_read"}
        FileFind     = Tool{name: "file_find"}
        FileReadDiff = Tool{name: "file_read_diff"}
        CodeSearch   = Tool{name: "code_search"}
)
```

这里集中定义了 OpenCodeReview 中的工具名称。

也就是说：

```text
file_read
file_find
file_read_diff
code_search
code_comment
```

这些名称都定义在：

```text
internal/tool/definitions.go
```

这很重要。

因为这些工具名会贯穿多个地方：

```text
1. 工具注册；
2. LLM tool call；
3. 工具执行；
4. 终端日志；
5. JSON tool_calls 统计；
6. Viewer 展示；
7. 测试用例。
```

所以工具名是 Agent 工具调用链路中的核心标识。

---

## 八、Tool 结构体：工具的名称抽象

在 `definitions.go` 中，可以看到：

```go
type Tool struct {
        name string
}
```

这说明一个工具最基础的信息就是它的名字。

例如：

```go
FileRead = Tool{name: "file_read"}
```

表示定义了一个名为：

```text
file_read
```

的工具。

同时还有：

```go
func (t Tool) Name() string { return t.name }
```

也就是说，外部可以通过：

```go
t.Name()
```

拿到工具名称。

这也是后面日志打印和统计时使用的名称。

---

## 九、Provider 接口：所有工具都要实现的能力

`definitions.go` 中还有一个接口：

```go
type Provider interface {
        // Tool returns which tool this provider implements.
        Tool() Tool
        // Execute runs the tool with the given arguments and returns the result string.
        Execute(ctx context.Context, args map[string]any) (string, error)
}
```

这个接口非常关键。

它说明所有具体工具都要实现两个方法：

```text
Tool()
Execute(...)
```

其中：

```text
Tool()
```

用于告诉系统：

```text
我实现的是哪个工具？
```

而：

```text
Execute(...)
```

用于真正执行工具逻辑。

例如：

```text
file_read 的 Execute 负责读取文件；
code_search 的 Execute 负责搜索代码；
code_comment 的 Execute 负责提交评论。
```

所以可以把 Provider 理解为：

```text
工具实现的统一接口。
```

只要一个结构体实现了：

```go
Tool() Tool
Execute(ctx context.Context, args map[string]any) (string, error)
```

它就可以被注册到 Registry 中，供 Agent 调用。

---

## 十、Registry：工具名到工具实现的映射

继续看 `definitions.go`：

```go
type Registry struct {
        providers map[string]Provider
        frozen    bool
}
```

这个结构体中有一个：

```go
providers map[string]Provider
```

它表示：

```text
工具名 → 工具实现
```

例如可以理解成：

```text
"file_read"      → FileReadProvider
"file_find"      → FileFindProvider
"code_search"    → CodeSearchProvider
"code_comment"   → CodeCommentProvider
```

注册工具时，调用的是：

```go
func (r *Registry) Register(p Provider) {
        if r.frozen {
                panic("tool: Register called on frozen registry")
        }
        r.providers[p.Tool().name] = p
}
```

这里可以看到：

```go
p.Tool().name
```

就是工具名。

```go
p
```

就是具体工具实现。

所以 `Register` 的作用是：

```text
把工具名和工具实现保存到 map 中。
```

后面执行工具时，可以通过：

```go
func (r *Registry) Get(name string) (Provider, bool) {
        p, ok := r.providers[name]
        return p, ok
}
```

根据工具名拿到对应实现。

这就是工具调用的基础。

---

## 十一、internal/tool 目录中有哪些工具文件

为了看工具实现分布，我执行：

```powershell
Get-ChildItem .\internal\tool
```

输出中可以看到很多文件：

```text
code_comment.go
code_search.go
comment_collector.go
definitions.go
filereader.go
file_find.go
file_read.go
file_read_diff.go
response_message.go
stub.go
```

从文件名就可以大致看出：

| 文件                     | 作用                        |
| ---------------------- | ------------------------- |
| `definitions.go`       | 定义 Tool、Provider、Registry |
| `file_read.go`         | 实现 `file_read`            |
| `file_find.go`         | 实现 `file_find`            |
| `file_read_diff.go`    | 实现 `file_read_diff`       |
| `code_search.go`       | 实现 `code_search`          |
| `code_comment.go`      | 实现 `code_comment`         |
| `comment_collector.go` | 收集代码评论                    |
| `filereader.go`        | 提供文件读取能力                  |
| `response_message.go`  | 工具调用结果结构                  |
| `stub.go`              | 测试或占位相关工具                 |

这说明 OpenCodeReview 把 Agent 工具相关逻辑集中放在了：

```text
internal/tool
```

目录下。

---

## 十二、file_read 对应的实现文件

搜索 `NewFileRead`：

```powershell
Select-String -Path .\internal\tool\*.go -Pattern "NewFileRead"
```

输出中可以看到：

```text
internal\tool\file_read.go:16:func NewFileRead(fr *FileReader) *FileReadProvider { return &FileReadProvider{FileReader: fr} }
```

这说明：

```text
file_read 的实现文件是 internal/tool/file_read.go
```

在 `buildToolRegistry` 中注册的是：

```go
reg.Register(tool.NewFileRead(fr))
```

所以链路是：

```text
buildToolRegistry
  ↓
tool.NewFileRead(fr)
  ↓
FileReadProvider
  ↓
注册为 file_read
```

运行日志中的：

```text
[ocr]   ▶ file_read file_path=s01/src/user.js
[ocr]   ✔ file_read (2ms)
```

就是这个工具在执行。

它的作用是读取文件内容，为 Agent 提供代码上下文。

源码里还有几个值得注意的细节：

```text
1. file_read 支持 start_line / end_line，只读取指定行范围；
2. 单次最多返回 500 行，超过会标记 IS_TRUNCATED；
3. workspace 模式从当前工作区磁盘读取文件；
4. commit / range 模式通过 git show <ref>:<path> 读取指定版本的文件。
```

这说明 `file_read` 不是简单的 `cat 文件`，而是会根据 Review 模式读取正确版本的代码。

---

## 十三、file_find 对应的实现文件

搜索 `NewFileFind`：

```powershell
Select-String -Path .\internal\tool\*.go -Pattern "NewFileFind"
```

输出：

```text
internal\tool\file_find.go:25:func NewFileFind(fr *FileReader) *FileFindProvider { return &FileFindProvider{FileReader: fr} }
```

这说明：

```text
file_find 的实现文件是 internal/tool/file_find.go
```

在 `buildToolRegistry` 中注册的是：

```go
reg.Register(tool.NewFileFind(fr))
```

链路是：

```text
buildToolRegistry
  ↓
tool.NewFileFind(fr)
  ↓
FileFindProvider
  ↓
注册为 file_find
```

`file_find` 主要用于按文件名关键词查找相关文件。

它底层会优先通过 Git 列出文件：

```text
workspace 模式：git ls-files --cached --others --exclude-standard
range / commit 模式：git ls-tree -r --name-only <ref>
```

然后根据 `query_name` 在文件名中做包含匹配，默认大小写不敏感，最多返回 100 个匹配文件。

在小 Demo 中，它的作用可能不明显，但在真实项目里很有用。

比如修改了：

```text
src/user.js
```

Agent 可能想找：

```text
userService.js
userController.js
user.test.js
userRepository.js
```

这类相关文件。

---

## 十四、file_read_diff 对应的实现文件

搜索 `NewFileReadDiff`：

```powershell
Select-String -Path .\internal\tool\*.go -Pattern "NewFileReadDiff"
```

输出：

```text
internal\tool\file_read_diff.go:34:func NewFileReadDiff(dm DiffMap) *FileReadDiffProvider {
```

这说明：

```text
file_read_diff 的实现文件是 internal/tool/file_read_diff.go
```

在 `buildToolRegistry` 中注册的是：

```go
reg.Register(tool.NewFileReadDiff(tool.DiffMap{}))
```

`file_read_diff` 关注的是 Git diff，而不是完整文件。

可以简单区分：

| 工具               | 关注点    |
| ---------------- | ------ |
| `file_read`      | 文件内容   |
| `file_read_diff` | 本次变更内容 |

这也是 Code Review 场景中非常重要的区别。

因为审查工具不仅要知道文件现在长什么样，还要知道：

```text
本次到底改了什么。
```

这里还有一个源码细节：`buildToolRegistry` 注册 `file_read_diff` 时传入的是空的 `DiffMap`：

```go
reg.Register(tool.NewFileReadDiff(tool.DiffMap{}))
```

真正的 diff 内容不是在这里注入的，而是在 `Agent.Run` 里完成：

```text
Agent.Run
  ↓
loadDiffs
  ↓
injectDiffMap
  ↓
把解析后的每个文件 diff 放入 DiffMap
  ↓
FileReadDiffProvider.SetDiffMap
  ↓
Tools.Freeze
```

也就是说，`file_read_diff` 的执行依赖两个阶段：

```text
注册阶段：先注册一个 provider；
运行阶段：加载 Git diff 后再注入真实 DiffMap。
```

---

## 十五、code_search 对应的实现文件

搜索 `NewCodeSearch`：

```powershell
Select-String -Path .\internal\tool\*.go -Pattern "NewCodeSearch"
```

输出：

```text
internal\tool\code_search.go:24:func NewCodeSearch(fr *FileReader) *CodeSearchProvider { return &CodeSearchProvider{FileReader: fr} }
```

这说明：

```text
code_search 的实现文件是 internal/tool/code_search.go
```

在 `buildToolRegistry` 中注册的是：

```go
reg.Register(tool.NewCodeSearch(fr))
```

`code_search` 的作用是搜索代码。

源码中它底层主要通过 `git grep` 实现，支持：

```text
search_text：搜索文本；
file_patterns：限制搜索范围；
case_sensitive：是否大小写敏感；
use_perl_regexp：是否使用 Perl 正则。
```

默认情况下它使用字面量搜索，并且最多返回 100 条结果，避免一次搜索把上下文撑爆。

例如本次代码里有：

```js
db.query("UPDATE users SET email = '" + email + "' WHERE id = " + userId);
```

Agent 可能会搜索：

```text
db.query
UPDATE users
userId
```

它这样做是为了判断：

```text
项目里有没有类似写法；
有没有参数化查询示例；
有没有统一数据库封装；
有没有错误处理模式。
```

普通 Prompt Review 只能看用户粘贴的代码，而 OpenCodeReview 可以通过 `code_search` 继续探索代码库上下文。

---

## 十六、code_comment 对应的实现文件

搜索 `CodeCommentProvider`：

```powershell
Select-String -Path .\internal\tool\*.go -Pattern "CodeCommentProvider"
```

输出中可以看到：

```text
internal\tool\code_comment.go:11:// CodeCommentProvider submits review comments to the per-Agent CommentCollector.
internal\tool\code_comment.go:12:type CodeCommentProvider struct {
internal\tool\code_comment.go:16:func (p *CodeCommentProvider) Tool() Tool { return CodeComment }
internal\tool\code_comment.go:18:func (p *CodeCommentProvider) Execute(_ context.Context, args map[string]any) (string, error) {
```

这说明：

```text
code_comment 的实现文件是 internal/tool/code_comment.go
```

注释中有一句非常关键：

```text
CodeCommentProvider submits review comments to the per-Agent CommentCollector.
```

也就是说，`code_comment` 并不是读取上下文的工具，而是提交审查评论的工具。

前面的工具主要是：

```text
获取信息
```

而 `code_comment` 是：

```text
输出结果
```

它会把 Agent 生成的代码评论提交给当前 Agent 的 `CommentCollector`。

不过 `code_comment` 在 `llmloop.executeToolCall` 中还有特殊处理，不完全等同于普通工具的 `Provider.Execute` 路径。

源码里会做几件关键事情：

```text
1. 强制把 path 覆盖为当前正在审查的文件，避免模型写错路径；
2. 解析 comments 参数；
3. 根据 diff 解析 existing_code 对应的行号；
4. 如果定位失败，可能触发 re-location 任务重新定位；
5. 可以通过 CommentWorkerPool 异步处理；
6. 最后写入 CommentCollector。
```

所以 `code_comment` 不只是“保存一段文本”，它还承担了评论结构化、定位和收集的职责。

这也解释了为什么运行日志中会出现：

```text
[ocr]   ▶ code_comment "s01/src/user.js"
[ocr]   ✔ code_comment (0s)
```

它表示 Agent 确认了一个问题，并通过 `code_comment` 提交了一条审查评论。

---

## 十七、工具可以分成两类

结合源码和功能，可以把这几个工具分成两类。

### 1. 上下文获取工具

```text
file_read
file_find
file_read_diff
code_search
```

这些工具的作用是帮助 Agent 获取上下文。

它们分别解决：

```text
读取文件内容；
查找相关文件；
读取本次 diff；
搜索相关代码。
```

### 2. 评论输出工具

```text
code_comment
```

这个工具的作用是提交最终审查评论。

可以总结为：

```text
上下文获取工具
  ↓
帮助 Agent 理解代码

评论输出工具
  ↓
帮助 Agent 生成结构化 Review 结果
```

这也是 OpenCodeReview 具备 Agent 特征的核心原因之一。

---

## 十八、LLM 返回 tool_calls 后如何执行工具

前面分析的是工具如何注册。

接下来继续看工具如何被执行。

我搜索了：

```powershell
Select-String -Path .\internal\**\*.go -Pattern "ToolCall"
```

输出中可以看到很多关键位置，其中最重要的是：

```text
internal\llmloop\loop.go
```

里面出现了：

```text
resp.ToolCalls()
executeToolCall
recordToolCall
PrintToolCallStarted
PrintToolCallFinished
PrintToolCallError
```

这说明工具调用大致发生在 `internal/llmloop/loop.go` 中。

从搜索结果可以整理出一条链路：

```text
LLM 返回响应
  ↓
resp.ToolCalls()
  ↓
遍历 tool calls
  ↓
executeToolCall(...)
  ↓
tool.OfName(call.Function.Name)
  ↓
判断是否是 task_done / code_comment / 普通工具
  ↓
从 Registry 中找到对应 Provider
  ↓
执行 Provider.Execute(...) 或 code_comment 特殊处理
  ↓
记录工具调用次数
  ↓
打印工具调用日志
  ↓
把工具结果返回给 LLM loop
```

这里还要注意 `task_done`。

它也定义在工具名称里，并且会暴露给 LLM 使用，但它不是普通 Provider。`llmloop` 看到 `task_done` 后会把当前文件任务标记为完成，用来结束本轮工具调用循环。

这就是 Agent 工具调用的核心流程。

可以简单理解为：

```text
LLM 负责决定要调用哪个工具；
OpenCodeReview 负责执行这个工具；
工具执行结果再回到对话上下文中；
LLM 根据结果继续分析或生成评论。
```

---

## 十九、recordToolCall：为什么 JSON 能统计工具次数

搜索结果中可以看到：

```text
internal\llmloop\loop.go:99:// ToolCalls returns a snapshot of the per-tool call counts.
internal\llmloop\loop.go:100:func (r *Runner) ToolCalls() map[string]int64
internal\llmloop\loop.go:110:func (r *Runner) recordToolCall(name string)
internal\llmloop\loop.go:276:   r.recordToolCall(t.Name())
```

这里说明 `llmloop.Runner` 内部会记录每个工具的调用次数。

当工具执行时，会调用类似：

```go
r.recordToolCall(t.Name())
```

其中：

```go
t.Name()
```

就是工具名称，例如：

```text
file_read
code_search
code_comment
```

所以 JSON 中才能输出：

```json
{
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
}
```

也就是说：

```text
JSON 中的 tool_calls 不是事后猜出来的；
而是在 LLM loop 执行工具时逐次记录的。
```

这让 OpenCodeReview 的 Agent 执行过程具备了可观测性。

---

## 二十、工具调用日志从哪里打印

终端中看到的日志是：

```text
[ocr]   ▶ file_read file_path=s01/src/user.js
[ocr]   ✔ file_read (2ms)
```

搜索结果中可以看到：

```text
internal\telemetry\events.go:84:// PrintToolCallStarted prints a line when a tool begins execution.
internal\telemetry\events.go:96:// PrintToolCallFinished prints a line when a tool finishes successfully.
internal\telemetry\events.go:102:// PrintToolCallError prints a line when a tool fails.
```

也就是说，终端日志主要来自：

```text
internal/telemetry/events.go
```

结合搜索结果，在 `llmloop` 中可以看到相关调用：

```text
telemetry.PrintToolCallStarted(...)
telemetry.PrintToolCallFinished(...)
telemetry.PrintToolCallError(...)
```

所以日志符号可以这样理解：

| 日志符号 | 含义     |
| ---- | ------ |
| `▶`  | 工具开始调用 |
| `✔`  | 工具调用成功 |
| `✘`  | 工具调用失败 |

比如：

```text
[ocr]   ▶ file_read file_path=s01/src/user.js
```

表示开始调用 `file_read`。

```text
[ocr]   ✔ file_read (2ms)
```

表示 `file_read` 执行成功，用时 2ms。

如果工具执行失败，就会出现：

```text
[ocr]   ✘ file_read failed: ...
```

我之前在错误目录执行 `ocr review` 时，就遇到过 `file_read` 失败的问题。

这说明工具日志不仅是展示信息，也能帮助排查 Agent 执行问题。

---

## 二十一、工具调用结果如何回到 LLM 对话

搜索 `ToolCallResult` 时，可以看到：

```text
internal\tool\response_message.go:3:// ToolCallResult holds a single tool call and its execution result.
```

同时在 `llmloop` 中还能看到：

```text
llm.NewToolCallMessage(...)
llm.NewToolResultMessage(...)
```

这说明工具调用不是执行完就结束，而是会把工具结果重新放回 LLM 对话中。

流程可以理解为：

```text
LLM：我要调用 file_read，读取 s01/src/user.js
  ↓
OpenCodeReview：执行 file_read
  ↓
file_read 返回文件内容
  ↓
OpenCodeReview 把工具结果作为 tool result message 返回给 LLM
  ↓
LLM 基于文件内容继续分析
```

这就是典型的工具调用型 Agent 流程。

普通 Prompt Review 中，模型只能看一开始输入的内容。

而在这里，模型可以通过工具逐步获取信息。

---

## 二十二、Agent 工具调用完整流程图

结合目前看到的源码，可以整理出一张完整流程图：

```text
runReview
  ↓
loadLLMRuntime
  ↓
tools.json -> PlanToolDefs / MainToolDefs
  ↓
创建 FileReader
  ↓
buildToolRegistry
  ↓
注册工具实现：
  - file_read
  - file_find
  - file_read_diff
  - code_search
  - code_comment
  ↓
agent.New(...)
  ↓
ag.Run(...)
  ↓
loadDiffs
  ↓
injectDiffMap 注入 file_read_diff 的真实 diff 数据
  ↓
Tools.Freeze
  ↓
LLM 请求携带 MainToolDefs
  ↓
LLM 生成 tool_calls
  ↓
llmloop.Runner 读取 resp.ToolCalls()
  ↓
executeToolCall(...)
  ↓
处理 task_done / code_comment / 普通工具
  ↓
Registry.Get(toolName)
  ↓
Provider.Execute(...) 或 code_comment 特殊处理
  ↓
recordToolCall(toolName)
  ↓
telemetry 打印工具调用日志
  ↓
工具结果返回给 LLM
  ↓
LLM 继续分析
  ↓
code_comment 提交评论
  ↓
CommentCollector 收集评论
  ↓
Review filter 校验并移除可证明错误的评论
  ↓
输出终端结果或 JSON
```

这张图是本文最重要的源码理解。

它说明 OpenCodeReview 的 Agent 工具调用并不是抽象概念，而是由几个明确的源码模块协作完成：

```text
review_cmd.go
  负责注册工具实现

internal/config/toolsconfig/tools.json
  负责定义暴露给 LLM 的工具 schema

internal/tool
  负责定义和实现工具 Provider

internal/llmloop
  负责执行工具调用循环

internal/telemetry
  负责打印工具调用日志和记录指标

CommentCollector
  负责收集 code_comment 提交的评论
```

---

## 二十三、Review filter removed comment 是什么

本次终端日志中还有一行：

```text
[ocr] Review filter removed 1 comment(s) for s01/src/user.js
```

为了定位它，我搜索：

```powershell
Select-String -Path .\internal\**\*.go -Pattern "Review filter removed"
```

输出结果：

```text
internal\agent\agent.go:540:    fmt.Fprintf(stdout.Writer(), "[ocr] Review filter removed %d comment(s) for %s\n", len(indices), newPath)
```

这说明这条日志来自：

```text
internal/agent/agent.go
```

它表示：

```text
Agent 原本生成了一些评论，
但是 Review filter 过滤掉了其中一部分。
```

为什么要过滤？

这里需要说得更准确一点：Review filter 不是普通去重器，也不是泛化的质量评分器。

源码注释里的语义是：

```text
移除那些仅根据当前 diff 就能证明是错误的评论。
```

它会把当前文件的 diff 和已经生成的评论再次交给 LLM，让它返回需要删除的评论编号。

简化流程是：

```text
executeReviewFilter
  ↓
读取当前文件 comments
  ↓
把 diff 和 comments 组装成 ReviewFilterTask prompt
  ↓
LLM 返回要移除的评论 ID 列表
  ↓
parseFilterResponse
  ↓
CommentCollector.RemoveByPathAndIndices
```

这一步体现了 OpenCodeReview 的工程化设计：

```text
不是 LLM 生成什么就全部输出，
而是增加了一层基于 diff 的结果校验。
```

---

## 二十四、结合本次 Review 评论理解 code_comment

本次终端执行最终输出了 2 条评论。

第一条是 SQL 注入问题：

```text
s01/src/user.js:37-37
```

指出：

```text
email 和 userId 被直接拼接到 SQL 查询字符串中，存在 SQL 注入风险。
```

建议改成：

```js
db.query("UPDATE users SET email = ? WHERE id = ?", [email, userId]);
```

第二条是异步和错误处理问题：

```text
s01/src/user.js:36-39
```

指出：

```text
db.query 可能是异步操作；
当前函数没有 await；
没有 try/catch；
可能在数据库操作失败时仍然返回 true。
```

建议改成：

```js
async function updateUserEmail(db, userId, email) {
  try {
    await db.query("UPDATE users SET email = ? WHERE id = ?", [email, userId]);
    return true;
  } catch (error) {
    console.error('Failed to update user email:', error);
    throw new Error('Failed to update user email');
  }
}
```

从源码角度看，这些最终评论不是普通文本随便输出的，而是通过：

```text
code_comment
  ↓
CommentCollector
  ↓
Review filter
  ↓
emitRunResult
```

这样的链路进入最终结果。

---

## 二十五、普通 Prompt Review 和 OpenCodeReview 的区别

通过这一篇源码分析，可以更清楚地区分普通 Prompt Review 和 OpenCodeReview。

| 对比项  | 普通 Prompt Review | OpenCodeReview              |
| ---- | ---------------- | ----------------------------- |
| 输入   | 用户手动复制代码         | Git diff 自动识别                 |
| 规则   | 临时写在 Prompt 中    | `.opencodereview/rule.json`   |
| 上下文  | 只能看用户粘贴内容        | 可通过工具读取文件、diff、搜索代码           |
| 工具注册 | 没有明确工具注册表        | `buildToolRegistry` 注册 Provider |
| 工具描述 | 没有结构化 schema        | `tools.json` 定义工具参数和阶段       |
| 工具实现 | 没有工程实现           | `internal/tool` 中有具体 Provider |
| 工具执行 | 不存在              | `llmloop` 执行 tool calls       |
| 日志   | 不透明              | telemetry 输出工具调用日志            |
| 统计   | 很难统计             | JSON 中有 `tool_calls`          |
| 评论收集 | 普通文本             | `CommentCollector` 收集结构化评论    |
| 评论过滤 | 通常没有             | Review filter 过滤低质量评论         |

所以 OpenCodeReview 更像是：

```text
确定性工程 + Agent 工具调用 + LLM 分析 + 评论过滤 + 结构化输出
```

而不是一个简单的大模型脚本。

---

## 二十六、本篇使用的 PowerShell 命令记录

### 1. 搜索工具注册入口

```powershell
Select-String -Path .\cmd\opencodereview\review_cmd.go -Pattern "buildToolRegistry"
```

### 2. 查看工具注册函数

```powershell
Get-Content .\cmd\opencodereview\review_cmd.go | Select-Object -Skip 180 -First 40
```

### 3. 查看工具名称定义

```powershell
Get-Content .\internal\tool\definitions.go
```

### 4. 查看工具目录

```powershell
Get-ChildItem .\internal\tool
```

### 5. 查看工具 schema 配置

```powershell
Get-Content .\internal\config\toolsconfig\tools.json
Get-Content .\internal\config\toolsconfig\toolsconfig.go
```

### 6. 搜索各工具实现

```powershell
Select-String -Path .\internal\tool\*.go -Pattern "NewFileRead"
Select-String -Path .\internal\tool\*.go -Pattern "NewFileFind"
Select-String -Path .\internal\tool\*.go -Pattern "NewFileReadDiff"
Select-String -Path .\internal\tool\*.go -Pattern "NewCodeSearch"
Select-String -Path .\internal\tool\*.go -Pattern "CodeCommentProvider"
```

### 7. 搜索工具调用链路

```powershell
Select-String -Path .\internal\**\*.go -Pattern "ToolCall"
```

### 8. 搜索 file_read 相关日志和测试

```powershell
Select-String -Path .\internal\**\*.go -Pattern "file_read"
```

### 9. 搜索 Review filter 日志

```powershell
Select-String -Path .\internal\**\*.go -Pattern "Review filter removed"
```

---

## 二十七、本篇总结

通过这一篇，对 OpenCodeReview 的 Agent 工具调用有了更深入的理解。

第一篇中，从运行日志看到：

```text
file_read
file_find
code_search
code_comment
```

而这一篇通过源码进一步确认：

```text
这些工具是在 review_cmd.go 的 buildToolRegistry 中注册 Provider 实现的；
工具名称定义在 internal/tool/definitions.go；
工具 schema 定义在 internal/config/toolsconfig/tools.json；
工具实现分布在 internal/tool 目录下；
所有普通工具都实现 Provider 接口；
Registry 负责保存工具名和工具实现的映射；
file_read_diff 会在 Agent.Run 加载 diff 后通过 injectDiffMap 注入真实 diff；
LLM 返回 tool_calls 后，由 llmloop 执行工具；
task_done 和 code_comment 在 llmloop 中有特殊处理；
工具执行时会通过 telemetry 打印日志；
工具调用次数会通过 recordToolCall 统计；
code_comment 会把评论提交给 CommentCollector；
Review filter 会移除那些仅根据 diff 就能证明错误的评论。
```

当前对 `ocr review` 的理解可以串成下面这条主线：

```text
Git diff
  ↓
确定审查文件

rule.json
  ↓
确定审查规则

buildToolRegistry
  ↓
注册 Agent 工具实现

tools.json
  ↓
定义 LLM 可见的工具 schema

llmloop
  ↓
执行 LLM 返回的 tool_calls

internal/tool
  ↓
真正读取文件、搜索代码、提交评论

telemetry
  ↓
打印工具调用日志

CommentCollector
  ↓
收集评论

Review filter
  ↓
移除可由 diff 证明错误的评论

emitRunResult
  ↓
输出文本或 JSON
```

这说明 OpenCodeReview 的审查流程不是：

```text
diff → LLM → 评论
```

而更接近：

```text
diff → rules → tools → agent loop → comments → filter → output
```




---

## 二十八、下一篇计划：JSON 输出结构与 Markdown 报告设计

下一篇准备继续学习：

```text
从 0 学习 Alibaba OpenCodeReview：JSON 输出结构与 Markdown 报告设计
```

前面几篇已经知道：

```text
Git diff 决定审查哪些文件；
rule.json 决定按什么规则审查；
Agent 工具调用负责获取上下文和生成评论。
```

接下来要继续分析：

```text
OpenCodeReview 的审查结果是如何被结构化输出的？
```

在第一篇和第五篇中，我都使用过：

```powershell
ocr review --format json > ocr-review-result.json
```

下一篇会重点分析：

```text
1. JSON 输出中的 status、summary、tool_calls、comments；
2. comments 中 path、start_line、end_line、existing_code 的作用；
3. tool_calls 如何支撑 Agent 可观测性；
4. summary 中 token 和 elapsed 如何反映成本；
5. 如何把 OCR JSON 转换成 Markdown Report；
6. 这一步如何为后续 Code Review Agent MVP 做准备。
```

如果说第五篇解决的是：

```text
Agent 工具是如何注册和调用的？
```

那么第六篇要解决的是：

```text
Agent 审查结果如何被结构化保存，并为后续工程化处理做准备？
```
