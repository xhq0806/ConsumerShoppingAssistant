# M1-C 商品输入与用户偏好闭环

> 归档日期：2026-08-10
> 原始 spec：`changes/archive/2026-08-10-m1c-shopping-input-preferences/spec.md`
> 验收报告：`docs/m1c-verification.md`

## 功能描述

M1-C 在 M1-B Comparison API 之上提供首个可操作的 Web 闭环：用户从根页面输入 2～3 个
Fixture 商品链接，完成解析与 SKU 确认，再保存评论窗口、预算、使用场景、关注点和禁忌项。
任务 ID 写入路由，确认页和偏好页刷新后均从服务端详情恢复。

本里程碑仍只服务于本地 Fixture 开发，不包含用户鉴权、动态维度、评论分析、异步编排、
报告或真实淘宝数据接入。

## 核心流程

1. `/` 接受 2～3 个商品链接和 30/60 天评论窗口。
2. 前端创建任务并启动 Fixture 解析，成功后进入 `/comparisons/:id/confirm`。
3. 确认页查询服务端详情，展示最新商品事实、价格、规格和 SKU。
4. 用户一次提交全部商品选择，成功后进入 `/comparisons/:id/preferences`。
5. 偏好页查询详情并回填已有评论窗口和偏好。
6. `PUT /api/v1/comparisons/{id}/preferences` 在短事务内规范化并整体替换偏好。
7. 页面显示保存成功；重新加载后预算和文本列表仍可恢复。

## 边界约束

- 预算使用 Decimal，范围为 0～1,000,000；上限不得低于下限。
- 使用场景为 1～5 项，关注点为 1～8 项，禁忌项为 0～8 项。
- 文本执行 trim、Unicode NFKC、空值拒绝和稳定去重，单项不超过 80 字。
- 只有 `awaiting_dimension_confirmation` 任务可以保存偏好；相同内容可幂等重放。
- 偏好复用 `comparison_tasks.preferences` JSONB，不新增表或 Alembic 迁移。
- 事件只保存评论窗口和条目数量，不保存用户偏好正文。
- 前端统一通过相对 `/api` 请求，不硬编码 API host。
- 原始商品链接不写入 localStorage；浏览器只缓存最近任务 ID 作为继续入口。
- Fixture 图片不可用时展示本地占位视觉，不产生外部图片请求。
- 当前流程无身份和任务归属控制，不得直接公网开放。

## 代码索引

| 文件路径 | 职责 |
|---|---|
| `backend/src/app/domain/comparisons/preferences.py` | 偏好金额、文本规范化和 JSONB 映射 |
| `backend/src/app/application/comparisons.py` | 偏好状态门禁、事务更新和事件留痕 |
| `backend/src/app/api/comparisons.py` | 偏好 PUT 路由和响应映射 |
| `backend/src/app/api/schemas/comparisons.py` | 偏好请求与响应白名单 Schema |
| `frontend/src/api/request.ts` | JSON 请求、超时和 ProblemDetails 解析 |
| `frontend/src/api/comparisons.ts` | Comparison API 类型与端点函数 |
| `frontend/src/stores/comparison.ts` | 创建、解析、恢复、确认和偏好更新状态 |
| `frontend/src/views/comparisons/InputView.vue` | 商品链接输入与解析状态 |
| `frontend/src/views/comparisons/ConfirmProductsView.vue` | 商品事实和 SKU 确认 |
| `frontend/src/views/comparisons/PreferencesView.vue` | 评论窗口和购买偏好表单 |
| `frontend/nginx.conf` | `/api` 反向代理和 SPA fallback |

## 接口定义

| 接口 | 方法 | 说明 |
|---|---|---|
| `/api/v1/comparisons` | POST | 创建包含 2～3 个候选的对比草稿 |
| `/api/v1/comparisons/{comparison_id}/parse` | POST | 使用 Fixture 解析候选商品 |
| `/api/v1/comparisons/{comparison_id}` | GET | 恢复任务、商品、SKU、偏好和事件 |
| `/api/v1/comparisons/{comparison_id}/confirm-products` | POST | 原子确认全部商品与 SKU |
| `/api/v1/comparisons/{comparison_id}/preferences` | PUT | 整体替换评论窗口与用户偏好 |

## 外部依赖

| 包/服务 | 用途 | 备注 |
|---|---|---|
| Vue 3 / Vue Router / Pinia | 三步业务流程与状态恢复 | 页面按路由懒加载 |
| Ant Design Vue | 表单、步骤和反馈控件 | 当前全局导入仍有大 chunk 警告 |
| FastAPI / Pydantic | 偏好 HTTP 契约 | 禁止额外字段 |
| PostgreSQL 16 | 任务和偏好持久化 | 复用既有 JSONB |
| Fixture Commerce Provider | 合成商品解析 | 不执行真实淘宝网络请求 |
