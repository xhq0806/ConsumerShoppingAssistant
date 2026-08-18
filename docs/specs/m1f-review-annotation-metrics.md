# M1-F 评论智能注解与指标计算闭环

> 归档日期：2026-08-17
> 版本：v0.7.0-m1f
> 原始变更：`changes/archive/2026-08-17-m1f-review-annotation-metrics/`
> 验收报告：`docs/m1f-verification.md`

## 功能描述

M1-F 把 M1-E 的 `processing/45` 评论数据边界接入 LLM analysis profile。Worker 以最多
20 条评论为一批执行结构化注解，应用层再次校验任务维度、批次覆盖、唯一关系和原文连续
证据；每批提交 `review_annotations`、`model_runs` 和 `partial_result` 断点。全部评论处理
后，由 Python 根据持久化注解确定性重建商品级与任务级指标，并推进到 `processing/75`。

## 核心行为

1. 只允许任务已选目录维度进入模型 Prompt。
2. 每条评论恰好返回一个结果，可包含零到多个不同维度注解。
3. 注解字段为 review ID、dimension code、情感、置信度和原文连续证据。
4. Prompt injection 评论只作为不可信数据，不执行其中指令。
5. LLM 调用位于数据库写事务之外；安全审计先收集到内存，再随批次短事务提交。
6. `partial_result` 只保存 schema version、phase、已处理 review IDs 和计数，不保存正文。
7. 重复 Worker 在提交前重查断点，已处理批次不会重复创建注解。
8. timeout、rate limit、provider unavailable 和 invalid structured output 可 retry。
9. retry 保留已获取评论和成功批次，不重新调用 Commerce Provider。
10. Python 计算 annotation/sentiment count、sentiment ratio、coverage ratio 和 average confidence。
11. 指标整体重建，来源引用只包含受控 review/annotation UUID。
12. 完成后保持 `processing`，progress=75；报告和 completed 状态由 M1-G 负责。

## 进度 API

现有 start/retry/progress API 扩展返回：

```text
annotated_review_count
annotation_count
metric_count
```

`processing` 且 progress<75 时继续轮询；75 时 `stage=metrics_ready` 且
`polling_complete=true`。

## Web

进度页展示六阶段：

```text
任务排队 -> 获取近期评论 -> 清洗评论数据 -> 智能注解 -> 计算指标 -> 报告待生成
```

页面同时展示 Provider 获取数、有效评论数、已有维度注解评论数、注解总数、指标数和评论窗口。

## 边界

- Alembic head 保持 `0006`，业务表保持 16 张。
- `0006` downgrade 会先清理种子维度关联的注解、指标和任务维度。
- 不实现报告、推荐结论、图表、追问、鉴权或真实淘宝 Provider。
- DeepSeek report profile 尚未接入业务流程。
