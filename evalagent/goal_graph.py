"""Day 35：自然语言目标 -> 结构化评测计划 的最小 StateGraph。

节点：parse_goal -> validate_plan（条件分支结束）
- 完整目标：status=ready（可执行）
- 缺参数：status=needs_info，missing_fields 列出缺什么（不执行）
- 非法目标：status=invalid，errors 记录原因（不是评测任务）

MVP 的 parse_goal 用规则解析（不调 LLM），保证可复现、可测试。
"""

import re
from typing import TypedDict

from langgraph.graph import END, StateGraph

from evalagent.models import EvaluationPlan

# 已知模型名（小写匹配）
KNOWN_MODELS = ["deepseek", "mock", "dummy", "v4-flash", "v4-pro", "gpt-4o"]
# 评测意图关键词（出现才算"这是评测任务"）
INTENT_WORDS = ["评测", "评估", "evaluate", "benchmark", "比较", "对比", "跑分", "score"]


class EvalState(TypedDict, total=False):
    """图的状态：目标文本 -> 计划 -> 校验结果。"""

    user_goal: str
    plan: dict
    missing_fields: list[str]
    status: str
    errors: list[str]


def _extract_models(goal: str) -> list[str]:
    """从目标文本里找出模型名（去重、保序）。"""
    lower = goal.lower()
    found = [name for name in KNOWN_MODELS if name in lower]
    return list(dict.fromkeys(found))


def _extract_dataset(goal: str) -> str | None:
    """找数据集路径（如 dataset.jsonl 或 '数据集 xxx'）。"""
    match = re.search(r"([\w./\\-]+\.jsonl?)", goal)
    if match:
        return match.group(1)
    match = re.search(r"(?:数据集|dataset)[:：=]?\s*([\w./\\-]+)", goal)
    if match:
        return match.group(1)
    return None


def _extract_sample_limit(goal: str) -> int:
    match = re.search(r"(?:sample_limit|样本|条|个)[:：]?\s*(\d{1,3})", goal)
    return int(match.group(1)) if match else 20


def parse_goal(state: EvalState) -> EvalState:
    """节点 1：把自然语言目标解析成 EvaluationPlan（规则版）。"""
    goal = state["user_goal"].strip()
    lower = goal.lower()
    has_intent = any(word in lower for word in INTENT_WORDS)

    models = _extract_models(goal)
    if not has_intent and not models:
        return {
            **state,
            "plan": None,
            "status": "invalid",
            "errors": ["目标不是可执行的评测任务（无模型名，也无评测意图关键词）"],
        }

    evaluators = []
    if re.search(r"json(?!l)", lower):  # json 后不是 l（排除 .jsonl 文件名）
        evaluators.append("json_schema")
    evaluators.append("exact_match")

    plan = EvaluationPlan(
        models=models,
        dataset=_extract_dataset(goal),
        evaluators=list(dict.fromkeys(evaluators)),
        sample_limit=_extract_sample_limit(goal),
    )
    return {**state, "plan": plan.model_dump(), "errors": []}


def validate_plan(state: EvalState) -> EvalState:
    """节点 2：检查计划必填项；缺什么记进 missing_fields，不执行。"""
    plan = EvaluationPlan.model_validate(state["plan"])
    missing = []
    if not plan.models:
        missing.append("models")
    if not plan.dataset:
        missing.append("dataset")
    if not plan.evaluators:
        missing.append("evaluators")
    state["missing_fields"] = missing
    state["status"] = "needs_info" if missing else "ready"
    return state


def route_after_parse(state: EvalState) -> str:
    """parse_goal 后分支：非法目标直接结束，否则进 validate_plan。"""
    return "invalid" if state.get("status") == "invalid" else "validate"


def route_after_validate(state: EvalState) -> str:
    """validate_plan 后分支：ready / needs_info 都结束（状态已标记）。"""
    return state["status"]


def build_graph():
    """构建并编译状态图。"""
    graph = StateGraph(EvalState)
    graph.add_node("parse_goal", parse_goal)
    graph.add_node("validate_plan", validate_plan)
    graph.set_entry_point("parse_goal")
    graph.add_conditional_edges(
        "parse_goal",
        route_after_parse,
        {"validate": "validate_plan", "invalid": END},
    )
    graph.add_conditional_edges(
        "validate_plan",
        route_after_validate,
        {"ready": END, "needs_info": END, "invalid": END},
    )
    return graph.compile()


def ask_missing(plan: dict | None, missing: list[str]) -> str:
    """把缺的字段转成给用户的问题（MVP 的 ask 行为：不执行，返回问题）。"""
    questions = {
        "models": "要评测哪些模型？",
        "dataset": "用哪个评测数据集？",
        "evaluators": "用哪些评分器？",
    }
    return "；".join(questions[f] for f in missing if f in questions)