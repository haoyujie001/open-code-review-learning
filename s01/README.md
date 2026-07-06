#从 0 学习 Alibaba Open Code Review（一）：用最小 Demo 跑通 AI 代码审查

## 前言

最近学习 Alibaba 开源的 `open-code-review` 项目。这个项目的核心目标是利用大模型能力，对代码变更进行自动化 Code Review。

刚开始学习首先从使用者角度跑通完整流程，本文包括：

* 安装 Open Code Review；
* 配置 LLM Provider；
* 执行 `ocr llm test` 测试模型连接；
* 创建一个最小 JavaScript Demo 项目；
* 制造一次待审查的 Git diff；
* 使用 `ocr review --preview` 预览审查范围；
* 使用 `ocr review` 审查 Git diff；
* 使用 `ocr review --format json` 保存结构化审查结果；
* 配置 `.opencodereview/rule.json` 自定义审查规则；
* 使用 `ocr rules check` 验证规则是否命中；
* 对比自定义规则前后的审查结果；
* 分析本次 Review 中调用的 `file_read`、`file_find`、`file_read_diff`、`code_search`、`code_comment` 等工具。


本文是第一篇学习记录，通过一个自己创建的最小 JavaScript Demo，跑通 Open Code Review 的基础使用流程。

---

## 一、安装 Open Code Review

首先需要安装 Open Code Review CLI。

这里使用 npm 安装：

```bash
npm install -g @alibaba-group/open-code-review
```

安装完成后，可以查看版本：

```bash
ocr version
```

如果能够输出版本信息，说明 CLI 已经安装成功。

---

## 二、配置 LLM Provider

Open Code Review 需要连接大模型才能执行代码审查，所以安装完成后需要先配置 LLM。

可以使用下面的命令进入配置流程：

```bash
ocr config provider
```

然后配置使用的模型：

```bash
ocr config model
```

也可以查看当前支持或已经配置的 LLM Provider：

```bash
ocr llm providers
```

配置完成后，执行测试命令：

```bash
ocr llm test
```

ocr llm test 成功执行说明本地 LLM 配置已经打通，Open Code Review 已经可以正常调用模型。




## 三、创建练习项目

首先创建一个新的目录：

```bash
mkdir ocr-practice-demo
cd ocr-practice-demo
git init
```

然后创建源码目录和文件：

```bash
mkdir src
touch src/user.js
```

接着在 `src/user.js` 中写入下面这段代码：

```js
// src/user.js

function getUserName(user) {
  return user.name;
}

function login(username, password) {
  const adminPassword = "123456";

  if (password === adminPassword) {
    return {
      success: true,
      token: "fake-token"
    };
  }

  return {
    success: false
  };
}

function buildUserQuery(userId) {
  return "SELECT * FROM users WHERE id = " + userId;
}

async function fetchUser(api, id) {
  const response = await api.get("/users/" + id);
  return response.data.name;
}

module.exports = {
  getUserName,
  login,
  buildUserQuery,
  fetchUser
};
```

这段代码里已经故意放了一些问题，比如：

* `getUserName(user)` 没有判断 `user` 是否为空；
* `login` 中存在硬编码密码；
* `buildUserQuery` 使用字符串拼接 SQL，存在 SQL 注入风险；
* `fetchUser` 没有异常处理；
* `fetchUser` 默认认为 `response.data.name` 一定存在。

然后提交初始版本：

```bash
git add .
git commit -m "init practice demo"
```

这一步的作用是创建一个干净的 Git 基线。执行提交后，终端会输出类似如下信息：
```bash
[master (root-commit) f6ad09f] init practice demo
 1 file changed, 36 insertions(+)
 create mode 100644 src/user.js
 ```
后面我们再制造新的代码变更，让 ocr review 可以审查 Git diff。

---


## 四、制造一次待审查变更

前面已经完成了初始代码提交，此时 Git 仓库中有了一个干净的基线版本。

接下来故意制造一次新的代码变更，用来测试 `ocr review` 对 Git diff 的审查能力。

这次在 `src/user.js` 中新增一个删除用户的函数：

```js
function deleteUser(db, userId) {
  db.query("DELETE FROM users WHERE id = " + userId);
  return true;
}
```

同时把这个函数加入到 `module.exports` 中，让它可以被外部模块使用：

```js
module.exports = {
  getUserName,
  login,
  buildUserQuery,
  fetchUser,
  deleteUser
};
```

修改后的 `src/user.js` 完整代码大致如下：

```js
// src/user.js

function getUserName(user) {
  return user.name;
}

function login(username, password) {
  const adminPassword = "123456";

  if (password === adminPassword) {
    return {
      success: true,
      token: "fake-token"
    };
  }

  return {
    success: false
  };
}

function buildUserQuery(userId) {
  return "SELECT * FROM users WHERE id = " + userId;
}

async function fetchUser(api, id) {
  const response = await api.get("/users/" + id);
  return response.data.name;
}

function deleteUser(db, userId) {
  db.query("DELETE FROM users WHERE id = " + userId);
  return true;
}

module.exports = {
  getUserName,
  login,
  buildUserQuery,
  fetchUser,
  deleteUser
};
```

这里注意：**修改完成后先不要提交 commit**。

因为我们可以让 `ocr review` 审查当前工作区中的未提交变更。如果现在执行 `git commit`，当前工作区就会变干净。

可以先执行下面的命令查看当前代码变更：

```bash
git diff
```

终端会输出类似下面的 diff 内容：

