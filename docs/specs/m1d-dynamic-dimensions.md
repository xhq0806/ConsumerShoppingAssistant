# M1-D 动态维度推荐与维度确认闭环

> 归档日期：2026-08-11
> 版本：v0.5.0-m1d
> 原始变更：`changes/archive/2026-08-11-m1d-dynamic-dimensions/`
> 验收报告：`docs/m1d-verification.md`

## 功能描述

M1-D 在商品确认和用户偏好闭环之上，实现动态对比维度的生成、恢复、调整和确认。系统
从版本化维度目录中加载通用及手机品类候选，根据用户关注点、商品事实差异和数据完整度
执行确定性排序，默认选择 8 个重点维度。用户可添加、删除和调整顺序，确认后任务推进到
`queued`，但不启动 Celery/LangGraph 分析。

## 核心行为

1. `0006` 数据迁移注册 16 个受控维度，不新增表或字段。
2. 首次推荐持久化全部候选到 `task_dimensions`，重复生成幂等返回。
3. 用户关注点通过 NFKC 受控同义词映射置顶，不调用 LLM，不创建目录外维度。
4. 商品存在差异且数据可用的维度优先；数据风险分为 available/partial/unavailable。
5. 查询接口恢复重点项、其他可选项、顺序、理由和风险。
6. 确认请求必须提交唯一、非空且属于当前任务候选的有序 code。
7. 确认时先重置 position，再写入连续顺序，避免唯一位置冲突。
8. 状态依次从 `awaiting_dimension_confirmation` 进入 `ready_for_analysis`、`queued`。
9. queued 后相同顺序可幂等确认，不同内容返回冲突。
10. 事件只记录候选数、选中数和状态，不记录用户自由文本。

## API

```text
POST /api/v1/comparisons/{comparison_id}/dimensions/recommendations
GET  /api/v1/comparisons/{comparison_id}/dimensions
POST /api/v1/comparisons/{comparison_id}/dimensions/confirm
```

## Web

新增 `/comparisons/:id/dimensions`，支持：

- 重点对比和其他可选两个区域；
- 受控推荐理由和数据风险；
- 搜索、添加、删除、原生拖拽和上下移动按钮；
- 刷新后从服务端恢复；
- 零维度确认拦截；
- queued 后锁定编辑并明确分析尚未启动。

## 代码索引

| 路径 | 职责 |
|---|---|
| `backend/alembic/versions/0006_seed_m1d_dimension_catalog.py` | 通用和手机维度种子 |
| `backend/src/app/domain/dimensions/recommendation.py` | 确定性推荐、风险和理由 |
| `backend/src/app/application/comparisons.py` | 生成、查询、确认和状态推进 |
| `backend/src/app/infrastructure/db/catalog_repository.py` | 任务维度持久化查询 |
| `backend/src/app/api/comparisons.py` | 三个动态维度端点 |
| `frontend/src/views/comparisons/DimensionsView.vue` | 动态维度确认页面 |
| `frontend/src/stores/comparison.ts` | 维度请求状态与恢复 |

## Out Of Scope

- 评论获取、清洗、主题识别和指标计算；
- 品牌资料采集；
- Celery/LangGraph 实际分析编排；
- 任务进度页、报告和图表；
- 用户鉴权、真实淘宝 Provider 和真实 LLM。
