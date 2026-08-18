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

export type DimensionDataRisk = 'available' | 'partial' | 'unavailable'

export interface DimensionRecommendation {
  code: string
  name: string
  source_type: string
  selected: boolean
  position: number | null
  user_selected: boolean
  reason: string
  data_risk: DimensionDataRisk
  has_difference: boolean
  affects_recommendation: boolean
  user_removable: boolean
  description: string
}

export interface DimensionSet {
  comparison_id: string
  status: string
  category: string | null
  generated: boolean
  dimensions: DimensionRecommendation[]
}

export interface AnalysisProgress {
  comparison_id: string
  status: string
  progress: number
  stage: string
  message: string
  fetched_review_count: number
  valid_review_count: number
  annotated_review_count: number
  annotation_count: number
  metric_count: number
  can_retry: boolean
  polling_complete: boolean
}

export type ReportClaimType =
  | 'fact'
  | 'advantage'
  | 'disadvantage'
  | 'recommendation'
  | 'warning'

export interface ReportSourceRef {
  type: 'product_snapshot' | 'brand_source' | 'analysis_metric' | 'raw_review'
  id: string
  field?: string
  evidence?: string
}

export interface ReportClaim {
  id: string
  claim_type: ReportClaimType
  text: string
  source_refs: ReportSourceRef[]
  confidence: number | null
  display_order: number
}

export interface ReportScenarioRecommendation {
  scenario: string
  product_id: string | null
  claim_index: number
}

export interface ReportSummary {
  headline: string
  recommended_product_id: string | null
  recommendation_claim_index: number
  scenario_recommendations: ReportScenarioRecommendation[]
  key_reason_claim_indexes: number[]
  risk_claim_indexes: number[]
  confidence: number
}

export interface ReportDifference {
  dimension_code: string
  dimension_name: string
  claim_index: number
}

export interface ReportMetric {
  id: string
  dimension_code: string
  metric_type: string
  numeric_value: string | null
  sample_size: number
  confidence: number | null
}

export interface ReportProduct {
  id: string
  title: string
  category: string | null
  brand: string | null
  shop_name: string | null
  price: string | null
  currency: string
  specifications: Record<string, string>
  after_sales: string[]
  review_count: number
  metrics: ReportMetric[]
}

export interface ReportDimension {
  id: string
  code: string
  name: string
  min_sample_size: number
}

export interface ReportFullComparison {
  products: ReportProduct[]
  dimensions: ReportDimension[]
  task_metrics: ReportMetric[]
  evidence_count: number
}

export interface ComparisonReport {
  id: string
  comparison_id: string
  version: number
  status: 'completed' | 'partial'
  summary: ReportSummary
  differences: ReportDifference[]
  full_comparison: ReportFullComparison
  warnings: string[]
  generated_at: string
  claims: ReportClaim[]
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

export interface ConfirmDimensionsPayload {
  dimension_codes: string[]
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

export function generateComparisonDimensions(comparisonId: string): Promise<DimensionSet> {
  /** 首次生成并持久化任务动态维度候选。by AI.Coding */
  return requestJson<DimensionSet>(
    `${COMPARISON_API}/${comparisonId}/dimensions/recommendations`,
    { method: 'POST' },
  )
}

export function getComparisonDimensions(comparisonId: string): Promise<DimensionSet> {
  /** 查询服务端持久化的重点和其他可选维度。by AI.Coding */
  return requestJson<DimensionSet>(`${COMPARISON_API}/${comparisonId}/dimensions`)
}

export function confirmComparisonDimensions(
  comparisonId: string,
  payload: ConfirmDimensionsPayload,
): Promise<DimensionSet> {
  /** 按用户当前顺序整体确认维度并进入 queued 边界。by AI.Coding */
  return requestJson<DimensionSet>(`${COMPARISON_API}/${comparisonId}/dimensions/confirm`, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function startComparisonAnalysis(comparisonId: string): Promise<AnalysisProgress> {
  /** 投递 queued 分析任务或返回当前持久化进度。by AI.Coding */
  return requestJson<AnalysisProgress>(`${COMPARISON_API}/${comparisonId}/analysis/start`, {
    method: 'POST',
  })
}

export function retryComparisonAnalysis(comparisonId: string): Promise<AnalysisProgress> {
  /** 重新投递可重试的评论采集失败。by AI.Coding */
  return requestJson<AnalysisProgress>(`${COMPARISON_API}/${comparisonId}/analysis/retry`, {
    method: 'POST',
  })
}

export function getComparisonAnalysisProgress(
  comparisonId: string,
): Promise<AnalysisProgress> {
  /** 查询异步评论采集的服务端持久化进度。by AI.Coding */
  return requestJson<AnalysisProgress>(
    `${COMPARISON_API}/${comparisonId}/analysis/progress`,
  )
}

export function getComparisonReport(comparisonId: string): Promise<ComparisonReport> {
  /** 查询任务最新已发布的完整或降级报告。by AI.Coding */
  return requestJson<ComparisonReport>(`${COMPARISON_API}/${comparisonId}/report`)
}
