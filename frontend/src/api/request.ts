// M1-C 统一 JSON 请求、超时和 ProblemDetails 错误边界。by AI.Coding

export interface ProblemFieldError {
  field: string
  message: string
  error_type: string
}

export interface ProblemDetails {
  title: string
  status: number
  code: string
  detail: string
  trace_id: string
  field_errors: ProblemFieldError[]
  metadata: Record<string, unknown>
}

export class ApiError extends Error {
  /** 保存页面可稳定判断的状态、错误码和 trace ID。by AI.Coding */
  constructor(
    message: string,
    readonly status: number,
    readonly code: string,
    readonly traceId: string | null,
    readonly fieldErrors: ProblemFieldError[] = [],
    readonly metadata: Record<string, unknown> = {},
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

const REQUEST_TIMEOUT_MS = 15_000

export async function requestJson<ResponseT>(
  path: string,
  options: RequestInit = {},
): Promise<ResponseT> {
  /** 发送统一 JSON 请求并把服务端错误转换为 ApiError。by AI.Coding */
  const controller = new AbortController()
  const callerSignal = options.signal
  const abortFromCaller = () => controller.abort(callerSignal?.reason)
  callerSignal?.addEventListener('abort', abortFromCaller, { once: true })
  const timeout = window.setTimeout(() => controller.abort('timeout'), REQUEST_TIMEOUT_MS)
  const headers = new Headers(options.headers)
  headers.set('Accept', 'application/json')
  if (options.body !== undefined) {
    headers.set('Content-Type', 'application/json')
  }

  try {
    const response = await fetch(path, {
      ...options,
      headers,
      signal: controller.signal,
    })
    const payload = await readJson(response)
    if (!response.ok) {
      throw toApiError(response.status, payload)
    }
    return payload as ResponseT
  } catch (error) {
    if (error instanceof ApiError) {
      throw error
    }
    if (controller.signal.aborted) {
      const timedOut = !callerSignal?.aborted
      throw new ApiError(
        timedOut ? '请求超时，请稍后重试。' : '请求已取消。',
        timedOut ? 408 : 499,
        timedOut ? 'CLIENT_TIMEOUT' : 'REQUEST_ABORTED',
        null,
      )
    }
    throw new ApiError('无法连接服务，请检查本地 API 是否已启动。', 0, 'NETWORK_ERROR', null)
  } finally {
    window.clearTimeout(timeout)
    callerSignal?.removeEventListener('abort', abortFromCaller)
  }
}

async function readJson(response: Response): Promise<unknown> {
  /** 在空响应或无效 JSON 时返回空对象，避免泄露原始响应正文。by AI.Coding */
  const contentType = response.headers.get('Content-Type') ?? ''
  if (!contentType.includes('json')) {
    return {}
  }
  try {
    return await response.json()
  } catch {
    return {}
  }
}

function toApiError(status: number, payload: unknown): ApiError {
  /** 从未知响应中只提取 ProblemDetails 白名单字段。by AI.Coding */
  if (isProblemDetails(payload)) {
    return new ApiError(
      payload.detail,
      payload.status,
      payload.code,
      payload.trace_id,
      payload.field_errors,
      payload.metadata,
    )
  }
  return new ApiError('服务暂时无法处理请求。', status, 'HTTP_ERROR', null)
}

function isProblemDetails(value: unknown): value is ProblemDetails {
  /** 使用最小稳定字段识别服务端 ProblemDetails。by AI.Coding */
  if (typeof value !== 'object' || value === null) {
    return false
  }
  const problem = value as Partial<ProblemDetails>
  return (
    typeof problem.status === 'number' &&
    typeof problem.code === 'string' &&
    typeof problem.detail === 'string' &&
    typeof problem.trace_id === 'string' &&
    Array.isArray(problem.field_errors) &&
    typeof problem.metadata === 'object' &&
    problem.metadata !== null
  )
}
