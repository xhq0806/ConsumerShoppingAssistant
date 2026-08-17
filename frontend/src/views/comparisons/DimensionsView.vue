<script setup lang="ts">
// M1-D 动态维度恢复、调整和确认页面。by AI.Coding

import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ArrowDownOutlined,
  ArrowLeftOutlined,
  ArrowUpOutlined,
  CheckCircleOutlined,
  DeleteOutlined,
  HolderOutlined,
  PlusOutlined,
  SearchOutlined,
  WarningOutlined,
} from '@ant-design/icons-vue'
import AppHeader from '@/components/comparisons/AppHeader.vue'
import FlowSteps from '@/components/comparisons/FlowSteps.vue'
import type { DimensionDataRisk, DimensionRecommendation } from '@/api/comparisons'
import { useComparisonStore } from '@/stores/comparison'

const route = useRoute()
const router = useRouter()
const comparisonStore = useComparisonStore()
const comparisonId = computed(() => String(route.params.id))
const selectedCodes = ref<string[]>([])
const searchQuery = ref('')
const draggedCode = ref<string | null>(null)
const queued = computed(() => comparisonStore.dimensionSet?.status === 'queued')
const selectedDimensions = computed(() =>
  selectedCodes.value
    .map((code) => dimensionByCode.value.get(code))
    .filter((item): item is DimensionRecommendation => item !== undefined),
)
const dimensionByCode = computed(
  () =>
    new Map(
      (comparisonStore.dimensionSet?.dimensions ?? []).map((dimension) => [
        dimension.code,
        dimension,
      ]),
    ),
)
const optionalDimensions = computed(() => {
  const query = searchQuery.value.trim().toLocaleLowerCase()
  return (comparisonStore.dimensionSet?.dimensions ?? []).filter(
    (dimension) =>
      !selectedCodes.value.includes(dimension.code) &&
      (!query ||
        dimension.name.toLocaleLowerCase().includes(query) ||
        dimension.code.toLocaleLowerCase().includes(query)),
  )
})
const loading = computed(() =>
  ['loading', 'loading-dimensions', 'generating-dimensions'].includes(
    comparisonStore.action ?? '',
  ),
)

onMounted(loadDimensions)

async function loadDimensions(): Promise<void> {
  /** 以路由任务 ID 恢复任务和维度；尚未生成时执行一次幂等生成。by AI.Coding */
  try {
    const comparison = await comparisonStore.loadComparison(comparisonId.value)
    if (comparison.status === 'awaiting_product_confirmation') {
      await router.replace({ name: 'comparison-confirm', params: { id: comparison.id } })
      return
    }
    if (comparison.status === 'draft' || comparison.status === 'parsing') {
      await router.replace({ name: 'comparison-input' })
      return
    }
    let dimensions = await comparisonStore.loadDimensions(comparisonId.value)
    if (!dimensions.generated) {
      dimensions = await comparisonStore.generateDimensions(comparisonId.value)
    }
    hydrateSelection(dimensions.dimensions)
  } catch {
    // store 持有页面可展示错误。
  }
}

function hydrateSelection(dimensions: DimensionRecommendation[]): void {
  /** 按服务端 position 恢复重点维度顺序。by AI.Coding */
  selectedCodes.value = dimensions
    .filter((dimension) => dimension.selected)
    .sort((left, right) => (left.position ?? 0) - (right.position ?? 0))
    .map((dimension) => dimension.code)
}

function addDimension(code: string): void {
  /** 从其他可选项追加一个维度。by AI.Coding */
  if (!queued.value && !selectedCodes.value.includes(code)) {
    selectedCodes.value.push(code)
  }
}

function removeDimension(dimension: DimensionRecommendation): void {
  /** 删除可移除的重点维度。by AI.Coding */
  if (!queued.value && dimension.user_removable) {
    selectedCodes.value = selectedCodes.value.filter((code) => code !== dimension.code)
  }
}

