"""EvalAgent 最小 HTTP 服务：/health（健康检查用）。"""

from fastapi import FastAPI

app = FastAPI(title="EvalAgent API", version="0.1.0")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "evalagent"}