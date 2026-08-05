# M0 运行验收报告

> spec：`changes/active/spec.md`
> tasks：`changes/active/tasks.md`
> 初次验证：2026-07-16
> 补齐运行验收：2026-08-05
> 结论：**有条件通过（PASS_WITH_CONCERNS），允许进入 M1**

## 本次验收范围

仅验收进入 M1 前尚未完成的 M0 运行项：

1. PostgreSQL/Alembic 数据库迁移；
2. Testcontainers PostgreSQL 集成测试；
3. Docker Compose 全栈启动；
4. 健康检查正常路径、依赖故障路径和故障恢复。

## 维度总览

| 维度 | 判定 | 通过率 | 说明 |
|---|:---:|:---:|---|
| 完整性 | ✅ | 7/7 | 四项 M0 补验均有实际执行证据 |
| 正确性 | ✅ | 8/8 | 迁移、临时数据库、服务访问、故障与恢复语义正确 |
| 一致性 | ⚠️ | 4/5 | 运行结果一致；发现并治理 Compose 项目名混杂风险 |

## 数据库迁移

执行环境：Python 3.12 API 容器、PostgreSQL 16。

```text
alembic upgrade head
Running upgrade  -> 0001, 建立 M0 空迁移基线。

alembic current
0001 (head)

alembic check
No new upgrade operations detected.
```

结论：✅ 空迁移链可在目标容器环境中执行，数据库处于 migration head。

为支持容器内迁移，`backend/Dockerfile` 已复制 `alembic.ini` 和 `alembic/`。

## Testcontainers

执行：

```bash
cd backend
PYTHONPATH=src python -m pytest -m integration tests/integration/db -v
```

结果：

```text
1 passed in 5.27s
```

测试实际完成：

- 启动临时 `postgres:16-alpine`；
- 执行 Alembic migration；
- 使用 asyncpg 执行 `SELECT 1`；
- 执行事务 rollback；
- 测试结束后销毁临时容器。

首次运行暴露宿主环境缺少 psycopg binary wrapper；安装 `psycopg-binary` 后通过。项目 `pyproject.toml` 已声明 `psycopg[binary]>=3.2,<4`，CI/干净安装具备可复现依赖。

## Docker Compose 全栈启动

目标服务：

| 服务 | 结果 |
|---|---|
| PostgreSQL 16 | ✅ healthy |
| Redis 7 | ✅ healthy |
| FastAPI API | ✅ running，端口 8000 |
| Celery Worker | ✅ running，`inspect ping` 返回 `pong`，1 node online |
| Vue/Nginx Web | ✅ HTTP 200，端口 5173 |

Compose 文件当前位于 `docker/docker-compose.yml`，已完成两项运行修复：

- `env_file` 从相对 Compose 目录的 `.env` 修正为 `../.env`；
- 增加顶层 `name: consumer-shopping-assistant`，避免与用户已有 Dify Compose 的通用 `docker` 项目名共享命名空间。

## 健康检查

### 正常状态

| 请求 | 结果 |
|---|---|
| `GET /health/live` | ✅ HTTP 200，`{"status":"ok"}`，包含 `X-Trace-Id` |
| `GET /health/ready` | ✅ HTTP 200，`{"status":"ready"}`，包含 `X-Trace-Id` |

### Redis 故障

停止 Redis 后：

- ✅ live 保持 HTTP 200；
- ✅ ready 返回 HTTP 503；
- ✅ Content-Type 为 `application/problem+json`；
- ✅ 包含 `code=PROVIDER_UNAVAILABLE`、`detail` 和 `trace_id`；
- ✅ 响应体 `trace_id` 与 `X-Trace-Id` 一致；
- ✅ Redis 恢复后重新 healthy。

### PostgreSQL 故障

停止 PostgreSQL 后：

- ✅ live 保持 HTTP 200；
- ✅ ready 返回相同契约的 HTTP 503 ProblemDetails；
- ✅ PostgreSQL 恢复后重新 healthy；
- ✅ 最终 ready 恢复 HTTP 200，Worker 再次返回 `pong`。

## 运行期间修复的问题

### 1. Pydantic Settings 白名单解析

症状：API/Worker 容器启动时报：

```text
SettingsError: error parsing value for field "taobao_allowed_hosts"
```

根因：`pydantic-settings` 对 tuple 环境变量先按 JSON 解码，`.env` 使用逗号分隔字符串，原有 field validator 没有机会执行。

修复：

- 使用 `Annotated[tuple[str, ...], NoDecode]`；
- 由 validator 解析逗号分隔 host；
- 新增配置回归测试。

验证：14 个相关测试通过，Ruff 和 mypy 通过，Python 3.12 API/Worker 均启动成功。

排查记录：`changes/active/debug-log-2026-08-05-settings-hosts.md`。

### 2. 容器缺少 Alembic 文件

根因：原 Dockerfile 只复制 `pyproject.toml` 和 `src/`，没有将 `alembic.ini` 与 migration scripts 放入镜像。

修复后容器内 `upgrade/current/check` 全部通过。

## 问题清单

### 🔴 Critical

无。

### 🟡 Warning

- Compose 已设置顶层 `name: consumer-shopping-assistant`，与用户已有 Dify Compose 隔离；旧的本项目 `docker-*` 五个容器已确认标签归属后替换为 `consumer-shopping-assistant-*`，未删除或修改 Dify 服务。
- 前端构建仍有大 chunk 提示，属于 M1 之后的非阻塞优化项。
- 真实淘宝 Provider 仍因正式授权与合规核验未完成而 blocked；不影响 Fixture 模式进入 M1。

### 🔵 Suggestion

- 后续统一使用：

```bash
docker compose -f docker/docker-compose.yml <command>
```

- 不再从 `docker/` 目录隐式运行 Compose，也不手工使用通用 project name `docker`。
- 可在后续 CI 中增加 live/ready 依赖故障 smoke test。

## 最终结论

**PASS_WITH_CONCERNS — 有条件通过。**

M0 的数据库迁移、Testcontainers、五服务启动及健康检查正常/故障/恢复路径均已通过，允许进入 M1。剩余 Warning 为运维隔离和后续优化问题，不构成 M1 阻塞。

## 合规门禁

T07 仍为 `blocked`：尚未取得正式淘宝数据接口授权和合规批准。T09 与真实淘宝生产发布不得开始；Fixture 内部开发可继续。
