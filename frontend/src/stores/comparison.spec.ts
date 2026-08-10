// M1-C 对比工作流 Pinia store 行为测试。by AI.Coding

import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  confirmComparisonProducts,
  createComparison,
  getComparison,
  parseComparison,
  updateComparisonPreferences,
  type ComparisonDetail,
} from '@/api/comparisons'
import { useComparisonStore } from './comparison'

vi.mock('@/api/comparisons', () => ({
  createComparison: vi.fn(),
  parseComparison: vi.fn(),
  getComparison: vi.fn(),
  confirmComparisonProducts: vi.fn(),
  updateComparisonPreferences: vi.fn(),
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
})
