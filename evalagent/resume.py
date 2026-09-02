"""Day 37：可恢复执行器——创建 job 幂等、断点续跑、结果验证不误报。

规则：
- 创建外部 job 前：若 checkpoint 已有 external_job_id → 不重新创建（幂等，不重复收费）
- 重启恢复：load checkpoint → 跳过 completed_steps → 从未完成处继续
- 结果验证：actual < expected → status=incomplete（92/100 不误报完成）
"""

from typing import Callable, Optional

from evalagent.checkpoint import CheckpointStore, new_idempotency_key, new_run


class ResumableRunner:
    """把"创建任务 + 逐步执行 + 结果验证"包成可断点续跑的执行器。"""

    def __init__(
        self,
        store: CheckpointStore,
        create_job: Callable[[str], str],          # 输入 idempotency_key，返回外部 job_id
        execute_step: Callable[[int], None],        # 执行一步（下标从 0）
        fetch_actual_count: Callable[[str], int],   # 输入 job_id，返回实际完成的样本数
        expected_total: int,
    ):
        self.store = store
        self.create_job = create_job
        self.execute_step = execute_step
        self.fetch_actual_count = fetch_actual_count
        self.expected_total = expected_total

    def start_or_resume(self, plan: dict, run_id: Optional[str] = None) -> dict:
        """开始或恢复：已有 checkpoint 则续跑，否则新建。"""
        run = self.store.load(run_id) if run_id else None
        if run is None:
            run = new_run(plan, run_id=run_id)
            run["idempotency_key"] = new_idempotency_key()
        run["status"] = "running"

        # 幂等创建：已有 external_job_id 就不重建（实战题 1/3）
        if run["external_job_id"] is None:
            run["external_job_id"] = self.create_job(run["idempotency_key"])
            self.store.save(run)

        # 从 completed_steps 之后继续（重启后从未完成节点继续）
        steps = run["plan"].get("steps", [])
        for index in range(len(steps)):
            if index in run["completed_steps"]:
                continue
            run["step_id"] = index
            try:
                self.execute_step(index)
                run["completed_steps"].append(index)
            except Exception as exc:  # 某一步失败：记录错误，保持可恢复
                run["errors"].append(f"step {index}: {exc}")
                self.store.save(run)
                return run  # 停在失败处，可再 resume
            self.store.save(run)

        # 结果验证（实战题 2：92/100 不误报完成）
        actual = self.fetch_actual_count(run["external_job_id"])
        run["actual_count"] = actual
        if actual < self.expected_total:
            run["status"] = "incomplete"
            run["errors"].append(f"样本不齐：期望 {self.expected_total}，实际 {actual}")
        else:
            run["status"] = "completed"
        self.store.save(run)
        return run