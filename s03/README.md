#从 0 学习 Alibaba Open Code Review（三）：Git Diff 解析流程

## 前言

上一篇文章中，从源码角度找到了 `ocr review` 的命令入口。

当用户执行：


```bash
ocr review
```


程序会从 `cmd/opencodereview/main.go` 进入命令分发逻辑，然后进入：

```go
runReview(args[1:])
```

接着会调用：

```go
parseReviewFlags(args)
```

解析命令行参数。

也就是说，第二篇主要解决的是：

```text
ocr review 是从哪里启动的？
```

这一篇继续往下学习一个更基础、也更关键的问题：

```text
ocr review 为什么知道我改了哪个文件？
```

在第一篇中，执行过：

```bash
ocr review --preview
```

终端输出：

```text
Preview: 1 file(s) changed  |  +7  -1

Will review (1):
  [M]  s01/src/user.js
```

当时只是知道：

```text
OpenCodeReview 识别到了 s01/src/user.js 的变更。
```

但是还不清楚：

```text
[M] 是什么意思？
+7 -1 是怎么来的？
为什么它知道要审查这个文件？
ocr review --preview 和 git diff 有什么关系？
```

所以本文就围绕这些问题，学习 Open Code Review 的核心输入：**Git Diff**。

---

## 一、本篇学习目标

本文主要解决下面几个问题：

```text
1. 什么是 Git diff？
2. 为什么 ocr review 依赖 Git diff？
3. git status、git diff 和 ocr review --preview 有什么关系？
4. [M] 表示什么？
5. +7 -1 是怎么统计出来的？
6. 为什么 Git diff 中会出现 -1？
7. ocr review --preview 做了什么？
```


这一篇关注：

```text
Open Code Review 是如何识别本次代码变更的？
```

---

## 二、为什么先学习 Git Diff

`ocr review` 和 `ocr scan` 不一样。

`ocr scan` 更偏向全量扫描目录或文件，而 `ocr review` 的核心是审查本次代码变更。

也就是说，`ocr review` 首先要知道：

```text
这次改了哪些文件？
每个文件新增了多少行？
每个文件删除了多少行？
哪些文件需要审查？
哪些文件应该排除？
```

这些信息主要来自 Git。

所以可以先简单理解为：

```text
Git diff 是 ocr review 的输入。
```

如果没有 Git diff，`ocr review` 就不知道本次要审查哪些代码变更。

这也是为什么 Open Code Review 适合用于：

```text
本地未提交变更审查
commit 审查
分支差异审查
Pull Request 审查
```

因为这些场景的本质都是：

```text
比较两份代码之间的差异。
```

---

## 三、准备一个代码变更

为了方便观察 Git diff，在练习项目中修改了：

```text
s01/src/user.js
```

本次新增了一个函数：

```js
function updateUserEmail(db, userId, email) {
  db.query("UPDATE users SET email = '" + email + "' WHERE id = " + userId);
  return true;
}
```

并且在 `module.exports` 中导出了它：

```js
module.exports = {
  getUserName,
  login,
  buildUserQuery,
  fetchUser,
  deleteUser,
  updateUserEmail
};
```

这个函数写得比较简单，而且包含明显的问题：

```text
1. SQL 字符串拼接；
2. 没有参数化查询；
3. 没有错误处理；
4. 总是 return true。
```

不过这一篇不分析代码审查结果，只分析 Git diff 和 preview 输出。

---

## 四、查看当前 Git 状态

首先进入练习项目目录：

```powershell
cd D:\agent\open-code-review-main\ocr-practice-demo
```

然后执行：

```powershell
git status --short
```

输出结果中可以看到：

```text
 M s01/src/user.js
```

这里的：

```text
M
```

表示文件被修改了。

也就是说，Git 已经检测到：

```text
s01/src/user.js 发生了修改。
```

注意这里的 `M` 是 Git 原生输出中的文件状态。

后面 `ocr review --preview` 中看到的：

```text
[M]
```

也是类似含义，表示：

```text
Modified，文件被修改。
```

---

## 五、查看变更文件状态：`git diff --name-status`

接着执行：

```powershell
git diff --name-status
```

输出类似：

```text
M       s01/src/user.js
```

这条命令只关心：

```text
哪些文件变了？
这些文件是什么状态？
```

其中：

