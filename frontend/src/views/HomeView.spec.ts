import { mount } from '@vue/test-utils'
import { createPinia } from 'pinia'
import { describe, expect, it } from 'vitest'
import HomeView from './HomeView.vue'

describe('HomeView', () => {
  it('展示 M1-B 后端基线和 Fixture 限制', () => {
    const wrapper = mount(HomeView, {
      global: {
        plugins: [createPinia()],
        stubs: {
          'a-card': { template: '<div><slot /></div>' },
          'a-space': { template: '<div><slot /></div>' },
          'a-tag': { template: '<span><slot /></span>' },
          'a-typography-title': { template: '<h1><slot /></h1>' },
          'a-typography-paragraph': { template: '<p><slot /></p>' },
        },
      },
    })
    expect(wrapper.text()).toContain('M1-B')
    expect(wrapper.text()).toContain('Fixture')
    expect(wrapper.text()).toContain('真实淘宝数据分析尚未开放')
  })
})
