import { createRouter, createWebHistory } from 'vue-router'

export default createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'comparison-input',
      component: () => import('@/views/comparisons/InputView.vue'),
    },
    {
      path: '/comparisons/:id/confirm',
      name: 'comparison-confirm',
      component: () => import('@/views/comparisons/ConfirmProductsView.vue'),
    },
    {
      path: '/comparisons/:id/preferences',
      name: 'comparison-preferences',
      component: () => import('@/views/comparisons/PreferencesView.vue'),
    },
    {
      path: '/comparisons/:id/dimensions',
      name: 'comparison-dimensions',
      component: () => import('@/views/comparisons/DimensionsView.vue'),
    },
    {
      path: '/comparisons/:id/progress',
      name: 'comparison-progress',
      component: () => import('@/views/comparisons/ProgressView.vue'),
    },
  ],
})
