"""Day 39：端到端演示——比较两个模型 + RAG 解释 + 生成报告。

容器内运行（三个服务都起来后）：
    docker exec evalagent python scripts/e2e_demo.py
会生成 artifacts/e2e_report.md。
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import json
import time
import uuid
from typing import Any, Optional

import httpx

EVALHUB_URL = "http://evalhub:8000"    # compose 网络内用服务名，不用 localhost（验收）
RAGEVAL_URL = "http://rageval:8000"
MAX_RETRIES = 2


def new_request_id() -> str:
    return f"req-{uuid.uuid4().hex[:12]}"


def _request(client: httpx.Client, method: str, url: str,
             request_id: str, **kwargs) -> Optional[dict]:
    """带 request_id 的请求，服务端错误做有界重试（实战题 2：不无限循环）。"""
    headers = {"X-Request-Id": request_id}
    last_error = "unknown"
    for attempt in range(1, MAX_RETRIES + 2):
        try:
            response = client.request(method, url, headers=headers, timeout=5.0, **kwargs)
            if response.status_code < 500:
                return response.json()
            last_error = f"HTTP {response.status_code}"
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            last_error = type(exc).__name__
        if attempt <= MAX_RETRIES:
            time.sleep(0.2)
    raise RuntimeError(f"服务不可用（重试 {MAX_RETRIES} 次后）：{url} -> {last_error}")


def main() -> int:
    request_id = new_request_id()
    report = {
        "request_id": request_id,
        "model_a": "deepseek", "model_b": "mock",
        "evalhub": {"ok": False}, "rageval": {"ok": False},
        "status": "incomplete",
        "failures": [],
    }

    # 1) 调 EvalHub：列模型 + 创建评测
    try:
        with httpx.Client(base_url=EVALHUB_URL) as client:
            models = _request(client, "GET", "/models", request_id)
            job = _request(client, "POST", "/evaluations", request_id,
                           json={"model": report["model_a"], "dataset": "d.jsonl",
                                 "sample_limit": 5})
        report["evalhub"]["ok"] = True
        report["evalhub"]["models"] = models
        report["job_id"] = job.get("job_id")
        report["model_a_result"] = {"accuracy": 0.85, "p95_ms": 320}
        report["model_b_result"] = {"accuracy": 0.90, "p95_ms": 280}
    except RuntimeError as exc:
        report["evalhub"]["detail"] = str(exc)
        report["failures"].append(f"EvalHub 不可用：{exc}")

    # 2) 调 RAGEval：解释失败案例
    try:
        with httpx.Client(base_url=RAGEVAL_URL) as client:
            rag = _request(client, "GET", "/rag/search", request_id,
                           params={"query": "为什么 exact_match 会失败", "top_k": 3})
        report["rageval"]["ok"] = True
        report["rageval"]["hits"] = rag.get("hits", [])
    except RuntimeError as exc:
        report["rageval"]["detail"] = str(exc)
        report["failures"].append(f"RAGEval 不可用：{exc}")

    # 3) 报告状态：两个服务都成功才 completed（单服务故障不假装成功）
    if report["evalhub"]["ok"] and report["rageval"]["ok"]:
        report["status"] = "completed"

    lines = [
        "# E2E 评测报告", "",
        f"- request_id: `{report['request_id']}`",
        f"- 状态: **{report['status']}**",
        f"- 模型对比: {report['model_a']} vs {report['model_b']}", "",
        "## EvalHub", f"- 可用: {report['evalhub']['ok']}",
    ]
    if report["evalhub"].get("models"):
        lines.append(f"- 模型列表: {report['evalhub']['models']}")
    if report.get("model_a_result"):
        lines.append(f"- {report['model_a']}: {report['model_a_result']}")
    if report.get("model_b_result"):
        lines.append(f"- {report['model_b']}: {report['model_b_result']}")
    lines += ["", "## RAGEval（失败案例解释）", f"- 可用: {report['rageval']['ok']}"]
    if report["rageval"].get("hits"):
        for hit in report["rageval"]["hits"][:3]:
            lines.append(f"- {hit}")
    if report["failures"]:
        lines += ["", "## 未完成任务（不假装成功）"]
        lines += [f"- {f}" for f in report["failures"]]
    lines += ["", "## 已知限制", "- 演示使用 Mock 结果；真实模型接入后数字会变化。"]

    out = Path("artifacts/e2e_report.md")
    out.parent.mkdir(exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"报告已生成：{out}（状态 {report['status']}）")
    return 0 if report["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())