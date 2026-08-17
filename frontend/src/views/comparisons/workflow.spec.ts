// M1-C 商品输入与偏好页面主流程测试。by AI.Coding

import Antd from 'ant-design-vue'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  confirmComparisonDimensions,
  createComparison,
  generateComparisonDimensions,
  getComparison,
  getComparisonDimensions,
  parseComparison,
  updateComparisonPreferences,
  type ComparisonDetail,
  type DimensionSet,
} from '@/api/comparisons'
import ConfirmProductsView from './ConfirmProductsView.vue'
import DimensionsView from './DimensionsView.vue'
import InputView from './InputView.vue'
import PreferencesView from './PreferencesView.vue'
import { limitPreferenceItems } from './preferenceLimits'

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
  status: 'awaiting_dimension_confirmation',
  review_window_days: 60,
  progress: 100,
  products: [
    {
      id: 'product-1',
      position: 0,
      platform: 'taobao',
      external_product_id: '10001',
      parse_status: 'needs_confirmation',
      selected_sku_id: 'sku-1',
      latest_snapshot: {
        id: 'snapshot-1',
        title: '星河 X1 合成测试手机',
        image_url: null,
        brand: '星河实验室',
        category: '手机',
        shop_name: '星河合成数据旗舰店',
        price: '3999.00',
        currency: 'CNY',
        specifications: { 存储: '256GB' },
        after_sales: [],
        source_provider: 'fixture',
        source_id: 'product-10001',
        captured_at: '2026-08-07T00:00:00Z',
      },
      skus: [
        {
          id: 'sku-1',
          external_sku_id: 'sku-1',
          name: '蓝色 256GB',
          attributes: { 颜色: '蓝色' },
          price: '3999.00',
          selectable: true,
        },
      ],
    },
  ],
  preferences: {
    budget_min: '3000.00',
    budget_max: '4500.00',
    usage_scenarios: ['日常通勤'],
    priority_concerns: ['续航'],
    deal_breakers: [],
  },
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
      description: '比较候选商品价格。',
    },
    {
      code: 'battery_life',
      name: '续航',
      source_type: 'product_fact',
      selected: true,
      position: 1,
      user_selected: false,
      reason: '匹配用户明确关注点',
      data_risk: 'unavailable',
      has_difference: false,
      affects_recommendation: true,
      user_removable: true,
      description: '比较电池与续航规格。',
    },
    {
      code: 'review_reputation',
      name: '近期评论口碑',
      source_type: 'review_metric',
      selected: false,
      position: null,
      user_selected: false,
      reason: '当前阶段尚无完整数据来源',
      data_risk: 'unavailable',
      has_difference: false,
      affects_recommendation: true,
      user_removable: true,
      description: '后续汇总近期评论。',
    },
  ],
}

beforeEach(() => {
  vi.clearAllMocks()
  localStorage.clear()
  vi.stubGlobal(
    'matchMedia',
    vi.fn().mockReturnValue({
      matches: false,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }),
  )
  vi.stubGlobal(
    'ResizeObserver',
    class {
      /** 提供 Ant Design 测试环境所需的空观察器。by AI.Coding */
      observe(): void {}
      unobserve(): void {}
      disconnect(): void {}
    },
  )
})

