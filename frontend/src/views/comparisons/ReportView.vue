<script setup lang="ts">
// M1-G 可追溯购买决策报告与刷新恢复页面。by AI.Coding

import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ArrowLeftOutlined,
  CheckCircleOutlined,
  DatabaseOutlined,
  FileTextOutlined,
  WarningOutlined,
} from '@ant-design/icons-vue'
import AppHeader from '@/components/comparisons/AppHeader.vue'
import FlowSteps from '@/components/comparisons/FlowSteps.vue'
import type {
  ReportClaim,
  ReportDifference,
  ReportDimension,
  ReportProduct,
  ReportSourceRef,
} from '@/api/comparisons'
import { useComparisonStore } from '@/stores/comparison'

const route = useRoute()
const router = useRouter()
const comparisonStore = useComparisonStore()
const comparisonId = computed(() => String(route.params.id))
const report = computed(() => comparisonStore.report)
const summary = computed(() => report.value?.summary)
const products = computed(() => report.value?.full_comparison.products ?? [])
const busy = computed(() =>
  ['loading', 'loading-report'].includes(comparisonStore.action ?? ''),
)
const recommendedProduct = computed(() =>
  products.value.find((product) => product.id === summary.value?.recommended_product_id),
)
const recommendationClaim = computed(() =>
  claimAt(summary.value?.recommendation_claim_index),
)
const scenarioRecommendations = computed(() =>
  (summary.value?.scenario_recommendations ?? []).map((scenario) => ({
    ...scenario,
    product: products.value.find((product) => product.id === scenario.product_id),
    claim: claimAt(scenario.claim_index),
  })),
)
const reasonClaims = computed(() =>
  (summary.value?.key_reason_claim_indexes ?? [])
    .map(claimAt)
    .filter((claim): claim is ReportClaim => claim !== undefined),
)
const riskClaims = computed(() =>
  (summary.value?.risk_claim_indexes ?? [])
    .map(claimAt)
    .filter((claim): claim is ReportClaim => claim !== undefined),
)
const differences = computed(() =>
  (report.value?.differences ?? []).map((difference) => ({
    ...difference,
    claim: claimAt(difference.claim_index),
  })),
)
const dimensions = computed(() => report.value?.full_comparison.dimensions ?? [])

onMounted(initialize)

async function initialize(): Promise<void> {
  /** 按路由任务 ID 恢复终态和最新报告。by AI.Coding */
  try {
    const comparison = await comparisonStore.loadComparison(comparisonId.value)
    if (!['completed', 'partially_completed'].includes(comparison.status)) {
      await router.replace({
        name: 'comparison-progress',
        params: { id: comparison.id },
      })
      return
    }
    await comparisonStore.loadReport(comparison.id)
  } catch {
    // 统一错误由 store 保存并在页面显示。
  }
}

function claimAt(index: number | undefined): ReportClaim | undefined {
  /** 按报告稳定 display_order 读取模型结论。by AI.Coding */
  if (index === undefined) return undefined
  return report.value?.claims[index]
}

function confidenceText(value: number | null | undefined): string {
  /** 把零到一置信度转换为整数百分比。by AI.Coding */
  if (value === null || value === undefined) return '未提供'
  return `${Math.round(value * 100)}%`
}

function priceText(product: ReportProduct): string {
  /** 显示确定性商品价格或缺失状态。by AI.Coding */
  if (product.price === null) return '价格缺失'
  return `¥${product.price}`
}

function sourceLabel(source: ReportSourceRef): string {
  /** 把来源白名单类型映射为用户可识别的证据标签。by AI.Coding */
  if (source.type === 'product_snapshot') {
    return `商品事实 · ${source.field ?? '字段'}`
  }
  if (source.type === 'analysis_metric') {
    return '确定性指标'
  }
  if (source.type === 'raw_review') {
    return `评论证据 · ${source.evidence ?? ''}`
  }
  return '品牌来源'
}

function claimTypeLabel(claim: ReportClaim): string {
  /** 映射报告 claim 类型。by AI.Coding */
  return {
    fact: '事实',
    advantage: '优势',
    disadvantage: '限制',
    recommendation: '建议',
    warning: '风险',
  }[claim.claim_type]
}

