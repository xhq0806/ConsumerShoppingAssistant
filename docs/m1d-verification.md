# M1-D 动态维度推荐与维度确认闭环验收报告

> 验收日期：2026-08-11
> 版本：v0.5.0-m1d
> 结论：PASS

## 验收范围

- `0006` 受控通用/Fixture 手机维度数据迁移；
- 基于用户关注点、商品差异和数据完整度的确定性推荐；
- 候选生成、查询和确认 API；
- `task_dimensions` 全候选持久化、顺序调整和刷新恢复；
- 动态维度确认页面；
- 确认后经 `ready_for_analysis` 推进到 `queued`；
- 桌面和移动端真实浏览器流程。

不验收评论分析、品牌采集、Celery/LangGraph Worker、进度页、报告、鉴权、真实淘宝或真实
LLM Provider。

## 自动化门禁

标准命令：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\verify-local.ps1
```

| 检查 | 结果 |
|---|---|
| Ruff lint | PASS |
| Ruff format check | PASS，97 个文件 |
| mypy strict | PASS，66 个源文件 |
| Pytest | PASS，157 passed |
| 前端 typecheck | PASS |
| 前端 Vitest | PASS，3 个文件、10 passed |
| 前端 production build | PASS |
| Docker Compose config | PASS |
| Alembic upgrade/check/downgrade | PASS，head=`0006` |
| API readiness | PASS，HTTP 200 |

前端主 chunk 约 1.53 MB，仍有既存的非阻断 chunk size 警告。

## 浏览器流程

在全新 PostgreSQL 16 数据卷中完成：

1. 填入 Fixture `10001`、`10002` 并创建解析任务。
2. 选择 `10001` 的 256GB SKU，确认两个商品。
3. 保存预算 3000～4500、使用场景“日常通勤”、关注点“续航”“拍照”。
4. 生成 16 个候选，默认选中 8 个；续航和拍照置顶。
5. 刷新页面后从服务端恢复候选和顺序。
6. 将拍照上移、删除价格、添加近期评论口碑。
7. 确认后任务进入 queued，全部编辑控件锁定。
8. 浏览器控制台为 0 errors、0 warnings；API 流程全部返回 2xx。

## 响应式验收

| 视口 | 结果 |
|---|---|
| `1440x900` | PASS |
| `390x844` | PASS，`scrollWidth=390`，无横向溢出 |

截图：

- `docs/assets/m1d-dimensions-desktop.png`
- `docs/assets/m1d-dimensions-mobile.png`

## 环境 Concern

原 Compose 项目的历史 PostgreSQL 卷被标记为 Alembic `0005`，但实际缺少 `0003` 应有的
`dimension_definitions.config` 列，属于本地旧卷 Schema 漂移。验收未删除或修改该旧卷，
而是使用独立 Compose 项目 `consumer-shopping-assistant-m1d` 和全新卷完成迁移及浏览器
验证。全新数据库的 `0001 -> 0006`、downgrade 和 re-upgrade 均通过。

使用旧卷的开发者应先备份并检查 Schema；确认不需要旧数据后再自行重建卷。
