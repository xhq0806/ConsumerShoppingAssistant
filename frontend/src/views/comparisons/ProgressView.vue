<script setup lang="ts">
// M1-E 异步评论采集进度、轮询恢复和失败重试页面。by AI.Coding

import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  CheckCircleOutlined,
  ClockCircleOutlined,
  DatabaseOutlined,
  ReloadOutlined,
  SyncOutlined,
  WarningOutlined,
} from '@ant-design/icons-vue'
import AppHeader from '@/components/comparisons/AppHeader.vue'
import FlowSteps from '@/components/comparisons/FlowSteps.vue'
import type { AnalysisProgress } from '@/api/comparisons'
import { useComparisonStore } from '@/stores/comparison'

const POLL_INTERVAL_MS = 1000
const route = useRoute()
const router = useRouter()
const comparisonStore = useComparisonStore()
const comparisonId = computed(() => String(route.params.id))
const polling = ref(false)
let pollTimer: ReturnType<typeof setTimeout> | null = null

const progress = computed(() => comparisonStore.analysisProgress)
const busy = computed(() =>
  ['loading', 'starting-analysis', 'loading-progress', 'retrying-analysis'].includes(
    comparisonStore.action ?? '',
  ),
)
const stages = computed(() => [
  {
    key: 'queued',
    title: '任务排队',
    description: '等待异步 Worker 接收任务',
    state: stageState(0),
  },
  {
    key: 'fetching',
    title: '获取近期评论',
    description: `按近 ${comparisonStore.comparison?.review_window_days ?? 30} 天窗口获取`,
    state: stageState(1),
  },
  {
    key: 'cleaning',
    title: '清洗评论数据',
    description: '规范化、过滤和稳定去重',
    state: stageState(2),
  },
  {
    key: 'analysis',
    title: '后续分析',
    description: '主题、情感和指标将在下一里程碑执行',
    state: stageState(3),
  },
])

onMounted(initialize)
onBeforeUnmount(stopPolling)

async function initialize(): Promise<void> {
  /** 从路由任务 ID 恢复状态，queued 时执行一次幂等投递。by AI.Coding */
  try {
    const comparison = await comparisonStore.loadComparison(comparisonId.value)
    if (
      comparison.status === 'draft' ||
      comparison.status === 'parsing' ||
      comparison.status === 'awaiting_product_confirmation'
    ) {
      await router.replace({ name: 'comparison-confirm', params: { id: comparison.id } })
      return
    }
    if (comparison.status === 'awaiting_dimension_confirmation') {
      await router.replace({ name: 'comparison-dimensions', params: { id: comparison.id } })
      return
    }
    let current = await comparisonStore.loadAnalysisProgress(comparisonId.value)
    if (current.status === 'queued') {
      current = await comparisonStore.startAnalysis(comparisonId.value)
    }
    continuePolling(current)
  } catch {
    // 初次恢复遇到临时网络错误时继续轮询，避免只能依赖用户刷新。
    schedulePollingRetry()
  }
}

async function pollProgress(): Promise<void> {
  /** 查询一次服务端进度，并在未到边界时安排下一次轮询。by AI.Coding */
  try {
    let current = await comparisonStore.loadAnalysisProgress(comparisonId.value)
    if (current.status === 'queued') {
      current = await comparisonStore.startAnalysis(comparisonId.value)
    }
    continuePolling(current)
  } catch {
    schedulePollingRetry()
  }
}

function continuePolling(current: AnalysisProgress): void {
  /** 根据服务端 polling_complete 决定是否继续轮询。by AI.Coding */
  stopPolling()
  if (current.polling_complete) return
  polling.value = true
  pollTimer = setTimeout(pollProgress, POLL_INTERVAL_MS)
}

function stopPolling(): void {
  /** 清理页面卸载或终态后的轮询计时器。by AI.Coding */
  polling.value = false
  if (pollTimer !== null) {
    clearTimeout(pollTimer)
    pollTimer = null
  }
}

