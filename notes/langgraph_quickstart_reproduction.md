# LangGraph Quickstart 官方示例复现记录（Day 35）

- 复现日期：2026-08-29
- 环境：`D:\Annaconda\envs\evalhub-py311\python.exe`，langgraph **1.2.11**
- 官方文档：<https://langchain-ai.github.io/langgraph/>

## 第 1 步：官方最小示例本地跑通

官方 Quickstart 的最小形态是"两个节点按顺序传值"的加法器演示，
与官方 StateGraph 入门代码一致：

```python
from typing import TypedDict
from langgraph.graph import StateGraph, START, END

class State(TypedDict):
    value: int

def add_one(state: State) -> State:
    return {"value": state["value"] + 1}

def double(state: State) -> State:
    return {"value": state["value"] * 2}

builder = StateGraph(State)
builder.add_node("add_one", add_one)
builder.add_node("double", double)
builder.add_edge(START, "add_one")
builder.add_edge("add_one", "double")
builder.add_edge("double", END)
graph = builder.compile()

print(graph.invoke({"value": 1}))   # {'value': 4}
print(graph.invoke({"value": 10}))  # {'value': 22}
```

本机实测输出：

```
langgraph 1.2.11
invoke({'value': 1}) -> {'value': 4}
invoke({'value': 10}) -> {'value': 22}
节点列表: __start__ -> add_one -> double -> __end__
边: __start__->add_one, add_one->double, double->__end__
```

机制解读：

- **State 是 TypedDict**：节点函数入参是整个 state，返回值是"要更新的字段"，LangGraph 自动合并进 state；
- **add_node 注册节点、add_edge 定顺序**：`START -> add_one -> double -> END` 是固定线性流；
- **compile() 得到可 invoke 的 app**：`invoke(初始 state)` 让 state 一路流经所有节点，最后返回最终 state。

## 第 2 步：官方示例 vs 我的评测计划图

| 维度 | 官方最小示例（加法器） | 我的 `evalagent/goal_graph.py` |
|---|---|---|
| 节点 | `add_one` / `double`（纯计算，无业务含义） | `parse_goal` / `validate_plan`（业务节点：解析目标 → 校验计划） |
| state 传值 | `state["value"]` 一个数字逐节点运算 | `user_goal` → `plan`（Pydantic 模型 `model_dump()` 成 dict）→ `missing_fields` / `status` / `errors` |
| 边 | 固定线性 `add_edge` | **条件分支**：`parse_goal` 后非法目标直接 `END`，否则进 `validate_plan`；`validate_plan` 后按 `status`（ready / needs_info / invalid）分支出图 |
| 数据模型 | `TypedDict`（int） | `TypedDict(EvalState)` + **Pydantic `EvaluationPlan`**（models.py：models / dataset / evaluators / sample_limit / steps） |
| 目的 | 演示状态如何在节点间流转 | 自然语言目标 → 结构化评测计划；缺参不执行（needs_info 转提问）、非法目标拦截（invalid） |
| 实测结果 | `{'value': 4}` / `{'value': 22}` | `status=ready` / `needs_info+missing_fields` / `invalid+errors` |

本机实测我的图（langgraph 1.2.11）：

- 「评测 deepseek 和 mock，用 dataset.jsonl，样本 20 条」→ `status=ready`，plan 含 `models=[deepseek, mock]`、`dataset=dataset.jsonl`、`steps=[retrieve, generate, score]`
- 「评测 deepseek」（缺 dataset）→ `status=needs_info`，`missing=[dataset]`，`ask_missing` → "用哪个评测数据集？"
- 「今天天气怎么样」→ `status=invalid`，`errors=[目标不是可执行的评测任务（无模型名，也无评测意图关键词）]`

## 结论

官方示例演示的是"**节点间传值**"这一最基础机制（状态如何流过图）；
我在同一机制上加了三样东西：**业务节点**（parse_goal/validate_plan）、**条件分支**（按状态走不同出口）、**Pydantic 结构化计划**（EvaluationPlan），
把 `notes/day35.md` 里"固定评测流程用 Workflow 更安全"的判断落地成了可复现、可测试的最小状态图。
