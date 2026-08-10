<script setup lang="ts">
// M1-C 商品事实、缺失状态和 SKU 选择组件。by AI.Coding

import { computed, ref, watch } from 'vue'
import { MobileOutlined, ShopOutlined } from '@ant-design/icons-vue'
import type { ComparisonProduct } from '@/api/comparisons'

const props = defineProps<{
  product: ComparisonProduct
  selectedSkuId: string | null | undefined
  disabled?: boolean
}>()

const emit = defineEmits<{
  'update:selectedSkuId': [value: string | null]
}>()

const imageAvailable = ref(canLoadImage(props.product.latest_snapshot?.image_url))
const snapshot = computed(() => props.product.latest_snapshot)
const displayPrice = computed(() => {
  const price = snapshot.value?.price
  return price === null || price === undefined ? '价格缺失' : `¥${price}`
})
const specifications = computed(() => Object.entries(snapshot.value?.specifications ?? {}))

watch(
  () => props.product.latest_snapshot?.image_url,
  (value) => {
    imageAvailable.value = canLoadImage(value)
  },
)

function selectSku(value: string | number): void {
  /** 把 Ant Radio 值收敛为稳定 SKU ID。by AI.Coding */
  emit('update:selectedSkuId', String(value))
}

function canLoadImage(value: string | null | undefined): boolean {
  /** Fixture 的 .invalid 图片不发起网络请求，直接使用本地占位视觉。by AI.Coding */
  if (!value) {
    return false
  }
  try {
    return !new URL(value).hostname.endsWith('.invalid')
  } catch {
    return false
  }
}
</script>

<template>
  <article class="product-panel">
    <div class="product-visual">
      <img
        v-if="imageAvailable && snapshot?.image_url"
        :alt="snapshot.title"
        :src="snapshot.image_url"
        @error="imageAvailable = false"
      />
      <div v-else class="product-fallback" aria-hidden="true">
        <MobileOutlined />
        <span>{{ product.external_product_id }}</span>
      </div>
    </div>

    <div class="product-body">
      <div class="product-heading">
        <div>
          <span class="product-position">候选 {{ product.position + 1 }}</span>
          <h2>{{ snapshot?.title ?? '商品信息不可用' }}</h2>
        </div>
        <strong class="product-price">{{ displayPrice }}</strong>
      </div>

      <div class="product-meta">
        <span><ShopOutlined /> {{ snapshot?.shop_name ?? '店铺信息缺失' }}</span>
        <span>{{ snapshot?.brand ?? '品牌待核验' }}</span>
        <span>{{ snapshot?.category ?? '品类信息缺失' }}</span>
      </div>

      <dl v-if="specifications.length" class="specification-list">
        <template v-for="[name, value] in specifications" :key="name">
          <dt>{{ name }}</dt>
          <dd>{{ value }}</dd>
        </template>
      </dl>
      <p v-else class="missing-copy">规格字段缺失，后续对比将保留该不确定性。</p>

      <section class="sku-section">
        <div class="section-label">
          <span>SKU / 规格</span>
          <a-tag v-if="!product.skus.length" color="default">无需选择</a-tag>
        </div>
        <a-radio-group
          v-if="product.skus.length"
          class="sku-list"
          :disabled="disabled"
          :value="selectedSkuId"
          @update:value="selectSku"
        >
          <a-radio
            v-for="sku in product.skus"
            :key="sku.id"
            :disabled="!sku.selectable"
            :value="sku.id"
          >
            <span class="sku-name">{{ sku.name }}</span>
            <span class="sku-price">{{ sku.price ? `¥${sku.price}` : '价格缺失' }}</span>
          </a-radio>
        </a-radio-group>
        <p v-else class="no-sku-copy">该商品没有可选 SKU，将以当前商品快照继续。</p>
      </section>
    </div>
  </article>
</template>

<style scoped>
.product-panel {
  display: grid;
  min-width: 0;
  border: 1px solid var(--line);
  border-radius: 6px;
  background: var(--surface);
  grid-template-columns: 168px minmax(0, 1fr);
  overflow: hidden;
}

.product-visual {
  min-height: 280px;
  border-right: 1px solid var(--line);
  background: var(--surface-subtle);
}

.product-visual img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.product-fallback {
  display: grid;
  height: 100%;
  min-height: 280px;
  place-content: center;
  color: var(--muted);
  gap: 12px;
  text-align: center;
}

.product-fallback :deep(svg) {
  font-size: 48px;
  stroke-width: 1;
}

.product-fallback span {
  font-family: Consolas, monospace;
  font-size: 11px;
}

.product-body {
  min-width: 0;
  padding: 22px;
}

.product-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 20px;
}

.product-position,
.section-label {
  color: var(--muted);
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
}

.product-heading h2 {
  margin: 5px 0 0;
  color: var(--ink);
  font-size: 19px;
  line-height: 1.35;
}

.product-price {
  color: var(--positive);
  font-family: Georgia, serif;
  font-size: 21px;
  white-space: nowrap;
}

.product-meta {
  display: flex;
  flex-wrap: wrap;
  margin-top: 12px;
  color: var(--muted);
  font-size: 12px;
  gap: 8px 18px;
}

.specification-list {
  display: grid;
  margin: 20px 0 0;
  border-top: 1px solid var(--line);
  grid-template-columns: minmax(90px, 0.45fr) minmax(120px, 1fr);
}

.specification-list dt,
.specification-list dd {
  margin: 0;
  border-bottom: 1px solid var(--line);
  padding: 8px 0;
  font-size: 12px;
}

.specification-list dt {
  color: var(--muted);
}

.missing-copy,
.no-sku-copy {
  margin: 16px 0 0;
  color: var(--muted);
  font-size: 12px;
}

.sku-section {
  margin-top: 20px;
}

.section-label {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.sku-list {
  display: grid;
  margin-top: 10px;
  gap: 8px;
}

.sku-list :deep(.ant-radio-wrapper) {
  display: flex;
  min-height: 42px;
  align-items: center;
  margin-inline-end: 0;
  border: 1px solid var(--line);
  border-radius: 4px;
  padding: 8px 12px;
}

.sku-name {
  color: var(--ink);
  font-weight: 600;
}

.sku-price {
  margin-left: 8px;
  color: var(--muted);
  font-size: 12px;
}

@media (max-width: 720px) {
  .product-panel {
    grid-template-columns: 1fr;
  }

  .product-visual {
    height: 190px;
    min-height: 190px;
    border-right: 0;
    border-bottom: 1px solid var(--line);
  }

  .product-fallback {
    min-height: 190px;
  }
}
</style>
