"""Day 36：ToolRegistry——7 个有输入校验的服务工具 + 注册表。

为什么需要注册表：EvalAgent 要调 EvalHub（评测）和 RAGEval（检索）的服务，
每个工具 = 名字 + 说明 + Pydantic 输入模型（先校验再执行，非法参数不调服务，省钱防错）。
执行时先 model_validate 参数，失败抛 ToolError(status=400)；HTTP 5xx 映射为 retryable=True。
"""

from dataclasses import dataclass
from typing import Any, Callable

import httpx
from pydantic import BaseModel, Field, ValidationError

# ---------- 工具错误 ----------


class ToolError(Exception):
    """工具层错误：status=HTTP 语义状态码，retryable=是否值得重试。"""

    def __init__(self, message: str, status: int = 500, retryable: bool = False):
        super().__init__(message)
        self.message = message
        self.status = status
        self.retryable = retryable


# ---------- 各工具的 Pydantic 输入模型（非法参数在进 handler 前就被拦下）----------


class ListModelsInput(BaseModel):
    """列可用模型：无需参数，模型可为空。"""

    pass


class InspectDatasetInput(BaseModel):
    dataset: str = Field(..., min_length=1, description="数据集路径，如 dataset.jsonl")


class EstimateCostInput(BaseModel):
    model: str = Field("deepseek", description="模型名")
    prompt_tokens: int = Field(0, ge=0, description="输入 token 数（不能为负）")
    completion_tokens: int = Field(0, ge=0, description="输出 token 数（不能为负）")


class CreateEvaluationInput(BaseModel):
    model: str = Field(..., min_length=1, description="要评测的模型")
    dataset: str = Field(..., min_length=1, description="评测数据集路径")
    concurrency: int = Field(1, ge=1, le=10, description="并发数（上限 10，防止打爆服务）")


class GetJobStatusInput(BaseModel):
    job_id: str = Field(..., min_length=1, description="评测任务 id")


class FetchResultsInput(BaseModel):
    job_id: str = Field(..., min_length=1, description="评测任务 id")


class QueryRagInput(BaseModel):
    query: str = Field(..., min_length=1, description="检索问题")
    top_k: int = Field(5, ge=1, le=50, description="返回条数")


# ---------- 工具本体 ----------


@dataclass
class Tool:
    """一个可执行工具：校验参数后调用 handler(client, **参数)。"""

    name: str
    description: str
    input_model: type[BaseModel]
    handler: Callable[..., dict]


def _check_response(response: httpx.Response) -> dict:
    """把 HTTP 响应转成结果 dict；5xx 映射为 retryable、4xx 为不可重试。"""
    if response.status_code >= 500:
        raise ToolError(
            f"服务错误 {response.status_code}: {response.text[:200]}",
            status=response.status_code,
            retryable=True,
        )
    if response.status_code >= 400:
        raise ToolError(
            f"请求失败 {response.status_code}: {response.text[:200]}",
            status=response.status_code,
            retryable=False,
        )
    return response.json()


# --- handler：真正调服务的部分（client 由外部注入，便于 MockTransport 测试）---

def _h_list_models(client: httpx.Client, **_: Any) -> dict:
    resp = client.get("/models")
    return _check_response(resp)


def _h_inspect_dataset(client: httpx.Client, dataset: str, **_: Any) -> dict:
    resp = client.get(f"/datasets/{dataset}")
    return _check_response(resp)


# 价格表：每 1M token 的 USD（prompt / completion）；教学用估算，不接真实计费
_PRICES_PER_M = {"deepseek": (0.27, 1.10), "gpt-4o": (2.50, 10.00), "mock": (0.0, 0.0)}


def _h_estimate_cost(
    client: httpx.Client | None = None,
    model: str = "deepseek",
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    **_: Any,
) -> dict:
    p_price, c_price = _PRICES_PER_M.get(model, _PRICES_PER_M["deepseek"])
    cost = (prompt_tokens * p_price + completion_tokens * c_price) / 1_000_000
    return {
        "model": model,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "estimated_cost_usd": round(cost, 6),
    }


def _h_create_evaluation(
    client: httpx.Client, model: str, dataset: str, concurrency: int = 1, **_: Any
) -> dict:
    resp = client.post(
        "/evaluations",
        json={"model": model, "dataset": dataset, "concurrency": concurrency},
    )
    return _check_response(resp)


def _h_get_job_status(client: httpx.Client, job_id: str, **_: Any) -> dict:
    resp = client.get(f"/evaluations/{job_id}")
    return _check_response(resp)


def _h_fetch_results(client: httpx.Client, job_id: str, **_: Any) -> dict:
    resp = client.get(f"/evaluations/{job_id}/report")
    return _check_response(resp)


def _h_query_rag(client: httpx.Client, query: str, top_k: int = 5, **_: Any) -> dict:
    resp = client.get("/rag/search", params={"query": query, "top_k": top_k})
    return _check_response(resp)


# ---------- 注册表 ----------


class ToolRegistry:
    """名字 -> Tool 的注册表：注册、查询、统一执行（先校验再调用）。"""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def list_names(self) -> list[str]:
        """返回已注册工具名列表（保持注册顺序）。"""
        return list(self._tools)

    def get(self, name: str) -> Tool:
        if name not in self._tools:
            raise ToolError(f"未知工具: {name}", status=404)
        return self._tools[name]

    def execute(self, name: str, params: dict, client: httpx.Client | None = None) -> dict:
        """统一入口：先 Pydantic 校验参数，再调 handler；校验失败不调服务。"""
        tool = self.get(name)
        try:
            validated = tool.input_model.model_validate(params)
        except ValidationError as exc:
            raise ToolError(f"参数校验失败: {exc}", status=400) from exc
        return tool.handler(client, **validated.model_dump())


def build_default_registry() -> ToolRegistry:
    """建默认注册表：EvalAgent 的 7 个服务工具。"""
    registry = ToolRegistry()
    registry.register(Tool("list_models", "列出当前可用的评测模型", ListModelsInput, _h_list_models))
    registry.register(Tool("inspect_dataset", "查看评测数据集的信息", InspectDatasetInput, _h_inspect_dataset))
    registry.register(Tool("estimate_cost", "估算一次评测的 API 成本（USD）", EstimateCostInput, _h_estimate_cost))
    registry.register(Tool("create_evaluation", "发起一次评测任务（并发 ≤ 10）", CreateEvaluationInput, _h_create_evaluation))
    registry.register(Tool("get_job_status", "查询评测任务状态", GetJobStatusInput, _h_get_job_status))
    registry.register(Tool("fetch_results", "获取评测任务的报告", FetchResultsInput, _h_fetch_results))
    registry.register(Tool("query_rag", "对 RAG 语料做向量检索，返回相关块（路径/行号/分数）", QueryRagInput, _h_query_rag))
    return registry