function moveDimension(code: string, direction: -1 | 1): void {
  /** 使用键盘友好的按钮调整重点维度顺序。by AI.Coding */
  if (queued.value) return
  const current = selectedCodes.value.indexOf(code)
  const target = current + direction
  if (current < 0 || target < 0 || target >= selectedCodes.value.length) return
  const next = [...selectedCodes.value]
  ;[next[current], next[target]] = [next[target], next[current]]
  selectedCodes.value = next
}

function startDrag(code: string): void {
  /** 记录原生拖拽中的维度 code。by AI.Coding */
  if (!queued.value) draggedCode.value = code
}

function dropBefore(targetCode: string): void {
  /** 把拖拽项移动到目标维度之前。by AI.Coding */
  const sourceCode = draggedCode.value
  draggedCode.value = null
  if (!sourceCode || sourceCode === targetCode || queued.value) return
  const next = selectedCodes.value.filter((code) => code !== sourceCode)
  const target = next.indexOf(targetCode)
  next.splice(target, 0, sourceCode)
  selectedCodes.value = next
}

async function confirmDimensions(): Promise<void> {
  /** 确认非空有序维度并进入 queued 分析边界。by AI.Coding */
  if (selectedCodes.value.length === 0 || queued.value) return
  try {
    const confirmed = await comparisonStore.confirmDimensions(comparisonId.value, {
      dimension_codes: selectedCodes.value,
    })
    hydrateSelection(confirmed.dimensions)
    await router.push({ name: 'comparison-progress', params: { id: comparisonId.value } })
  } catch {
    // store 持有页面可展示错误。
  }
}

async function backToPreferences(): Promise<void> {
  /** 返回偏好页，仅在确认前允许修改。by AI.Coding */
  if (!queued.value) {
    await router.push({ name: 'comparison-preferences', params: { id: comparisonId.value } })
  }
}

function riskLabel(risk: DimensionDataRisk): string {
  /** 将受控数据风险转换为简短展示文案。by AI.Coding */
  return {
    available: '数据可用',
    partial: '部分缺失',
    unavailable: '暂不可用',
  }[risk]
}
</script>

