# M1-C 商品输入与用户偏好闭环验收报告

> 验收日期：2026-08-10
> 版本：v0.4.0-m1c
> 原始规格：`changes/archive/2026-08-10-m1c-shopping-input-preferences/spec.md`
> 结论：**PASS**

## 验收范围

本次验收覆盖 T26 商品输入与确认前端、T13 用户偏好，包括：

- 根页面 2～3 个 Fixture 商品链接输入和 30/60 天评论窗口；
- 创建、解析、商品事实展示、SKU 选择和三步路由推进；
- 路由任务 ID 驱动的确认页与偏好页刷新恢复；
- 偏好领域规范化、PUT API、JSONB 持久化和脱敏事件；
- 预算、使用场景、关注点和禁忌项表单；
- Vite/Nginx `/api` 代理、SPA fallback 和本地占位图片；
- 桌面端、移动端真实浏览器流程和本地完整质量门禁。

不验收用户鉴权、动态维度、评论获取与分析、Celery/LangGraph 业务编排、报告、真实淘宝
Provider 或真实 LLM Provider。

## 本地验收证据

本项目为个人项目，不以远端 CI 运行记录作为验收前提。以下门禁于 2026-08-10 在本地
Windows、Python 3.12.13、Node.js 22 和 Docker Desktop/PostgreSQL 16 环境执行。

| 检查 | 结果 |
|---|---|
| Ruff lint | PASS |
| Ruff format check | PASS，93 个文件 |
| mypy strict | PASS，65 个源文件 |
| Pytest 完整套件 | PASS，149 passed |
| 前端 typecheck | PASS |
| 前端 Vitest | PASS，3 个文件、8 passed |
| 前端 production build | PASS |
| Docker Compose config | PASS |
| API readiness | PASS，HTTP 200 |
| Compose 五服务 | PASS，PostgreSQL/Redis healthy |

标准本地门禁：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/verify-local.ps1
```

## 浏览器验收

使用本地 Compose Web 与 API 完成真实流程：

1. 两个 Fixture 商品已创建、解析并完成 SKU 确认。
2. 偏好页填写预算 `3000.00`～`4500.00`、场景“通勤拍照”、关注点“续航稳定”和禁忌项
   “频繁卡顿”。
3. 保存后页面显示“偏好已保存”。
4. 重新加载深层路由后，全部预算和文本字段从服务端恢复。
5. 桌面端 `1440x900` 和移动端 `390x844` 的 `scrollWidth` 均等于 viewport 宽度，无横向溢出。
6. 桌面端和移动端页面未发现元素遮挡或文字溢出，浏览器控制台错误和警告均为 0。
7. 倒置预算会显示“预算上限不能低于预算下限”，不会发出保存请求或产生未捕获控制台错误。
8. Comparison API 返回 503 时页面显示受控错误提示；移除故障模拟后重新加载即可恢复服务端数据。

验收截图：

- [桌面端偏好页](assets/m1c-preferences-desktop.png)
- [移动端偏好页](assets/m1c-preferences-mobile.png)

## 已验证行为

- 偏好请求只允许完整白名单结构，额外字段被拒绝。
- 金额使用 Decimal 规范化，上限低于下限时拒绝。
- 文本执行 NFKC、trim、去重、长度和条目数量校验。
- 前端受控标签值会在 5/8/8 项上限处截断，表单规则和后端领域规则继续提供双重校验。
- 只有 `awaiting_dimension_confirmation` 状态允许保存偏好。
- 相同偏好重复提交保持幂等，不重复写入敏感正文。
- 详情响应包含规范化偏好，页面刷新不依赖 Pinia 内存状态。
- Vite 与 Nginx 均可通过相对 `/api` 完成请求；深层 SPA 路由可直接刷新。
- 无效 Fixture 图片使用本地占位视觉，不再发起 `.invalid` 图片网络请求。
- API 在领域规范化之后执行文本长度、去重后数量校验，不会误拒绝可折叠空白和重复项。
- PostgreSQL 集成测试逐字段断言偏好事件的 stage、type、message 和脱敏 details 白名单。

## 已知限制

- API 和任务页面没有用户身份、任务归属或匿名访问凭证，只能用于本地开发。
- 商品解析仍同步使用 Fixture，不代表真实 Provider 的性能、字段覆盖和可用性。
- 非目标状态保存和解析失败主要由 API、领域与数据库自动化测试覆盖，未逐项手工构造浏览器场景。
- 前端生产构建主 chunk 约 1.53 MB，构建成功但仍有大 chunk 警告；后续应继续按需导入
  Ant Design Vue 和拆分共享依赖。
- M1-C 保存偏好后停留在维度确认阶段，动态维度与分析启动属于下一里程碑。

## 最终结论

**PASS**

M1-C 的 T26 商品输入与确认前端、T13 用户偏好后端和前端闭环均满足规格。后端、前端、
Compose 和浏览器行为已通过本地验收，可以归档并进入动态维度与维度确认开发。
