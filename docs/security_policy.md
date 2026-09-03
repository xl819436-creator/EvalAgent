# 安全策略（Day 38）

## 三态决策
- allow：只读查询自动执行（list_models / inspect_dataset / query_rag 等）
- awaiting_approval：超预算 / 超并发 / 超样本 / 写操作 → 暂停等确认
- block：命中危险特征（删除 / drop / shell / rm / os.system 等）→ 拦截

## 确认信息（四要素）
模型 / 数据集 / 样本数 / 并发 + 预计成本

## 工具边界
- allowlist 7 个工具，无任意 Shell / 无删除数据库 / 无未授权路径

## 实测（2026-08-28）
- 10 条危险任务拦截率 100%，10 条正常任务完成率 100%