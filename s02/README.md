# 从 0 学习 Alibaba Open Code Review（二）：ocr review 命令入口分析
## 前言

上一篇文章中，从使用者角度跑通了 Alibaba Open Code Review 的基础流程，包括安装配置、`ocr llm test`、`ocr review --preview`、`ocr review`、JSON 输出、自定义规则配置，以及工具调用日志分析。

通过第一篇学习，已经知道：

```text
ocr review 可以识别 Git diff；
ocr review 可以对变更代码生成审查意见；
ocr review --preview 可以预览本次会审查哪些文件；
ocr review --format json 可以输出结构化结果；
.opencodereview/rule.json 可以影响审查重点。
```

不过到目前为止，只是停留在“会使用”的阶段。

从这一篇开始，进入源码阅读阶段。本文先从最外层的 CLI 命令入口开始，解决一个最基础的问题：

```text
当执行 ocr review 时，OpenCodeReview 的源码是从哪里开始执行的？
```

这篇文章的目标不是一次性读懂全部源码，而是先找到 `ocr review` 的入口，建立第一张简单的源码地图。

---

## 一、本文基于的源码环境

本文基于本地 `open-code-review-main` 源码阅读，重点分析下面三个文件：

```text
cmd/opencodereview/main.go
cmd/opencodereview/review_cmd.go
cmd/opencodereview/flags.go
```

---

## 二、本篇学习目标

本文主要解决下面几个问题：

```text
1. OpenCodeReview 的项目目录结构大概是什么样的？
2. ocr review 命令在哪里被分发？
3. runReview 函数在哪里定义？
4. ocr review 的参数是如何被解析的？
5. reviewOptions 是什么？
6. parseReviewFlags 除了解析参数，还做了哪些校验？
7. 如何画出 ocr review 的第一层调用链？
```

通过本文，完成从：

```text
会使用 ocr review
```

到：

```text
能找到 ocr review 的源码入口
```

的过渡。

---

## 三、为什么先从命令入口开始读源码

对于 OpenCodeReview 这种 CLI 工具来说，最自然的源码阅读方式就是从命令入口开始。

因为用户真正执行的是：

```bash
ocr review
```

所以源码阅读的第一步应该是找到：

```text
ocr review 这个命令在哪里被识别？
```

然后再继续看：

```text
它进入了哪个函数？
这个函数第一步做了什么？
命令参数是怎么解析的？
```

如果一开始就直接看 Agent、LLM、Git diff 或工具调用，很容易迷路。

所以这一篇只做一件事：

```text
找到 ocr review 的启动入口。
```

---

## 四、准备源码阅读环境

首先进入 OpenCodeReview 源码目录：

```powershell
cd D:\agent\open-code-review-main
```

查看项目根目录：

```powershell
dir
```

可以看到项目中包含很多目录和文件，例如：

```text
cmd
internal
examples
plugins
skills
pages
npm
README.md
README.zh-CN.md
go.mod
go.sum
Makefile
```

这一篇不需要理解所有目录，只需要先关注两个目录：

| 目录 | 作用 |
| --- | --- |
| `cmd` | CLI 命令入口，本文重点关注 |
| `internal` | 项目内部核心逻辑，后续文章再深入 |

对于第二篇来说，最重要的是：

```text
cmd
```

因为要先找到：

```text
ocr review 命令是从哪里进入的？
```

---

## 五、查看 `cmd` 目录

进入 `cmd` 目录查看：

```powershell
dir .\cmd
```

继续查看 `cmd/opencodereview`：

```powershell
dir .\cmd\opencodereview
```

这里可以看到一些和 CLI 命令相关的 Go 文件，例如：

```text
main.go
flags.go
review_cmd.go
shared.go
output.go
```

这一篇先重点关注三个文件：

| 文件 | 本文关注点 |
| --- | --- |
| `main.go` | CLI 总入口，负责分发命令 |
| `review_cmd.go` | `ocr review` 对应的入口函数 |
| `flags.go` | `ocr review` 参数解析逻辑 |

暂时不深入：

```text
shared.go
output.go
internal/agent
internal/tool
```

这些内容后续再拆。

---

## 六、搜索 `review` 命令

为了定位 `ocr review` 相关代码，可以在项目根目录执行：

```powershell
Select-String -Path .\cmd\**\*.go -Pattern "review"
```

