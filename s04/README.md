# 从 0 学习 Alibaba Open Code Review（四）：自定义规则 rule.json 解析
## 前言

上一篇文章中，我学习了 OpenCodeReview 的 Git Diff 解析流程。

通过对比下面几类命令：

```powershell
git status --short
git diff --name-status
git diff --numstat
git diff --stat
git diff
ocr review --preview
```

理解了：

```text
Git diff 决定本次审查哪些文件；
[M] 表示文件被修改；
+7 -1 表示新增 7 行、删除 1 行；
ocr review --preview 可以在不调用 LLM 的情况下预览审查范围。
```

第三篇解决的是：

```text
ocr review 看哪些代码？
```

这一篇继续学习另一个重要问题：

```text
ocr review 按什么规则审查代码？
```

在第一篇中，已经配置过：

```text
.opencodereview/rule.json
```

并且在规则中写了：

```text
重点检查 SQL 注入、硬编码密钥、空值异常、异步错误处理、权限校验缺失和删除类危险操作。
```

当时只是知道加了规则后，OpenCodeReview 的审查结果更关注 SQL 注入、异步错误处理和权限校验问题。

但还没有系统理解：

```text
rule.json 应该放在哪里？
rule.json 的结构是什么？
path: **/*.js 是什么意思？
merge_system_rule: true 是什么作用？
include / exclude 如何影响审查范围？
ocr rules check 输出怎么看？
rule.json 在源码里是如何加载和匹配的？
```

本文就围绕 `.opencodereview/rule.json`，学习 OpenCodeReview 的自定义规则机制。

---

## 一、本篇学习目标

本文主要解决下面几个问题：

```text
1. .opencodereview/rule.json 应该放在哪里？
2. rule.json 的整体结构是什么？
3. path: **/*.js 为什么能匹配 JavaScript 文件？
4. rule 字段如何影响审查重点？
5. merge_system_rule: true 是什么意思？
6. include / exclude 字段有什么作用？
7. ocr rules check 如何验证规则是否命中？
8. rule.json 和 Git diff 的关系是什么？
9. 从源码角度看，rule.json 是如何进入 Agent 审查流程的？
```

---



## 二、规则文件的位置

当前练习项目的 Git 根目录是：

```text
D:\agent\open-code-review-main\ocr-practice-demo
```

本次练习代码放在：

```text
D:\agent\open-code-review-main\ocr-practice-demo\s01
```

当前规则文件实际放在：

```text
D:\agent\open-code-review-main\ocr-practice-demo\s01\.opencodereview\rule.json
```

也就是：

```text
ocr-practice-demo
└─s01
   ├─.opencodereview
   │  └─rule.json
   └─src
      └─user.js
```

这里有一个容易踩坑的点：根据源码，Open Code Review 加载项目级规则时，并不是在所有子目录中递归查找 .opencodereview/rule.json，而是加载 repoDir 下的 .opencodereview/rule.json。


源码中的项目规则路径可以理解为：

```text
repoDir/.opencodereview/rule.json
```

也就是说，如果当前执行命令时的 `repoDir` 是：

```text
ocr-practice-demo
```

那么默认项目规则路径是：

```text
ocr-practice-demo/.opencodereview/rule.json
```

而不是：

```text
ocr-practice-demo/s01/.opencodereview/rule.json
```

所以当前这个练习有两种正确用法。

### 第一种：把规则文件放到当前 `repoDir` 下

也就是放到：

```text
ocr-practice-demo/.opencodereview/rule.json
```

这样执行 `ocr review` 或 `ocr rules check` 时，就会自动作为 Project 规则加载。

例如：

```powershell
cd D:\agent\open-code-review-main\ocr-practice-demo

ocr rules check "s01/src/user.js"

ocr review
```

这种情况下，如果规则成功加载，`ocr rules check` 输出中的 Source 通常会显示为：

```text
Project (.opencodereview/rule.json)
```

这种方式比较适合真实项目，因为项目级规则一般就应该放在项目根目录下，由整个仓库统一使用。

---

### 第二种：保留当前文件位置，但执行命令时显式指定规则文件

如果继续把规则文件放在：

```text
ocr-practice-demo/s01/.opencodereview/rule.json
```

那么执行规则检查时，需要显式指定规则文件：

```powershell
ocr rules check --rule "s01/.opencodereview/rule.json" "s01/src/user.js"
```

如果真正执行代码审查时也想使用这份规则文件，也需要同样显式指定：

```powershell
ocr review --rule "s01/.opencodereview/rule.json"
```

这种方式会把规则作为自定义规则文件加载，输出中的 Source 通常会显示为：

