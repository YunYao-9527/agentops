# AgentOps — Agent 评测与可观测平台

一个轻量但功能完整的 AI Agent 评测与可观测平台，参考 Langfuse、Braintrust、LangSmith 的架构设计。

## 核心功能

### 🔗 Trace 采集与可观测
- **`@observe` 装饰器**：零侵入式 Span 采集，自动捕获输入/输出、耗时、嵌套关系
- **OpenAI/Anthropic Wrapper**：一行代码自动追踪所有 LLM 调用
- **Span 树可视化**：甘特图 + 树形图展示完整执行链路
- **批量上报**：异步缓冲 + 定时 flush，不影响业务延迟

### 🧪 评测引擎
- **规则评分 (RuleScorer)**：精确匹配、包含检查、正则匹配、工具调用检查、JSON Path 校验
- **LLM Judge (LLMJudgeScorer)**：使用 LLM 评估输出质量，支持自定义评判标准
- **组合评分 (CompositeScorer)**：加权平均、全部通过、任一通过三种聚合模式
- **评测执行器 (EvalRunner)**：并发执行数据集评测，自动收集 Trace 和 Score

### 📝 Prompt 版本管理
- 版本化存储（name + version 唯一）
- 标签系统（"production", "staging", "canary"）
- 按 name + label 运行时解析，支持 A/B 测试

### 📊 仪表盘与指标
- 成本追踪（按 model/project）
- 延迟统计（P50, P95, P99）
- 成功率、Token 用量、状态分布
- 模型使用对比

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端框架 | FastAPI + Uvicorn |
| 数据库 | PostgreSQL + SQLAlchemy 2.0 (async) |
| 缓存 | Redis |
| SDK | Python (装饰器 + contextvars) |
| 前端 | Jinja2 + Tailwind CSS + HTMX + Alpine.js |
| 评测 | 内置规则引擎 + OpenAI LLM Judge |
| 部署 | Docker Compose |

## 快速开始

### 1. 启动基础设施

```bash
docker compose up -d postgres redis
```

### 2. 安装依赖

```bash
pip install -e ".[dev]"
```

### 3. 配置环境

```bash
cp .env.example .env
# 编辑 .env，填入 API Key 等配置
```

### 4. 初始化数据库

```bash
make db-migrate
```

### 5. 启动服务

```bash
make run
```

访问 http://localhost:8080 查看 Dashboard。

## SDK 使用

### 基本用法

```python
import agentops

# 初始化
client = agentops.init(project="my-project")

# 装饰函数自动创建 Span
@agentops.observe(name="process-query")
async def process_query(query: str):
    return await llm_call(query)

# 手动创建 Trace
async with agentops.trace("my-task") as t:
    result = await process_query("Hello")
    t.set_output(result)

# 添加评分
agentops.score(trace_id, "accuracy", 0.95)
```

### OpenAI 自动追踪

```python
import openai
import agentops

# 包装客户端
client = agentops.openai_wrapper(openai.AsyncOpenAI())

# 所有调用自动追踪
response = await client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Hello"}],
)
```

## 评测使用

### 规则评分

```python
from src.core.scorers import RuleScorer

scorer = RuleScorer(
    name="tool_usage",
    rules=[
        {"type": "tool_called", "tool_name": "get_order"},
        {"type": "not_contains", "field": "content", "value": "sorry"},
    ],
)

result = await scorer.score(input={...}, output={...}, trace_data={...})
```

### LLM Judge

```python
from src.core.scorers import LLMJudgeScorer

judge = LLMJudgeScorer(
    name="task_completion",
    criteria="Did the agent complete the refund correctly?",
    threshold=0.7,
)

result = await judge.score(input={...}, output={...}, expected={...})
```

### 评测执行

```python
from src.core.eval_runner import EvalRunner

runner = EvalRunner(scorers=[scorer, judge], max_concurrent=5)
results = await runner.run(
    dataset=[{"input": {...}, "expected_output": {...}}, ...],
    task_fn=my_agent_function,
)
```

## API 文档

启动服务后访问 http://localhost:8080/docs 查看 Swagger 文档。

### 主要端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/ingestion` | POST | 批量接收 Trace/Span/Score |
| `/api/v1/traces` | GET | 查询 Trace 列表 |
| `/api/v1/traces/{id}` | GET | Trace 详情 + Span 树 |
| `/api/v1/prompts` | GET/POST | Prompt 管理 |
| `/api/v1/prompts/{name}/resolve` | GET | 按标签解析 Prompt |
| `/api/v1/datasets` | GET/POST | 数据集管理 |
| `/api/v1/evaluations/run` | POST | 运行评测 |
| `/api/v1/metrics/dashboard` | GET | 仪表盘指标 |

## 项目结构

```
agentops/
├── agentops/               # Python SDK
│   ├── client.py           # 客户端
│   ├── context.py          # 上下文管理
│   ├── decorators.py       # @observe 装饰器
│   ├── wrappers.py         # OpenAI/Anthropic wrapper
│   └── buffer.py           # 异步事件缓冲
├── src/
│   ├── api/                # FastAPI 路由
│   ├── core/               # 核心引擎
│   │   ├── scorers/        # 评分器
│   │   ├── eval_runner.py  # 评测执行器
│   │   └── metrics.py      # 指标收集
│   ├── db/                 # 数据模型
│   ├── prompts/            # Prompt 注册表
│   ├── web/                # 前端模板
│   └── eval/               # 评测场景
└── tests/                  # 测试
```

## 设计参考

本项目参考了以下平台的架构设计：

- [Langfuse](https://github.com/langfuse/langfuse) — 开源 LLM 可观测平台
- [Braintrust](https://www.braintrust.dev/) — 评测优先的 AI 平台
- [LangSmith](https://smith.langchain.com/) — LangChain 生态的 Trace 平台

## License

MIT
