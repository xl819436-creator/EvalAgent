# Tool 契约（Day 36）

## 五要素（对比 OpenAI Agents SDK / LangGraph 后提炼）

| 要素 | 我的实现 | 说明 |
|---|---|---|
| 名称 | `Tool.name` | 唯一、Agent 引用 |
| 描述 | `Tool.description` | 帮 Agent 选对工具 |
| 参数 | `Tool.input_model`（Pydantic） | 非法参数在入口被拒 |
| 执行 | `Tool.handler(input, client)` | 经 typed HTTP client |
| 错误 | `ToolError(status, retryable)` | 外部错误统一映射 |

## 参考的两个官方 tool 定义

### OpenAI Agents SDK（`@function_tool` 装饰器）

官方文档：<https://openai.github.io/openai-agents-python/tools/>

```python
from agents import function_tool

@function_tool
def get_weather(city: str) -> str:
    """Get the current weather for a city."""
    return f"Weather in {city}: sunny"
```

- 五要素映射：名称 = 函数名；描述 = docstring；参数 = 类型注解生成的 JSON Schema；执行 = 函数体；错误 = 抛异常由 SDK 层捕获。
- 与我的对应：docstring 描述 ≈ `Tool.description`；类型注解/JSON Schema 校验 ≈ Pydantic `input_model`。

### LangGraph（LangChain `@tool` + ToolNode）

官方文档：<https://langchain-ai.github.io/langgraph/concepts/tools/>

```python
from langchain_core.tools import tool
from langgraph.prebuilt import ToolNode

@tool
def multiply(a: int, b: int) -> int:
    """Multiply two numbers."""
    return a * b

# 图里挂 ToolNode 执行：graph.add_node("tools", ToolNode([multiply]))
```

- 五要素映射：名称 = 函数名；描述 = docstring；参数 = `args_schema`（类型注解 → JSON Schema）；执行 = 函数体 / ToolNode；错误 = 异常 → ToolMessage 回传给 Agent。
- 与我的对应：docstring ≈ `Tool.description`；`args_schema` ≈ Pydantic `input_model`。

## 不引入双框架

只用自己这套 registry + httpx；LangGraph / Agents SDK 的 tool 仅作概念参考。

我的实现是"教学最小版"：把两个框架共同的本质（名称 / 描述 / 参数校验 / 执行 / 错误映射）提炼成五要素，换成任意框架都能对号入座；同时零框架依赖、可用 MockTransport 离线测试。