```text
M = Modified，修改文件
A = Added，新增文件
D = Deleted，删除文件
R = Renamed，重命名文件
```

所以这次输出：

```text
M       s01/src/user.js
```

表示：

```text
s01/src/user.js 是一个被修改的文件。
```

这和 `ocr review --preview` 中的：

```text
[M]  s01/src/user.js
```

是对应的。


---

## 六、查看新增和删除行数：`git diff --numstat`

继续执行：

```powershell
git diff --numstat
```

输出结果：

```text
7       1       s01/src/user.js
```

这三个部分分别表示：

```text
7    新增行数
1    删除行数
文件路径
```

所以这次变更可以理解为：

```text
src/user.js 新增了 7 行，删除了 1 行。
```

这个输出可以帮助我们验证 `ocr review --preview` 中 `+7 -1` 的含义：

```text
7 insertions  →  +7
1 deletion    →  -1
```

需要注意：这里是用 `git diff --numstat` 辅助理解 Preview 输出，并不表示 OpenCodeReview 源码中直接调用了 `git diff --numstat`。

从源码角度看，OpenCodeReview 会先获取 unified diff 文本，再解析 diff 内容，统计每个文件的新增行和删除行。

---

## 七、查看 diff 统计：`git diff --stat`

继续执行：

```powershell
git diff --stat
```

输出结果：

```text
.../src/user.js"                                                  | 8 +++++++-

1 file changed, 7 insertions(+), 1 deletion(-)
```

这条输出更适合人阅读。

它说明：

```text
1 个文件发生变化；
新增了 7 行；
删除了 1 行。
```

其中：

```text
7 insertions(+)
```

表示新增 7 行。

```text
1 deletion(-)
```

表示删除 1 行。

这和前面的 `git diff --numstat`、`ocr review --preview` 是一致的。

可以整理成下面的对应关系：

| 命令                       | 输出                                         | 含义                      |
| ------------------------ | ------------------------------------------ | ----------------------- |
| `git diff --name-status` | `M s01/src/user.js`                        | 文件被修改                   |
| `git diff --numstat`     | `7 1 s01/src/user.js`                      | 新增 7 行，删除 1 行           |
| `git diff --stat`        | `1 file changed, 7 insertions, 1 deletion` | 变更统计                    |
| `ocr review --preview`   | `[M] src/user.js +7 -1`                    | Open Code Review 预览审查范围 |

---

## 八、查看具体 diff 内容

接下来执行：

```powershell
git diff
```

可以看到具体代码差异：

```diff
diff --git a/s01：用最小 Demo 跑通 AI 代码审查/src/user.js b/s01：用最小 Demo 跑通 AI 代码审查/src/user.js
index 1445e1f..f9f2188 100644
--- a/s01/src/user.js
+++ b/s01/src/user.js
@@ -33,10 +33,16 @@ function deleteUser(db, userId) {
   return true;
 }

+function updateUserEmail(db, userId, email) {
+  db.query("UPDATE users SET email = '" + email + "' WHERE id = " + userId);
+  return true;
+}
+
 module.exports = {
   getUserName,
   login,
   buildUserQuery,
   fetchUser,
-  deleteUser
+  deleteUser,
+  updateUserEmail
 };
```

这段 diff 是理解 `+7 -1` 的关键。

其中这一行叫做 hunk header：

```diff
@@ -33,10 +33,16 @@ function deleteUser(db, userId) {
```

可以简单理解为：

```text
-33,10 表示旧文件从第 33 行开始，共 10 行；
+33,16 表示新文件从第 33 行开始，共 16 行。
```

这类行号信息后面会非常重要，因为 Agent 最终生成的 `code_comment` 需要定位到具体文件和具体代码行。

---

## 九、理解 diff 中的 `+` 和 `-`

在 Git diff 中：

```text
+ 表示新增行
- 表示删除行
```

例如下面这几行：

```diff
+function updateUserEmail(db, userId, email) {
+  db.query("UPDATE users SET email = '" + email + "' WHERE id = " + userId);
+  return true;
+}
+
```

这些都是新增行。

所以它们会被统计到：

```text
+7
```

而这一行：

```diff
-  deleteUser
```

表示旧版本中原来是：

```js
  deleteUser
```

后来变成了：

```diff
+  deleteUser,
+  updateUserEmail
```