<template>
  <div class="app-frame">
    <AppHeader />
    <FlowSteps :current="3" />

    <main class="workspace dimensions-workspace">
      <header class="workspace-heading">
        <div>
          <span class="eyebrow">M1-D / 动态维度</span>
          <h1>确认真正重要的对比项</h1>
          <p>
            {{ comparisonStore.dimensionSet?.category ?? '通用' }}品类 ·
            {{ selectedCodes.length }} 项重点对比
          </p>
        </div>
        <a-button type="text" :disabled="queued" @click="backToPreferences">
          <ArrowLeftOutlined />
          返回购买偏好
        </a-button>
      </header>

      <a-alert
        v-if="comparisonStore.error"
        class="workspace-alert"
        :description="comparisonStore.error.message"
        :message="comparisonStore.error.code"
        show-icon
        type="error"
      />

      <a-spin :spinning="loading">
        <section v-if="queued" class="queued-banner">
          <CheckCircleOutlined />
          <div>
            <strong>维度已确认</strong>
            <span>任务已进入分析队列边界，当前里程碑尚未启动实际分析。</span>
          </div>
        </section>

        <div class="dimension-layout">
          <section class="dimension-section">
            <header class="section-heading">
              <div>
                <span class="section-index">01</span>
                <h2>重点对比</h2>
              </div>
              <span>{{ selectedDimensions.length }} 项</span>
            </header>

            <a-empty
              v-if="selectedDimensions.length === 0"
              description="至少添加一个对比维度"
            />

            <ol v-else class="dimension-list selected-list">
              <li
                v-for="(dimension, index) in selectedDimensions"
                :key="dimension.code"
                :draggable="!queued"
                @dragstart="startDrag(dimension.code)"
                @dragover.prevent
                @drop="dropBefore(dimension.code)"
              >
                <span class="position">{{ index + 1 }}</span>
                <HolderOutlined class="drag-handle" />
                <div class="dimension-copy">
                  <div class="dimension-title">
                    <strong>{{ dimension.name }}</strong>
                    <code>{{ dimension.code }}</code>
                  </div>
                  <p>{{ dimension.reason }}</p>
                  <small>{{ dimension.description }}</small>
                  <div class="dimension-meta">
                    <span :class="['risk', `risk-${dimension.data_risk}`]">
                      <WarningOutlined v-if="dimension.data_risk !== 'available'" />
                      {{ riskLabel(dimension.data_risk) }}
                    </span>
                    <span v-if="dimension.has_difference">存在商品差异</span>
                    <span v-if="!dimension.affects_recommendation">不参与推荐评分</span>
                  </div>
                </div>
                <div class="row-actions">
                  <a-tooltip title="上移">
                    <a-button
                      :aria-label="`上移${dimension.name}`"
                      :disabled="queued || index === 0"
                      type="text"
                      @click="moveDimension(dimension.code, -1)"
                    >
                      <ArrowUpOutlined />
                    </a-button>
                  </a-tooltip>
                  <a-tooltip title="下移">
                    <a-button
                      :aria-label="`下移${dimension.name}`"
                      :disabled="queued || index === selectedDimensions.length - 1"
                      type="text"
                      @click="moveDimension(dimension.code, 1)"
                    >
                      <ArrowDownOutlined />
                    </a-button>
                  </a-tooltip>
                  <a-tooltip title="删除">
                    <a-button
                      :aria-label="`删除${dimension.name}`"
                      danger
                      :disabled="queued || !dimension.user_removable"
                      type="text"
                      @click="removeDimension(dimension)"
                    >
                      <DeleteOutlined />
                    </a-button>
                  </a-tooltip>
                </div>
              </li>
            </ol>
          </section>

          <aside class="dimension-section optional-section">
            <header class="section-heading">
              <div>
                <span class="section-index">02</span>
                <h2>其他可选</h2>
              </div>
              <span>{{ optionalDimensions.length }} 项</span>
            </header>

            <a-input
              v-model:value="searchQuery"
              allow-clear
              placeholder="搜索维度"
              :disabled="queued"
            >
              <template #prefix><SearchOutlined /></template>
            </a-input>

            <ul class="optional-list">
              <li v-for="dimension in optionalDimensions" :key="dimension.code">
                <div>
                  <strong>{{ dimension.name }}</strong>
                  <span :class="['risk', `risk-${dimension.data_risk}`]">
                    {{ riskLabel(dimension.data_risk) }}
                  </span>
                  <p>{{ dimension.reason }}</p>
                </div>
                <a-button
                  :aria-label="`添加${dimension.name}`"
                  :disabled="queued"
                  type="text"
                  @click="addDimension(dimension.code)"
                >
                  <PlusOutlined />
                </a-button>
              </li>
            </ul>
          </aside>
        </div>

        <footer class="confirmation-bar">
          <span v-if="selectedCodes.length === 0">至少保留一个维度才能继续</span>
          <span v-else>{{ selectedCodes.length }} 个维度将用于后续分析</span>
          <a-button
            class="primary-command"
            :disabled="selectedCodes.length === 0 || queued"
            :loading="comparisonStore.action === 'confirming-dimensions'"
            size="large"
            type="primary"
            @click="confirmDimensions"
          >
            <CheckCircleOutlined />
            {{ queued ? '已进入分析队列' : '确认维度并进入队列' }}
          </a-button>
        </footer>
      </a-spin>
    </main>
  </div>
</template>

<style scoped>
.dimension-layout {
  display: grid;
  align-items: start;
  gap: 24px;
  grid-template-columns: minmax(0, 1.65fr) minmax(280px, 0.85fr);
}

.dimension-section {
  border-top: 2px solid var(--ink);
  background: var(--surface);
  padding: 20px;
}

