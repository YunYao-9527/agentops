"""Order refund evaluation scenario — tests agent's ability to handle refund requests."""

from src.core.scorers import RuleScorer, LLMJudgeScorer, CompositeScorer

# ─── Test Dataset ─────────────────────────────────────────────────────────────

ORDER_REFUND_DATASET = [
    {
        "id": "refund_basic",
        "input": {
            "user_message": "我想退款，订单号是 ORD20240101001",
            "user_id": "user_001",
            "context": "User wants a full refund for order ORD20240101001",
        },
        "expected_output": {
            "action": "request_refund",
            "order_no": "ORD20240101001",
            "refund_type": "full",
            "tool_calls": ["get_order", "request_refund"],
        },
    },
    {
        "id": "refund_partial",
        "input": {
            "user_message": "我只想退订单ORD20240101002里的第一个商品",
            "user_id": "user_001",
        },
        "expected_output": {
            "action": "request_refund",
            "order_no": "ORD20240101002",
            "refund_type": "partial",
        },
    },
    {
        "id": "refund_already_delivered",
        "input": {
            "user_message": "我的订单ORD20240101003已经签收了，还能退吗？",
            "user_id": "user_002",
        },
        "expected_output": {
            "action": "check_policy",
            "order_no": "ORD20240101003",
            "should_check_return_policy": True,
        },
    },
    {
        "id": "refund_no_order",
        "input": {
            "user_message": "我要退订单 ORD9999999",
            "user_id": "user_001",
        },
        "expected_output": {
            "action": "error",
            "error_type": "order_not_found",
        },
    },
    {
        "id": "refund_with_confirmation",
        "input": {
            "user_message": "帮我退掉订单ORD20240101001，全额退款到原支付方式",
            "user_id": "user_001",
        },
        "expected_output": {
            "action": "request_refund",
            "requires_confirmation": True,
            "refund_amount_should_be_specified": True,
        },
    },
]

# ─── Scorers ──────────────────────────────────────────────────────────────────

ORDER_REFUND_SCORERS = [
    # 1. Must call get_order before attempting refund
    RuleScorer(
        name="tool_order",
        rules=[
            {
                "type": "tool_called",
                "tool_name": "get_order",
                "description": "Must retrieve order details before processing refund",
            }
        ],
    ),
    # 2. Should not hallucinate tools
    RuleScorer(
        name="no_hallucination",
        rules=[
            {
                "type": "no_hallucination_tools",
                "allowed_tools": [
                    "get_order", "get_user_orders", "request_refund",
                    "approve_refund", "process_refund", "get_user",
                    "verify_user_identity", "get_account", "get_logistics",
                ],
            }
        ],
    ),
    # 3. LLM judge for task completion
    LLMJudgeScorer(
        name="task_completion",
        criteria="""Evaluate whether the customer service agent:
1. Correctly identified the user's refund intent
2. Retrieved order information before acting
3. Followed proper refund procedures
4. Communicated clearly with the user
5. Handled edge cases (order not found, already delivered, etc.)""",
        threshold=0.7,
    ),
]

# Composite scorer combining all
ORDER_REFUND_COMPOSITE = CompositeScorer(
    name="order_refund_eval",
    scorers=[
        (ORDER_REFUND_SCORERS[0], 0.3),  # tool_order
        (ORDER_REFUND_SCORERS[1], 0.2),  # no_hallucination
        (ORDER_REFUND_SCORERS[2], 0.5),  # task_completion
    ],
    aggregation="weighted_average",
    pass_threshold=0.7,
)