也就是：

```js
  deleteUser,
  updateUserEmail
```

所以 Git 认为：

```text
旧的 deleteUser 这一行被删除；
新的 deleteUser, 这一行被新增；
updateUserEmail 这一行也被新增。
```

这就是为什么只是加了一个逗号，却会出现：

```text
-1
```

---


## 十、执行 `ocr review --preview`

接下来执行 Open Code Review 的预览命令：

```powershell
ocr review --preview
```

输出结果：

```text
[ocr] A new version (v1.7.0) is available. Run to update:
  npm i -g @alibaba-group/open-code-review@1.7.0


Preview: 1 file(s) changed  |  +7  -1

Will review (1):
  [M]  s01/src/user.js
```



真正重要的是：

```text
Preview: 1 file(s) changed  |  +7  -1
```

以及：

```text
Will review (1):
  [M]  s01/src/user.js
```

这说明 Open Code Review 识别到了：

```text
1 个文件发生变化；
新增 7 行；
删除 1 行；
这个文件会被纳入审查；
文件状态是 Modified。
```

---

## 十一、把 Git 输出和 OCR Preview 对应起来

现在可以把 Git 原生命令和 Open Code Review Preview 输出对应起来。

### 1. 文件数量对应

`git diff --stat` 输出：

```text
1 file changed
```

`ocr review --preview` 输出：

```text
Preview: 1 file(s) changed
```

二者对应：

```text
Git 检测到 1 个文件变化
        ↓
OCR Preview 显示 1 file(s) changed
```

---

### 2. 文件状态对应

`git diff --name-status` 输出：

```text
M       s01：用最小 Demo 跑通 AI 代码审查/src/user.js
```

`ocr review --preview` 输出：

```text
[M]  s01/src/user.js
```

二者对应：

```text
Git 中的 M
        ↓
OCR Preview 中的 [M]
```

含义都是：

```text
Modified，文件被修改。
```

---

### 3. 新增删除行数对应

`git diff --numstat` 输出：

```text
7       1       s01：用最小 Demo 跑通 AI 代码审查/src/user.js
```

`ocr review --preview` 输出：

```text
+7  -1
```

二者对应：

```text
7 insertions
        ↓
+7

1 deletion
        ↓
-1
```

所以 `ocr review --preview` 展示的 `+7 -1`，本质上来自本次 Git diff 的新增和删除行数统计。

---

## 十二、`ocr review --preview` 的作用

通过前面的对比可以发现，`ocr review --preview` 的作用是：

```text
在不真正调用 LLM 的情况下，
提前告诉我这次会审查哪些文件。
```

它可以帮助我在正式执行审查前确认几个问题：

```text
1. 当前是否有 Git 变更；
2. 哪些文件会被审查；
3. 哪些文件被排除；
4. 每个文件的变更规模是多少；
5. 文件状态是新增、修改还是删除。
```

这一步非常重要。

因为正式执行：

```bash
ocr review
```

会调用 LLM，可能产生 token 消耗和等待时间。

所以在正式 review 前，先执行：

```bash
ocr review --preview
```

可以避免一些问题。

例如：

```text
不小心审查了无关文件；
忘记忽略生成文件；
把 JSON 结果文件也纳入了 review；
当前其实没有代码变更；
审查范围比预期大很多。
```

因此，使用习惯是：

```text
先执行 ocr review --preview
确认范围没问题
再执行 ocr review
```

---

## 十三、为什么 `git diff` 和 Preview 有时对不上

本文示例中的修改是未暂存的 tracked 文件，所以 `git diff`、`git diff --numstat` 和 `ocr review --preview` 的结果可以很好地对应起来。

但在真实项目里，有时你会发现：

```text
git diff 看不到某些文件，
ocr review --preview 却能看到。
```

原因是 OpenCodeReview 的 workspace 模式不只是简单执行裸 `git diff`。

从源码逻辑看，workspace 模式会处理两类变更：

```text
1. tracked 文件变更：通过 git diff HEAD 获取相对 HEAD 的变更；
2. untracked 文件变更：通过 git ls-files --others --exclude-standard 找到未跟踪文件，并手动构造 diff。
```

这意味着：

