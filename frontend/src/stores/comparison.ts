// M1-C 对比任务跨页面状态与服务端恢复入口。by AI.Coding

import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import {
  confirmComparisonProducts,
  confirmComparisonDimensions,
  createComparison,
  generateComparisonDimensions,
  getComparison,
  getComparisonAnalysisProgress,
  getComparisonReport,
  getComparisonDimensions,
  parseComparison,
  retryComparisonAnalysis,
  startComparisonAnalysis,
  updateComparisonPreferences,
  type AnalysisProgress,
  type ComparisonDetail,
  type ComparisonReport,
  type ConfirmDimensionsPayload,
  type ConfirmProductsPayload,
  type CreateComparisonPayload,
  type DimensionSet,
  type UpdatePreferencesPayload,
} from '@/api/comparisons'
import { ApiError } from '@/api/request'

const LAST_COMPARISON_KEY = 'shopping-assistant:last-comparison-id'

type ComparisonAction =
  | 'creating'
  | 'parsing'
  | 'loading'
  | 'confirming'
  | 'saving'
  | 'generating-dimensions'
  | 'loading-dimensions'
  | 'confirming-dimensions'
  | 'starting-analysis'
  | 'loading-progress'
  | 'retrying-analysis'
  | 'loading-report'

export const useComparisonStore = defineStore('comparison', () => {
  /** 管理当前任务详情、请求状态和仅含任务 ID 的恢复提示。by AI.Coding */
  const comparison = ref<ComparisonDetail | null>(null)
  const dimensionSet = ref<DimensionSet | null>(null)
  const analysisProgress = ref<AnalysisProgress | null>(null)
  const report = ref<ComparisonReport | null>(null)
  const action = ref<ComparisonAction | null>(null)
  const error = ref<ApiError | null>(null)
  const lastComparisonId = ref(localStorage.getItem(LAST_COMPARISON_KEY))
  const busy = computed(() => action.value !== null)

  async function createAndParse(payload: CreateComparisonPayload): Promise<ComparisonDetail> {
    /** 创建草稿后立即解析，并在解析失败时保留已创建任务供恢复。by AI.Coding */
    error.value = null
    action.value = 'creating'
    try {
      const created = await createComparison(payload, crypto.randomUUID())
      comparison.value = created
      rememberComparison(created.id)
      action.value = 'parsing'
      const parsed = await parseComparison(created.id)
      comparison.value = parsed
      return parsed
    } catch (cause) {
      error.value = normalizeError(cause)
      throw error.value
    } finally {
      action.value = null
    }
  }

  async function loadComparison(comparisonId: string): Promise<ComparisonDetail> {
    /** 按路由任务 ID 重新加载详情，页面刷新不依赖 Pinia 内存。by AI.Coding */
    error.value = null
    action.value = 'loading'
    try {
      const loaded = await getComparison(comparisonId)
      comparison.value = loaded
      rememberComparison(loaded.id)
      return loaded
    } catch (cause) {
      error.value = normalizeError(cause)
      throw error.value
    } finally {
      action.value = null
    }
  }

  async function confirmProducts(
    comparisonId: string,
    payload: ConfirmProductsPayload,
  ): Promise<ComparisonDetail> {
    /** 原子提交全部商品选择并更新当前聚合。by AI.Coding */
    error.value = null
    action.value = 'confirming'
    try {
      const confirmed = await confirmComparisonProducts(comparisonId, payload)
      comparison.value = confirmed
      return confirmed
    } catch (cause) {
      error.value = normalizeError(cause)
      throw error.value
    } finally {
      action.value = null
    }
  }

  async function savePreferences(
    comparisonId: string,
    payload: UpdatePreferencesPayload,
  ): Promise<ComparisonDetail> {
    /** 保存整体偏好并保留服务端规范化后的恢复结构。by AI.Coding */
    error.value = null
    action.value = 'saving'
    try {
      const updated = await updateComparisonPreferences(comparisonId, payload)
      comparison.value = updated
      return updated
    } catch (cause) {
      error.value = normalizeError(cause)
      throw error.value
    } finally {
      action.value = null
    }
  }

  async function generateDimensions(comparisonId: string): Promise<DimensionSet> {
    /** 生成候选并保存服务端返回的稳定维度集合。by AI.Coding */
    error.value = null
    action.value = 'generating-dimensions'
    try {
      const generated = await generateComparisonDimensions(comparisonId)
      dimensionSet.value = generated
      return generated
    } catch (cause) {
      error.value = normalizeError(cause)
      throw error.value
    } finally {
      action.value = null
    }
  }

  async function loadDimensions(comparisonId: string): Promise<DimensionSet> {
    /** 从服务端恢复候选、选择状态和顺序。by AI.Coding */
    error.value = null
    action.value = 'loading-dimensions'
    try {
      const loaded = await getComparisonDimensions(comparisonId)
      dimensionSet.value = loaded
      return loaded
    } catch (cause) {
      error.value = normalizeError(cause)
      throw error.value
    } finally {
      action.value = null
    }
  }

  async function confirmDimensions(
    comparisonId: string,
    payload: ConfirmDimensionsPayload,
  ): Promise<DimensionSet> {
    /** 确认当前有序维度集合并保存 queued 状态。by AI.Coding */
    error.value = null
    action.value = 'confirming-dimensions'
    try {
      const confirmed = await confirmComparisonDimensions(comparisonId, payload)
      dimensionSet.value = confirmed
      if (comparison.value?.id === comparisonId) {
        comparison.value = { ...comparison.value, status: confirmed.status, progress: 0 }
      }
      return confirmed
    } catch (cause) {
      error.value = normalizeError(cause)
      throw error.value
    } finally {
      action.value = null
    }
  }

  async function startAnalysis(comparisonId: string): Promise<AnalysisProgress> {
    /** 投递 queued 任务并保存服务端返回的初始进度。by AI.Coding */
    error.value = null
    action.value = 'starting-analysis'
    try {
      const progress = await startComparisonAnalysis(comparisonId)
      analysisProgress.value = progress
      return progress
    } catch (cause) {
      error.value = normalizeError(cause)
      throw error.value
    } finally {
      action.value = null
    }
  }

  async function loadAnalysisProgress(comparisonId: string): Promise<AnalysisProgress> {
    /** 轮询服务端持久化分析进度。by AI.Coding */
    error.value = null
    action.value = 'loading-progress'
    try {
      const progress = await getComparisonAnalysisProgress(comparisonId)
      analysisProgress.value = progress
      if (comparison.value?.id === comparisonId) {
        comparison.value = {
          ...comparison.value,
          status: progress.status,
          progress: progress.progress,
        }
      }
      return progress
    } catch (cause) {
      error.value = normalizeError(cause)
      throw error.value
    } finally {
      action.value = null
    }
  }

  async function retryAnalysis(comparisonId: string): Promise<AnalysisProgress> {
    /** 把可重试失败重新排队并保存最新进度。by AI.Coding */
    error.value = null
    action.value = 'retrying-analysis'
    try {
      const progress = await retryComparisonAnalysis(comparisonId)
      analysisProgress.value = progress
      return progress
    } catch (cause) {
      error.value = normalizeError(cause)
      throw error.value
    } finally {
      action.value = null
    }
  }

  async function loadReport(comparisonId: string): Promise<ComparisonReport> {
    /** 从服务端恢复最新已发布报告。by AI.Coding */
    error.value = null
    action.value = 'loading-report'
    try {
      const loaded = await getComparisonReport(comparisonId)
      report.value = loaded
      return loaded
    } catch (cause) {
      error.value = normalizeError(cause)
      throw error.value
    } finally {
      action.value = null
    }
  }

  function clearError(): void {
    /** 清除页面已展示的请求错误。by AI.Coding */
    error.value = null
  }

  function rememberComparison(comparisonId: string): void {
    /** 只持久化任务 ID，不把原始商品链接或偏好正文写入浏览器缓存。by AI.Coding */
    lastComparisonId.value = comparisonId
    localStorage.setItem(LAST_COMPARISON_KEY, comparisonId)
  }

  return {
    comparison,
    dimensionSet,
    analysisProgress,
    report,
    action,
    error,
    busy,
    lastComparisonId,
    createAndParse,
    loadComparison,
    confirmProducts,
    savePreferences,
    generateDimensions,
    loadDimensions,
    confirmDimensions,
    startAnalysis,
    loadAnalysisProgress,
    retryAnalysis,
    loadReport,
    clearError,
  }
})

function normalizeError(cause: unknown): ApiError {
  /** 把未知前端异常收敛为页面可显示的 ApiError。by AI.Coding */
  if (cause instanceof ApiError) {
    return cause
  }
  return new ApiError('操作失败，请稍后重试。', 0, 'CLIENT_ERROR', null)
}
