# Day 37 实战题记录

实战题 1/2/3 全部由 `tests/test_resume_idempotency.py` 覆盖（4 passed），各记一句结论：

1. **重启不重建 job = 幂等防重复收费**：`test_restart_after_job_created_does_not_recreate` —— 创建外部 job 后进程中断，重启用同一 `run_id` resume 时不再调用 `create_job`（checkpoint 已记录 `external_job_id`，直接沿用续跑），外部 job 只创建 1 次。
2. **92/100 必须标 incomplete**：`test_92_of_100_marks_incomplete` —— 期望 100、实际 92 时 `status=incomplete` 且 errors 记录"样本不齐"，绝不误报 completed。
3. **重复 resume 计数不变**：`test_repeated_resume_is_idempotent` —— 同一 `run_id` 连续 resume 两次，`create_job` 仍只调 1 次，状态 / `external_job_id` / `completed_steps` 与第一次完全一致。

附加验收：`test_checkpoint_does_not_store_secrets` —— checkpoint JSON 不存明文密钥（无 `api_key` 字段、无 `sk-` 前缀内容）。
