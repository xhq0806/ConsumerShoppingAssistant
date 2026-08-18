# M1-G 报告生成与任务完成闭环验收

> 验收日期：2026-08-18
> 结论：PASS
> 版本：v0.8.0-m1g

## 验收范围

- report profile 结构化调用与脱敏审计。
- claim source catalog 和当前 comparison 归属校验。
- version=1 报告占位、发布和重复 Worker 幂等。
- Python full comparison、数据警告和 partial 判定。
- report 模型失败后的确定性基础报告。
- completed/partially_completed 任务终态。
- 报告查询 API、进度入口和六步前端流程。

## 自动化结果

| 检查 | 结果 |
|---|---|
| Ruff lint | PASS |
| Ruff format check | PASS |
| mypy strict | PASS，77 个源文件 |
| Backend Pytest | PASS，195 passed |
| M1-G PostgreSQL 集成 | PASS，3 passed |
| Frontend typecheck | PASS |
| Frontend Vitest | PASS，15 passed |
| Frontend production build | PASS |
| Docker Compose config | PASS |
| Alembic head/check | PASS，head=`0006` |

## 真实 DeepSeek 与 fallback

真实 DeepSeek V4 Pro report profile 已执行：

- 60 秒配置：返回前超时，审计 `LLM_TIMEOUT`；
- 120 秒配置：约 109.6 秒返回，但未通过结构化契约，审计
  `LLM_STRUCTURED_OUTPUT_INVALID`；
- 两种情况均未保存 Prompt、响应正文或 reasoning content。

M1-G 随后使用同一受控 source catalog 生成确定性基础报告并完成任务，证明外部解释模型不可用
时任务不会永久失败。

最终中文验收任务：

```text
comparison_id=9a5cbc02-403c-4e60-85bc-0b978993774c
status=partially_completed
progress=100
report_status=partial
report_version=1
claim_count=2
difference_count=1
warning_count=3
scenario_count=1
```

报告包含独立的 recommendation claim 和 price difference fact claim；两者均引用当前任务两个
商品快照的 `price` 字段。

## 数据安全

- 应用层拒绝任务外商品、未知维度、越界 claim index 和目录外来源。
- PostgreSQL 集成测试证明另一个 comparison 的 snapshot UUID 无法通过发布门禁。
- 模型失败只记录 provider/model/token/时延/状态/错误码，不记录正文。
- full comparison 数值全部来自数据库，不来自模型输出。

## 浏览器

- 桌面：1440×900，四层报告和证据列表完整可见。
- 移动：390×844，document/body `scrollWidth=390`，无页面横向溢出。
- 中文“日常通勤”、价格差异、partial 警告和来源标签显示正确。

证据：

```text
docs/assets/m1g-report-desktop.png
docs/assets/m1g-report-mobile.png
```

## 已知非阻断项

- 当前 V4 Pro high thinking 在本地真实调用中尚未通过完整结构化报告契约，系统使用 partial
  fallback 保证业务闭环。
- Ant Design Vue 全局导入使主 chunk 约 1.53 MB，仍为非阻断构建警告。
- 报告追问、重新生成、多版本切换和导出留给后续里程碑。
