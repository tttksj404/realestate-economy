import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  type TooltipProps,
} from 'recharts'
import type { PriceData } from '@/types'

interface PriceChartProps {
  data: PriceData[]
  title?: string
}

function formatPrice(value: number): string {
  if (value >= 10000) {
    return `${(value / 10000).toFixed(1)}억`
  }
  return `${value.toLocaleString()}만`
}

function CustomTooltip({ active, payload, label }: TooltipProps<number, string>) {
  if (!active || !payload || payload.length === 0) return null

  return (
    <div className="rounded-xl border border-slate-600/60 bg-slate-800 p-3 shadow-xl">
      <p className="mb-2 text-xs font-semibold text-slate-300">{label}</p>
      {payload.map((entry, i) => (
        <div key={i} className="flex items-center gap-2 text-xs">
          <span className="inline-block h-2 w-2 rounded-full" style={{ backgroundColor: entry.color }} />
          <span className="text-slate-400">{entry.name}:</span>
          <span className="font-bold text-slate-100">
            {typeof entry.value === 'number' ? formatPrice(entry.value) : entry.value}
          </span>
        </div>
      ))}
    </div>
  )
}

export default function PriceChart({ data, title = '가격 추이' }: PriceChartProps) {
  if (!data || data.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center rounded-xl border border-slate-700/50 bg-slate-800/40">
        <p className="text-sm text-slate-500">데이터가 없습니다.</p>
      </div>
    )
  }

  const formatted = data.map((d) => ({
    ...d,
    period: d.period,
    avg_price: d.avg_price,
    median_price: d.median_price,
  }))

  return (
    <div className="rounded-2xl border border-slate-700/50 bg-slate-800/60 p-5">
      <h3 className="mb-4 text-sm font-semibold text-slate-200">{title}</h3>
      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={formatted} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
          <XAxis
            dataKey="period"
            tick={{ fill: '#94a3b8', fontSize: 11 }}
            tickLine={false}
            axisLine={{ stroke: '#334155' }}
          />
          <YAxis
            tickFormatter={formatPrice}
            tick={{ fill: '#94a3b8', fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            width={55}
          />
          <Tooltip content={<CustomTooltip />} />
          <Legend
            wrapperStyle={{ fontSize: '12px', color: '#94a3b8', paddingTop: '12px' }}
          />
          <Line
            type="monotone"
            dataKey="avg_price"
            name="평균가"
            stroke="#60a5fa"
            strokeWidth={2}
            dot={{ fill: '#60a5fa', r: 3, strokeWidth: 0 }}
            activeDot={{ r: 5, strokeWidth: 0 }}
          />
          <Line
            type="monotone"
            dataKey="median_price"
            name="중간가"
            stroke="#a78bfa"
            strokeWidth={2}
            strokeDasharray="5 3"
            dot={{ fill: '#a78bfa', r: 3, strokeWidth: 0 }}
            activeDot={{ r: 5, strokeWidth: 0 }}
          />
        </LineChart>
      </ResponsiveContainer>

      {/* Transaction count bar */}
      <div className="mt-3 border-t border-slate-700/50 pt-3">
        <p className="mb-2 text-xs text-slate-500">거래량</p>
        <div className="flex items-end gap-1" style={{ height: 40 }}>
          {formatted.map((d, i) => {
            const max = Math.max(...formatted.map((x) => x.transaction_count))
            const height = max > 0 ? (d.transaction_count / max) * 100 : 0
            return (
              <div key={i} className="flex flex-1 flex-col items-center gap-1">
                <div
                  className="w-full rounded-sm bg-slate-600/60"
                  style={{ height: `${height}%`, minHeight: 2 }}
                  title={`${d.period}: ${d.transaction_count}건`}
                />
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