```diff
diff --git a/src/user.js b/src/user.js
index 613f54b..1445e1f 100644
--- a/src/user.js
+++ b/src/user.js
@@ -28,9 +28,15 @@ async function fetchUser(api, id) {
   return response.data.name;
 }

+function deleteUser(db, userId) {
+  db.query("DELETE FROM users WHERE id = " + userId);
+  return true;
+}
+
 module.exports = {
   getUserName,
   login,
   buildUserQuery,
-  fetchUser
+  fetchUser,
+  deleteUser
 };
```

这段 diff 第一部分是新增了 `deleteUser` 函数：

```diff
+function deleteUser(db, userId) {
+  db.query("DELETE FROM users WHERE id = " + userId);
+  return true;
+}
```

在 git diff 中，前面带 `+` 的行表示新增内容。

第二部分是修改了 `module.exports`：

```diff
-  fetchUser
+  fetchUser,
+  deleteUser
```



在原来的代码中，`fetchUser` 是最后一个导出项：



所以它后面可以不写逗号。

但是现在新增了 `deleteUser`，`fetchUser` 就不再是最后一个属性了。js 对象中，多个属性之间用逗号分隔，所以把原来的：

```js
fetchUser
```

改成：

```js
fetchUser,
deleteUser
```

因此，diff 中出现：

```diff
-  fetchUser
+  fetchUser,
+  deleteUser
```


这次新增的 `deleteUser` 函数也故意保留了几个明显问题，以观察 Open Code Review 是否能识别出来：

1. 使用字符串拼接 SQL，存在 SQL 注入风险；
2. 删除用户前没有做权限校验；
3. `db.query` 没有使用 `await`，可能没有等待数据库操作完成；
4. 没有错误处理；
5. 无论数据库删除是否成功，都直接返回 `true`。



## 五、使用 `ocr review --preview` 预览审查范围

在正式执行 AI 代码审查之前，先使用 `ocr review --preview` 预览本次将要被审查的文件范围。

执行命令：

```bash
ocr review --preview
```

终端输出如下：

```text
Preview: 1 file(s) changed  |  +7  -1

Will review (1):
  [M]  src/user.js          +7    -1
```

这段输出说明 Open Code Review 已经识别到了当前工作区中的代码变更。

其中：

```text
Preview: 1 file(s) changed
```

表示当前 Git 工作区中有 1 个文件发生了变化。

```text
+7  -1
```

表示本次 diff 中一共有 7 行新增、1 行删除。



```text
Will review (1):
  [M]  src/user.js          +7    -1
```

其中 `Will review (1)` 表示 Open Code Review 准备审查 1 个文件。

`[M]` 表示 `Modified`，也就是该文件是被修改过的文件。

`src/user.js` 是本次将被审查的文件路径。

后面的 `+7 -1` 表示这个文件中新增了 7 行，删除了 1 行。

这里的 “删除 1 行” 是在上一章中，把原来的：

```js
fetchUser
```

修改成了：

```js
fetchUser,
```

也就是说，原来的这一行：

```diff
-  fetchUser
```

被替换成了新的这一行：

```diff
+  fetchUser,
```

Git diff 会把这种行级修改显示成：

```text
删除旧行 + 新增新行
```

所以这一次 preview 中才会出现 `+7 -1`。

完整来看，本次变更大致包括：

```diff
+function deleteUser(db, userId) {
+  db.query("DELETE FROM users WHERE id = " + userId);
+  return true;
+}
+
-  fetchUser
+  fetchUser,
+  deleteUser
```

本次变更主要有两部分：

1. 新增了 `deleteUser` 函数；
2. 修改了 `module.exports`，把 `deleteUser` 导出。

通过这次 `preview`，可以在真正调用大模型之前先确认审查范围。

在真实项目中。如果不先预览，可能会把一些不相关文件、构建产物、依赖目录或者临时文件也送去审查，导致 token 浪费，甚至影响审查结果质量。

因此，对 `ocr review --preview` 的理解是：


**ocr review --preview 不会真正调用 LLM，
它主要用于提前查看本次将被审查的文件列表和 diff 规模。**


在这个练习项目中，预览结果符合预期：Open Code Review 只识别到了 `src/user.js` 这一个发生变更的文件，说明当前审查范围是正确的。

## 六、执行第一次 `ocr review`

完成 `ocr review --preview` 预览之后，确认本次只有 `src/user.js` 一个文件会被审查，接下来就可以正式执行 AI 代码审查了。

执行命令：

```bash
ocr review
```

终端输出如下：

```text
[ocr] 1 file(s) changed, reviewing 1 in D:\agent\open-code-review-main\ocr-practice-demo
[ocr] Skipping plan phase for src/user.js (8 lines < threshold 50)
[ocr]   ▶ file_read file_path=src/user.js
[ocr]   ✔ file_read (1ms)
[ocr]   ▶ file_read end_line=60 file_path=src/user.js start_line=1
[ocr]   ✔ file_read (1ms)
[ocr]   ▶ file_find query_name=user.js
[ocr]   ✔ file_find (39ms)
[ocr]   ▶ code_search file_patterns=[src/user.js] search_text=db.query
[ocr]   ✔ code_search (37ms)
[ocr]   ▶ code_comment "src/user.js"
[ocr]   ✔ code_comment (0s)
[ocr] Summary: 1 file(s) reviewed, 2 comment(s), ~23989 token(s) used (input: ~22820, output: ~1169), 22s elapsed
```

从这段日志可以看出，Open Code Review 识别到当前项目中有 1 个文件发生变化，并且实际审查了 1 个文件，也就是：

```text
src/user.js
```


---

### 6.1 为什么跳过了 plan phase？

日志中有一行：

```text
[ocr] Skipping plan phase for src/user.js (8 lines < threshold 50)
```

这表示 Open Code Review 跳过了针对 `src/user.js` 的计划阶段。