function schedulePollingRetry(): void {
  /** 临时请求或队列错误后继续轮询，直到服务端进入明确终态。by AI.Coding */
  stopPolling()
  polling.value = true
  pollTimer = setTimeout(pollProgress, POLL_INTERVAL_MS)
}

async function retryAnalysis(): Promise<void> {
  /** 重新排队可重试失败并恢复轮询。by AI.Coding */
  try {
    const current = await comparisonStore.retryAnalysis(comparisonId.value)
    continuePolling(current)
  } catch {
    // retry 可能已提交 queued 但投递失败；重新读取真源并继续幂等 start。
    try {
      const current = await comparisonStore.loadAnalysisProgress(comparisonId.value)
      continuePolling(current)
    } catch {
      schedulePollingRetry()
    }
  }
}

function stageState(index: number): 'done' | 'active' | 'pending' | 'failed' {
  /** 按持久化状态映射四个进度阶段。by AI.Coding */
  const status = progress.value?.status
  if (status === 'failed') {
    return index <= 1 ? 'failed' : 'pending'
  }
  const currentIndex =
    {
    queued: 0,
    fetching: 1,
    processing: 2,
    completed: 3,
    partially_completed: 3,
    }[status ?? 'queued'] ?? 0
  if (index < currentIndex) return 'done'
  if (index === currentIndex) return status === 'processing' && index === 2 ? 'done' : 'active'
  return 'pending'
}
</script>

<template>
  <div class="app-frame">
    <AppHeader />
    <FlowSteps :current="4" />

    <main class="workspace progress-workspace">
      <header class="workspace-heading">
        <div>
          <span class="eyebrow">M1-E / 异步任务</span>
          <h1>准备近期评论数据</h1>
          <p>任务 {{ comparisonId }}</p>
        </div>
        <span v-if="polling" class="polling-state">
          <SyncOutlined spin />
          自动更新
        </span>
      </header>

      <a-alert
        v-if="comparisonStore.error"
        class="workspace-alert"
        :description="comparisonStore.error.message"
        :message="comparisonStore.error.code"
        show-icon
        type="error"
      />

      <a-spin :spinning="busy && !progress">
        <section class="progress-summary">
          <div class="progress-copy">
            <span :class="['status-mark', `status-${progress?.status ?? 'queued'}`]">
              <CheckCircleOutlined v-if="progress?.status === 'processing'" />
              <WarningOutlined v-else-if="progress?.status === 'failed'" />
              <ClockCircleOutlined v-else />
            </span>
            <div>
              <strong>{{ progress?.message ?? '正在读取任务状态。' }}</strong>
              <span>{{ progress?.progress ?? 0 }}%</span>
            </div>
          </div>
          <a-progress
            :percent="progress?.progress ?? 0"
            :status="progress?.status === 'failed' ? 'exception' : 'active'"
            :show-info="false"
            stroke-color="#286f51"
          />
        </section>

        <section class="stage-list" aria-label="分析任务阶段">
          <article v-for="(stage, index) in stages" :key="stage.key">
            <span :class="['stage-icon', `stage-${stage.state}`]">
              <CheckCircleOutlined v-if="stage.state === 'done'" />
              <WarningOutlined v-else-if="stage.state === 'failed'" />
              <SyncOutlined v-else-if="stage.state === 'active'" spin />
              <span v-else>{{ index + 1 }}</span>
            </span>
            <div>
              <strong>{{ stage.title }}</strong>
              <p>{{ stage.description }}</p>
            </div>
          </article>
        </section>

        <section class="review-stats">
          <header>
            <DatabaseOutlined />
            <h2>评论样本</h2>
          </header>
          <dl>
            <div>
              <dt>Provider 获取</dt>
              <dd>{{ progress?.fetched_review_count ?? 0 }}</dd>
            </div>
            <div>
              <dt>清洗后有效</dt>
              <dd>{{ progress?.valid_review_count ?? 0 }}</dd>
            </div>
            <div>
              <dt>评论窗口</dt>
              <dd>近 {{ comparisonStore.comparison?.review_window_days ?? 30 }} 天</dd>
            </div>
          </dl>
        </section>

        <footer v-if="progress?.status === 'failed'" class="failure-actions">
          <span>评论采集未完成。</span>
          <a-button
            v-if="progress.can_retry"
            class="primary-command"
            :loading="comparisonStore.action === 'retrying-analysis'"
            type="primary"
            @click="retryAnalysis"
          >
            <ReloadOutlined />
            重新执行
          </a-button>
        </footer>
      </a-spin>
    </main>
  </div>
