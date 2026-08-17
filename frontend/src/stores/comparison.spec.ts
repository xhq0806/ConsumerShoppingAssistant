// M1-C 对比工作流 Pinia store 行为测试。by AI.Coding

import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  confirmComparisonDimensions,
  confirmComparisonProducts,
  createComparison,
  generateComparisonDimensions,
  getComparison,
  getComparisonDimensions,
  parseComparison,
  updateComparisonPreferences,
  type ComparisonDetail,
  type DimensionSet,
} from '@/api/comparisons'
import { useComparisonStore } from './comparison'

vi.mock('@/api/comparisons', () => ({
  createComparison: vi.fn(),
  parseComparison: vi.fn(),
  getComparison: vi.fn(),
  confirmComparisonProducts: vi.fn(),
  updateComparisonPreferences: vi.fn(),
  generateComparisonDimensions: vi.fn(),
  getComparisonDimensions: vi.fn(),
  confirmComparisonDimensions: vi.fn(),
}))

const comparisonFixture: ComparisonDetail = {
  id: 'comparison-1',
  status: 'draft',
  review_window_days: 30,
  progress: 0,
  products: [],
  preferences: null,
  events: [],
  warnings: [],
}

const dimensionSetFixture: DimensionSet = {
  comparison_id: 'comparison-1',
  status: 'awaiting_dimension_confirmation',
  category: '手机',
  generated: true,
  dimensions: [
    {
      code: 'price',
      name: '价格',
      source_type: 'product_fact',
      selected: true,
      position: 0,
      user_selected: false,
      reason: '候选商品在该维度存在差异',
      data_risk: 'available',
      has_difference: true,
      affects_recommendation: true,
      user_removable: true,
      description: '比较价格。',
    },
  ],
}

describe('useComparisonStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.clearAllMocks()
  })

  it('创建后解析任务并保存可恢复的任务 ID', async () => {
    vi.mocked(createComparison).mockResolvedValue(comparisonFixture)
    vi.mocked(parseComparison).mockResolvedValue({
      ...comparisonFixture,
      status: 'awaiting_product_confirmation',
      progress: 100,
    })
    const store = useComparisonStore()

    const result = await store.createAndParse({
      product_urls: ['https://item.taobao.com/item.htm?id=10001', 'https://item.taobao.com/item.htm?id=10002'],
      review_window_days: 30,
    })

    expect(result.status).toBe('awaiting_product_confirmation')
    expect(store.comparison?.id).toBe('comparison-1')
    expect(store.lastComparisonId).toBe('comparison-1')
    expect(localStorage.getItem('shopping-assistant:last-comparison-id')).toBe('comparison-1')
  })

  it('通过任务 ID 恢复、确认商品并保存偏好', async () => {
    vi.mocked(getComparison).mockResolvedValue({
      ...comparisonFixture,
      status: 'awaiting_product_confirmation',
    })
    vi.mocked(confirmComparisonProducts).mockResolvedValue({
      ...comparisonFixture,
      status: 'awaiting_dimension_confirmation',
    })
    vi.mocked(updateComparisonPreferences).mockResolvedValue({
      ...comparisonFixture,
      status: 'awaiting_dimension_confirmation',
      review_window_days: 60,
      preferences: {
        budget_min: '3000.00',
        budget_max: '4500.00',
        usage_scenarios: ['日常通勤'],
        priority_concerns: ['续航'],
        deal_breakers: [],
      },
    })
    const store = useComparisonStore()

    await store.loadComparison('comparison-1')
    await store.confirmProducts('comparison-1', {
      products: [
        { comparison_product_id: 'product-1', selected_sku_id: 'sku-1' },
        { comparison_product_id: 'product-2', selected_sku_id: null },
      ],
    })
    await store.savePreferences('comparison-1', {
      review_window_days: 60,
      budget_min: '3000.00',
      budget_max: '4500.00',
      usage_scenarios: ['日常通勤'],
      priority_concerns: ['续航'],
      deal_breakers: [],
    })

    expect(store.comparison?.preferences?.budget_max).toBe('4500.00')
    expect(store.comparison?.review_window_days).toBe(60)
  })

  it('生成、恢复并确认有序维度集合', async () => {
    vi.mocked(generateComparisonDimensions).mockResolvedValue(dimensionSetFixture)
    vi.mocked(getComparisonDimensions).mockResolvedValue(dimensionSetFixture)
    vi.mocked(confirmComparisonDimensions).mockResolvedValue({
      ...dimensionSetFixture,
      status: 'queued',
    })
    const store = useComparisonStore()

    await store.generateDimensions('comparison-1')
    await store.loadDimensions('comparison-1')
    await store.confirmDimensions('comparison-1', { dimension_codes: ['price'] })

    expect(confirmComparisonDimensions).toHaveBeenCalledWith('comparison-1', {
      dimension_codes: ['price'],
    })
    expect(store.dimensionSet?.status).toBe('queued')
  })
})