```text
Custom (--rule)
```

---

## 三、查看 `rule.json` 内容

当前规则文件内容如下：

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

这个 JSON 文件主要包含两类配置：

```text
rules
exclude
```

其中：

```text
rules
```

表示针对不同文件路径配置不同审查规则。

```text
exclude
```

表示排除不需要审查的文件或目录。

OpenCodeReview 还支持：

```text
include
```

用来显式标记一些路径为用户关注范围。本文示例里暂时没有使用 `include`。

---

## 四、`rule.json` 的整体结构

可以把这个文件拆成下面几部分理解：

```json
{
  "rules": [
    {
      "path": "**/*.js",
      "rule": "用户自定义审查规则",
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

对应含义是：

```text
rules:
  定义哪些文件使用哪些审查规则。

rules[].path:
  文件匹配模式。

rules[].rule:
  匹配到文件后使用的自定义审查规则。

rules[].merge_system_rule:
  是否把系统默认规则和用户自定义规则合并。

exclude:
  从审查范围中排除的路径模式。
```

其中 `rules` 是一个数组，说明可以配置多条规则。

例如：

```json
"rules": [
  {
    "path": "**/*.js",
    "rule": "JavaScript 文件重点检查 SQL 注入、XSS、异步错误处理。",
    "merge_system_rule": true
  },
  {
    "path": "**/*.go",
    "rule": "Go 文件重点检查错误处理、并发安全、资源释放。",
    "merge_system_rule": true
  }
]
```

这样就可以给不同类型的文件配置不同的审查重点。

需要注意：同一个 `rule.json` 里如果多条规则都能匹配同一个文件，源码实现是：

```text
first match wins
```

也就是先匹配到的规则优先生效。

---

## 五、理解 `path: "**/*.js"`

当前规则中有一行：

```json
"path": "**/*.js"
```

这表示：

```text
匹配任意目录层级下的 .js 文件。
```

其中：

```text
**
```

表示任意层级目录。

```text
*.js
```

表示所有以 `.js` 结尾的文件。

所以：

```text
**/*.js
```

可以匹配：

```text
src/user.js
s01/src/user.js
src/order/order.js
test/user.test.js
pages/index.js
```

当前练习文件是：

```text
s01/src/user.js
```

它符合：

```text
**/*.js
```

所以这条规则可以命中它。

从源码角度看，OpenCodeReview 使用 glob 匹配规则，并且支持 `**` 这种递归路径匹配。

---

## 六、理解 `rule` 字段

当前规则中最核心的是：

```json
"rule": "重点检查 SQL 注入、硬编码密钥、空值异常、异步错误处理、权限校验缺失和删除类危险操作。"
```

这段内容会告诉 OpenCodeReview：

```text
当审查匹配到的 JavaScript 文件时，要重点关注这些问题。
```

也就是：

```text
SQL 注入
硬编码密钥
空值异常
异步错误处理
权限校验缺失
删除类危险操作
```

比如代码中有这样的函数：

```js
function updateUserEmail(db, userId, email) {
  db.query("UPDATE users SET email = '" + email + "' WHERE id = " + userId);
  return true;
}
```

这段代码就很容易触发规则中的：

```text
SQL 注入
异步错误处理
```

因为它直接拼接了 SQL：

```js
"UPDATE users SET email = '" + email + "' WHERE id = " + userId
```

如果 `email` 或 `userId` 来自用户输入，就可能产生 SQL 注入风险。

所以 `rule` 字段的作用可以理解为：

```text
告诉 AI Code Review Agent 本项目希望重点检查什么。
```

源码里还有一个细节：`rule` 不一定只能写内联文本，也可以写一个规则文件路径。

例如：

```json
{
  "path": "**/*.js",
  "rule": "rules/javascript.md",
  "merge_system_rule": true
}
```

如果 `rule` 看起来像 `.md`、`.txt`、`.markdown` 文件路径，OpenCodeReview 会尝试读取这个文件内容作为规则文本。

这适合规则比较长的项目。

---

## 七、理解 `merge_system_rule: true`

当前规则中还有一个字段：

```json
"merge_system_rule": true
```

这个字段非常重要。

它表示：

```text
把系统默认规则和用户自定义规则合并使用。
```

也就是说，OpenCodeReview 不会只使用我写的这条规则，而是会同时使用：

```text
系统默认规则
+
用户自定义规则
```

如果 `merge_system_rule` 没有配置，默认可以理解为 `false`。

这时用户规则会替换系统规则：

```text
只使用用户自定义规则
```

所以两种情况可以对比为：

```text
merge_system_rule: true
  系统规则 + 用户规则

