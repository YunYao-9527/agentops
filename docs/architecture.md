# AgentOps 架构设计

## 整体架构

```
┌─────────────────────────────────────────────────────────┐
│                    Agent Application                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐  │
│  │ @observe │  │ wrapper  │  │  manual trace/score  │  │
│  └────┬─────┘  └────┬─────┘  └──────────┬───────────┘  │
│       └──────────────┴───────────────────┘              │
│                        │                                │
│                 ┌──────┴──────┐                         │
│                 │ EventBuffer │ (async, batched)        │
│                 └──────┬──────┘                         │
└────────────────────────┼────────────────────────────────┘
                         │ HTTP POST /api/v1/ingestion
                         ▼
┌─────────────────────────────────────────────────────────┐
│                    AgentOps Platform                     │
│                                                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐ │
│  │ Ingestion   │  │ Query API   │  │ Web Dashboard   │ │
│  │ API         │  │             │  │ (Jinja2+HTMX)  │ │
│  └──────┬──────┘  └──────┬──────┘  └────────┬────────┘ │
│         │                │                   │          │
│  ┌──────┴────────────────┴───────────────────┴────────┐ │
│  │              PostgreSQL (traces, spans, scores,     │ │
│  │              prompts, datasets, experiments)        │ │
│  └────────────────────────────────────────────────────┘ │
│                                                         │
│  ┌─────────────────────────────────────────────────────┐│
│  │              Evaluation Engine                       ││
│  │  ┌──────────┐ ┌───────────┐ ┌──────────────────┐   ││
│  │  │RuleScorer│ │LLMJudge   │ │CompositeScorer   │   ││
│  │  └──────────┘ └───────────┘ └──────────────────┘   ││
│  │  ┌──────────────────────────────────────────────┐   ││
│  │  │EvalRunner (concurrent dataset evaluation)    │   ││
│  │  └──────────────────────────────────────────────┘   ││
│  └─────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────┘
```

## 数据模型

```
Trace (顶层执行记录)
├── id, project, name, user_id, session_id
├── tags[], metadata{}, input{}, output{}
├── start_time, end_time, latency_ms
├── total_tokens, total_cost_usd, status
│
└── Span (操作节点，树形嵌套)
    ├── id, trace_id, parent_id
    ├── name, type (llm|tool|chain|event)
    ├── input{}, output{}
    ├── model, prompt_tokens, completion_tokens
    ├── tool_name, tool_input{}, tool_output{}
    ├── start_time, end_time, latency_ms
    └── status, error

Score (评分结果)
├── trace_id, span_id (optional)
├── name, value, source (rule|llm_judge|human)
└── comment, metadata{}

Prompt (版本化 Prompt)
├── name, description
└── PromptVersion[]
    ├── version, type (text|chat)
    ├── content, config{}, labels[]
    └── commit_message

Dataset (评测数据集)
├── name, description
└── DatasetItem[]
    ├── input{}, expected_output{}
    └── metadata{}

Experiment (评测实验)
├── name, dataset_id, config{}
├── status, total_items, completed_items, failed_items
├── aggregate_scores{}, trace_ids[]
└── started_at, completed_at
```

## SDK 集成模式

### 1. 装饰器模式 (推荐)

```python
@agentops.observe(name="my-function", type="chain")
async def my_function(input):
    return await process(input)
```

- 自动创建 Span
- 捕获输入/输出
- 计算耗时
- 处理嵌套关系 (contextvars)

### 2. Wrapper 模式

```python
client = agentops.openai_wrapper(openai.AsyncOpenAI())
```

- 替换原始 `create` 方法
- 自动记录 model、tokens、耗时
- 透明，无需修改业务代码

### 3. 手动模式

```python
async with agentops.trace("my-task") as t:
    result = await do_work()
    t.set_output(result)
    agentops.score(t.id, "quality", 0.9)
```

## 评分体系

### RuleScorer (确定性评分)

| 规则类型 | 说明 |
|---------|------|
| `exact_match` | 字段精确匹配 |
| `contains` | 包含子串 |
| `not_contains` | 不包含子串 |
| `regex` | 正则匹配 |
| `json_path_exists` | JSON Path 存在 |
| `json_path_equals` | JSON Path 值相等 |
| `tool_called` | 指定工具被调用 |
| `tool_not_called` | 指定工具未被调用 |
| `no_hallucination_tools` | 无幻觉工具调用 |
| `max_tool_calls` | 工具调用次数限制 |
| `output_length` | 输出长度检查 |

### LLMJudgeScorer (LLM 评分)

- 使用 OpenAI/Anthropic 模型作为评委
- 自定义评判标准 (criteria)
- 可配置阈值 (threshold)
- 返回评分 + 理由

### CompositeScorer (组合评分)

- `weighted_average`: 加权平均
- `all_must_pass`: 全部通过
- `any_must_pass`: 任一通过