function dimensionMetricText(
  product: ReportProduct,
  dimension: ReportDimension,
): string {
  /** 汇总单商品单维度的注解数、覆盖率和正负反馈。by AI.Coding */
  const metrics = product.metrics.filter(
    (metric) => metric.dimension_code === dimension.code,
  )
  if (!metrics.length) return '无评论指标'
  const value = (type: string) =>
    metrics.find((metric) => metric.metric_type === type)?.numeric_value
  const annotations = Number(value('annotation_count') ?? 0)
  const coverage = Number(value('coverage_ratio') ?? 0)
  const positive = Number(value('positive_ratio') ?? 0)
  const negative = Number(value('negative_ratio') ?? 0)
  return `${annotations} 条 · 覆盖 ${Math.round(coverage * 100)}% · 正向 ${Math.round(
    positive * 100,
  )}% · 负向 ${Math.round(negative * 100)}%`
}

function generatedAtText(): string {
  /** 按本地时区显示报告生成时间。by AI.Coding */
  if (!report.value) return ''
  return new Intl.DateTimeFormat('zh-CN', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(report.value.generated_at))
}
</script>

<template>
  <div class="app-frame">
    <AppHeader />
    <FlowSteps :current="5" />

    <main class="workspace report-workspace">
      <header class="workspace-heading">
        <div>
          <span class="eyebrow">M1-G / 对比报告</span>
          <h1>{{ summary?.headline ?? '购买决策报告' }}</h1>
          <p v-if="report">
            版本 {{ report.version }} · {{ generatedAtText() }} · 任务 {{ comparisonId }}
          </p>
        </div>
        <a-button
          aria-label="返回任务进度"
          @click="
            router.push({
              name: 'comparison-progress',
              params: { id: comparisonId },
            })
          "
        >
          <ArrowLeftOutlined />
          任务进度
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

      <a-spin :spinning="busy && !report">
        <template v-if="report">
          <a-alert
            v-if="report.status === 'partial'"
            class="workspace-alert"
            message="部分数据不足，本报告已降低结论强度"
            show-icon
            type="warning"
          >
            <template #description>
              <ul class="warning-list">
                <li v-for="warning in report.warnings" :key="warning">{{ warning }}</li>
              </ul>
            </template>
          </a-alert>

          <section class="summary-band">
            <div class="summary-mark">
              <CheckCircleOutlined />
            </div>
            <div class="summary-main">
              <span class="section-kicker">综合建议</span>
              <h2>
                {{ recommendedProduct?.title ?? '当前没有明确的单一推荐商品' }}
              </h2>
              <p>{{ recommendationClaim?.text }}</p>
            </div>
            <div class="confidence-block">
              <span>报告置信度</span>
              <strong>{{ confidenceText(summary?.confidence) }}</strong>
            </div>
          </section>

          <section v-if="scenarioRecommendations.length" class="report-section">
            <header class="section-heading">
              <span>分场景建议</span>
              <h2>不同使用场景下的选择</h2>
            </header>
            <div class="scenario-grid">
              <article
                v-for="scenario in scenarioRecommendations"
                :key="scenario.scenario"
                class="scenario-item"
              >
                <span>{{ scenario.scenario }}</span>
                <strong>{{ scenario.product?.title ?? '暂无明确推荐' }}</strong>
                <p>{{ scenario.claim?.text }}</p>
              </article>
            </div>
          </section>

          <section class="reason-grid">
            <div class="report-section">
              <header class="section-heading compact">
                <span>主要依据</span>
                <h2>推荐理由</h2>
              </header>
              <article
                v-for="claim in reasonClaims"
                :key="claim.id"
                class="claim-line"
              >
                <CheckCircleOutlined />
                <div>
                  <p>{{ claim.text }}</p>
                  <span>置信度 {{ confidenceText(claim.confidence) }}</span>
                </div>
              </article>
            </div>
            <div class="report-section">
              <header class="section-heading compact">
                <span>限制条件</span>
                <h2>主要风险</h2>
              </header>
              <article
                v-for="claim in riskClaims"
                :key="claim.id"
                class="claim-line risk"
              >
                <WarningOutlined />
                <div>
                  <p>{{ claim.text }}</p>
                  <span>置信度 {{ confidenceText(claim.confidence) }}</span>
                </div>
              </article>
              <p v-if="!riskClaims.length" class="empty-copy">
                未生成额外模型风险结论，确定性数据警告见页面顶部。
              </p>
            </div>
          </section>

          <section class="report-section">
            <header class="section-heading">
              <span>关键差异</span>
              <h2>最影响当前决策的维度</h2>
            </header>
            <div class="difference-list">
              <article
                v-for="difference in differences"
                :key="difference.dimension_code"
              >
                <span>{{ difference.dimension_name }}</span>
                <p>{{ difference.claim?.text }}</p>
              </article>
            </div>
          </section>

          <section class="report-section">
            <header class="section-heading">
              <span>完整对比</span>
              <h2>商品事实与样本范围</h2>
            </header>
            <div class="product-report-grid">
              <article v-for="product in products" :key="product.id">
                <div class="product-report-heading">
                  <div>
                    <span>{{ product.brand ?? '品牌信息缺失' }}</span>
                    <h3>{{ product.title }}</h3>
                  </div>
                  <strong>{{ priceText(product) }}</strong>
                </div>
                <dl>
                  <div>
                    <dt>店铺</dt>
                    <dd>{{ product.shop_name ?? '缺失' }}</dd>
                  </div>
                  <div>
                    <dt>有效评论</dt>
                    <dd>{{ product.review_count }}</dd>
                  </div>
                  <div>
                    <dt>规格</dt>
                    <dd>
                      {{
                        Object.entries(product.specifications)
                          .map(([key, value]) => `${key} ${value}`)
                          .join('、') || '缺失'
                      }}
                    </dd>
                  </div>
                  <div>
                    <dt>售后</dt>
                    <dd>{{ product.after_sales.join('、') || '缺失' }}</dd>
                  </div>
                </dl>
              </article>
            </div>

            <div class="dimension-table-wrap">
              <table class="dimension-table">
                <thead>
                  <tr>
                    <th>维度</th>
                    <th v-for="product in products" :key="product.id">
                      {{ product.title }}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="dimension in dimensions" :key="dimension.id">
                    <th>{{ dimension.name }}</th>
                    <td v-for="product in products" :key="product.id">
                      {{ dimensionMetricText(product, dimension) }}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </section>

          <section class="report-section">
            <header class="section-heading">
              <span>证据说明</span>
              <h2>结论来源与置信度</h2>
            </header>
            <div class="evidence-list">
              <article v-for="claim in report.claims" :key="claim.id">
                <header>
                  <span>{{ claimTypeLabel(claim) }}</span>
                  <strong>{{ confidenceText(claim.confidence) }}</strong>
                </header>
                <p>{{ claim.text }}</p>
                <div class="source-list">
                  <span v-for="source in claim.source_refs" :key="`${source.type}-${source.id}-${source.field ?? source.evidence}`">
                    <DatabaseOutlined />
                    {{ sourceLabel(source) }}
                  </span>
                </div>
              </article>
            </div>
            <footer class="report-disclaimer">
              <FileTextOutlined />
              <span>
                本报告仅基于当前商品快照、已获取评论和用户偏好。代表性评论不代表所有消费者体验。
              </span>
            </footer>
          </section>
        </template>
      </a-spin>
    </main>
  </div>
