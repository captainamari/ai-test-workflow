# Prompt 2 — Design cases

读取本次运行目录中的 spec.json、review-spec.json 和全部 inputs，以及本 Skill 的 references/formats.md。先执行 python workflow.py check 本次运行目录 --stage spec，再执行 python workflow.py verify-review 本次运行目录 --stage spec；若失败，报告需要重新审核并停止。

根据已审核规则生成 cases.json。覆盖成功、有效边界、无效输入和需求明确规定的重复请求行为。每条用例写出目标规则、初始状态、请求及预期的响应和资源变化；除目标失败条件外，其余前置保持有效。

识别 SDK 是否会转换或拦截非法输入。需要验证服务端参数检查时保留原始类型和值。测试相同请求时复用同一 key；不同测试依靠框架的独立命名空间隔离。

核对构造、调用、观察、清理五类能力。缺少能力的场景保留为 blocked，说明具体缺口；不要发明 API，不要用无条件 skip 或删除场景把它隐藏。预期必须由规则推导，不能先运行服务再反填答案。

执行 python workflow.py check 本次运行目录 --stage cases，最多做两次针对检查错误的修复。最后提供可读剧本表、规则关联、未覆盖边界和 blocked 清单。停止在剧本审核处，不执行 approve、render 或 run。不读取 examples/reference 或 demo_service.py。
