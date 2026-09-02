# Day 36 实战题记录

## 实战 1：concurrency=100 被拒（测试已覆盖）

- 测试 `test_create_evaluation_concurrency_100_rejected` 已覆盖：
  `CreateEvaluationInput.concurrency` 用 Pydantic `Field(1, ge=1, le=10)` 约束，
  传 `concurrency=100` → `ToolError(status=400, "参数校验失败")`，**handler 不被调用**（不浪费任何外部调用）。
- 实测：`tests/test_tool_registry.py` 8 passed。

## 实战 2：工具描述模糊 → 改清楚

- **问题**：模糊描述（如"检索一下"）让 Agent 无法判断该用哪个工具——它可能选错工具、或反复试错浪费调用。
- **修改**：`query_rag` 的描述从模糊版改成清晰版：
  - 模糊版（改前）："检索一下"（只说了动作，没说对象和返回）
  - 清晰版（改后）："对 RAG 语料做向量检索，返回相关块（路径/行号/分数）"
- **为什么**：描述是 Agent 选工具时**唯一能读到的信息**（五要素之一）。清晰描述 = 动作 + 作用对象 + 返回内容，
  Agent 才能把"帮我搜一下 load_jsonl 在哪里定义"这类目标正确映射到 `query_rag`，而不是 `inspect_dataset` 或别的工具。
- **代码同步**：`evalagent/tools.py` 中 `query_rag` 的注册描述已同步更新为清晰版（描述仍非空，测试不受影响）。

## 实战 3：Mock 500 → 可恢复错误（测试已覆盖）

- 测试 `test_external_500_mapped_to_retryable_error` 已覆盖：
  Mock EvalHub 返回 500 → 工具层抛 `ToolError(status=500, retryable=True)`；
  Agent 看到 `retryable=True` 就知道这是**瞬时故障、可以重试**，而不会把失败当成功、也不会把可恢复错误当永久失败。
- 实测：通过（`exc.value.status == 500` 且 `exc.value.retryable is True`）。
