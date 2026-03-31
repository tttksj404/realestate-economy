import axios from 'axios'
import type {
  EconomyOverview,
  RegionDetail,
  ListingsResponse,
  PricesResponse,
  Region,
  ChatRequest,
  TokenEvent,
} from '@/types'

// Axios instance
export const apiClient = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Error interceptor
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response) {
      const status = error.response.status
      const message = error.response.data?.detail || error.response.data?.message || '서버 오류가 발생했습니다.'
      if (status === 404) {
        console.error(`[API 404] ${error.config?.url}: ${message}`)
      } else if (status >= 500) {
        console.error(`[API ${status}] 서버 오류: ${message}`)
      } else {
        console.error(`[API ${status}] ${message}`)
      }
    } else if (error.request) {
      console.error('[API] 서버에 연결할 수 없습니다. 백엔드 서버가 실행 중인지 확인하세요.')
    }
    return Promise.reject(error)
  }
)

// API functions
export async function getEconomyOverview(): Promise<EconomyOverview> {
  const { data } = await apiClient.get<EconomyOverview>('/economy/overview')
  return data
}

export async function getRegionDetail(regionCode: string): Promise<RegionDetail> {
  const { data } = await apiClient.get<RegionDetail>(`/economy/${regionCode}`)
  return data
}

export async function getRegions(): Promise<Region[]> {
  const { data } = await apiClient.get<Region[]>('/regions')
  return data
}

export async function getRegionListings(
  regionCode: string,
  page = 1,
  propertyType?: string
): Promise<ListingsResponse> {
  const params: Record<string, string | number> = { page }
  if (propertyType) params.type = propertyType
  const { data } = await apiClient.get<ListingsResponse>(`/regions/${regionCode}/listings`, { params })
  return data
}

export async function getRegionPrices(regionCode: string): Promise<PricesResponse> {
  const { data } = await apiClient.get<PricesResponse>(`/regions/${regionCode}/prices`)
  return data
}

// SSE chat streaming using fetch + ReadableStream
export async function streamChat(
  request: ChatRequest,
  onToken: (token: TokenEvent) => void,
  onDone: () => void,
  onError: (err: Error) => void
): Promise<void> {
  try {
    const response = await fetch('/api/v1/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
      },
      body: JSON.stringify(request),
    })

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`)
    }

    if (!response.body) {
      throw new Error('Response body is empty')
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() ?? ''

      for (const line of lines) {
        const trimmed = line.trim()
        if (!trimmed) continue

        if (trimmed.startsWith('event:')) {
          // event type line — skip, handled by next data line
          continue
        }

        if (trimmed.startsWith('data:')) {
          const jsonStr = trimmed.slice(5).trim()
          if (jsonStr === '[DONE]') {
            onDone()
            return
          }
          try {
            const parsed = JSON.parse(jsonStr) as TokenEvent
            onToken(parsed)
          } catch {
            // ignore non-JSON lines
          }
        }
      }
    }

    onDone()
  } catch (err) {
    onError(err instanceof Error ? err : new Error(String(err)))
  }
}
