export type SignalType = 'boom' | 'normal' | 'slump'
export type PropertyType = '아파트' | '빌라' | '오피스텔' | '단독주택' | '상가'

export interface IndicatorData {
  name: string
  value: number | string
  unit?: string
  change?: number
  trend?: 'up' | 'down' | 'stable'
  description?: string
}

export interface RegionSignal {
  region_code: string
  region_name: string
  signal: SignalType
  confidence: number
  summary: string
  indicators: IndicatorData[]
}

export interface EconomyOverview {
  regions: RegionSignal[]
}

export interface Listing {
  id: string
  type: PropertyType
  region: string
  district?: string
  price: number
  area: number
  floor?: number
  total_floors?: number
  listed_at: string
  address?: string
  description?: string
}

export interface PriceData {
  period: string
  avg_price: number
  median_price: number
  transaction_count: number
  property_type?: PropertyType
}

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

export interface ListingsResponse {
  listings: Listing[]
  total: number
  page: number
  per_page?: number
}

export interface PricesResponse {
  prices: PriceData[]
}

export interface Region {
  code: string
  name: string
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
  isStreaming?: boolean
}

export interface ChatRequest {
  message: string
  region?: string
  history?: Array<{ role: string; content: string }>
}

export interface TokenEvent {
  content: string
}

