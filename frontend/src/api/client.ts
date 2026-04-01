import type {
  EconomyOverview,
  RegionDetail,
  ListingsResponse,
  PricesResponse,
  Region,
  ChatRequest,
  TokenEvent,
} from '@/types'
import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1'

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response) {
      const status = error.response.status as number
      const message =
        (error.response.data?.detail as string | undefined) ??
        (error.response.data?.message as string | undefined) ??
        '요청을 처리하는 중 오류가 발생했습니다.'
      console.error(`[API ${status}] ${message}`)
    } else if (error.request) {
      console.error('[API] 서버에 연결할 수 없습니다. 백엔드 실행 상태를 확인하세요.')
    }
    return Promise.reject(error)
  }
)

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
  if (propertyType) {
    params.type = propertyType
  }

  const { data } = await apiClient.get<ListingsResponse>(`/regions/${regionCode}/listings`, { params })
  return data
}

export async function getRegionPrices(regionCode: string): Promise<PricesResponse> {
  const { data } = await apiClient.get<PricesResponse>(`/regions/${regionCode}/prices`)
  return data
}

export async function streamChat(
  request: ChatRequest,
  onToken: (token: TokenEvent) => void,
  onDone: () => void,
  onError: (err: Error) => void
): Promise<void> {
  try {
    const response = await fetch(`${API_BASE_URL}/chat`, {
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
      if (done) {
        break
      }

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() ?? ''

      for (const line of lines) {
        const trimmed = line.trim()
        if (!trimmed.startsWith('data:')) {
          continue
        }

        const payload = trimmed.slice(5).trim()
        if (payload === '[DONE]') {
          onDone()
          return
        }

        try {
          onToken(JSON.parse(payload) as TokenEvent)
        } catch {
          // Ignore malformed lines.
        }
      }
    }

    onDone()
  } catch (error) {
    onError(error instanceof Error ? error : new Error(String(error)))
  }
}

