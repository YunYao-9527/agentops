# 云端运行 AgentOps

本仓库包含真实 FastAPI 后端。GitHub Pages 仅承载项目介绍，运行服务请使用 Render 的 Web Service。

## Render 配置

- 运行环境：Python 3.12（也可使用仓库根目录 Dockerfile）
- 构建命令：`pip install -e .`
- 启动命令：`uvicorn src.main:app --host 0.0.0.0 --port $PORT`
- 健康检查：`/health`
- 预览实例：Free
- 环境变量：`DATABASE_URL=sqlite+aiosqlite:///./agentops.db`，`APP_ENV=production`

也可以在 Render 中使用仓库根目录 `render.yaml` 创建 Blueprint。

访问服务根路径打开仪表盘，访问 `/docs` 查看 API 文档。Trace、Span、Score 写入与查询、数据集及规则评测无需外部 LLM 密钥。LLM Judge 需在 Render 环境变量中配置对应模型密钥。

## 数据保存

此配置用于在线预览。Render Free 的 SQLite 文件会在实例休眠、重启或重新部署后丢失。需要长期保存数据时，请配置外部 PostgreSQL 或持久磁盘；不要将预览库作为唯一的数据副本。

## 已验证

- 后端启动及仪表盘页面。
- SQLite 下真实 Trace / Span / Score 写入与详情查询。
- 数据集创建、条目写入及指标读取。
- 现有 12 项单元与集成测试。
- `/evaluations` 中可创建示例数据集并真实运行规则评分，结果和 Trace 会写入数据库。

云平台返回服务部署成功且实际请求通过后，才算云端服务已上线。
