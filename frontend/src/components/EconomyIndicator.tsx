import type { IndicatorData, SignalType } from '@/types'
import { Minus, TrendingDown, TrendingUp } from 'lucide-react'

interface SignalBadgeProps {
  signal: SignalType
  size?: 'sm' | 'md' | 'lg'
}

const signalConfig = {
  boom: { label: '호황', bg: 'bg-emerald-900/60', text: 'text-emerald-300', border: 'border-emerald-700/50' },
  normal: { label: '보통', bg: 'bg-amber-900/60', text: 'text-amber-300', border: 'border-amber-700/50' },
  slump: { label: '침체', bg: 'bg-rose-900/60', text: 'text-rose-300', border: 'border-rose-700/50' },
} as const

const sizeClass = {
  sm: 'px-2 py-0.5 text-xs',
  md: 'px-3 py-1 text-sm',
  lg: 'px-4 py-1.5 text-base',
} as const

export function SignalBadge({ signal, size = 'md' }: SignalBadgeProps) {
  const config = signalConfig[signal]
  return (
    <span
      className={`inline-flex items-center rounded-full border font-semibold ${sizeClass[size]} ${config.bg} ${config.text} ${config.border}`}
    >
      {config.label}
    </span>
  )
}

interface ConfidenceBarProps {
  confidence: number
  signal: SignalType
}

export function ConfidenceBar({ confidence, signal }: ConfidenceBarProps) {
  const barColor = {
    boom: 'bg-emerald-500',
    normal: 'bg-amber-500',
    slump: 'bg-rose-500',
  }[signal]

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-xs text-slate-400">
        <span>신뢰도</span>
        <span className="font-semibold text-slate-200">{confidence}%</span>
      </div>
      <div className="h-2 w-full rounded-full bg-slate-700/70">
        <div className={`h-full rounded-full transition-all duration-700 ${barColor}`} style={{ width: `${confidence}%` }} />
      </div>
    </div>
  )
}

function TrendIcon({ trend, change }: { trend?: 'up' | 'down' | 'stable'; change?: number }) {
  if (trend === 'up' || (change ?? 0) > 0) {
    return <TrendingUp size={14} className="text-emerald-400" />
  }
  if (trend === 'down' || (change ?? 0) < 0) {
    return <TrendingDown size={14} className="text-rose-400" />
  }
  return <Minus size={14} className="text-slate-500" />
}

export function IndicatorCard({ indicator }: { indicator: IndicatorData }) {
  const changeTextClass =
    indicator.change == null
      ? 'text-slate-400'
      : indicator.change > 0
      ? 'text-emerald-400'
      : indicator.change < 0
      ? 'text-rose-400'
      : 'text-slate-400'

  return (
    <div className="rounded-xl border border-slate-700/50 bg-slate-800/70 p-4">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-xs text-slate-400">{indicator.name}</span>
        <TrendIcon trend={indicator.trend} change={indicator.change} />
      </div>
      <div className="flex items-end gap-1">
        <span className="text-xl font-bold text-slate-100">
          {typeof indicator.value === 'number' ? indicator.value.toLocaleString() : indicator.value}
        </span>
        {indicator.unit && <span className="pb-0.5 text-xs text-slate-400">{indicator.unit}</span>}
      </div>
      {indicator.change != null && (
        <p className={`mt-1 text-xs ${changeTextClass}`}>
          {indicator.change > 0 ? '+' : ''}
          {indicator.change}%
        </p>
      )}
      {indicator.description && <p className="mt-2 text-xs text-slate-500">{indicator.description}</p>}
    </div>
  )
}

