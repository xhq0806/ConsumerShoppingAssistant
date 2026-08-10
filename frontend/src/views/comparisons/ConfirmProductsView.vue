<script setup lang="ts">
// M1-C 商品事实与 SKU 确认页面。by AI.Coding

import { computed, onMounted, reactive } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeftOutlined, ArrowRightOutlined, ReloadOutlined } from '@ant-design/icons-vue'
import AppHeader from '@/components/comparisons/AppHeader.vue'
import FlowSteps from '@/components/comparisons/FlowSteps.vue'
import ProductSummary from '@/components/comparisons/ProductSummary.vue'
import { useComparisonStore } from '@/stores/comparison'

const route = useRoute()
const router = useRouter()
const comparisonStore = useComparisonStore()
const selections = reactive<Record<string, string | null | undefined>>({})
const comparisonId = computed(() => String(route.params.id))
const products = computed(() => comparisonStore.comparison?.products ?? [])
const allSelectionsComplete = computed(() =>
  products.value.every((product) =>
    product.skus.length ? Boolean(selections[product.id]) : selections[product.id] === null,
  ),
)

onMounted(loadComparison)

async function loadComparison(): Promise<void> {
  /** 从路由任务 ID 恢复详情并初始化每个商品选择。by AI.Coding */
  try {
    const comparison = await comparisonStore.loadComparison(comparisonId.value)
    if (comparison.status === 'awaiting_dimension_confirmation') {
      await router.replace({ name: 'comparison-preferences', params: { id: comparison.id } })
      return
    }
    for (const product of comparison.products) {
      selections[product.id] =
        product.selected_sku_id ?? (product.skus.length === 0 ? null : undefined)
    }
  } catch {
    // store 持有可展示错误，页面保留重试入口。
  }
}

async function confirmProducts(): Promise<void> {
  /** 提交全部商品选择并进入偏好页面。by AI.Coding */
  if (!allSelectionsComplete.value) {
    return
  }
  try {
    const comparison = await comparisonStore.confirmProducts(comparisonId.value, {
      products: products.value.map((product) => ({
        comparison_product_id: product.id,
        selected_sku_id: selections[product.id] ?? null,
      })),
    })
    await router.push({ name: 'comparison-preferences', params: { id: comparison.id } })
  } catch {
    // 统一错误由 store 暴露。
  }
}

async function restart(): Promise<void> {
  /** 返回输入页创建新任务，不尝试重解析失败终态。by AI.Coding */
  await router.push({ name: 'comparison-input' })
}
</script>

<template>
  <div class="app-frame">
    <AppHeader />
    <FlowSteps :current="1" />

    <main class="workspace">
      <header class="workspace-heading">
        <div>
          <span class="eyebrow">M1-C / T26</span>
          <h1>确认商品与 SKU</h1>
          <p>核对解析结果。所有候选确认完成后，才能继续填写购买偏好。</p>
        </div>
        <a-button type="text" @click="restart"><ArrowLeftOutlined /> 重新创建</a-button>
      </header>

      <a-alert
        v-if="comparisonStore.error"
        class="workspace-alert"
        :description="comparisonStore.error.message"
        :message="comparisonStore.error.code"
        show-icon
        type="error"
      >
        <template #action>
          <a-button size="small" @click="loadComparison"><ReloadOutlined /> 重试</a-button>
        </template>
      </a-alert>

      <a-spin :spinning="comparisonStore.action === 'loading'">
        <section v-if="products.length" class="product-list">
          <ProductSummary
            v-for="product in products"
            :key="product.id"
            v-model:selected-sku-id="selections[product.id]"
            :product="product"
          />
        </section>

        <a-empty
          v-else-if="!comparisonStore.busy && !comparisonStore.error"
          description="没有可确认的商品"
        />
      </a-spin>

      <a-alert
        v-for="warning in comparisonStore.comparison?.warnings ?? []"
        :key="warning.code"
        class="workspace-alert"
        :message="warning.message"
        show-icon
        type="warning"
      />

      <footer v-if="products.length" class="command-bar">
        <div>
          <strong>{{ allSelectionsComplete ? '全部商品已选择' : '仍有商品需要选择 SKU' }}</strong>
          <span>任务 {{ comparisonId }}</span>
        </div>
        <a-button
          :disabled="!allSelectionsComplete"
          :loading="comparisonStore.action === 'confirming'"
          size="large"
          type="primary"
          @click="confirmProducts"
        >
          确认商品并继续
          <ArrowRightOutlined />
        </a-button>
      </footer>
    </main>
  </div>
</template>

<style scoped>
.product-list {
  display: grid;
  gap: 16px;
}

.command-bar {
  position: sticky;
  bottom: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 22px;
  border: 1px solid var(--line-strong);
  background: rgb(255 255 255 / 96%);
  padding: 14px 16px;
  box-shadow: 0 -8px 24px rgb(25 35 32 / 6%);
  gap: 18px;
}

.command-bar > div {
  display: grid;
  min-width: 0;
  gap: 3px;
}

.command-bar strong {
  color: var(--ink);
  font-size: 13px;
}

.command-bar span {
  overflow: hidden;
  color: var(--muted);
  font-family: Consolas, monospace;
  font-size: 10px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (max-width: 640px) {
  .command-bar {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
