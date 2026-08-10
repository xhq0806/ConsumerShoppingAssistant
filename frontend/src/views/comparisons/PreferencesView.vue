<script setup lang="ts">
// M1-C 购买偏好填写、恢复和保存页面。by AI.Coding

import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { FormInstance, Rule } from 'ant-design-vue/es/form'
import {
  ArrowLeftOutlined,
  CheckCircleOutlined,
  SaveOutlined,
} from '@ant-design/icons-vue'
import AppHeader from '@/components/comparisons/AppHeader.vue'
import FlowSteps from '@/components/comparisons/FlowSteps.vue'
import { useComparisonStore } from '@/stores/comparison'
import { limitPreferenceItems } from './preferenceLimits'

const route = useRoute()
const router = useRouter()
const comparisonStore = useComparisonStore()
const formRef = ref<FormInstance>()
const saved = ref(false)
const comparisonId = computed(() => String(route.params.id))
const form = reactive<{
  review_window_days: 30 | 60
  budget_min: number | null
  budget_max: number | null
  usage_scenarios: string[]
  priority_concerns: string[]
  deal_breakers: string[]
}>({
  review_window_days: 30,
  budget_min: null,
  budget_max: null,
  usage_scenarios: [],
  priority_concerns: [],
  deal_breakers: [],
})

const usageOptions = ['日常通勤', '旅行拍照', '影音娱乐', '轻度游戏', '商务办公']
const concernOptions = ['价格', '续航', '拍照', '性能', '便携性', '售后', '存储空间']
const dealBreakerOptions = ['机身过重', '续航不足', '广告过多', '售后网点少', '无现货']

const rules: Record<string, Rule[]> = {
  usage_scenarios: [
    { required: true, type: 'array', min: 1, message: '至少填写一个使用场景' },
    { type: 'array', max: 5, message: '最多填写五个使用场景' },
    { validator: validateTags, trigger: 'change' },
  ],
  priority_concerns: [
    { required: true, type: 'array', min: 1, message: '至少填写一个关注点' },
    { type: 'array', max: 8, message: '最多填写八个关注点' },
    { validator: validateTags, trigger: 'change' },
  ],
  deal_breakers: [
    { type: 'array', max: 8, message: '最多填写八个禁忌项' },
    { validator: validateTags, trigger: 'change' },
  ],
  budget_max: [{ validator: validateBudgetRange, trigger: 'change' }],
}

onMounted(loadPreferences)

async function loadPreferences(): Promise<void> {
  /** 从详情响应恢复偏好，并在商品尚未确认时返回确认页。by AI.Coding */
  try {
    const comparison = await comparisonStore.loadComparison(comparisonId.value)
    if (comparison.status === 'awaiting_product_confirmation') {
      await router.replace({ name: 'comparison-confirm', params: { id: comparison.id } })
      return
    }
    form.review_window_days = comparison.review_window_days as 30 | 60
    if (comparison.preferences) {
      form.budget_min = toNumber(comparison.preferences.budget_min)
      form.budget_max = toNumber(comparison.preferences.budget_max)
      form.usage_scenarios = [...comparison.preferences.usage_scenarios]
      form.priority_concerns = [...comparison.preferences.priority_concerns]
      form.deal_breakers = [...comparison.preferences.deal_breakers]
    }
  } catch {
    // store 持有页面可展示错误。
  }
}

async function validateTags(_rule: Rule, values: string[]): Promise<void> {
  /** 校验标签单项长度，数量上限由受控组件和表单规则共同保证。by AI.Coding */
  if (values.some((value) => value.trim().length === 0 || value.trim().length > 80)) {
    throw new Error('每项内容必须为 1～80 个字符')
  }
}

async function validateBudgetRange(): Promise<void> {
  /** 校验预算上下限关系。by AI.Coding */
  if (
    form.budget_min !== null &&
    form.budget_max !== null &&
    form.budget_max < form.budget_min
  ) {
    throw new Error('预算上限不能低于预算下限')
  }
}

