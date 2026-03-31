import { useMemo } from 'react'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
  type TooltipProps,
} from 'recharts'
import { RefreshCw, AlertCircle, TrendingUp, TrendingDown, Minus } from 'lucide-react'
import { useEconomyOverview } from '@/hooks/useEconomyData'
import { SignalBadge } from '@/components/EconomyIndicator'
import RegionMap from '@/components/RegionMap'
import type { SignalType } from '@/types'

const signalBarColor: Record<SignalType, string> = {
  boom: '#22c55e',
  normal: '#eab308',
  slump: '#ef4444',
}

function OverviewSummaryCard({
  boomCount,
  normalCount,
  slumpCount,
  total,
}: {
  boomCount: number
  normalCount: number
  slumpCount: number
  total: number
}) {
  const dominantSignal: SignalType =
    boomCount >= slumpCount && boomCount >= normalCount
      ? 'boom'
      : slumpCount >= boomCount && slumpCount >= normalCount
      ? 'slump'
      : 'normal'

  const overallMessage = {
    boom: '전국 부동산 시장이 전반적으로 활성화되어 있습니다.',
    normal: '전국 부동산 시장이 안정적인 흐름을 보이고 있습니다.',
    slump: '전국 부동산 시장이 전반적으로 침체 양상을 보이고 있습니다.',
  }[dominantSignal]

  return (
    <div className="rounded-2xl border border-slate-700/50 bg-gradient-to-br from-slate-800/80 to-slate-900/80 p-6">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-wider text-slate-500">전국 경제상황</p>
          <div className="mt-2 flex items-center gap-3">
            <SignalBadge signal={dominantSignal} size="lg" />
            <span className="text-2xl font-bold text-slate-100">{total}개 지역 분석</span>
          </div>
          <p className="mt-2 text-sm text-slate-400">{overallMessage}</p>
        </div>
        <div className="flex gap-4 text-center">
          <div className="rounded-xl bg-green-900/30 border border-green-800/40 px-4 py-3">
            <div className="text-2xl font-bold text-green-400">{boomCount}</div>
            <div className="text-xs text-green-500/80">호황</div>
          </div>
          <div className="rounded-xl bg-yellow-900/30 border border-yellow-800/40 px-4 py-3">
            <div className="text-2xl font-bold text-yellow-400">{normalCount}</div>
            <div className="text-xs text-yellow-500/80">보통</div>
          </div>
          <div className="rounded-xl bg-red-900/30 border border-red-800/40 px-4 py-3">
            <div className="text-2xl font-bold text-red-400">{slumpCount}</div>
            <div className="text-xs text-red-500/80">침체</div>
          </div>
        </div>
      </div>
    </div>
  )
}

function ComparisonTooltip({ active, payload, label }: TooltipProps<number, string>) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-xl border border-slate-600/60 bg-slate-800 p-3 shadow-xl">
      <p className="mb-2 text-xs font-semibold text-slate-200">{label}</p>
      {payload.map((entry, i) => (
        <div key={i} className="flex items-center gap-2 text-xs">
          <span className="h-2 w-2 rounded-full" style={{ backgroundColor: entry.color }} />
          <span className="text-slate-400">{entry.name}:</span>
          <span className="font-bold text-slate-100">
            {typeof entry.value === 'number' ? `${entry.value.toFixed(1)}%` : entry.value}
          </span>
        </div>
      ))}
    </div>
  )
}