describe('M1-C workflow views', () => {
  it('在前端受控标签值中硬限制偏好条目数量', () => {
    expect(limitPreferenceItems(['1', '2', '3', '4', '5', '6'], 5)).toEqual([
      '1',
      '2',
      '3',
      '4',
      '5',
    ])
    expect(limitPreferenceItems('invalid', 5)).toEqual([])
  })

  it('填入 Fixture 链接后创建解析并进入确认页', async () => {
    vi.mocked(createComparison).mockResolvedValue({
      ...comparisonFixture,
      status: 'draft',
      preferences: null,
    })
    vi.mocked(parseComparison).mockResolvedValue({
      ...comparisonFixture,
      status: 'awaiting_product_confirmation',
      preferences: null,
    })
    const router = createTestRouter()
    await router.push('/')
    await router.isReady()
    const wrapper = mount(InputView, {
      global: { plugins: [createPinia(), router, Antd] },
    })

    await findButton(wrapper, '填入合成样本').trigger('click')
    await findButton(wrapper, '创建并解析商品').trigger('click')
    await flushPromises()

    expect(createComparison).toHaveBeenCalledWith(
      {
        product_urls: [
          'https://item.taobao.com/item.htm?id=10001',
          'https://item.taobao.com/item.htm?id=10002',
        ],
        review_window_days: 30,
      },
      expect.any(String),
    )
    expect(router.currentRoute.value.fullPath).toBe('/comparisons/comparison-1/confirm')
  })

  it('恢复已保存偏好并提交后进入维度页', async () => {
    vi.mocked(getComparison).mockResolvedValue(comparisonFixture)
    vi.mocked(updateComparisonPreferences).mockResolvedValue(comparisonFixture)
    const router = createTestRouter()
    await router.push('/comparisons/comparison-1/preferences')
    await router.isReady()
    const wrapper = mount(PreferencesView, {
      global: { plugins: [createPinia(), router, Antd] },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('日常通勤')
    expect(wrapper.text()).toContain('续航')
    await findButton(wrapper, '保存并选择对比维度').trigger('click')
    await flushPromises()

    expect(updateComparisonPreferences).toHaveBeenCalledWith(
      'comparison-1',
      expect.objectContaining({
        review_window_days: 60,
        budget_min: '3000.00',
        budget_max: '4500.00',
        usage_scenarios: ['日常通勤'],
        priority_concerns: ['续航'],
      }),
    )
    expect(router.currentRoute.value.fullPath).toBe('/comparisons/comparison-1/dimensions')
  })

  it('倒置预算只显示表单错误且不提交偏好请求', async () => {
    vi.mocked(getComparison).mockResolvedValue(comparisonFixture)
    const router = createTestRouter()
    await router.push('/comparisons/comparison-1/preferences')
    await router.isReady()
    const wrapper = mount(PreferencesView, {
      global: { plugins: [createPinia(), router, Antd] },
    })
    await flushPromises()

    await wrapper.find('input[placeholder="可选"]').setValue('5000')
    await findButton(wrapper, '保存并选择对比维度').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('预算上限不能低于预算下限')
    expect(updateComparisonPreferences).not.toHaveBeenCalled()
  })

  it('恢复维度后支持删除、添加并按当前顺序确认', async () => {
    vi.mocked(getComparison).mockResolvedValue(comparisonFixture)
    vi.mocked(getComparisonDimensions).mockResolvedValue(dimensionSetFixture)
    vi.mocked(confirmComparisonDimensions).mockResolvedValue({
      ...dimensionSetFixture,
      status: 'queued',
      dimensions: dimensionSetFixture.dimensions.map((dimension, index) => ({
        ...dimension,
        selected: dimension.code !== 'price',
        position: dimension.code === 'price' ? null : index - 1,
      })),
    })
    const router = createTestRouter()
    await router.push('/comparisons/comparison-1/dimensions')
    await router.isReady()
    const wrapper = mount(DimensionsView, {
      global: { plugins: [createPinia(), router, Antd] },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('匹配用户明确关注点')
    await wrapper.find('button[aria-label="删除价格"]').trigger('click')
    await wrapper.find('button[aria-label="添加近期评论口碑"]').trigger('click')
    await findButton(wrapper, '确认维度并进入队列').trigger('click')
    await flushPromises()

    expect(confirmComparisonDimensions).toHaveBeenCalledWith('comparison-1', {
      dimension_codes: ['battery_life', 'review_reputation'],
    })
    expect(wrapper.text()).toContain('任务已进入分析队列边界')
  })
})

function createTestRouter() {
  /** 创建覆盖 M1-D 四个页面的内存路由。by AI.Coding */
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'comparison-input', component: InputView },
      {
        path: '/comparisons/:id/confirm',
        name: 'comparison-confirm',
        component: ConfirmProductsView,
      },
      {
        path: '/comparisons/:id/preferences',
        name: 'comparison-preferences',
        component: PreferencesView,
      },
      {
        path: '/comparisons/:id/dimensions',
        name: 'comparison-dimensions',
        component: DimensionsView,
      },
    ],
  })
}

function findButton(wrapper: ReturnType<typeof mount>, text: string) {
  /** 按用户可见命令文本定位按钮。by AI.Coding */
  const button = wrapper.findAll('button').find((item) => item.text().includes(text))
  if (!button) {
    throw new Error(`未找到按钮：${text}`)
  }
  return button
}