</template>

<style scoped>
.progress-workspace {
  max-width: 900px;
}

.polling-state {
  display: inline-flex;
  align-items: center;
  color: var(--positive);
  font-size: 12px;
  gap: 7px;
}

.progress-summary {
  border-top: 2px solid var(--ink);
  background: var(--surface);
  padding: 24px;
}

.progress-copy {
  display: flex;
  align-items: center;
  margin-bottom: 18px;
  gap: 14px;
}

.progress-copy > div {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  width: 100%;
  gap: 16px;
}

.progress-copy strong {
  font-size: 15px;
}

.progress-copy span {
  color: var(--muted);
  font-family: Georgia, serif;
  font-size: 20px;
}

.status-mark {
  display: grid;
  width: 38px;
  height: 38px;
  flex: 0 0 38px;
  place-items: center;
  border: 1px solid var(--line-strong);
  border-radius: 50%;
  color: var(--muted);
}

.status-processing {
  border-color: var(--positive);
  color: var(--positive);
}

.status-failed {
  border-color: var(--danger);
  color: var(--danger);
}

.stage-list {
  display: grid;
  margin-top: 18px;
  border-top: 2px solid var(--ink);
  background: var(--surface);
}

.stage-list article {
  display: grid;
  align-items: center;
  border-bottom: 1px solid var(--line);
  padding: 18px 24px;
  grid-template-columns: 34px minmax(0, 1fr);
  gap: 14px;
}

.stage-list strong {
  font-size: 13px;
}

.stage-list p {
  margin: 4px 0 0;
  color: var(--muted);
  font-size: 11px;
}

.stage-icon {
  display: grid;
  width: 30px;
  height: 30px;
  place-items: center;
  border: 1px solid var(--line-strong);
  border-radius: 50%;
  color: var(--muted);
  font-size: 11px;
}

.stage-done {
  border-color: var(--positive);
  color: var(--positive);
}

.stage-active {
  border-color: var(--accent);
  color: var(--accent);
}

.stage-failed {
  border-color: var(--danger);
  color: var(--danger);
}

.review-stats {
  margin-top: 18px;
  border-top: 2px solid var(--accent);
  background: var(--surface-subtle);
  padding: 22px 24px;
}

.review-stats header {
  display: flex;
  align-items: center;
  gap: 9px;
}

.review-stats h2 {
  margin: 0;
  font-size: 15px;
}

.review-stats dl {
  display: grid;
  margin: 18px 0 0;
  grid-template-columns: repeat(3, 1fr);
}

.review-stats dl > div {
  border-left: 1px solid var(--line);
  padding: 0 18px;
}

.review-stats dl > div:first-child {
  border-left: 0;
  padding-left: 0;
}

.review-stats dt {
  color: var(--muted);
  font-size: 11px;
}

.review-stats dd {
  margin: 6px 0 0;
  color: var(--ink);
  font-family: Georgia, "Noto Serif SC", serif;
  font-size: 24px;
}

.failure-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 18px;
  border: 1px solid rgb(184 67 54 / 25%);
  background: rgb(184 67 54 / 6%);
  padding: 15px 18px;
  color: var(--danger);
  font-size: 12px;
  gap: 16px;
}

@media (max-width: 600px) {
  .progress-summary,
  .stage-list article,
  .review-stats {
    padding-right: 14px;
    padding-left: 14px;
  }

  .review-stats dl {
    gap: 14px;
    grid-template-columns: 1fr;
  }

  .review-stats dl > div,
  .review-stats dl > div:first-child {
    border-top: 1px solid var(--line);
    border-left: 0;
    padding: 12px 0 0;
  }

  .review-stats dl > div:first-child {
    border-top: 0;
    padding-top: 0;
  }

  .failure-actions {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