原因是本次变更只有 8 行，小于阈值 50 行。对于这种比较小的代码变更，不需要先进行复杂的分析规划，可以直接进入文件读取和代码审查流程。




**当 diff 较小时，Open Code Review 会跳过 plan phase，直接进行审查；
当 diff 较大时，可能会先进行 plan phase，用来规划应该如何审查代码。**


这样做可以减少不必要的分析步骤，提高小规模代码变更的审查效率。

---

### 6.2 审查过程中调用了哪些工具？

从日志中可以看到，Open Code Review 在审查过程中调用了多个工具。

首先是读取文件：

```text
[ocr]   ▶ file_read file_path=src/user.js
[ocr]   ✔ file_read (1ms)
```

这里表示它读取了 `src/user.js` 文件。

接着又读取了文件的指定行范围：

```text
[ocr]   ▶ file_read end_line=60 file_path=src/user.js start_line=1
[ocr]   ✔ file_read (1ms)
```

这说明它不只是看 Git diff，还会读取文件上下文。这样可以帮助模型更准确地理解代码，而不是只看到新增的几行代码。

然后是查找文件：

```text
[ocr]   ▶ file_find query_name=user.js
[ocr]   ✔ file_find (39ms)
```

这里表示它根据文件名 `user.js` 进行文件查找。

接着是代码搜索：

```text
[ocr]   ▶ code_search file_patterns=[src/user.js] search_text=db.query
[ocr]   ✔ code_search (37ms)
```

这一步比较关键。因为新增代码里出现了：

```js
db.query("DELETE FROM users WHERE id = " + userId);
```

所以 Open Code Review 搜索了 `db.query` 相关代码，用来判断当前项目里是否还有类似用法，或者是否需要更多上下文。

最后是生成评论：

```text
[ocr]   ▶ code_comment "src/user.js"
[ocr]   ✔ code_comment (0s)
```

这说明它已经针对 `src/user.js` 生成了代码审查意见。

通过这段日志，可以看到 Open Code Review 并不是简单地把 diff 直接丢给大模型，而是会结合文件读取、文件查找、代码搜索和评论生成等工具完成一次审查。

---

### 6.3 本次审查的总体结果

日志最后给出了本次审查的总结：

```text
[ocr] Summary: 1 file(s) reviewed, 2 comment(s), ~23989 token(s) used (input: ~22820, output: ~1169), 22s elapsed
```



* 审查了 1 个文件；
* 生成了 2 条评论；
* 大约使用了 23989 个 token；
* 其中输入约 22820 个 token，输出约 1169 个 token；
* 总耗时 22 秒。

---

### 6.4 第一个问题：SQL 注入风险

Open Code Review 给出的第一条评论如下：

```text
─── src/user.js:32-32 ───
SQL Injection Vulnerability: The userId parameter is directly concatenated into the SQL query
string. An attacker could pass a malicious userId value (e.g., 1; DROP TABLE users; --) to
manipulate the SQL query. This is a critical security flaw.
```

它指出的问题位于：

```text
src/user.js:32
```

对应代码是：

```js
db.query("DELETE FROM users WHERE id = " + userId);
```

这个问题是准确的。

因为直接把 `userId` 拼接进 SQL 字符串中，如果用户传入恶意内容，就可能改变原本的 SQL 语义，造成 SQL 注入风险。

比如攻击者可能传入类似：

```text
1; DROP TABLE users; --
```

这样最终拼接出来的 SQL 就可能变成危险语句。

Open Code Review 也给出了修改建议：

```js
db.query('DELETE FROM users WHERE id = ?', [userId]);
```

它的意思是使用参数化查询，而不是字符串拼接。

对比修改前后：

```diff
- db.query("DELETE FROM users WHERE id = " + userId);
+ db.query("DELETE FROM users WHERE id = ?", [userId]);
```

这条 Review 是有效的，而且属于比较重要的安全问题。

---

### 6.5 第二个问题：返回值没有反映真实执行结果

Open Code Review 给出的第二条评论如下：

```text
─── src/user.js:31-34 ───
Return value ignores operation result: The function always returns true regardless of whether
the DELETE query succeeds or fails. This can mask database errors and make debugging difficult.
```

它指出的问题范围是：

```text
src/user.js:31-34
```

对应代码是：

```js
function deleteUser(db, userId) {
  db.query("DELETE FROM users WHERE id = " + userId);
  return true;
}
```

这个问题同样是准确的。

当前 `deleteUser` 函数无论数据库删除是否成功，都会直接返回 `true`。这样会带来几个问题：

1. 如果数据库执行失败，调用方仍然以为删除成功；
2. 错误被隐藏，后续排查问题会更困难；
3. 函数返回值没有真实表达操作结果；
4. 如果 `db.query` 是异步操作，这里还可能没有等待数据库执行完成。

Open Code Review 建议：

```text
Return the result of the query or handle errors properly.
If using async/await, consider making this function async and returning the query result.
```

也就是说，可以把函数改成异步函数，并处理数据库返回结果。

例如可以修改成：

```js
async function deleteUser(db, userId) {
  const result = await db.query("DELETE FROM users WHERE id = ?", [userId]);
  return result.affectedRows > 0;
}
```

具体写法还要看实际使用的数据库驱动。这里的重点是：函数不应该在没有确认数据库操作结果的情况下直接返回 `true`。

---

### 6.6 本次 Review 的效果分析

这次故意在代码中放入了几个明显问题：

1. SQL 字符串拼接；
2. 删除用户没有权限校验；
3. `db.query` 没有 `await`；
4. 没有错误处理；
5. 无论操作是否成功都返回 `true`。

