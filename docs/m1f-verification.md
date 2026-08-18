# M1-F 评论智能注解与指标计算验收

> 验收日期：2026-08-17
> 结论：PASS
> 版本：v0.7.0-m1f

## 验收范围

- LLM 结构化注解、语义校验和 Prompt injection 隔离。
- 每批最多 20 条评论。
- 注解、模型审计和 `partial_result` 分批提交。
- LLM 失败重试与评论断点恢复。
- 商品级和任务级确定性指标重建。
- processing/45 至 processing/75 进度闭环。
- API、Web、PostgreSQL、Alembic 和真实 DeepSeek 联调。

## 自动化结果

| 检查 | 结果 |
|---|---|
| Ruff lint | PASS |
| Ruff format check | PASS |
| mypy strict | PASS，75 个源文件 |
| Backend Pytest | PASS，187 passed |
| PostgreSQL M1-F 集成 | PASS，4 passed |
| Frontend typecheck | PASS |
| Frontend Vitest | PASS，13 passed |
| Frontend production build | PASS |
| Docker Compose config | PASS |
| Alembic head/check | PASS，head=`0006` |

## 真实 DeepSeek

使用根目录本地 `.env` 中已配置的 DeepSeek analysis profile 重建 API/Worker/Web，并创建新的
Fixture 对比任务：

```text
comparison_id=abfa0d7c-1f99-4cfd-8076-bb207b3f3714
status=processing
progress=75
stage=metrics_ready
fetched_review_count=3
valid_review_count=2
annotated_review_count=1
annotation_count=2
metric_count=54
polling_complete=true
```

本次选择 `camera`、`heating`、`review_reputation`，证明真实模型调用可返回多维结构化注解。
API Key、Prompt、评论正文、模型响应和 reasoning content 均未进入验收输出或模型审计。

## 失败与恢复

PostgreSQL 集成测试模拟 `LLM_TIMEOUT`：

- `raw_reviews` 保持 2 条；
- 失败 `model_runs` 安全记录错误码；
- progress 保持 45 且 `can_retry=true`；
- retry 后不重新调用 Commerce Provider；
- 从已保存评论继续并完成 144 条 Fake 确定性指标。

重复 Worker 消息不会重复创建注解或指标。

## 浏览器

- 桌面：1440×900，六阶段、75% 进度和六项统计完整可见。
- 移动：390×844，`innerWidth=390`、document/body `scrollWidth=390`，无横向溢出。
- 页面刷新通过任务 ID 恢复 `metrics_ready`。

桌面证据：

```text
docs/assets/m1f-progress-desktop.png
```

## 已知非阻断项

- Ant Design Vue 全局导入使主 chunk 约 1.53 MB，构建继续给出 chunk size warning。
- M1-F 只准备注解和指标；报告生成、购买建议与完成状态由 M1-G 实现。
