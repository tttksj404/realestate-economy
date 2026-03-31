// Signal types
export type SignalType = 'boom' | 'normal' | 'slump'

// Indicator data
export interface IndicatorData {
  name: string
  value: number | string
  unit?: string
  change?: number
  trend?: 'up' | 'down' | 'stable'
  description?: string
}

// Region signal summary (from overview)
export interface RegionSignal {
  region_code: string
  region_name: string
  signal: SignalType
  confidence: number // 0-100
  summary: string
  indicators: IndicatorData[]
}

// Economy overview response
export interface EconomyOverview {
  regions: RegionSignal[]
}

// Listing item
export interface Listing {
  id: string
  type: '아파트' | '빌라' | '오피스텔' | '단독주택' | '상가'
  region: string
  district?: string
  price: number // in 만원
  area: number // in m²
  floor?: number
  total_floors?: number
  listed_at: string // ISO date
  address?: string
  description?: string
}

// Price data point
export interface PriceData {
  period: string // e.g. "2024-01"
  avg_price: number
  median_price: number
  transaction_count: number
  property_type?: string
}

// Region detail response
export interface RegionDetail {
  region_code: string
  region_name: string
  signal: SignalType
  confidence: number
  summary: string
  indicators: IndicatorData[]
  recent_listings: Listing[]
  price_trend: PriceData[]
}

// Paginated listings response
export interface ListingsResponse {
  listings: Listing[]
  total: number
  page: number
  per_page?: number
}

// Prices response
export interface PricesResponse {
  prices: PriceData[]
}

// Region info
export interface Region {
  code: string
  name: string
}

// Chat message
export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
  isStreaming?: boolean
}

// Chat request
export interface ChatRequest {
  message: string
  region?: string
  history?: { role: string; content: string }[]
}

// SSE token event
export interface TokenEvent {
  content: string
}