merge_system_rule: false 或不写
  用户规则替换系统规则
```

这也解释了为什么命中当前规则时，`ocr rules check` 输出里会同时出现：

```text
System-Specific Rules
User-Specific Rules
```

因为当前配置明确写了：

```json
"merge_system_rule": true
```

---

## 八、理解 `exclude` 字段

当前规则中还有：

```json
"exclude": [
  "**/node_modules/**",
  "**/dist/**",
  "**/build/**"
]
```

这表示排除下面这些目录：

```text
node_modules
dist
build
```

也就是说，如果 Git diff 中出现这些目录里的文件，OpenCodeReview 可以根据规则把它们排除掉。

这些目录通常不适合进行 AI Code Review：

```text
node_modules 是依赖目录；
dist 是构建产物；
build 是编译输出。
```

它们大多数不是人工手写代码。

如果把这些文件也交给 LLM 审查，会造成：

```text
审查范围变大；
token 消耗增加；
结果噪声变多；
有效评论变少。
```

所以 `exclude` 的作用是：

```text
排除不应该进入审查范围的文件。
```

这一点和第三篇中的 Git diff 有关系。

Git diff 负责告诉 OpenCodeReview：

```text
哪些文件变了？
```

而 `exclude` 可以进一步告诉 OpenCodeReview：

```text
哪些变更文件不需要审查？
```

需要注意：`ocr rules check` 主要用于检查“某个文件会命中哪条规则”，它不会完整模拟 `ocr review --preview` 的文件过滤结果。

如果想确认某个文件是否会被排除，应该看：

```powershell
ocr review --preview
```

Preview 里会区分：

```text
Will review
Excluded from review
```

---

## 九、补充理解 `include` 字段

虽然当前示例没有写 `include`，但 OpenCodeReview 的 `rule.json` 支持：

```json
{
  "include": [
    "src/**/*.js"
  ],
  "exclude": [
    "**/node_modules/**"
  ]
}
```

可以简单理解为：

```text
include 用来声明用户特别关注的路径；
exclude 用来声明用户明确排除的路径。
```

源码里的过滤顺序可以简化理解为：

```text
1. 二进制文件优先排除；
2. 如果命中用户 exclude，则排除；
3. 如果配置了 include 且文件命中 include，则保留；
4. 再检查扩展名是否支持；
5. 再检查默认排除路径。
```

其中 `exclude` 的优先级很高。

如果一个文件同时命中 `include` 和 `exclude`，会被排除。

---

## 十、使用 `ocr rules check` 验证规则是否命中

为了确认 `s01/src/user.js` 是否命中了规则，可以执行：

```powershell
ocr rules check "s01/src/user.js"
```

输出：

```text
File: s01/src/user.js
Source: Custom (--rule)
Pattern: **/*.js
Rule:
────────────────────────────────────────
## System-Specific Rules (Mandatory)

...
---

## User-Specific Rules (Mandatory)

重点检查 SQL 注入、硬编码密钥、空值异常、异步错误处理、权限校验缺失和删除类危险操作。
────────────────────────────────────────
```

如果规则文件在 Git 根目录作为项目规则加载，Source 会是：

```text
Source: Project (.opencodereview/rule.json)
```

如果通过 `--rule` 显式指定规则文件，Source 会是：

```text
Source: Custom (--rule)
```

这个区别可以帮助判断：

```text
当前规则到底是从哪里加载的。
```

---

## 十一、理解 `File`

输出中第一行是：

```text
File: s01/src/user.js
```

这表示当前检查的是：

```text
s01/src/user.js
```

也就是我要验证规则是否命中的目标文件。

---

## 十二、理解 `Source`

输出中会出现：

```text
Source: Custom (--rule)
```

或者：

```text
Source: Project (.opencodereview/rule.json)
```

它表示当前命中的规则来源。

OpenCodeReview 的规则来源有优先级：

```text
1. Custom (--rule)
2. Project (.opencodereview/rule.json)
3. Global (~/.opencodereview/rule.json)
4. System built-in
```

也就是说：

```text
--rule 显式指定的规则优先级最高；
项目规则次之；
用户全局规则再次；
最后才是系统内置规则。
```

如果 Source 显示的是：

```text
System built-in
```

通常说明当前文件没有命中自定义规则，或者自定义规则文件没有被正确加载。

---

## 十三、理解 `Pattern`

输出中还有：

```text
Pattern: **/*.js
```

这说明当前文件命中了规则里的：

```json
"path": "**/*.js"
```

也就是说：

```text
s01/src/user.js 是 .js 文件
        ↓