```text
如果文件已经 git add，普通 git diff 可能看不到，因为它默认比较工作区和暂存区；
如果文件是 untracked，普通 git diff 也看不到，因为它还没有进入 Git 跟踪；
但 ocr review --preview 仍然可能把它们纳入审查范围。
```

所以在对照 OCR Preview 时，更接近的理解方式是：

```text
tracked changes: git diff HEAD
untracked files: git ls-files --others --exclude-standard
```

而不是只看：

```text
git diff
```

---

## 十四、哪些变更文件不会进入 `Will review`

`ocr review --preview` 不只是列出 Git diff 中出现的文件，还会判断这些文件是否真的会进入审查。

Preview 输出里有两个重要区域：

```text
Will review
Excluded from review
```

不是所有发生变更的文件都会进入 `Will review`。OpenCodeReview 在拿到 diff 后，还会经过文件过滤逻辑。

常见被排除的原因包括：

```text
1. 二进制文件；
2. 被 .gitignore 或内置目录规则排除；
3. 被 .opencodereview/rule.json 的 exclude 命中；
4. 文件扩展名不在支持范围内；
5. 位于默认排除路径，例如 node_modules、vendor 等；
6. 纯删除文件。
```

所以 `ocr review --preview` 的价值不只是告诉我“哪些文件变了”，还会告诉我：

```text
哪些文件最终会被审查；
哪些文件虽然变了，但会被排除。
```

这也为下一篇分析 `rule.json` 的 `exclude`、`path` 和规则匹配做了铺垫。

---

## 十五、从源码角度简单理解 Preview 流程

上一篇已经找到 `ocr review` 的入口在：

```text
cmd/opencodereview/main.go
```

并且会进入：

```go
runReview(args[1:])
```

在 `runReview` 中，程序会先解析参数。

当用户执行：

```bash
ocr review --preview
```

时，参数解析后可以简单理解为：

```text
opts.preview = true
```

然后 `runReview` 会根据这个参数进入 preview 分支。

整体流程可以先简单理解为：

```text
用户执行 ocr review --preview
        ↓
main.go
        ↓
dispatch()
        ↓
runReview(args[1:])
        ↓
parseReviewFlags(args)
        ↓
opts.preview = true
        ↓
runPreview
        ↓
ag.Preview
        ↓
loadDiffs
        ↓
diff.Provider.GetDiff
        ↓
diff.ParseDiffText
        ↓
生成 model.Diff
        ↓
whyExcluded / diffStatus
        ↓
outputPreviewText
        ↓
终端显示 Preview 结果
```

这里最重要的是 `model.Diff`。

它可以理解为 OpenCodeReview 内部对“单个文件变更”的结构化表示，里面会保存：

```text
OldPath / NewPath
Diff 原始文本
NewFileContent 新文件内容
IsBinary / IsDeleted / IsNew / IsRenamed
Insertions / Deletions
```

所以 `ocr review --preview` 展示的文件路径、状态、`+7 -1`，不是凭空来的，而是来自 `model.Diff` 中的结构化字段。

目前只需要知道：

```text
Preview 模式不会真正调用 LLM；
它会加载 Git diff，解析成 model.Diff，应用文件过滤规则，然后渲染预览结果。
```

---

## 十六、理解几种常见文件状态

在 Git diff 或 OCR Preview 中，常见文件状态包括：

| 状态          | 含义             |
| ----------- | -------------- |
| `M` / `[M]` | Modified，文件被修改 |
| `A` / `[A]` | Added，新增文件     |
| `D` / `[D]` | Deleted，删除文件   |
| `R` / `[R]` | Renamed，文件重命名  |
| `B` / `[B]` | Binary，二进制文件   |

本次输出中出现的是：

```text
[M]
```

所以表示：

```text
s01/src/user.js 是一个被修改的文件。
```

如果后续新增一个文件，例如：

```text
src/order.js
```

那么可能看到：

```text
[A] src/order.js
```

如果删除一个文件，可能看到：

```text
[D] src/old.js
```

这些状态都来自 Git 对文件变更的判断。

---

## 十七、理解三种 review 场景

虽然本文主要使用的是当前工作区变更，但 `ocr review` 还可以用于其他场景。

### 1. 默认工作区模式

直接执行：

```bash
ocr review
```

或者：

```bash
ocr review --preview
```

通常审查的是当前工作区中的变更。

也就是还没有提交的修改。

