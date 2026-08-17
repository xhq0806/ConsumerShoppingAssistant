# DeepSeek LLM 配置与 Adapter

> 归档日期：2026-08-17
> 版本：v0.6.1-deepseek-config

## 功能描述

项目在供应商中立 `LLMGateway` 后新增 DeepSeek Chat Completions Adapter。默认 Provider
仍为 `fake`；只有本地配置 `LLM_PROVIDER=deepseek` 和非空 API Key 时才创建 DeepSeek
客户端。当前 Adapter 尚未接入 M1-E 评论流程，供后续评论注解和报告生成使用。

## 配置 Profile

| Profile | 默认模型 | Thinking | 用途 |
|---|---|---|---|
| `analysis` | `deepseek-v4-flash` | disabled | 评论主题、情感和证据结构化提取 |
| `report` | `deepseek-v4-pro` | enabled/high | 综合购买建议和风险解释 |

公共配置包括 API Key、HTTPS base URL、超时和最大重试；两个 profile 分别配置模型、
thinking 和 max tokens。

## 核心行为

- 调用 `/chat/completions`，不使用 Responses API。
- 使用非流式 `response_format={"type":"json_object"}`。
- 自动添加仅输出 JSON 对象的系统约束。
- 最终内容继续由调用方 Pydantic response model 校验。
- 空 content、无效 JSON 和结构校验失败按 Gateway 规则重试。
- 400/422、401/403 和 402 不重试；429、5xx、连接错误和超时使用受控错误。
- `reasoning_content` 不进入业务结果或审计。
- API Key 使用 `SecretStr`，不进入 repr、日志、异常和审计。
- 当前只支持 System/Human/AI 纯文本消息，不支持工具和多模态消息。

## 关键代码

| 路径 | 职责 |
|---|---|
| `backend/src/app/core/config.py` | DeepSeek 配置和条件式凭据校验 |
| `backend/src/app/providers/llm/deepseek.py` | 原生 httpx ChatModel Adapter |
| `backend/src/app/providers/llm/factory.py` | Fake/DeepSeek 和 profile 工厂 |
| `backend/src/app/providers/llm/gateway.py` | 结构化校验、重试和审计 |
| `backend/src/app/providers/llm/deepseek_smoke.py` | Key 配置后的最小连通性检查 |
| `backend/tests/contract/llm/test_deepseek_adapter.py` | HTTP、thinking、usage、错误和脱敏契约 |

## 安全边界

- `.env` 和 API Key 不提交仓库。
- Prompt、评论、响应正文和思考正文不写入审计。
- 统计数字仍由确定性 Python 程序计算。
- 真实模型调用未接入评论采集 Worker，配置 Key 本身不会启动模型分析。
