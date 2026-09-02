"""Day 36：ToolRegistry 测试——7 工具注册、非法参数拒绝、错误映射。"""

import httpx
import pytest

from evalagent.tools import ToolError, build_default_registry


@pytest.fixture()
def registry():
    return build_default_registry()


def mock_client(routes: dict):
    """用 MockTransport 模拟 EvalHub/RAGEval 的 HTTP 响应。"""

    def handler(request):
        key = (request.method, request.url.path)
        if key in routes:
            status, payload = routes[key]
            return httpx.Response(status, json=payload)
        return httpx.Response(404, json={"detail": "not found"})

    return httpx.Client(transport=httpx.MockTransport(handler), base_url="http://mock")


def test_seven_tools_registered(registry):
    names = registry.list_names()
    assert len(names) == 7
    assert {"list_models", "inspect_dataset", "estimate_cost", "create_evaluation",
            "get_job_status", "fetch_results", "query_rag"} == set(names)


def test_every_tool_has_input_model(registry):
    for name in registry.list_names():
        tool = registry.get(name)
        assert tool.input_model is not None
        assert tool.description


def test_create_evaluation_concurrency_100_rejected(registry):
    # 实战题 1：concurrency=100 被拒绝（≤10），不执行 handler
    client = mock_client({("POST", "/evaluations"): (202, {"job_id": "job-1"})})
    with pytest.raises(ToolError, match="参数校验失败") as exc:
        registry.execute("create_evaluation",
                         {"model": "deepseek", "dataset": "d.jsonl", "concurrency": 100},
                         client)
    assert exc.value.status == 400


def test_invalid_params_do_not_call_handler(registry):
    client = mock_client({})
    with pytest.raises(ToolError, match="参数校验失败"):
        registry.execute("estimate_cost", {"prompt_tokens": -5, "completion_tokens": 10}, client)


def test_create_evaluation_valid_calls_handler(registry):
    client = mock_client({("POST", "/evaluations"): (202, {"job_id": "job-1", "status": "pending"})})
    result = registry.execute("create_evaluation",
                              {"model": "deepseek", "dataset": "d.jsonl", "concurrency": 5},
                              client)
    assert result["job_id"] == "job-1"


def test_external_500_mapped_to_retryable_error(registry):
    # 实战题 3：Mock EvalHub 返回 500 → ToolError(retryable=True)
    client = mock_client({("GET", "/evaluations/job-x"): (500, {"detail": "boom"})})
    with pytest.raises(ToolError) as exc:
        registry.execute("get_job_status", {"job_id": "job-x"}, client)
    assert exc.value.status == 500
    assert exc.value.retryable is True


def test_unknown_tool_error(registry):
    client = mock_client({})
    with pytest.raises(ToolError, match="未知工具"):
        registry.execute("no_such_tool", {}, client)


def test_query_rag_passes_params(registry):
    client = mock_client({("GET", "/rag/search"): (200, {"hits": [{"chunk_id": "c1"}]})})
    result = registry.execute("query_rag", {"query": "load_jsonl", "top_k": 3}, client)
    assert result["hits"][0]["chunk_id"] == "c1"