# E2E 评测报告

- request_id: `req-f2ecd27c1900`
- 状态: **completed**
- 模型对比: deepseek vs mock

## EvalHub
- 可用: True
- 模型列表: {'code': 'HTTP_ERROR', 'message': 'Not Found', 'request_id': '39f5ba61-e15a-45f5-b366-1785634b5d2a', 'details': None}
- deepseek: {'accuracy': 0.85, 'p95_ms': 320}
- mock: {'accuracy': 0.9, 'p95_ms': 280}

## RAGEval（失败案例解释）
- 可用: True
- {'chunk_id': 'evaluators.py:36-49', 'file_path': 'evaluators.py', 'line_range': [36, 49], 'score': 0.3123}
- {'chunk_id': 'evaluator.py:10-16', 'file_path': 'evaluator.py', 'line_range': [10, 16], 'score': 0.189}
- {'chunk_id': 'evaluators.py:41-49', 'file_path': 'evaluators.py', 'line_range': [41, 49], 'score': 0.1655}

## 已知限制
- 演示使用 Mock 结果；真实模型接入后数字会变化。