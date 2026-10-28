# AI Test Workflow

从需求和接口资料生成可审阅的业务规则、测试剧本，再通过 Python 骨架生成并执行测试。附可复用的 Prompt 和 Skill。

Python 3.10+，运行工程仅使用标准库。建议在隔离的开发目录运行。支持 Windows、macOS、Linux 的 Python 命令写法；本次验证环境为 Windows / Python 3.12。

## 获取工程

```sh
git clone https://github.com/captainamari/ai-test-workflow.git
cd ai-test-workflow
```

## 先运行参考示例

```sh
python workflow.py demo
python -m unittest test_workflow -v
```

`demo` 在本机随机端口启动 HTTP 服务，执行 10 条参考测试，再分别注入 3 种缺陷。正常版本应 passed；三个缺陷版本应 failed，且失败来自断言。整个 demo 命令返回 0，表示这种预期对比成立。它没有调用模型，使用的是 `examples/reference` 内已写好的规约和剧本；自动生成的 review 记录明确标成 `reference-example-not-human-review`。

宿主机必须允许 Python 监听及连接 127.0.0.1。遇到 socket 权限错误应先解决宿主权限；不要将它记成业务缺陷检出。服务只存内存数据，退出即释放。

## 实际让 AI 生成一次

```sh
python workflow.py init runs/pilot
```

在当前工程根目录打开可读写文件的编程助手。告诉它本次目录为 `runs/pilot`，按 `skills/ai-test-workflow/SKILL.md` 只完成规则提取阶段。也可直接粘贴 `references/01-spec.md`，连同 `formats.md` 和 inputs 的内容交给普通聊天模型，再手动保存 JSON。不要先把 reference 答案或 demo_service 实现提供给模型。

业务人员核对 `spec.json` 后执行或委托测试人员执行：

```sh
python workflow.py check runs/pilot --stage spec
python workflow.py approve runs/pilot --stage spec --reviewer "实际审核者"
```

让助手按 `references/02-cases.md` 生成剧本。测试人员审核每条前置、请求及独立推导的预期，然后执行：

```sh
python workflow.py check runs/pilot --stage cases
python workflow.py approve runs/pilot --stage cases --reviewer "实际审核者"
python workflow.py render runs/pilot
python workflow.py run runs/pilot
```

不通过时用 `references/03-diagnose.md` 分析。返回码 0 表示完整通过，1 表示测试失败或部分 blocked，2 表示输入/审核/执行准备错误。审核是本地流程记录，不提供身份认证。摘要匹配只能确认版本关联。

`render` 将 ready 剧本填入固定 Python 骨架，并非自由执行模型输出的 Python。`run` 始终启动配套本机服务，不接受公司 URL。所有报告保存在对应目录的 reports；每次运行是新文件。已有运行目录不会被 init 覆盖。

## 更换资料与公司接入

输入样本位于 runs/pilot/inputs。修改前保留原运行用于追溯；新建运行更容易比较。修改本次 inputs 后执行 `python workflow.py snapshot runs/pilot`，重新生成或核对 spec/cases，再审核。上游变化会使旧审核失效。

当前 schema 只表达单商品同步库存预占。通用部分是分阶段产物、来源关联、审核、模板生成和报告，不是库存字段本身。公司接入需测试开发人员维护：

1. 选一个业务操作，列出范围和不做的部分；整理五类 inputs。
2. 按 `references/04-adapt.md` 将构造、调用、观察和清理映射到已存在的函数。
3. 按领域调整 `cases_check`、`code_for`、`harness.py` 和回归样例；超出库存模型时必须同步调整 schema。
4. 修改 `run_tests` 的服务生命周期入口：用已有测试环境/fixture 取代 `demo_service.serve`，使用现有身份与配置入口。保留测试发现计数、版本校验、失败记录及 blocked 处理。不要只把本机 URL 替换成生产地址。
5. 先审阅并执行一条成功和一条业务拒绝场景，确认请求确实抵达被测服务、断言有真实观察依据、数据能清理，再扩大到试点集合。
6. 接入现有 CI。CI 运行已审核产物；需求变化通过代码评审或现有审批记录确认，不能在 CI 内用自动 approve 冒充人工审核。

文件摘要用于追溯，不能抵抗能够同时修改输入、程序、清单和审核记录的人。在公司环境应以代码评审与 CI 权限作为审核凭据。这里不提供完整的执行沙箱、权限系统、分布式并发控制或测试平台。

## 目录

- `examples/inputs`：虚构业务资料、契约、领域说明、能力清单、存量脚本样例。
- `examples/reference`：手写参考答案，供演示重放和事后比较。
- `skills/ai-test-workflow`：Skill 入口、格式说明和 4 份可复制 Prompt。
- `workflow.py`：输入校验、审核关联、生成、执行和报告。
- `harness.py`：测试基类与 API adapter。
- `demo_service.py`：本地被测系统和 3 个故障开关。
- `test_workflow.py`：工作流自身的 10 项回归测试。

示例只覆盖选定规则的代表场景。10 条测试不代表全部边界、分支、并发或完整 API 契约覆盖。