Open Code Review 实际发现了其中 2 个问题：

1. SQL 注入风险；
2. 返回值没有反映真实执行结果。

从结果来看，这两条评论都是有效的，没有明显误报。

不过它没有明确指出“删除用户前缺少权限校验”这个问题，因为当前 Demo 代码非常简单，没有用户身份、权限系统、路由层或者业务上下文，所以模型不一定能判断这里是否应该进行权限校验。

这也说明 AI Code Review 的效果和上下文有很大关系。如果项目中有更完整的权限逻辑、数据库封装和业务调用链，模型可能会给出更准确的审查意见。



通过第一次执行 `ocr review`可以看出：

它不是只简单地输出几句建议，而是会先分析变更文件，然后读取文件上下文，再结合代码搜索等工具生成审查评论。

本次 Review 的两个问题都比较准确，尤其是 SQL 注入风险，对于代码安全很有价值。

不过，AI Code Review 并不是万能的。它能够发现一部分明显问题，但不一定能发现所有业务层面的风险。因此在真实开发中，它更适合作为人工 Code Review 的辅助工具，而不是完全替代人工审查。




## 七、保存 JSON 格式审查结果

除了直接在终端中查看 `ocr review` 的审查结果之外，Open Code Review 还支持将结果以 JSON 格式输出。

这对于后续分析非常有用。比如我们可以把 JSON 结果保存下来，用来统计审查文件数量、评论数量、token 消耗、工具调用次数，以及每条 Review 评论对应的文件和行号。

执行命令如下：

```bash
ocr review --format json > ocr-review-result.json
```

执行完成后，项目目录下会生成一个文件：

```text
ocr-review-result.json
```

打开这个 JSON 文件后，可以看到整体结构如下：

```json
{
  "status": "success",
  "summary": {
    "files_reviewed": 2,
    "comments": 1,
    "total_tokens": 46264,
    "input_tokens": 43199,
    "output_tokens": 3065,
    "cache_read_tokens": 12032,
    "elapsed": "45s"
  },
  "tool_calls": {
    "total": 11,
    "by_tool": {
      "code_comment": 1,
      "code_search": 2,
      "file_find": 5,
      "file_read": 3
    }
  },
  "comments": [
    {
      "path": "src/user.js",
      "start_line": 31,
      "end_line": 34
    }
  ]
}
```

从这个 JSON 结果中可以看到，本次审查状态是：

```json
"status": "success"
```

这说明本次 `ocr review` 执行成功。

---

### 7.1 summary：本次审查的整体统计信息

JSON 中的 `summary` 字段记录了本次审查的整体结果：

```json
"summary": {
  "files_reviewed": 2,
  "comments": 1,
  "total_tokens": 46264,
  "input_tokens": 43199,
  "output_tokens": 3065,
  "cache_read_tokens": 12032,
  "elapsed": "45s"
}
```

其中：

```text
files_reviewed: 2
```

表示本次一共审查了 2 个文件。

```text
comments: 1
```

表示本次最终生成了 1 条代码审查评论。

```text
total_tokens: 46264
```

表示本次大约消耗了 46264 个 token。

```text
input_tokens: 43199
output_tokens: 3065
```

分别表示输入 token 和输出 token 的数量。

```text
cache_read_tokens: 12032
```

表示有一部分 token 来自缓存读取。

```text
elapsed: 45s
```

表示本次审查总耗时约 45 秒。

这里需要注意的是，JSON 输出中的统计结果可能和前面某一次终端直接执行 `ocr review` 时看到的结果不完全一致。原因是可能执行了多次 review，或者在保存 JSON 前后修改过规则文件、项目文件或审查范围。

所以在写博客或做实验记录时，应该以当前这次生成的 `ocr-review-result.json` 为准。

---

### 7.2 tool_calls：审查过程中调用了哪些工具

JSON 中还有一个 `tool_calls` 字段：

```json
"tool_calls": {
  "total": 11,
  "by_tool": {
    "code_comment": 1,
    "code_search": 2,
    "file_find": 5,
    "file_read": 3
  }
}
```

这部分记录了 Open Code Review 在审查过程中调用工具的情况。

其中：

```text
total: 11
```

表示本次一共调用了 11 次工具。

具体来看：

```text
file_read: 3
```

表示读取文件内容 3 次。

```text
file_find: 5
```

表示查找文件 5 次。

```text
code_search: 2
```

表示进行了 2 次代码搜索。

```text
code_comment: 1
```

表示最终生成了 1 次代码评论。

这个结果表明：它并不是简单地把 Git diff 直接发送给大模型，而是会结合文件读取、文件查找、代码搜索和评论生成等工具，完成一次相对完整的代码审查流程。

---

### 7.3 comments：具体的代码审查意见

最重要的是 `comments` 字段，它保存了具体的代码审查结果。

本次 JSON 中生成了 1 条评论，位置在：

```json
{
  "path": "src/user.js",
  "start_line": 31,
  "end_line": 34
}
```

这表示问题出现在：


src/user.js 第 31 行到第 34 行


对应代码是：

```js
function deleteUser(db, userId) {
  db.query("DELETE FROM users WHERE id = " + userId);
  return true;
}
```

Open Code Review 指出的问题是 SQL 注入风险。

原因是这里直接把 `userId` 拼接到了 SQL 语句中：

```js
db.query("DELETE FROM users WHERE id = " + userId);
```

如果 `userId` 来自用户输入，那么攻击者就可能传入恶意内容，从而改变原本 SQL 的含义，可能导致严重的数据库安全问题。

Open Code Review 给出的建议是使用参数化查询，也就是不要直接拼接 SQL 字符串，而是把参数单独传入：