匹配 **/*.js
        ↓
应用这条规则
```

所以 `Pattern` 这一行证明了：

```text
path 匹配成功。
```

如果没有命中自定义规则，可能会显示系统规则的 pattern，或者显示：

```text
default
```

---

## 十四、理解 `System-Specific Rules`

输出中出现了：

```text
## System-Specific Rules (Mandatory)
```

下面包含系统默认规则，例如：

```text
代码质量
死代码
空值检查
异步处理
安全检查
敏感信息泄露
特定语言最佳实践
```

这些规则不是在当前 `rule.json` 里写的，而是 OpenCodeReview 内置的系统规则。

之所以会显示它们，是因为配置了：

```json
"merge_system_rule": true
```

也就是说，选择了：

```text
保留系统默认规则，同时追加我的自定义规则。
```

---

## 十五、理解 `User-Specific Rules`

输出的后面会出现：

```text
## User-Specific Rules (Mandatory)

重点检查 SQL 注入、硬编码密钥、空值异常、异步错误处理、权限校验缺失和删除类危险操作。
```

这正是我在 `rule.json` 中写的内容：

```json
"rule": "重点检查 SQL 注入、硬编码密钥、空值异常、异步错误处理、权限校验缺失和删除类危险操作。"
```

这说明：

```text
我的自定义规则已经成功加载；
并且已经应用到当前 s01/src/user.js 文件上。
```

到这里，就可以确认：

```text
rule.json 配置成功；
path 匹配成功；
系统规则和用户规则合并成功。
```

---

## 十六、从源码角度理解规则加载流程

第二篇中已经知道，`ocr review` 会进入：

```text
runReview
```

在 `runReview` 中，会调用公共上下文加载逻辑。

简化后的规则加载流程是：

```text
runReview
        ↓
loadCommonContext
        ↓
rules.NewResolver(repoDir, rulePath)
        ↓
加载系统内置规则
        ↓
加载 --rule 指定的 custom 规则
        ↓
加载项目级 .opencodereview/rule.json
        ↓
加载全局 ~/.opencodereview/rule.json
        ↓
生成 composedResolver
        ↓
返回 Resolver 和 FileFilter
```

其中 `Resolver` 负责：

```text
根据文件路径找到应该使用哪段审查规则。
```

`FileFilter` 负责：

```text
根据 include / exclude 判断文件是否应该进入审查范围。
```

所以 `rule.json` 在源码里其实影响两个地方：

```text
1. rules[].path + rules[].rule 决定某个文件使用什么审查规则；
2. include / exclude 决定某些文件是否应该进入审查范围。
```

---

## 十七、规则如何进入 Agent Prompt

真正执行审查时，Agent 会针对每个变更文件解析系统规则。

源码里的逻辑可以简化理解为：

```text
executeSubtask
        ↓
resolveSystemRule(newPath)
        ↓
SystemRule.Resolve(path)
        ↓
得到当前文件对应的规则文本
        ↓
替换 Prompt 模板中的 {{system_rule}}
        ↓
发送给 LLM / Agent 执行审查
```

所以 `rule.json` 不是单独运行的，它最终会变成 Agent prompt 的一部分。

可以理解为：

```text
Git diff 决定 Agent 看哪些代码；
rule.json 决定 Agent 审查这些代码时要重点关注什么。
```

---

## 十八、rule.json 和 Git diff 的关系

第三篇中已经学习过：

```text
Git diff 决定本次有哪些文件发生变更。
```

比如：

```text
[M] s01/src/user.js
```

表示 `s01/src/user.js` 被修改了。

但是 Git diff 只解决一个问题：

```text
看哪些文件？
```

它并不负责告诉 AI：

```text
应该重点检查什么问题？
```

这个时候就需要 `rule.json`。

所以两者的关系可以理解为：

```text
Git diff
  ↓
决定本次变更了哪些文件

rule.json
  ↓
决定这些文件应该按照什么规则审查
```

也可以画成：

```text
Git diff
  ↓
找到变更文件 s01/src/user.js
  ↓
rule.json 匹配 path: **/*.js
  ↓
加载系统规则和用户规则
  ↓
Agent 按规则审查代码
  ↓
