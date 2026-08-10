// M1-C 统一请求边界行为测试。by AI.Coding

import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, requestJson } from './request'

describe('requestJson', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('返回成功 JSON 并为请求设置 JSON 头', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: 'ok' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    await expect(
      requestJson<{ status: string }>('/api/example', {
        method: 'POST',
        body: JSON.stringify({ value: 1 }),
      }),
    ).resolves.toEqual({ status: 'ok' })
    const headers = new Headers(fetchMock.mock.calls[0]?.[1]?.headers)
    expect(headers.get('Accept')).toBe('application/json')
    expect(headers.get('Content-Type')).toBe('application/json')
  })

  it('把 ProblemDetails 转换为稳定 ApiError', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({
            title: '当前状态存在冲突',
            status: 409,
            code: 'DOMAIN_CONFLICT',
            detail: '当前任务状态不允许操作',
            trace_id: 'trace-1',
            field_errors: [],
            metadata: {},
          }),
          {
            status: 409,
            headers: { 'Content-Type': 'application/problem+json' },
          },
        ),
      ),
    )

    try {
      await requestJson('/api/example')
      expect.fail('请求应抛出 ApiError')
    } catch (error) {
      expect(error).toBeInstanceOf(ApiError)
      const apiError = error as ApiError
      expect(apiError.status).toBe(409)
      expect(apiError.code).toBe('DOMAIN_CONFLICT')
      expect(apiError.message).toBe('当前任务状态不允许操作')
      expect(apiError.traceId).toBe('trace-1')
    }
  })
})
