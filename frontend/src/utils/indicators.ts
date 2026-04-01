import type { IndicatorData } from '@/types'

/**
 * V2 지표 메타데이터
 * direction: 'higher_better' = 값이 높을수록 호황, 'lower_better' = 값이 낮을수록 호황
 * center: supply_demand처럼 기준점이 100인 경우
 */
interface IndicatorMeta {
  key: string
  label: string
  unit: string
  description: string
  direction: 'higher_better' | 'lower_better' | 'center'
  center?: number
  thresholds: { boom: number; recession: number }
}

const INDICATOR_META: IndicatorMeta[] = [
  {
    key: 'sale_index_change',
    label: '매매가격지수 변동',
    unit: '%',
    description: 'R-ONE 공식 아파트 매매지수 전월비',
    direction: 'higher_better',
    thresholds: { boom: 0.3, recession: -0.3 },
  },
  {
    key: 'jeonse_ratio',
    label: '전세가율',
    unit: '%',
    description: '전세평균가 / 매매평균가',
    direction: 'lower_better',
    thresholds: { boom: 55, recession: 75 },
  },
  {
    key: 'unsold_change',
    label: '미분양 증감률',
    unit: '%',
    description: '전월 대비 미분양 주택 수 변동',
    direction: 'lower_better',
    thresholds: { boom: -10, recession: 10 },
  },
  {
    key: 'tx_count_change',
    label: '거래량 변동률',
    unit: '%',
    description: '국토부 실거래 건수 전월비',
    direction: 'higher_better',
    thresholds: { boom: 10, recession: -10 },
  },
  {
    key: 'supply_demand',
    label: '매매수급동향',
    unit: '',
    description: '100 초과=수요우위, 100 미만=공급우위',
    direction: 'center',
    center: 100,
    thresholds: { boom: 105, recession: 95 },
  },
  {
    key: 'auction_change',
    label: '공매 증감률',
    unit: '%',
    description: '온비드 공매 물건 수 전월비',
    direction: 'lower_better',
    thresholds: { boom: -10, recession: 10 },
  },
]

function getTrend(
  value: number | null | undefined,
  meta: IndicatorMeta,
): 'up' | 'down' | 'stable' {
  if (value == null) return 'stable'

  if (meta.direction === 'center') {
    const c = meta.center ?? 100
    if (value > c + 2) return 'up'
    if (value < c - 2) return 'down'
    return 'stable'
  }

  if (value > 0.5) return 'up'
  if (value < -0.5) return 'down'
  return 'stable'
}

function getHealthColor(
  value: number | null | undefined,
  meta: IndicatorMeta,
): 'good' | 'neutral' | 'bad' {
  if (value == null) return 'neutral'

  const { boom, recession } = meta.thresholds
  if (meta.direction === 'higher_better') {
    if (value >= boom) return 'good'
    if (value <= recession) return 'bad'
  } else if (meta.direction === 'lower_better') {
    if (value <= boom) return 'good'
    if (value >= recession) return 'bad'
  } else {
    // center
    if (value >= meta.thresholds.boom) return 'good'
    if (value <= meta.thresholds.recession) return 'bad'
  }
  return 'neutral'
}

export interface DisplayIndicator extends IndicatorData {
  health: 'good' | 'neutral' | 'bad'
}

/**
 * 백엔드 flat object를 프론트 IndicatorData[] 배열로 변환
 */
export function toDisplayIndicators(
  raw: Record<string, number | null | undefined>,
): DisplayIndicator[] {
  return INDICATOR_META.map((meta) => {
    const value = raw[meta.key] ?? null
    const trend = getTrend(value, meta)
    const health = getHealthColor(value, meta)

    let change: number | undefined
    if (meta.direction === 'center' && value != null) {
      change = Math.round((value - (meta.center ?? 100)) * 100) / 100
    } else if (value != null) {
      change = value
    }

    return {
      name: meta.key,
      value: value != null ? Math.round(value * 100) / 100 : '-',
      unit: meta.unit,
      change,
      trend,
      description: meta.description,
      label: meta.label,
      health,
    } as DisplayIndicator & { label: string }
  })
}

export { INDICATOR_META }