```js
db.query("DELETE FROM users WHERE id = ?", [userId]);
```

这样数据库驱动会把 `userId` 当作参数处理，而不是直接当作 SQL 片段执行，从而降低 SQL 注入风险。

---

### 7.4 JSON 输出的价值

通过这次 JSON 结果，发现 `ocr review --format json` 不只是换了一种展示格式，它更适合后续做工程化集成。

例如，在 CI/CD 场景中，可以把 JSON 审查结果用于：

1. 统计本次 PR 产生了多少条 Review 评论；
2. 判断是否存在严重安全问题；
3. 把评论转换成 GitHub PR 评论；
4. 记录每次审查的 token 消耗；
5. 分析不同规则下的审查效果；
6. 作为后续自动化质量报告的数据来源。

相比终端文本输出，JSON 的优势是结构清晰，方便程序解析。

例如可以重点关注这些字段：

```text
status：本次审查是否成功
summary.files_reviewed：审查了几个文件
summary.comments：生成了几条评论
summary.total_tokens：消耗了多少 token
tool_calls.by_tool：调用了哪些工具
comments.path：问题所在文件
comments.start_line / end_line：问题所在行号
comments.content：具体审查意见
comments.existing_code：存在问题的原始代码
```




终端输出更适合人直接阅读，而 JSON 输出更适合程序处理。

如果只是本地学习，可以直接看终端结果；但如果要接入 GitHub Actions、GitLab CI 或团队质量平台，就更应该使用 JSON 输出。

Open Code Review 不只是一个“命令行 AI Review 工具”，它也具备进一步工程化集成的基础。

可以总结为：


**ocr review --format json 可以把 AI Code Review 的结果结构化输出，
方便后续做结果分析、CI 集成、PR 评论生成和代码质量统计。**


### 7.5 对比 ocr review 和 ocr scan
前面使用的是 ocr review，它主要审查 Git diff，也就是代码变更。

接下来体验 ocr scan。

先预览扫描范围：

```bash
ocr scan --preview
```

然后只扫描 src 目录：

```bash
ocr scan --path src
```

这一步和 ocr review 的区别非常明显。

ocr review 主要关注本次代码变更，而 ocr scan 会扫描指定目录下的完整代码。

对于练习项目来说，ocr scan --path src 不仅可能发现新增的 deleteUser 问题，也可能发现初始代码里的问题，比如：

getUserName 没有空值判断；
login 存在硬编码密码；
buildUserQuery 存在 SQL 注入风险；
fetchUser 缺少异常处理；
response.data.name 可能为空。


ocr review：适合审查 PR / commit diff，成本低，关注新增代码质量。
ocr scan：适合扫描整个目录或历史代码，覆盖面更广，但 token 成本更高。

---


## 八、配置自定义规则

### 8.1 创建规则文件
为了让 Open Code Review 更关注我想检查的问题，可以添加自定义规则。


先创建配置目录：

```bash
mkdir -p .opencodereview
New-Item -ItemType Directory -Force -Path .\.opencodereview
New-Item -ItemType File -Force -Path .\.opencodereview\rule.json
```

然后写入下面内容：

```json
{
  "rules": [
    {
      "path": "**/*.js",
      "rule": "重点检查 SQL 注入、硬编码密钥、空值异常、异步错误处理、权限校验缺失和删除类危险操作。",
      "merge_system_rule": true
    }
  ],
  "exclude": [
    "**/node_modules/**",
    "**/dist/**",
    "**/build/**"
  ]
}
```

这个规则的含义是：

* 对所有 JavaScript 文件生效；
* 重点检查 SQL 注入、硬编码密钥、空值异常、异步错误处理、权限校验缺失和删除类危险操作；
* `merge_system_rule: true` 表示在系统默认规则的基础上合并我的自定义规则；
* 排除 `node_modules`、`dist`、`build` 等目录，避免审查依赖文件或构建产物。

---

### 8.2 使用 `ocr rules check` 检查规则是否命中

配置完成后，执行下面的命令，检查 `src/user.js` 是否命中了自定义规则：

```powershell
ocr rules check src/user.js
```

终端输出中有几行非常关键：

```text
File: src/user.js
Source: Project (.opencodereview/rule.json)
Pattern: **/*.js
```

这说明：

```text
src/user.js 命中了项目级规则文件 .opencodereview/rule.json
匹配规则是 **/*.js
```

继续往下看，输出中同时包含了系统规则和用户自定义规则。

系统规则部分包括：

```text
## System-Specific Rules (Mandatory)
```

用户规则部分包括：

```text
## User-Specific Rules (Mandatory)

重点检查 SQL 注入、硬编码密钥、空值异常、异步错误处理、权限校验缺失和删除类危险操作。
```

这说明我配置的规则已经生效，并且由于设置了：

```json
"merge_system_rule": true
```

所以 Open Code Review 会同时使用系统默认规则和自定义的项目规则。

---

### 8.3 重新执行 `ocr review`

确认规则命中后，重新执行代码审查：

```powershell
ocr review
```

终端输出如下：

```text
[ocr] 3 file(s) changed, reviewing 3 in D:\agent\open-code-review-main\ocr-practice-demo
[ocr] Skipping plan phase for ocr-review-result.json (31 lines < threshold 50)
[ocr] Skipping plan phase for src/user.js (8 lines < threshold 50)
[ocr] Skipping plan phase for .opencodereview/rule.json (14 lines < threshold 50)
```

这里需要注意，这次 Open Code Review 识别到了 3 个变更文件：

```text
ocr-review-result.json
src/user.js
.opencodereview/rule.json
```

原因是我前面生成了 `ocr-review-result.json`，又新增了 `.opencodereview/rule.json`，它们目前也属于 Git 工作区中的变更文件。