</template>

<style scoped>
.report-workspace {
  max-width: 1080px;
}

.warning-list {
  margin: 0;
  padding-left: 18px;
}

.summary-band {
  display: grid;
  align-items: center;
  border-top: 2px solid var(--ink);
  background: var(--surface);
  padding: 28px;
  grid-template-columns: 42px minmax(0, 1fr) auto;
  gap: 18px;
}

.summary-mark {
  display: grid;
  width: 42px;
  height: 42px;
  place-items: center;
  border: 1px solid var(--positive);
  border-radius: 50%;
  color: var(--positive);
}

.section-kicker,
.section-heading span,
.scenario-item > span,
.difference-list article > span,
.product-report-heading span,
.evidence-list header span {
  color: var(--positive);
  font-size: 10px;
  font-weight: 800;
}

.summary-main h2 {
  margin: 5px 0 8px;
  font-family: Georgia, "Noto Serif SC", serif;
  font-size: 25px;
}

.summary-main p,
.scenario-item p,
.claim-line p,
.difference-list p,
.evidence-list p {
  margin: 0;
  color: var(--muted);
  font-size: 12px;
  line-height: 1.7;
}

.confidence-block {
  min-width: 110px;
  border-left: 1px solid var(--line);
  padding-left: 22px;
  text-align: right;
}

.confidence-block span {
  display: block;
  color: var(--muted);
  font-size: 10px;
}

.confidence-block strong {
  display: block;
  margin-top: 5px;
  font-family: Georgia, serif;
  font-size: 28px;
}

