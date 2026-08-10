<script setup lang="ts">
// M1-C 商品链接输入、创建和解析页面。by AI.Coding

import { computed, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import type { FormInstance, Rule } from 'ant-design-vue/es/form'
import {
  ArrowRightOutlined,
  DeleteOutlined,
  LinkOutlined,
  PlusOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons-vue'
import AppHeader from '@/components/comparisons/AppHeader.vue'
import FlowSteps from '@/components/comparisons/FlowSteps.vue'
import { useComparisonStore } from '@/stores/comparison'

const router = useRouter()
const comparisonStore = useComparisonStore()
const formRef = ref<FormInstance>()
const form = reactive<{
  product_urls: string[]
  review_window_days: 30 | 60
}>({
  product_urls: ['', ''],
  review_window_days: 30,
})

const urlRules: Rule[] = [
  { required: true, message: '请填写商品链接', trigger: 'blur' },
  { validator: validateProductUrl, trigger: 'blur' },
]
const canAddProduct = computed(() => form.product_urls.length < 3)
const phaseLabel = computed(() => {
  if (comparisonStore.action === 'creating') return '正在创建对比草稿'
  if (comparisonStore.action === 'parsing') return '正在解析合成商品数据'
  return ''
})

async function validateProductUrl(_rule: Rule, value: string): Promise<void> {
  /** 校验单个候选为完整 HTTP/HTTPS URL。by AI.Coding */
  try {
    const url = new URL(value.trim())
    if (!['http:', 'https:'].includes(url.protocol)) {
      throw new Error()
    }
  } catch {
    throw new Error('请输入完整的 HTTP/HTTPS 商品链接')
  }
}

function addProduct(): void {
  /** 增加可选的第三个候选输入。by AI.Coding */
  if (canAddProduct.value) {
    form.product_urls.push('')
  }
}

function removeProduct(index: number): void {
  /** 在至少保留两个候选的前提下删除输入项。by AI.Coding */
  if (form.product_urls.length > 2) {
    form.product_urls.splice(index, 1)
  }
}

function fillFixtureSamples(): void {
  /** 填充无网络 Fixture 可识别的两个安全样本链接。by AI.Coding */
  form.product_urls = [
    'https://item.taobao.com/item.htm?id=10001',
    'https://item.taobao.com/item.htm?id=10002',
  ]
}

async function submitComparison(): Promise<void> {
  /** 创建并解析任务，成功后把任务 ID 写入确认路由。by AI.Coding */
  comparisonStore.clearError()
  await formRef.value?.validate()
  try {
    const comparison = await comparisonStore.createAndParse({
      product_urls: form.product_urls.map((value) => value.trim()),
      review_window_days: form.review_window_days,
    })
    await router.push({ name: 'comparison-confirm', params: { id: comparison.id } })
  } catch {
    // store 已保存统一 ApiError，页面只负责展示并允许用户重试。
  }
}

async function resumeLastComparison(): Promise<void> {
  /** 跳转到最近任务，由目标页面按服务端状态恢复。by AI.Coding */
  if (comparisonStore.lastComparisonId) {
    await router.push({
      name: 'comparison-confirm',
      params: { id: comparisonStore.lastComparisonId },
    })
  }
}
</script>

<template>
  <div class="app-frame">
    <AppHeader />
    <FlowSteps :current="0" />

    <main class="workspace">
      <header class="workspace-heading">
        <div>
          <span class="eyebrow">M1-C / T26</span>
          <h1>建立候选商品组</h1>
          <p>提交 2～3 个候选链接，系统将使用合成 Fixture 解析商品事实。</p>
        </div>
        <a-button
          v-if="comparisonStore.lastComparisonId"
          type="text"
          @click="resumeLastComparison"
        >
          继续上次任务
          <ArrowRightOutlined />
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

      <section class="input-layout">
        <a-form
          ref="formRef"
          class="input-form"
          :model="form"
          layout="vertical"
        >
          <div class="form-section-heading">
            <div>
              <span>候选商品</span>
              <small>{{ form.product_urls.length }} / 3</small>
            </div>
            <a-button size="small" type="text" @click="fillFixtureSamples">
              <ThunderboltOutlined />
              填入合成样本
            </a-button>
          </div>

          <div class="url-list">
            <div v-for="(_, index) in form.product_urls" :key="index" class="url-row">
              <span class="url-index">{{ index + 1 }}</span>
              <a-form-item
                class="url-form-item"
                :name="['product_urls', index]"
                :rules="urlRules"
              >
                <a-input
                  v-model:value="form.product_urls[index]"
                  :aria-label="`候选商品链接 ${index + 1}`"
                  :disabled="comparisonStore.busy"
                  placeholder="https://item.taobao.com/item.htm?id=..."
                  size="large"
                >
                  <template #prefix><LinkOutlined /></template>
                </a-input>
              </a-form-item>
              <a-tooltip title="删除候选">
                <a-button
                  v-if="form.product_urls.length > 2"
                  aria-label="删除候选"
                  danger
                  shape="circle"
                  type="text"
                  @click="removeProduct(index)"
                >
                  <DeleteOutlined />
                </a-button>
              </a-tooltip>
            </div>
          </div>

          <a-button
            v-if="canAddProduct"
            class="add-product-button"
            block
            :disabled="comparisonStore.busy"
            @click="addProduct"
          >
            <PlusOutlined />
            增加第三个候选
          </a-button>

          <div class="review-window-field">
            <div>
              <strong>评论时间范围</strong>
              <span>用于后续评论分析阶段</span>
            </div>
            <a-segmented
              v-model:value="form.review_window_days"
              :disabled="comparisonStore.busy"
              :options="[
                { label: '近 30 天', value: 30 },
                { label: '近 60 天', value: 60 },
              ]"
            />
          </div>

          <a-button
            block
            class="primary-command"
            :loading="comparisonStore.busy"
            size="large"
            type="primary"
            @click="submitComparison"
          >
            {{ comparisonStore.busy ? phaseLabel : '创建并解析商品' }}
            <ArrowRightOutlined v-if="!comparisonStore.busy" />
          </a-button>
        </a-form>

        <aside class="boundary-panel">
          <span class="eyebrow">数据边界</span>
          <h2>只使用合成 Fixture</h2>
          <ul>
            <li>不会请求淘宝登录态、Cookie 或账号信息</li>
            <li>原始链接不会写入浏览器持久化缓存</li>
            <li>商品事实用于本地流程和自动化测试</li>
          </ul>
          <div class="fixture-codes">
            <span>10001</span>
            <span>10002</span>
            <small>可用样本 ID</small>
          </div>
        </aside>
      </section>
    </main>
  </div>
</template>

<style scoped>
.input-layout {
  display: grid;
  align-items: start;
  gap: 28px;
  grid-template-columns: minmax(0, 1fr) 280px;
}

.input-form {
  border-top: 2px solid var(--ink);
  background: var(--surface);
  padding: 24px;
}

.form-section-heading,
.review-window-field {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.form-section-heading {
  margin-bottom: 14px;
}

.form-section-heading > div {
  display: inline-flex;
  align-items: baseline;
  gap: 8px;
}

.form-section-heading span,
.review-window-field strong {
  color: var(--ink);
  font-size: 13px;
  font-weight: 700;
}

.form-section-heading small,
.review-window-field span {
  color: var(--muted);
  font-size: 11px;
}

.url-list {
  display: grid;
  gap: 10px;
}

.url-row {
  display: grid;
  align-items: start;
  gap: 10px;
  grid-template-columns: 28px minmax(0, 1fr) 32px;
}

.url-form-item {
  margin-bottom: 0;
}

.url-index {
  display: grid;
  width: 26px;
  height: 26px;
  place-items: center;
  border: 1px solid var(--line-strong);
  border-radius: 50%;
  color: var(--muted);
  font-family: Georgia, serif;
  font-size: 12px;
}

.add-product-button {
  margin-top: -6px;
  border-style: dashed;
}

.review-window-field {
  margin: 28px 0;
  border-top: 1px solid var(--line);
  border-bottom: 1px solid var(--line);
  padding: 18px 0;
}

.review-window-field > div {
  display: grid;
  gap: 3px;
}

.primary-command {
  height: 46px;
}

.boundary-panel {
  border-top: 2px solid var(--positive);
  background: var(--surface-subtle);
  padding: 22px;
}

.boundary-panel h2 {
  margin: 7px 0 16px;
  color: var(--ink);
  font-family: Georgia, "Noto Serif SC", serif;
  font-size: 20px;
}

.boundary-panel ul {
  display: grid;
  margin: 0;
  padding-left: 18px;
  color: var(--muted);
  font-size: 12px;
  gap: 10px;
  line-height: 1.55;
}

.fixture-codes {
  display: grid;
  margin-top: 24px;
  border-top: 1px solid var(--line);
  padding-top: 16px;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
}

.fixture-codes span {
  border: 1px solid var(--line);
  background: var(--surface);
  padding: 8px;
  color: var(--positive);
  font-family: Consolas, monospace;
  font-size: 12px;
  text-align: center;
}

.fixture-codes small {
  grid-column: 1 / -1;
  color: var(--muted);
  font-size: 10px;
  text-align: center;
}

@media (max-width: 820px) {
  .input-layout {
    grid-template-columns: 1fr;
  }

  .boundary-panel {
    order: -1;
  }
}

@media (max-width: 560px) {
  .input-form {
    padding: 18px 14px;
  }

  .review-window-field {
    align-items: flex-start;
    flex-direction: column;
    gap: 12px;
  }
}
</style>
