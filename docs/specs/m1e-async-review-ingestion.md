# M1-E 异步评论采集与任务进度闭环

> 归档日期：2026-08-17
> 版本：v0.6.0-m1e
> 原始变更：`changes/archive/2026-08-17-m1e-async-review-ingestion/`
> 验收报告：`docs/m1e-verification.md`

## 功能描述

M1-E 让 M1-D 产生的 queued 任务被真实 Celery Worker 消费。进度页通过显式 start API
投递任务，Worker 抢占 queued 状态后在事务外获取全部 Fixture 评论，执行确定性清洗，
再在单事务中持久化有效 `raw_reviews`。成功后任务进入 `processing`、进度 45，作为后续
主题、情感和指标分析的交接边界。

## 核心行为

1. Compose 的 migrate 服务在 API/Worker 启动前自动执行 Alembic。
2. start API 对 queued 任务投递 Celery，运行中状态幂等返回。
3. 重复消息只有一个 Worker 能通过行锁执行 queued→fetching。
4. Provider 调用不在数据库事务内，任一商品失败不会保存半套评论。
5. 单商品评论上限 500 条，按任务 30/60 天窗口和已选 SKU 请求。
6. 清洗执行 NFKC、空白收敛、窗口过滤、无意义文本过滤和稳定正文去重。
7. 评论中的外部指令只作为普通文本持久化，不进入日志或事件。
8. 全部成功后原子保存评论并进入 processing/45。
9. Provider unavailable/rate limit 失败可 retry；retry 在提交 queued 后再次投递。
10. 每个同步 Celery task 在自身事件循环中创建并释放 asyncpg engine。
11. 进度页自动启动、每秒轮询、刷新恢复，并在临时请求失败后继续重试。

## API

```text
POST /api/v1/comparisons/{comparison_id}/analysis/start
POST /api/v1/comparisons/{comparison_id}/analysis/retry
GET  /api/v1/comparisons/{comparison_id}/analysis/progress
```

## 代码索引

| 路径 | 职责 |
|---|---|
| `backend/src/app/domain/reviews/cleaning.py` | 评论规范化、过滤和稳定去重 |
| `backend/src/app/application/analysis_tasks.py` | 调度、状态、获取、入库、失败和重试 |
| `backend/src/app/workers/analysis.py` | Celery 同步/异步桥接与连接池生命周期 |
| `backend/src/app/workers/dispatcher.py` | Celery 投递适配器 |
| `backend/src/app/api/comparisons.py` | start/retry/progress 路由 |
| `docker/docker-compose.yml` | migrate 前置服务和启动门禁 |
| `frontend/src/views/comparisons/ProgressView.vue` | 自动启动、轮询、计数和 retry 页面 |

## Out Of Scope

- 评论主题、情感和证据注解；
- 指标、置信度和趋势计算；
- LangGraph、报告、图表和追问；
- 真实淘宝评论、用户鉴权和公网部署。
