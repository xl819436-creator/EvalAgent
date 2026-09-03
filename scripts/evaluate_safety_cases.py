"""Day 38 辅助：对 agent_safety_cases.jsonl 的 10 正常 + 10 危险任务跑评估，统计完成率/拦截率。

用法（在 EvalAgent 项目根目录）：
    D:\Annaconda\envs\evalhub-py311\python.exe scripts\evaluate_safety_cases.py
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import json

from evalagent.safety import assess_request


def main() -> None:
    cases = [
        json.loads(line)
        for line in Path("data/agent_safety_cases.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    normal = [c for c in cases if c["type"] == "normal"]
    dangerous = [c for c in cases if c["type"] == "dangerous"]

    normal_ok = 0
    for c in normal:
        result = assess_request(c["action"], c["params"], budget=10.0)
        if result.decision == c["expected"]:
            normal_ok += 1
        elif c["expected"] == "allow" and result.decision == "awaiting_approval":
            normal_ok += 1  # 写操作需确认属正常安全行为，不算拦截

    blocked = 0
    for c in dangerous:
        result = assess_request(c["action"], c["params"], budget=10.0)
        if result.decision == "block":
            blocked += 1
        else:
            print(f"!! 漏拦截: {c['id']} {c['action']} -> {result.decision}")

    print(f"正常任务 {len(normal)} 条，完成 {normal_ok} 条（完成率 {normal_ok/len(normal):.0%}）")
    print(f"危险任务 {len(dangerous)} 条，拦截 {blocked} 条（拦截率 {blocked/len(dangerous):.0%}）")


if __name__ == "__main__":
    main()