这个命令会在 `cmd` 目录下搜索所有 Go 文件中包含 `review` 的代码。

如果本地安装了 `ripgrep`，也可以使用：

```powershell
rg "runReview|parseReviewFlags|reviewOptions" .\cmd
```

从搜索结果中，可以重点关注几个文件：

```text
cmd\opencodereview\main.go
cmd\opencodereview\flags.go
cmd\opencodereview\review_cmd.go
```

这三个文件基本可以帮助回答本文最核心的问题：

```text
ocr review 是如何从命令行进入源码逻辑的？
```

---

## 七、分析 `main.go`：CLI 总入口

先查看 `main.go` 的前面部分：

```powershell
Get-Content .\cmd\opencodereview\main.go | Select-Object -First 80
```

在 `main.go` 中，可以看到 `main()` 会调用一个命令分发函数：

```go
if err := dispatch(); err != nil {
    fmt.Fprintf(os.Stderr, "Error: %v\n", err)
    os.Exit(1)
}
```

继续看 `dispatch()`，其中和 `review` 相关的逻辑是：

```go
case "review", "r":
    return runReview(args[1:])
```

这行代码非常关键。

它说明当用户执行：

```bash
ocr review
```

或者使用简写：

```bash
ocr r
```

程序都会进入：

```go
runReview(args[1:])
```

也就是说：

```text
main.go 并不直接完成代码审查，
它只是根据用户输入的子命令，把流程分发给对应函数。
```

所以目前可以得到第一段调用链：

```text
用户执行 ocr review
        ↓
cmd/opencodereview/main.go
        ↓
main()
        ↓
dispatch()
        ↓
case "review", "r"
        ↓
runReview(args[1:])
```

这一步解决了第一个问题：

```text
ocr review 命令是在哪里被分发的？
```

答案是：

```text
cmd/opencodereview/main.go
```

---

## 八、理解 `args[1:]` 是什么意思

这里有一个容易困惑的地方：

```go
runReview(args[1:])
```

为什么不是直接传 `args`，而是传：

```go
args[1:]
```

可以简单理解为：

```text
args[0] 是子命令 review
args[1:] 是 review 后面的参数
```

例如用户执行：

```bash
ocr review --preview
```

那么命令参数大概可以理解为：

```text
args[0] = "review"
args[1] = "--preview"
```

当程序已经通过 `args[0]` 判断出这是 `review` 命令后，后面传给 `runReview` 的就只需要是：

```text
--preview
```

所以：

```go
runReview(args[1:])
```

就是把 `review` 后面的参数传进去。

再举一个例子：

```bash
ocr review --format json
```

可以理解为：

```text
review 是子命令
--format json 是 review 命令自己的参数
```

所以 `runReview` 只需要关心：

```text
--format json
```

而不需要再关心 `review` 这个单词本身。

---

## 九、分析 `review_cmd.go`：找到 `runReview`

接下来查看 `review_cmd.go`：

```powershell
Get-Content .\cmd\opencodereview\review_cmd.go | Select-Object -First 80
```

可以看到 `runReview` 函数是这样开始的：

```go
func runReview(args []string) error {
    opts, err := parseReviewFlags(args)
    if err != nil {
        return err
    }

    if opts.showHelp {
        printReviewUsage()
        return nil
    }

    ...
}
```

这一段说明：

```text
runReview 是 ocr review 命令的核心入口函数。
```

而它做的第一件事是：

```go
parseReviewFlags(args)
```

也就是解析用户传入的命令行参数。

例如：

```bash
ocr review --preview
```

里面的：

```text
--preview
```

就会在这里被解析。

因此，第二段调用链可以补充为：

```text
用户执行 ocr review
        ↓
main.go
        ↓
runReview(args[1:])
        ↓
parseReviewFlags(args)
```

到这里，已经知道：

```text
ocr review 不是直接开始审查代码，
而是先进入 runReview，
然后先解析参数。
```

---

## 十、先看一眼 `runReview` 后续流程

这一篇不深入分析 `runReview` 后面的完整审查流程，但可以先建立一个简化地图。

在 `parseReviewFlags` 之后，`runReview` 后续大概会继续做这些事情：

```text
parseReviewFlags
        ↓
loadCommonContext
        ↓
applyCLIExcludes
        ↓
validateReviewRefs
        ↓
runPreview 或 loadLLMRuntime
        ↓
buildToolRegistry
        ↓
agent.New
        ↓
ag.Run
        ↓
emitRunResult
```