所以 Open Code Review 会把它们也算进本次变更范围。

不过这次真正产生代码审查评论的文件仍然是：

```text
src/user.js
```

日志最后显示：

```text
[ocr] Summary: 3 file(s) reviewed, 3 comment(s), ~50323 token(s) used (input: ~44398, output: ~5925), cache(read: ~13568, write: ~0), 48s elapsed
```

这表示：

* 本次审查了 3 个变更文件；
* 生成了 3 条评论；
* 大约使用了 50323 个 token；
* 总耗时约 48 秒。

---

### 8.4 自定义规则生效后的审查结果

这次审查一共生成了 3 条评论，全部都集中在 `src/user.js` 的 `deleteUser` 函数上。

原始问题代码如下：

```js
function deleteUser(db, userId) {
  db.query("DELETE FROM users WHERE id = " + userId);
  return true;
}
```

---

### 8.5 第一条评论：SQL 注入风险

第一条评论指出：

```text
Critical: SQL Injection Vulnerability
```

Open Code Review 认为 `userId` 被直接拼接进 SQL 字符串中，存在 SQL 注入风险。

对应代码是：

```js
db.query("DELETE FROM users WHERE id = " + userId);
```

它建议使用参数化查询：

```js
db.query("DELETE FROM users WHERE id = ?", [userId]);
```

对应 diff 如下：

```diff
- db.query("DELETE FROM users WHERE id = " + userId);
+ db.query("DELETE FROM users WHERE id = ?", [userId]);
```

这条评论和自定义规则中的：


**重点检查 SQL 注入**


是对应的。

说明自定义规则确实影响了审查重点。

---

### 8.6 第二条评论：缺少异步错误处理

第二条评论指出：

```text
Critical: Missing Error Handling
```

Open Code Review 认为当前函数直接调用：

```js
db.query(...)
```

但是没有：

* `await`；
* `try-catch`；
* Promise `.catch()`；
* 真实返回数据库执行结果。

当前函数无论数据库操作是否成功，都会直接返回：

```js
return true;
```

这会误导调用方，让调用方以为删除操作一定成功。

Open Code Review 给出的修改建议大致如下：

```js
async function deleteUser(db, userId) {
  try {
    const result = await db.query("DELETE FROM users WHERE id = ?", [userId]);
    return result.affectedRows > 0;
  } catch (error) {
    console.error('Failed to delete user:', error);
    throw new Error('Failed to delete user');
  }
}
```

这条评论对应自定义规则中的：


**异步错误处理**


说明添加规则后，Open Code Review 不只是发现 SQL 注入，还进一步关注到了异步数据库操作的错误处理问题。

---

### 8.7 第三条评论：缺少权限校验

第三条评论指出：

```text
Warning: Missing Authorization Check
```

Open Code Review 认为 `deleteUser` 是一个删除用户的危险操作，但是函数内部没有任何权限校验。

原始代码是：

```js
function deleteUser(db, userId) {
  db.query("DELETE FROM users WHERE id = " + userId);
  return true;
}
```

它建议增加调用者身份或权限参数，例如：

```js
function deleteUser(db, userId, authUser) {
  if (!authUser || !authUser.canDelete) {
    throw new Error('Unauthorized: you do not have permission to delete users');
  }
}
```

这条评论非常符合我在自定义规则中写的：

```text
权限校验缺失和删除类危险操作
```

这也是本次实验中最明显的变化。

在没有添加自定义规则之前，Open Code Review 主要关注 SQL 注入和返回值问题；添加规则之后，它开始明确指出删除操作缺少权限校验。

---

### 8.8 为什么这次审查了 3 个文件？

这次日志中显示：

```text
[ocr] 3 file(s) changed, reviewing 3
```

而前面 `ocr review --preview` 时只看到 1 个文件。

这是因为在实验过程中，我新增或修改了这些文件：

```text
src/user.js
ocr-review-result.json
.opencodereview/rule.json
```

这些文件都还没有提交到 Git，所以都属于当前工作区的变更。

如果只希望 Open Code Review 审查业务代码，可以考虑：

1. 把 `.opencodereview/rule.json` 提交到 Git；
2. 把 `ocr-review-result.json` 加入 `.gitignore`；
3. 保持工作区里只剩下业务代码变更。




---

### 8.9 加规则前后效果对比

根据目前的实验结果，可以做一个简单对比。

加规则前，Open Code Review 主要发现了：

```text
1. SQL 注入风险
2. 返回值没有反映真实执行结果
```

加规则后，Open Code Review 发现了：

```text
1. SQL 注入风险
2. 缺少异步错误处理
3. 缺少权限校验
```

可以看出，自定义规则确实起到了作用。

尤其是第三条“缺少权限校验”，很明显是受到了用户自定义规则中：

```text
权限校验缺失和删除类危险操作
```

这部分内容的影响。

---

### 8.10 小结

`ocr rules check` 可以用来检查某个文件最终会命中哪些规则，这一步非常有用。

如果不确定规则是否生效，不应该直接跑 `ocr review`，而是应该先执行：

```powershell
ocr rules check src/user.js
```

确认规则命中后，再执行：

```powershell
ocr review
```

这样可以避免误以为规则没有生效。

这次实验也说明，自定义规则可以明显影响 AI Code Review 的关注点。默认规则更偏通用代码质量检查，而项目级规则可以让审查更贴近具体业务。




**.opencodereview/rule.json 可以用来配置项目级审查规则；
ocr rules check 可以验证规则是否命中；
merge_system_rule: true 可以让系统规则和用户规则同时生效；
自定义规则能够让 AI Review 更关注项目真正关心的问题。**