.report-section {
  margin-top: 22px;
  border-top: 2px solid var(--ink);
  background: var(--surface);
  padding: 24px;
}

.section-heading {
  margin-bottom: 18px;
}

.section-heading h2 {
  margin: 4px 0 0;
  font-size: 18px;
}

.section-heading.compact h2 {
  font-size: 16px;
}

.scenario-grid,
.product-report-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}

.scenario-item,
.product-report-grid > article,
.evidence-list > article {
  min-width: 0;
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 17px;
}

.scenario-item strong {
  display: block;
  margin: 7px 0;
  font-size: 15px;
}

.reason-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 22px;
}

.reason-grid .report-section {
  margin-top: 22px;
}

.claim-line {
  display: grid;
  align-items: flex-start;
  border-top: 1px solid var(--line);
  padding: 13px 0;
  color: var(--positive);
  grid-template-columns: 20px minmax(0, 1fr);
  gap: 9px;
}

.claim-line:first-of-type {
  border-top: 0;
}

.claim-line.risk {
  color: var(--danger);
}

.claim-line span,
.empty-copy {
  color: var(--muted);
  font-size: 10px;
}

.empty-copy {
  margin: 0;
}

.difference-list {
  display: grid;
  border-top: 1px solid var(--line);
}

.difference-list article {
  display: grid;
  border-bottom: 1px solid var(--line);
  padding: 15px 0;
  grid-template-columns: minmax(100px, 0.28fr) minmax(0, 1fr);
  gap: 20px;
}

.product-report-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
}

.product-report-heading h3 {
  margin: 5px 0 0;
  font-size: 16px;
}

.product-report-heading strong {
  color: var(--positive);
  font-family: Georgia, serif;
  font-size: 19px;
  white-space: nowrap;
}

.product-report-grid dl {
  display: grid;
  margin: 17px 0 0;
  gap: 9px;
}

.product-report-grid dl > div {
  display: grid;
  grid-template-columns: 70px minmax(0, 1fr);
  gap: 10px;
}

.product-report-grid dt,
.product-report-grid dd {
  margin: 0;
  font-size: 11px;
  line-height: 1.5;
}

.product-report-grid dt {
  color: var(--muted);
}

.dimension-table-wrap {
  max-width: 100%;
  margin-top: 20px;
  overflow-x: auto;
}

.dimension-table {
  width: 100%;
  min-width: 680px;
  border-collapse: collapse;
}

.dimension-table th,
.dimension-table td {
  border-bottom: 1px solid var(--line);
  padding: 11px 12px;
  font-size: 11px;
  text-align: left;
}

.dimension-table thead th {
  background: var(--surface-subtle);
  color: var(--muted);
}

.dimension-table tbody th {
  color: var(--ink);
  font-weight: 700;
}

.evidence-list {
  display: grid;
  gap: 12px;
}

.evidence-list header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 7px;
}

.evidence-list header strong {
  font-family: Georgia, serif;
}

.source-list {
  display: flex;
  flex-wrap: wrap;
  margin-top: 12px;
  gap: 7px;
}

.source-list span {
  display: inline-flex;
  align-items: center;
  border: 1px solid var(--line);
  border-radius: 4px;
  background: var(--surface-subtle);
  padding: 5px 8px;
  color: var(--muted);
  font-size: 10px;
  gap: 5px;
}

.report-disclaimer {
  display: flex;
  align-items: flex-start;
  margin-top: 18px;
  border-top: 1px solid var(--line);
  padding-top: 15px;
  color: var(--muted);
  font-size: 10px;
  line-height: 1.6;
  gap: 8px;
}

@media (max-width: 720px) {
  .summary-band {
    align-items: flex-start;
    padding: 20px 16px;
    grid-template-columns: 36px minmax(0, 1fr);
  }

  .summary-mark {
    width: 36px;
    height: 36px;
  }

  .summary-main h2 {
    font-size: 21px;
  }

  .confidence-block {
    grid-column: 2;
    min-width: 0;
    border-top: 1px solid var(--line);
    border-left: 0;
    padding-top: 12px;
    padding-left: 0;
    text-align: left;
  }

  .confidence-block strong {
    font-size: 23px;
  }

  .scenario-grid,
  .product-report-grid,
  .reason-grid {
    grid-template-columns: 1fr;
  }

  .report-section {
    padding: 20px 14px;
  }

  .difference-list article {
    grid-template-columns: 1fr;
    gap: 6px;
  }
}
</style>
