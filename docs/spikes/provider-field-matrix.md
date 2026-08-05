# Provider 字段覆盖矩阵

> 当前结论：真实淘宝数据源 **blocked**；`fixture` 一列表示 M0 合成测试能力，不代表生产字段可得。

| 内部规范字段 | M0 DTO | Fixture | 正式来源字段 | 可得性 | 授权前提 | 刷新语义 | 30/60 天 | SKU 粒度 | 脱敏/保留限制 | 缺失降级 |
|---|---|---:|---|---|---|---|---|---|---|---|
| 规范化 URL | `NormalizedProductUrl.canonical_url` | 是 | 待核验 | blocked | 正式域名与接口许可 | 请求时 | 不适用 | 商品 | 不记录原始 query | 拒绝不安全 URL |
| 外部商品 ID | `external_product_id` | 是 | 待核验 | blocked | 商品接口权限 | 请求时 | 不适用 | 商品 | 非个人信息 | 无 ID 则解析失败 |
| 标题 | `ProductDTO.title` | 是 | 待核验 | blocked | 商品字段权限 | 采集时快照 | 不适用 | 商品 | 按条款保留 | 标记缺失 |
| 图片 | `image_url` | 是/可缺失 | 待核验 | blocked | 图片使用与展示许可 | 采集时快照 | 不适用 | 商品/SKU | 不下载原图，优先保存引用 | 隐藏图片 |
| 品牌 | `brand` | 是/可缺失 | 待核验 | blocked | 商品字段权限 | 采集时快照 | 不适用 | 商品 | 记录来源 | 显示未知 |
| 类目 | `category` | 是 | 待核验 | blocked | 类目字段权限 | 采集时快照 | 不适用 | 商品 | 记录来源 | 要求人工确认 |
| 当前价格 | `price` | 是 | 待核验 | blocked | 价格字段权限 | 明确采集时间 | 不适用 | 商品/SKU | 只作为时点事实 | 标记缺失，不推断 |
| SKU | `SkuDTO` | 是 | 待核验 | blocked | SKU 接口权限 | 采集时快照 | 不适用 | SKU | 不存用户订单信息 | 要求用户确认或降级 |
| 店铺 | `shop_name` | 是 | 待核验 | blocked | 店铺字段权限 | 采集时快照 | 不适用 | 商品 | 不扩展采集联系人信息 | 标记缺失 |
| 售后信息 | `after_sales` | 是/可缺失 | 待核验 | blocked | 售后字段权限 | 采集时快照 | 不适用 | 商品/SKU | 仅保存展示事实 | 标记缺失 |
| 评分/销量/热度 | 后续事实 DTO | 尚未加入 | 待核验 | blocked | 对应字段权限 | 明确采集时间 | 不适用 | 商品/SKU | 不作为历史趋势 | 不展示 |
| 评论 ID | `external_review_id` | 是 | 待核验 | blocked | 评论接口与处理许可 | 获取时 | 待核验 | 商品/SKU | 需确认是否允许持久化 | 无 ID 时采用不可逆内部指纹或拒绝 |
| 评论时间 | `created_at` | 是 | 待核验 | blocked | 评论接口权限 | 原始时间 | 待核验 | 商品/SKU | 按保留策略处理 | 无法进入时间窗统计 |
| 评论正文 | `content` | 合成文本 | 待核验 | blocked | 模型分析、存储、展示许可 | 原始文本 | 待核验 | 待核验 | 发送模型前去除昵称、手机号、地址等；默认原文 30 天 | 不输出评论口碑结论 |
| 评论评分 | `rating` | 是/可缺失 | 待核验 | blocked | 评论字段权限 | 原始值 | 待核验 | 商品/SKU | 聚合后展示 | 标记缺失 |
| 评论 SKU 文本 | `sku_text` | 是/可缺失 | 待核验 | blocked | 评论-SKU 关联许可 | 原始值 | 待核验 | 待核验 | 不包含订单或身份字段 | 仅做商品级分析 |
| 实际覆盖范围 | `actual_start_at/end_at` | 是 | 由结果计算 | blocked | 评论数据可得 | 每次任务 | 待核验 | 商品 | 始终展示实际范围 | 标记未知 |
| 来源引用 | `SourceReference` | 是 | 待核验 | blocked | 来源标识可保存 | 每次获取 | 不适用 | 字段/记录 | 不含凭据 | 无来源不得形成关键 claim |
| 未授权 | Provider error | 可模拟 | 待核验 | blocked | 无 | 请求时 | 不适用 | 不适用 | 不记录原始响应 | 停止并提示未授权 |
| 限流 | Provider error | 可模拟 | 待核验 | blocked | 配额说明 | 请求时 | 不适用 | 不适用 | 只记错误码与 trace ID | 有限重试/降级 |
| 暂时不可用 | Provider error | 可模拟 | 待核验 | blocked | SLA 说明 | 请求时 | 不适用 | 不适用 | 不记录敏感响应 | 重试后降级 |
| 字段不支持 | missing/warning | 可模拟 | 待核验 | blocked | 字段清单 | 版本变化时 | 待核验 | 待核验 | 记录版本 | 显式缺失，不由 LLM 补全 |

## 统一错误分类

未来真实 Provider 至少映射为：`not_authorized`、`not_found`、`rate_limited`、`temporarily_unavailable`、`invalid_response`、`field_unsupported`。上游原始响应正文、Cookie、Authorization 和签名参数不得进入 API 响应或日志。
