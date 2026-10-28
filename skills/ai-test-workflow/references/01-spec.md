# Prompt 1 — Extract rules

你正在维护一个分阶段测试工作流。项目根目录有 workflow.py，本次运行目录由用户指定。

读取本次目录中的 inputs/requirements.md、contract.json、domain.md、capabilities.json、existing_test.py，以及本 Skill 的 references/formats.md。

先说明被测操作、范围和排除项；理解存量脚本的前置构造、原始参数发送、观察与清理方式。然后仅在本次运行目录生成 spec.json。

每条规则写明触发条件、业务动作和可观察结果，分配稳定 R 编号，并引用输入文件内一段精确原文。区分字段合法性、业务拒绝、状态改变和仅记录告警的行为。接口结构不能替代缺失的业务语义；代码现状也不能覆盖已确认的新需求。

冲突和缺失信息写入 open_questions，不凭常识补出错误码、超时、重试次数、权限或幂等策略。可以提出待确认的候选解释，但不得将其写成已确认规则。只提取本次范围内的行为。

执行 python workflow.py check 本次运行目录 --stage spec。根据错误做最多两次局部修复。最后给出规则清单、来源、待确认问题和实际检查结果。停止在规则审核处，不执行 approve，不生成测试代码。不读取 examples/reference 或 demo_service.py。