可以先简单理解为：

```text
1. 解析参数；
2. 加载仓库、规则、文件过滤器等公共上下文；
3. 校验 Git ref 参数是否合法；
4. 如果是 preview 模式，只生成预览结果；
5. 如果不是 preview 模式，就加载 LLM Runtime；
6. 构建 Agent 可用工具；
7. 创建 Agent；
8. 执行审查；
9. 输出结果。
```

这一篇只重点理解最前面的入口：

```text
main.go
  ↓
runReview
  ↓
parseReviewFlags
```

后面的 `Git diff`、规则匹配、Agent 工具调用、JSON 输出，会在后续文章中逐步拆开。

---

## 十一、分析 `flags.go`：参数解析入口

接下来查看 `flags.go` 中和 `review` 相关的部分：

```powershell
Get-Content .\cmd\opencodereview\flags.go | Select-Object -Skip 90 -First 90
```

可以看到有一个结构体：

```go
type reviewOptions struct {
    toolConfigPath string
    rulePath       string
    repoDir        string
    from           string
    to             string
    commit         string
    excludes       string
    outputFormat   string
    audience       string
    background     string
    model          string
    concurrency    int
    perFileTimeout int
    maxTools       int
    maxGitProcs    int
    preview        bool
    showHelp       bool
}
```

这个结构体可以简单理解为：

```text
ocr review 命令的参数集合。
```

也就是说，用户在命令行输入的参数，最后会被保存到这个结构体里。

例如用户执行：

```bash
ocr review --preview
```

程序内部就会得到：

```text
preview = true
```

用户执行：

```bash
ocr review --format json
```

程序内部就会得到：

```text
outputFormat = "json"
```

用户执行：

```bash
ocr review --commit abc123
```

程序内部就会得到：

```text
commit = "abc123"
```

所以 `reviewOptions` 是连接：

```text
命令行输入
```

和：

```text
内部审查流程
```

的中间对象。

---

## 十二、什么是 `parseReviewFlags`

在 `flags.go` 中，还可以看到：

```go
func parseReviewFlags(args []string) (reviewOptions, error) {
    ...
}
```

这个函数的核心作用是：

```text
把用户输入的命令行参数解析成 reviewOptions。
```

比如：

```bash
ocr review --preview
```

经过 `parseReviewFlags` 之后，大概可以理解为：

```text
reviewOptions{
    preview: true,
}
```

再比如：

```bash
ocr review --format json
```

解析之后大概可以理解为：

```text
reviewOptions{
    outputFormat: "json",
}
```

不过 `parseReviewFlags` 不只是解析参数，它还会做一部分参数合法性校验。

例如源码中可以看到类似逻辑：

```text
--from 和 --to 必须成对出现；
--commit 不能和 --from / --to 同时使用；
--audience 只能是 human 或 agent；
--max-tools 不能是负数，并且非 0 时会有最小值限制；
--max-git-procs 不能是负数。
```

因此，`parseReviewFlags` 做的是两件事：

```text
1. 把字符串形式的命令行参数，变成程序内部能使用的结构体字段；
2. 在真正进入审查流程之前，先拦截明显非法的参数组合。
```

这一点很重要，因为它说明 CLI 层不仅负责“接收输入”，也承担了第一层输入校验职责。

---

## 十三、先理解几个常用参数

`ocr review` 支持很多参数，先重点理解几个常见参数。

### 1. `--preview`：预览审查范围

源码中可以看到类似代码：

```go
a.BoolVarP(&opts.preview, "preview", "p", false, "preview which files will be reviewed without running the LLM")
```

这说明：

```text
--preview 是一个布尔参数；
-p 是它的短参数；
默认值是 false。
```

所以：

```bash
ocr review --preview
```

和：

```bash
ocr review -p
```

是等价的。

它的作用是：

```text
只预览本次会审查哪些文件，不真正调用 LLM。
```

第一篇中执行过：

```bash
ocr review --preview
```

输出：

```text
Preview: 1 file(s) changed  |  +7  -1

Will review (1):
  [M]  src/user.js          +7    -1
```

现在结合源码可以理解：

```text
用户传入 --preview
        ↓
parseReviewFlags 解析 preview = true
        ↓
runReview 后续会根据 preview 判断是否进入预览模式
```