## 九、查看审查历史

如果已经执行过 `ocr review` 或 `ocr scan`，还可以使用 viewer 查看审查历史。

执行：

```bash
ocr viewer
```

然后根据终端提示打开本地页面。

这里可以观察：

```text
viewer 是否能看到本次 review：
结果是否按文件展示：
是否能看到问题详情：
是否适合团队 Review 场景：
```

Open Code Review 不只是一个命令行工具，它也提供了结果查看和历史记录能力。

---
## 十、本次 Review 中调用了哪些工具

在前面的实验中，多次执行了 `ocr review`，并在终端日志中观察到了 Open Code Review 的工具调用过程。

它并不是简单地把 Git diff 直接发送给大模型，然后等待模型返回结果，而是通过一组工具读取文件、查找文件、搜索代码、读取 diff，并最终生成代码审查评论。

从整体设计来看，这种方式更接近一个 **Agent 项目**：模型并不是一次性完成所有分析，而是通过“工具调用”的方式逐步获取信息、补充上下文、做出判断，最终生成结果。这种“工具驱动 + LLM 推理”的模式，是当前 AI 工程化的重要方向。

在本次 Demo 中，观察到主要调用了下面这些工具：

```text
file_read
file_find
file_read_diff
code_search
code_comment
```

---

### 10.1 file_read：读取文件内容

在日志中可以看到类似输出：

```text
[ocr]   ▶ file_read file_path=src/user.js
[ocr]   ✔ file_read (1ms)
```

以及：

```text
[ocr]   ▶ file_read end_line=60 file_path=src/user.js start_line=1
[ocr]   ✔ file_read (1ms)
```

`file_read` 的作用是读取文件内容。

在本次 Demo 中，它读取的是：

```text
src/user.js
```

这一步很重要，因为 AI Code Review 不能只看新增的几行代码。很多问题必须结合上下文才能判断。

例如，这次新增的代码是：

```js
function deleteUser(db, userId) {
  db.query("DELETE FROM users WHERE id = " + userId);
  return true;
}
```

如果只看这一段，模型可以发现 SQL 注入风险；但如果想进一步理解它在文件中的位置、是否被导出、上下文中是否还有类似数据库操作，就需要读取完整文件。

所以对 `file_read` 的理解是：


**file_read 用来读取目标文件内容，为模型提供代码上下文。**


从 Agent 的角度来看，这一步相当于“主动获取上下文信息”，而不是被动依赖输入。

---

### 10.2   file_find：查找相关文件

日志中还出现了：

```text
[ocr]   ▶ file_find query_name=user.js
[ocr]   ✔ file_find (39ms)
```

`file_find` 的作用是根据文件名查找相关文件。

在这个 Demo 中，项目很小，只有一个主要源码文件：

```text
src/user.js
```

所以 `file_find` 看起来作用不明显。

但是在真实项目中，文件查找会更有价值。例如，一个项目中可能存在：

```text
src/user.js
src/user.test.js
src/userService.js
src/userController.js
```

当某个变更发生在 `user.js` 中时，Agent 可以通过文件查找找到相关文件，进一步理解代码结构和业务上下文。

所以对 `file_find` 的理解是：

**file_find 用来根据文件名查找相关文件，帮助 Agent 获取更多项目结构信息。**


在 Agent 体系中，这一步类似于“扩展搜索范围”，避免只局限于当前文件。

---

### 10.3 file_read_diff：读取 Git diff 内容

在添加自定义规则后重新执行 `ocr review` 时，日志中出现了：

```text
[ocr]   ▶ file_read_diff path_array=[src/user.js]
[ocr]   ✔ file_read_diff (0s)
```

`file_read_diff` 的作用是读取指定文件的 Git diff。

也就是说，它会获取这次代码变更中真正发生变化的内容。

在本次 Demo 中，核心 diff 是：

```diff
+function deleteUser(db, userId) {
+  db.query("DELETE FROM users WHERE id = " + userId);
+  return true;
+}
+
-  fetchUser
+  fetchUser,
+  deleteUser
```

这一步可以帮助 Agent 聚焦本次变更，而不是无差别地审查整个文件。

`file_read` 和 `file_read_diff` 的区别可以简单理解为：

```text
file_read：读取文件完整内容或指定行范围
file_read_diff：读取本次 Git 变更内容
```

所以对 `file_read_diff` 的理解是：


**file_read_diff 用来读取 Git diff，让 Agent 聚焦当前变更。**


在 Agent 流程中，这一步相当于“确定任务范围”。

---

### 10.4 code_search：搜索相关代码

在日志中可以看到：

```text
[ocr]   ▶ code_search file_patterns=[src/user.js] search_text=db.query
[ocr]   ✔ code_search (37ms)
```

添加自定义规则后，还出现了更多搜索：

```text
[ocr]   ▶ code_search search_text=db.query file_patterns=[src/user.js]
[ocr]   ✔ code_search (38ms)

[ocr]   ▶ code_search file_patterns=[src/*.js] search_text=db.query
[ocr]   ✔ code_search (27ms)

[ocr]   ▶ code_search file_patterns=[*.js] search_text=db.query
[ocr]   ✔ code_search (41ms)

[ocr]   ▶ code_search file_patterns=[*.js] search_text=DELETE FROM users
[ocr]   ✔ code_search (27ms)
```

`code_search` 的作用是搜索项目中的相关代码。

在本次 Demo 中，Agent 发现新增代码中出现了：

```js
db.query("DELETE FROM users WHERE id = " + userId);
```

于是它搜索了：

```text
db.query
DELETE FROM users
```

这样做的目的可能是：