这是我目前练习时最常用的模式。

---

### 2. Commit 模式

也可以审查某一个 commit：

```bash
ocr review --commit abc123
```

它表示：

```text
审查 abc123 这个提交相对于它父提交的代码差异。
```

这种方式适合在某次提交后单独审查。

---

### 3. From-To 模式

还可以审查两个 Git 引用之间的差异：

```bash
ocr review --from main --to feature-branch
```

它表示：

```text
审查 main 到 feature-branch 之间的代码变化。
```

这类模式更接近 Pull Request 或分支对比场景。

---

## 十八、为什么 Git Diff 是 Agent Review 的第一步

现在可以重新理解 `ocr review` 的流程。

一开始以为它大概是：

```text
把代码发给 LLM
        ↓
LLM 给出评论
```

但现在通过 Git diff 观察，发现它至少要先完成：

```text
识别变更文件
统计新增删除行数
判断文件状态
过滤不需要审查的文件
确定本次审查范围
```

这些都属于 LLM 之前的确定性工程处理。

也就是说，`ocr review` 的第一步不是调用大模型，而是：

```text
先通过 Git diff 确定输入。
```

然后后续才会进入：

```text
规则匹配
文件读取
上下文检索
Agent 工具调用
LLM 审查
评论输出
```

所以 Git diff 是整个代码审查流程的起点。

---

## 十九、本篇使用的 PowerShell 命令记录

为了方便复盘，本文主要使用了下面这些命令。

### 1. 进入练习项目

```powershell
cd D:\agent\open-code-review-main\ocr-practice-demo
```

### 2. 查看 Git 状态

```powershell
git status --short
```

### 3. 查看变更文件状态

```powershell
git diff --name-status
```

### 4. 查看新增和删除行数

```powershell
git diff --numstat
```

### 5. 查看 diff 统计

```powershell
git diff --stat
```

### 6. 查看具体 diff 内容

```powershell
git diff
```

### 7. 查看 OCR Preview

```powershell
ocr review --preview
```

---

## 二十、本篇总结

通过这一篇，对 `ocr review` 的输入有了更清晰的理解。

本文最核心的结论是：

```text
ocr review 的核心输入是 Git diff。
```

Git diff 会告诉 Open Code Review：

```text
哪些文件发生了变化；
文件是新增、修改还是删除；
新增了多少行；
删除了多少行；
具体变更内容是什么。
```

本次示例中，Git 检测到：

```text
1 个文件被修改；
新增 7 行；
删除 1 行。
```

所以 `ocr review --preview` 输出：

```text
Preview: 1 file(s) changed  |  +7  -1

Will review (1):
  [M]  s01：用最小 Demo 跑通 AI 代码审查/src/user.js
```

其中：

```text
[M] 表示文件被修改；
+7 表示新增 7 行；
-1 表示删除 1 行。
```

而 `-1` 的来源是：

```diff
-  deleteUser
+  deleteUser,
```

也就是说，它不是删除了业务逻辑，而是 Git 认为原来的 `deleteUser` 这一行被替换成了新的 `deleteUser,`。

通过这一篇，已经能把下面几类输出对应起来：

```text
git status --short
git diff --name-status
git diff --numstat
git diff --stat
ocr review --preview
```


---

## 二十一、下一篇：自定义规则 rule.json 解析

第一篇中，已经配置过：

```text
.opencodereview/rule.json
```

并且通过：

```bash
ocr rules check src/user.js
```

验证了规则可以命中 JavaScript 文件。

第三篇解决的是：

```text
ocr review 的输入 Git diff 是怎么来的？
```

下一篇准备继续分析：

```text
从 0 学习 Alibaba Open Code Review：自定义规则 rule.json 解析
```

下一篇主要解决这些问题：

```text
1. 为什么 .opencodereview/rule.json 能影响审查结果？
2. path: **/*.js 是如何匹配 src/user.js 的？
3. rule 字段如何影响 Agent 的审查重点？
4. merge_system_rule: true 是什么意思？
5. exclude 如何影响审查范围？
6. ocr rules check 的输出应该怎么看？
```

到这里，学习路线就从：

```text
ocr review 能做什么
```

进入到：

```text
ocr review 看哪些代码
```

再继续进入：

```text
ocr review 按什么规则审查代码
```
