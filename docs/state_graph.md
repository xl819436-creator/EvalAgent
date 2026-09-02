# EvalAgent 状态图（Day 35）

```mermaid
flowchart TD
    START([用户目标]) --> parse_goal[parse_goal]
    parse_goal -->|invalid| END1([END: invalid])
    parse_goal -->|validate| validate_plan[validate_plan]
    validate_plan -->|ready| END2([END: ready, 计划可执行])
    validate_plan -->|needs_info| END3([END: needs_info, 返回缺失字段问题])