async function savePreferences(): Promise<void> {
  /** 保存偏好并展示服务端规范化后的完成状态。by AI.Coding */
  comparisonStore.clearError()
  saved.value = false
  try {
    await formRef.value?.validate()
    await comparisonStore.savePreferences(comparisonId.value, {
      review_window_days: form.review_window_days,
      budget_min: formatBudget(form.budget_min),
      budget_max: formatBudget(form.budget_max),
      usage_scenarios: form.usage_scenarios,
      priority_concerns: form.priority_concerns,
      deal_breakers: form.deal_breakers,
    })
    saved.value = true
  } catch {
    // 表单展示校验错误；请求错误由 store 持有并展示。
  }
}

async function backToConfirmation(): Promise<void> {
  /** 返回商品确认页面复核选择。by AI.Coding */
  await router.push({ name: 'comparison-confirm', params: { id: comparisonId.value } })
}

function formatBudget(value: number | null): string | null {
  /** 把输入金额固定为后端 Decimal 接受的两位小数字符串。by AI.Coding */
  return value === null ? null : value.toFixed(2)
}

function toNumber(value: string | null): number | null {
  /** 把后端金额字符串转换为输入控件值。by AI.Coding */
  return value === null ? null : Number(value)
}
</script>

<template>
  <div class="app-frame">
    <AppHeader />
    <FlowSteps :current="2" />

    <main class="workspace preferences-workspace">
      <header class="workspace-heading">
        <div>
          <span class="eyebrow">M1-C / T13</span>
          <h1>定义购买偏好</h1>
          <p>这些信息将在下一阶段用于排序已注册的对比维度，不会替代商品事实。</p>
        </div>
        <a-button type="text" @click="backToConfirmation">
          <ArrowLeftOutlined />
          返回商品确认
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

      <section class="preferences-layout">
        <a-spin :spinning="comparisonStore.action === 'loading'">
          <a-form
            ref="formRef"
            class="preferences-form"
            :model="form"
            :rules="rules"
            layout="vertical"
          >
            <section class="preference-section">
              <header>
                <span class="section-number">01</span>
                <div>
                  <h2>评论范围与预算</h2>
                  <p>预算可只填写上限，也可以给出完整区间。</p>
                </div>
              </header>

              <a-form-item label="评论时间范围" name="review_window_days">
                <a-segmented
                  v-model:value="form.review_window_days"
                  :options="[
                    { label: '近 30 天', value: 30 },
                    { label: '近 60 天', value: 60 },
                  ]"
                />
              </a-form-item>

              <div class="budget-grid">
                <a-form-item label="预算下限">
                  <a-input-number
                    v-model:value="form.budget_min"
                    addon-before="¥"
                    :max="1000000"
                    :min="0"
                    :precision="2"
                    placeholder="可选"
                  />
                </a-form-item>
                <a-form-item label="预算上限" name="budget_max">
                  <a-input-number
                    v-model:value="form.budget_max"
                    addon-before="¥"
                    :max="1000000"
                    :min="0"
                    :precision="2"
                    placeholder="例如 4500"
                  />
                </a-form-item>
              </div>
            </section>

            <section class="preference-section">
              <header>
                <span class="section-number">02</span>
                <div>
                  <h2>使用场景</h2>
                  <p>至少一项，最多五项。</p>
                </div>
              </header>
              <a-form-item name="usage_scenarios">
                <a-select
                  :value="form.usage_scenarios"
                  mode="tags"
                  :max-tag-count="5"
                  :options="usageOptions.map((value) => ({ label: value, value }))"
                  placeholder="选择或输入场景"
                  @update:value="form.usage_scenarios = limitPreferenceItems($event, 5)"
                />
              </a-form-item>
            </section>

            <section class="preference-section">
              <header>
                <span class="section-number">03</span>
                <div>
                  <h2>重点关注</h2>
                  <p>至少一项，后续会优先映射到已注册维度。</p>
                </div>
              </header>
              <a-form-item name="priority_concerns">
                <a-select
                  :value="form.priority_concerns"
                  mode="tags"
                  :max-tag-count="8"
                  :options="concernOptions.map((value) => ({ label: value, value }))"
                  placeholder="选择或输入关注点"
                  @update:value="form.priority_concerns = limitPreferenceItems($event, 8)"
                />
              </a-form-item>
            </section>

            <section class="preference-section">
              <header>
                <span class="section-number">04</span>
                <div>
                  <h2>不能接受</h2>
                  <p>可选。用于后续报告中的风险提示。</p>
                </div>
              </header>
              <a-form-item name="deal_breakers">
                <a-select
                  :value="form.deal_breakers"
                  mode="tags"
                  :max-tag-count="8"
                  :options="dealBreakerOptions.map((value) => ({ label: value, value }))"
                  placeholder="选择或输入禁忌项"
                  @update:value="form.deal_breakers = limitPreferenceItems($event, 8)"
                />
              </a-form-item>
            </section>

            <a-button
              block
              class="primary-command"
              :loading="comparisonStore.action === 'saving'"
              size="large"
              type="primary"
              @click="savePreferences"
            >
              <SaveOutlined />
              保存购买偏好
            </a-button>
          </a-form>
        </a-spin>

        <aside class="preference-summary">
          <span class="eyebrow">当前候选</span>
          <ol>
            <li
              v-for="product in comparisonStore.comparison?.products ?? []"
              :key="product.id"
            >
              <span>{{ product.position + 1 }}</span>
              <div>
                <strong>{{ product.latest_snapshot?.title ?? '商品信息缺失' }}</strong>
                <small>
                  {{ product.latest_snapshot?.price ? `¥${product.latest_snapshot.price}` : '价格缺失' }}
                </small>
              </div>
            </li>
          </ol>

          <div v-if="saved" class="saved-state">
            <CheckCircleOutlined />
            <div>
              <strong>偏好已保存</strong>
              <span>刷新页面仍可恢复。下一阶段将生成动态对比维度。</span>
            </div>
          </div>
        </aside>
      </section>
    </main>
  </div>