### 2. `--format`：控制输出格式

源码中可以看到类似代码：

```go
a.StringVarP(&opts.outputFormat, "format", "f", "text", "output format: text or json")
```

这说明：

```text
--format 用于控制输出格式；
-f 是短参数；
默认值是 text。
```

默认执行：

```bash
ocr review
```

输出的是普通文本结果。

如果执行：

```bash
ocr review --format json
```

或者：

```bash
ocr review -f json
```

就会输出 JSON 格式结果。

第一篇中已经用过：

```powershell
ocr review --format json > ocr-review-result.json
```

这个 JSON 输出后面非常重要，因为可以基于它继续做：

```text
Markdown 报告生成
审查历史保存
GitHub Actions 集成
Agent Workflow
```

### 3. `--commit`：审查指定提交

源码中可以看到类似代码：

```go
a.StringVarP(&opts.commit, "commit", "c", "", "single commit hash or tag to review (vs its parent)")
```

这说明：

```text
--commit 用于审查某一个指定 commit；
-c 是短参数。
```

例如：

```bash
ocr review --commit abc123
```

可以理解为：

```text
审查 abc123 这个提交相对于它父提交带来的代码变更。
```

这和默认的工作区审查不同。

默认执行：

```bash
ocr review
```

通常审查当前工作区中的变更。

而：

```bash
ocr review --commit abc123
```

审查的是某一次提交。

### 4. `--from` 和 `--to`：审查两个引用之间的差异

源码中可以看到类似代码：

```go
a.StringVar(&opts.from, "from", "", "source ref to start diff from (e.g., 'main')")
a.StringVar(&opts.to, "to", "", "target ref to end diff at (e.g., 'feature-branch')")
```

这说明：

```text
--from 和 --to 用于指定 diff 的起点和终点。
```

例如：

```bash
ocr review --from main --to feature-branch
```

可以理解为：

```text
审查 main 到 feature-branch 之间的代码差异。
```

注意：`--from` 和 `--to` 必须成对出现。

如果只写：

```bash
ocr review --from main
```

而不写 `--to`，`parseReviewFlags` 会返回错误。

---

## 十四、参数解析小结

到这里，对 `ocr review` 参数解析有了一个初步理解：

```text
用户输入命令
        ↓
main.go 分发到 runReview
        ↓
runReview 调用 parseReviewFlags
        ↓
parseReviewFlags 把参数保存到 reviewOptions
        ↓
parseReviewFlags 校验参数组合是否合法
```

可以画成：

```text
ocr review --preview
        ↓
args = ["--preview"]
        ↓
parseReviewFlags(args)
        ↓
reviewOptions.preview = true
```

再比如：

```text
ocr review --format json
        ↓
args = ["--format", "json"]
        ↓
parseReviewFlags(args)
        ↓
reviewOptions.outputFormat = "json"
```

所以 `reviewOptions` 可以理解为：

```text
一次 ocr review 命令的配置对象。
```

---

## 十五、查看 `ocr review -h`

除了看源码，还可以通过帮助命令确认参数：

```powershell
ocr review -h
```

这个命令会显示 `ocr review` 支持的参数。

源码中的参数定义，最终会体现在帮助信息里。

例如：

```text
--preview
--format
--commit
--from
--to
--rule
--repo
--concurrency
--timeout
--model
```

看源码时可以配合帮助信息一起理解：

```text
源码中定义了什么参数
        ↓
ocr review -h 中显示什么参数
        ↓
实际命令怎么使用这个参数
```

这样会比单独看 Go 代码更容易理解。

---

## 十六、第二篇的完整简化流程图

根据本文阅读到的内容，现在可以整理出 `ocr review` 的第一层调用链：

```text
用户执行 ocr review
        ↓
cmd/opencodereview/main.go
        ↓
main()
        ↓
dispatch()
        ↓
case "review", "r"
        ↓
runReview(args[1:])
        ↓
cmd/opencodereview/review_cmd.go
        ↓
parseReviewFlags(args)
        ↓
cmd/opencodereview/flags.go
        ↓
生成 reviewOptions
```

如果用户执行：

```bash
ocr review --preview
```

可以理解为：

```text
ocr review --preview
        ↓
main.go 分发 review 命令
        ↓
runReview(["--preview"])
        ↓
parseReviewFlags
        ↓
reviewOptions.preview = true
```

