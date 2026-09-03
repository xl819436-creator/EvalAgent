"""Day 38：安全策略——高费用/高并发/写操作前确认，危险请求拦截。

决策三态：
- allow：只读/低风险，自动执行
- awaiting_approval：超预算/超并发/样本过多 → 暂停等人工确认（不偷偷缩小样本）
- block：危险请求（删除数据/任意 Shell/未授权路径）→ 拦截

确认信息必须完整展示：预计成本 / 模型 / 样本数 / 并发（实战题 3）。
"""

import json
from typing import Any, Optional

# 危险操作特征词（出现即拦截）——工具采用 allowlist，禁止任意 Shell/删除数据库
DANGER_WORDS = [
    "删除", "清空", "删库", "移除全部", "drop", "delete", "truncate",
    "rm -rf", "rm ", "shell", "bash", "exec(", "os.system", "subprocess",
    "eval(", "写文件到系统", "修改系统",
]

# 只读查询：按风险级别自动执行（不参与预算暂停/确认）
READ_ONLY_ACTIONS = {
    "list_models", "inspect_dataset", "get_job_status",
    "fetch_results", "query_rag", "estimate_cost",
}

# 高费用/高并发的上限（可配置）
MAX_CONCURRENCY = 10
MAX_SAMPLE_LIMIT = 200


class Assessment:
    """一次请求的安全评估结果。"""

    def __init__(self, decision: str, reason: str, approval: Optional[dict] = None):
        self.decision = decision  # allow / awaiting_approval / block
        self.reason = reason
        self.approval = approval  # 确认信息（awaiting_approval 时非空）

    def __repr__(self) -> str:
        return f"Assessment(decision={self.decision}, reason={self.reason!r})"


def _estimated_cost(sample_limit: int, concurrency: int) -> float:
    """粗略成本估算：样本越多成本越高（演示用，真实按 token 算）。"""
    return round(sample_limit * (1.0 + concurrency / 10.0), 2)


def assess_request(
    action: str,
    params: dict[str, Any],
    budget: float,
) -> Assessment:
    """评估一个请求/计划：危险拦截、只读放行、超限/写操作暂停确认。"""
    text = f"{action} {json.dumps(params, ensure_ascii=False)}".lower()

    # 1) 危险请求拦截（实战题 1："删除全部评测数据"必须拦截）
    for word in DANGER_WORDS:
        if word in text:
            return Assessment("block", f"危险操作被拦截：命中特征「{word}」")

    # 2) 只读查询自动执行（验收：正常任务仍可完成）
    if action in READ_ONLY_ACTIONS:
        return Assessment("allow", "只读查询，自动执行")

    # 3) 读取参数（缺省用合理默认）
    sample_limit = int(params.get("sample_limit", 20))
    concurrency = int(params.get("concurrency", 1))

    # 4) 超并发/超样本 → 暂停等确认（不悄悄改小）
    if concurrency > MAX_CONCURRENCY:
        return Assessment("awaiting_approval",
                          f"并发 {concurrency} 超过上限 {MAX_CONCURRENCY}，等待确认",
                          approval=_approval_info(params, None))
    if sample_limit > MAX_SAMPLE_LIMIT:
        return Assessment("awaiting_approval",
                          f"样本数 {sample_limit} 超过上限 {MAX_SAMPLE_LIMIT}，等待确认",
                          approval=_approval_info(params, None))

    # 5) 预算检查（实战题 2：超预算 → 暂停，不缩小样本）
    cost = _estimated_cost(sample_limit, concurrency)
    if cost > budget:
        return Assessment(
            "awaiting_approval",
            f"预计成本 {cost} 元超过预算 {budget} 元：暂停等待确认（不自动缩小样本）",
            approval=_approval_info(params, cost),
        )

    # 6) 数据变更/写操作即使低成本也要确认（如创建评测任务）
    if action in ("create_evaluation", "publish_report", "update_dataset"):
        return Assessment(
            "awaiting_approval",
            f"写操作「{action}」执行前需人工确认",
            approval=_approval_info(params, cost),
        )

    return Assessment("allow", "只读/低风险，自动执行")


def _approval_info(params: dict[str, Any], cost: Optional[float]) -> dict:
    """确认信息：预计成本、模型、样本数、并发（实战题 3 要求的四要素）。"""
    return {
        "model": params.get("model", "未知"),
        "dataset": params.get("dataset", "未指定"),
        "sample_limit": params.get("sample_limit", 20),
        "concurrency": params.get("concurrency", 1),
        "estimated_cost": cost,
    }