生成 Review 评论
```

这是第四篇最重要的一点。

---

## 十九、为什么加规则后审查结果会变化

在没有自定义规则时，OpenCodeReview 也会根据系统规则审查代码。

但是加上下面这条规则后：

```text
重点检查 SQL 注入、硬编码密钥、空值异常、异步错误处理、权限校验缺失和删除类危险操作。
```

Agent 的注意力会更集中到这些方向。

比如我的代码里有：

```js
function updateUserEmail(db, userId, email) {
  db.query("UPDATE users SET email = '" + email + "' WHERE id = " + userId);
  return true;
}
```

这段代码本身就和规则中的关键词高度相关：

```text
SQL 注入
异步错误处理
```

如果是删除用户函数，还可能和：

```text
权限校验缺失
删除类危险操作
```

相关。

所以自定义规则的价值是：

```text
把通用 AI Code Review 变成更贴近当前项目的 Code Review。
```

不同项目关注的问题可能不一样。

例如：

```text
后端项目更关注 SQL 注入、权限校验、事务处理；
前端项目更关注 XSS、状态管理、React Hooks；
支付项目更关注金额精度、幂等性、重复回调；
管理后台更关注越权操作和敏感数据泄露。
```

因此，`rule.json` 可以让 OpenCodeReview 更贴近具体业务场景。

---

## 二十、rule.json 在整个审查流程中的位置

结合前几篇内容，现在可以把 `ocr review` 的流程理解成这样：

```text
用户执行 ocr review
        ↓
读取 Git diff
        ↓
确定本次变更文件
        ↓
根据 include / exclude 和默认规则过滤文件
        ↓
根据 rule.json 的 path 匹配当前文件规则
        ↓
根据 merge_system_rule 判断是否合并系统规则
        ↓
创建 Agent 审查任务
        ↓
Agent 读取代码上下文
        ↓
Agent 根据规则生成 Review 评论
        ↓
输出终端结果或 JSON
```

其中：

```text
Git diff
```

解决的是：

```text
审查哪些文件？
```

而：

```text
rule.json
```

解决的是：

```text
按照什么规则审查？
```

这两个部分共同决定了一次 Review 的输入和审查方向。

---

## 二十一、本文使用的 PowerShell 命令记录

为了方便复盘，本文使用了下面这些命令。

### 1. 查看项目结构

```powershell
tree /F
```

### 2. 查看当前规则文件

如果规则文件仍然在 `s01` 目录下：

```powershell
Get-Content .\s01\.opencodereview\rule.json
```

如果已经移动到 Git 根目录：

```powershell
Get-Content .\.opencodereview\rule.json
```

### 3. 验证指定规则文件是否命中

当前文件在 `s01/.opencodereview/rule.json` 时，使用：

```powershell
ocr rules check --rule "s01/.opencodereview/rule.json" "s01/src/user.js"
```

如果规则文件已经移动到 Git 根目录 `.opencodereview/rule.json`，使用：

```powershell
ocr rules check "s01/src/user.js"
```

### 4. 验证文件是否会被审查

```powershell
ocr review --preview
```

`ocr rules check` 负责看规则是否命中，`ocr review --preview` 负责看文件是否进入审查范围。

---

## 二十二、本篇总结

当前规则文件是：

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

其中：

```text
path: **/*.js
```

表示匹配任意目录下的 JavaScript 文件。

```text
rule
```

表示用户自定义审查重点。

```text
merge_system_rule: true
```

表示合并系统默认规则和用户自定义规则。

```text
exclude
```

表示排除不需要审查的目录。

需要特别注意：

```text
rule.json 如果要作为项目规则自动加载，应该放在 Git 仓库根目录的 .opencodereview/rule.json；
如果放在子目录，需要通过 --rule 显式指定。
```

通过执行：

```powershell
ocr rules check --rule "s01/.opencodereview/rule.json" "s01/src/user.js"
```

可以验证：

```text
规则文件被成功读取；
s01/src/user.js 命中了 **/*.js；
系统规则和用户规则被合并；
自定义规则已经生效。
```

到这里，可以把前几篇的学习串起来：

```text
第一篇：ocr review 能做什么？
第二篇：ocr review 是从哪里启动的？
第三篇：ocr review 看哪些代码？
第四篇：ocr review 按什么规则审查？
```

这一篇的核心结论是：

```text
Git diff 决定审查哪些文件；
rule.json 决定按照什么规则审查这些文件；
ocr rules check 用来验证规则命中；
ocr review --preview 用来验证审查范围。
```

---

## 二十三、下一篇计划：Agent 工具调用分析

下一篇准备继续学习：

```text
从 0 学 OpenCodeReview 源码：Agent 工具调用分析
```

前面几篇已经知道：

```text
Git diff 决定输入；
rule.json 决定规则；
ocr review 会生成审查评论。
```

但还没有深入理解：

```text
OpenCodeReview 为什么不是简单把 diff 丢给 LLM？
file_read 是做什么的？
file_find 是做什么的？
code_search 为什么会出现？
code_comment 如何生成评论？
```

下一篇就围绕这些工具调用日志展开，继续分析 OpenCodeReview 的 Agent 审查流程。
