# 恢复场景（Day 37）

配套实现：`evalagent/checkpoint.py`（CheckpointStore，JSON 持久化）+ `evalagent/resume.py`（ResumableRunner，断点续跑）。
测试：`tests/test_resume_idempotency.py`（4 passed）。

## 场景一：创建外部 job 后进程中断 → 重启不重建 job

- **故障**：`create_job` 已成功（外部评测任务 JOB-1 已创建、会计费），但进程随即崩溃，任何步骤都未执行。
- **恢复行为**：重启后用同一 `run_id` 调 `start_or_resume` → CheckpointStore 读回已持久化的 `external_job_id`，`ResumableRunner` **不再调用 create_job**，沿用 JOB-1 从第 0 步续跑直到完成。
- **效果**：外部 job 全程只创建 1 次 → **幂等，不重复收费**。
- **测试**：`test_restart_after_job_created_does_not_recreate`（create_calls 保持 1；重启后 `completed_steps=[0,1,2]`、`status=completed`）。

## 场景二：结果样本不齐 → 92/100 不误报完成

- **故障**：步骤全部执行完，但外部任务实际只完成 92/100 条样本（部分样本失败/超时被跳过）。
- **恢复行为**：`fetch_actual_count(job_id)` 返回 92 < `expected_total=100` → `status=incomplete`，errors 记录"样本不齐：期望 100，实际 92"，**绝不标 completed**。
- **效果**：不把不完整结果当成功 → 结果验证不误报。
- **测试**：`test_92_of_100_marks_incomplete`（`actual_count==92`、errors 含"样本不齐"）。

## 场景三：重复 resume → 恢复操作幂等，无副作用

- **故障**：Agent 因网络重试或手动重跑，同一 `run_id` 被反复 `start_or_resume`。
- **恢复行为**：第二次起直接读 checkpoint：job 不重建、`completed_steps` 不重跑、`status`/`external_job_id`/`completed_steps` 与第一次完全一致。
- **效果**：重复恢复不会重复收费、不会重复执行。
- **测试**：`test_repeated_resume_is_idempotent`（resume 两次，create_calls 仍为 1，两次结果全等）。

## 附加保证：Checkpoint 不存明文密钥

- checkpoint JSON 只持久化 run 状态字段（run_id / thread_id / step_id / idempotency_key / plan / completed_steps / external_job_id / cost / errors / status），
  任何位置不允许出现 `api_key` 字段或 `sk-` 前缀的明文密钥内容。
- **测试**：`test_checkpoint_does_not_store_secrets`（断言原始 JSON 无 `api_key`、序列化全文无 `sk-`）。
