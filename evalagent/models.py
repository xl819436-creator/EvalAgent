"""Day 35：EvalAgent 结构化评测计划模型（Pydantic）。

EvaluationPlan 是"自然语言目标 -> 可执行计划"的产物：
models / dataset / evaluators / sample_limit / steps 都是 Agent 后续执行要用的字段。
"""

from typing import Optional

from pydantic import BaseModel, Field


class EvaluationPlan(BaseModel):
    """一次评测任务的完整计划（结构化模型）。"""

    models: list[str] = Field(default_factory=list, description="要评测的模型列表")
    dataset: Optional[str] = Field(default=None, description="评测数据集（文件路径）")
    evaluators: list[str] = Field(default_factory=list, description="评分器列表")
    sample_limit: int = Field(default=20, ge=1, le=200, description="最多评测样本数")
    steps: list[str] = Field(
        default_factory=lambda: ["retrieve", "generate", "score"],
        description="执行步骤（固定流程）",
    )