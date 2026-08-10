// M1-C Comparison API 契约与端点函数。by AI.Coding

import { requestJson } from './request'

const COMPARISON_API = '/api/v1/comparisons'

export interface UserPreferences {
  budget_min: string | null
  budget_max: string | null
  usage_scenarios: string[]
  priority_concerns: string[]
  deal_breakers: string[]
}

export interface ProductSku {
  id: string
  external_sku_id: string
  name: string
  attributes: Record<string, string>
  price: string | null
  selectable: boolean
}

export interface ProductSnapshot {
  id: string
  title: string
  image_url: string | null
  brand: string | null
  category: string | null
  shop_name: string | null
  price: string | null
  currency: string
  specifications: Record<string, string>
  after_sales: string[]
  source_provider: string
  source_id: string
  captured_at: string
}

export interface ComparisonProduct {
  id: string
  position: number
  platform: string
  external_product_id: string
  parse_status: string
  selected_sku_id: string | null
  latest_snapshot: ProductSnapshot | null
  skus: ProductSku[]
}

export interface TaskEvent {
  id: string
  stage: string
  event_type: string
  progress: number | null
  message: string | null
  details: Record<string, unknown>
  created_at: string
}

export interface ComparabilityWarning {
  code: string
  message: string
}

export interface ComparisonDetail {
  id: string
  status: string
  review_window_days: number
  progress: number
  products: ComparisonProduct[]
  preferences: UserPreferences | null
  events: TaskEvent[]
  warnings: ComparabilityWarning[]
}

export interface CreateComparisonPayload {
  product_urls: string[]
  review_window_days: 30 | 60
}

export interface ConfirmProductsPayload {
  products: Array<{
    comparison_product_id: string
    selected_sku_id: string | null
  }>
}

export interface UpdatePreferencesPayload {
  review_window_days: 30 | 60
  budget_min: string | null
  budget_max: string | null
  usage_scenarios: string[]
  priority_concerns: string[]
  deal_breakers: string[]
}

export function createComparison(
  payload: CreateComparisonPayload,
  idempotencyKey: string,
): Promise<ComparisonDetail> {
  /** 创建对比草稿并传递不落地浏览器存储的单次幂等键。by AI.Coding */
  return requestJson<ComparisonDetail>(COMPARISON_API, {
    method: 'POST',
    headers: { 'Idempotency-Key': idempotencyKey },
    body: JSON.stringify(payload),
  })
}

export function parseComparison(comparisonId: string): Promise<ComparisonDetail> {
  /** 同步触发 Fixture 商品解析。by AI.Coding */
  return requestJson<ComparisonDetail>(`${COMPARISON_API}/${comparisonId}/parse`, {
    method: 'POST',
  })
}

export function getComparison(comparisonId: string): Promise<ComparisonDetail> {
  /** 按任务 ID 恢复服务端聚合详情。by AI.Coding */
  return requestJson<ComparisonDetail>(`${COMPARISON_API}/${comparisonId}`)
}

export function confirmComparisonProducts(
  comparisonId: string,
  payload: ConfirmProductsPayload,
): Promise<ComparisonDetail> {
  /** 原子提交任务内全部商品和 SKU 选择。by AI.Coding */
  return requestJson<ComparisonDetail>(`${COMPARISON_API}/${comparisonId}/confirm-products`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function updateComparisonPreferences(
  comparisonId: string,
  payload: UpdatePreferencesPayload,
): Promise<ComparisonDetail> {
  /** 整体替换评论窗口和规范化用户偏好。by AI.Coding */
  return requestJson<ComparisonDetail>(`${COMPARISON_API}/${comparisonId}/preferences`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}
