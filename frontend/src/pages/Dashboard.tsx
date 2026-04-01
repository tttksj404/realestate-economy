import RegionMap from '@/components/RegionMap'
import Skeleton from '@/components/Skeleton'
import { useEconomyOverview, useMacroInterpretation } from '@/hooks/useEconomyData'
import { toDisplayIndicators, INDICATOR_META } from '@/utils/indicators'
import type { SignalType } from '@/types'
import { AlertCircle, Brain, RefreshCw } from 'lucide-react'
import { useMemo } from 'react'
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, Legend } from 'recharts'

function signalText(signal: SignalType): string {
  if (signal === 'boom') {
    return '호황'
  }
  if (signal === 'slump') {
    return '침체'
  }
  return '보통'
}

function RegionComparisonChart({ regions }: { regions: { region_code: string; region_name: string; confidence: number; indicators: { name: string; value: number | string }[] }[] }) {
  const chartData = regions.map((r) => {
    const saleIdx = r.indicators.find((i) => i.name === 'sale_index_change')
    const txChange = r.indicators.find((i) => i.name === 'tx_count_change')
    const supplyDemand = r.indicators.find((i) => i.name === 'supply_demand')
    return {
      name: r.region_name.replace(/특별시|광역시|특별자치시|도/g, ''),
      매매지수변동: typeof saleIdx?.value === 'number' ? saleIdx.value : 0,
      거래량변동: typeof txChange?.value === 'number' ? txChange.value : 0,
      수급동향: typeof supplyDemand?.value === 'number' ? supplyDemand.value - 100 : 0,
    }
  })

  if (chartData.length === 0) return null

  return (
    <section className="rounded-2xl border border-slate-700/50 bg-slate-800/60 p-4">
      <h2 className="mb-3 text-sm font-semibold text-slate-200">지역별 비교 차트</h2>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={chartData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
          <XAxis dataKey="name" tick={{ fill: '#94a3b8', fontSize: 12 }} />
          <YAxis tick={{ fill: '#94a3b8', fontSize: 12 }} />
          <Tooltip contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #475569', borderRadius: '8px', color: '#e2e8f0' }} />
          <Legend wrapperStyle={{ color: '#94a3b8' }} />
          <Bar dataKey="매매지수변동" fill="#60a5fa" radius={[4, 4, 0, 0]} />
          <Bar dataKey="거래량변동" fill="#fbbf24" radius={[4, 4, 0, 0]} />
          <Bar dataKey="수급동향" fill="#34d399" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </section>
  )
}

function NationalIndicators({ overview }: { overview?: { national_avg_indicators?: Record<string, number | null> } }) {
  const indicators = overview?.national_avg_indicators
  if (!indicators) return null

  const cards = toDisplayIndicators(indicators as Record<string, number | null | undefined>)
  const meta = Object.fromEntries(INDICATOR_META.map((m) => [m.key, m]))

  const healthBorder = { good: 'border-emerald-700/50', neutral: 'border-slate-700/50', bad: 'border-rose-700/50' }
  const healthBg = { good: 'bg-emerald-950/20', neutral: 'bg-slate-800/70', bad: 'bg-rose-950/20' }
  const healthText = { good: 'text-emerald-400', neutral: 'text-slate-300', bad: 'text-rose-400' }

  return (
    <section>
      <h2 className="mb-3 text-sm font-semibold text-slate-300">전국 평균 6개 핵심 지표</h2>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {cards.map((card) => {
          const m = meta[card.name]
          return (
            <div key={card.name} className={`rounded-xl border p-4 ${healthBorder[card.health]} ${healthBg[card.health]}`}>
              <div className="mb-2 flex items-center justify-between">
                <span className="text-xs text-slate-400">{m?.label ?? card.name}</span>
                <span className={`text-xs font-semibold ${healthText[card.health]}`}>
                  {card.health === 'good' ? '호황' : card.health === 'bad' ? '침체' : '보통'}
                </span>
              </div>
              <div className="flex items-end gap-1">
                <span className="text-xl font-bold text-slate-100">
                  {typeof card.value === 'number' ? card.value.toLocaleString() : card.value}
                </span>
                {card.unit && <span className="pb-0.5 text-xs text-slate-400">{card.unit}</span>}
              </div>
              <p className="mt-1 text-xs text-slate-500">{card.description}</p>
            </div>
          )
        })}
      </div>
    </section>
  )
}

function MacroPanel() {
  const { data: macro, isLoading, isError } = useMacroInterpretation()

  if (isLoading) {
    return <Skeleton className="h-48" />
  }

  if (isError || !macro) return null

  const signalColor = {
    boom: 'border-emerald-700/50 bg-emerald-950/10',
    normal: 'border-amber-700/50 bg-amber-950/10',
    slump: 'border-rose-700/50 bg-rose-950/10',
  }[macro.overall_signal === '호황' ? 'boom' : macro.overall_signal === '침체' ? 'slump' : 'normal']

  return (
    <section className={`rounded-2xl border p-5 ${signalColor}`}>
      <div className="mb-3 flex items-center gap-2">
        <Brain size={18} className="text-blue-400" />
        <h2 className="text-sm font-semibold text-slate-200">AI 거시경제 해석</h2>
        <span className="ml-auto text-xs text-slate-500">{macro.period} 기준</span>
      </div>
      <div className="space-y-2">
        {macro.interpretation.split('\n').filter(Boolean).map((line, i) => (
          <p key={`macro-${i}`} className="text-sm leading-relaxed text-slate-300">
            {line}
          </p>
        ))}
      </div>
    </section>
  )
}

export default function Dashboard() {
  const { data, isLoading, isError, refetch, isFetching } = useEconomyOverview()

  const stats = useMemo(() => {
    const regions = data?.regions ?? []
    const boom = regions.filter((r) => r.signal === 'boom').length
    const normal = regions.filter((r) => r.signal === 'normal').length
    const slump = regions.filter((r) => r.signal === 'slump').length

    return { boom, normal, slump }
  }, [data])

  if (isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-28" />
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          {Array.from({ length: 9 }).map((_, index) => (
            <Skeleton key={`card-${index}`} className="h-28" />
          ))}
        </div>
      </div>
    )
  }

  if (isError) {
    return (
      <div className="mx-auto mt-12 max-w-lg rounded-2xl border border-red-800/40 bg-red-950/20 p-6 text-center">
        <AlertCircle className="mx-auto text-red-400" />
        <p className="mt-2 text-sm text-red-200">대시보드 데이터를 불러오지 못했습니다.</p>
        <button onClick={() => refetch()} className="mt-4 rounded-xl bg-red-600 px-4 py-2 text-sm text-white">
          다시 시도
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">부동산 경제 대시보드</h1>
          <p className="mt-1 text-sm text-slate-400">매물과 가격 지표 기반 전국 경기 신호</p>
        </div>
        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className="inline-flex items-center gap-2 rounded-xl border border-slate-700/60 bg-slate-800/70 px-3 py-2 text-sm text-slate-200 disabled:opacity-50"
        >
          <RefreshCw size={14} className={isFetching ? 'animate-spin' : ''} />
          새로고침
        </button>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <div className="rounded-2xl border border-emerald-700/40 bg-emerald-950/20 p-4">
          <p className="text-xs text-emerald-200/80">호황 지역</p>
          <p className="mt-2 text-2xl font-bold text-emerald-300">{stats.boom}</p>
        </div>
        <div className="rounded-2xl border border-amber-700/40 bg-amber-950/20 p-4">
          <p className="text-xs text-amber-200/80">보통 지역</p>
          <p className="mt-2 text-2xl font-bold text-amber-300">{stats.normal}</p>
        </div>
        <div className="rounded-2xl border border-rose-700/40 bg-rose-950/20 p-4">
          <p className="text-xs text-rose-200/80">침체 지역</p>
          <p className="mt-2 text-2xl font-bold text-rose-300">{stats.slump}</p>
        </div>
      </div>

      <section>
        <h2 className="mb-3 text-sm font-semibold text-slate-300">지역별 신호 카드</h2>
        <RegionMap signals={data?.regions} isLoading={isLoading} />
      </section>

      <NationalIndicators overview={data} />

      <MacroPanel />

      <RegionComparisonChart regions={data?.regions ?? []} />

      <section className="rounded-2xl border border-slate-700/50 bg-slate-800/60 p-4">
        <h2 className="mb-3 text-sm font-semibold text-slate-200">신호 요약</h2>
        <div className="space-y-2">
          {(data?.regions ?? []).map((region) => (
            <div key={region.region_code} className="flex items-center justify-between rounded-lg bg-slate-900/40 px-3 py-2">
              <span className="text-sm text-slate-200">{region.region_name}</span>
              <span className="text-xs text-slate-400">
                {signalText(region.signal)} · 신뢰도 {region.confidence}%
              </span>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}

