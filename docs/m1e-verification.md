# M1-E 异步评论采集与任务进度闭环验收报告

> 验收日期：2026-08-17
> 版本：v0.6.0-m1e
> 结论：PASS

## 验收范围

- Compose 自动迁移；
- queued 分析启动和 Celery Worker；
- Fixture 30/60 天评论获取；
- 评论规范化、窗口过滤、无意义文本过滤和稳定去重；
- 多商品原子入库、空样本、失败和重试；
- 分析进度 API 和五步前端进度页；
- 桌面和移动端真实浏览器流程。

不验收评论主题/情感注解、指标、LangGraph、报告、鉴权或真实 Provider。

## 自动化门禁

```powershell
powershell -ExecutionPolicy Bypass -File scripts\verify-local.ps1
```

| 检查 | 结果 |
|---|---|
| Ruff lint | PASS |
| Ruff format check | PASS，104 个文件 |
| mypy strict | PASS，70 个源文件 |
| Pytest | PASS，168 passed |
| 前端 typecheck | PASS |
| 前端 Vitest | PASS，3 个文件、13 passed |
| 前端 production build | PASS |
| Docker Compose config | PASS |
| Alembic | PASS，head=`0006`，无新增迁移 |
| API readiness | PASS，HTTP 200 |

## 独立验收

首次独立验收发现同步 Celery task 复用进程级 asyncpg engine，第二个任务可能遇到已关闭
事件循环。实现已改为每个 Celery task 在自己的事件循环内创建 engine，并在
`asyncio.run()` 返回前执行 `engine.dispose()`。

修复后验证：

- 同一进程连续处理两个任务：PASS；
- 两个任务均进入 processing/45；
- 每个任务 fetched=3、valid=2；
- 500 条硬上限：PASS；
- 初次/轮询临时失败自动恢复：PASS；
- retry 投递失败后按 queued 真源恢复：PASS。

独立验收剩余的大小写去重 concern 也已修复：正文去重严格使用 NFKC/空白规范化结果，
不额外 casefold。

## 真实 Compose 与浏览器

独立项目 `consumer-shopping-assistant-m1e` 使用全新卷启动：

- migrate 完整执行 `0001 -> 0006` 并 `Exited (0)`；
- API/Worker 在 migrate 成功后启动；
- Worker 注册 `app.workers.process_comparison`；
- 完整五步页面自动投递任务；
- Worker 返回 `processed/processing/fetched=3/valid=2`；
- 数据库确认 `status=processing`、`progress=45`、`raw_reviews=2`；
- 刷新后进度和计数恢复；
- 浏览器控制台 0 errors、0 warnings。

修复镜像重建后，又通过真实 API 连续运行两个任务，二者均为 processing/45、3/2。

## 响应式验收

| 视口 | 结果 |
|---|---|
| `1440x900` | PASS |
| `390x844` | PASS，`scrollWidth=390`，无横向溢出 |

截图：

- `docs/assets/m1e-progress-desktop.png`
- `docs/assets/m1e-progress-mobile.png`

## 非阻断 Concern

- Ant Design Vue 主 chunk 约 1.53 MB，沿用既有构建警告。
- Celery 开发容器以 root 运行并输出官方 SecurityWarning；当前仅限本地 Fixture 环境，
  生产部署前应配置非 root 用户。
