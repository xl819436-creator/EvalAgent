"""Day 38：安全策略测试——危险拦截、预算暂停、确认信息完整。"""

import pytest

from evalagent.safety import assess_request


def test_delete_all_data_is_blocked():
    # 实战题 1：请求"删除全部评测数据"必须拦截
    result = assess_request("delete", {"target": "删除全部评测数据"}, budget=10.0)
    assert result.decision == "block"
    assert "拦截" in result.reason


def test_drop_database_is_blocked():
    result = assess_request("run", {"sql": "drop database evalhub"}, budget=10.0)
    assert result.decision == "block"


def test_arbitrary_shell_is_blocked():
    # 验收：工具无任意 Shell
    result = assess_request("execute", {"command": "rm -rf /"}, budget=10.0)
    assert result.decision == "block"


def test_over_budget_pauses_not_shrinks_sample():
    # 实战题 2：超预算 → 暂停等待确认，不自动缩小样本
    result = assess_request("create_evaluation",
                            {"model": "deepseek", "dataset": "d.jsonl",
                             "sample_limit": 200, "concurrency": 1},
                            budget=10.0)
    assert result.decision == "awaiting_approval"
    assert "预算" in result.reason
    assert result.approval["sample_limit"] == 200  # 样本数保持，没被偷偷改小


def test_approval_info_contains_four_fields():
    # 实战题 3：确认信息必须展示预计成本、模型、样本数、并发
    result = assess_request("create_evaluation",
                            {"model": "deepseek", "dataset": "d.jsonl",
                             "sample_limit": 300, "concurrency": 1},
                            budget=10.0)
    assert result.decision == "awaiting_approval"
    approval = result.approval
    assert "model" in approval
    assert "sample_limit" in approval
    assert "concurrency" in approval
    assert "estimated_cost" in approval


def test_low_risk_read_is_allowed():
    # 只读查询自动执行（正常任务不误拦）
    result = assess_request("list_models", {}, budget=10.0)
    assert result.decision == "allow"


def test_write_action_requires_confirmation_even_if_cheap():
    # 写操作（创建评测）即使低成本也要确认
    result = assess_request("create_evaluation",
                            {"model": "mock", "dataset": "d.jsonl",
                             "sample_limit": 5, "concurrency": 1},
                            budget=100.0)
    assert result.decision == "awaiting_approval"