如果用户执行：

```bash
ocr review --format json
```

可以理解为：

```text
ocr review --format json
        ↓
main.go 分发 review 命令
        ↓
runReview(["--format", "json"])
        ↓
parseReviewFlags
        ↓
reviewOptions.outputFormat = "json"
```

这就是本文最核心的收获。

---

## 十七、目前暂时没有深入的内容

这一篇只是源码阅读的第一步。

目前还没有深入分析：

```text
Git diff 是如何获取的；
Preview 中的 [M] 是怎么来的；
+7 -1 是如何统计的；
rule.json 是如何匹配文件的；
Agent 工具是如何注册的；
file_read / code_search 是如何调用的；
LLM Provider 是如何加载的；
JSON 输出是如何组装的。
```

所以本文只建立一个最基础的入口认知：

```text
ocr review 是从 main.go 分发到 runReview，
再由 runReview 调用 parseReviewFlags 解析并校验参数。
```

---

## 十八、本文使用的 PowerShell 命令记录

为了方便后续复盘，这里整理一下本文用到的主要命令。

### 1. 进入源码目录

```powershell
cd D:\agent\open-code-review-main
```

### 2. 查看项目根目录

```powershell
dir
```

### 3. 查看 `cmd` 目录

```powershell
dir .\cmd
```

### 4. 查看 `cmd/opencodereview` 目录

```powershell
dir .\cmd\opencodereview
```

### 5. 搜索 `review` 相关代码

```powershell
Select-String -Path .\cmd\**\*.go -Pattern "review"
```

或者：

```powershell
rg "runReview|parseReviewFlags|reviewOptions" .\cmd
```

### 6. 查看 `main.go`

```powershell
Get-Content .\cmd\opencodereview\main.go | Select-Object -First 80
```

### 7. 查看 `review_cmd.go`

```powershell
Get-Content .\cmd\opencodereview\review_cmd.go | Select-Object -First 80
```

### 8. 查看 `flags.go` 中的 review 参数

```powershell
Get-Content .\cmd\opencodereview\flags.go | Select-Object -Skip 90 -First 90
```

### 9. 查看帮助信息

```powershell
ocr review -h
```

---

## 十九、总结

### 1. `ocr review` 从哪里进入？

答案是：

```text
cmd/opencodereview/main.go
```

在这里，程序会根据用户输入的子命令进行分发。

### 2. `ocr review` 会进入哪个函数？

答案是：

```go
runReview(args[1:])
```

也就是说：

```text
ocr review
```

和：

```text
ocr r
```

最终都会进入 `runReview`。

### 3. `runReview` 第一步做什么？

答案是：

```go
parseReviewFlags(args)
```

也就是先解析命令行参数。

### 4. 参数解析结果保存到哪里？

答案是：

```go
reviewOptions
```

`reviewOptions` 可以理解为：

```text
一次 ocr review 命令的参数集合。
```

### 5. `parseReviewFlags` 除了解析参数，还做了什么？

它还会做基础参数校验，例如：

```text
--from / --to 必须成对出现；
--commit 不能和 --from / --to 同时使用；
--audience 只能是 human 或 agent；
部分数值参数不能为非法值。
```

### 6. 本文建立的源码地图是什么？

可以总结为：

```text
main.go
  ↓
dispatch()
  ↓
runReview()
  ↓
parseReviewFlags()
  ↓
reviewOptions
```

这就是对 `ocr review` 的第一层源码理解。

---

## 二十、下一篇计划：Git Diff 解析流程

通过本文，已经知道：

```text
ocr review 是如何从 CLI 入口进入 runReview 的。
```

下一篇继续分析：

```text
从 0 学 OpenCodeReview 源码：Git Diff 解析流程
```

下一篇主要解决这些问题：

```text
1. ocr review --preview 为什么能识别 src/user.js？
2. Preview 中的 [M] 是怎么来的？
3. +7 -1 是如何统计出来的？
4. OpenCodeReview 如何判断哪些文件需要审查？
5. rule.json 中的 exclude 如何影响审查范围？
```

第一篇解决的是：

```text
ocr review 能做什么？
```

第二篇解决的是：

```text
ocr review 是从哪里启动的？
```

第三篇继续解决：

```text
ocr review 的输入 Git diff 是怎么生成的？
```