1. 查找项目中是否还有其他 `db.query` 用法；
2. 判断是否存在统一的数据库访问封装；
3. 检查其他地方是否使用参数化查询；
4. 获取和当前代码相关的上下文。

在真实项目中，这个工具会非常重要。因为很多代码问题不是单看当前文件就能判断的，比如：

* 当前函数有没有被调用；
* 项目中是否有统一的权限校验方法；
* 数据库访问是否有统一封装；
* 类似逻辑在其他模块中是怎么写的。

所以对 `code_search` 的理解是：


**code_search 用来搜索项目中的相关代码，帮助 Agent 获取更完整的上下文。**


在 Agent 模型中，这一步体现了“主动探索环境”的能力。

---

### 10.5 code_comment：生成代码审查评论

日志中最后出现了：

```text
[ocr]   ▶ code_comment "src/user.js"
[ocr]   ✔ code_comment (0s)
```

`code_comment` 的作用是生成最终的代码审查评论。

前面的 `file_read`、`file_find`、`file_read_diff`、`code_search` 都是在帮助 Agent 获取上下文，而 `code_comment` 则是把分析结果转化为具体的 Review 评论。

在本次 Demo 中，最终生成的评论包括：

```text
SQL Injection Vulnerability
Missing Error Handling
Missing Authorization Check
```

也就是：

1. SQL 注入风险；
2. 缺少异步错误处理；
3. 缺少权限校验。

这些评论最终被定位到了具体文件和行号，例如：

```text
src/user.js:32-32
src/user.js:31-34
src/user.js:31-31
```

所以对 `code_comment` 的理解是：


**code_comment 用来生成最终的代码审查评论，并将问题绑定到具体文件和行号。**


在 Agent 流程中，这一步相当于“输出决策结果”。

---

### 10.6 本次工具调用链路总结

结合这次 Demo 的日志，可以把 Open Code Review 的工具调用流程概括成下面这样：

```text
识别 Git diff
    ↓
file_read_diff 读取变更内容
    ↓
file_read 读取文件上下文
    ↓
file_find 查找相关文件
    ↓
code_search 搜索相关代码
    ↓
code_comment 生成审查评论
    ↓
输出 Review 结果
```

如果从 Agent 的角度来看，这个流程可以理解为：

```text
确定任务范围
    ↓
获取上下文
    ↓
扩展信息来源
    ↓
搜索相关知识
    ↓
生成决策结果
```

这个流程说明，Open Code Review 并不是简单地把代码变更直接交给大模型，而是通过多个工具逐步补充上下文，再生成最终审查结果。

这也是它和普通“把代码复制给 AI，让 AI 帮忙看看”的方式不同的地方。

普通 Prompt Review 通常是：

```text
用户复制代码
    ↓
模型直接给建议
```

而 Open Code Review 更接近一个 Agent 系统：

```text
识别变更
    ↓
读取上下文
    ↓
搜索相关代码
    ↓
结合规则审查
    ↓
生成结构化评论
```

这种方式更适合真实项目中的代码审查场景。

---

### 10.7 小结

通过分析本次调用的工具，进一步理解了 Open Code Review 的核心思路。它不是单纯依赖大模型本身的能力，而是把代码审查过程拆成多个可控步骤，并通过 Agent 的方式逐步执行：

1. 先通过 Git diff 确定审查范围；
2. 再通过文件读取获取代码上下文；
3. 通过代码搜索寻找相关实现；
4. 结合规则系统确定审查重点；
5. 最后生成带有文件路径和行号的评论。

这种设计可以让 AI Code Review 更接近真实开发流程，也让审查结果更容易被开发者理解和使用。

本次实验中，工具调用帮助 Open Code Review 成功定位到了 `deleteUser` 函数中的问题，包括 SQL 注入、异步错误处理缺失和权限校验缺失。




**Open Code Review 的审查过程不是一次简单的大模型问答，
而是一个基于 Agent 的工程化流程，
由 Git diff、规则系统、工具调用和 LLM 协同完成代码审查。**

---
## 十一、学习总结








通过这个最小 Demo，对 Open Code Review 有了第一层理解。

首先，`ocr review` 更像是一个面向 PR 的代码审查工具。它关注当前 Git diff，因此更适合在开发流程中使用，比如提交代码前、本地自查、CI 中自动审查 PR。

其次，`ocr scan` 更像是一个代码质量扫描工具。它不依赖 Git diff，可以直接扫描文件或目录，更适合检查历史代码、陌生项目或准备做代码质量治理的场景。

第三，自定义规则非常重要。因为不同项目关注点不一样，前端项目可能更关注空值、异步错误、类型问题；后端项目可能更关注 SQL 注入、事务、并发、资源释放、权限校验。通过 `.opencodereview/rule.json`，可以让 AI Review 更贴近项目真实需求。

最后，AI Code Review 并不能完全替代人工 Review。它更适合作为辅助工具，帮助开发者提前发现低级错误、安全风险和工程规范问题。真正有价值的是把它接入日常开发流程，而不是只当成一次性的问答工具。



下一步准备学习：

1.查看 Open Code Review 的项目目录结构；
2.定位 ocr review 命令的源码入口；
3.分析 cmd/opencodereview 中 CLI 命令是如何组织的；
4.理解 ocr review 支持哪些参数，例如 --preview、--format、--from、--to、--commit 等；
5.追踪 ocr review 从命令入口到核心审查逻辑的调用链；
6.整理一次完整 ocr review 的执行流程。

---


本文对应的项目结构如下：

```text
ocr-practice-demo
├── .opencodereview
│   └── rule.json
├── src
│   └── user.js
└── ocr-review-result.json
```

第一篇学习记录到这里结束。
