"""Day 37：恢复与幂等测试——实战题 1/2/3。"""

import json

import pytest

from evalagent.checkpoint import CheckpointStore
from evalagent.resume import ResumableRunner

PLAN = {"models": ["mock"], "dataset": "d.jsonl", "evaluators": ["exact_match"],
        "sample_limit": 20, "steps": ["retrieve", "generate", "score"]}


@pytest.fixture()
def store(tmp_path):
    return CheckpointStore(directory=str(tmp_path / "ckpt"))


def test_restart_after_job_created_does_not_recreate(store):
    # 实战题 1：创建 job 后"进程中断"（第一步就抛错停止），重启不重复收费创建
    create_calls = {"n": 0}

    def create_job(key):
        create_calls["n"] += 1
        return f"JOB-{create_calls['n']}"

    def step_interrupt(i):
        raise RuntimeError("模拟中断：创建 job 后进程退出，尚未执行任何步骤")

    runner1 = ResumableRunner(store, create_job, step_interrupt,
                              fetch_actual_count=lambda j: 20, expected_total=20)
    run1 = runner1.start_or_resume(PLAN, run_id="run-A")
    assert create_calls["n"] == 1          # job 创建了 1 次
    assert run1["external_job_id"] == "JOB-1"

    # 重启：新 runner 实例（等价于进程重启），resume 同一个 run_id
    runner2 = ResumableRunner(store, create_job, lambda i: None,
                              fetch_actual_count=lambda j: 20, expected_total=20)
    run2 = runner2.start_or_resume(PLAN, run_id="run-A")

    assert create_calls["n"] == 1          # 关键：不重复创建（幂等，不重复收费）
    assert run2["external_job_id"] == "JOB-1"
    assert run2["status"] == "completed"
    assert run2["completed_steps"] == [0, 1, 2]


def test_92_of_100_marks_incomplete(store):
    # 实战题 2：期望 100，实际 92 → incomplete，不误报 completed
    runner = ResumableRunner(
        store,
        create_job=lambda key: "JOB-92",
        execute_step=lambda i: None,
        fetch_actual_count=lambda j: 92,
        expected_total=100,
    )
    run = runner.start_or_resume(PLAN, run_id="run-B")
    assert run["status"] == "incomplete"
    assert run["actual_count"] == 92
    assert any("样本不齐" in e for e in run["errors"])


def test_repeated_resume_is_idempotent(store):
    # 实战题 3：重复 resume 两次，状态与外部调用次数保持一致
    create_calls = {"n": 0}

    def create_job(key):
        create_calls["n"] += 1
        return f"JOB-{create_calls['n']}"

    runner = ResumableRunner(store, create_job, lambda i: None,
                             fetch_actual_count=lambda j: 20, expected_total=20)
    first = runner.start_or_resume(PLAN, run_id="run-C")
    second = runner.start_or_resume(PLAN, run_id="run-C")  # 重复 resume

    assert create_calls["n"] == 1          # job 只创建 1 次
    assert first["status"] == second["status"] == "completed"
    assert first["completed_steps"] == second["completed_steps"] == [0, 1, 2]
    assert first["external_job_id"] == second["external_job_id"] == "JOB-1"


def test_checkpoint_does_not_store_secrets(store):
    # 验收：Checkpoint 不存明文密钥
    runner = ResumableRunner(store, lambda key: "JOB-S", lambda i: None,
                             fetch_actual_count=lambda j: 1, expected_total=1)
    runner.start_or_resume(PLAN, run_id="run-D")
    raw = json.loads((store.directory / "run-D.json").read_text(encoding="utf-8"))
    assert "api_key" not in raw and "sk-" not in json.dumps(raw, ensure_ascii=False)