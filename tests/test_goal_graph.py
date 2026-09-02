"""Day 35：StateGraph 测试——完整 / 缺参 / 非法目标三种场景。"""

import pytest

from evalagent.goal_graph import ask_missing, build_graph


@pytest.fixture(scope="module")
def compiled():
    return build_graph()


def test_complete_goal_ready(compiled):
    result = compiled.invoke({
        "user_goal": "用 deepseek 模型评测 dataset.jsonl，用 exact_match",
    })
    assert result["status"] == "ready"
    assert result["missing_fields"] == []
    assert result["plan"]["models"] == ["deepseek"]
    assert result["plan"]["dataset"] == "dataset.jsonl"
    assert result["plan"]["evaluators"] == ["exact_match"]


def test_compare_models_without_dataset_needs_info(compiled):
    # 实战题 1：比较两个模型但没有数据集 → needs_info，不得执行
    result = compiled.invoke({
        "user_goal": "比较 deepseek 和 mock 两个模型",
    })
    assert result["status"] == "needs_info"
    assert "dataset" in result["missing_fields"]
    assert result["plan"]["models"] == ["deepseek", "mock"]


def test_invalid_goal_rejected(compiled):
    # 非法目标：不是评测任务 → invalid + errors
    result = compiled.invoke({"user_goal": "帮我写一首关于春天的诗"})
    assert result["status"] == "invalid"
    assert result["errors"]


def test_ask_missing_returns_question():
    questions = ask_missing({"dataset": None}, ["dataset"])
    assert "数据集" in questions


def test_sample_limit_extracted(compiled):
    result = compiled.invoke({
        "user_goal": "用 mock 评测 data.jsonl，样本 50 条",
    })
    assert result["plan"]["sample_limit"] == 50


def test_plan_is_structured_model(compiled):
    # 验收：计划为结构化模型（EvaluationPlan 字段齐全）
    result = compiled.invoke({
        "user_goal": "用 dummy 评测 eval.jsonl",
    })
    plan = result["plan"]
    for field in ("models", "dataset", "evaluators", "sample_limit", "steps"):
        assert field in plan