</template>

<style scoped>
.preferences-layout {
  display: grid;
  align-items: start;
  gap: 28px;
  grid-template-columns: minmax(0, 1fr) 300px;
}

.preferences-form {
  display: grid;
  gap: 14px;
}

.preference-section {
  border-top: 2px solid var(--ink);
  background: var(--surface);
  padding: 22px 24px 10px;
}

.preference-section > header {
  display: flex;
  align-items: flex-start;
  margin-bottom: 18px;
  gap: 12px;
}

.section-number {
  color: var(--positive);
  font-family: Georgia, serif;
  font-size: 12px;
}

.preference-section h2 {
  margin: 0;
  color: var(--ink);
  font-size: 16px;
}

.preference-section p {
  margin: 4px 0 0;
  color: var(--muted);
  font-size: 11px;
}

.budget-grid {
  display: grid;
  gap: 14px;
  grid-template-columns: 1fr 1fr;
}

.budget-grid :deep(.ant-input-number-group-wrapper),
.budget-grid :deep(.ant-input-number) {
  width: 100%;
}

.preference-summary {
  position: sticky;
  top: 20px;
  border-top: 2px solid var(--accent);
  background: var(--surface-subtle);
  padding: 22px;
}

.preference-summary ol {
  display: grid;
  margin: 16px 0 0;
  padding: 0;
  list-style: none;
  gap: 12px;
}

.preference-summary li {
  display: grid;
  align-items: center;
  border-bottom: 1px solid var(--line);
  padding-bottom: 12px;
  grid-template-columns: 28px minmax(0, 1fr);
  gap: 10px;
}

.preference-summary li > span {
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

.preference-summary li div {
  display: grid;
  min-width: 0;
  gap: 3px;
}

.preference-summary strong {
  overflow: hidden;
  color: var(--ink);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.preference-summary small {
  color: var(--positive);
  font-size: 11px;
}

.saved-state {
  display: flex;
  margin-top: 22px;
  border: 1px solid rgb(40 111 81 / 24%);
  background: rgb(40 111 81 / 7%);
  padding: 14px;
  color: var(--positive);
  gap: 10px;
}

.saved-state div {
  display: grid;
  gap: 4px;
}

.saved-state span {
  color: var(--muted);
  font-size: 11px;
  line-height: 1.5;
}

@media (max-width: 860px) {
  .preferences-layout {
    grid-template-columns: 1fr;
  }

  .preference-summary {
    position: static;
    order: -1;
  }
}

@media (max-width: 560px) {
  .preference-section {
    padding: 18px 14px 6px;
  }

  .budget-grid {
    grid-template-columns: 1fr;
  }
}
</style>
