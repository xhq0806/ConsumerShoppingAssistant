# M1-G 报告生成与任务完成闭环

> 归档日期：2026-08-18
> 版本：v0.8.0-m1g
> 原始变更：`changes/archive/2026-08-18-m1g-report-completion/`
> 验收报告：`docs/m1g-verification.md`

## 功能描述

M1-G 从 `processing/75` 继续生成可追溯购买报告。Worker 创建 version=1 generating 报告，
使用 DeepSeek report profile 选择推荐解释和来源 claim；应用层对商品、维度、claim index 和
source catalog 做语义校验，Repository 再按当前 comparison 查询来源存在性。商品事实、指标
值、完整对比和 partial 判定始终由 Python 与数据库负责。

## 核心行为

1. report profile 使用 V4 Pro、thinking enabled、high effort、120 秒单次超时和 0 次重试。
2. Prompt 只包含当前任务商品事实、规范化偏好、选中维度、精选指标和已验证评论证据。
3. 模型不得创造价格、指标、商品 ID、维度 code 或来源 ID。
4. summary 和 differences 通过零基 claim index 引用统一 claim 列表。
5. snapshot、metric 和 review evidence 必须属于当前 comparison。
6. 每条 claim 至少绑定一个存在且字段/evidence 一致的来源。
7. Python 构造 full_comparison、数据完整度警告和最终报告状态。
8. 缺字段、零评论、低样本或模型 fallback 会生成 partial 报告。
9. report 模型受控失败时保存 error model run，并立即生成确定性基础报告。
10. 成功发布后任务进入 completed/100 或 partially_completed/100。
11. 重复 Worker 复用 version=1；终态不重复创建报告或 claim。

## API

```text
GET /api/v1/comparisons/{comparison_id}/report
```

只返回已发布的 completed/partial 报告：

- summary；
- differences；
- Python 构造的 full_comparison；
- warnings；
- 带来源与置信度的 claims。

## Web

新增：

```text
/comparisons/:id/report
```

报告页面展示：

1. 决策摘要和报告置信度；
2. 分场景建议、主要理由和风险；
3. 关键差异；
4. 商品事实、样本范围和维度指标；
5. claim 来源和置信度。

进度页在 processing<100 时继续轮询，终态提供报告入口。

## 确定性 fallback

report profile 若发生 timeout、供应商错误、无效 JSON 或语义校验失败：

- 不丢失 M1-F 评论、注解和指标；
- `model_runs` 记录受控错误；
- 使用同一 source catalog 构造基础 recommendation 和独立 difference fact claim；
- 增加“报告模型暂不可用”警告；
- 发布 partial 报告并推进 partially_completed/100。

## 边界

- Alembic head 保持 `0006`，业务表保持 16 张。
- 首版固定 version=1，不提供重新生成和版本切换。
- 不实现报告追问、导出、交互图表、鉴权或真实淘宝 Provider。