.optional-section {
  position: sticky;
  top: 20px;
  border-top-color: var(--accent);
}

.section-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.section-heading > div {
  display: flex;
  align-items: baseline;
  gap: 10px;
}

.section-heading h2 {
  margin: 0;
  font-size: 17px;
}

.section-heading > span,
.section-index {
  color: var(--muted);
  font-size: 11px;
}

.section-index {
  color: var(--positive);
  font-family: Georgia, serif;
}

.dimension-list,
.optional-list {
  display: grid;
  margin: 0;
  padding: 0;
  list-style: none;
}

.dimension-list li {
  display: grid;
  align-items: start;
  border-top: 1px solid var(--line);
  padding: 16px 0;
  grid-template-columns: 28px 20px minmax(0, 1fr) auto;
  gap: 8px;
}

.position {
  display: grid;
  width: 25px;
  height: 25px;
  place-items: center;
  border: 1px solid var(--line-strong);
  border-radius: 50%;
  color: var(--muted);
  font-family: Georgia, serif;
  font-size: 11px;
}

.drag-handle {
  margin-top: 4px;
  color: var(--line-strong);
  cursor: grab;
}

.dimension-copy {
  min-width: 0;
}

.dimension-title {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 8px;
}

.dimension-title strong {
  font-size: 14px;
}

.dimension-title code {
  color: var(--muted);
  font-size: 10px;
}

.dimension-copy p,
.optional-list p {
  margin: 5px 0;
  color: var(--positive);
  font-size: 12px;
}

.dimension-copy small {
  display: block;
  color: var(--muted);
  font-size: 11px;
  line-height: 1.55;
}

.dimension-meta {
  display: flex;
  flex-wrap: wrap;
  margin-top: 9px;
  gap: 6px;
}

.dimension-meta span,
.risk {
  border: 1px solid var(--line);
  padding: 2px 6px;
  color: var(--muted);
  font-size: 10px;
}

.risk-available {
  border-color: rgb(40 111 81 / 30%);
  color: var(--positive);
}

.risk-partial {
  border-color: rgb(212 93 67 / 35%);
  color: var(--accent);
}

.risk-unavailable {
  border-color: rgb(184 67 54 / 35%);
  color: var(--danger);
}

.row-actions {
  display: flex;
}

.row-actions .ant-btn {
  width: 30px;
  height: 30px;
  padding: 0;
}

.optional-list {
  margin-top: 12px;
  max-height: 560px;
  overflow: auto;
}

.optional-list li {
  display: grid;
  align-items: center;
  border-top: 1px solid var(--line);
  padding: 13px 0;
  grid-template-columns: minmax(0, 1fr) 34px;
  gap: 8px;
}

.optional-list strong {
  margin-right: 8px;
  font-size: 12px;
}

.optional-list p {
  color: var(--muted);
  line-height: 1.4;
}

.queued-banner {
  display: flex;
  align-items: center;
  margin-bottom: 18px;
  border: 1px solid rgb(40 111 81 / 28%);
  background: rgb(40 111 81 / 7%);
  padding: 15px 18px;
  color: var(--positive);
  gap: 12px;
}

.queued-banner div {
  display: grid;
  gap: 3px;
}

.queued-banner span {
  color: var(--muted);
  font-size: 11px;
}

.confirmation-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 20px;
  border-top: 1px solid var(--line-strong);
  background: var(--surface-subtle);
  padding: 16px 20px;
  gap: 20px;
}

.confirmation-bar > span {
  color: var(--muted);
  font-size: 12px;
}

@media (max-width: 900px) {
  .dimension-layout {
    grid-template-columns: 1fr;
  }

  .optional-section {
    position: static;
  }
}

@media (max-width: 600px) {
  .dimension-section {
    padding: 16px 12px;
  }

  .dimension-list li {
    grid-template-columns: 24px 16px minmax(0, 1fr);
  }

  .row-actions {
    grid-column: 3;
  }

  .confirmation-bar {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