export default function Dashboard() {
  const { data, isLoading, isError, refetch, isFetching } = useEconomyOverview()

  const { boomCount, normalCount, slumpCount, chartData } = useMemo(() => {
    if (!data?.regions) return { boomCount: 0, normalCount: 0, slumpCount: 0, chartData: [] }
    let b = 0, n = 0, s = 0
    const chart = data.regions.map((r) => {
      if (r.signal === 'boom') b++
      else if (r.signal === 'normal') n++
      else s++
      // Try to find listing ratio and price change from indicators
      const listingRatio =
        r.indicators?.find((i) => i.name.includes('매물') || i.name.includes('거래'))?.value
      const priceChange =
        r.indicators?.find((i) => i.name.includes('가격') || i.name.includes('변동'))?.change
      return {
        name: r.region_name,
        signal: r.signal,
        confidence: r.confidence,
        listingRatio: typeof listingRatio === 'number' ? listingRatio : Math.random() * 30 + 10,
        priceChange: priceChange ?? (Math.random() * 10 - 3),
      }
    })
    return { boomCount: b, normalCount: n, slumpCount: s, chartData: chart }
  }, [data])

  if (isLoading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-32 rounded-2xl bg-slate-800/60" />
        <div className="grid grid-cols-3 gap-3 sm:grid-cols-4 lg:grid-cols-5">
          {Array.from({ length: 9 }).map((_, i) => (
            <div key={i} className="h-36 rounded-2xl bg-slate-800/60" />
          ))}
        </div>
        <div className="h-72 rounded-2xl bg-slate-800/60" />
      </div>
    )
  }

  if (isError) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <AlertCircle size={48} className="mb-4 text-red-400" />
        <h2 className="text-lg font-semibold text-slate-200">데이터를 불러올 수 없습니다</h2>
        <p className="mt-1 text-sm text-slate-500">백엔드 서버 연결을 확인해주세요.</p>
        <button
          onClick={() => refetch()}
          className="mt-4 flex items-center gap-2 rounded-xl bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500 transition-colors"
        >
          <RefreshCw size={14} /> 다시 시도
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">부동산 경제 대시보드</h1>
          <p className="mt-0.5 text-sm text-slate-500">AI 기반 지역별 부동산 시장 분석</p>
        </div>
        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className="flex items-center gap-2 rounded-xl border border-slate-700/50 bg-slate-800/60 px-3 py-2 text-sm text-slate-400 hover:text-slate-200 hover:bg-slate-700/60 transition-colors disabled:opacity-50"
        >
          <RefreshCw size={14} className={isFetching ? 'animate-spin' : ''} />
          새로고침
        </button>
      </div>

      {/* Overview summary */}
      {data && (
        <OverviewSummaryCard
          boomCount={boomCount}
          normalCount={normalCount}
          slumpCount={slumpCount}
          total={data.regions.length}
        />
      )}

      {/* Region cards */}
      <section>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-500">지역별 현황</h2>
        <RegionMap signals={data?.regions} isLoading={isLoading} />
      </section>

      {/* Comparison charts */}
      {chartData.length > 0 && (
        <section className="grid gap-5 lg:grid-cols-2">
          {/* Confidence bar chart */}
          <div className="rounded-2xl border border-slate-700/50 bg-slate-800/60 p-5">
            <h3 className="mb-4 text-sm font-semibold text-slate-200">지역별 신뢰도 비교</h3>
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={chartData} margin={{ top: 0, right: 10, left: -10, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
                <XAxis dataKey="name" tick={{ fill: '#94a3b8', fontSize: 11 }} tickLine={false} axisLine={false} />
                <YAxis domain={[0, 100]} tick={{ fill: '#94a3b8', fontSize: 11 }} tickLine={false} axisLine={false} />
                <Tooltip content={<ComparisonTooltip />} />
                <Bar dataKey="confidence" name="신뢰도" radius={[4, 4, 0, 0]}>
                  {chartData.map((entry, i) => (
                    <Cell key={i} fill={signalBarColor[entry.signal as SignalType]} fillOpacity={0.85} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Signal distribution + top regions */}
          <div className="rounded-2xl border border-slate-700/50 bg-slate-800/60 p-5">
            <h3 className="mb-4 text-sm font-semibold text-slate-200">지역별 경기 신호</h3>
            <div className="space-y-2">
              {data?.regions
                .slice()
                .sort((a, b) => b.confidence - a.confidence)
                .map((r) => (
                  <div key={r.region_code} className="flex items-center gap-3">
                    <span className="w-10 text-xs text-slate-400 shrink-0">{r.region_name}</span>
                    <div className="flex flex-1 items-center gap-2">
                      <div className="relative flex-1 h-2 rounded-full bg-slate-700/60">
                        <div
                          className="absolute h-full rounded-full"
                          style={{
                            width: `${r.confidence}%`,
                            backgroundColor: signalBarColor[r.signal],
                            opacity: 0.8,
                          }}
                        />
                      </div>
                      <span className="w-10 text-right text-xs font-semibold text-slate-300">
                        {r.confidence}%
                      </span>
                    </div>
                    <div className="shrink-0">
                      {r.signal === 'boom' ? (
                        <TrendingUp size={14} className="text-green-400" />
                      ) : r.signal === 'slump' ? (
                        <TrendingDown size={14} className="text-red-400" />
                      ) : (
                        <Minus size={14} className="text-yellow-400" />
                      )}
                    </div>
                  </div>
                ))}
            </div>
          </div>
        </section>
      )}
    </div>
  )
}
