import type { SignalType, IndicatorData } from '@/types'
import { TrendingUp, TrendingDown, Minus } from 'lucide-react'

interface SignalBadgeProps {
  signal: SignalType
  size?: 'sm' | 'md' | 'lg'
}

export function SignalBadge({ signal, size = 'md' }: SignalBadgeProps) {
  const config = {
    boom: { label: '호황', emoji: '🟢', bg: 'bg-green-900/60', text: 'text-green-400', border: 'border-green-700/50' },
    normal: { label: '보통', emoji: '🟡', bg: 'bg-yellow-900/60', text: 'text-yellow-400', border: 'border-yellow-700/50' },
    slump: { label: '침체', emoji: '🔴', bg: 'bg-red-900/60', text: 'text-red-400', border: 'border-red-700/50' },
  }
  const sizeClass = {
    sm: 'text-xs px-2 py-0.5',
    md: 'text-sm px-3 py-1',
    lg: 'text-base px-4 py-1.5',
  }
  const { label, emoji, bg, text, border } = config[signal]

  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border font-semibold ${bg} ${text} ${border} ${sizeClass[size]}`}>
      <span>{emoji}</span>
      <span>{label}</span>
    </span>
  )
}

interface ConfidenceBarProps {
  confidence: number
  signal: SignalType
}

export function ConfidenceBar({ confidence, signal }: ConfidenceBarProps) {
  const color = {
    boom: 'bg-green-500',
    normal: 'bg-yellow-500',
    slump: 'bg-red-500',
  }[signal]

  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs text-slate-400">
        <span>신뢰도</span>
        <span className="font-semibold text-slate-200">{confidence}%</span>
      </div>
      <div className="h-1.5 w-full rounded-full bg-slate-700">
        <div
          className={`h-full rounded-full confidence-bar ${color}`}
          style={{ width: `${confidence}%` }}
        />
      </div>
    </div>
  )
}

interface TrendIconProps {
  trend?: 'up' | 'down' | 'stable'
  change?: number
}

function TrendIcon({ trend, change }: TrendIconProps) {
  if (trend === 'up' || (change !== undefined && change > 0)) {
    return <TrendingUp size={14} className="text-green-400 shrink-0" />
  }
  if (trend === 'down' || (change !== undefined && change < 0)) {
    return <TrendingDown size={14} className="text-red-400 shrink-0" />
  }
  return <Minus size={14} className="text-slate-500 shrink-0" />
}

interface IndicatorCardProps {
  indicator: IndicatorData
}

export function IndicatorCard({ indicator }: IndicatorCardProps) {
  const changeColor =
    indicator.change === undefined
      ? 'text-slate-400'
      : indicator.change > 0
      ? 'text-green-400'
      : indicator.change < 0
      ? 'text-red-400'
      : 'text-slate-400'

  return (
    <div className="rounded-xl border border-slate-700/50 bg-slate-800/60 p-4 card-hover">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-xs font-medium text-slate-400">{indicator.name}</span>
        <TrendIcon trend={indicator.trend} change={indicator.change} />
      </div>
      <div className="flex items-baseline gap-1.5">
        <span className="text-xl font-bold text-slate-100">
          {typeof indicator.value === 'number'
            ? indicator.value.toLocaleString()
            : indicator.value}
        </span>
        {indicator.unit && (
          <span className="text-sm text-slate-400">{indicator.unit}</span>
        )}
      </div>
      {indicator.change !== undefined && (
        <div className={`mt-1 text-xs font-medium ${changeColor}`}>
          {indicator.change > 0 ? '+' : ''}
          {indicator.change}% 전월 대비
        </div>
      )}
      {indicator.description && (
        <p className="mt-2 text-xs text-slate-500 leading-relaxed">{indicator.description}</p>
      )}
    </div>
  )
}

interface EconomyIndicatorProps {
  signal: SignalType
  confidence: number
  summary: string
  indicators?: IndicatorData[]
  regionName?: string
}

export default function EconomyIndicator({
  signal,
  confidence,
  summary,
  indicators,
  regionName,
}: EconomyIndicatorProps) {
  return (
    <div className="rounded-2xl border border-slate-700/50 bg-slate-800/80 p-6 space-y-4">
      <div className="flex items-center justify-between">
        {regionName && <h3 className="text-lg font-bold text-slate-100">{regionName}</h3>}
        <SignalBadge signal={signal} size="md" />
      </div>

      <ConfidenceBar confidence={confidence} signal={signal} />

      <p className="text-sm text-slate-300 leading-relaxed">{summary}</p>

      {indicators && indicators.length > 0 && (
        <div className="grid grid-cols-2 gap-3">
          {indicators.slice(0, 4).map((ind, i) => (
            <IndicatorCard key={i} indicator={ind} />
          ))}
        </div>
      )}
    </div>
  )
}
