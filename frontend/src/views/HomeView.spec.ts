import { mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { describe, expect, it } from 'vitest'
import HomeView from './HomeView.vue'

describe('HomeView', () => {
  it('展示 M0 和 Fixture 限制', () => {
    const wrapper = mount(HomeView, {
      global: { plugins: [createPinia()] },
    })
    expect(wrapper.text()).toContain('M0')
    expect(wrapper.text()).toContain('Fixture')
    expect(wrapper.text()).toContain('尚未开放真实淘宝数据分析')
  })
})
