import type { PriceData } from '@/types'
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  type TooltipProps,
  XAxis,
  YAxis,
} from 'recharts'

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
  if (!active || !payload?.length) {
    return null
  }

  return (
    <div className="rounded-xl border border-slate-600/60 bg-slate-800 p-3 shadow-xl">
      <p className="mb-2 text-xs font-semibold text-slate-300">{label}</p>
      {payload.map((entry) => (
        <div key={`${entry.dataKey}-${entry.color}`} className="flex items-center gap-2 text-xs">
          <span className="h-2 w-2 rounded-full" style={{ backgroundColor: entry.color }} />
          <span className="text-slate-400">{entry.name}</span>
          <span className="font-semibold text-slate-100">
            {typeof entry.value === 'number' ? formatPrice(entry.value) : entry.value}
          </span>
        </div>
      ))}
    </div>
  )
}

export default function PriceChart({ data, title = '가격 추이' }: PriceChartProps) {
  if (data.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center rounded-2xl border border-slate-700/50 bg-slate-800/60 text-sm text-slate-500">
        가격 데이터가 없습니다.
      </div>
    )
  }

  return (
    <div className="rounded-2xl border border-slate-700/50 bg-slate-800/60 p-5">
      <h3 className="mb-4 text-sm font-semibold text-slate-200">{title}</h3>
      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={data} margin={{ top: 5, right: 15, left: 0, bottom: 5 }}>
          <CartesianGrid stroke="#334155" strokeDasharray="3 3" />
          <XAxis dataKey="period" tick={{ fill: '#94a3b8', fontSize: 11 }} tickLine={false} axisLine={false} />
          <YAxis
            tick={{ fill: '#94a3b8', fontSize: 11 }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(value) => formatPrice(Number(value))}
            width={55}
          />
          <Tooltip content={<CustomTooltip />} />
          <Legend wrapperStyle={{ fontSize: '12px', color: '#94a3b8' }} />
          <Line type="monotone" dataKey="avg_price" name="평균가" stroke="#60a5fa" strokeWidth={2} dot={false} />
          <Line
            type="monotone"
            dataKey="median_price"
            name="중간가"
            stroke="#34d399"
            strokeWidth={2}
            strokeDasharray="5 4"
            dot={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

