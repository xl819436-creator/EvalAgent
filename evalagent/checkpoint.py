"""Day 37：Checkpoint 存储——把 run 的执行状态持久化到磁盘。

每个 run 记录：run_id / thread_id / step_id / idempotency_key /
plan / completed_steps / external_job_id / cost / errors / status。
MVP 用 JSON 文件（可换 SQLite），Checkpoint 不存明文密钥。
"""

import json
import uuid
from pathlib import Path
from typing import Any, Optional


def new_idempotency_key() -> str:
    """每次"新建任务"前分配的唯一键（幂等依据）。"""
    return f"idem-{uuid.uuid4().hex[:12]}"


class CheckpointStore:
    """把 run 存成 JSON 文件，重启后仍能读回。"""

    def __init__(self, directory: str = "checkpoints"):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def _path(self, run_id: str) -> Path:
        return self.directory / f"{run_id}.json"

    def save(self, run: dict[str, Any]) -> None:
        self._path(run["run_id"]).write_text(
            json.dumps(run, ensure_ascii=False, indent=2), encoding="utf-8")

    def load(self, run_id: str) -> Optional[dict[str, Any]]:
        path = self._path(run_id)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))


def new_run(plan: dict, run_id: Optional[str] = None) -> dict[str, Any]:
    """初始化一个 run 记录。"""
    return {
        "run_id": run_id or f"run-{uuid.uuid4().hex[:8]}",
        "thread_id": f"thread-{uuid.uuid4().hex[:8]}",
        "step_id": 0,
        "idempotency_key": None,
        "plan": plan,
        "completed_steps": [],
        "external_job_id": None,
        "cost": 0.0,
        "errors": [],
        "status": "pending",  # pending / running / completed / incomplete / failed
    }